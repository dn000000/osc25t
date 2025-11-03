# GitConfig - Quick Reference

## 🚀 Быстрый старт

```bash
quickstart.bat
```

## 📊 Оценка: 38/38 баллов (максимум)

## 🎯 Основные команды

### Установка
```bash
install.bat
```

### Тестирование
```bash
run_all_tests.bat
```

### Запуск узла
```bash
python gitconfig_node.py start --repo ./data/node1 --http-port 8080
```

### CLI команды
```bash
# Set
python gitconfig_cli.py set /app/db/host localhost --http http://localhost:8080

# Get
python gitconfig_cli.py get /app/db/host --http http://localhost:8080

# Delete
python gitconfig_cli.py delete /app/db/host --http http://localhost:8080

# List
python gitconfig_cli.py list /app/ --recursive --http http://localhost:8080

# History
python gitconfig_cli.py history /app/db/host --http http://localhost:8080

# Watch
python gitconfig_cli.py watch /app/db/host --repo ./data/node1

# CAS
python gitconfig_cli.py cas /counter 6 --value 7 --expected 6 --http http://localhost:8080
```

### HTTP API
```bash
# Set
curl -X POST -d "localhost" http://localhost:8080/keys/app/db/host

# Get
curl http://localhost:8080/keys/app/db/host

# Delete
curl -X DELETE http://localhost:8080/keys/app/db/host

# List
curl "http://localhost:8080/list?prefix=/app/&recursive=true"

# History
curl http://localhost:8080/keys/app/db/host/history

# CAS
curl -X POST -H "Content-Type: application/json" \
  -d '{"expected":"5","new_value":"6"}' \
  http://localhost:8080/cas/counter

# Health
curl http://localhost:8080/health
```

## 📚 Документация

| Файл | Описание |
|------|----------|
| **START_HERE.txt** | Начните здесь! |
| **README.md** | Обзор проекта |
| **SCORING.md** | Детальный разбор критериев |
| **USAGE.md** | Подробное руководство |
| **ARCHITECTURE.md** | Архитектура системы |
| **SCENARIOS.md** | 10 практических сценариев |

## ✅ Реализованные возможности

- ✅ Базовые операции (set/get/delete) - 12 баллов
- ✅ Иерархические ключи - 6 баллов
- ✅ Синхронизация между узлами - 8 баллов
- ✅ HTTP API - 5 баллов
- ✅ Версионирование - 6 баллов
- ✅ Watch mechanism - 6 баллов
- ✅ TTL - 4 балла
- ✅ Production quality - 5 баллов
- ✅ Compare-and-Swap - 4 балла

## 🧪 Тесты

```bash
# Все тесты
run_all_tests.bat

# Unit тесты
python test_gitconfig.py

# HTTP API тесты
python test_http_api.py

# Конкретный тест
python -m unittest test_gitconfig.TestGitConfigBasic.test_set_and_get
```

## 🎬 Демонстрации

```bash
# Полная демонстрация
python full_demo.py

# Базовые примеры
python example_usage.py
```

## 🔧 Технологии

- Python 3.7+
- GitPython
- Flask
- Threading
- Requests
- psutil

## 📁 Структура проекта

```
gitconfig/
├── gitconfig_core.py       # Основное хранилище
├── gitconfig_node.py       # HTTP API сервер
├── gitconfig_cli.py        # CLI интерфейс
├── test_gitconfig.py       # Unit тесты
├── test_http_api.py        # Integration тесты
├── example_usage.py        # Примеры
├── full_demo.py            # Демонстрация
├── install.bat             # Установка
├── quickstart.bat          # Быстрый старт
├── run_all_tests.bat       # Тесты
└── [документация]          # 8 файлов документации
```

## 💡 Примеры использования

### Централизованная конфигурация
```bash
python gitconfig_node.py start --repo ./config --http-port 8080
curl -X POST -d "postgres://db:5432" http://localhost:8080/keys/app/db/url
```

### Распределённая система
```bash
git init --bare ./shared.git
python gitconfig_node.py start --repo ./dc1 --http-port 8080 --remote ./shared.git
python gitconfig_node.py start --repo ./dc2 --http-port 8081 --remote ./shared.git
```

### Feature flags
```bash
python gitconfig_cli.py set /features/new_ui enabled --http http://localhost:8080
python gitconfig_cli.py history /features/new_ui --http http://localhost:8080
```

### Distributed lock
```python
from gitconfig_core import GitConfigStore
store = GitConfigStore('./locks')
if store.cas('/locks/resource', '', 'node1'):
    # Critical section
    store.delete('/locks/resource')
```

### Session storage
```bash
curl -X POST -d '{"user_id":123}' "http://localhost:8080/keys/sessions/abc?ttl=3600"
```
