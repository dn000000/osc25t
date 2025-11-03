#!/bin/bash
# Test runner script for RPM Dependency Graph project
# Runs all tests and generates coverage reports

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Print colored message
print_message() {
    local color=$1
    local message=$2
    echo -e "${color}${message}${NC}"
}

# Print section header
print_header() {
    echo ""
    print_message "$BLUE" "=========================================="
    print_message "$BLUE" "$1"
    print_message "$BLUE" "=========================================="
    echo ""
}

# Check if virtual environment is activated
check_venv() {
    if [[ -z "$VIRTUAL_ENV" ]]; then
        print_message "$YELLOW" "Warning: Virtual environment not activated"
        print_message "$YELLOW" "Attempting to activate venv..."
        
        if [ -d "venv" ]; then
            source venv/bin/activate
            print_message "$GREEN" "✓ Virtual environment activated"
        else
            print_message "$RED" "Error: Virtual environment not found"
            print_message "$YELLOW" "Please run: python -m venv venv && source venv/bin/activate"
            exit 1
        fi
    else
        print_message "$GREEN" "✓ Virtual environment is active: $VIRTUAL_ENV"
    fi
}

# Check if dependencies are installed
check_dependencies() {
    print_header "Checking Dependencies"
    
    if ! python -c "import pytest" 2>/dev/null; then
        print_message "$RED" "Error: pytest not installed"
        print_message "$YELLOW" "Installing test dependencies..."
        pip install -r requirements.txt
    else
        print_message "$GREEN" "✓ pytest is installed"
    fi
    
    if ! python -c "import pytest_cov" 2>/dev/null; then
        print_message "$YELLOW" "Warning: pytest-cov not installed"
        print_message "$YELLOW" "Installing pytest-cov..."
        pip install pytest-cov
    else
        print_message "$GREEN" "✓ pytest-cov is installed"
    fi
}

# Run unit tests
run_unit_tests() {
    print_header "Running Unit Tests"
    
    if pytest tests/unit/ -v --tb=short; then
        print_message "$GREEN" "✓ Unit tests passed"
        return 0
    else
        print_message "$RED" "✗ Unit tests failed"
        return 1
    fi
}

# Run integration tests
run_integration_tests() {
    print_header "Running Integration Tests"
    
    if pytest tests/integration/ -v --tb=short; then
        print_message "$GREEN" "✓ Integration tests passed"
        return 0
    else
        print_message "$RED" "✗ Integration tests failed"
        return 1
    fi
}

# Run all tests with coverage
run_all_tests_with_coverage() {
    print_header "Running All Tests with Coverage"
    
    if pytest tests/ -v --cov=src --cov-report=html --cov-report=term-missing --cov-report=xml; then
        print_message "$GREEN" "✓ All tests passed"
        return 0
    else
        print_message "$RED" "✗ Some tests failed"
        return 1
    fi
}

# Generate coverage report
generate_coverage_report() {
    print_header "Coverage Report"
    
    if [ -f ".coverage" ]; then
        coverage report --show-missing
        
        if [ -d "htmlcov" ]; then
            print_message "$GREEN" "✓ HTML coverage report generated in htmlcov/"
            print_message "$BLUE" "Open htmlcov/index.html in your browser to view the report"
        fi
    else
        print_message "$YELLOW" "Warning: No coverage data found"
    fi
}

# Display test results summary
display_summary() {
    print_header "Test Summary"
    
    local unit_result=$1
    local integration_result=$2
    local coverage_result=$3
    
    echo "Test Results:"
    if [ $unit_result -eq 0 ]; then
        print_message "$GREEN" "  ✓ Unit Tests: PASSED"
    else
        print_message "$RED" "  ✗ Unit Tests: FAILED"
    fi
    
    if [ $integration_result -eq 0 ]; then
        print_message "$GREEN" "  ✓ Integration Tests: PASSED"
    else
        print_message "$RED" "  ✗ Integration Tests: FAILED"
    fi
    
    if [ $coverage_result -eq 0 ]; then
        print_message "$GREEN" "  ✓ Coverage: PASSED"
    else
        print_message "$RED" "  ✗ Coverage: FAILED"
    fi
    
    echo ""
    
    if [ $unit_result -eq 0 ] && [ $integration_result -eq 0 ] && [ $coverage_result -eq 0 ]; then
        print_message "$GREEN" "All tests passed! 🎉"
        return 0
    else
        print_message "$RED" "Some tests failed. Please review the output above."
        return 1
    fi
}

# Main execution
main() {
    print_header "RPM Dependency Graph - Test Runner"
    
    # Check environment
    check_venv
    check_dependencies
    
    # Parse command line arguments
    case "${1:-all}" in
        unit)
            run_unit_tests
            exit $?
            ;;
        integration)
            run_integration_tests
            exit $?
            ;;
        coverage)
            run_all_tests_with_coverage
            generate_coverage_report
            exit $?
            ;;
        all)
            # Run all test suites
            run_unit_tests
            unit_result=$?
            
            run_integration_tests
            integration_result=$?
            
            run_all_tests_with_coverage
            coverage_result=$?
            
            generate_coverage_report
            
            display_summary $unit_result $integration_result $coverage_result
            exit $?
            ;;
        *)
            print_message "$RED" "Unknown option: $1"
            echo ""
            echo "Usage: $0 [unit|integration|coverage|all]"
            echo ""
            echo "Options:"
            echo "  unit         - Run only unit tests"
            echo "  integration  - Run only integration tests"
            echo "  coverage     - Run all tests with coverage report"
            echo "  all          - Run all test suites (default)"
            exit 1
            ;;
    esac
}

# Run main function
main "$@"
