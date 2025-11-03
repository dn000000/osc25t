# PowerShell скрипт для запуска Docker тестов на Windows

$ErrorActionPreference = "Stop"

# Цвета для вывода
function Write-ColorOutput($ForegroundColor) {
    $fc = $host.UI.RawUI.ForegroundColor
    $host.UI.RawUI.ForegroundColor = $ForegroundColor
    if ($args) {
        Write-Output $args
    }
    $host.UI.RawUI.ForegroundColor = $fc
}

function Log($message) {
    $timestamp = Get-Date -Format "HH:mm:ss"
    Write-ColorOutput Blue "[$timestamp] $message"
}

function Success($message) {
    Write-ColorOutput Green "✓ $message"
}

function Error($message) {
    Write-ColorOutput Red "✗ $message"
}

function Warning($message) {
    Write-ColorOutput Yellow "⚠ $message"
}

Write-ColorOutput Blue "╔════════════════════════════════════════════════════════╗"
Write-ColorOutput Blue "║     Sysaudit Docker Test Pipeline                     ║"
Write-ColorOutput Blue "╚════════════════════════════════════════════════════════╝"

# Создание директорий для результатов
New-Item -ItemType Directory -Force -Path "test-results" | Out-Null
New-Item -ItemType Directory -Force -Path "htmlcov" | Out-Null

# Проверка Docker
Log "Проверка Docker..."
if (!(Get-Command docker -ErrorAction SilentlyContinue)) {
    Error "Docker не установлен"
    exit 1
}
Success "Docker установлен"

# Очистка старых контейнеров
Log "Очистка старых контейнеров..."
docker-compose down -v 2>$null
Success "Очистка завершена"

# Сборка образа
Log "Сборка Docker образа..."
docker build -t sysaudit:test .
if ($LASTEXITCODE -ne 0) {
    Error "Ошибка сборки образа"
    exit 1
}
Success "Образ собран успешно"

# Запуск тестов
Write-Host ""
Log "Запуск тестов..."
Write-Host ""

# Unit тесты
Write-ColorOutput Blue "═══════════════════════════════════════════════════════"
Write-ColorOutput Blue "  Unit Tests"
Write-ColorOutput Blue "═══════════════════════════════════════════════════════"
docker run --rm `
    -v "${PWD}/test-results:/app/test-results" `
    -v "${PWD}/htmlcov:/app/htmlcov" `
    sysaudit:test `
    python run_tests.py --unit --coverage --html-coverage
if ($LASTEXITCODE -ne 0) {
    Error "Unit тесты провалены"
    exit 1
}
Success "Unit тесты пройдены"

# Integration тесты
Write-Host ""
Write-ColorOutput Blue "═══════════════════════════════════════════════════════"
Write-ColorOutput Blue "  Integration Tests"
Write-ColorOutput Blue "═══════════════════════════════════════════════════════"
docker run --rm `
    -v "${PWD}/test-results:/app/test-results" `
    sysaudit:test `
    python run_tests.py --integration
if ($LASTEXITCODE -ne 0) {
    Error "Integration тесты провалены"
    exit 1
}
Success "Integration тесты пройдены"

# Compliance тесты
Write-Host ""
Write-ColorOutput Blue "═══════════════════════════════════════════════════════"
Write-ColorOutput Blue "  Compliance Tests"
Write-ColorOutput Blue "═══════════════════════════════════════════════════════"
docker run --rm `
    -v "${PWD}/test-results:/app/test-results" `
    sysaudit:test `
    python run_tests.py --compliance
if ($LASTEXITCODE -ne 0) {
    Error "Compliance тесты провалены"
    exit 1
}
Success "Compliance тесты пройдены"

# E2E тесты
Write-Host ""
Write-ColorOutput Blue "═══════════════════════════════════════════════════════"
Write-ColorOutput Blue "  E2E Tests (Real User Scenarios)"
Write-ColorOutput Blue "═══════════════════════════════════════════════════════"
docker run --rm `
    --user root `
    -v "${PWD}/test-results:/app/test-results" `
    -e PYTHONUNBUFFERED=1 `
    sysaudit:test `
    python tests/e2e/test_real_user_scenarios.py
if ($LASTEXITCODE -ne 0) {
    Error "E2E тесты провалены"
    exit 1
}
Success "E2E тесты пройдены"

# Генерация итогового отчета
Write-Host ""
Log "Генерация итогового отчета..."

python -c @"
import json
import os
from datetime import datetime
from pathlib import Path

test_results_dir = Path('test-results')
report = {
    'timestamp': datetime.now().isoformat(),
    'project': 'sysaudit',
    'version': '0.1.0',
    'tests': {}
}

for json_file in test_results_dir.glob('*.json'):
    try:
        with open(json_file) as f:
            data = json.load(f)
            test_type = json_file.stem.replace('-report', '')
            report['tests'][test_type] = data
    except Exception as e:
        print(f'Error reading {json_file}: {e}')

total_passed = sum(t.get('passed', 0) for t in report['tests'].values() if isinstance(t, dict))
total_failed = sum(t.get('failed', 0) for t in report['tests'].values() if isinstance(t, dict))
total_tests = total_passed + total_failed

report['summary'] = {
    'total_tests': total_tests,
    'passed': total_passed,
    'failed': total_failed,
    'success_rate': f'{(total_passed / total_tests * 100):.1f}%' if total_tests > 0 else 'N/A'
}

with open('test-results/final-report.json', 'w') as f:
    json.dump(report, f, indent=2)

print('\n' + '='*60)
print('FINAL TEST REPORT')
print('='*60)
print(f'Project: {report[\"project\"]}')
print(f'Version: {report[\"version\"]}')
print(f'Timestamp: {report[\"timestamp\"]}')
print('\nSummary:')
print(f'  Total Tests: {report[\"summary\"][\"total_tests\"]}')
print(f'  Passed: {report[\"summary\"][\"passed\"]} ✓')
print(f'  Failed: {report[\"summary\"][\"failed\"]} ✗')
print(f'  Success Rate: {report[\"summary\"][\"success_rate\"]}')
print('\nTest Results by Type:')
for test_type, data in report['tests'].items():
    if isinstance(data, dict):
        print(f'\n  {test_type.upper()}:')
        print(f'    Passed: {data.get(\"passed\", \"N/A\")}')
        print(f'    Failed: {data.get(\"failed\", \"N/A\")}')
        if 'duration_seconds' in data:
            print(f'    Duration: {data[\"duration_seconds\"]:.2f}s')
print('='*60)
"@

Success "Отчет сгенерирован"

# Итоговое сообщение
Write-Host ""
Write-ColorOutput Green "╔════════════════════════════════════════════════════════╗"
Write-ColorOutput Green "║  Все тесты успешно пройдены!                          ║"
Write-ColorOutput Green "╚════════════════════════════════════════════════════════╝"
Write-Host ""
Write-Host "Результаты тестов: " -NoNewline
Write-ColorOutput Blue "test-results/"
Write-Host "Coverage отчет: " -NoNewline
Write-ColorOutput Blue "htmlcov/index.html"
Write-Host "Итоговый отчет: " -NoNewline
Write-ColorOutput Blue "test-results/final-report.json"
Write-Host ""
