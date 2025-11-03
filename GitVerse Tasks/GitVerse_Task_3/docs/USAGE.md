# GitProc Usage Guide

Полное руководство по использованию GitProc - менеджера процессов с Git-интеграцией.

## Содержание

- [Быстрый старт](#быстрый-старт)
- [Установка и настройка](#установка-и-настройка)
- [Управление сервисами](#управление-сервисами)
- [Формат unit-файлов](#формат-unit-файлов)
- [Продвинутые возможности](#продвинутые-возможности)
- [Примеры использования](#примеры-использования)
- [Лучшие практики](#лучшие-практики)

## Быстрый старт

### 1. Установка

**Linux/Unix:**
```bash
git clone <repository-url>
cd gitproc
chmod +x setup.sh
./setup.sh
```

**Windows:**
```cmd
git clone <repository-url>
cd gitproc
setup.bat
```

### 2. Инициализация репозитория сервисов

```bash
# Создать репозиторий для хранения конфигураций сервисов
python3 -m gitproc.cli init --repo /etc/gitproc/services
```

Эта команда создаст:
- Директорию `/etc/gitproc/services`
- Git-репозиторий внутри неё
- Начальный коммит

### 3. Создание первого сервиса

Создайте файл `/etc/gitproc/services/web-server.service`:

```ini
[Service]
ExecStart=/usr/bin/python3 -m http.server 8080
Restart=always
User=nobody
Environment=PORT=8080
```

Закоммитьте его:

```bash
cd /etc/gitproc/services
git add web-server.service
git commit -m "Add web server service"
```

### 4. Запуск демона

```bash
# Запустить демон в фоновом режиме
python3 -m gitproc.cli daemon --watch-branch main
```

Демон будет:
- Мониторить Git-репозиторий на изменения
- Управлять жизненным циклом сервисов
- Автоматически применять изменения конфигураций
- Перезапускать упавшие сервисы (если настроено)

### 5. Управление сервисом

```bash
# Запустить сервис
python3 -m gitproc.cli start web-server

# Проверить статус
python3 -m gitproc.cli status web-server

# Просмотреть логи
python3 -m gitproc.cli logs web-server

# Остановить сервис
python3 -m gitproc.cli stop web-server
```

## Установка и настройка

### Системные требования

- **Python**: 3.8 или выше
- **Git**: 2.0 или выше
- **ОС**: Linux (полная поддержка), macOS (частичная), Windows (ограниченная)
- **Права**: root для namespace и cgroups операций

### Зависимости Python

```bash
# Основные зависимости
GitPython>=3.1.40      # Git интеграция
watchdog>=3.0.0        # Мониторинг файловой системы
requests>=2.31.0       # HTTP health checks

# Тестовые зависимости
pytest>=7.4.0
pytest-timeout>=2.1.0
pytest-cov>=4.1.0
```

### Конфигурационный файл

GitProc использует конфигурационный файл `~/.gitproc/config.json`:

```json
{
  "repo_path": "/etc/gitproc/services",
  "branch": "main",
  "socket_path": "/var/run/gitproc.sock",
  "state_file": "/var/lib/gitproc/state.json",
  "log_dir": "/var/log/gitproc",
  "cgroup_root": "/sys/fs/cgroup/gitproc"
}
```

**Параметры:**

- `repo_path` - путь к Git-репозиторию с unit-файлами
- `branch` - ветка Git для мониторинга
- `socket_path` - путь к Unix-сокету для IPC
- `state_file` - файл для сохранения состояния сервисов
- `log_dir` - директория для логов сервисов
- `cgroup_root` - корневая директория для cgroups

### Структура директорий

После установки и инициализации:

```
/etc/gitproc/
└── services/              # Git-репозиторий
    ├── .git/             # Git метаданные
    ├── web-server.service
    ├── database.service
    └── app.service

/var/lib/gitproc/
└── state.json            # Состояние сервисов

/var/log/gitproc/
├── daemon.log            # Логи демона
├── web-server.log        # Логи сервисов
├── database.log
└── app.log

/var/run/
└── gitproc.sock          # Unix-сокет для IPC

/sys/fs/cgroup/gitproc/   # Cgroups (Linux)
├── web-server/
├── database/
└── app/
```

## Управление сервисами

### Команды CLI

#### init - Инициализация репозитория

```bash
python3 -m gitproc.cli init --repo <path>
```

Создаёт новый Git-репозиторий для управления сервисами.

**Опции:**
- `--repo` - путь для создания репозитория (обязательно)

**Пример:**
```bash
python3 -m gitproc.cli init --repo /etc/gitproc/services
```

#### daemon - Запуск демона

```bash
python3 -m gitproc.cli daemon [--watch-branch <branch>]
```

Запускает фоновый процесс демона.

**Опции:**
- `--watch-branch` - ветка Git для мониторинга (по умолчанию: main)

**Пример:**
```bash
# Запустить демон для ветки main
python3 -m gitproc.cli daemon

# Запустить демон для ветки production
python3 -m gitproc.cli daemon --watch-branch production
```

**Что делает демон:**
- Мониторит изменения в Git-репозитории
- Автоматически применяет изменения конфигураций
- Перезапускает сервисы при изменении их unit-файлов
- Выполняет health checks
- Перезапускает упавшие сервисы (если настроено)

#### start - Запуск сервиса

```bash
python3 -m gitproc.cli start <service-name>
```

Запускает указанный сервис.

**Пример:**
```bash
python3 -m gitproc.cli start web-server
```

**Что происходит:**
1. Парсинг unit-файла
2. Разрешение зависимостей (After)
3. Создание cgroup (если настроены лимиты)
4. Создание PID namespace (Linux)
5. Понижение привилегий (если указан User)
6. Запуск процесса
7. Сохранение состояния

#### stop - Остановка сервиса

```bash
python3 -m gitproc.cli stop <service-name>
```

Останавливает запущенный сервис.

**Пример:**
```bash
python3 -m gitproc.cli stop web-server
```

**Процесс остановки:**
1. Отправка SIGTERM процессу
2. Ожидание 10 секунд
3. Отправка SIGKILL если процесс не завершился
4. Очистка cgroup
5. Обновление состояния

#### restart - Перезапуск сервиса

```bash
python3 -m gitproc.cli restart <service-name>
```

Перезапускает сервис (stop + start).

**Пример:**
```bash
python3 -m gitproc.cli restart web-server
```

#### status - Статус сервиса

```bash
python3 -m gitproc.cli status <service-name>
```

Показывает текущий статус сервиса.

**Пример:**
```bash
python3 -m gitproc.cli status web-server
```

**Вывод включает:**
- Имя сервиса
- Текущий статус (running/stopped/failed)
- PID процесса (если запущен)
- Время запуска
- Количество перезапусков
- Код последнего выхода

**Пример вывода:**
```
Service: web-server
Status: running
PID: 12345
Started: 2024-10-25 14:30:15
Restarts: 2
Last Exit Code: 0
```

#### logs - Просмотр логов

```bash
python3 -m gitproc.cli logs <service-name> [--follow] [--lines <n>]
```

Показывает логи сервиса (stdout/stderr).

**Опции:**
- `--follow`, `-f` - следить за логами в реальном времени
- `--lines`, `-n` - количество строк для отображения

**Примеры:**
```bash
# Показать все логи
python3 -m gitproc.cli logs web-server

# Показать последние 50 строк
python3 -m gitproc.cli logs web-server --lines 50

# Следить за логами в реальном времени
python3 -m gitproc.cli logs web-server --follow
```

#### list - Список сервисов

```bash
python3 -m gitproc.cli list
```

Показывает все доступные сервисы.

**Пример вывода:**
```
Available services:
  web-server (running, PID: 12345)
  database (running, PID: 12346)
  app (stopped)
  worker (failed, exit code: 1)
```

#### rollback - Откат конфигурации

```bash
python3 -m gitproc.cli rollback <commit-hash>
```

Откатывает конфигурации сервисов к предыдущему коммиту.

**Пример:**
```bash
# Посмотреть историю коммитов
cd /etc/gitproc/services
git log --oneline

# Откатиться к предыдущему коммиту
python3 -m gitproc.cli rollback abc123
```

**Что происходит:**
1. Git checkout указанного коммита
2. Перезагрузка всех изменённых unit-файлов
3. Перезапуск затронутых сервисов

#### sync - Синхронизация с Git

```bash
python3 -m gitproc.cli sync
```

Вручную запускает синхронизацию с Git-репозиторием.

**Пример:**
```bash
python3 -m gitproc.cli sync
```

Полезно когда:
- Нужно немедленно применить изменения
- Демон не обнаружил изменения автоматически
- После ручного изменения репозитория

## Формат unit-файлов

Unit-файлы используют INI-формат, похожий на systemd. Файлы должны иметь расширение `.service` и содержать секцию `[Service]`.

### Обязательные директивы

#### ExecStart

Команда для выполнения (обязательная).

```ini
ExecStart=/usr/bin/python3 /app/server.py
```

**Особенности:**
- Должен быть полный путь к исполняемому файлу
- Поддерживаются аргументы командной строки
- Переменные окружения подставляются автоматически

### Опциональные директивы

#### Restart

Политика перезапуска при завершении процесса.

```ini
Restart=always
```

**Значения:**
- `always` - всегда перезапускать при выходе
- `on-failure` - перезапускать только при ненулевом коде выхода
- `no` - никогда не перезапускать (по умолчанию)

#### User

Пользователь для запуска сервиса.

```ini
User=nobody
```

**Особенности:**
- Демон должен быть запущен с правами root
- Пользователь должен существовать в системе
- Повышает безопасность, запуская сервис без root-прав

#### Environment

Переменные окружения (можно указывать несколько раз).

```ini
Environment=PORT=8080
Environment=DEBUG=true
Environment=DATABASE_URL=postgresql://localhost/mydb
```

**Особенности:**
- Каждая переменная на отдельной строке
- Формат: `KEY=VALUE`
- Доступны в процессе сервиса

#### MemoryLimit

Максимальное использование памяти.

```ini
MemoryLimit=100M
MemoryLimit=1G
MemoryLimit=512M
```

**Единицы измерения:**
- `K` - килобайты
- `M` - мегабайты
- `G` - гигабайты

**Требования:**
- Linux с cgroups v2
- Демон запущен с правами root

#### CPUQuota

Лимит использования CPU в процентах.

```ini
CPUQuota=50%
CPUQuota=150%
```

**Значения:**
- `50%` - половина одного ядра
- `100%` - одно полное ядро
- `200%` - два полных ядра

**Требования:**
- Linux с cgroups v2
- Демон запущен с правами root

#### HealthCheckURL

HTTP endpoint для проверки здоровья сервиса.

```ini
HealthCheckURL=http://localhost:8080/health
```

**Особенности:**
- Демон отправляет GET-запросы
- HTTP 200 = здоров
- Другие коды или timeout = нездоров
- При неудаче сервис перезапускается

#### HealthCheckInterval

Интервал проверки здоровья в секундах.

```ini
HealthCheckInterval=60
```

**По умолчанию:** 30 секунд

**Рекомендации:**
- Меньший интервал = быстрее обнаружение проблем
- Больший интервал = меньше нагрузки

#### After

Зависимости сервиса (запускать после указанных).

```ini
After=database.service
After=network.service
```

**Особенности:**
- Можно указывать несколько зависимостей
- GitProc автоматически определяет порядок запуска
- Обнаруживает циклические зависимости

### Полный пример unit-файла

```ini
[Service]
# Веб-приложение с полной конфигурацией
ExecStart=/usr/bin/python3 /opt/myapp/app.py

# Автоматический перезапуск
Restart=always

# Запуск от имени пользователя приложения
User=appuser

# Переменные окружения
Environment=FLASK_APP=app.py
Environment=FLASK_ENV=production
Environment=PORT=5000
Environment=DATABASE_URL=postgresql://localhost/myapp
Environment=REDIS_URL=redis://localhost:6379

# Лимиты ресурсов
MemoryLimit=512M
CPUQuota=100%

# Health check
HealthCheckURL=http://localhost:5000/health
HealthCheckInterval=30

# Зависимости
After=database.service
After=redis.service
```

## Продвинутые возможности

### Автоматическая синхронизация с Git

Демон автоматически обнаруживает изменения в Git-репозитории:

```bash
# В репозитории сервисов
cd /etc/gitproc/services

# Изменить конфигурацию
vim web-server.service

# Закоммитить
git add web-server.service
git commit -m "Update web server config"

# Демон автоматически:
# 1. Обнаружит изменение (в течение 10-30 секунд)
# 2. Перезагрузит конфигурацию
# 3. Перезапустит сервис
```

### Управление зависимостями

GitProc автоматически разрешает зависимости между сервисами:

```ini
# database.service
[Service]
ExecStart=/usr/bin/postgres -D /var/lib/postgresql/data
Restart=always

# app.service
[Service]
ExecStart=/usr/bin/python3 /opt/app/server.py
Restart=always
After=database.service  # Запустится после database

# worker.service
[Service]
ExecStart=/usr/bin/python3 /opt/app/worker.py
Restart=always
After=app.service  # Запустится после app
```

При запуске `python3 -m gitproc.cli start worker`, GitProc автоматически:
1. Запустит `database.service`
2. Дождётся его запуска
3. Запустит `app.service`
4. Дождётся его запуска
5. Запустит `worker.service`

### Health Checks

Автоматический мониторинг здоровья сервисов:

```ini
[Service]
ExecStart=/usr/bin/python3 /opt/app/server.py
Restart=always
HealthCheckURL=http://localhost:5000/health
HealthCheckInterval=30
```

**Требования к health endpoint:**

```python
# Flask пример
@app.route('/health')
def health():
    try:
        # Проверить подключение к БД
        db.execute('SELECT 1')
        
        # Проверить другие зависимости
        redis.ping()
        
        return 'OK', 200
    except Exception as e:
        return f'Unhealthy: {e}', 503
```

### Ограничение ресурсов

Контроль использования CPU и памяти:

```ini
[Service]
ExecStart=/usr/bin/python3 /opt/app/server.py
MemoryLimit=256M  # Максимум 256 МБ памяти
CPUQuota=50%      # Максимум 50% одного ядра
```

**Что происходит при превышении:**
- **Память**: процесс убивается OOM killer
- **CPU**: процесс throttling (замедляется)

### Откат конфигураций

Использование Git для отката к предыдущим версиям:

```bash
# Посмотреть историю
cd /etc/gitproc/services
git log --oneline

# Вывод:
# abc123 Update app config
# def456 Add health check
# ghi789 Initial config

# Откатиться к предыдущей версии
python3 -m gitproc.cli rollback def456

# Все сервисы автоматически перезагрузятся
# с конфигурацией из коммита def456
```

### Изоляция процессов

На Linux GitProc использует PID namespaces для изоляции:

```bash
# Внутри сервиса процесс видит только себя
ps aux
# PID 1: /usr/bin/python3 /opt/app/server.py

# Снаружи (в хост-системе)
ps aux | grep python
# PID 12345: /usr/bin/python3 /opt/app/server.py
```

**Преимущества:**
- Сервис не видит другие процессы системы
- Повышенная безопасность
- Изоляция от других сервисов

## Примеры использования

### Простой веб-сервер

```ini
# simple-web.service
[Service]
ExecStart=/usr/bin/python3 -m http.server 8080
Restart=always
User=nobody
Environment=PORT=8080
```

```bash
python3 -m gitproc.cli start simple-web
curl http://localhost:8080
```

### Flask приложение с БД

```ini
# database.service
[Service]
ExecStart=/usr/bin/postgres -D /var/lib/postgresql/data
Restart=always
User=postgres

# app.service
[Service]
ExecStart=/usr/bin/python3 /opt/myapp/app.py
Restart=always
User=appuser
Environment=DATABASE_URL=postgresql://localhost/myapp
Environment=FLASK_ENV=production
MemoryLimit=512M
CPUQuota=100%
HealthCheckURL=http://localhost:5000/health
HealthCheckInterval=30
After=database.service
```

```bash
# Запустить оба сервиса (database запустится автоматически)
python3 -m gitproc.cli start app
```

### Микросервисная архитектура

```ini
# redis.service
[Service]
ExecStart=/usr/bin/redis-server
Restart=always

# api.service
[Service]
ExecStart=/usr/bin/python3 /opt/api/server.py
Restart=always
Environment=PORT=8000
HealthCheckURL=http://localhost:8000/health
After=redis.service

# worker.service
[Service]
ExecStart=/usr/bin/python3 /opt/worker/worker.py
Restart=always
After=redis.service

# frontend.service
[Service]
ExecStart=/usr/bin/node /opt/frontend/server.js
Restart=always
Environment=API_URL=http://localhost:8000
After=api.service
```

```bash
# Запустить всю систему
python3 -m gitproc.cli start frontend
# Автоматически запустятся: redis → api → frontend
```

### Периодические задачи

```ini
# backup.service
[Service]
ExecStart=/usr/bin/python3 /opt/scripts/backup.py
Restart=on-failure
User=backup
Environment=BACKUP_DIR=/var/backups
Environment=RETENTION_DAYS=7
```

```bash
# Запустить backup вручную
python3 -m gitproc.cli start backup

# Посмотреть результат
python3 -m gitproc.cli logs backup
```

## Лучшие практики

### 1. Используйте Git для версионирования

```bash
# Всегда коммитьте изменения с понятными сообщениями
git add app.service
git commit -m "Increase memory limit to 512M"

# Используйте ветки для тестирования
git checkout -b test-new-config
# ... внести изменения ...
git commit -m "Test new configuration"

# Демон для тестовой ветки
python3 -m gitproc.cli daemon --watch-branch test-new-config
```

### 2. Настройте health checks

```ini
# Всегда добавляйте health checks для критичных сервисов
[Service]
ExecStart=/usr/bin/python3 /opt/app/server.py
HealthCheckURL=http://localhost:5000/health
HealthCheckInterval=30
```

### 3. Ограничивайте ресурсы

```ini
# Предотвращайте утечки памяти и CPU hogging
[Service]
ExecStart=/usr/bin/python3 /opt/app/server.py
MemoryLimit=512M
CPUQuota=100%
```

### 4. Используйте непривилегированных пользователей

```ini
# Никогда не запускайте сервисы от root
[Service]
ExecStart=/usr/bin/python3 /opt/app/server.py
User=appuser  # Создайте отдельного пользователя
```

### 5. Настройте автоматический перезапуск

```ini
# Для production сервисов
[Service]
ExecStart=/usr/bin/python3 /opt/app/server.py
Restart=always  # Автоматический перезапуск при сбоях
```

### 6. Документируйте конфигурации

```ini
# Добавляйте комментарии в unit-файлы
[Service]
# API сервер для мобильного приложения
# Требует подключения к PostgreSQL и Redis
ExecStart=/usr/bin/python3 /opt/api/server.py

# Перезапуск при любом выходе (включая обновления)
Restart=always

# Лимит памяти основан на профилировании под нагрузкой
MemoryLimit=512M
```

### 7. Мониторьте логи

```bash
# Регулярно проверяйте логи
python3 -m gitproc.cli logs app --lines 100

# Следите за логами в реальном времени
python3 -m gitproc.cli logs app --follow

# Проверяйте логи демона
tail -f /var/log/gitproc/daemon.log
```

### 8. Тестируйте изменения

```bash
# Перед применением в production
# 1. Создайте тестовую ветку
git checkout -b test-config

# 2. Внесите изменения
vim app.service
git commit -m "Test: increase memory limit"

# 3. Запустите демон для тестовой ветки
python3 -m gitproc.cli daemon --watch-branch test-config

# 4. Проверьте работу
python3 -m gitproc.cli status app
python3 -m gitproc.cli logs app

# 5. Если всё ОК, merge в main
git checkout main
git merge test-config
```

### 9. Используйте зависимости правильно

```ini
# Явно указывайте зависимости
[Service]
ExecStart=/usr/bin/python3 /opt/app/server.py
After=database.service
After=redis.service
After=rabbitmq.service
```

### 10. Регулярно делайте backup

```bash
# Backup Git-репозитория
cd /etc/gitproc/services
git bundle create /backup/gitproc-$(date +%Y%m%d).bundle --all

# Backup состояния
cp /var/lib/gitproc/state.json /backup/state-$(date +%Y%m%d).json
```

## Устранение проблем

См. раздел "Troubleshooting" в основном README.md для подробной информации о решении типичных проблем.

## Дополнительные ресурсы

- [Архитектура](ARCHITECTURE.md) - детальное описание архитектуры системы
- [Производительность](PERFORMANCE.md) - оптимизация и профилирование
- [Тесты](../tests/README.md) - запуск и написание тестов
- [Примеры](../examples/) - готовые примеры unit-файлов
