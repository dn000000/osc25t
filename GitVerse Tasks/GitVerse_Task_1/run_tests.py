#!/usr/bin/env python3
"""
Test runner script for sysaudit

This script provides a convenient way to run tests with various options.
It wraps pytest with common configurations and provides additional functionality.

Usage:
    python run_tests.py                    # Run all tests
    python run_tests.py --unit             # Run only unit tests
    python run_tests.py --integration      # Run only integration tests
    python run_tests.py --compliance       # Run only compliance tests
    python run_tests.py --coverage         # Run with coverage report
    python run_tests.py --verbose          # Run with verbose output
    python run_tests.py --fast             # Skip slow tests
    python run_tests.py tests/test_filter.py  # Run specific test file
"""

import sys
import os
import argparse
import subprocess
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(
        description='Run sysaudit test suite',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    # Test selection options
    parser.add_argument(
        '--unit', '-u',
        action='store_true',
        help='Run only unit tests'
    )
    parser.add_argument(
        '--integration', '-i',
        action='store_true',
        help='Run only integration tests'
    )
    parser.add_argument(
        '--compliance', '-c',
        action='store_true',
        help='Run only compliance tests'
    )
    parser.add_argument(
        '--fast', '-f',
        action='store_true',
        help='Skip slow tests'
    )
    
    # Output options
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Verbose output'
    )
    parser.add_argument(
        '--quiet', '-q',
        action='store_true',
        help='Quiet output (only show summary)'
    )
    parser.add_argument(
        '--coverage',
        action='store_true',
        help='Generate coverage report'
    )
    parser.add_argument(
        '--html-coverage',
        action='store_true',
        help='Generate HTML coverage report'
    )
    
    # Test execution options
    parser.add_argument(
        '--failfast', '-x',
        action='store_true',
        help='Stop on first failure'
    )
    parser.add_argument(
        '--last-failed', '--lf',
        action='store_true',
        help='Run only tests that failed last time'
    )
    parser.add_argument(
        '--failed-first', '--ff',
        action='store_true',
        help='Run failed tests first, then others'
    )
    parser.add_argument(
        '--parallel', '-n',
        type=int,
        metavar='NUM',
        help='Run tests in parallel with NUM workers'
    )
    
    # Specific test selection
    parser.add_argument(
        'tests',
        nargs='*',
        help='Specific test files or directories to run'
    )
    
    # Additional pytest arguments
    parser.add_argument(
        '--pytest-args',
        nargs=argparse.REMAINDER,
        help='Additional arguments to pass to pytest'
    )
    
    args = parser.parse_args()
    
    # Build pytest command
    cmd = [sys.executable, '-m', 'pytest']
    
    # Add test selection markers
    markers = []
    if args.unit:
        markers.append('unit')
    if args.integration:
        markers.append('integration')
    if args.compliance:
        markers.append('compliance')
    
    if markers:
        cmd.extend(['-m', ' or '.join(markers)])
    
    # Add fast option (skip slow tests)
    if args.fast:
        cmd.extend(['-m', 'not slow'])
    
    # Add verbosity options
    if args.verbose:
        cmd.append('-vv')
    elif args.quiet:
        cmd.append('-q')
    else:
        cmd.append('-v')
    
    # Add coverage options
    if args.coverage or args.html_coverage:
        cmd.extend(['--cov=sysaudit', '--cov-report=term-missing'])
        if args.html_coverage:
            cmd.append('--cov-report=html')
    
    # Add execution options
    if args.failfast:
        cmd.append('-x')
    if args.last_failed:
        cmd.append('--lf')
    if args.failed_first:
        cmd.append('--ff')
    if args.parallel:
        cmd.extend(['-n', str(args.parallel)])
    
    # Add specific tests or default to tests directory
    if args.tests:
        cmd.extend(args.tests)
    else:
        cmd.append('tests')
    
    # Add any additional pytest arguments
    if args.pytest_args:
        cmd.extend(args.pytest_args)
    
    # Print command for debugging
    print(f"Running: {' '.join(cmd)}")
    print("-" * 70)
    
    # Run pytest
    try:
        result = subprocess.run(cmd)
        return result.returncode
    except KeyboardInterrupt:
        print("\n\nTest run interrupted by user")
        return 130
    except Exception as e:
        print(f"\nError running tests: {e}", file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
