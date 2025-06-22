#!/usr/bin/env python3
"""Generate comprehensive test reports from multiple sources.

This script aggregates results from:
- PyTest JSON reports
- K6 performance results
- Locust results
- Monitoring metrics
- Log analysis
"""

import os
import sys
import json
import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from jinja2 import Template

# Configure matplotlib
plt.style.use('seaborn-v0_8-darkgrid')
sns.set_palette("husl")


class ReportGenerator:
    """Generates comprehensive test reports."""
    
    def __init__(self, report_dir: str, output_format: str = "html"):
        self.report_dir = Path(report_dir)
        self.output_format = output_format
        self.data = {
            "pytest": {},
            "k6": {},
            "locust": {},
            "monitoring": {},
            "summary": {},
        }
        self.timestamp = datetime.now()
    
    def collect_data(self):
        """Collect data from all sources."""
        print("Collecting test data...")
        
        # Collect PyTest results
        self._collect_pytest_results()
        
        # Collect K6 results
        self._collect_k6_results()
        
        # Collect Locust results
        self._collect_locust_results()
        
        # Collect monitoring data
        self._collect_monitoring_data()
        
        # Generate summary statistics
        self._generate_summary()
    
    def _collect_pytest_results(self):
        """Collect PyTest JSON reports."""
        for json_file in self.report_dir.glob("*_report.json"):
            if "pytest" in json_file.name or json_file.name.endswith("_report.json"):
                try:
                    with open(json_file) as f:
                        data = json.load(f)
                        scenario = json_file.stem.replace("_report", "")
                        self.data["pytest"][scenario] = data
                except Exception as e:
                    print(f"Error reading {json_file}: {e}")
    
    def _collect_k6_results(self):
        """Collect K6 performance results."""
        for json_file in self.report_dir.glob("k6_*_summary_*.json"):
            try:
                with open(json_file) as f:
                    data = json.load(f)
                    test_type = json_file.name.split("_")[1]  # smoke, load, etc.
                    self.data["k6"][test_type] = data
            except Exception as e:
                print(f"Error reading {json_file}: {e}")
    
    def _collect_locust_results(self):
        """Collect Locust results."""
        for csv_file in self.report_dir.glob("locust_stats_*_stats.csv"):
            try:
                df = pd.read_csv(csv_file)
                timestamp = csv_file.name.split("_")[2]
                self.data["locust"][timestamp] = df.to_dict(orient="records")
            except Exception as e:
                print(f"Error reading {csv_file}: {e}")
    
    def _collect_monitoring_data(self):
        """Collect monitoring metrics."""
        monitoring_dir = self.report_dir / "monitoring"
        if monitoring_dir.exists():
            for json_file in monitoring_dir.glob("metrics_*.json"):
                try:
                    with open(json_file) as f:
                        data = json.load(f)
                        self.data["monitoring"][json_file.stem] = data
                except Exception as e:
                    print(f"Error reading {json_file}: {e}")
    
    def _generate_summary(self):
        """Generate summary statistics."""
        summary = {
            "total_tests": 0,
            "passed_tests": 0,
            "failed_tests": 0,
            "skipped_tests": 0,
            "total_duration": 0,
            "scenarios": {},
            "performance": {},
            "issues": [],
        }
        
        # Aggregate PyTest results
        for scenario, data in self.data["pytest"].items():
            if "summary" in data:
                s = data["summary"]
                summary["total_tests"] += s.get("total", 0)
                summary["passed_tests"] += s.get("passed", 0)
                summary["failed_tests"] += s.get("failed", 0)
                summary["skipped_tests"] += s.get("skipped", 0)
                summary["total_duration"] += s.get("duration", 0)
                
                summary["scenarios"][scenario] = {
                    "total": s.get("total", 0),
                    "passed": s.get("passed", 0),
                    "failed": s.get("failed", 0),
                    "duration": s.get("duration", 0),
                }
        
        # Aggregate performance metrics
        if self.data["k6"]:
            k6_metrics = {}
            for test_type, data in self.data["k6"].items():
                if "metrics" in data:
                    metrics = data["metrics"]
                    if "http_req_duration" in metrics:
                        k6_metrics[test_type] = {
                            "avg_response_time": metrics["http_req_duration"]["values"]["avg"],
                            "p95_response_time": metrics["http_req_duration"]["values"]["p(95)"],
                            "p99_response_time": metrics["http_req_duration"]["values"]["p(99)"],
                        }
            summary["performance"]["k6"] = k6_metrics
        
        # Identify issues
        if summary["failed_tests"] > 0:
            summary["issues"].append({
                "severity": "high",
                "message": f"{summary['failed_tests']} tests failed",
            })
        
        # Check performance thresholds
        for test_type, metrics in summary["performance"].get("k6", {}).items():
            if metrics.get("p95_response_time", 0) > 5000:  # 5 seconds
                summary["issues"].append({
                    "severity": "medium",
                    "message": f"{test_type}: P95 response time > 5s ({metrics['p95_response_time']:.0f}ms)",
                })
        
        self.data["summary"] = summary
    
    def generate_report(self):
        """Generate the final report."""
        print(f"Generating {self.output_format} report...")
        
        if self.output_format == "html":
            self._generate_html_report()
        elif self.output_format == "markdown":
            self._generate_markdown_report()
        elif self.output_format == "json":
            self._generate_json_report()
        else:
            raise ValueError(f"Unsupported format: {self.output_format}")
    
    def _generate_html_report(self):
        """Generate HTML report with charts."""
        # Create charts
        charts_dir = self.report_dir / "charts"
        charts_dir.mkdir(exist_ok=True)
        
        # Generate test results chart
        self._create_test_results_chart(charts_dir / "test_results.png")
        
        # Generate performance charts
        self._create_performance_charts(charts_dir)
        
        # HTML template
        template = Template("""
<!DOCTYPE html>
<html>
<head>
    <title>E2E Test Report - {{ timestamp }}</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            margin: 0;
            padding: 20px;
            background: #f5f5f5;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        h1, h2, h3 { color: #333; }
        .summary-cards {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin: 20px 0;
        }
        .card {
            padding: 20px;
            border-radius: 8px;
            text-align: center;
            background: #f8f9fa;
        }
        .card.success { background: #d4edda; color: #155724; }
        .card.warning { background: #fff3cd; color: #856404; }
        .card.danger { background: #f8d7da; color: #721c24; }
        .card h3 { margin: 0; font-size: 2em; }
        .card p { margin: 5px 0 0 0; }
        .chart { margin: 20px 0; text-align: center; }
        .chart img { max-width: 100%; height: auto; }
        table { width: 100%; border-collapse: collapse; margin: 20px 0; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }
        th { background: #f8f9fa; font-weight: 600; }
        .issue { padding: 10px; margin: 10px 0; border-radius: 4px; }
        .issue.high { background: #f8d7da; color: #721c24; }
        .issue.medium { background: #fff3cd; color: #856404; }
        .issue.low { background: #cce5ff; color: #004085; }
        .scenario-section {
            margin: 30px 0;
            padding: 20px;
            background: #f8f9fa;
            border-radius: 8px;
        }
        .metric-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 15px;
            margin: 15px 0;
        }
        .metric {
            text-align: center;
            padding: 15px;
            background: white;
            border-radius: 4px;
        }
        .metric-value { font-size: 1.5em; font-weight: bold; }
        .metric-label { font-size: 0.9em; color: #666; }
    </style>
</head>
<body>
    <div class="container">
        <h1>E2E Test Report</h1>
        <p>Generated on {{ timestamp.strftime('%Y-%m-%d %H:%M:%S') }}</p>
        
        <h2>Summary</h2>
        <div class="summary-cards">
            <div class="card">
                <h3>{{ summary.total_tests }}</h3>
                <p>Total Tests</p>
            </div>
            <div class="card success">
                <h3>{{ summary.passed_tests }}</h3>
                <p>Passed</p>
            </div>
            <div class="card danger">
                <h3>{{ summary.failed_tests }}</h3>
                <p>Failed</p>
            </div>
            <div class="card warning">
                <h3>{{ summary.skipped_tests }}</h3>
                <p>Skipped</p>
            </div>
        </div>
        
        <div class="chart">
            <h3>Test Results Overview</h3>
            <img src="charts/test_results.png" alt="Test Results">
        </div>
        
        {% if summary.issues %}
        <h2>Issues</h2>
        {% for issue in summary.issues %}
        <div class="issue {{ issue.severity }}">
            <strong>{{ issue.severity|upper }}:</strong> {{ issue.message }}
        </div>
        {% endfor %}
        {% endif %}
        
        <h2>Scenario Results</h2>
        {% for scenario, stats in summary.scenarios.items() %}
        <div class="scenario-section">
            <h3>{{ scenario|title }}</h3>
            <div class="metric-grid">
                <div class="metric">
                    <div class="metric-value">{{ stats.total }}</div>
                    <div class="metric-label">Total Tests</div>
                </div>
                <div class="metric">
                    <div class="metric-value">{{ stats.passed }}</div>
                    <div class="metric-label">Passed</div>
                </div>
                <div class="metric">
                    <div class="metric-value">{{ stats.failed }}</div>
                    <div class="metric-label">Failed</div>
                </div>
                <div class="metric">
                    <div class="metric-value">{{ "%.1f"|format(stats.duration) }}s</div>
                    <div class="metric-label">Duration</div>
                </div>
            </div>
        </div>
        {% endfor %}
        
        {% if summary.performance.k6 %}
        <h2>Performance Metrics</h2>
        <div class="chart">
            <img src="charts/performance_comparison.png" alt="Performance Comparison">
        </div>
        
        <table>
            <thead>
                <tr>
                    <th>Test Type</th>
                    <th>Avg Response Time</th>
                    <th>P95 Response Time</th>
                    <th>P99 Response Time</th>
                </tr>
            </thead>
            <tbody>
                {% for test_type, metrics in summary.performance.k6.items() %}
                <tr>
                    <td>{{ test_type|title }}</td>
                    <td>{{ "%.0f"|format(metrics.avg_response_time) }}ms</td>
                    <td>{{ "%.0f"|format(metrics.p95_response_time) }}ms</td>
                    <td>{{ "%.0f"|format(metrics.p99_response_time) }}ms</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
        {% endif %}
        
        <h2>Test Duration</h2>
        <p>Total test execution time: {{ "%.1f"|format(summary.total_duration) }} seconds</p>
        
        <div class="chart">
            <img src="charts/scenario_duration.png" alt="Scenario Duration">
        </div>
    </div>
</body>
</html>
""")
        
        # Render HTML
        html_content = template.render(
            timestamp=self.timestamp,
            summary=self.data["summary"],
        )
        
        # Save report
        output_file = self.report_dir / f"test_report_{self.timestamp.strftime('%Y%m%d_%H%M%S')}.html"
        with open(output_file, "w") as f:
            f.write(html_content)
        
        print(f"HTML report generated: {output_file}")
    
    def _create_test_results_chart(self, output_path: Path):
        """Create test results pie chart."""
        summary = self.data["summary"]
        
        # Data for pie chart
        sizes = [
            summary["passed_tests"],
            summary["failed_tests"],
            summary["skipped_tests"]
        ]
        labels = ["Passed", "Failed", "Skipped"]
        colors = ["#28a745", "#dc3545", "#ffc107"]
        
        # Create pie chart
        plt.figure(figsize=(8, 6))
        plt.pie(sizes, labels=labels, colors=colors, autopct='%1.1f%%', startangle=90)
        plt.axis('equal')
        plt.title("Test Results Distribution")
        plt.tight_layout()
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        plt.close()
    
    def _create_performance_charts(self, charts_dir: Path):
        """Create performance comparison charts."""
        k6_data = self.data["summary"]["performance"].get("k6", {})
        
        if not k6_data:
            return
        
        # Response time comparison
        test_types = list(k6_data.keys())
        avg_times = [k6_data[t]["avg_response_time"] for t in test_types]
        p95_times = [k6_data[t]["p95_response_time"] for t in test_types]
        p99_times = [k6_data[t]["p99_response_time"] for t in test_types]
        
        # Create grouped bar chart
        x = range(len(test_types))
        width = 0.25
        
        plt.figure(figsize=(10, 6))
        plt.bar([i - width for i in x], avg_times, width, label='Average', color='#3498db')
        plt.bar(x, p95_times, width, label='P95', color='#e74c3c')
        plt.bar([i + width for i in x], p99_times, width, label='P99', color='#f39c12')
        
        plt.xlabel('Test Type')
        plt.ylabel('Response Time (ms)')
        plt.title('Response Time Comparison')
        plt.xticks(x, [t.title() for t in test_types])
        plt.legend()
        plt.grid(axis='y', alpha=0.3)
        plt.tight_layout()
        plt.savefig(charts_dir / "performance_comparison.png", dpi=150, bbox_inches='tight')
        plt.close()
        
        # Scenario duration chart
        scenarios = self.data["summary"]["scenarios"]
        if scenarios:
            scenario_names = list(scenarios.keys())
            durations = [scenarios[s]["duration"] for s in scenario_names]
            
            plt.figure(figsize=(10, 6))
            plt.barh(scenario_names, durations, color='#2ecc71')
            plt.xlabel('Duration (seconds)')
            plt.title('Test Scenario Duration')
            plt.grid(axis='x', alpha=0.3)
            plt.tight_layout()
            plt.savefig(charts_dir / "scenario_duration.png", dpi=150, bbox_inches='tight')
            plt.close()
    
    def _generate_markdown_report(self):
        """Generate Markdown report."""
        summary = self.data["summary"]
        
        md_content = f"""# E2E Test Report

**Generated:** {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}

## Summary

- **Total Tests:** {summary['total_tests']}
- **Passed:** {summary['passed_tests']}
- **Failed:** {summary['failed_tests']}
- **Skipped:** {summary['skipped_tests']}
- **Total Duration:** {summary['total_duration']:.1f} seconds

"""
        
        if summary["issues"]:
            md_content += "## Issues\n\n"
            for issue in summary["issues"]:
                md_content += f"- **{issue['severity'].upper()}:** {issue['message']}\n"
            md_content += "\n"
        
        # Scenario results
        md_content += "## Scenario Results\n\n"
        md_content += "| Scenario | Total | Passed | Failed | Duration |\n"
        md_content += "|----------|-------|--------|--------|---------|\n"
        
        for scenario, stats in summary["scenarios"].items():
            md_content += f"| {scenario} | {stats['total']} | {stats['passed']} | {stats['failed']} | {stats['duration']:.1f}s |\n"
        
        # Performance metrics
        if summary["performance"].get("k6"):
            md_content += "\n## Performance Metrics\n\n"
            md_content += "| Test Type | Avg Response | P95 | P99 |\n"
            md_content += "|-----------|--------------|-----|-----|\n"
            
            for test_type, metrics in summary["performance"]["k6"].items():
                md_content += f"| {test_type} | {metrics['avg_response_time']:.0f}ms | {metrics['p95_response_time']:.0f}ms | {metrics['p99_response_time']:.0f}ms |\n"
        
        # Save report
        output_file = self.report_dir / f"test_report_{self.timestamp.strftime('%Y%m%d_%H%M%S')}.md"
        with open(output_file, "w") as f:
            f.write(md_content)
        
        print(f"Markdown report generated: {output_file}")
    
    def _generate_json_report(self):
        """Generate JSON report."""
        output_file = self.report_dir / f"test_report_{self.timestamp.strftime('%Y%m%d_%H%M%S')}.json"
        
        report_data = {
            "timestamp": self.timestamp.isoformat(),
            "summary": self.data["summary"],
            "details": {
                "pytest": self.data["pytest"],
                "k6": self.data["k6"],
                "locust": self.data["locust"],
            }
        }
        
        with open(output_file, "w") as f:
            json.dump(report_data, f, indent=2)
        
        print(f"JSON report generated: {output_file}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Generate E2E Test Report")
    
    parser.add_argument(
        "--report-dir",
        default="reports",
        help="Directory containing test results"
    )
    
    parser.add_argument(
        "--format",
        choices=["html", "markdown", "json"],
        default="html",
        help="Output format"
    )
    
    args = parser.parse_args()
    
    # Check dependencies
    try:
        import pandas
        import matplotlib
        import jinja2
    except ImportError as e:
        print(f"Missing dependency: {e}")
        print("Install with: pip install pandas matplotlib jinja2")
        sys.exit(1)
    
    # Generate report
    generator = ReportGenerator(args.report_dir, args.format)
    generator.collect_data()
    generator.generate_report()


if __name__ == "__main__":
    main()