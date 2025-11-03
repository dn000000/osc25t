#!/usr/bin/env python
"""
Cross-platform test runner script for RPM Dependency Graph project.
Runs all tests and generates coverage reports.
"""

import sys
import subprocess
import argparse
from pathlib import Path


class Colors:
    """ANSI color codes for terminal output"""
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    NC = '\033[0m'  # No Color
    
    @classmethod
    def disable(cls):
        """Disable colors (for Windows or when piping output)"""
        cls.RED = ''
        cls.GREEN = ''
        cls.YELLOW = ''
        cls.BLUE = ''
        cls.NC = ''


def print_message(color, message):
    """Print colored message"""
    print(f"{color}{message}{Colors.NC}")


def print_header(message):
    """Print section header"""
    print()
    print_message(Colors.BLUE, "=" * 60)
    print_message(Colors.BLUE, message)
    print_message(Colors.BLUE, "=" * 60)
    print()


def check_dependencies():
    """Check if required test dependencies are installed"""
    print_header("Checking Dependencies")
    
    try:
        import pytest
        print_message(Colors.GREEN, "✓ pytest is installed")
    except ImportError:
        print_message(Colors.RED, "✗ pytest not installed")
        print_message(Colors.YELLOW, "Installing test dependencies...")
        subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], check=True)
    
    try:
        import pytest_cov
        print_message(Colors.GREEN, "✓ pytest-cov is installed")
    except ImportError:
        print_message(Colors.YELLOW, "Warning: pytest-cov not installed")
        print_message(Colors.YELLOW, "Installing pytest-cov...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pytest-cov"], check=True)


def run_tests(test_path, description):
    """
    Run tests for a specific path.
    
    Args:
        test_path: Path to test directory
        description: Description of test suite
        
    Returns:
        True if tests passed, False otherwise
    """
    print_header(f"Running {description}")
    
    cmd = [
        sys.executable, "-m", "pytest",
        str(test_path),
        "-v",
        "--tb=short"
    ]
    
    result = subprocess.run(cmd)
    
    if result.returncode == 0:
        print_message(Colors.GREEN, f"✓ {description} passed")
        return True
    else:
        print_message(Colors.RED, f"✗ {description} failed")
        return False


def run_tests_with_coverage():
    """
    Run all tests with coverage reporting.
    
    Returns:
        True if tests passed, False otherwise
    """
    print_header("Running All Tests with Coverage")
    
    cmd = [
        sys.executable, "-m", "pytest",
        "tests/",
        "-v",
        "--cov=src",
        "--cov-report=html",
        "--cov-report=term-missing",
        "--cov-report=xml"
    ]
    
    result = subprocess.run(cmd)
    
    if result.returncode == 0:
        print_message(Colors.GREEN, "✓ All tests passed")
        
        # Check if HTML report was generated
        htmlcov_path = Path("htmlcov")
        if htmlcov_path.exists():
            print_message(Colors.GREEN, f"✓ HTML coverage report generated in {htmlcov_path}/")
            print_message(Colors.BLUE, f"Open {htmlcov_path}/index.html in your browser to view the report")
        
        return True
    else:
        print_message(Colors.RED, "✗ Some tests failed")
        return False


def display_summary(unit_result, integration_result, coverage_result):
    """
    Display test results summary.
    
    Args:
        unit_result: Result of unit tests
        integration_result: Result of integration tests
        coverage_result: Result of coverage tests
        
    Returns:
        True if all tests passed, False otherwise
    """
    print_header("Test Summary")
    
    print("Test Results:")
    
    if unit_result:
        print_message(Colors.GREEN, "  ✓ Unit Tests: PASSED")
    else:
        print_message(Colors.RED, "  ✗ Unit Tests: FAILED")
    
    if integration_result:
        print_message(Colors.GREEN, "  ✓ Integration Tests: PASSED")
    else:
        print_message(Colors.RED, "  ✗ Integration Tests: FAILED")
    
    if coverage_result:
        print_message(Colors.GREEN, "  ✓ Coverage: PASSED")
    else:
        print_message(Colors.RED, "  ✗ Coverage: FAILED")
    
    print()
    
    if unit_result and integration_result and coverage_result:
        print_message(Colors.GREEN, "All tests passed! 🎉")
        return True
    else:
        print_message(Colors.RED, "Some tests failed. Please review the output above.")
        return False


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Test runner for RPM Dependency Graph project",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_tests.py              # Run all tests
  python run_tests.py unit         # Run only unit tests
  python run_tests.py integration  # Run only integration tests
  python run_tests.py coverage     # Run all tests with coverage
        """
    )
    
    parser.add_argument(
        'test_type',
        nargs='?',
        default='all',
        choices=['unit', 'integration', 'coverage', 'all'],
        help='Type of tests to run (default: all)'
    )
    
    parser.add_argument(
        '--no-color',
        action='store_true',
        help='Disable colored output'
    )
    
    args = parser.parse_args()
    
    # Disable colors if requested or on Windows
    if args.no_color or sys.platform == 'win32':
        Colors.disable()
    
    print_header("RPM Dependency Graph - Test Runner")
    
    # Check dependencies
    try:
        check_dependencies()
    except subprocess.CalledProcessError as e:
        print_message(Colors.RED, f"Failed to install dependencies: {e}")
        return 1
    
    # Run tests based on argument
    if args.test_type == 'unit':
        success = run_tests(Path("tests/unit"), "Unit Tests")
        return 0 if success else 1
    
    elif args.test_type == 'integration':
        success = run_tests(Path("tests/integration"), "Integration Tests")
        return 0 if success else 1
    
    elif args.test_type == 'coverage':
        success = run_tests_with_coverage()
        return 0 if success else 1
    
    elif args.test_type == 'all':
        # Run all test suites
        unit_result = run_tests(Path("tests/unit"), "Unit Tests")
        integration_result = run_tests(Path("tests/integration"), "Integration Tests")
        coverage_result = run_tests_with_coverage()
        
        success = display_summary(unit_result, integration_result, coverage_result)
        return 0 if success else 1
    
    return 1


if __name__ == '__main__':
    sys.exit(main())
