# Примеры использования Docker Pipeline

## Быстрые команды

### Запуск всех тестов

```bash
# Linux/macOS
./scripts/run-docker-tests.sh

# Windows PowerShell
.\scripts\run-docker-tests.ps1

# Docker Compose
docker-compose up --abort-on-container-exit

# Make (если установлен)
make -f Makefile.docker test
```

### Запуск отдельных типов тестов

```bash
# Unit тесты
make -f Makefile.docker test-unit

# Integration тесты
make -f Makefile.docker test-integration

# Compliance тесты
make -f Makefile.docker test-compliance

# E2E тесты
make -f Makefile.docker test-e2e
```

## Сценарии использования

### 1. Разработчик: Локальное тестирование перед коммитом

```bash
# Быстрая проверка unit тестов
docker build -t sysaudit:test .
docker run --rm sysaudit:test python run_tests.py --unit --fast

# Если все ОК, запустить полный набор
./scripts/run-docker-tests.sh
```

### 2. CI/CD: Автоматическое тестирование

GitHub Actions автоматически запускает пайплайн при push:

```yaml
# .github/workflows/docker-ci.yml уже настроен
# Просто делайте git push и смотрите результаты в Actions
```

### 3. QA: Проверка перед релизом

```bash
# Полный набор тестов с отчетами
./scripts/run-docker-tests.sh

# Проверка coverage
open htmlcov/index.html

# Проверка E2E отчета
cat test-results/e2e-report.json | python -m json.tool
```

### 4. DevOps: Интеграция в существующий CI

```bash
# Jenkins
stage('Test') {
    steps {
        sh './scripts/run-docker-tests.sh'
        publishHTML([
            reportDir: 'htmlcov',
            reportFiles: 'index.html',
            reportName: 'Coverage Report'
        ])
    }
}

# GitLab CI
test:
  script:
    - ./scripts/run-docker-tests.sh
  artifacts:
    paths:
      - test-results/
      - htmlcov/
```

## Отладка тестов

### Запуск одного теста

```bash
# Конкретный тест
docker run --rm sysaudit:test \
  pytest tests/test_filter.py::TestFilterManager::test_default_ignore_patterns -v

# С отладочным выводом
docker run --rm sysaudit:test \
  pytest tests/test_filter.py -v -s
```

### Интерактивная отладка

```bash
# Запуск shell в контейнере
docker run -it --rm sysaudit:test /bin/bash

# Внутри контейнера
cd /app
python -m pytest tests/test_filter.py --pdb  # Отладчик при ошибке
python -c "from sysaudit.monitor.filter import FilterManager; fm = FilterManager(); print(fm)"
```

### Просмотр логов

```bash
# Логи последнего запуска
docker logs sysaudit-test

# Следить за логами в реальном времени
docker logs -f sysaudit-test

# Логи с временными метками
docker logs -t sysaudit-test
```

## Работа с отчетами

### Просмотр coverage

```bash
# Генерация HTML отчета
docker run --rm \
  -v $(pwd)/htmlcov:/app/htmlcov \
  sysaudit:test \
  python run_tests.py --unit --html-coverage

# Открыть в браузере
# macOS
open htmlcov/index.html

# Linux
xdg-open htmlcov/index.html

# Windows
start htmlcov/index.html
```

### Анализ JSON отчетов

```bash
# Красивый вывод JSON
cat test-results/e2e-report.json | python -m json.tool

# Извлечение конкретных данных
cat test-results/final-report.json | python -c "
import json, sys
data = json.load(sys.stdin)
print(f\"Success Rate: {data['summary']['success_rate']}\")
print(f\"Total Tests: {data['summary']['total_tests']}\")
"

# Проверка на провалы
if grep -q '"failed": 0' test-results/final-report.json; then
  echo "All tests passed!"
else
  echo "Some tests failed!"
  exit 1
fi
```

### Экспорт отчетов

```bash
# Копирование отчетов
cp -r htmlcov /path/to/reports/coverage-$(date +%Y%m%d)
cp test-results/final-report.json /path/to/reports/

# Архивирование
tar -czf test-reports-$(date +%Y%m%d).tar.gz test-results/ htmlcov/

# Отправка на S3 (пример)
aws s3 cp test-reports-$(date +%Y%m%d).tar.gz s3://my-bucket/reports/
```

## Оптимизация производительности

### Параллельный запуск тестов

```bash
# Использование pytest-xdist
docker run --rm sysaudit:test \
  pytest -n 4 tests/  # 4 параллельных процесса
```

### Кеширование Docker слоев

```bash
# Использование BuildKit
export DOCKER_BUILDKIT=1
docker build -t sysaudit:test .

# Кеширование из registry
docker build \
  --cache-from ghcr.io/yourorg/sysaudit:latest \
  -t sysaudit:test .
```

### Быстрые тесты для разработки

```bash
# Пропуск медленных тестов
docker run --rm sysaudit:test \
  python run_tests.py --fast

# Только измененные файлы (требует git)
docker run --rm \
  -v $(pwd)/.git:/app/.git:ro \
  sysaudit:test \
  pytest --testmon
```

## Интеграция с IDE

### VS Code

Создайте `.vscode/tasks.json`:

```json
{
  "version": "2.0.0",
  "tasks": [
    {
      "label": "Docker: Run Tests",
      "type": "shell",
      "command": "./scripts/run-docker-tests.sh",
      "group": {
        "kind": "test",
        "isDefault": true
      }
    },
    {
      "label": "Docker: Run Unit Tests",
      "type": "shell",
      "command": "make -f Makefile.docker test-unit"
    }
  ]
}
```

### PyCharm

1. Settings → Tools → External Tools
2. Add new tool:
   - Name: Docker Tests
   - Program: `./scripts/run-docker-tests.sh`
   - Working directory: `$ProjectFileDir$`

## Мониторинг и метрики

### Время выполнения тестов

```bash
# Измерение времени
time ./scripts/run-docker-tests.sh

# Детальная статистика по тестам
docker run --rm sysaudit:test \
  pytest --durations=10 tests/
```

### Размер образа

```bash
# Проверка размера
docker images sysaudit:test

# История слоев
docker history sysaudit:test

# Анализ содержимого
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
  wagoodman/dive:latest sysaudit:test
```

### Использование ресурсов

```bash
# Статистика контейнера
docker stats sysaudit-test

# Ограничение ресурсов
docker run --rm \
  --memory="512m" \
  --cpus="1.0" \
  sysaudit:test \
  python run_tests.py
```

## Troubleshooting

### Проблема: Тесты падают с timeout

```bash
# Увеличить timeout
docker run --rm \
  -e PYTEST_TIMEOUT=300 \
  sysaudit:test \
  pytest --timeout=300 tests/
```

### Проблема: Недостаточно памяти

```bash
# Увеличить лимит памяти
docker run --rm \
  --memory="2g" \
  sysaudit:test \
  python run_tests.py
```

### Проблема: Конфликт портов

```bash
# Использовать другие порты
docker run --rm \
  -p 8081:8080 \
  sysaudit:test
```

### Проблема: Старые кеши

```bash
# Очистка всех кешей
docker system prune -af --volumes
docker builder prune -af

# Пересборка без кеша
docker build --no-cache -t sysaudit:test .
```

## Best Practices

### 1. Регулярное тестирование

```bash
# Добавить в pre-commit hook
cat > .git/hooks/pre-commit << 'EOF'
#!/bin/bash
echo "Running tests..."
docker build -q -t sysaudit:test . && \
docker run --rm sysaudit:test python run_tests.py --fast
EOF
chmod +x .git/hooks/pre-commit
```

### 2. Версионирование образов

```bash
# Тегирование по версии
docker build -t sysaudit:0.1.0 .
docker build -t sysaudit:latest .

# Тегирование по коммиту
GIT_SHA=$(git rev-parse --short HEAD)
docker build -t sysaudit:$GIT_SHA .
```

### 3. Безопасность

```bash
# Сканирование уязвимостей
docker scan sysaudit:test

# Использование непривилегированного пользователя
docker run --rm --user 1000:1000 sysaudit:test

# Только чтение файловой системы
docker run --rm --read-only sysaudit:test
```

### 4. Документирование

```bash
# Добавить метаданные в образ
docker build \
  --label "version=0.1.0" \
  --label "git.commit=$(git rev-parse HEAD)" \
  --label "build.date=$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  -t sysaudit:test .

# Просмотр метаданных
docker inspect sysaudit:test | jq '.[0].Config.Labels'
```

## Дополнительные инструменты

### Docker Compose для разработки

```yaml
# docker-compose.dev.yml
version: '3.8'
services:
  dev:
    build: .
    volumes:
      - ./sysaudit:/app/sysaudit
      - ./tests:/app/tests
    command: python run_tests.py --watch
```

### Makefile для удобства

```makefile
# Добавить в Makefile
docker-test:
	./scripts/run-docker-tests.sh

docker-shell:
	docker run -it --rm sysaudit:test /bin/bash

docker-clean:
	docker system prune -af
```

### GitHub Actions локально

```bash
# Установить act
brew install act  # macOS
# или скачать с https://github.com/nektos/act

# Запустить workflow локально
act -j test-unit
```
