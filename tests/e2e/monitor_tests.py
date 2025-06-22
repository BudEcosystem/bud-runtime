#!/usr/bin/env python3
"""Real-time test monitoring and metrics collection.

This script monitors test execution and collects metrics from:
- Prometheus
- Kubernetes API
- Test logs
"""

import os
import sys
import time
import json
import asyncio
import argparse
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import requests
from pathlib import Path
import logging

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from kubernetes import client, config
from tests.e2e.utils import setup_logging


class MetricsCollector:
    """Collects metrics during test execution."""
    
    def __init__(self, prometheus_url: str, output_dir: str):
        self.prometheus_url = prometheus_url
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.logger = setup_logging()
        self.metrics = []
        self.start_time = None
        self.stop_event = asyncio.Event()
    
    async def start(self):
        """Start collecting metrics."""
        self.start_time = datetime.now()
        self.logger.info(f"Starting metrics collection at {self.start_time}")
        
        # Start collection tasks
        tasks = [
            asyncio.create_task(self.collect_prometheus_metrics()),
            asyncio.create_task(self.collect_kubernetes_metrics()),
            asyncio.create_task(self.monitor_logs()),
        ]
        
        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            self.logger.info("Metrics collection stopped")
    
    def stop(self):
        """Stop collecting metrics."""
        self.stop_event.set()
        self.save_metrics()
    
    async def collect_prometheus_metrics(self):
        """Collect metrics from Prometheus."""
        queries = {
            "request_rate": 'rate(http_requests_total[1m])',
            "error_rate": 'rate(http_requests_total{status=~"5.."}[1m])',
            "response_time_p95": 'histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[1m]))',
            "cpu_usage": 'rate(container_cpu_usage_seconds_total[1m])',
            "memory_usage": 'container_memory_usage_bytes',
            "gpu_utilization": 'DCGM_FI_DEV_GPU_UTIL',
            "active_connections": 'http_connections_active',
        }
        
        while not self.stop_event.is_set():
            timestamp = datetime.now()
            metrics_data = {"timestamp": timestamp.isoformat(), "prometheus": {}}
            
            for metric_name, query in queries.items():
                try:
                    response = requests.get(
                        f"{self.prometheus_url}/api/v1/query",
                        params={"query": query},
                        timeout=5
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        if data["status"] == "success":
                            results = data["data"]["result"]
                            metrics_data["prometheus"][metric_name] = results
                    else:
                        self.logger.debug(f"Failed to query {metric_name}: {response.status_code}")
                
                except Exception as e:
                    self.logger.debug(f"Error querying {metric_name}: {e}")
            
            self.metrics.append(metrics_data)
            await asyncio.sleep(10)  # Collect every 10 seconds
    
    async def collect_kubernetes_metrics(self):
        """Collect metrics from Kubernetes API."""
        try:
            config.load_incluster_config()
        except:
            config.load_kube_config()
        
        v1 = client.CoreV1Api()
        apps_v1 = client.AppsV1Api()
        
        while not self.stop_event.is_set():
            timestamp = datetime.now()
            k8s_metrics = {
                "timestamp": timestamp.isoformat(),
                "kubernetes": {
                    "pods": {},
                    "deployments": {},
                    "nodes": {},
                }
            }
            
            try:
                # Collect pod metrics
                pods = v1.list_pod_for_all_namespaces()
                pod_stats = {}
                
                for pod in pods.items:
                    namespace = pod.metadata.namespace
                    if namespace not in ["bud-system", "inference-system"]:
                        continue
                    
                    if namespace not in pod_stats:
                        pod_stats[namespace] = {
                            "total": 0,
                            "running": 0,
                            "pending": 0,
                            "failed": 0,
                            "restarts": 0,
                        }
                    
                    pod_stats[namespace]["total"] += 1
                    
                    if pod.status.phase == "Running":
                        pod_stats[namespace]["running"] += 1
                    elif pod.status.phase == "Pending":
                        pod_stats[namespace]["pending"] += 1
                    elif pod.status.phase == "Failed":
                        pod_stats[namespace]["failed"] += 1
                    
                    # Count restarts
                    if pod.status.container_statuses:
                        for container in pod.status.container_statuses:
                            pod_stats[namespace]["restarts"] += container.restart_count
                
                k8s_metrics["kubernetes"]["pods"] = pod_stats
                
                # Collect deployment metrics
                deployments = apps_v1.list_deployment_for_all_namespaces()
                deployment_stats = {}
                
                for deployment in deployments.items:
                    namespace = deployment.metadata.namespace
                    if namespace not in ["bud-system", "inference-system"]:
                        continue
                    
                    name = deployment.metadata.name
                    deployment_stats[f"{namespace}/{name}"] = {
                        "replicas": deployment.spec.replicas,
                        "ready_replicas": deployment.status.ready_replicas or 0,
                        "available_replicas": deployment.status.available_replicas or 0,
                    }
                
                k8s_metrics["kubernetes"]["deployments"] = deployment_stats
                
                # Collect node metrics
                nodes = v1.list_node()
                node_stats = {}
                
                for node in nodes.items:
                    node_name = node.metadata.name
                    node_stats[node_name] = {
                        "ready": "Ready" in [c.type for c in node.status.conditions if c.status == "True"],
                        "cpu_capacity": node.status.capacity.get("cpu", "0"),
                        "memory_capacity": node.status.capacity.get("memory", "0"),
                        "gpu_capacity": node.status.capacity.get("nvidia.com/gpu", "0"),
                    }
                
                k8s_metrics["kubernetes"]["nodes"] = node_stats
                
            except Exception as e:
                self.logger.error(f"Error collecting Kubernetes metrics: {e}")
            
            self.metrics.append(k8s_metrics)
            await asyncio.sleep(15)  # Collect every 15 seconds
    
    async def monitor_logs(self):
        """Monitor test logs for errors and warnings."""
        log_patterns = {
            "errors": ["ERROR", "FAILED", "Exception", "Traceback"],
            "warnings": ["WARNING", "WARN", "Timeout", "Retry"],
            "info": ["Starting test", "Test completed", "PASSED"],
        }
        
        log_stats = {
            "errors": 0,
            "warnings": 0,
            "info": 0,
        }
        
        # This is a simplified version - in production, you'd tail actual log files
        while not self.stop_event.is_set():
            await asyncio.sleep(30)
    
    def save_metrics(self):
        """Save collected metrics to file."""
        if not self.metrics:
            return
        
        output_file = self.output_dir / f"metrics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        summary = {
            "start_time": self.start_time.isoformat(),
            "end_time": datetime.now().isoformat(),
            "duration": (datetime.now() - self.start_time).total_seconds(),
            "metrics_count": len(self.metrics),
            "metrics": self.metrics,
        }
        
        with open(output_file, "w") as f:
            json.dump(summary, f, indent=2)
        
        self.logger.info(f"Metrics saved to {output_file}")
        
        # Generate summary report
        self.generate_summary()
    
    def generate_summary(self):
        """Generate a summary of collected metrics."""
        if not self.metrics:
            return
        
        summary_file = self.output_dir / f"metrics_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        
        with open(summary_file, "w") as f:
            f.write("=== Metrics Collection Summary ===\n")
            f.write(f"Start Time: {self.start_time}\n")
            f.write(f"End Time: {datetime.now()}\n")
            f.write(f"Duration: {datetime.now() - self.start_time}\n")
            f.write(f"Total Metrics Collected: {len(self.metrics)}\n\n")
            
            # Analyze Kubernetes metrics
            if any("kubernetes" in m for m in self.metrics):
                f.write("=== Kubernetes Summary ===\n")
                
                # Find max pod counts
                max_pods = {}
                total_restarts = 0
                
                for metric in self.metrics:
                    if "kubernetes" in metric:
                        pods = metric["kubernetes"].get("pods", {})
                        for namespace, stats in pods.items():
                            if namespace not in max_pods:
                                max_pods[namespace] = stats["total"]
                            else:
                                max_pods[namespace] = max(max_pods[namespace], stats["total"])
                            total_restarts += stats.get("restarts", 0)
                
                for namespace, count in max_pods.items():
                    f.write(f"{namespace}: Max {count} pods\n")
                
                f.write(f"Total container restarts: {total_restarts}\n\n")
            
            # Analyze Prometheus metrics if available
            if any("prometheus" in m for m in self.metrics):
                f.write("=== Performance Metrics ===\n")
                f.write("(Prometheus metrics would be analyzed here)\n\n")
        
        self.logger.info(f"Summary saved to {summary_file}")


class TestMonitor:
    """Monitors test execution in real-time."""
    
    def __init__(self, test_name: str, prometheus_url: str, grafana_url: Optional[str] = None):
        self.test_name = test_name
        self.prometheus_url = prometheus_url
        self.grafana_url = grafana_url
        self.logger = setup_logging()
        self.output_dir = Path("reports/monitoring")
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    async def monitor_test_execution(self, test_command: List[str]):
        """Monitor a test execution."""
        self.logger.info(f"Starting monitoring for test: {self.test_name}")
        
        # Start metrics collector
        collector = MetricsCollector(self.prometheus_url, str(self.output_dir))
        collector_task = asyncio.create_task(collector.start())
        
        # Create dashboard URL if Grafana is available
        if self.grafana_url:
            dashboard_url = self.create_dashboard_url()
            self.logger.info(f"Grafana dashboard: {dashboard_url}")
        
        # Run the test command
        import subprocess
        self.logger.info(f"Running test command: {' '.join(test_command)}")
        
        test_start = time.time()
        try:
            process = await asyncio.create_subprocess_exec(
                *test_command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            # Monitor test output
            async def read_output(stream, prefix):
                while True:
                    line = await stream.readline()
                    if not line:
                        break
                    print(f"{prefix}: {line.decode().strip()}")
            
            await asyncio.gather(
                read_output(process.stdout, "STDOUT"),
                read_output(process.stderr, "STDERR")
            )
            
            await process.wait()
            test_duration = time.time() - test_start
            
            self.logger.info(f"Test completed in {test_duration:.2f} seconds")
            self.logger.info(f"Exit code: {process.returncode}")
            
        finally:
            # Stop metrics collection
            collector.stop()
            collector_task.cancel()
            
            try:
                await collector_task
            except asyncio.CancelledError:
                pass
        
        # Generate final report
        self.generate_monitoring_report(test_duration, process.returncode)
        
        return process.returncode
    
    def create_dashboard_url(self) -> str:
        """Create a Grafana dashboard URL with time range."""
        start_time = int(time.time() * 1000)
        
        # Assuming a standard inference dashboard exists
        dashboard_url = (
            f"{self.grafana_url}/d/inference-monitoring/inference-monitoring"
            f"?orgId=1&from={start_time}&to=now&refresh=5s"
        )
        
        return dashboard_url
    
    def generate_monitoring_report(self, duration: float, exit_code: int):
        """Generate monitoring report."""
        report_file = self.output_dir / f"monitor_report_{self.test_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        
        with open(report_file, "w") as f:
            f.write(f"# Test Monitoring Report: {self.test_name}\n\n")
            f.write(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"**Duration:** {duration:.2f} seconds\n")
            f.write(f"**Exit Code:** {exit_code}\n")
            f.write(f"**Status:** {'PASSED' if exit_code == 0 else 'FAILED'}\n\n")
            
            f.write("## Metrics Collection\n")
            f.write(f"- Metrics saved to: {self.output_dir}\n")
            
            if self.grafana_url:
                f.write(f"\n## Grafana Dashboard\n")
                f.write(f"- URL: {self.create_dashboard_url()}\n")
            
            f.write("\n## Key Observations\n")
            f.write("- (Add automated analysis here)\n")
            f.write("- Pod restarts: Check metrics files\n")
            f.write("- Error rates: Check metrics files\n")
            f.write("- Performance degradation: Check metrics files\n")
        
        self.logger.info(f"Monitoring report saved to {report_file}")


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Test Execution Monitor")
    
    parser.add_argument(
        "--test-name",
        required=True,
        help="Name of the test being monitored"
    )
    
    parser.add_argument(
        "--prometheus",
        default="http://localhost:9090",
        help="Prometheus URL"
    )
    
    parser.add_argument(
        "--grafana",
        help="Grafana URL (optional)"
    )
    
    parser.add_argument(
        "command",
        nargs="+",
        help="Test command to execute"
    )
    
    args = parser.parse_args()
    
    # Create monitor
    monitor = TestMonitor(
        test_name=args.test_name,
        prometheus_url=args.prometheus,
        grafana_url=args.grafana
    )
    
    # Run monitoring
    exit_code = await monitor.monitor_test_execution(args.command)
    
    sys.exit(exit_code)


if __name__ == "__main__":
    asyncio.run(main())