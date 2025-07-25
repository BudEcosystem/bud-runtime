from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

import aiohttp

from budapp.commons import logging


logger = logging.get_logger(__name__)


class ClusterMetricsFetcher:
    """Fetches cluster metrics from Prometheus."""

    def __init__(self, prometheus_url: str):
        """Initialize with Prometheus server URL."""
        self.prometheus_url = prometheus_url
        self.api_url = f"{prometheus_url}/api/v1"

    def _get_time_range_params(self, time_range: str, include_previous: bool = False) -> dict:
        """Get start and end timestamps based on time range."""
        now = datetime.now(timezone.utc)

        if time_range == "10min":
            start_time = now - timedelta(minutes=10)
            step = "30s"
            end_time = now
        elif time_range == "today":
            if include_previous:
                # For yesterday's comparison, get data from 24 hours ago
                start_time = now - timedelta(
                    days=1, hours=now.hour, minutes=now.minute, seconds=now.second, microseconds=now.microsecond
                )
                end_time = start_time + timedelta(days=1)
            else:
                # For today, start from midnight and end at current time
                start_time = now.replace(hour=0, minute=0, second=0, microsecond=0)
                end_time = now
            step = "5m"  # 1 hour for today's metrics
        elif time_range == "7days":
            start_time = now - timedelta(days=7)
            end_time = now
            step = "6h"  # 6 hours for weekly view
        elif time_range == "month":
            start_time = now - timedelta(days=30)
            end_time = now
            step = "1d"  # 1 day for monthly view
        else:
            start_time = now - timedelta(minutes=10)
            end_time = now
            step = "30s"

        return {"start": start_time.timestamp(), "end": end_time.timestamp(), "step": step}

    def _get_metric_queries(self, cluster_name: str) -> Dict[str, str]:
        """Get memory, CPU, storage, and network-related Prometheus queries."""
        return {
            "node_uname_info": f'node_uname_info{{cluster="{cluster_name}",job="node-exporter"}}',
            "memory_total": f'node_memory_MemTotal_bytes{{cluster="{cluster_name}",job="node-exporter"}}',
            "memory_available": f'node_memory_MemAvailable_bytes{{cluster="{cluster_name}",job="node-exporter"}}',
            "cpu_usage": f'(1 - avg by (instance) (irate(node_cpu_seconds_total{{cluster="{cluster_name}",mode="idle",job="node-exporter"}}[5m]))) * 100',
            "storage_total": f'node_filesystem_size_bytes{{cluster="{cluster_name}",mountpoint="/",job="node-exporter"}}',
            "storage_available": f'node_filesystem_avail_bytes{{cluster="{cluster_name}",mountpoint="/",job="node-exporter"}}',
            "network_in": f"""
            sum by (instance) (
                rate(node_network_receive_bytes_total{{
                    cluster="{cluster_name}",
                    device!~"lo|veth.*|docker.*|br.*|cni.*",
                    job="node-exporter"
                }}[5m])
            ) * 8
        """,
            "network_out": f"""
            sum by (instance) (
                rate(node_network_transmit_bytes_total{{
                    cluster="{cluster_name}",
                    device!~"lo|veth.*|docker.*|br.*|cni.*",
                    job="node-exporter"
                }}[5m])
            ) * 8
        """,
            "network_bandwidth": f"""
            sum by (instance) (
                rate(node_network_receive_bytes_total{{
                    cluster="{cluster_name}",
                    device!~"lo|veth.*|docker.*|br.*|cni.*",
                    job="node-exporter"
                }}[5m]) +
                rate(node_network_transmit_bytes_total{{
                    cluster="{cluster_name}",
                    device!~"lo|veth.*|docker.*|br.*|cni.*",
                    job="node-exporter"
                }}[5m])
            ) * 8
        """,
        }

    async def _fetch_metrics(self, session: aiohttp.ClientSession, query: str, time_params: dict) -> List[Dict]:
        """Fetch metrics from Prometheus."""
        try:
            logger.debug(f"Fetching metrics with query: {query}")
            logger.debug(f"Time params: {time_params}")

            # Add unit conversion to the query
            if "MemTotal" in query or "MemAvailable" in query or "filesystem" in query:
                query = f"({query}) / 1024 / 1024 / 1024"  # Convert bytes to GiB
            elif "network" in query:
                query = f"({query}) / 1024 / 1024"  # Convert to Mbps

            async with session.get(
                f"{self.api_url}/query_range",
                params={
                    "query": query,
                    "start": time_params["start"],
                    "end": time_params["end"],
                    "step": time_params["step"],
                },
                timeout=10,
            ) as response:
                response.raise_for_status()
                result = await response.json()
                logger.debug(
                    f"Got response data: {result.get('data', {}).get('result', [])[:2]}"
                )  # Log first 2 results as sample
                return result["data"]["result"]
        except Exception as e:
            logger.error(f"Failed to fetch metrics: {e}")
            logger.error(f"Full error details: {str(e)}")
            return []

    def _process_metrics(
        self, current_results: Dict[str, List], previous_results: Dict[str, List] = None
    ) -> Dict[str, Any]:
        """Process memory, CPU, storage, and network metrics results."""
        metrics = {
            "nodes": {},
            "cluster_summary": {
                "memory": {"total_gib": 0, "used_gib": 0, "available_gib": 0, "usage_percent": 0, "change_percent": 0},
                "cpu": {"usage_percent": 0, "change_percent": 0},
                "storage": {
                    "total_gib": 0,
                    "used_gib": 0,
                    "available_gib": 0,
                    "usage_percent": 0,
                    "change_percent": 0,
                },
                "power": {"total_watt": 0, "change_percent": 0},
                "network_in": {"inbound_mbps": 0, "change_percent": 0, "time_series": []},
                "network_out": {"outbound_mbps": 0, "change_percent": 0, "time_series": []},
                "network_bandwidth": {"total_mbps": 0, "change_percent": 0, "time_series": []},
            },
        }

        nodename_to_instance = {}
        try:
            for node_data in current_results.get("node_uname_info", []):
                if "metric" in node_data:
                    nodename = node_data["metric"].get("nodename")
                    instance = node_data["metric"].get("instance")
                    if nodename and instance:
                        nodename_to_instance[nodename] = instance
            logger.debug(f"Nodename to instance mapping: {nodename_to_instance}")
        except Exception as e:
            logger.error(f"Error creating nodename to instance mapping: {e}")

        # Get previous cluster usage if available
        previous_memory_usage = None
        previous_cpu_usage = None
        previous_storage_usage = None
        previous_network_in = None
        previous_network_out = None
        previous_power_usage = None
        if previous_results:
            if "power" in previous_results:
                previous_power = sum(float(node["values"][-1][1]) for node in previous_results["power"])
                if previous_power > 0:
                    previous_power_usage = round(((previous_power - previous_power) / previous_power) * 100, 2)

            if "memory_total" in previous_results and "memory_available" in previous_results:
                prev_total = sum(float(node["values"][-1][1]) for node in previous_results["memory_total"])
                prev_available = sum(float(node["values"][-1][1]) for node in previous_results["memory_available"])
                if prev_total > 0:
                    previous_memory_usage = round(((prev_total - prev_available) / prev_total) * 100, 2)

            if "cpu_usage" in previous_results and previous_results["cpu_usage"]:
                prev_cpu_values = [float(node["values"][-1][1]) for node in previous_results["cpu_usage"]]
                if prev_cpu_values:
                    previous_cpu_usage = round(sum(prev_cpu_values) / len(prev_cpu_values), 2)

            if "storage_total" in previous_results and "storage_available" in previous_results:
                prev_total = sum(float(node["values"][-1][1]) for node in previous_results["storage_total"])
                prev_available = sum(float(node["values"][-1][1]) for node in previous_results["storage_available"])
                if prev_total > 0:
                    previous_storage_usage = round(((prev_total - prev_available) / prev_total) * 100, 2)

            if "network_in" in previous_results and previous_results["network_in"]:
                prev_network_values = [float(node["values"][-1][1]) for node in previous_results["network_in"]]
                if prev_network_values:
                    previous_network_in = round(sum(prev_network_values), 2)

            if "network_out" in previous_results and previous_results["network_out"]:
                prev_network_values = [float(node["values"][-1][1]) for node in previous_results["network_out"]]
                if prev_network_values:
                    previous_network_out = round(sum(prev_network_values), 2)

        # Process metrics for each node
        processed_nodes = set()

        # Initialize metrics structure for a new node
        def init_node_metrics(instance):
            if instance not in metrics["nodes"]:
                metrics["nodes"][instance] = {
                    "memory": {},
                    "cpu": {"usage_percent": 0, "change_percent": 0},
                    "storage": {
                        "total_gib": 0,
                        "used_gib": 0,
                        "available_gib": 0,
                        "usage_percent": 0,
                        "change_percent": 0,
                    },
                    "power": {"total_watt": 0, "change_percent": 0},
                    "network_in": {"inbound_mbps": 0, "change_percent": 0, "time_series": []},
                    "network_out": {"outbound_mbps": 0, "change_percent": 0, "time_series": []},
                    "network_bandwidth": {"total_mbps": 0, "change_percent": 0, "time_series": []},
                }

        # Process Power Metrics
        if "power" in current_results:
            logger.debug(f"Power Metrics: {current_results['power']}")

            # [{'metric': {'instance': 'fl4u42'}, 'value': [1739776921.221, '1.0290890332632034']}, {'metric': {'instance': 'fl4u44'}, 'value': [1739776921.221, '1.0421553174477174']}]"
            for node_data in current_results["power"]:
                nodename = node_data["metric"]["instance"]
                instance = nodename_to_instance.get(nodename, nodename)
                processed_nodes.add(instance)
                init_node_metrics(instance)
                total_values = round(float(node_data["value"][1]), 2)

                logger.debug(f"Nodename: {nodename}, Instance: {instance}, Total Values: {total_values}")

                # Find previous power values for this node
                prev_power_values = None
                if previous_results and "power" in previous_results:
                    for prev_node in previous_results["power"]:
                        if prev_node["metric"]["instance"] == instance:
                            prev_power_values = round(float(prev_node["values"][-1][1]), 2)
                            break

                # Calculate power change percentage
                power_change_percent = 0
                if prev_power_values is not None:
                    power_change_percent = round(((total_values - prev_power_values) / prev_power_values) * 100, 2)
                else:
                    power_change_percent = 0

                metrics["nodes"][instance]["power"].update(
                    {
                        "total_watt": total_values,
                        "unit": "kWh",
                        "change_percent": power_change_percent,
                    }
                )

                metrics["cluster_summary"]["power"]["total_watt"] += total_values
                metrics["cluster_summary"]["power"]["unit"] = "kWh"

        # Process memory metrics
        if "memory_total" in current_results and "memory_available" in current_results:
            for node_data in current_results["memory_total"]:
                instance = node_data["metric"]["instance"]
                processed_nodes.add(instance)
                init_node_metrics(instance)
                total_values = node_data["values"]

                # Find corresponding available memory
                available_values = []
                for avail_data in current_results["memory_available"]:
                    if avail_data["metric"]["instance"] == instance:
                        available_values = avail_data["values"]
                        break

                # Process current memory values
                total = round(float(total_values[-1][1]), 2)
                available = round(float(available_values[-1][1]), 2) if available_values else 0
                used = round(total - available, 2)
                memory_usage_percent = round((used / total * 100), 2) if total > 0 else 0

                # Find previous day memory values for this node
                prev_memory_usage_percent = None
                if previous_results and "memory_total" in previous_results and "memory_available" in previous_results:
                    for prev_node in previous_results["memory_total"]:
                        if prev_node["metric"]["instance"] == instance:
                            prev_total = float(prev_node["values"][-1][1])
                            for prev_avail in previous_results["memory_available"]:
                                if prev_avail["metric"]["instance"] == instance:
                                    prev_available = float(prev_avail["values"][-1][1])
                                    prev_used = prev_total - prev_available
                                    prev_memory_usage_percent = (
                                        round((prev_used / prev_total * 100), 2) if prev_total > 0 else 0
                                    )
                                    break
                            break

                # Calculate memory change percentage
                memory_change_percent = 0
                if prev_memory_usage_percent is not None:
                    memory_change_percent = round(memory_usage_percent - prev_memory_usage_percent, 2)

                # Update node memory metrics
                metrics["nodes"][instance]["memory"].update(
                    {
                        "total_gib": total,
                        "used_gib": used,
                        "available_gib": available,
                        "usage_percent": memory_usage_percent,
                        "change_percent": memory_change_percent,
                    }
                )

                # Update cluster memory summary
                metrics["cluster_summary"]["memory"]["total_gib"] += total
                metrics["cluster_summary"]["memory"]["used_gib"] += used
                metrics["cluster_summary"]["memory"]["available_gib"] += available

        # Process CPU metrics
        if "cpu_usage" in current_results:
            for node_data in current_results["cpu_usage"]:
                instance = node_data["metric"]["instance"]
                processed_nodes.add(instance)
                init_node_metrics(instance)

                # Process current CPU values
                cpu_usage_percent = round(float(node_data["values"][-1][1]), 2)

                # Find previous day CPU values for this node
                prev_cpu_usage_percent = None
                if previous_results and "cpu_usage" in previous_results:
                    for prev_node in previous_results["cpu_usage"]:
                        if prev_node["metric"]["instance"] == instance:
                            prev_cpu_usage_percent = round(float(prev_node["values"][-1][1]), 2)
                            break

                # Calculate CPU change percentage
                cpu_change_percent = 0
                if prev_cpu_usage_percent is not None:
                    cpu_change_percent = round(cpu_usage_percent - prev_cpu_usage_percent, 2)

                # Update node CPU metrics
                metrics["nodes"][instance]["cpu"].update(
                    {"usage_percent": cpu_usage_percent, "change_percent": cpu_change_percent}
                )

        # Process storage metrics
        if "storage_total" in current_results and "storage_available" in current_results:
            for node_data in current_results["storage_total"]:
                instance = node_data["metric"]["instance"]
                processed_nodes.add(instance)
                init_node_metrics(instance)

                total_values = node_data["values"]

                # Find corresponding available storage
                available_values = []
                for avail_data in current_results["storage_available"]:
                    if avail_data["metric"]["instance"] == instance:
                        available_values = avail_data["values"]
                        break

                # Process current storage values
                total = round(float(total_values[-1][1]), 2)
                available = round(float(available_values[-1][1]), 2) if available_values else 0
                used = round(total - available, 2)
                storage_usage_percent = round((used / total * 100), 2) if total > 0 else 0

                # Find previous day storage values for this node
                prev_storage_usage_percent = None
                if (
                    previous_results
                    and "storage_total" in previous_results
                    and "storage_available" in previous_results
                ):
                    for prev_node in previous_results["storage_total"]:
                        if prev_node["metric"]["instance"] == instance:
                            prev_total = float(prev_node["values"][-1][1])
                            for prev_avail in previous_results["storage_available"]:
                                if prev_avail["metric"]["instance"] == instance:
                                    prev_available = float(prev_avail["values"][-1][1])
                                    prev_used = prev_total - prev_available
                                    prev_storage_usage_percent = (
                                        round((prev_used / prev_total * 100), 2) if prev_total > 0 else 0
                                    )
                                    break
                            break

                # Calculate storage change percentage
                storage_change_percent = 0
                if prev_storage_usage_percent is not None:
                    storage_change_percent = round(storage_usage_percent - prev_storage_usage_percent, 2)

                # Update node storage metrics
                metrics["nodes"][instance]["storage"].update(
                    {
                        "total_gib": total,
                        "used_gib": used,
                        "available_gib": available,
                        "usage_percent": storage_usage_percent,
                        "change_percent": storage_change_percent,
                    }
                )

                # Update cluster storage summary
                metrics["cluster_summary"]["storage"]["total_gib"] += total
                metrics["cluster_summary"]["storage"]["used_gib"] += used
                metrics["cluster_summary"]["storage"]["available_gib"] += available

        # Process network metrics
        if "network_in" in current_results:
            # Initialize time series data structure
            time_series_data = {}

            for node_data in current_results["network_in"]:
                instance = node_data["metric"]["instance"]
                processed_nodes.add(instance)
                init_node_metrics(instance)

                # Process all time series values
                for timestamp, value in node_data["values"]:
                    ts = int(timestamp)
                    if ts not in time_series_data:
                        time_series_data[ts] = 0
                    time_series_data[ts] += float(value)

                # Get current value for the node
                current_value = round(float(node_data["values"][-1][1]), 2)

                # Find previous day value for this node
                prev_value = None
                if previous_results and "network_in" in previous_results:
                    for prev_node in previous_results["network_in"]:
                        if prev_node["metric"]["instance"] == instance:
                            prev_value = round(float(prev_node["values"][-1][1]), 2)
                            break

                # Calculate change percentage
                change_percent = 0
                if prev_value is not None and prev_value > 0:
                    change_percent = round(((current_value - prev_value) / prev_value) * 100, 2)

                # Update node network metrics
                metrics["nodes"][instance]["network_in"].update(
                    {
                        "inbound_mbps": current_value,
                        "change_percent": change_percent,
                        "time_series": [
                            {"timestamp": int(ts), "value": round(float(val), 2)} for ts, val in node_data["values"]
                        ],
                    }
                )

            # Update cluster network summary
            if time_series_data:
                # Sort time series data by timestamp
                sorted_times = sorted(time_series_data.items())
                metrics["cluster_summary"]["network_in"]["time_series"] = [
                    {"timestamp": ts, "value": round(val, 2)} for ts, val in sorted_times
                ]

                # Current total inbound traffic
                current_total = round(time_series_data[sorted_times[-1][0]], 2)
                metrics["cluster_summary"]["network_in"]["inbound_mbps"] = current_total

                # Calculate change percentage for cluster
                if previous_network_in is not None and previous_network_in > 0:
                    change_percent = round(((current_total - previous_network_in) / previous_network_in) * 100, 2)
                    metrics["cluster_summary"]["network_in"]["change_percent"] = change_percent

        # Process network outbound metrics
        if "network_out" in current_results:
            # Initialize time series data structure
            time_series_data = {}

            for node_data in current_results["network_out"]:
                instance = node_data["metric"]["instance"]
                processed_nodes.add(instance)
                init_node_metrics(instance)

                # Process all time series values
                for timestamp, value in node_data["values"]:
                    ts = int(timestamp)
                    if ts not in time_series_data:
                        time_series_data[ts] = 0
                    time_series_data[ts] += float(value)

                # Get current value for the node
                current_value = round(float(node_data["values"][-1][1]), 2)

                # Find previous day value for this node
                prev_value = None
                if previous_results and "network_out" in previous_results:
                    for prev_node in previous_results["network_out"]:
                        if prev_node["metric"]["instance"] == instance:
                            prev_value = round(float(prev_node["values"][-1][1]), 2)
                            break

                # Calculate change percentage
                change_percent = 0
                if prev_value is not None and prev_value > 0:
                    change_percent = round(((current_value - prev_value) / prev_value) * 100, 2)

                # Update node network metrics
                metrics["nodes"][instance]["network_out"].update(
                    {
                        "outbound_mbps": current_value,
                        "change_percent": change_percent,
                        "time_series": [
                            {"timestamp": int(ts), "value": round(float(val), 2)} for ts, val in node_data["values"]
                        ],
                    }
                )

            # Update cluster network summary
            if time_series_data:
                # Sort time series data by timestamp
                sorted_times = sorted(time_series_data.items())
                metrics["cluster_summary"]["network_out"]["time_series"] = [
                    {"timestamp": ts, "value": round(val, 2)} for ts, val in sorted_times
                ]

                # Current total outbound traffic
                current_total = round(time_series_data[sorted_times[-1][0]], 2)
                metrics["cluster_summary"]["network_out"]["outbound_mbps"] = current_total

                # Calculate change percentage for cluster
                if previous_network_out is not None and previous_network_out > 0:
                    change_percent = round(((current_total - previous_network_out) / previous_network_out) * 100, 2)
                    metrics["cluster_summary"]["network_out"]["change_percent"] = change_percent

        # Process network bandwidth (total of in and out)
        if "network_bandwidth" in current_results:
            # Initialize time series data structure for total bandwidth
            bandwidth_time_series = {}

            for node_data in current_results["network_bandwidth"]:
                instance = node_data["metric"]["instance"]
                processed_nodes.add(instance)
                init_node_metrics(instance)

                # Process time series values
                for timestamp, value in node_data["values"]:
                    ts = int(timestamp)
                    if ts not in bandwidth_time_series:
                        bandwidth_time_series[ts] = 0.0
                    val = float(value)
                    bandwidth_time_series[ts] += val

                    # Update node time series
                    metrics["nodes"][instance]["network_bandwidth"]["time_series"].append(
                        {"timestamp": ts, "value": round(val, 2)}
                    )

                # Get current value for the node
                current_value = round(float(node_data["values"][-1][1]), 2)

                # Find previous day value for this node
                prev_value = None
                if previous_results and "network_bandwidth" in previous_results:
                    for prev_node in previous_results["network_bandwidth"]:
                        if prev_node["metric"]["instance"] == instance:
                            prev_value = round(float(prev_node["values"][-1][1]), 2)
                            break

                # Calculate change percentage
                change_percent = 0
                if prev_value is not None and prev_value > 0:
                    change_percent = round(((current_value - prev_value) / prev_value) * 100, 2)

                # Update node bandwidth metrics
                metrics["nodes"][instance]["network_bandwidth"].update(
                    {"total_mbps": current_value, "change_percent": change_percent}
                )

            # Update cluster bandwidth summary
            if bandwidth_time_series:
                # Sort time series data by timestamp
                sorted_times = sorted(bandwidth_time_series.items())
                metrics["cluster_summary"]["network_bandwidth"]["time_series"] = [
                    {"timestamp": ts, "value": round(val, 2)} for ts, val in sorted_times
                ]

                # Current total bandwidth
                current_total = round(bandwidth_time_series[sorted_times[-1][0]], 2)
                metrics["cluster_summary"]["network_bandwidth"]["total_mbps"] = current_total

                # Calculate previous total bandwidth
                prev_total = None
                if previous_results and "network_bandwidth" in previous_results:
                    prev_values = [float(node["values"][-1][1]) for node in previous_results["network_bandwidth"]]
                    if prev_values:
                        prev_total = round(sum(prev_values), 2)

                # Calculate change percentage for cluster
                if prev_total is not None and prev_total > 0:
                    change_percent = round(((current_total - prev_total) / prev_total) * 100, 2)
                    metrics["cluster_summary"]["network_bandwidth"]["change_percent"] = change_percent

        # Calculate cluster summaries
        if processed_nodes:
            # Calculate memory summary
            if metrics["cluster_summary"]["memory"]["total_gib"] > 0:
                metrics["cluster_summary"]["memory"]["total_gib"] = round(
                    metrics["cluster_summary"]["memory"]["total_gib"], 2
                )
                metrics["cluster_summary"]["memory"]["used_gib"] = round(
                    metrics["cluster_summary"]["memory"]["used_gib"], 2
                )
                metrics["cluster_summary"]["memory"]["available_gib"] = round(
                    metrics["cluster_summary"]["memory"]["available_gib"], 2
                )

                current_memory_usage = round(
                    (
                        metrics["cluster_summary"]["memory"]["used_gib"]
                        / metrics["cluster_summary"]["memory"]["total_gib"]
                        * 100
                    ),
                    2,
                )
                metrics["cluster_summary"]["memory"]["usage_percent"] = current_memory_usage

                if previous_memory_usage is not None:
                    metrics["cluster_summary"]["memory"]["change_percent"] = round(
                        current_memory_usage - previous_memory_usage, 2
                    )

            # Calculate power summary
            if "power" in current_results:
                current_power_values = [
                    metrics["nodes"][instance]["power"]["total_watt"] for instance in processed_nodes
                ]
                if current_power_values:
                    avg_power_usage = round(sum(current_power_values) / len(current_power_values), 2)
                    metrics["cluster_summary"]["power"]["total_watt"] = avg_power_usage

                    if previous_power_usage is not None:
                        metrics["cluster_summary"]["power"]["change_percent"] = round(
                            avg_power_usage - previous_power_usage, 2
                        )

            # Calculate CPU summary
            if "cpu_usage" in current_results:
                current_cpu_values = [
                    metrics["nodes"][instance]["cpu"]["usage_percent"] for instance in processed_nodes
                ]
                if current_cpu_values:
                    avg_cpu_usage = round(sum(current_cpu_values) / len(current_cpu_values), 2)
                    metrics["cluster_summary"]["cpu"]["usage_percent"] = avg_cpu_usage

                    if previous_cpu_usage is not None:
                        metrics["cluster_summary"]["cpu"]["change_percent"] = round(
                            avg_cpu_usage - previous_cpu_usage, 2
                        )

            # Calculate storage summary
            if metrics["cluster_summary"]["storage"]["total_gib"] > 0:
                metrics["cluster_summary"]["storage"]["total_gib"] = round(
                    metrics["cluster_summary"]["storage"]["total_gib"], 2
                )
                metrics["cluster_summary"]["storage"]["used_gib"] = round(
                    metrics["cluster_summary"]["storage"]["used_gib"], 2
                )
                metrics["cluster_summary"]["storage"]["available_gib"] = round(
                    metrics["cluster_summary"]["storage"]["available_gib"], 2
                )

                current_storage_usage = round(
                    (
                        metrics["cluster_summary"]["storage"]["used_gib"]
                        / metrics["cluster_summary"]["storage"]["total_gib"]
                        * 100
                    ),
                    2,
                )
                metrics["cluster_summary"]["storage"]["usage_percent"] = current_storage_usage

                if previous_storage_usage is not None:
                    metrics["cluster_summary"]["storage"]["change_percent"] = round(
                        current_storage_usage - previous_storage_usage, 2
                    )

        return metrics

    async def _fetch_power_metrics(self, session: aiohttp.ClientSession, query: str, time_params: dict) -> List[Dict]:
        params = {"query": query}

        try:
            async with session.get(
                f"{self.prometheus_url}/api/v1/query", ssl=False, params=params, headers={"Accept": "application/json"}
            ) as response:
                response_data = await response.json()
                logger.debug(f"Power Metrics: {response_data}")
                return response_data.get("data", []).get("result", [])
        except Exception as e:
            logger.error(f"Failed to fetch power metrics: {e}")
            return []

    async def get_cluster_metrics(
        self, cluster_id: UUID, time_range: str = "today", metric_type: str = "all"
    ) -> Optional[Dict[str, Any]]:
        """Fetch cluster metrics.

        Args:
            cluster_id: The cluster ID to fetch metrics for
            time_range: One of '10min', 'today', '7days', 'month'
            metric_type: Type of metric to fetch ('all', 'memory', 'cpu', 'disk', 'network_in', 'network_out', 'network_bandwidth', 'power')

        Returns:
            Dict with node and summary metrics for the requested metric type
        """
        # if not cluster_id:
        #     logger.error("Cluster ID is required to fetch cluster metrics")
        #     return None

        cluster_name = str(cluster_id)
        current_time_params = self._get_time_range_params(time_range)
        previous_time_params = (
            self._get_time_range_params(time_range, include_previous=True) if time_range == "today" else None
        )

        # Get all available queries
        all_queries = self._get_metric_queries(cluster_name)

        # Filter queries based on metric_type
        queries = {}
        if metric_type == "all":
            queries = all_queries
        else:
            # Map metric types to their required queries
            metric_query_mapping = {
                "memory": ["memory_total", "memory_available", "node_uname_info"],
                "cpu": ["cpu_usage", "node_uname_info"],
                "disk": ["storage_total", "storage_available", "node_uname_info"],
                "network_in": ["network_in", "node_uname_info"],
                "network_out": ["network_out", "node_uname_info"],
                "network_bandwidth": ["network_bandwidth", "node_uname_info"],
                "network": ["network_in", "network_out", "network_bandwidth", "node_uname_info"],
            }

            if metric_type in metric_query_mapping:
                for query_name in metric_query_mapping[metric_type]:
                    if query_name in all_queries:
                        queries[query_name] = all_queries[query_name]

        if not queries and metric_type != "power":
            logger.error(f"Invalid metric type: {metric_type}")
            return None

        try:
            # Get Power Metrics
            if time_range == "today":
                power_query = f"""
                sum by (instance) (
                    increase(kepler_container_joules_total{{cluster="{cluster_id}"}}[24h])
                    * on(node) group_left()
                    (
                        count by (node) (node_uname_info{{
                            cluster="{cluster_id}",
                            job="node-exporter"
                        }})
                    )
                ) / 3600000
                """
                power_query_pre = f"""
                sum by (instance) (
                    increase(kepler_container_joules_total{{cluster="{cluster_name}"}}[24h] offset 24h)
                    * on(node) group_left()
                    (
                        count by (node) (node_uname_info{{
                            cluster="{cluster_name}",
                            job="node-exporter"
                        }})
                    )
                ) / 3600000
                """
            elif time_range == "10min":
                power_query = f"""
                sum by (instance) (
                    increase(kepler_container_joules_total{{cluster="{cluster_name}"}}[10m])
                    * on(node) group_left()
                    (
                        count by (node) (node_uname_info{{
                            cluster="{cluster_name}",
                            job="node-exporter"
                        }})
                    )
                ) / 3600000
                """
                power_query_pre = f"""
                sum by (instance) (
                    increase(kepler_container_joules_total{{cluster="{cluster_name}"}}[10m] offset 10m)
                    * on(node) group_left()
                    (
                        count by (node) (node_uname_info{{
                            cluster="{cluster_name}",
                            job="node-exporter"
                        }})
                    )
                ) / 3600000
                """
            elif time_range == "7days":
                power_query = f"""
                sum by (instance) (
                    increase(kepler_container_joules_total{{cluster="{cluster_name}"}}[7d])
                    * on(node) group_left()
                    (
                        count by (node) (node_uname_info{{
                            cluster="{cluster_name}",
                            job="node-exporter"
                        }})
                    )
                ) / 3600000
                """
                power_query_pre = f"""
                sum by (instance) (
                    increase(kepler_container_joules_total{{cluster="{cluster_name}"}}[7d] offset 7d)
                    * on(node) group_left()
                    (
                        count by (node) (node_uname_info{{
                            cluster="{cluster_name}",
                            job="node-exporter"
                        }})
                    )
                ) / 3600000
                """
            else:
                power_query = f"""
                sum by (instance) (
                    increase(kepler_container_joules_total{{cluster="{cluster_name}"}}[30d])
                    * on(node) group_left()
                    (
                        count by (node) (node_uname_info{{
                            cluster="{cluster_name}",
                            job="node-exporter"
                        }})
                    )
                ) / 3600000
                """
                power_query_pre = f"""
                sum by (instance) (
                    increase(kepler_container_joules_total{{cluster="{cluster_name}"}}[30d] offset 30d)
                    * on(node) group_left()
                    (
                        count by (node) (node_uname_info{{
                            cluster="{cluster_name}",
                            job="node-exporter"
                        }})
                    )
                ) / 3600000
                """

            # Fetch current metrics concurrently
            async with aiohttp.ClientSession() as session:
                tasks = []
                for metric_name, query in queries.items():
                    task = self._fetch_metrics(session, query, current_time_params)
                    tasks.append((metric_name, task))

                # Condition to check if power query is present
                if metric_type == "all" or metric_type == "power":
                    # Fetch Power Metrics
                    power_task = self._fetch_power_metrics(session, power_query, current_time_params)
                    tasks.append(("power", power_task))

                # If it's "today", also fetch previous day metrics
                if previous_time_params:
                    for metric_name, query in queries.items():
                        task = self._fetch_metrics(session, query, previous_time_params)
                        tasks.append((f"prev_{metric_name}", task))
                if metric_type == "all" or metric_type == "power":
                    # Previous Power Query
                    power_task_pr = self._fetch_power_metrics(session, power_query_pre, current_time_params)
                    tasks.append(("pre_power", power_task_pr))

                # Gather results
                current_results = {}
                previous_results = {}
                for metric_name, task in tasks:
                    try:
                        result = await task

                        if metric_name.startswith("prev_"):
                            previous_results[metric_name[5:]] = result  # Remove 'prev_' prefix
                        else:
                            current_results[metric_name] = result
                        logger.debug(f"Gathered results for {metric_name}: {len(result) if result else 0} data points")
                    except Exception as e:
                        logger.error(f"Failed to fetch {metric_name}: {e}")
                        if metric_name.startswith("prev_"):
                            previous_results[metric_name[5:]] = []
                        else:
                            current_results[metric_name] = []

            # Process metrics
            processed_metrics = self._process_metrics(
                current_results, previous_results if previous_time_params else None
            )

            logger.debug(f"Processed Metrics: {processed_metrics}")

            # Add metadata
            processed_metrics.update(
                {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "time_range": time_range,
                    "cluster_id": str(cluster_id),
                    "metric_type": metric_type,
                }
            )

            logger.debug(f"Successfully fetched {metric_type} metrics for cluster {cluster_id}")
            logger.debug(f"Number of nodes found: {len(processed_metrics.get('nodes', {}))}")
            return processed_metrics

        except Exception as e:
            logger.error(f"Failed to fetch cluster metrics: {e}")
            logger.error(f"Full error details: {str(e)}")
            return None
