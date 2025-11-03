# GitProc FAQ (Часто задаваемые вопросы)

Ответы на часто задаваемые вопросы о GitProc.

## Общие вопросы

### Что такое GitProc?

GitProc - это менеджер процессов, похожий на systemd, который хранит конфигурации сервисов в Git-репозитории. Это обеспечивает версионирование конфигураций, возможность отката и распределённое управление сервисами.

### Чем GitProc отличается от systemd?

**Основные отличия:**

| Функция | GitProc | systemd |
|---------|---------|---------|
| Git-интеграция | ✅ Встроенная | ❌ Нет |
| Кроссплатформенность | ✅ Linux/macOS/Windows | ❌ Только Linux |
| Системная интеграция | ❌ Не требуется | ✅ Требуется |
| Версионирование конфигураций | ✅ Автоматическое | ❌ Ручное |
| Откат конфигураций | ✅ Через Git | ❌ Ручной |
| Изоляция процессов | ✅ PID namespaces | ✅ Полная изоляция |
| Зрелость | ⚠️ В разработке | ✅ Production-ready |

**Когда использовать GitProc:**
- Нужно версионирование конфигураций
- Требуется кроссплатформенность
- Хотите простоту без системной интеграции
- Разработка и тестирование

**Когда использовать systemd:**
- Production Linux системы
- Нужна полная системная интеграция
- Требуется максимальная стабильность
- Сложные сценарии изоляции

### Чем GitProc отличается от Docker/Kubernetes?

**Docker/Kubernetes** - это контейнеризация и оркестрация:
- Полная изоляция (файловая система, сеть, и т.д.)
- Управление образами и контейнерами
- Распределённая оркестрация
- Более сложная настройка

**GitProc** - это управление процессами:
- Лёгкая изоляция (PID namespaces)
- Управление обычными процессами
- Простая настройка
- Git-based конфигурация

**Можно использовать вместе:**
- GitProc внутри Docker контейнера
- GitProc для управления локальными сервисами
- Docker для изоляции, GitProc для управления

### Можно ли использовать GitProc в production?

**Для production:**
1. Тщательно протестируйте на dev-окружении
2. Настройте мониторинг и алертинг
3. Регулярно делайте backup конфигураций
4. Имейте план отката (например, на systemd)
5. Следите за обновлениями проекта

## Установка и настройка

### Какие системные требования?

**Минимальные:**
- Python 3.8+
- Git 2.0+
- 50 MB свободного места
- Linux/macOS/Windows

**Для полной функциональности:**
- Linux kernel 3.8+ (PID namespaces, cgroups)
- Root права (для namespace и cgroup операций)
- Cgroups v2 (для ограничения ресурсов)

### Как установить на Windows?

```cmd
git clone <repository-url>
cd gitproc
setup.bat
```

**Ограничения на Windows:**
- ❌ PID namespaces не поддерживаются
- ❌ Cgroups не поддерживаются
- ⚠️ User switching работает по-другому
- ✅ Базовое управление процессами работает

### Нужны ли root права?

**Зависит от функций:**

**Без root:**
- ✅ Базовое управление процессами
- ✅ Git интеграция
- ✅ Health checks
- ✅ Запуск от текущего пользователя

**С root:**
- ✅ PID namespaces
- ✅ Cgroups (ограничение ресурсов)
- ✅ User switching (запуск от других пользователей)

**Рекомендация:**
- Разработка: можно без root
- Production: лучше с root для полной функциональности

### Как настроить автозапуск демона?

**Через systemd (Linux):**

```ini
# /etc/systemd/system/gitproc.service
[Unit]
Description=GitProc Daemon
After=network.target

[Service]
Type=simple
User=root
ExecStart=/usr/bin/python3 -m gitproc.cli daemon
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable gitproc
sudo systemctl start gitproc
```

**Через cron (Linux/macOS):**

```bash
# Добавить в crontab
@reboot /usr/bin/python3 -m gitproc.cli daemon
```

**Через Task Scheduler (Windows):**

1. Открыть Task Scheduler
2. Create Basic Task
3. Trigger: At startup
4. Action: Start a program
5. Program: `python`
6. Arguments: `-m gitproc.cli daemon`

## Использование

### Как создать первый сервис?

```bash
# 1. Инициализировать репозиторий
python3 -m gitproc.cli init --repo /etc/gitproc/services

# 2. Создать unit-файл
cat > /etc/gitproc/services/web.service << EOF
[Service]
ExecStart=/usr/bin/python3 -m http.server 8080
Restart=always
User=nobody
EOF

# 3. Закоммитить
cd /etc/gitproc/services
git add web.service
git commit -m "Add web service"

# 4. Запустить демон
python3 -m gitproc.cli daemon &

# 5. Запустить сервис
python3 -m gitproc.cli start web
```

### Как просмотреть логи сервиса?

```bash
# Все логи
python3 -m gitproc.cli logs web

# Последние 50 строк
python3 -m gitproc.cli logs web --lines 50

# Следить в реальном времени
python3 -m gitproc.cli logs web --follow

# Логи также доступны в файлах
tail -f /var/log/gitproc/web.log
```

### Как настроить автоматический перезапуск?

```ini
[Service]
ExecStart=/usr/bin/python3 /app/server.py
Restart=always  # Всегда перезапускать
```

**Опции Restart:**
- `always` - всегда перезапускать при выходе
- `on-failure` - только при ненулевом коде выхода
- `no` - никогда не перезапускать (по умолчанию)

### Как ограничить использование ресурсов?

```ini
[Service]
ExecStart=/usr/bin/python3 /app/server.py
MemoryLimit=512M  # Максимум 512 МБ памяти
CPUQuota=100%     # Максимум 100% одного ядра (одно полное ядро)
```

**Требования:**
- Linux с cgroups v2
- Демон запущен с правами root

**Проверка cgroups:**
```bash
# Проверить наличие cgroups v2
mount | grep cgroup2

# Проверить использование ресурсов
cat /sys/fs/cgroup/gitproc/web/memory.current
cat /sys/fs/cgroup/gitproc/web/cpu.stat
```

### Как настроить health checks?

```ini
[Service]
ExecStart=/usr/bin/python3 /app/server.py
HealthCheckURL=http://localhost:5000/health
HealthCheckInterval=30  # Проверять каждые 30 секунд
```

**Требования к health endpoint:**

```python
# Flask пример
@app.route('/health')
def health():
    try:
        # Проверить зависимости
        db.execute('SELECT 1')
        redis.ping()
        return 'OK', 200
    except Exception as e:
        return f'Unhealthy: {e}', 503
```

**Поведение:**
- HTTP 200 = здоров
- Другие коды или timeout = нездоров
- При неудаче сервис автоматически перезапускается

### Как настроить зависимости между сервисами?

```ini
# database.service
[Service]
ExecStart=/usr/bin/postgres -D /var/lib/postgresql/data

# app.service
[Service]
ExecStart=/usr/bin/python3 /app/server.py
After=database.service  # Запустится после database
```

**При запуске app:**
```bash
python3 -m gitproc.cli start app
# Автоматически запустит database, затем app
```

**Множественные зависимости:**
```ini
[Service]
ExecStart=/usr/bin/python3 /app/server.py
After=database.service
After=redis.service
After=rabbitmq.service
```

### Как откатить конфигурацию?

```bash
# 1. Посмотреть историю
cd /etc/gitproc/services
git log --oneline

# Вывод:
# abc123 Update app config
# def456 Add health check
# ghi789 Initial config

# 2. Откатиться
python3 -m gitproc.cli rollback def456

# Все сервисы автоматически перезагрузятся
# с конфигурацией из коммита def456
```

## Устранение проблем

### Демон не запускается

**Проблема:** Демон падает сразу после запуска.

**Решения:**

1. **Проверить что демон не запущен:**
```bash
ps aux | grep gitproc
# Убить если запущен
kill <PID>
```

2. **Проверить socket:**
```bash
ls -la /var/run/gitproc.sock
# Удалить если существует
rm /var/run/gitproc.sock
```

3. **Проверить логи:**
```bash
cat /var/log/gitproc/daemon.log
```

4. **Проверить права:**
```bash
# Запустить с sudo если нужны namespace/cgroups
sudo python3 -m gitproc.cli daemon
```

### Сервис не запускается

**Проблема:** Сервис падает сразу после запуска.

**Решения:**

1. **Проверить статус:**
```bash
python3 -m gitproc.cli status web
```

2. **Проверить логи:**
```bash
python3 -m gitproc.cli logs web
```

3. **Проверить команду:**
```bash
# Попробовать запустить вручную
/usr/bin/python3 /app/server.py
```

4. **Проверить права:**
```bash
# Проверить что файл исполняемый
ls -la /app/server.py
chmod +x /app/server.py
```

5. **Проверить пользователя:**
```bash
# Проверить что пользователь существует
id nobody
```

### Permission denied ошибки

**Проблема:** Ошибки прав доступа при запуске.

**Решения:**

1. **Запустить демон с sudo:**
```bash
sudo python3 -m gitproc.cli daemon
```

2. **Проверить cgroups:**
```bash
mount | grep cgroup
ls -la /sys/fs/cgroup/
```

3. **Проверить права на файлы:**
```bash
ls -la /etc/gitproc/services/
chmod 644 /etc/gitproc/services/*.service
```

### Git sync не работает

**Проблема:** Изменения в Git не применяются автоматически.

**Решения:**

1. **Проверить что изменения закоммичены:**
```bash
cd /etc/gitproc/services
git status
git log
```

2. **Проверить ветку:**
```bash
# Демон должен мониторить правильную ветку
python3 -m gitproc.cli daemon --watch-branch main
```

3. **Ручная синхронизация:**
```bash
python3 -m gitproc.cli sync
```

4. **Проверить логи демона:**
```bash
tail -f /var/log/gitproc/daemon.log
```

### Health checks не работают

**Проблема:** Health checks не обнаруживают проблемы.

**Решения:**

1. **Проверить endpoint вручную:**
```bash
curl http://localhost:8080/health
```

2. **Проверить что сервис слушает:**
```bash
netstat -tlnp | grep 8080
# или
ss -tlnp | grep 8080
```

3. **Увеличить интервал:**
```ini
HealthCheckInterval=60  # Дать больше времени на запуск
```

4. **Проверить логи:**
```bash
python3 -m gitproc.cli logs web
grep "health" /var/log/gitproc/daemon.log
```

### Процесс становится зомби

**Проблема:** Остановленные процессы остаются зомби.

**Решения:**

1. **Перезапустить демон:**
```bash
# Найти PID демона
ps aux | grep gitproc

# Убить демон
kill <PID>

# Запустить снова
python3 -m gitproc.cli daemon
```

2. **Проверить SIGCHLD handler:**
```bash
# Проверить логи демона
grep "SIGCHLD" /var/log/gitproc/daemon.log
```

### Не могу подключиться к демону

**Проблема:** CLI команды не могут подключиться к демону.

**Решения:**

1. **Проверить что демон запущен:**
```bash
ps aux | grep gitproc
```

2. **Проверить socket:**
```bash
ls -la /var/run/gitproc.sock
```

3. **Проверить права на socket:**
```bash
chmod 666 /var/run/gitproc.sock
```

4. **Проверить путь к socket:**
```bash
# В конфигурации
cat ~/.gitproc/config.json
```

## Производительность

### Сколько ресурсов использует демон?

**Типичное использование (10 сервисов):**
- CPU: <1% idle, 2-5% active
- Память: 40-50 MB
- Диск I/O: минимальный

**Масштабирование:**
- Линейный рост памяти (~1-2 MB на сервис)
- Константное использование CPU (event-driven)

### Как оптимизировать производительность?

**1. Настроить Git polling:**
```python
# В gitproc/daemon.py
poll_interval = 15  # Увеличить для меньшей нагрузки
max_poll_interval = 60
```

**2. Настроить state persistence:**
```python
# В gitproc/state_manager.py
min_save_interval = 5.0  # Увеличить для меньшего I/O
```

**3. Использовать health checks разумно:**
```ini
# Не слишком частые проверки
HealthCheckInterval=60  # Вместо 10
```

**4. Мониторить производительность:**
```bash
# Использовать профилировщик
python3 profile_daemon.py --duration 60
```

См. [PERFORMANCE.md](PERFORMANCE.md) для деталей.

### Сколько сервисов можно запустить?

**Протестировано:**
- 100+ сервисов работают стабильно
- Линейный рост использования памяти
- Константное использование CPU

**Ограничения:**
- Системные лимиты (ulimit, file descriptors)
- Доступная память
- Производительность диска (для логов)

**Рекомендации:**
- <50 сервисов: отлично
- 50-100 сервисов: хорошо
- >100 сервисов: требуется тестирование

## Разработка

### Как запустить тесты?

```bash
# Все тесты
./run_tests.sh

# Конкретный файл
pytest tests/test_parser.py -v

# С покрытием
pytest tests/ --cov=gitproc --cov-report=html

# В Docker
./run_tests_docker.sh
```

См. [TESTING.md](TESTING.md) для деталей.

### Как добавить новую функцию?

1. **Создать issue** с описанием функции
2. **Fork репозитория**
3. **Создать feature branch:**
```bash
git checkout -b feature/my-feature
```
4. **Написать код и тесты**
5. **Обновить документацию**
6. **Создать Pull Request**

### Как сообщить о баге?

1. **Проверить существующие issues**
2. **Создать новый issue** с:
   - Описанием проблемы
   - Шагами для воспроизведения
   - Ожидаемым поведением
   - Фактическим поведением
   - Версией GitProc
   - ОС и версией Python
   - Логами (если применимо)

### Где найти документацию для разработчиков?

- [ARCHITECTURE.md](ARCHITECTURE.md) - архитектура системы
- [TESTING.md](TESTING.md) - тестирование
- [API.md](API.md) - API reference
- [PERFORMANCE.md](PERFORMANCE.md) - производительность
- Комментарии в коде

## Интеграция

### Как интегрировать с CI/CD?

**GitHub Actions:**
```yaml
- name: Deploy services
  run: |
    cd /etc/gitproc/services
    git pull
    python3 -m gitproc.cli sync
```

**GitLab CI:**
```yaml
deploy:
  script:
    - cd /etc/gitproc/services
    - git pull
    - python3 -m gitproc.cli sync
```

См. [API.md](API.md) для примеров.

### Как интегрировать с Ansible?

```yaml
- name: Deploy GitProc services
  hosts: servers
  tasks:
    - name: Update configs
      git:
        repo: https://github.com/example/services.git
        dest: /etc/gitproc/services
    
    - name: Sync GitProc
      command: python3 -m gitproc.cli sync
```

См. [API.md](API.md) для полного примера.

### Как интегрировать с Docker?

```dockerfile
FROM python:3.11-slim

# Установить GitProc
COPY gitproc/ /opt/gitproc/
RUN pip install -r /opt/gitproc/requirements.txt

# Скопировать конфигурации
COPY services/ /etc/gitproc/services/

# Запустить демон
CMD ["python3", "-m", "gitproc.cli", "daemon"]
```

### Как интегрировать с Prometheus?

```python
from prometheus_client import start_http_server, Gauge

service_status = Gauge('gitproc_service_status', 'Status', ['service'])

# Собирать метрики
def collect():
    result = subprocess.run(["python3", "-m", "gitproc.cli", "list"])
    # Парсить и обновлять метрики
    service_status.labels(service="web").set(1)

start_http_server(9090)
```

См. [API.md](API.md) для полного примера.

## Безопасность

### Безопасно ли запускать сервисы от root?

**Нет!** Всегда используйте непривилегированных пользователей:

```ini
[Service]
ExecStart=/usr/bin/python3 /app/server.py
User=appuser  # НЕ root!
```

**Почему:**
- Компрометация сервиса = компрометация системы
- Нет изоляции от системных ресурсов
- Нарушение принципа наименьших привилегий

**Исключения:**
- Сервисы требующие привилегированных портов (<1024)
- Системные сервисы (с осторожностью)

### Как обеспечить безопасность конфигураций?

1. **Не храните секреты в Git:**
```ini
# Плохо
Environment=DATABASE_PASSWORD=secret123

# Хорошо
Environment=DATABASE_PASSWORD_FILE=/etc/secrets/db_password
```

2. **Используйте .gitignore:**
```
secrets/
*.key
*.pem
```

3. **Используйте переменные окружения:**
```bash
export DATABASE_PASSWORD="secret123"
```

4. **Используйте secret management:**
- HashiCorp Vault
- AWS Secrets Manager
- Kubernetes Secrets

### Как ограничить доступ к демону?

1. **Права на socket:**
```bash
chmod 600 /var/run/gitproc.sock
chown root:root /var/run/gitproc.sock
```

2. **Firewall для health checks:**
```bash
# Разрешить только localhost
iptables -A INPUT -p tcp --dport 8080 -s 127.0.0.1 -j ACCEPT
iptables -A INPUT -p tcp --dport 8080 -j DROP
```

3. **SELinux/AppArmor:**
```bash
# Создать профиль для GitProc
```

## Миграция

### Как мигрировать с systemd?

1. **Конвертировать unit-файлы:**
```bash
# systemd: /etc/systemd/system/web.service
[Unit]
Description=Web Server
After=network.target

[Service]
ExecStart=/usr/bin/python3 /app/server.py
Restart=always
User=www-data

# GitProc: /etc/gitproc/services/web.service
[Service]
ExecStart=/usr/bin/python3 /app/server.py
Restart=always
User=www-data
```

2. **Тестировать на dev:**
```bash
# Остановить systemd сервис
sudo systemctl stop web

# Запустить через GitProc
python3 -m gitproc.cli start web

# Проверить работу
python3 -m gitproc.cli status web
```

3. **Постепенная миграция:**
- Мигрировать по одному сервису
- Мониторить работу
- Держать systemd как fallback

### Как мигрировать с Docker Compose?

1. **Конвертировать docker-compose.yml:**
```yaml
# docker-compose.yml
services:
  web:
    image: nginx
    ports:
      - "80:80"
    environment:
      - ENV=production
```

```ini
# GitProc: web.service
[Service]
ExecStart=/usr/bin/docker run -p 80:80 -e ENV=production nginx
Restart=always
```

2. **Или запустить напрямую:**
```ini
[Service]
ExecStart=/usr/bin/nginx -g "daemon off;"
Restart=always
Environment=ENV=production
```

## Дополнительные ресурсы

- [README.md](../README.md) - Главная документация
- [USAGE.md](USAGE.md) - Руководство пользователя
- [API.md](API.md) - API reference
- [ARCHITECTURE.md](ARCHITECTURE.md) - Архитектура
- [TESTING.md](TESTING.md) - Тестирование
- [PERFORMANCE.md](PERFORMANCE.md) - Производительность
- [Examples](../examples/) - Примеры конфигураций

## Получить помощь

- **Documentation** - прочитать документацию
- **Examples** - посмотреть примеры

## Лицензия

См. LICENSE файл в корне репозитория.
