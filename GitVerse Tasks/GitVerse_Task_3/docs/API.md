# GitProc API Reference

Справочник по программному API GitProc для интеграции в другие приложения.

## Содержание

- [Обзор](#обзор)
- [CLI API](#cli-api)
- [Python API](#python-api)
- [IPC Protocol](#ipc-protocol)
- [Примеры интеграции](#примеры-интеграции)

## Обзор

GitProc предоставляет несколько способов интеграции:

1. **CLI Interface** - командная строка для скриптов и автоматизации
2. **Python API** - прямое использование модулей Python
3. **IPC Protocol** - Unix socket для межпроцессного взаимодействия

## CLI API

### Формат команд

```bash
python3 -m gitproc.cli <command> [options] [arguments]
```

### Коды возврата

- `0` - успешное выполнение
- `1` - ошибка выполнения
- `2` - ошибка аргументов командной строки

### Команды

#### init

Инициализация нового репозитория сервисов.

```bash
python3 -m gitproc.cli init --repo <path>
```

**Аргументы:**
- `--repo` (обязательный) - путь для создания репозитория

**Возвращает:**
- Код 0 при успехе
- Код 1 если репозиторий уже существует или ошибка создания

**Пример:**
```bash
python3 -m gitproc.cli init --repo /etc/gitproc/services
echo $?  # 0 = успех
```

#### daemon

Запуск демона в фоновом режиме.

```bash
python3 -m gitproc.cli daemon [--watch-branch <branch>] [--config <path>]
```

**Аргументы:**
- `--watch-branch` (опционально) - ветка Git для мониторинга (по умолчанию: main)
- `--config` (опционально) - путь к конфигурационному файлу

**Возвращает:**
- Код 0 при успешном запуске
- Код 1 при ошибке (демон уже запущен, ошибка конфигурации и т.д.)

**Пример:**
```bash
python3 -m gitproc.cli daemon --watch-branch production &
DAEMON_PID=$!
```

#### start

Запуск сервиса.

```bash
python3 -m gitproc.cli start <service-name>
```

**Аргументы:**
- `service-name` (обязательный) - имя сервиса без расширения .service

**Возвращает:**
- Код 0 если сервис успешно запущен
- Код 1 при ошибке (сервис не найден, уже запущен, ошибка запуска)

**Вывод:**
```
Service started: web-server (PID: 12345)
```

**Пример:**
```bash
if python3 -m gitproc.cli start web-server; then
    echo "Service started successfully"
else
    echo "Failed to start service"
fi
```

#### stop

Остановка сервиса.

```bash
python3 -m gitproc.cli stop <service-name>
```

**Аргументы:**
- `service-name` (обязательный) - имя сервиса

**Возвращает:**
- Код 0 если сервис успешно остановлен
- Код 1 при ошибке (сервис не найден, не запущен)

**Вывод:**
```
Service stopped: web-server
```

#### restart

Перезапуск сервиса.

```bash
python3 -m gitproc.cli restart <service-name>
```

**Аргументы:**
- `service-name` (обязательный) - имя сервиса

**Возвращает:**
- Код 0 если сервис успешно перезапущен
- Код 1 при ошибке

**Вывод:**
```
Service restarted: web-server (PID: 12346)
```

#### status

Получение статуса сервиса.

```bash
python3 -m gitproc.cli status <service-name>
```

**Аргументы:**
- `service-name` (обязательный) - имя сервиса

**Возвращает:**
- Код 0 если сервис существует
- Код 1 если сервис не найден

**Вывод:**
```
Service: web-server
Status: running
PID: 12345
Started: 2024-10-25 14:30:15
Restarts: 2
Last Exit Code: 0
```

**Парсинг вывода:**
```bash
STATUS=$(python3 -m gitproc.cli status web-server)
if echo "$STATUS" | grep -q "Status: running"; then
    echo "Service is running"
fi
```

#### logs

Просмотр логов сервиса.

```bash
python3 -m gitproc.cli logs <service-name> [--follow] [--lines <n>]
```

**Аргументы:**
- `service-name` (обязательный) - имя сервиса
- `--follow`, `-f` (опционально) - следить за логами в реальном времени
- `--lines`, `-n` (опционально) - количество строк для отображения

**Возвращает:**
- Код 0 при успехе
- Код 1 если сервис не найден или нет логов

**Вывод:**
```
[2024-10-25 14:30:15] Starting server on port 8080
[2024-10-25 14:30:16] Server ready
```

**Пример:**
```bash
# Последние 50 строк
python3 -m gitproc.cli logs web-server --lines 50

# Следить за логами
python3 -m gitproc.cli logs web-server --follow
```

#### list

Список всех сервисов.

```bash
python3 -m gitproc.cli list
```

**Возвращает:**
- Код 0 всегда

**Вывод:**
```
Available services:
  web-server (running, PID: 12345)
  database (running, PID: 12346)
  worker (stopped)
  app (failed, exit code: 1)
```

**Парсинг:**
```bash
python3 -m gitproc.cli list | grep "running" | wc -l
# Количество запущенных сервисов
```

#### rollback

Откат конфигураций к предыдущему коммиту.

```bash
python3 -m gitproc.cli rollback <commit-hash>
```

**Аргументы:**
- `commit-hash` (обязательный) - хеш коммита Git

**Возвращает:**
- Код 0 при успешном откате
- Код 1 при ошибке (неверный хеш, ошибка Git)

**Пример:**
```bash
# Получить список коммитов
cd /etc/gitproc/services
git log --oneline

# Откатиться
python3 -m gitproc.cli rollback abc123
```

#### sync

Ручная синхронизация с Git.

```bash
python3 -m gitproc.cli sync
```

**Возвращает:**
- Код 0 при успешной синхронизации
- Код 1 при ошибке

**Вывод:**
```
Synced with Git repository
Reloaded 3 services
```

## Python API

### Импорт модулей

```python
from gitproc.cli import CLI
from gitproc.daemon import Daemon
from gitproc.parser import UnitFileParser
from gitproc.process_manager import ProcessManager
from gitproc.git_integration import GitIntegration
from gitproc.state_manager import StateManager
from gitproc.resource_controller import ResourceController
from gitproc.dependency_resolver import DependencyResolver
from gitproc.health_monitor import HealthMonitor
```

### UnitFileParser

Парсинг unit-файлов.

```python
from gitproc.parser import UnitFileParser, UnitFile

# Парсинг из строки
content = """
[Service]
ExecStart=/usr/bin/python3 server.py
Restart=always
User=nobody
"""

unit = UnitFileParser.parse("test.service", content)

# Доступ к полям
print(unit.name)          # "test"
print(unit.exec_start)    # "/usr/bin/python3 server.py"
print(unit.restart)       # "always"
print(unit.user)          # "nobody"

# Парсинг из файла
with open("service.service", "r") as f:
    content = f.read()
    unit = UnitFileParser.parse("service.service", content)
```

**UnitFile dataclass:**

```python
@dataclass
class UnitFile:
    name: str                          # Имя сервиса
    exec_start: str                    # Команда запуска
    restart: str = "no"                # Политика перезапуска
    user: Optional[str] = None         # Пользователь
    environment: Dict[str, str] = None # Переменные окружения
    memory_limit: Optional[int] = None # Лимит памяти (байты)
    cpu_quota: Optional[int] = None    # Лимит CPU (проценты)
    health_check_url: Optional[str] = None        # URL health check
    health_check_interval: int = 30               # Интервал проверки
    after: List[str] = None            # Зависимости
```

### ProcessManager

Управление процессами.

```python
from gitproc.process_manager import ProcessManager, ProcessInfo

manager = ProcessManager()

# Запуск процесса
unit = UnitFile(
    name="test",
    exec_start="/usr/bin/python3 server.py",
    user="nobody",
    environment={"PORT": "8080"}
)

proc_info = manager.start_process(unit, cgroup_path=None)

print(proc_info.pid)           # PID процесса
print(proc_info.start_time)    # Время запуска
print(proc_info.status)        # "running"

# Проверка статуса
is_running = manager.is_running(proc_info.pid)

# Остановка процесса
manager.stop_process(proc_info.pid, timeout=10)

# Получение логов
logs = manager.get_logs(unit.name, lines=100)
```

**ProcessInfo dataclass:**

```python
@dataclass
class ProcessInfo:
    pid: int                    # PID процесса
    start_time: datetime        # Время запуска
    status: str                 # "running", "stopped", "failed"
    exit_code: Optional[int]    # Код выхода (если завершён)
```

### GitIntegration

Работа с Git-репозиторием.

```python
from gitproc.git_integration import GitIntegration

git = GitIntegration("/etc/gitproc/services")

# Инициализация репозитория
git.init()

# Получение списка unit-файлов
unit_files = git.get_unit_files()
# ["web-server.service", "database.service"]

# Чтение unit-файла
content = git.read_unit_file("web-server.service")

# Получение изменённых файлов
changed = git.get_changed_files(since_commit="HEAD~1")
# ["web-server.service"]

# Откат к коммиту
git.rollback("abc123")

# Получение текущего коммита
commit_hash = git.get_current_commit()
```

### StateManager

Управление состоянием сервисов.

```python
from gitproc.state_manager import StateManager, ServiceState

manager = StateManager("/var/lib/gitproc/state.json")

# Регистрация сервиса
state = ServiceState(
    name="web-server",
    status="running",
    pid=12345,
    start_time=datetime.now(),
    restart_count=0
)
manager.register_service(state)

# Получение состояния
state = manager.get_service("web-server")
print(state.status)  # "running"
print(state.pid)     # 12345

# Обновление состояния
manager.update_status("web-server", "stopped", exit_code=0)

# Получение всех сервисов
all_services = manager.get_all_services()

# Сохранение состояния
manager.save_state()

# Загрузка состояния
manager.load_state()
```

**ServiceState dataclass:**

```python
@dataclass
class ServiceState:
    name: str                           # Имя сервиса
    status: str                         # "running", "stopped", "failed"
    pid: Optional[int] = None           # PID (если запущен)
    start_time: Optional[datetime] = None  # Время запуска
    restart_count: int = 0              # Количество перезапусков
    last_exit_code: Optional[int] = None   # Последний код выхода
```

### ResourceController

Управление ресурсами через cgroups.

```python
from gitproc.resource_controller import ResourceController

controller = ResourceController("/sys/fs/cgroup/gitproc")

# Создание cgroup
cgroup_path = controller.create_cgroup(
    service_name="web-server",
    memory_limit=512 * 1024 * 1024,  # 512 MB
    cpu_quota=100  # 100% одного ядра
)

# Добавление процесса в cgroup
controller.add_process_to_cgroup(cgroup_path, pid=12345)

# Получение использования ресурсов
memory_usage = controller.get_memory_usage(cgroup_path)
cpu_usage = controller.get_cpu_usage(cgroup_path)

# Удаление cgroup
controller.remove_cgroup(cgroup_path)
```

### DependencyResolver

Разрешение зависимостей между сервисами.

```python
from gitproc.dependency_resolver import DependencyResolver

resolver = DependencyResolver()

# Добавление сервисов
resolver.add_service("database", dependencies=[])
resolver.add_service("app", dependencies=["database"])
resolver.add_service("worker", dependencies=["app"])

# Получение порядка запуска
start_order = resolver.get_start_order(["worker"])
# ["database", "app", "worker"]

# Проверка циклических зависимостей
has_cycle = resolver.has_cycle()
# False

# Получение зависимостей сервиса
deps = resolver.get_dependencies("worker")
# ["app"]
```

### HealthMonitor

Мониторинг здоровья сервисов.

```python
from gitproc.health_monitor import HealthMonitor, HealthCheck

monitor = HealthMonitor()

# Добавление health check
check = HealthCheck(
    service_name="web-server",
    url="http://localhost:8080/health",
    interval=30,
    timeout=5
)
monitor.add_check(check)

# Запуск мониторинга
monitor.start()

# Проверка здоровья
is_healthy = monitor.is_healthy("web-server")

# Получение последней ошибки
last_error = monitor.get_last_error("web-server")

# Остановка мониторинга
monitor.stop()
```

### Daemon

Основной класс демона.

```python
from gitproc.daemon import Daemon

daemon = Daemon(
    repo_path="/etc/gitproc/services",
    branch="main",
    socket_path="/var/run/gitproc.sock"
)

# Запуск демона
daemon.start()

# Демон работает в фоновом режиме
# Обрабатывает команды через Unix socket

# Остановка демона
daemon.stop()
```

## IPC Protocol

Демон использует Unix domain socket для межпроцессного взаимодействия.

### Формат сообщений

**Request:**
```json
{
  "command": "start|stop|restart|status|logs|list|rollback|sync",
  "service": "service-name",
  "args": {
    "follow": true,
    "lines": 100,
    "commit": "abc123"
  }
}
```

**Response:**
```json
{
  "status": "success|error",
  "data": {
    "pid": 12345,
    "state": "running",
    "logs": "...",
    "services": [...]
  },
  "error": "error message if status=error"
}
```

### Пример использования

```python
import socket
import json

# Подключение к демону
sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
sock.connect("/var/run/gitproc.sock")

# Отправка команды
request = {
    "command": "start",
    "service": "web-server",
    "args": {}
}
sock.sendall(json.dumps(request).encode() + b'\n')

# Получение ответа
response = sock.recv(4096)
result = json.loads(response.decode())

if result["status"] == "success":
    print(f"Service started with PID: {result['data']['pid']}")
else:
    print(f"Error: {result['error']}")

sock.close()
```

### Команды IPC

#### start

```json
{
  "command": "start",
  "service": "web-server"
}
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "pid": 12345,
    "service": "web-server"
  }
}
```

#### stop

```json
{
  "command": "stop",
  "service": "web-server"
}
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "service": "web-server"
  }
}
```

#### status

```json
{
  "command": "status",
  "service": "web-server"
}
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "service": "web-server",
    "state": "running",
    "pid": 12345,
    "start_time": "2024-10-25T14:30:15",
    "restart_count": 2,
    "last_exit_code": 0
  }
}
```

#### logs

```json
{
  "command": "logs",
  "service": "web-server",
  "args": {
    "lines": 100,
    "follow": false
  }
}
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "logs": "[2024-10-25 14:30:15] Server started\n[2024-10-25 14:30:16] Ready\n"
  }
}
```

#### list

```json
{
  "command": "list"
}
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "services": [
      {
        "name": "web-server",
        "status": "running",
        "pid": 12345
      },
      {
        "name": "database",
        "status": "running",
        "pid": 12346
      }
    ]
  }
}
```

## Примеры интеграции

### Bash скрипт

```bash
#!/bin/bash
# deploy.sh - Скрипт деплоя сервиса

set -e

SERVICE_NAME="web-app"
REPO_PATH="/etc/gitproc/services"

echo "Deploying $SERVICE_NAME..."

# 1. Обновить конфигурацию в Git
cd "$REPO_PATH"
git pull origin main

# 2. Перезапустить сервис
if python3 -m gitproc.cli restart "$SERVICE_NAME"; then
    echo "Service restarted successfully"
else
    echo "Failed to restart service"
    exit 1
fi

# 3. Проверить статус
sleep 2
STATUS=$(python3 -m gitproc.cli status "$SERVICE_NAME")
if echo "$STATUS" | grep -q "Status: running"; then
    echo "Service is running"
else
    echo "Service failed to start"
    exit 1
fi

# 4. Показать логи
python3 -m gitproc.cli logs "$SERVICE_NAME" --lines 20

echo "Deployment completed"
```

### Python скрипт

```python
#!/usr/bin/env python3
# monitor.py - Мониторинг сервисов

import subprocess
import json
import time
from datetime import datetime

def get_service_status(service_name):
    """Получить статус сервиса"""
    result = subprocess.run(
        ["python3", "-m", "gitproc.cli", "status", service_name],
        capture_output=True,
        text=True
    )
    return result.stdout

def is_service_running(service_name):
    """Проверить запущен ли сервис"""
    status = get_service_status(service_name)
    return "Status: running" in status

def restart_service(service_name):
    """Перезапустить сервис"""
    result = subprocess.run(
        ["python3", "-m", "gitproc.cli", "restart", service_name],
        capture_output=True,
        text=True
    )
    return result.returncode == 0

def monitor_services(services, interval=60):
    """Мониторить список сервисов"""
    print(f"Starting monitoring at {datetime.now()}")
    
    while True:
        for service in services:
            if not is_service_running(service):
                print(f"[{datetime.now()}] Service {service} is down, restarting...")
                if restart_service(service):
                    print(f"[{datetime.now()}] Service {service} restarted")
                else:
                    print(f"[{datetime.now()}] Failed to restart {service}")
            else:
                print(f"[{datetime.now()}] Service {service} is healthy")
        
        time.sleep(interval)

if __name__ == "__main__":
    services = ["web-server", "database", "worker"]
    monitor_services(services, interval=60)
```

### Ansible playbook

```yaml
# deploy.yml - Ansible playbook для деплоя
---
- name: Deploy GitProc services
  hosts: servers
  become: yes
  
  vars:
    gitproc_repo: /etc/gitproc/services
    services:
      - web-server
      - database
      - worker
  
  tasks:
    - name: Update service configurations
      git:
        repo: https://github.com/example/services.git
        dest: "{{ gitproc_repo }}"
        version: main
    
    - name: Sync GitProc with Git
      command: python3 -m gitproc.cli sync
      register: sync_result
      changed_when: "'Reloaded' in sync_result.stdout"
    
    - name: Restart services
      command: python3 -m gitproc.cli restart {{ item }}
      loop: "{{ services }}"
      register: restart_result
      failed_when: restart_result.rc != 0
    
    - name: Wait for services to start
      pause:
        seconds: 5
    
    - name: Check service status
      command: python3 -m gitproc.cli status {{ item }}
      loop: "{{ services }}"
      register: status_result
      failed_when: "'running' not in status_result.stdout"
    
    - name: Display service logs
      command: python3 -m gitproc.cli logs {{ item }} --lines 20
      loop: "{{ services }}"
      register: logs_result
    
    - name: Show logs
      debug:
        msg: "{{ logs_result.results }}"
```

### Systemd integration

```ini
# /etc/systemd/system/gitproc.service
[Unit]
Description=GitProc Daemon
After=network.target

[Service]
Type=simple
User=root
ExecStart=/usr/bin/python3 -m gitproc.cli daemon --watch-branch main
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
# Управление через systemd
sudo systemctl enable gitproc
sudo systemctl start gitproc
sudo systemctl status gitproc
```

### Docker integration

```dockerfile
# Dockerfile для приложения с GitProc
FROM python:3.11-slim

# Установить GitProc
COPY gitproc/ /opt/gitproc/
COPY requirements.txt /opt/gitproc/
RUN pip install -r /opt/gitproc/requirements.txt

# Скопировать конфигурации сервисов
COPY services/ /etc/gitproc/services/

# Инициализировать Git репозиторий
RUN cd /etc/gitproc/services && \
    git init && \
    git add . && \
    git commit -m "Initial commit"

# Запустить демон
CMD ["python3", "-m", "gitproc.cli", "daemon"]
```

### Prometheus monitoring

```python
# prometheus_exporter.py - Экспорт метрик в Prometheus
from prometheus_client import start_http_server, Gauge
import subprocess
import time

# Метрики
service_status = Gauge('gitproc_service_status', 'Service status', ['service'])
service_restarts = Gauge('gitproc_service_restarts', 'Restart count', ['service'])

def collect_metrics():
    """Собрать метрики из GitProc"""
    # Получить список сервисов
    result = subprocess.run(
        ["python3", "-m", "gitproc.cli", "list"],
        capture_output=True,
        text=True
    )
    
    for line in result.stdout.split('\n'):
        if '(' in line:
            # Парсинг: "web-server (running, PID: 12345)"
            parts = line.strip().split('(')
            service = parts[0].strip()
            status = parts[1].split(',')[0].strip()
            
            # Обновить метрики
            service_status.labels(service=service).set(
                1 if status == "running" else 0
            )

if __name__ == "__main__":
    # Запустить HTTP сервер для Prometheus
    start_http_server(9090)
    
    # Собирать метрики каждые 15 секунд
    while True:
        collect_metrics()
        time.sleep(15)
```

## Обработка ошибок

### CLI ошибки

```bash
# Проверка кода возврата
if ! python3 -m gitproc.cli start web-server; then
    echo "Failed to start service"
    # Проверить логи
    python3 -m gitproc.cli logs web-server --lines 50
    exit 1
fi
```

### Python ошибки

```python
from gitproc.parser import UnitFileParser, ParseError

try:
    unit = UnitFileParser.parse("test.service", content)
except ParseError as e:
    print(f"Failed to parse unit file: {e}")
except FileNotFoundError as e:
    print(f"Unit file not found: {e}")
except Exception as e:
    print(f"Unexpected error: {e}")
```

### IPC ошибки

```python
import socket
import json

try:
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.connect("/var/run/gitproc.sock")
    
    request = {"command": "start", "service": "web-server"}
    sock.sendall(json.dumps(request).encode() + b'\n')
    
    response = json.loads(sock.recv(4096).decode())
    
    if response["status"] == "error":
        print(f"Error: {response['error']}")
    
except socket.error as e:
    print(f"Cannot connect to daemon: {e}")
except json.JSONDecodeError as e:
    print(f"Invalid response from daemon: {e}")
finally:
    sock.close()
```

## Дополнительные ресурсы

- [Usage Guide](USAGE.md) - Руководство пользователя
- [Architecture](ARCHITECTURE.md) - Архитектура системы
- [Testing](TESTING.md) - Тестирование
- [Examples](../examples/) - Примеры unit-файлов
