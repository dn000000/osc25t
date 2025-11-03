# Сценарии использования GitConfig

## Сценарий 1: Централизованное хранилище конфигураций

### Описание
Один центральный сервер конфигураций, к которому обращаются несколько приложений.

### Реализация

```bash
# Запустить центральный сервер
python gitconfig_node.py start --repo ./config/central --http-port 8080
```

```bash
# Приложение 1 устанавливает свою конфигурацию
curl -X POST -d "postgres://db1:5432/app1" http://localhost:8080/keys/app1/database/url
curl -X POST -d "redis://cache1:6379" http://localhost:8080/keys/app1/cache/url

# Приложение 2 устанавливает свою конфигурацию
curl -X POST -d "postgres://db2:5432/app2" http://localhost:8080/keys/app2/database/url

# Приложения читают конфигурацию при старте
curl http://localhost:8080/keys/app1/database/url
curl http://localhost:8080/keys/app2/database/url
```

### Преимущества
- Единая точка управления конфигурациями
- История всех изменений через Git
- Простое развёртывание

---

## Сценарий 2: Распределённая система с репликацией

### Описание
Несколько датацентров, каждый со своим узлом. Автоматическая синхронизация конфигураций.

### Реализация

```bash
# Создать центральный bare repository
git init --bare ./config/shared.git

# Датацентр 1 (Москва)
python gitconfig_node.py start \
  --repo ./dc1/config \
  --http-port 8080 \
  --remote ./config/shared.git \
  --sync-interval 30

# Датацентр 2 (Санкт-Петербург)
python gitconfig_node.py start \
  --repo ./dc2/config \
  --http-port 8081 \
  --remote ./config/shared.git \
  --sync-interval 30

# Датацентр 3 (Екатеринбург)
python gitconfig_node.py start \
  --repo ./dc3/config \
  --http-port 8082 \
  --remote ./config/shared.git \
  --sync-interval 30
```

```bash
# Изменение в DC1 автоматически распространяется на DC2 и DC3
curl -X POST -d "new_value" http://localhost:8080/keys/global/config

# Через 30 секунд доступно на всех узлах
curl http://localhost:8081/keys/global/config  # DC2
curl http://localhost:8082/keys/global/config  # DC3
```

### Преимущества
- Высокая доступность (работает при отвале узлов)
- Низкая латентность (локальное чтение)
- Eventual consistency

---

## Сценарий 3: Feature Flags с версионированием

### Описание
Управление feature flags с возможностью отката к предыдущим версиям.

### Реализация

```bash
# Включить feature
python gitconfig_cli.py set /features/new_ui enabled --http http://localhost:8080

# Приложение проверяет флаг
curl http://localhost:8080/keys/features/new_ui

# Если что-то пошло не так, смотрим историю
python gitconfig_cli.py history /features/new_ui --http http://localhost:8080

# Откатываемся к предыдущей версии
python gitconfig_cli.py get /features/new_ui --commit abc123 --http http://localhost:8080
```

### Преимущества
- Полная история изменений
- Быстрый откат
- Audit log из коробки

---

## Сценарий 4: Distributed Lock через CAS

### Описание
Реализация распределённой блокировки для координации между сервисами.

### Реализация

```python
from gitconfig_core import GitConfigStore
import time
import socket

store = GitConfigStore('./data/locks')
node_id = socket.gethostname()

def acquire_lock(resource_name, timeout=10):
    """Попытка получить блокировку"""
    start = time.time()
    
    while time.time() - start < timeout:
        # Попытка установить lock (CAS: '' -> node_id)
        if store.cas(f'/locks/{resource_name}', '', node_id):
            print(f"Lock acquired by {node_id}")
            return True
        
        # Проверить, не истёк ли TTL у существующего lock
        time.sleep(0.5)
    
    return False

def release_lock(resource_name):
    """Освободить блокировку"""
    current = store.get(f'/locks/{resource_name}')
    if current == node_id:
        store.delete(f'/locks/{resource_name}')
        print(f"Lock released by {node_id}")
        return True
    return False

# Использование
if acquire_lock('database_migration'):
    try:
        # Критическая секция
        print("Running database migration...")
        time.sleep(5)
    finally:
        release_lock('database_migration')
else:
    print("Could not acquire lock")
```

### Преимущества
- Атомарность через CAS
- Простая реализация
- Видимость через Git history

---

## Сценарий 5: Session Storage с TTL

### Описание
Хранение временных сессий с автоматическим удалением.

### Реализация

```bash
# Создать сессию с TTL 1 час
curl -X POST -d '{"user_id":123,"role":"admin"}' \
  "http://localhost:8080/keys/sessions/abc123?ttl=3600"

# Проверить сессию
curl http://localhost:8080/keys/sessions/abc123

# Через час сессия автоматически удалится
```

```python
# В приложении
def create_session(session_id, user_data, ttl=3600):
    store.set(f'/sessions/{session_id}', json.dumps(user_data), ttl=ttl)

def get_session(session_id):
    data = store.get(f'/sessions/{session_id}')
    return json.loads(data) if data else None

def extend_session(session_id, ttl=3600):
    data = get_session(session_id)
    if data:
        store.set(f'/sessions/{session_id}', json.dumps(data), ttl=ttl)
```

### Преимущества
- Автоматическая очистка
- Не требует внешней БД
- Распределённое хранение

---

## Сценарий 6: Configuration Watch для Hot Reload

### Описание
Приложение автоматически перезагружает конфигурацию при изменении.

### Реализация

```python
import threading
from gitconfig_core import GitConfigStore

store = GitConfigStore('./data/app')

class ConfigWatcher:
    def __init__(self):
        self.config = {}
        self.load_config()
        self.start_watching()
    
    def load_config(self):
        """Загрузить конфигурацию"""
        self.config = {
            'db_host': store.get('/app/db/host'),
            'db_port': store.get('/app/db/port'),
            'api_key': store.get('/app/api/key'),
        }
        print(f"Config loaded: {self.config}")
    
    def watch_key(self, key):
        """Следить за изменениями ключа"""
        while True:
            if store.watch(key):
                print(f"Key {key} changed, reloading config...")
                self.load_config()
    
    def start_watching(self):
        """Запустить watchers для всех ключей"""
        keys = ['/app/db/host', '/app/db/port', '/app/api/key']
        for key in keys:
            thread = threading.Thread(target=self.watch_key, args=(key,), daemon=True)
            thread.start()

# Использование
watcher = ConfigWatcher()

# В другом процессе изменить конфигурацию
# store.set('/app/db/host', 'new_host')
# Приложение автоматически перезагрузит конфигурацию
```

### Преимущества
- Hot reload без перезапуска
- Реактивная конфигурация
- Минимальная задержка

---

## Сценарий 7: Multi-Environment Configuration

### Описание
Управление конфигурациями для разных окружений (dev, staging, prod).

### Реализация

```bash
# Development
python gitconfig_cli.py set /env/dev/db/host localhost --repo ./config
python gitconfig_cli.py set /env/dev/db/port 5432 --repo ./config
python gitconfig_cli.py set /env/dev/debug true --repo ./config

# Staging
python gitconfig_cli.py set /env/staging/db/host staging-db.internal --repo ./config
python gitconfig_cli.py set /env/staging/db/port 5432 --repo ./config
python gitconfig_cli.py set /env/staging/debug false --repo ./config

# Production
python gitconfig_cli.py set /env/prod/db/host prod-db.internal --repo ./config
python gitconfig_cli.py set /env/prod/db/port 5432 --repo ./config
python gitconfig_cli.py set /env/prod/debug false --repo ./config

# Приложение читает конфигурацию для своего окружения
ENV=prod
curl http://localhost:8080/list?prefix=/env/$ENV/&recursive=true
```

### Преимущества
- Изоляция окружений
- Единое хранилище
- История изменений для каждого окружения

---

## Сценарий 8: Service Discovery

### Описание
Регистрация и обнаружение сервисов в распределённой системе.

### Реализация

```python
import time
from gitconfig_core import GitConfigStore

store = GitConfigStore('./data/discovery')

class ServiceRegistry:
    def register(self, service_name, host, port, ttl=60):
        """Зарегистрировать сервис с TTL"""
        key = f'/services/{service_name}/{host}:{port}'
        data = f'{{"host":"{host}","port":{port},"registered_at":{time.time()}}}'
        store.set(key, data, ttl=ttl)
        print(f"Registered {service_name} at {host}:{port}")
    
    def discover(self, service_name):
        """Найти все экземпляры сервиса"""
        keys = store.list_keys(f'/services/{service_name}/', recursive=True)
        instances = []
        
        for key in keys:
            data = store.get(key)
            if data:
                instances.append(json.loads(data))
        
        return instances
    
    def heartbeat(self, service_name, host, port, interval=30, ttl=60):
        """Периодически обновлять регистрацию"""
        while True:
            self.register(service_name, host, port, ttl=ttl)
            time.sleep(interval)

# Использование
registry = ServiceRegistry()

# Сервис регистрируется при старте
registry.register('api-service', 'localhost', 8080, ttl=60)

# Heartbeat в фоне
import threading
thread = threading.Thread(
    target=registry.heartbeat,
    args=('api-service', 'localhost', 8080),
    daemon=True
)
thread.start()

# Клиент находит сервисы
instances = registry.discover('api-service')
print(f"Found {len(instances)} instances of api-service")
```

### Преимущества
- Автоматическое удаление мёртвых сервисов (TTL)
- Распределённое обнаружение
- История регистраций

---

## Сценарий 9: A/B Testing Configuration

### Описание
Управление A/B тестами с постепенным rollout.

### Реализация

```bash
# Начальная конфигурация (0% пользователей на новой версии)
python gitconfig_cli.py set /ab_tests/new_checkout/enabled true --http http://localhost:8080
python gitconfig_cli.py set /ab_tests/new_checkout/rollout_percent 0 --http http://localhost:8080

# Постепенное увеличение
python gitconfig_cli.py set /ab_tests/new_checkout/rollout_percent 10 --http http://localhost:8080
# Проверить метрики...

python gitconfig_cli.py set /ab_tests/new_checkout/rollout_percent 50 --http http://localhost:8080
# Проверить метрики...

python gitconfig_cli.py set /ab_tests/new_checkout/rollout_percent 100 --http http://localhost:8080

# Если что-то пошло не так, откатиться
python gitconfig_cli.py history /ab_tests/new_checkout/rollout_percent --http http://localhost:8080
# Найти предыдущий commit и откатиться
```

```python
# В приложении
def should_use_new_feature(user_id, feature_name):
    enabled = store.get(f'/ab_tests/{feature_name}/enabled')
    if enabled != 'true':
        return False
    
    rollout = int(store.get(f'/ab_tests/{feature_name}/rollout_percent') or '0')
    user_hash = hash(user_id) % 100
    
    return user_hash < rollout
```

### Преимущества
- Контролируемый rollout
- История изменений процента
- Быстрый откат при проблемах

---

## Сценарий 10: Audit Log для Compliance

### Описание
Использование Git истории для audit log и compliance требований.

### Реализация

```bash
# Все изменения автоматически логируются в Git
python gitconfig_cli.py set /security/admin_password "new_hash" --http http://localhost:8080

# Получить полную историю изменений
python gitconfig_cli.py history /security/admin_password --http http://localhost:8080

# Вывод:
# abc12345 - 2025-10-25T10:30:45 - Set /security/admin_password at 2025-10-25T10:30:45
# def67890 - 2025-10-24T15:20:30 - Set /security/admin_password at 2025-10-24T15:20:30
```

```python
# Генерация audit report
def generate_audit_report(key_prefix, start_date, end_date):
    keys = store.list_keys(key_prefix, recursive=True)
    report = []
    
    for key in keys:
        history = store.history(key)
        for entry in history:
            entry_date = datetime.fromisoformat(entry['date'])
            if start_date <= entry_date <= end_date:
                report.append({
                    'key': key,
                    'commit': entry['commit'],
                    'date': entry['date'],
                    'message': entry['message'],
                    'author': entry['author']
                })
    
    return report

# Использование
report = generate_audit_report('/security/', 
                               datetime(2025, 10, 1),
                               datetime(2025, 10, 31))
```

### Преимущества
- Неизменяемая история (Git)
- Полный audit trail
- Соответствие compliance требованиям
- Возможность отката к любой версии

---

## Заключение

GitConfig предоставляет гибкую основу для различных сценариев использования:

- **Централизованное управление** конфигурациями
- **Распределённые системы** с репликацией
- **Версионирование** и откат изменений
- **Координация** между сервисами (locks)
- **Временные данные** с TTL
- **Реактивные приложения** с watch
- **Audit и compliance**

Все сценарии используют одну и ту же простую архитектуру на основе Git, что обеспечивает надёжность, прозрачность и простоту использования.
