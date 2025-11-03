#!/bin/bash
# Скрипт для локального запуска Docker тестов

set -e

# Цвета для вывода
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║     Sysaudit Docker Test Pipeline                     ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════╝${NC}"

# Создание директорий для результатов
mkdir -p test-results htmlcov

# Функция для логирования
log() {
    echo -e "${BLUE}[$(date +'%H:%M:%S')]${NC} $1"
}

success() {
    echo -e "${GREEN}✓${NC} $1"
}

error() {
    echo -e "${RED}✗${NC} $1"
}

warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

# Проверка Docker
log "Проверка Docker..."
if ! command -v docker &> /dev/null; then
    error "Docker не установлен"
    exit 1
fi
success "Docker установлен"

# Проверка docker-compose
log "Проверка docker-compose..."
if ! command -v docker-compose &> /dev/null; then
    warning "docker-compose не установлен, используем docker compose"
    COMPOSE_CMD="docker compose"
else
    COMPOSE_CMD="docker-compose"
fi

# Очистка старых контейнеров
log "Очистка старых контейнеров..."
$COMPOSE_CMD down -v 2>/dev/null || true
success "Очистка завершена"

# Сборка образа
log "Сборка Docker образа..."
if docker build -t sysaudit:test .; then
    success "Образ собран успешно"
else
    error "Ошибка сборки образа"
    exit 1
fi

# Запуск тестов
echo ""
log "Запуск тестов..."
echo ""

# Unit тесты
echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  Unit Tests${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
if docker run --rm \
    -v "$(pwd)/test-results:/app/test-results" \
    -v "$(pwd)/htmlcov:/app/htmlcov" \
    sysaudit:test \
    python run_tests.py --unit --coverage --html-coverage; then
    success "Unit тесты пройдены"
else
    error "Unit тесты провалены"
    exit 1
fi

# Integration тесты
echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  Integration Tests${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
if docker run --rm \
    -v "$(pwd)/test-results:/app/test-results" \
    sysaudit:test \
    python run_tests.py --integration; then
    success "Integration тесты пройдены"
else
    error "Integration тесты провалены"
    exit 1
fi

# Compliance тесты
echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  Compliance Tests${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
if docker run --rm \
    -v "$(pwd)/test-results:/app/test-results" \
    sysaudit:test \
    python run_tests.py --compliance; then
    success "Compliance тесты пройдены"
else
    error "Compliance тесты провалены"
    exit 1
fi

# E2E тесты
echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  E2E Tests (Real User Scenarios)${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
if docker run --rm \
    --user root \
    -v "$(pwd)/test-results:/app/test-results" \
    -e PYTHONUNBUFFERED=1 \
    sysaudit:test \
    python tests/e2e/test_real_user_scenarios.py; then
    success "E2E тесты пройдены"
else
    error "E2E тесты провалены"
    exit 1
fi

# Генерация итогового отчета
echo ""
log "Генерация итогового отчета..."

python3 << 'EOF'
import json
import os
from datetime import datetime
from pathlib import Path

# Сбор результатов
test_results_dir = Path("test-results")
report = {
    "timestamp": datetime.now().isoformat(),
    "project": "sysaudit",
    "version": "0.1.0",
    "tests": {}
}

# Поиск JSON отчетов
for json_file in test_results_dir.glob("*.json"):
    try:
        with open(json_file) as f:
            data = json.load(f)
            test_type = json_file.stem.replace("-report", "")
            report["tests"][test_type] = data
    except Exception as e:
        print(f"Error reading {json_file}: {e}")

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

# Вывод отчета
print("\n" + "="*60)
print("FINAL TEST REPORT")
print("="*60)
print(f"Project: {report['project']}")
print(f"Version: {report['version']}")
print(f"Timestamp: {report['timestamp']}")
print("\nSummary:")
print(f"  Total Tests: {report['summary']['total_tests']}")
print(f"  Passed: {report['summary']['passed']} ✓")
print(f"  Failed: {report['summary']['failed']} ✗")
print(f"  Success Rate: {report['summary']['success_rate']}")
print("\nTest Results by Type:")
for test_type, data in report["tests"].items():
    if isinstance(data, dict):
        print(f"\n  {test_type.upper()}:")
        print(f"    Passed: {data.get('passed', 'N/A')}")
        print(f"    Failed: {data.get('failed', 'N/A')}")
        if 'duration_seconds' in data:
            print(f"    Duration: {data['duration_seconds']:.2f}s")
print("="*60)
EOF

success "Отчет сгенерирован"

# Итоговое сообщение
echo ""
echo -e "${GREEN}╔════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  Все тесты успешно пройдены!                          ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "Результаты тестов: ${BLUE}test-results/${NC}"
echo -e "Coverage отчет: ${BLUE}htmlcov/index.html${NC}"
echo -e "Итоговый отчет: ${BLUE}test-results/final-report.json${NC}"
echo ""
