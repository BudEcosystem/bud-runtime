#!/usr/bin/env python3
"""
Compare performance test results between baseline and current run.
Outputs a markdown report suitable for PR comments.
"""

import json
import sys
from typing import Dict, Tuple

def load_results(filename: str) -> Dict:
    """Load performance test results from JSON file."""
    try:
        with open(filename, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: Could not find file {filename}")
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"Error: Invalid JSON in {filename}")
        sys.exit(1)

def extract_metrics(results: Dict) -> Dict[str, float]:
    """Extract key metrics from vegeta results."""
    return {
        'latency_mean': results['latencies']['mean'] / 1_000_000,  # ns to ms
        'latency_p50': results['latencies']['50th'] / 1_000_000,
        'latency_p95': results['latencies']['95th'] / 1_000_000,
        'latency_p99': results['latencies']['99th'] / 1_000_000,
        'latency_max': results['latencies']['max'] / 1_000_000,
        'success_rate': results['success'] * 100,
        'throughput': results['throughput'],
        'total_requests': results['requests'],
    }

def calculate_change(baseline: float, current: float) -> Tuple[float, str]:
    """Calculate percentage change and format string."""
    if baseline == 0:
        return 0, "N/A"
    
    change = ((current - baseline) / baseline) * 100
    
    if change > 0:
        symbol = "🔴"  # Regression
        prefix = "+"
    elif change < 0:
        symbol = "🟢"  # Improvement
        prefix = ""
    else:
        symbol = "⚪"  # No change
        prefix = ""
    
    return change, f"{symbol} {prefix}{change:.1f}%"

def check_regression(baseline_metrics: Dict[str, float], current_metrics: Dict[str, float], thresholds: Dict[str, float]) -> Tuple[bool, list]:
    """Check if there's a regression based on thresholds."""
    regressions = []
    
    for metric, threshold in thresholds.items():
        if metric not in baseline_metrics or metric not in current_metrics:
            continue
            
        baseline = baseline_metrics[metric]
        current = current_metrics[metric]
        
        if metric == 'success_rate':
            # For success rate, lower is worse
            if current < baseline - threshold:
                regressions.append(f"{metric}: {current:.2f}% (threshold: {baseline - threshold:.2f}%)")
        else:
            # For latency metrics, higher is worse
            change_percent = ((current - baseline) / baseline) * 100 if baseline > 0 else 0
            if change_percent > threshold:
                regressions.append(f"{metric}: +{change_percent:.1f}% (threshold: +{threshold}%)")
    
    return len(regressions) > 0, regressions

def generate_report(baseline_metrics: Dict[str, float], current_metrics: Dict[str, float]) -> str:
    """Generate a markdown report comparing performance."""
    report = []
    report.append("## 📊 Performance Test Results\n")
    
    # Summary table
    report.append("### Summary")
    report.append("| Metric | Baseline | Current | Change |")
    report.append("|--------|----------|---------|--------|")
    
    metrics_display = [
        ('latency_mean', 'Mean Latency', 'ms'),
        ('latency_p50', 'P50 Latency', 'ms'),
        ('latency_p95', 'P95 Latency', 'ms'),
        ('latency_p99', 'P99 Latency', 'ms'),
        ('success_rate', 'Success Rate', '%'),
        ('throughput', 'Throughput', 'req/s'),
    ]
    
    for metric_key, metric_name, unit in metrics_display:
        baseline = baseline_metrics.get(metric_key, 0)
        current = current_metrics.get(metric_key, 0)
        _, change_str = calculate_change(baseline, current)
        
        if unit == '%':
            report.append(f"| {metric_name} | {baseline:.2f}{unit} | {current:.2f}{unit} | {change_str} |")
        elif unit == 'req/s':
            report.append(f"| {metric_name} | {baseline:.0f} {unit} | {current:.0f} {unit} | {change_str} |")
        else:
            report.append(f"| {metric_name} | {baseline:.2f} {unit} | {current:.2f} {unit} | {change_str} |")
    
    # Strict regression check - any increase in P99 over 1.5ms fails
    thresholds = {
        'latency_p99': 0.0,  # No tolerance - P99 must stay under 1.5ms absolute
        'latency_p95': 5.0,  # Allow only 5% increase in P95 latency
        'success_rate': 0.1,  # Allow only 0.1% decrease in success rate
    }
    
    has_regression, regressions = check_regression(baseline_metrics, current_metrics, thresholds)
    
    # Also check absolute P99 threshold
    absolute_p99_fail = current_metrics.get('latency_p99', 0) > 1.5
    
    report.append("\n### Performance Check")
    if has_regression or absolute_p99_fail:
        report.append("❌ **Performance regression detected!**")
        if absolute_p99_fail:
            report.append(f"\n**CRITICAL**: P99 latency ({current_metrics['latency_p99']:.2f}ms) exceeds absolute threshold of 1.5ms")
        if has_regression:
            report.append("\nThe following metrics exceeded acceptable thresholds:")
            for regression in regressions:
                report.append(f"- {regression}")
    else:
        report.append("✅ **No performance regression detected**")
        report.append("\nAll metrics are within acceptable thresholds.")
        report.append(f"\nP99 latency: {current_metrics['latency_p99']:.2f}ms (threshold: 1.5ms)")
    
    # Details section
    report.append("\n<details>")
    report.append("<summary>Detailed Metrics</summary>\n")
    report.append("| Metric | Baseline | Current | Change |")
    report.append("|--------|----------|---------|--------|")
    
    all_metrics = [
        ('latency_mean', 'Mean Latency', 'ms'),
        ('latency_p50', 'P50 Latency', 'ms'),
        ('latency_p95', 'P95 Latency', 'ms'),
        ('latency_p99', 'P99 Latency', 'ms'),
        ('latency_max', 'Max Latency', 'ms'),
        ('success_rate', 'Success Rate', '%'),
        ('throughput', 'Throughput', 'req/s'),
        ('total_requests', 'Total Requests', ''),
    ]
    
    for metric_key, metric_name, unit in all_metrics:
        baseline = baseline_metrics.get(metric_key, 0)
        current = current_metrics.get(metric_key, 0)
        _, change_str = calculate_change(baseline, current)
        
        if unit == '%':
            report.append(f"| {metric_name} | {baseline:.2f}{unit} | {current:.2f}{unit} | {change_str} |")
        elif unit == 'req/s' or unit == '':
            report.append(f"| {metric_name} | {baseline:.0f} {unit} | {current:.0f} {unit} | {change_str} |")
        else:
            report.append(f"| {metric_name} | {baseline:.2f} {unit} | {current:.2f} {unit} | {change_str} |")
    
    report.append("\n</details>")
    
    return '\n'.join(report)

def main():
    if len(sys.argv) != 3:
        print("Usage: python compare-performance.py <baseline.json> <current.json>")
        sys.exit(1)
    
    baseline_file = sys.argv[1]
    current_file = sys.argv[2]
    
    # Load results
    baseline_results = load_results(baseline_file)
    current_results = load_results(current_file)
    
    # Extract metrics
    baseline_metrics = extract_metrics(baseline_results)
    current_metrics = extract_metrics(current_results)
    
    # Generate report
    report = generate_report(baseline_metrics, current_metrics)
    print(report)
    
    # Check for regression with strict thresholds
    thresholds = {
        'latency_p99': 0.0,  # No tolerance - P99 must stay under 1.5ms absolute
        'latency_p95': 5.0,  # Allow only 5% increase in P95 latency
        'success_rate': 0.1,  # Allow only 0.1% decrease in success rate
    }
    has_regression, _ = check_regression(baseline_metrics, current_metrics, thresholds)
    
    # Also check absolute P99 threshold
    absolute_p99_fail = current_metrics.get('latency_p99', 0) > 1.5
    
    # Exit with error if regression detected or P99 > 1.5ms
    sys.exit(1 if (has_regression or absolute_p99_fail) else 0)

if __name__ == "__main__":
    main()