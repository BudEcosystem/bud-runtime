#!/usr/bin/env python3
"""E2E test runner with comprehensive reporting.

Usage:
    ./run_tests.py                     # Run all tests
    ./run_tests.py --scenario smoke    # Run smoke tests only
    ./run_tests.py --scenario full     # Run full test suite
    ./run_tests.py --report html       # Generate HTML report
    ./run_tests.py --clusters app=app-cluster,inference=inference-cluster
"""

import os
import sys
import json
import time
import argparse
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import logging

# Add test directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from e2e.utils import setup_logging, get_kubernetes_clients
except ImportError:
    # Fallback imports if running from different location
    from utils import setup_logging, get_kubernetes_clients


# Test scenarios configuration
TEST_SCENARIOS = {
    "smoke": {
        "description": "Quick smoke tests",
        "marks": ["-m", "smoke"],
        "timeout": 300,
    },
    "functional": {
        "description": "Core functional tests",
        "marks": ["-m", "not slow and not load and not gpu"],
        "timeout": 1200,
    },
    "integration": {
        "description": "Integration tests",
        "marks": ["-m", "integration"],
        "timeout": 1800,
    },
    "failover": {
        "description": "Failover and resilience tests",
        "marks": ["-m", "failover"],
        "timeout": 1800,
    },
    "performance": {
        "description": "Performance and load tests",
        "marks": ["-m", "load or performance"],
        "timeout": 3600,
    },
    "full": {
        "description": "Complete test suite",
        "marks": [],
        "timeout": 7200,
    },
}


class TestRunner:
    """Orchestrates E2E test execution."""
    
    def __init__(self, args):
        self.args = args
        self.results = {}
        self.start_time = None
        self.end_time = None
        self.test_dir = Path(__file__).parent
        self.report_dir = self.test_dir / "reports"
        self.report_dir.mkdir(exist_ok=True)
        
        # Setup logging
        log_file = self.report_dir / f"test_run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        self.logger = setup_logging(log_file=str(log_file))
    
    def run(self) -> int:
        """Run the test suite."""
        self.start_time = datetime.now()
        self.logger.info(f"Starting E2E test run at {self.start_time}")
        
        # Check prerequisites
        if not self._check_prerequisites():
            return 1
        
        # Setup test environment
        self._setup_environment()
        
        # Run test scenarios
        exit_code = 0
        scenario = self.args.scenario
        
        if scenario in TEST_SCENARIOS:
            self.logger.info(f"Running {scenario} tests: {TEST_SCENARIOS[scenario]['description']}")
            result = self._run_scenario(scenario)
            if not result["success"]:
                exit_code = 1
            self.results[scenario] = result
        else:
            self.logger.error(f"Unknown scenario: {scenario}")
            return 1
        
        self.end_time = datetime.now()
        duration = (self.end_time - self.start_time).total_seconds()
        
        # Generate reports
        self._generate_reports()
        
        # Print summary
        self._print_summary(duration)
        
        return exit_code
    
    def _check_prerequisites(self) -> bool:
        """Check if prerequisites are met."""
        self.logger.info("Checking prerequisites...")
        
        # Check if pytest is installed
        try:
            subprocess.run(["pytest", "--version"], capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            self.logger.error("pytest is not installed. Run: pip install -r requirements-test.txt")
            return False
        
        # Check Kubernetes connectivity
        try:
            app_client, inference_client = get_kubernetes_clients()
            app_client.list_namespace()
            self.logger.info("✓ Kubernetes connectivity verified")
        except Exception as e:
            self.logger.error(f"Failed to connect to Kubernetes: {e}")
            return False
        
        # Check if services are deployed
        if self.args.check_services:
            if not self._verify_services():
                self.logger.error("Required services are not deployed")
                return False
        
        return True
    
    def _setup_environment(self):
        """Setup test environment variables."""
        self.logger.info("Setting up test environment...")
        
        # Set cluster contexts if provided
        if self.args.clusters:
            for cluster_config in self.args.clusters.split(","):
                role, context = cluster_config.split("=")
                env_var = f"K8S_{role.upper()}_CONTEXT"
                os.environ[env_var] = context
                self.logger.info(f"Set {env_var}={context}")
        
        # Set test configuration
        if self.args.endpoint:
            os.environ["BUDPROXY_ENDPOINT"] = self.args.endpoint
        
        if self.args.models:
            os.environ["TEST_MODELS"] = self.args.models
        
        # Set parallel execution
        if self.args.parallel:
            os.environ["PYTEST_XDIST_WORKER_COUNT"] = str(self.args.parallel)
    
    def _run_scenario(self, scenario: str) -> Dict:
        """Run a test scenario."""
        config = TEST_SCENARIOS[scenario]
        start_time = time.time()
        
        # Build pytest command
        cmd = [
            "pytest",
            "-v",
            "--tb=short",
            "--color=yes",
            f"--timeout={config['timeout']}",
            "--json-report",
            f"--json-report-file={self.report_dir}/{scenario}_report.json",
        ]
        
        # Add marks
        cmd.extend(config["marks"])
        
        # Add parallel execution
        if self.args.parallel > 1:
            cmd.extend(["-n", str(self.args.parallel)])
        
        # Add custom options
        if self.args.pytest_args:
            cmd.extend(self.args.pytest_args.split())
        
        # Add test directory
        cmd.append(str(self.test_dir))
        
        self.logger.info(f"Running command: {' '.join(cmd)}")
        
        # Run tests
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        duration = time.time() - start_time
        
        # Parse results
        report_file = self.report_dir / f"{scenario}_report.json"
        test_results = {}
        if report_file.exists():
            with open(report_file) as f:
                test_results = json.load(f)
        
        return {
            "success": result.returncode == 0,
            "duration": duration,
            "exit_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "tests": test_results.get("tests", []),
            "summary": test_results.get("summary", {}),
        }
    
    def _verify_services(self) -> bool:
        """Verify required services are running."""
        self.logger.info("Verifying services...")
        
        try:
            app_client, inference_client = get_kubernetes_clients()
            
            # Check BudProxy
            services = app_client.list_namespaced_service(namespace="bud-system")
            budproxy_found = any(s.metadata.name == "budproxy" for s in services.items)
            
            if not budproxy_found:
                self.logger.error("BudProxy service not found in bud-system namespace")
                return False
            
            # Check for at least one model
            statefulsets = inference_client.list_namespaced_stateful_set(
                namespace="inference-system"
            )
            
            if not statefulsets.items:
                self.logger.warning("No model deployments found in inference-system namespace")
            
            self.logger.info("✓ Services verified")
            return True
            
        except Exception as e:
            self.logger.error(f"Service verification failed: {e}")
            return False
    
    def _generate_reports(self):
        """Generate test reports."""
        self.logger.info("Generating reports...")
        
        # Generate summary JSON
        summary_file = self.report_dir / "test_summary.json"
        summary = {
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "duration": (self.end_time - self.start_time).total_seconds(),
            "scenarios": self.results,
            "environment": {
                "clusters": self.args.clusters,
                "endpoint": self.args.endpoint,
                "models": self.args.models,
            },
        }
        
        with open(summary_file, "w") as f:
            json.dump(summary, f, indent=2)
        
        # Generate HTML report if requested
        if self.args.report == "html":
            self._generate_html_report(summary)
        
        # Generate JUnit XML if requested
        elif self.args.report == "junit":
            self._generate_junit_report(summary)
    
    def _generate_html_report(self, summary: Dict):
        """Generate HTML test report."""
        html_file = self.report_dir / "test_report.html"
        
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>E2E Test Report - {self.start_time.strftime('%Y-%m-%d %H:%M')}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        h1, h2 {{ color: #333; }}
        .summary {{ background: #f0f0f0; padding: 15px; border-radius: 5px; }}
        .scenario {{ margin: 20px 0; border: 1px solid #ddd; padding: 15px; }}
        .success {{ color: green; }}
        .failure {{ color: red; }}
        .test-list {{ margin: 10px 0; }}
        .test-item {{ margin: 5px 0; padding: 5px; }}
        .passed {{ background: #d4edda; }}
        .failed {{ background: #f8d7da; }}
        .skipped {{ background: #fff3cd; }}
        table {{ border-collapse: collapse; width: 100%; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background: #f2f2f2; }}
    </style>
</head>
<body>
    <h1>E2E Test Report</h1>
    <div class="summary">
        <h2>Summary</h2>
        <p><strong>Start Time:</strong> {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}</p>
        <p><strong>End Time:</strong> {self.end_time.strftime('%Y-%m-%d %H:%M:%S')}</p>
        <p><strong>Duration:</strong> {summary['duration']:.2f} seconds</p>
        <p><strong>Environment:</strong></p>
        <ul>
            <li>Clusters: {summary['environment']['clusters'] or 'default'}</li>
            <li>Endpoint: {summary['environment']['endpoint'] or 'default'}</li>
            <li>Models: {summary['environment']['models'] or 'default'}</li>
        </ul>
    </div>
"""
        
        # Add scenario results
        for scenario, result in self.results.items():
            status_class = "success" if result["success"] else "failure"
            status_text = "PASSED" if result["success"] else "FAILED"
            
            html_content += f"""
    <div class="scenario">
        <h2>{scenario.title()} - <span class="{status_class}">{status_text}</span></h2>
        <p><strong>Duration:</strong> {result['duration']:.2f} seconds</p>
"""
            
            if result.get("summary"):
                summary_info = result["summary"]
                html_content += f"""
        <table>
            <tr>
                <th>Total Tests</th>
                <th>Passed</th>
                <th>Failed</th>
                <th>Skipped</th>
                <th>Errors</th>
            </tr>
            <tr>
                <td>{summary_info.get('total', 0)}</td>
                <td class="success">{summary_info.get('passed', 0)}</td>
                <td class="failure">{summary_info.get('failed', 0)}</td>
                <td>{summary_info.get('skipped', 0)}</td>
                <td class="failure">{summary_info.get('error', 0)}</td>
            </tr>
        </table>
"""
            
            # Add failed tests details
            if result.get("tests"):
                failed_tests = [t for t in result["tests"] if t.get("outcome") == "failed"]
                if failed_tests:
                    html_content += """
        <h3>Failed Tests</h3>
        <div class="test-list">
"""
                    for test in failed_tests:
                        html_content += f"""
            <div class="test-item failed">
                <strong>{test['nodeid']}</strong><br>
                <pre>{test.get('call', {}).get('longrepr', 'No error details')}</pre>
            </div>
"""
                    html_content += "</div>"
            
            html_content += "</div>"
        
        html_content += """
</body>
</html>
"""
        
        with open(html_file, "w") as f:
            f.write(html_content)
        
        self.logger.info(f"HTML report generated: {html_file}")
    
    def _generate_junit_report(self, summary: Dict):
        """Generate JUnit XML report."""
        junit_file = self.report_dir / "junit_report.xml"
        
        # Simple JUnit XML generation
        xml_content = '<?xml version="1.0" encoding="UTF-8"?>\n'
        xml_content += '<testsuites>\n'
        
        for scenario, result in self.results.items():
            summary_info = result.get("summary", {})
            xml_content += f'  <testsuite name="{scenario}" '
            xml_content += f'tests="{summary_info.get("total", 0)}" '
            xml_content += f'failures="{summary_info.get("failed", 0)}" '
            xml_content += f'errors="{summary_info.get("error", 0)}" '
            xml_content += f'skipped="{summary_info.get("skipped", 0)}" '
            xml_content += f'time="{result["duration"]:.2f}">\n'
            
            # Add test cases
            for test in result.get("tests", []):
                xml_content += f'    <testcase classname="{test.get("nodeid", "").split("::")[0]}" '
                xml_content += f'name="{test.get("nodeid", "").split("::")[-1]}" '
                xml_content += f'time="{test.get("duration", 0):.2f}">\n'
                
                if test.get("outcome") == "failed":
                    xml_content += '      <failure message="Test failed">\n'
                    xml_content += f'        {test.get("call", {}).get("longrepr", "")}\n'
                    xml_content += '      </failure>\n'
                elif test.get("outcome") == "skipped":
                    xml_content += '      <skipped />\n'
                
                xml_content += '    </testcase>\n'
            
            xml_content += '  </testsuite>\n'
        
        xml_content += '</testsuites>\n'
        
        with open(junit_file, "w") as f:
            f.write(xml_content)
        
        self.logger.info(f"JUnit report generated: {junit_file}")
    
    def _print_summary(self, duration: float):
        """Print test summary to console."""
        print("\n" + "="*60)
        print("E2E TEST SUMMARY")
        print("="*60)
        print(f"Total Duration: {duration:.2f} seconds")
        print()
        
        total_passed = 0
        total_failed = 0
        total_skipped = 0
        
        for scenario, result in self.results.items():
            summary_info = result.get("summary", {})
            passed = summary_info.get("passed", 0)
            failed = summary_info.get("failed", 0)
            skipped = summary_info.get("skipped", 0)
            
            total_passed += passed
            total_failed += failed
            total_skipped += skipped
            
            status = "✓ PASSED" if result["success"] else "✗ FAILED"
            print(f"{scenario.upper()}: {status}")
            print(f"  Duration: {result['duration']:.2f}s")
            print(f"  Tests: {passed} passed, {failed} failed, {skipped} skipped")
            print()
        
        print("-"*60)
        print(f"TOTAL: {total_passed} passed, {total_failed} failed, {total_skipped} skipped")
        print(f"Reports saved to: {self.report_dir}")
        print("="*60)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="E2E Test Runner")
    
    parser.add_argument(
        "--scenario",
        choices=list(TEST_SCENARIOS.keys()),
        default="smoke",
        help="Test scenario to run"
    )
    
    parser.add_argument(
        "--clusters",
        help="Cluster contexts (e.g., app=context1,inference=context2)"
    )
    
    parser.add_argument(
        "--endpoint",
        help="BudProxy endpoint URL"
    )
    
    parser.add_argument(
        "--models",
        help="Comma-separated list of models to test"
    )
    
    parser.add_argument(
        "--parallel",
        type=int,
        default=1,
        help="Number of parallel test workers"
    )
    
    parser.add_argument(
        "--report",
        choices=["html", "junit", "json"],
        default="json",
        help="Report format"
    )
    
    parser.add_argument(
        "--check-services",
        action="store_true",
        help="Verify services before running tests"
    )
    
    parser.add_argument(
        "--pytest-args",
        help="Additional arguments to pass to pytest"
    )
    
    args = parser.parse_args()
    
    # Run tests
    runner = TestRunner(args)
    exit_code = runner.run()
    
    sys.exit(exit_code)


if __name__ == "__main__":
    main()