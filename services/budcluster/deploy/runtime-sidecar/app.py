# This is a simplified conceptual example. Production code needs more robust error handling and configuration validation.
import collections
import logging  # Import the logging module
import os  # Import the os module to access environment variables
import time

import requests
from prometheus_client import CollectorRegistry, Gauge, start_http_server
from prometheus_client.parser import text_string_to_metric_families  # Corrected import path


# --- Configure Logging ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# --- Configuration loaded from environment variables ---
# Use os.environ.get() to read variables, providing default values if they aren't set.
# Remember to convert string environment variable values to the correct types (int, float).

ENGINE_METRICS_URL = os.environ.get("ENGINE_METRICS_URL", "http://localhost:8000/metrics")
LISTEN_PORT = int(os.environ.get("LISTEN_PORT", "9090"))  # Convert port to integer
# Convert interval to float first to handle milliseconds, then convert to integer if needed
SCRAPE_INTERVAL_SECONDS = float(os.environ.get("SCRAPE_INTERVAL_SECONDS", "10"))
CALCULATION_WINDOW_SECONDS = float(os.environ.get("CALCULATION_WINDOW_SECONDS", "300"))

# --- Log configuration ---
logging.info(
    f"Configuration: ENGINE_METRICS_URL: {ENGINE_METRICS_URL}, LISTEN_PORT: {LISTEN_PORT}, SCRAPE_INTERVAL_SECONDS: {SCRAPE_INTERVAL_SECONDS}, CALCULATION_WINDOW_SECONDS: {CALCULATION_WINDOW_SECONDS}"
)

# --- Create a custom registry ---
registry = CollectorRegistry()

# --- Data storage and Prometheus metric remain the same ---
# Store (timestamp, metrics_dict) tuples
time_series_data = collections.deque()

# --- Register gauges with the custom registry ---
AVG_TTFT_GAUGE = Gauge(
    "bud:time_to_first_token_seconds_average",
    "Calculated average time to first token over the window",
    registry=registry,
)
AVG_E2E_LATENCY_GAUGE = Gauge(
    "bud:e2e_request_latency_seconds_average", "Calculated average e2e latency over the window", registry=registry
)
AVG_TPOT_GAUGE = Gauge(
    "bud:time_per_output_token_seconds_average",
    "Calculated average time per output token over the window",
    registry=registry,
)
GPU_CACHE_USAGE_GAUGE = Gauge(
    "bud:gpu_cache_usage_perc_average", "Calculated average GPU cache usage over the window", registry=registry
)  # Renamed for clarity

# Add a variable to store the previous metrics
previous_metrics = None


# --- The scraping and processing logic ---
def scrape_and_process():
    """Scrapes vLLM metrics, updates data, and calculates rolling window average."""
    global time_series_data, previous_metrics
    try:
        response = requests.get(ENGINE_METRICS_URL, timeout=5)
        response.raise_for_status()
        content = response.text
        now = time.time()

        # Initialize metric values for this scrape
        current_metrics = {
            "time_to_first_token": {"sum": 0.0, "count": 0.0},
            "e2e_request_latency": {"sum": 0.0, "count": 0.0},
            "time_per_output_token": {"sum": 0.0, "count": 0.0},
            "gpu_cache_usage": 0.0,
        }
        found_metrics = set()

        # Parse the metrics content
        for family in text_string_to_metric_families(content):
            if family.name in [
                "vllm:time_to_first_token_seconds",
                "vllm:e2e_request_latency_seconds",
                "vllm:time_per_output_token_seconds",
            ]:
                metric_key = family.name.replace("vllm:", "").replace("_seconds", "")
                for sample in family.samples:
                    if sample.name.endswith("_sum"):
                        current_metrics[metric_key]["sum"] = sample.value
                        found_metrics.add(metric_key + "_sum")
                    elif sample.name.endswith("_count"):
                        current_metrics[metric_key]["count"] = sample.value
                        found_metrics.add(metric_key + "_count")

            elif family.name == "vllm:gpu_cache_usage_perc":
                for sample in family.samples:
                    current_metrics["gpu_cache_usage"] = sample.value
                    found_metrics.add("gpu_cache_usage")

        # Calculate delta metrics if we have previous values
        if previous_metrics is not None:
            delta_metrics = {
                "time_to_first_token": {
                    "sum": current_metrics["time_to_first_token"]["sum"]
                    - previous_metrics["time_to_first_token"]["sum"],
                    "count": current_metrics["time_to_first_token"]["count"]
                    - previous_metrics["time_to_first_token"]["count"],
                },
                "e2e_request_latency": {
                    "sum": current_metrics["e2e_request_latency"]["sum"]
                    - previous_metrics["e2e_request_latency"]["sum"],
                    "count": current_metrics["e2e_request_latency"]["count"]
                    - previous_metrics["e2e_request_latency"]["count"],
                },
                "time_per_output_token": {
                    "sum": current_metrics["time_per_output_token"]["sum"]
                    - previous_metrics["time_per_output_token"]["sum"],
                    "count": current_metrics["time_per_output_token"]["count"]
                    - previous_metrics["time_per_output_token"]["count"],
                },
                "gpu_cache_usage": current_metrics["gpu_cache_usage"],
            }

            if found_metrics:
                time_series_data.append((now, delta_metrics))
            else:
                logging.warning("No relevant metrics found in this scrape.")

            # Prune old data points
            cutoff_time = now - CALCULATION_WINDOW_SECONDS
            while time_series_data and time_series_data[0][0] < cutoff_time:
                time_series_data.popleft()

            # Calculate window averages
            window_totals = {
                "time_to_first_token": {"sum": 0.0, "count": 0.0},
                "e2e_request_latency": {"sum": 0.0, "count": 0.0},
                "time_per_output_token": {"sum": 0.0, "count": 0.0},
                "gpu_cache_usage": {"sum": 0.0, "count": 0},
            }

            # Sum up the deltas in the window
            for _, metrics in time_series_data:
                for metric_name, data in metrics.items():
                    if metric_name == "gpu_cache_usage":
                        window_totals[metric_name]["sum"] += data
                        window_totals[metric_name]["count"] += 1
                    else:
                        window_totals[metric_name]["sum"] += data["sum"]
                        window_totals[metric_name]["count"] += data["count"]

            # Calculate and set averages
            for metric_name, totals in window_totals.items():
                # Default to 0 instead of NaN
                average = 0.0
                # Calculate average only if count is positive
                if totals["count"] > 0:
                    average = totals["sum"] / totals["count"]

                # --- Always update the gauge ---
                if metric_name == "time_to_first_token":
                    AVG_TTFT_GAUGE.set(average)
                elif metric_name == "e2e_request_latency":
                    AVG_E2E_LATENCY_GAUGE.set(average)
                elif metric_name == "time_per_output_token":
                    AVG_TPOT_GAUGE.set(average)
                elif metric_name == "gpu_cache_usage":
                    GPU_CACHE_USAGE_GAUGE.set(average)

        logging.info(
            f"Window averages: TTFT={AVG_TTFT_GAUGE._value.get()}, E2E_LATENCY={AVG_E2E_LATENCY_GAUGE._value.get()}, TPOT={AVG_TPOT_GAUGE._value.get()}, GPU_CACHE_USAGE={GPU_CACHE_USAGE_GAUGE._value.get()}"
        )
        # Store current metrics for next iteration
        previous_metrics = current_metrics

    except requests.exceptions.RequestException as e:
        logging.error(f"Error scraping vLLM metrics: {e}")
        # Set gauges to 0 on error
        AVG_TTFT_GAUGE.set(0.0)
        AVG_E2E_LATENCY_GAUGE.set(0.0)
        AVG_TPOT_GAUGE.set(0.0)
        GPU_CACHE_USAGE_GAUGE.set(0.0)
    except Exception:
        # Use logging.exception to include traceback for unexpected errors
        logging.exception("An unexpected error occurred:")


def main():
    """Start the metrics server and scraping loop.

    This function initializes the Prometheus HTTP server for exposing metrics
    and starts the continuous scraping loop that collects metrics from vLLM
    and calculates rolling averages.
    """
    # Start the Prometheus HTTP server for the intermediary's metrics
    logging.info(f"Starting intermediary metrics server on port {LISTEN_PORT}")
    # --- Pass the custom registry to start_http_server ---
    start_http_server(LISTEN_PORT, registry=registry)

    # Start the scraping loop
    logging.info(
        f"Starting scraping loop with interval {SCRAPE_INTERVAL_SECONDS}s and window {CALCULATION_WINDOW_SECONDS}s"
    )
    while True:
        scrape_and_process()
        time.sleep(SCRAPE_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
