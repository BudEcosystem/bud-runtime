#!/usr/bin/env python3
"""Validate the E2E test framework structure and basic functionality."""

import os
import sys
import json
import yaml
from pathlib import Path
from typing import Dict, List, Tuple

# Colors for output
GREEN = '\033[0;32m'
YELLOW = '\033[1;33m'
RED = '\033[0;31m'
NC = '\033[0m'


def check_file_exists(filepath: Path, description: str) -> Tuple[bool, str]:
    """Check if a file exists."""
    if filepath.exists():
        return True, f"{GREEN}✓{NC} {description}"
    else:
        return False, f"{RED}✗{NC} {description} - Missing: {filepath}"


def check_directory_structure() -> List[Tuple[bool, str]]:
    """Validate the test directory structure."""
    results = []
    base_dir = Path(__file__).parent
    
    # Essential directories
    dirs_to_check = [
        (base_dir / "e2e", "E2E test directory"),
        (base_dir / "e2e/scenarios", "Test scenarios"),
        (base_dir / "e2e/utils", "Test utilities"),
        (base_dir / "e2e/fixtures", "Test fixtures"),
        (base_dir / "load", "Load test directory"),
        (base_dir / "load/k6", "K6 tests"),
        (base_dir / "load/locust", "Locust tests"),
    ]
    
    for dir_path, desc in dirs_to_check:
        results.append(check_file_exists(dir_path, desc))
    
    return results


def check_essential_files() -> List[Tuple[bool, str]]:
    """Check for essential test files."""
    results = []
    base_dir = Path(__file__).parent
    
    files_to_check = [
        (base_dir / "requirements-test.txt", "Test requirements file"),
        (base_dir / "pytest.ini", "PyTest configuration"),
        (base_dir / "conftest.py", "PyTest fixtures"),
        (base_dir / "e2e/run_tests.py", "Main test runner"),
        (base_dir / "e2e/run_performance_tests.sh", "Performance test runner"),
        (base_dir / "e2e/monitor_tests.py", "Test monitor"),
        (base_dir / "e2e/generate_test_report.py", "Report generator"),
        (base_dir / "e2e/config.yaml", "Test configuration"),
        (base_dir / "e2e/fixtures/test_data.yaml", "Test data"),
    ]
    
    for file_path, desc in files_to_check:
        results.append(check_file_exists(file_path, desc))
    
    return results


def check_test_scenarios() -> List[Tuple[bool, str]]:
    """Check test scenario files."""
    results = []
    scenarios_dir = Path(__file__).parent / "e2e/scenarios"
    
    scenarios = [
        "test_inference_flow.py",
        "test_routing.py",
        "test_autoscaling.py",
        "test_failover.py",
        "test_performance.py",
    ]
    
    for scenario in scenarios:
        file_path = scenarios_dir / scenario
        results.append(check_file_exists(file_path, f"Scenario: {scenario}"))
    
    return results


def validate_yaml_files() -> List[Tuple[bool, str]]:
    """Validate YAML configuration files."""
    results = []
    base_dir = Path(__file__).parent
    
    yaml_files = [
        base_dir / "e2e/config.yaml",
        base_dir / "e2e/fixtures/test_data.yaml",
    ]
    
    for yaml_file in yaml_files:
        if yaml_file.exists():
            try:
                with open(yaml_file) as f:
                    yaml.safe_load(f)
                results.append((True, f"{GREEN}✓{NC} Valid YAML: {yaml_file.name}"))
            except yaml.YAMLError as e:
                results.append((False, f"{RED}✗{NC} Invalid YAML: {yaml_file.name} - {e}"))
        else:
            results.append((False, f"{YELLOW}⚠{NC} YAML file missing: {yaml_file.name}"))
    
    return results


def check_python_syntax() -> List[Tuple[bool, str]]:
    """Check Python files for syntax errors."""
    results = []
    base_dir = Path(__file__).parent
    
    # Find all Python files
    python_files = []
    for pattern in ["e2e/**/*.py", "load/**/*.py"]:
        python_files.extend(base_dir.glob(pattern))
    
    for py_file in python_files[:5]:  # Check first 5 files as sample
        try:
            with open(py_file) as f:
                compile(f.read(), py_file, 'exec')
            results.append((True, f"{GREEN}✓{NC} Valid Python: {py_file.name}"))
        except SyntaxError as e:
            results.append((False, f"{RED}✗{NC} Syntax error in {py_file.name}: {e}"))
    
    return results


def validate_test_data() -> List[Tuple[bool, str]]:
    """Validate test data structure."""
    results = []
    test_data_file = Path(__file__).parent / "e2e/fixtures/test_data.yaml"
    
    if test_data_file.exists():
        try:
            with open(test_data_file) as f:
                data = yaml.safe_load(f)
            
            # Check expected sections
            expected_sections = ["prompts", "expected_patterns", "performance_configs"]
            for section in expected_sections:
                if section in data:
                    results.append((True, f"{GREEN}✓{NC} Test data section: {section}"))
                else:
                    results.append((False, f"{RED}✗{NC} Missing test data section: {section}"))
        except Exception as e:
            results.append((False, f"{RED}✗{NC} Error loading test data: {e}"))
    else:
        results.append((False, f"{RED}✗{NC} Test data file missing"))
    
    return results


def print_results(title: str, results: List[Tuple[bool, str]]):
    """Print validation results."""
    print(f"\n{YELLOW}{title}:{NC}")
    for success, message in results:
        print(f"  {message}")
    
    passed = sum(1 for success, _ in results if success)
    total = len(results)
    
    if passed == total:
        print(f"\n  {GREEN}All {total} checks passed!{NC}")
    else:
        print(f"\n  {YELLOW}Passed: {passed}/{total}{NC}")


def main():
    """Run all validations."""
    print("=" * 60)
    print("E2E Test Framework Validation")
    print("=" * 60)
    
    # Run validations
    validations = [
        ("Directory Structure", check_directory_structure()),
        ("Essential Files", check_essential_files()),
        ("Test Scenarios", check_test_scenarios()),
        ("YAML Files", validate_yaml_files()),
        ("Python Syntax", check_python_syntax()),
        ("Test Data", validate_test_data()),
    ]
    
    total_passed = 0
    total_checks = 0
    
    for title, results in validations:
        print_results(title, results)
        passed = sum(1 for success, _ in results if success)
        total_passed += passed
        total_checks += len(results)
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    if total_passed == total_checks:
        print(f"{GREEN}✓ All {total_checks} validation checks passed!{NC}")
        print(f"\nThe E2E test framework is properly structured and ready to use.")
        return 0
    else:
        print(f"{YELLOW}⚠ {total_passed}/{total_checks} checks passed{NC}")
        print(f"\nSome components are missing. This is expected if:")
        print("  - PyTest configuration files haven't been created yet")
        print("  - You're running this before full setup")
        return 1
    
    print("\nNext steps:")
    print("1. Install dependencies: pip install -r tests/requirements-test.txt")
    print("2. Set up Kubernetes clusters")
    print("3. Deploy services")
    print("4. Run tests: ./e2e/run_tests.py --scenario smoke")


if __name__ == "__main__":
    sys.exit(main())