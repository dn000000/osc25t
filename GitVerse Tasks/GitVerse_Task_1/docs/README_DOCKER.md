# Docker Testing Pipeline для Sysaudit

Полная документация по Docker пайплайну для сборки и тестирования проекта sysaudit.

## Обзор

Пайплайн включает:
- **Сборку Docker образа** с многоступенчатой оптимизацией
- **Unit тесты** - тестирование отдельных компонентов
- **Integration тесты** - тестирование взаимодействия компонентов
- **Compliance тесты** - проверка соответствия требованиям безопасности
- **E2E тесты** - реальные пользовательские сценарии
- **Детальные отчеты** - JSON и HTML отчеты о прохождении тестов

## Быстрый старт

### Linux/macOS

```bash
# Запуск всех тестов
chmod +x scripts/run-docker-tests.sh
./scripts/run-docker-tests.sh
```

### Windows (PowerShell)

```powershell
# Запуск всех тестов
.\scripts\run-docker-tests.ps1
```

### Docker Compose

```bash
# Запуск всех тестов через docker-compose
docker-compose up --abort-on-container-exit

# Запуск только unit тестов
docker-compose run --rm sysaudit-test python run_tests.py --unit

# Запуск E2E тестов
docker-compose run --rm sysaudit-e2e
```

## Структура файлов

```
.
├── Dockerfile                          # Многоступенчатая сборка
├── docker-compose.yml                  # Оркестрация тестов
├── .dockerignore                       # Исключения для сборки
├── .github/workflows/docker-ci.yml     # CI/CD пайплайн
├── scripts/
│   ├── run-docker-tests.sh            # Скрипт для Linux/macOS
│   └── run-docker-tests.ps1           # Скрипт для Windows
└── tests/e2e/
    └── test_real_user_scenarios.py    # E2E тесты
```

## Dockerfile

Многоступенчатая сборка для оптимизации размера образа:


**Stage 1: Builder**
- Установка зависимостей для сборки
- Создание виртуального окружения
- Установка Python пакетов

**Stage 2: Runtime**
- Минимальный базовый образ
- Копирование только необходимых файлов
- Создание непривилегированного пользователя

### Сборка образа

```bash
# Сборка образа
docker build -t sysaudit:test .

# Сборка с кешированием
docker build --cache-from sysaudit:test -t sysaudit:test .

# Сборка без кеша
docker build --no-cache -t sysaudit:test .
```

## Тестирование

### Unit тесты

Тестирование отдельных компонентов системы:

```bash
docker run --rm \
  -v $(pwd)/test-results:/app/test-results \
  -v $(pwd)/htmlcov:/app/htmlcov \
  sysaudit:test \
  python run_tests.py --unit --coverage --html-coverage
```

Покрывает:
- FilterManager (фильтрация файлов)
- FileMonitor (мониторинг изменений)
- GitManager (Git операции)
- ComplianceChecker (проверка соответствия)
- AlertManager (система оповещений)

### Integration тесты

Тестирование взаимодействия компонентов:

```bash
docker run --rm \
  -v $(pwd)/test-results:/app/test-results \
  sysaudit:test \
  python run_tests.py --integration
```

Покрывает:
- Интеграция мониторинга и Git
- Обработка событий и батчинг
- Взаимодействие с файловой системой

### Compliance тесты

Проверка соответствия требованиям безопасности:

```bash
docker run --rm \
  -v $(pwd)/test-results:/app/test-results \
  sysaudit:test \
  python run_tests.py --compliance
```

Покрывает:
- Обнаружение world-writable файлов
- Проверка SUID/SGID бинарников
- Слабые права доступа

### E2E тесты (Real User Scenarios)

Реальные пользовательские сценарии:

```bash
docker run --rm \
  --user root \
  -v $(pwd)/test-results:/app/test-results \
  -e PYTHONUNBUFFERED=1 \
  sysaudit:test \
  python tests/e2e/test_real_user_scenarios.py
```

Сценарии:
1. **Инициализация системы** - администратор настраивает мониторинг
2. **Мониторинг файлов** - отслеживание изменений конфигураций
3. **Обнаружение дрифта** - сравнение с базовой линией
4. **Проверка соответствия** - аудит безопасности
5. **Откат изменений** - восстановление предыдущих версий
6. **CLI команды** - использование интерфейса командной строки

## Отчеты

### Coverage отчет

HTML отчет о покрытии кода тестами:

```bash
# Генерация отчета
docker run --rm \
  -v $(pwd)/htmlcov:/app/htmlcov \
  sysaudit:test \
  python run_tests.py --unit --html-coverage

# Просмотр отчета
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
start htmlcov/index.html  # Windows
```

### JSON отчеты

Структурированные отчеты для каждого типа тестов:

- `test-results/e2e-report.json` - E2E тесты
- `test-results/.coverage` - Coverage данные
- `test-results/final-report.json` - Итоговый отчет

Пример отчета:

```json
{
  "timestamp": "2024-01-15T10:30:00",
  "test_type": "e2e",
  "passed": 15,
  "failed": 0,
  "total": 15,
  "duration_seconds": 45.2,
  "success_rate": "100.0%"
}
```

## CI/CD Pipeline

GitHub Actions автоматически запускает тесты при:
- Push в ветки `main` или `develop`
- Создании Pull Request
- Ручном запуске (workflow_dispatch)

### Этапы пайплайна

1. **Build** - сборка Docker образа
2. **Test Unit** - unit тесты
3. **Test Integration** - integration тесты
4. **Test Compliance** - compliance тесты
5. **Test E2E** - E2E тесты
6. **Report** - генерация итогового отчета
7. **Publish** - публикация образа (только main)

### Артефакты

После выполнения пайплайна доступны:
- Docker образ
- Результаты всех тестов
- Coverage отчет
- Итоговый отчет (JSON и Markdown)

### Комментарии в PR

Для Pull Request автоматически создается комментарий с результатами тестов.

## Локальная разработка

### Быстрое тестирование

```bash
# Только измененные тесты
docker run --rm sysaudit:test pytest tests/test_filter.py

# С verbose выводом
docker run --rm sysaudit:test python run_tests.py --verbose

# Остановка на первой ошибке
docker run --rm sysaudit:test python run_tests.py --failfast
```

### Интерактивная отладка

```bash
# Запуск контейнера с shell
docker run -it --rm sysaudit:test /bin/bash

# Внутри контейнера
python run_tests.py --unit
pytest tests/test_filter.py -v
sysaudit --help
```

### Монтирование кода

Для разработки без пересборки:

```bash
docker run --rm \
  -v $(pwd)/sysaudit:/app/sysaudit \
  -v $(pwd)/tests:/app/tests \
  sysaudit:test \
  python run_tests.py
```

## Оптимизация

### Кеширование слоев

Docker использует кеширование для ускорения сборки:

```dockerfile
# Сначала копируем зависимости (меняются редко)
COPY pyproject.toml setup.py ./
RUN pip install -e .[dev]

# Потом код (меняется часто)
COPY sysaudit/ ./sysaudit/
```

### .dockerignore

Исключает ненужные файлы из контекста сборки:
- `.git/` - история Git
- `__pycache__/` - Python кеш
- `*.pyc` - скомпилированные файлы
- `.pytest_cache/` - кеш pytest
- `htmlcov/` - coverage отчеты

### Многоступенчатая сборка

Разделение на builder и runtime уменьшает размер образа:
- Builder: ~500MB (с компиляторами)
- Runtime: ~200MB (только необходимое)

## Troubleshooting

### Ошибка "permission denied"

```bash
# Добавьте --user root для операций требующих привилегий
docker run --rm --user root sysaudit:test <command>
```

### Тесты не находят модули

```bash
# Убедитесь что пакет установлен
docker run --rm sysaudit:test pip list | grep sysaudit

# Переустановите пакет
docker run --rm sysaudit:test pip install -e .
```

### Медленная сборка

```bash
# Используйте BuildKit для параллельной сборки
DOCKER_BUILDKIT=1 docker build -t sysaudit:test .

# Или настройте в docker-compose.yml
COMPOSE_DOCKER_CLI_BUILD=1 DOCKER_BUILDKIT=1 docker-compose build
```

### Нет места на диске

```bash
# Очистка неиспользуемых образов
docker system prune -a

# Очистка volumes
docker volume prune
```

## Требования

- Docker 20.10+
- Docker Compose 2.0+ (опционально)
- 2GB свободного места
- 4GB RAM (рекомендуется)

## Дополнительные ресурсы

- [Dockerfile best practices](https://docs.docker.com/develop/develop-images/dockerfile_best-practices/)
- [Docker Compose documentation](https://docs.docker.com/compose/)
- [GitHub Actions documentation](https://docs.github.com/en/actions)
- [pytest documentation](https://docs.pytest.org/)