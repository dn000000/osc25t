# Руководство по использованию GitConfig

## Быстрый старт

### 1. Установка зависимостей

```bash
install.bat | ./install.sh
```

### 2. Запуск примеров

```bash
python example_usage.py
```

### 3. Запуск тестов

```bash
python test_gitconfig.py
python test_http_api.py
```

## Использование CLI

### Локальный режим (прямой доступ к репозиторию)

```bash
# Установить значение
python gitconfig_cli.py set /app/db/host localhost --repo ./data/node1

# Получить значение
python gitconfig_cli.py get /app/db/host --repo ./data/node1

# Удалить ключ
python gitconfig_cli.py delete /app/db/host --repo ./data/node1

# Список ключей
python gitconfig_cli.py list /app/ --repo ./data/node1

# Рекурсивный список
python gitconfig_cli.py list /app/ --recursive --repo ./data/node1

# История изменений
python gitconfig_cli.py history /app/db/host --repo ./data/node1

# Получить старую версию
python gitconfig_cli.py get /app/db/host --commit abc123 --repo ./data/node1

# Установить с TTL (10 секунд)
python gitconfig_cli.py set /session/token xyz --ttl 10 --repo ./data/node1

# Watch (ждать изменения)
python gitconfig_cli.py watch /app/db/host --repo ./data/node1

# Compare-and-Swap
python gitconfig_cli.py cas /counter 5 --value 6 --expected 5 --repo ./data/node1
```

### Удалённый режим (через HTTP API)

```bash
# Установить значение
python gitconfig_cli.py set /app/db/host localhost --http http://localhost:8080

# Получить значение
python gitconfig_cli.py get /app/db/host --http http://localhost:8080

# Удалить ключ
python gitconfig_cli.py delete /app/db/host --http http://localhost:8080

# Список ключей
python gitconfig_cli.py list /app/ --http http://localhost:8080

# История
python gitconfig_cli.py history /app/db/host --http http://localhost:8080

# CAS
python gitconfig_cli.py cas /counter 6 --value 7 --expected 6 --http http://localhost:8080
```

## Запуск HTTP узлов

### Одиночный узел

```bash
python gitconfig_node.py start --repo ./data/node1 --http-port 8080
```

### Два узла с синхронизацией

#### Вариант 1: Через bare repository

```bash
# Создать bare repository
git init --bare ./data/bare.git

# Запустить узел 1
python gitconfig_node.py start --repo ./data/node1 --http-port 8080 --remote ./data/bare.git

# Запустить узел 2
python gitconfig_node.py start --repo ./data/node2 --http-port 8081 --remote ./data/bare.git
```

#### Вариант 2: Прямая синхронизация

```bash
# Запустить узел 1
python gitconfig_node.py start --repo ./data/node1 --http-port 8080

# Запустить узел 2 (синхронизируется с узлом 1)
python gitconfig_node.py start --repo ./data/node2 --http-port 8081 --remote ./data/node1
```

### Настройка интервала синхронизации

```bash
python gitconfig_node.py start --repo ./data/node1 --http-port 8080 --sync-interval 10
```

## HTTP API

### Установить ключ

```bash
curl -X POST -d "localhost" http://localhost:8080/keys/app/db/host
```

С TTL:
```bash
curl -X POST -d "token123" "http://localhost:8080/keys/session/token?ttl=60"
```

### Получить ключ

```bash
curl http://localhost:8080/keys/app/db/host
```

Получить старую версию:
```bash
curl "http://localhost:8080/keys/app/db/host?commit=abc123"
```

### Удалить ключ

```bash
curl -X DELETE http://localhost:8080/keys/app/db/host
```

### Список ключей

```bash
curl "http://localhost:8080/list?prefix=/app/"
```

Рекурсивно:
```bash
curl "http://localhost:8080/list?prefix=/app/&recursive=true"
```

### История изменений

```bash
curl http://localhost:8080/keys/app/db/host/history
```

### Compare-and-Swap

```bash
curl -X POST -H "Content-Type: application/json" \
  -d '{"expected":"5","new_value":"6"}' \
  http://localhost:8080/cas/counter
```

### Health check

```bash
curl http://localhost:8080/health
```

## Программное использование (Python)

```python
from gitconfig_core import GitConfigStore

# Создать хранилище
store = GitConfigStore('./data/myapp')

# Установить значение
store.set('/app/db/host', 'localhost')

# Получить значение
value = store.get('/app/db/host')
print(value)  # localhost

# Установить с TTL
store.set('/session/token', 'abc123', ttl=60)

# Удалить
store.delete('/app/db/host')

# Список ключей
keys = store.list_keys('/app/', recursive=True)
for key in keys:
    print(key)

# История
history = store.history('/app/db/host')
for entry in history:
    print(f"{entry['commit']} - {entry['date']}")

# Watch (блокирующий вызов)
import threading

def watcher():
    if store.watch('/app/db/host', timeout=30):
        print("Key changed!")

thread = threading.Thread(target=watcher)
thread.start()

# В другом потоке изменить ключ
store.set('/app/db/host', 'newhost')

# Compare-and-Swap
success = store.cas('/counter', '5', '6')
if success:
    print("CAS succeeded")

# Синхронизация
store.add_remote('origin', './data/bare.git')
store.push('origin')
store.pull('origin')

# Автоматическая синхронизация
store.start_sync('origin')  # Каждые 30 секунд

# Очистка TTL
store.start_ttl_cleanup()

# Остановить фоновые задачи
store.stop()
```

## Сценарии использования

### Сценарий 1: Централизованная конфигурация

```bash
# Сервер конфигураций
python gitconfig_node.py start --repo ./config/central --http-port 8080

# Приложение 1 читает конфигурацию
curl http://localhost:8080/keys/app1/config

# Приложение 2 читает конфигурацию
curl http://localhost:8080/keys/app2/config
```

### Сценарий 2: Распределённая система

```bash
# Bare repository
git init --bare ./config/shared.git

# Узел в датацентре 1
python gitconfig_node.py start --repo ./dc1/config --http-port 8080 --remote ./config/shared.git

# Узел в датацентре 2
python gitconfig_node.py start --repo ./dc2/config --http-port 8081 --remote ./config/shared.git

# Изменения автоматически синхронизируются между узлами
```

### Сценарий 3: Версионирование конфигурации

```bash
# Установить конфигурацию v1
python gitconfig_cli.py set /app/config "version=1.0" --repo ./data/app

# Установить конфигурацию v2
python gitconfig_cli.py set /app/config "version=2.0" --repo ./data/app

# Откатиться к v1
python gitconfig_cli.py history /app/config --repo ./data/app
# Получить commit hash первой версии
python gitconfig_cli.py get /app/config --commit <hash> --repo ./data/app
```

### Сценарий 4: Distributed Lock через CAS

```python
from gitconfig_core import GitConfigStore
import time

store = GitConfigStore('./data/locks')

# Попытка получить lock
lock_acquired = store.cas('/locks/resource1', '', 'node1')

if lock_acquired:
    print("Lock acquired!")
    # Выполнить критическую секцию
    time.sleep(5)
    # Освободить lock
    store.delete('/locks/resource1')
else:
    print("Lock already held by another node")
```

## Graceful Shutdown

HTTP узлы корректно обрабатывают SIGTERM и SIGINT:

```bash
# Запустить узел
python gitconfig_node.py start --repo ./data/node1 --http-port 8080

# В другом терминале отправить SIGTERM
# Windows: Ctrl+C в терминале с узлом
# Linux: kill -TERM <pid>
```

Узел:
1. Остановит фоновые задачи синхронизации и TTL
2. Сохранит текущее состояние
3. Завершится за < 5 секунд

## Логирование

Все узлы используют структурированное JSON логирование:

```json
{"time":"2025-10-25T10:30:45","level":"INFO","message":"Starting GitConfig node on port 8080"}
{"time":"2025-10-25T10:30:50","level":"INFO","message":"SET /app/db/host (ttl=None)"}
{"time":"2025-10-25T10:30:55","level":"INFO","message":"GET /app/db/host"}
{"time":"2025-10-25T10:31:00","level":"WARNING","message":"Key not found: /nonexistent"}
```

## Troubleshooting

### Проблема: Конфликты при синхронизации

Система автоматически разрешает конфликты используя last-write-wins стратегию. Проверьте логи для деталей.

### Проблема: TTL не работает

Убедитесь что вызван `store.start_ttl_cleanup()` или узел запущен через HTTP API (автоматически запускает cleanup).

### Проблема: Watch не срабатывает

Watch работает только в рамках одного процесса. Для распределённого watch используйте polling через HTTP API.

### Проблема: Медленная синхронизация

Уменьшите `--sync-interval` при запуске узла (по умолчанию 30 секунд).
