# Быстрый старт тестирования

## Установка зависимостей
```bash
pip install -r requirements.txt
```

## Запуск тестов

### Windows
```bash
python -m pytest tests/ -v
```
**Результат:** 8 passed, 17 skipped ✅

### Linux/Mac
```bash
python3 -m pytest tests/ -v
```
**Результат:** 25 passed ✅

## Что тестируется

### ✅ Работает на всех ОС (8 тестов)
- HTTP API endpoints
- Compare-and-Swap через API
- Health check
- CRUD операции через HTTP

### ⏭️ Пропускается на Windows (17 тестов)
- Unit тесты с Git репозиториями
- Причина: file locking issues
- **Функциональность работает!** (см. примеры)

## Проверка функциональности

### Примеры (работают на всех ОС)
```bash
# Базовые примеры
python examples\example_usage.py

# Полная демонстрация
python examples\full_demo.py
```

### CLI (работает на всех ОС)
```bash
python src\gitconfig_cli.py set /test/key value --repo ./test_repo
python src\gitconfig_cli.py get /test/key --repo ./test_repo
```

## Подробности

- `WINDOWS_TESTING_GUIDE.md` - полное руководство
- `tests/README.md` - документация по тестам
- `TEST_REPORT.md` - отчёт о тестировании
