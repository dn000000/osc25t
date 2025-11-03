#!/bin/bash
# Автоматическая сборка и тестирование проекта sysaudit в Docker
# Использование: ./test-docker.sh [options]

set -e

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Конфигурация
IMAGE_NAME="sysaudit:test"
CONTAINER_NAME="sysaudit-test-runner"
RESULTS_DIR="test-results"
COVERAGE_DIR="htmlcov"

# Флаги
SKIP_BUILD=false
SKIP_UNIT=false
SKIP_INTEGRATION=false
SKIP_E2E=false
SKIP_COVERAGE=false
VERBOSE=false
CLEAN=false
QUICK=false

# Функции для вывода
print_header() {
    echo -e "${BLUE}╔════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║  $1${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════════════════╝${NC}"
}

print_step() {
    echo -e "${CYAN}▶ $1${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ $1${NC}"
}

# Функция помощи
show_help() {
    cat << EOF
Использование: $0 [OPTIONS]

Автоматическая сборка и тестирование проекта sysaudit в Docker

OPTIONS:
    -h, --help              Show this help
    -s, --skip-build        Skip image build
    -u, --skip-unit         Skip unit tests
    -i, --skip-integration  Skip integration tests
    -e, --skip-e2e          Skip E2E tests
    -c, --skip-coverage     Skip coverage generation
    -q, --quick             Quick mode (unit tests only)
    -v, --verbose           Verbose output
    --clean                 Clean results before run
    --no-cache              Build image without cache
    --rebuild               Full rebuild from scratch (clean + no-cache + prune)

EXAMPLES:
    $0                      # Full test run
    $0 --quick              # Quick run (unit only)
    $0 --skip-e2e           # All tests except E2E
    $0 --rebuild            # Complete rebuild from scratch

EOF
}

# Parse arguments
NO_CACHE=""
REBUILD=false
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            exit 0
            ;;
        -s|--skip-build)
            SKIP_BUILD=true
            shift
            ;;
        -u|--skip-unit)
            SKIP_UNIT=true
            shift
            ;;
        -i|--skip-integration)
            SKIP_INTEGRATION=true
            shift
            ;;
        -e|--skip-e2e)
            SKIP_E2E=true
            shift
            ;;
        -c|--skip-coverage)
            SKIP_COVERAGE=true
            shift
            ;;
        -q|--quick)
            QUICK=true
            SKIP_INTEGRATION=true
            SKIP_E2E=true
            shift
            ;;
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        --clean)
            CLEAN=true
            shift
            ;;
        --no-cache)
            NO_CACHE="--no-cache"
            shift
            ;;
        --rebuild)
            REBUILD=true
            CLEAN=true
            NO_CACHE="--no-cache"
            shift
            ;;
        *)
            print_error "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Check Docker
check_docker() {
    print_step "Checking Docker..."
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed"
        exit 1
    fi
    print_success "Docker installed: $(docker --version)"
}

# Cleanup
cleanup() {
    if [ "$CLEAN" = true ]; then
        print_step "Cleaning previous results..."
        rm -rf "$RESULTS_DIR" "$COVERAGE_DIR"
        docker rm -f "$CONTAINER_NAME" 2>/dev/null || true
        print_success "Cleanup completed"
    fi
    
    if [ "$REBUILD" = true ]; then
        print_step "Pruning Docker build cache..."
        docker builder prune -f > /dev/null 2>&1
        print_step "Removing old images..."
        docker rmi -f "$IMAGE_NAME" 2>/dev/null || true
        print_success "Docker cleanup completed"
    fi
}

# Create directories
create_dirs() {
    print_step "Creating result directories..."
    mkdir -p "$RESULTS_DIR" "$COVERAGE_DIR"
    print_success "Directories created"
}

# Build image
build_image() {
    if [ "$SKIP_BUILD" = true ]; then
        print_warning "Skipping image build"
        return
    fi
    
    print_header "DOCKER IMAGE BUILD"
    print_step "Building image $IMAGE_NAME..."
    
    local start_time=$(date +%s)
    
    if [ "$VERBOSE" = true ]; then
        docker build $NO_CACHE -t "$IMAGE_NAME" .
    else
        docker build $NO_CACHE -t "$IMAGE_NAME" . > /dev/null 2>&1
    fi
    
    if [ $? -ne 0 ]; then
        print_error "Image build failed"
        exit 1
    fi
    
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    
    print_success "Image built in ${duration}s"
}

# Run unit tests
run_unit_tests() {
    if [ "$SKIP_UNIT" = true ]; then
        print_warning "Skipping unit tests"
        return 0
    fi
    
    print_header "UNIT TESTS"
    print_step "Running all pytest tests (272 tests including E2E integration tests)..."
    
    local test_args="python -m pytest tests/ -v --ignore=tests/e2e/test_real_user_scenarios.py"
    
    if [ "$SKIP_COVERAGE" = false ]; then
        test_args="$test_args --cov=sysaudit --cov-report=html --cov-report=term-missing"
    fi
    
    output=$(docker run --rm \
        -v "$(pwd)/$RESULTS_DIR:/app/test-results" \
        -v "$(pwd)/$COVERAGE_DIR:/app/htmlcov" \
        "$IMAGE_NAME" \
        bash -c "$test_args" 2>&1)
    exit_code=$?
    
    echo "$output"
    
    # Parse pytest output to create JSON report
    passed=$(echo "$output" | grep -oP '\d+(?= passed)' | tail -1)
    failed=$(echo "$output" | grep -oP '\d+(?= failed)' | tail -1)
    
    passed=${passed:-0}
    failed=${failed:-0}
    total=$((passed + failed))
    
    if [ $total -gt 0 ]; then
        success_rate=$(awk "BEGIN {printf \"%.1f%%\", ($passed / $total) * 100}")
    else
        success_rate="N/A"
    fi
    
    # Create JSON report
    cat > "$RESULTS_DIR/pytest-report.json" <<EOF
{
  "timestamp": "$(date -Iseconds)",
  "test_type": "pytest",
  "passed": $passed,
  "failed": $failed,
  "total": $total,
  "success_rate": "$success_rate"
}
EOF
    
    if [ $exit_code -eq 0 ]; then
        print_success "Unit tests passed ($passed tests)"
        return 0
    else
        print_error "Unit tests failed"
        return 1
    fi
}

# Run integration tests (deprecated - kept for compatibility)
run_integration_tests() {
    if [ "$SKIP_INTEGRATION" = true ]; then
        print_warning "Skipping integration tests"
        return 0
    fi
    
    # Integration tests are now part of unit tests
    print_warning "Integration tests are included in unit tests (skipping separate run)"
    return 0
}

# Run E2E tests
run_e2e_tests() {
    if [ "$SKIP_E2E" = true ]; then
        print_warning "Skipping E2E tests"
        return 0
    fi
    
    print_header "E2E TESTS"
    print_step "Running E2E user scenario tests (20 scenarios)..."
    
    if docker run --rm \
        --user root \
        -v "$(pwd)/$RESULTS_DIR:/app/test-results" \
        -e PYTHONUNBUFFERED=1 \
        "$IMAGE_NAME" \
        python tests/e2e/test_real_user_scenarios.py; then
        print_success "E2E scenario tests passed"
        return 0
    else
        print_error "E2E scenario tests failed"
        return 1
    fi
}

# Generate final report
generate_report() {
    print_header "REPORT GENERATION"
    print_step "Creating final report..."
    
    python3 scripts/generate_report.py "$RESULTS_DIR"
    print_success "Report created"
}

# Show results (old function kept for compatibility)
generate_report_old() {
    python3 << 'PYTHON_SCRIPT'
import json
import os
from datetime import datetime
from pathlib import Path

results_dir = Path("test-results")
report = {
    "timestamp": datetime.now().isoformat(),
    "project": "sysaudit",
    "version": "0.1.0",
    "tests": {}
}

# Сбор результатов
for json_file in results_dir.glob("*.json"):
    try:
        with open(json_file) as f:
            data = json.load(f)
            test_type = json_file.stem.replace("-report", "")
            report["tests"][test_type] = data
    except Exception as e:
        print(f"Ошибка чтения {json_file}: {e}")

# Подсчет статистики
total_passed = sum(t.get("passed", 0) for t in report["tests"].values() if isinstance(t, dict))
total_failed = sum(t.get("failed", 0) for t in report["tests"].values() if isinstance(t, dict))
total_tests = total_passed + total_failed

report["summary"] = {
    "total_tests": total_tests,
    "passed": total_passed,
    "failed": total_failed,
    "success_rate": f"{(total_passed / total_tests * 100):.1f}%" if total_tests > 0 else "N/A"
}

# Сохранение отчета
with open("test-results/final-report.json", "w") as f:
    json.dump(report, f, indent=2)

print(f"Report saved: test-results/final-report.json")
PYTHON_SCRIPT
}

# Show results
show_results() {
    print_header "TEST RESULTS"
    
    if [ -f "$RESULTS_DIR/final-report.json" ]; then
        python3 scripts/show_report.py "$RESULTS_DIR"
    else
        print_warning "Report not found"
    fi
    
    echo ""
    print_info "Test results: $RESULTS_DIR/"
    
    if [ "$SKIP_COVERAGE" = false ] && [ -f "$COVERAGE_DIR/index.html" ]; then
        print_info "Coverage report: $COVERAGE_DIR/index.html"
    fi
    
    print_info "Final report: $RESULTS_DIR/final-report.json"
}

# Show results (old function kept for compatibility)
show_results_old() {
    if [ -f "$RESULTS_DIR/final-report.json" ]; then
        python3 << 'PYTHON_SCRIPT'
import json
from pathlib import Path

report_file = Path("test-results/final-report.json")
if report_file.exists():
    with open(report_file) as f:
        report = json.load(f)
    
    print("\n" + "="*60)
    print("ИТОГОВЫЙ ОТЧЕТ")
    print("="*60)
    print(f"Проект: {report['project']}")
    print(f"Версия: {report['version']}")
    print(f"Время: {report['timestamp']}")
    print("\nСводка:")
    print(f"  Всего тестов: {report['summary']['total_tests']}")
    print(f"  Пройдено: {report['summary']['passed']} ✓")
    print(f"  Провалено: {report['summary']['failed']} ✗")
    print(f"  Success Rate: {report['summary']['success_rate']}")
    
    if report['tests']:
        print("\nРезультаты по типам:")
        for test_type, data in report['tests'].items():
            if isinstance(data, dict):
                print(f"\n  {test_type.upper()}:")
                print(f"    Пройдено: {data.get('passed', 'N/A')}")
                print(f"    Провалено: {data.get('failed', 'N/A')}")
                if 'duration_seconds' in data:
                    print(f"    Время: {data['duration_seconds']:.2f}s")
    print("="*60)
PYTHON_SCRIPT
    fi
}

# Main function
main() {
    local start_time=$(date +%s)
    local failed=false
    
    print_header "SYSAUDIT DOCKER TEST PIPELINE"
    
    check_docker
    cleanup
    create_dirs
    build_image
    
    # Run tests
    run_unit_tests || failed=true
    
    if [ "$failed" = false ]; then
        run_integration_tests || failed=true
    fi
    
    if [ "$failed" = false ]; then
        run_e2e_tests || failed=true
    fi
    
    # Generate report
    generate_report
    
    # Show results
    local end_time=$(date +%s)
    local total_duration=$((end_time - start_time))
    
    show_results
    
    echo ""
    print_info "Total execution time: ${total_duration}s"
    
    if [ "$failed" = true ]; then
        echo ""
        print_error "Some tests failed"
        exit 1
    else
        echo ""
        print_success "All tests passed successfully!"
        exit 0
    fi
}

# Run
main
