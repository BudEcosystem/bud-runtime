"""Test runner script for comprehensive test execution."""

import sys
import subprocess
import argparse
from pathlib import Path


def run_tests(test_type: str = "all", verbose: bool = True, coverage: bool = False):
    """Run tests based on type specification."""

    # Base pytest command
    cmd = ["python", "-m", "pytest"]

    if verbose:
        cmd.append("-v")

    if coverage:
        cmd.extend([
            "--cov=budmetrics",
            "--cov-report=html",
            "--cov-report=term-missing",
            "--cov-fail-under=80"
        ])

    # Add test paths based on type
    if test_type == "unit":
        cmd.append("tests/unit/")
    elif test_type == "integration":
        cmd.append("tests/integration/")
    elif test_type == "performance":
        cmd.append("tests/performance/")
    elif test_type == "all":
        cmd.append("tests/")
    else:
        print(f"Unknown test type: {test_type}")
        return False

    # Add markers for specific test types
    if test_type != "all":
        cmd.extend(["-m", test_type])

    print(f"Running command: {' '.join(cmd)}")

    try:
        result = subprocess.run(cmd, check=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Tests failed with exit code: {e.returncode}")
        return False


def run_specific_test_suites():
    """Run specific test suites for comprehensive coverage."""

    test_suites = [
        ("Unit Tests - Frequency and Time Handling", "tests/unit/observability/test_models_frequency.py"),
        ("Unit Tests - TimeSeriesHelper", "tests/unit/observability/test_time_series_helper.py"),
        ("Unit Tests - QueryBuilder Basic", "tests/unit/observability/test_query_builder_basic.py"),
        ("Unit Tests - QueryBuilder Advanced", "tests/unit/observability/test_query_builder_advanced.py"),
        ("Unit Tests - ClickHouse Client", "tests/unit/observability/test_clickhouse_client.py"),
        ("Unit Tests - Services", "tests/unit/observability/test_services.py"),
        ("Unit Tests - Schemas", "tests/unit/observability/test_schemas.py"),
        ("Integration Tests - API Routes", "tests/integration/test_routes.py"),
        ("Performance & Edge Cases", "tests/performance/test_performance_edge_cases.py"),
    ]

    results = {}

    for suite_name, test_path in test_suites:
        print(f"\n{'='*60}")
        print(f"Running: {suite_name}")
        print(f"{'='*60}")

        cmd = ["python", "-m", "pytest", test_path, "-v"]

        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            results[suite_name] = "PASSED"
            print(f"✅ {suite_name}: PASSED")
        except subprocess.CalledProcessError as e:
            results[suite_name] = "FAILED"
            print(f"❌ {suite_name}: FAILED")
            print(f"Error output:\n{e.stdout}\n{e.stderr}")

    # Print summary
    print(f"\n{'='*60}")
    print("TEST SUMMARY")
    print(f"{'='*60}")

    passed = sum(1 for status in results.values() if status == "PASSED")
    failed = sum(1 for status in results.values() if status == "FAILED")

    for suite_name, status in results.items():
        status_icon = "✅" if status == "PASSED" else "❌"
        print(f"{status_icon} {suite_name}: {status}")

    print(f"\nTotal: {len(results)} suites, {passed} passed, {failed} failed")

    if failed == 0:
        print("\n🎉 All test suites passed!")
        return True
    else:
        print(f"\n⚠️  {failed} test suite(s) failed.")
        return False


def main():
    """Main test runner function."""
    parser = argparse.ArgumentParser(description="Run bud-serve-metrics tests")
    parser.add_argument(
        "--type",
        choices=["unit", "integration", "performance", "all"],
        default="all",
        help="Type of tests to run"
    )
    parser.add_argument(
        "--coverage",
        action="store_true",
        help="Run tests with coverage reporting"
    )
    parser.add_argument(
        "--suites",
        action="store_true",
        help="Run individual test suites with detailed reporting"
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Run tests in quiet mode"
    )

    args = parser.parse_args()

    if args.suites:
        success = run_specific_test_suites()
    else:
        success = run_tests(
            test_type=args.type,
            verbose=not args.quiet,
            coverage=args.coverage
        )

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
