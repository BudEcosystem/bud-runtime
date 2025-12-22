import time
from http import HTTPStatus
from typing import Any, Dict, List, Tuple

import requests
from fastapi import HTTPException

from budapp.cluster_ops.schemas import PrometheusConfig
from budapp.commons.config import app_settings


class PrometheusMetricsClient:
    def __init__(self, config: PrometheusConfig):
        self.config = config

    def query_prometheus(self, query: str) -> List[Dict]:
        """Query Prometheus for metrics in the specified cluster."""
        try:
            if self.config.cluster_id:
                if "{" in query:
                    full_query = query.replace("}", f',cluster="{self.config.cluster_id}"}}')
                else:
                    full_query = f'{query}{{cluster="{self.config.cluster_id}"}}'
            else:
                full_query = query

            response = requests.get(f"{self.config.base_url}/api/v1/query", params={"query": full_query}, timeout=30)

            if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code,
                    detail={
                        "code": response.status_code,
                        "type": "PrometheusQueryError",
                        "message": f"Prometheus query failed: {response.text}",
                    },
                )

            data = response.json()
            return data["data"]["result"]
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                detail={
                    "code": HTTPStatus.INTERNAL_SERVER_ERROR,
                    "type": "PrometheusQueryError",
                    "message": f"Unexpected error during Prometheus query: {str(e)}",
                },
            )

    def query_prometheus_range(self, query: str, start_time: int, end_time: int, step: str = "1h") -> List[Dict]:
        """Query Prometheus for range metrics."""
        if self.config.cluster_id:
            if "{" in query:
                full_query = query.replace("}", f',cluster="{self.config.cluster_id}"}}')
            else:
                full_query = f'{query}{{cluster="{self.config.cluster_id}"}}'
        else:
            full_query = query

        response = requests.get(
            f"{self.config.base_url}/api/v1/query_range",
            params={"query": full_query, "start": start_time, "end": end_time, "step": step},
            timeout=30,
        )

        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code, detail=f"Prometheus range query failed: {response.text}"
            )

        data = response.json()
        return data["data"]["result"]

    def get_node_status(self) -> Dict[str, str]:
        """Get the status (Ready/NotReady) for each node."""
        try:
            status_metrics = self.query_prometheus('kube_node_status_condition{condition="Ready",status="true"}')

            node_status = {}
            for metric in status_metrics:
                node_name = metric["metric"].get("node", "unknown")
                node_status[node_name] = "Ready"

            all_nodes = self.query_prometheus("node_uname_info")
            for node in all_nodes:
                node_name = node["metric"].get("nodename", "unknown")
                if node_name not in node_status:
                    node_status[node_name] = "NotReady"

            return node_status
        except HTTPException:
            # Re-raise the HTTPException to maintain the status code
            raise
        except Exception as e:
            # Convert any other exceptions to HTTPException
            raise HTTPException(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail=f"Failed to get node status: {str(e)}"
            )

    def get_pod_status(self) -> Dict[str, Dict]:
        """Get pod status (Available vs Desired) for each node."""
        pod_info = self.query_prometheus("kubelet_running_pods")
        pod_status = {}

        for metric in pod_info:
            node_name = metric["metric"].get("node", "unknown")
            if node_name not in pod_status:
                pod_status[node_name] = {"available": 0, "desired": 0}

            pod_count = float(metric["value"][1])
            pod_status[node_name] = {"available": pod_count, "desired": pod_count}

        return pod_status

    def get_node_info(self) -> Tuple[List[Dict], Dict[str, float], Dict[str, str], Dict[str, float], Dict[str, Dict]]:
        """Get node information, pod counts, status, max pods, and pod availability."""
        nodes = self.query_prometheus("node_uname_info")
        pod_metrics = self.query_prometheus("kubelet_running_pods")
        max_pods_metrics = self.query_prometheus("kube_node_status_allocatable_pods")

        pod_counts = {}
        for pod_metric in pod_metrics:
            node_name = pod_metric["metric"].get("node", "unknown")
            pod_counts[node_name] = float(pod_metric["value"][1]) if "value" in pod_metric else 0

        max_pods = {}
        for max_pod_metric in max_pods_metrics:
            node_name = max_pod_metric["metric"].get("node", "unknown")
            max_pods[node_name] = float(max_pod_metric["value"][1]) if "value" in max_pod_metric else 0

        node_status = self.get_node_status()
        pod_status = self.get_pod_status()

        return nodes, pod_counts, node_status, max_pods, pod_status

    def get_node_description(self, node_name: str) -> Dict:
        """Get detailed node description information."""
        description = {}
        conditions = self.query_prometheus(f'kube_node_status_condition{{node="{node_name}"}}')
        capacity = self.query_prometheus(f'kube_node_status_capacity{{node="{node_name}"}}')

        description["conditions"] = []
        for condition in conditions:
            labels = condition["metric"]
            if float(condition["value"][1]) == 1:
                description["conditions"].append(
                    {
                        "type": labels.get("condition", ""),
                        "status": labels.get("status", ""),
                        "reason": labels.get("reason", ""),
                    }
                )

        description["capacity"] = {}
        for cap in capacity:
            labels = cap["metric"]
            resource = labels.get("resource", "")
            value = cap["value"][1]
            description["capacity"][resource] = value

        return description

    def get_node_memory_usage(self, node_ip: str) -> float:
        """Get memory usage for a node with multiple fallback metrics."""
        memory_metrics = [
            f'node_memory_MemTotal_bytes{{instance=~".*{node_ip}.*"}} - node_memory_MemFree_bytes{{instance=~".*{node_ip}.*"}} - node_memory_Buffers_bytes{{instance=~".*{node_ip}.*"}} - node_memory_Cached_bytes{{instance=~".*{node_ip}.*"}}',
            f'sum(container_memory_usage_bytes{{instance=~".*{node_ip}.*"}}) by (instance)',
            f'sum(container_memory_working_set_bytes{{instance=~".*{node_ip}.*"}}) by (instance)',
            f'node_memory_Active_bytes{{instance=~".*{node_ip}.*"}}',
        ]

        for metric_query in memory_metrics:
            try:
                memory_data = self.query_prometheus(metric_query)
                if memory_data and len(memory_data) > 0:
                    for metric in memory_data:
                        if "value" in metric:
                            return float(metric["value"][1])
            except Exception:
                continue

        return 0

    def parse_memory_value(self, memory_str: str) -> float:
        """Convert memory string to bytes."""
        try:
            if isinstance(memory_str, (int, float)):
                return float(memory_str)

            memory_str = str(memory_str).strip()
            if memory_str.endswith("Ki"):
                return float(memory_str[:-2]) * 1024
            elif memory_str.endswith("Mi"):
                return float(memory_str[:-2]) * 1024 * 1024
            elif memory_str.endswith("Gi"):
                return float(memory_str[:-2]) * 1024 * 1024 * 1024
            elif memory_str.endswith("Ti"):
                return float(memory_str[:-2]) * 1024 * 1024 * 1024 * 1024
            else:
                return float(memory_str)
        except (ValueError, AttributeError):
            return 0

    def get_network_bandwidth(self, node_ip: str) -> List[Dict[str, Any]]:
        """Get combined network bandwidth metrics for the last 24 hours."""
        try:
            end_time = int(time.time())
            start_time = end_time - (24 * 60 * 60)

            bandwidth_query = f"""
            sum(
              rate(node_network_receive_bytes_total{{instance=~".*{node_ip}.*",device!~"lo|veth.*|docker.*|br.*|cni.*"}}[1h])
              +
              rate(node_network_transmit_bytes_total{{instance=~".*{node_ip}.*",device!~"lo|veth.*|docker.*|br.*|cni.*"}}[1h])
            ) by (instance)
            """

            bandwidth_data = self.query_prometheus_range(bandwidth_query, start_time, end_time, "1h")
            bandwidth_metrics = []

            if bandwidth_data and len(bandwidth_data) > 0:
                for metric in bandwidth_data:
                    if "values" in metric:
                        for value in metric["values"]:
                            timestamp = value[0]
                            bandwidth = float(value[1])
                            mbps = (bandwidth * 8) / (1024 * 1024)
                            bandwidth_metrics.append({"timestamp": timestamp, "mbps": round(mbps, 2)})

            return bandwidth_metrics

        except Exception:
            return []

    def get_network_stats(self, node_ip: str) -> Dict[str, Any]:
        """Get comprehensive network statistics."""
        try:
            end_time = int(time.time())
            start_time = end_time - 3600

            metrics = {
                "receive_errors": f'rate(node_network_receive_errors_total{{instance=~".*{node_ip}.*",device!~"lo|veth.*|docker.*|br.*|cni.*"}}[5m])',
                "transmit_errors": f'rate(node_network_transmit_errors_total{{instance=~".*{node_ip}.*",device!~"lo|veth.*|docker.*|br.*|cni.*"}}[5m])',
                "receive_packets_dropped": f'rate(node_network_receive_packets_dropped_total{{instance=~".*{node_ip}.*",device!~"lo|veth.*|docker.*|br.*|cni.*"}}[5m])',
                "transmit_packets_dropped": f'rate(node_network_transmit_packets_dropped_total{{instance=~".*{node_ip}.*",device!~"lo|veth.*|docker.*|br.*|cni.*"}}[5m])',
            }

            stats = {}
            for metric_name, query in metrics.items():
                try:
                    data = self.query_prometheus_range(query, start_time, end_time, "5m")
                    if data and len(data) > 0:
                        values = []
                        for metric in data:
                            if "values" in metric:
                                values.extend([float(v[1]) for v in metric["values"]])

                        if values:
                            stats[metric_name] = {
                                "current": round(values[-1], 3),
                                "avg": round(sum(values) / len(values), 3),
                                "max": round(max(values), 3),
                            }
                except Exception:
                    continue

            return stats

        except Exception:
            return {}

    def get_node_events_count(self, node_name: str) -> int:
        """Get the count of events for a specific node in the last 24 hours.

        Args:
            node_ip: IP address of the node to get events count for

        Returns:
            int: Count of events for the node

        Raises:
            HTTPException: If there's an error querying the events
        """
        try:
            # Use budmetrics for node event counts (from ClickHouse)
            events_endpoint = (
                f"{app_settings.dapr_base_url}/v1.0/invoke"
                f"/{app_settings.bud_metrics_app_id}/method"
                f"/cluster-metrics/{self.config.cluster_id}/node-events-count"
            )

            response = requests.get(events_endpoint, timeout=30)

            if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code,
                    detail={
                        "code": response.status_code,
                        "type": "EventsQueryError",
                        "message": f"Failed to get node events: {response.text}",
                    },
                )

            events_data = response.json()
            # Extract the events count for the specific node from the response
            # budmetrics returns events_count dict

            return events_data.get("events_count", {}).get(node_name, 0)

        except HTTPException as e:
            # Properly format the error response
            raise HTTPException(
                status_code=e.status_code,
                detail={"code": e.status_code, "type": "EventsQueryError", "message": str(e.detail)},
            )
        except Exception as e:
            raise HTTPException(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                detail={
                    "code": HTTPStatus.INTERNAL_SERVER_ERROR,
                    "type": "EventsQueryError",
                    "message": f"Failed to get node events: {str(e)}",
                },
            )

    def get_nodes_status(self) -> Dict:
        """Get comprehensive node status information in JSON format."""
        nodes, pod_counts, node_status, max_pods, pod_status = self.get_node_info()
        nodes_json = {"nodes": {}}

        for node in nodes:
            node_name = node["metric"].get("nodename", "unknown")
            node_ip = node["metric"].get("instance", "unknown").split(":")[0]

            pod_count = pod_counts.get(node_name, 0)
            status = node_status.get(node_name, "Unknown")

            description = self.get_node_description(node_name)
            max_pods = int(float(description.get("capacity", {}).get("pods", 0)))
            cpu_capacity = description.get("capacity", {}).get("cpu", "0")

            try:
                # Try multiple CPU usage metrics with fallbacks
                cpu_metrics = [
                    # Node level CPU usage
                    f'sum(rate(node_cpu_seconds_total{{instance=~".*{node_ip}.*",mode!="idle"}}[5m])) by (instance)',
                    # Container level CPU usage
                    f'sum(rate(container_cpu_usage_seconds_total{{instance=~".*{node_ip}.*"}}[5m])) by (instance)',
                    # Alternate container metric
                    f'sum(container_cpu_system_seconds_total{{instance=~".*{node_ip}.*"}}) by (instance)',
                ]

                current_cpu = 0
                for metric_query in cpu_metrics:
                    cpu_data = self.query_prometheus(metric_query)
                    if cpu_data and len(cpu_data) > 0:
                        for metric in cpu_data:
                            if "value" in metric:
                                current_cpu = float(metric["value"][1])
                                if current_cpu > 0:  # If we found a valid value, break
                                    break
                        if current_cpu > 0:  # If we found a valid value, break
                            break
            except Exception:
                current_cpu = 0

            try:
                memory_capacity = description.get("capacity", {}).get("memory", "0")
                memory_capacity_bytes = self.parse_memory_value(memory_capacity)
                current_memory = self.get_node_memory_usage(node_ip)
            except Exception:
                current_memory = 0
                memory_capacity_bytes = 0

            bandwidth_metrics = self.get_network_bandwidth(node_ip)
            # network_stats = self.get_network_stats(node_ip)
            events_count = self.get_node_events_count(node_name)

            nodes_json["nodes"][node_ip] = {
                "hostname": node_name,
                "status": status,
                "system_info": {
                    "os": node["metric"].get("sysname", "N/A"),
                    "kernel": node["metric"].get("release", "N/A"),
                    "architecture": node["metric"].get("machine", "N/A"),
                },
                "pods": {"current": int(pod_count), "max": max_pods},
                "cpu": {"current": round(current_cpu, 2), "capacity": float(cpu_capacity)},
                "memory": {
                    "current": round(current_memory / (1024 * 1024 * 1024), 2),
                    "capacity": round(memory_capacity_bytes / (1024 * 1024 * 1024), 2),
                },
                "network": {"bandwidth": bandwidth_metrics},
                "events_count": events_count,
                "capacity": description.get("capacity", {}),
            }

        return nodes_json
