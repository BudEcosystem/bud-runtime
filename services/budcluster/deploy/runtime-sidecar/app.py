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
# Engine type determines which metrics to parse (vllm, sglang, latentbud/infinity)
ENGINE_TYPE = os.environ.get("ENGINE_TYPE", "vllm").lower()

# --- Log configuration ---
logging.info(
    f"Configuration: ENGINE_METRICS_URL: {ENGINE_METRICS_URL}, LISTEN_PORT: {LISTEN_PORT}, "
    f"SCRAPE_INTERVAL_SECONDS: {SCRAPE_INTERVAL_SECONDS}, CALCULATION_WINDOW_SECONDS: {CALCULATION_WINDOW_SECONDS}, "
    f"ENGINE_TYPE: {ENGINE_TYPE}"
)

# --- Create a custom registry ---
registry = CollectorRegistry()

# --- Data storage and Prometheus metric remain the same ---
# Store (timestamp, metrics_dict) tuples
time_series_data = collections.deque()

# --- Register gauges with the custom registry ---
# vLLM/SGLang metrics
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
)

# vLLM/SGLang queue metrics (pass-through gauges, no averaging needed)
NUM_REQUESTS_WAITING_GAUGE = Gauge(
    "bud:num_requests_waiting",
    "Number of requests waiting in the queue",
    registry=registry,
)
NUM_REQUESTS_RUNNING_GAUGE = Gauge(
    "bud:num_requests_running",
    "Number of requests currently being processed",
    registry=registry,
)

# Infinity/LatentBud embedding metrics
AVG_INFINITY_LATENCY_GAUGE = Gauge(
    "bud:infinity_embedding_latency_seconds_average",
    "Calculated average embedding latency over the window",
    registry=registry,
)
INFINITY_QUEUE_DEPTH_GAUGE = Gauge(
    "bud:infinity_queue_depth",
    "Current queue depth for embedding requests",
    registry=registry,
)

# Add a variable to store the previous metrics
previous_metrics = None


def scrape_vllm_metrics(content: str) -> tuple:
    """Parse vLLM/SGLang metrics from Prometheus content.

    Returns:
        Tuple of (current_metrics dict, found_metrics set)
    """
    current_metrics = {
        "time_to_first_token": {"sum": 0.0, "count": 0.0},
        "e2e_request_latency": {"sum": 0.0, "count": 0.0},
        "time_per_output_token": {"sum": 0.0, "count": 0.0},
        "gpu_cache_usage": 0.0,
        "num_requests_waiting": 0.0,
        "num_requests_running": 0.0,
    }
    found_metrics = set()

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

        elif family.name in ["vllm:gpu_cache_usage_perc", "vllm:kv_cache_usage_perc"]:
            # Note: vLLM uses kv_cache_usage_perc (KV cache utilization)
            for sample in family.samples:
                current_metrics["gpu_cache_usage"] = sample.value
                found_metrics.add("gpu_cache_usage")

        elif family.name == "vllm:num_requests_waiting":
            for sample in family.samples:
                current_metrics["num_requests_waiting"] = sample.value
                found_metrics.add("num_requests_waiting")

        elif family.name == "vllm:num_requests_running":
            for sample in family.samples:
                current_metrics["num_requests_running"] = sample.value
                found_metrics.add("num_requests_running")

    return current_metrics, found_metrics


def scrape_infinity_metrics(content: str) -> tuple:
    """Parse Infinity/LatentBud embedding metrics from Prometheus content.

    Returns:
        Tuple of (current_metrics dict, found_metrics set)
    """
    current_metrics = {
        "infinity_embedding_latency": {"sum": 0.0, "count": 0.0},
        "infinity_queue_depth": 0.0,
    }
    found_metrics = set()

    for family in text_string_to_metric_families(content):
        if family.name == "infinity_embedding_latency_seconds":
            # This is a histogram - extract sum and count
            for sample in family.samples:
                if sample.name.endswith("_sum"):
                    current_metrics["infinity_embedding_latency"]["sum"] = sample.value
                    found_metrics.add("infinity_embedding_latency_sum")
                elif sample.name.endswith("_count"):
                    current_metrics["infinity_embedding_latency"]["count"] = sample.value
                    found_metrics.add("infinity_embedding_latency_count")

        elif family.name == "infinity_queue_depth":
            # This is a gauge - take the value directly
            for sample in family.samples:
                current_metrics["infinity_queue_depth"] = sample.value
                found_metrics.add("infinity_queue_depth")

    return current_metrics, found_metrics


def calculate_vllm_deltas(current_metrics: dict, prev_metrics: dict) -> dict:
    """Calculate delta metrics for vLLM between scrapes.

    Note: num_requests_waiting and num_requests_running are instantaneous gauges
    and are handled separately (not included in deltas/windowing).
    """
    return {
        "time_to_first_token": {
            "sum": current_metrics["time_to_first_token"]["sum"] - prev_metrics["time_to_first_token"]["sum"],
            "count": current_metrics["time_to_first_token"]["count"] - prev_metrics["time_to_first_token"]["count"],
        },
        "e2e_request_latency": {
            "sum": current_metrics["e2e_request_latency"]["sum"] - prev_metrics["e2e_request_latency"]["sum"],
            "count": current_metrics["e2e_request_latency"]["count"] - prev_metrics["e2e_request_latency"]["count"],
        },
        "time_per_output_token": {
            "sum": current_metrics["time_per_output_token"]["sum"] - prev_metrics["time_per_output_token"]["sum"],
            "count": current_metrics["time_per_output_token"]["count"]
            - prev_metrics["time_per_output_token"]["count"],
        },
        "gpu_cache_usage": current_metrics["gpu_cache_usage"],
    }


def calculate_infinity_deltas(current_metrics: dict, prev_metrics: dict) -> dict:
    """Calculate delta metrics for Infinity between scrapes."""
    return {
        "infinity_embedding_latency": {
            "sum": current_metrics["infinity_embedding_latency"]["sum"]
            - prev_metrics["infinity_embedding_latency"]["sum"],
            "count": current_metrics["infinity_embedding_latency"]["count"]
            - prev_metrics["infinity_embedding_latency"]["count"],
        },
        "infinity_queue_depth": current_metrics["infinity_queue_depth"],
    }


def update_vllm_gauges(window_totals: dict, latest_metrics: dict = None):
    """Update vLLM Prometheus gauges with calculated averages.

    Args:
        window_totals: Aggregated metrics over the window (for histograms)
        latest_metrics: Latest instantaneous metrics (for gauges like queue depth)
    """
    for metric_name, totals in window_totals.items():
        average = 0.0
        if totals["count"] > 0:
            average = totals["sum"] / totals["count"]

        if metric_name == "time_to_first_token":
            AVG_TTFT_GAUGE.set(average)
        elif metric_name == "e2e_request_latency":
            AVG_E2E_LATENCY_GAUGE.set(average)
        elif metric_name == "time_per_output_token":
            AVG_TPOT_GAUGE.set(average)
        elif metric_name == "gpu_cache_usage":
            GPU_CACHE_USAGE_GAUGE.set(average)

    # Set instantaneous gauge metrics (not averaged - use latest value)
    if latest_metrics:
        NUM_REQUESTS_WAITING_GAUGE.set(latest_metrics.get("num_requests_waiting", 0))
        NUM_REQUESTS_RUNNING_GAUGE.set(latest_metrics.get("num_requests_running", 0))

    logging.info(
        f"Window averages: TTFT={AVG_TTFT_GAUGE._value.get()}, E2E_LATENCY={AVG_E2E_LATENCY_GAUGE._value.get()}, "
        f"TPOT={AVG_TPOT_GAUGE._value.get()}, GPU_CACHE_USAGE={GPU_CACHE_USAGE_GAUGE._value.get()}, "
        f"NUM_REQ_WAITING={NUM_REQUESTS_WAITING_GAUGE._value.get()}, NUM_REQ_RUNNING={NUM_REQUESTS_RUNNING_GAUGE._value.get()}"
    )


def update_infinity_gauges(window_totals: dict, latest_metrics: dict = None):
    """Update Infinity Prometheus gauges with calculated averages."""
    for metric_name, totals in window_totals.items():
        average = 0.0
        if metric_name == "infinity_queue_depth":
            # Queue depth is a gauge, use latest value (already averaged in window)
            if totals["count"] > 0:
                average = totals["sum"] / totals["count"]
            INFINITY_QUEUE_DEPTH_GAUGE.set(average)
        elif metric_name == "infinity_embedding_latency":
            # Embedding latency is a histogram, calculate average
            if totals["count"] > 0:
                average = totals["sum"] / totals["count"]
            AVG_INFINITY_LATENCY_GAUGE.set(average)

    logging.info(
        f"Window averages: INFINITY_LATENCY={AVG_INFINITY_LATENCY_GAUGE._value.get()}, "
        f"INFINITY_QUEUE_DEPTH={INFINITY_QUEUE_DEPTH_GAUGE._value.get()}"
    )


def get_vllm_window_totals() -> dict:
    """Get initial window totals structure for vLLM metrics."""
    return {
        "time_to_first_token": {"sum": 0.0, "count": 0.0},
        "e2e_request_latency": {"sum": 0.0, "count": 0.0},
        "time_per_output_token": {"sum": 0.0, "count": 0.0},
        "gpu_cache_usage": {"sum": 0.0, "count": 0},
        # Note: num_requests_waiting and num_requests_running are instantaneous
        # gauges, not windowed - they're handled separately with latest values
    }


def get_infinity_window_totals() -> dict:
    """Get initial window totals structure for Infinity metrics."""
    return {
        "infinity_embedding_latency": {"sum": 0.0, "count": 0.0},
        "infinity_queue_depth": {"sum": 0.0, "count": 0},
    }


# --- The scraping and processing logic ---
def scrape_and_process():
    """Scrapes engine metrics, updates data, and calculates rolling window average."""
    global time_series_data, previous_metrics
    try:
        response = requests.get(ENGINE_METRICS_URL, timeout=5)
        response.raise_for_status()
        content = response.text
        now = time.time()

        # Parse metrics based on engine type
        if ENGINE_TYPE in ["latentbud", "infinity"]:
            current_metrics, found_metrics = scrape_infinity_metrics(content)
            get_window_totals = get_infinity_window_totals
            calculate_deltas = calculate_infinity_deltas
            update_gauges = update_infinity_gauges
            # Only infinity_queue_depth is a gauge; infinity_embedding_latency is a histogram
            gauge_names = ["infinity_queue_depth"]
        else:
            # Default to vLLM/SGLang
            current_metrics, found_metrics = scrape_vllm_metrics(content)
            get_window_totals = get_vllm_window_totals
            calculate_deltas = calculate_vllm_deltas
            update_gauges = update_vllm_gauges
            gauge_names = ["gpu_cache_usage"]
            # Note: num_requests_waiting/running are instantaneous, handled separately

        # Calculate delta metrics if we have previous values
        if previous_metrics is not None:
            delta_metrics = calculate_deltas(current_metrics, previous_metrics)

            if found_metrics:
                time_series_data.append((now, delta_metrics))
            else:
                logging.warning("No relevant metrics found in this scrape.")

            # Prune old data points
            cutoff_time = now - CALCULATION_WINDOW_SECONDS
            while time_series_data and time_series_data[0][0] < cutoff_time:
                time_series_data.popleft()

            # Calculate window averages
            window_totals = get_window_totals()

            # Sum up the deltas in the window
            for _, metrics in time_series_data:
                for metric_name, data in metrics.items():
                    if metric_name in gauge_names:
                        # Gauge metrics - store value directly
                        window_totals[metric_name]["sum"] += data
                        window_totals[metric_name]["count"] += 1
                    else:
                        # Histogram metrics - store sum and count
                        window_totals[metric_name]["sum"] += data["sum"]
                        window_totals[metric_name]["count"] += data["count"]

            # Update Prometheus gauges (pass current_metrics for instantaneous values)
            update_gauges(window_totals, current_metrics)

        # Store current metrics for next iteration
        previous_metrics = current_metrics

    except requests.exceptions.RequestException as e:
        logging.error(f"Error scraping {ENGINE_TYPE} metrics: {e}")
        # Set gauges to 0 on error based on engine type
        if ENGINE_TYPE in ["latentbud", "infinity"]:
            AVG_INFINITY_LATENCY_GAUGE.set(0.0)
            INFINITY_QUEUE_DEPTH_GAUGE.set(0.0)
        else:
            AVG_TTFT_GAUGE.set(0.0)
            AVG_E2E_LATENCY_GAUGE.set(0.0)
            AVG_TPOT_GAUGE.set(0.0)
            GPU_CACHE_USAGE_GAUGE.set(0.0)
            NUM_REQUESTS_WAITING_GAUGE.set(0.0)
            NUM_REQUESTS_RUNNING_GAUGE.set(0.0)
    except Exception:
        # Use logging.exception to include traceback for unexpected errors
        logging.exception("An unexpected error occurred:")


def main():
    """Start the metrics server and scraping loop.

    This function initializes the Prometheus HTTP server for exposing metrics
    and starts the continuous scraping loop that collects metrics from the
    inference engine and calculates rolling averages.
    """
    # Start the Prometheus HTTP server for the intermediary's metrics
    logging.info(f"Starting intermediary metrics server on port {LISTEN_PORT}")
    # --- Pass the custom registry to start_http_server ---
    start_http_server(LISTEN_PORT, registry=registry)

    # Start the scraping loop
    logging.info(
        f"Starting scraping loop for {ENGINE_TYPE} with interval {SCRAPE_INTERVAL_SECONDS}s "
        f"and window {CALCULATION_WINDOW_SECONDS}s"
    )
    while True:
        scrape_and_process()
        time.sleep(SCRAPE_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
