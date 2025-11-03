# Быстрый старт: Docker Testing Pipeline

## 🚀 Запуск за 30 секунд

### Linux/macOS

```bash
chmod +x scripts/run-docker-tests.sh
./scripts/run-docker-tests.sh
```

### Windows (PowerShell)

```powershell
.\scripts\run-docker-tests.ps1
```

### Docker Compose

```bash
docker-compose up --abort-on-container-exit
```

## 📋 Что тестируется

### ✅ Unit Tests
- Фильтрация файлов (FilterManager)
- Мониторинг изменений (FileMonitor)
- Git операции (GitManager)
- Проверка соответствия (ComplianceChecker)
- Система оповещений (AlertManager)

### ✅ Integration Tests
- Интеграция компонентов
- Обработка событий
- Батчинг операций

### ✅ Compliance Tests
- World-writable файлы
- SUID/SGID бинарники
- Слабые права доступа

### ✅ E2E Tests (Real User Scenarios)
1. Инициализация системы мониторинга
2. Отслеживание изменений файлов
3. Обнаружение дрифта от базовой линии
4. Проверка соответствия требованиям безопасности
5. Откат изменений к предыдущим версиям
6. Использование CLI команд

## 📊 Отчеты

После выполнения тестов доступны:

### Coverage Report (HTML)
```bash
# Открыть в браузере
open htmlcov/index.html        # macOS
xdg-open htmlcov/index.html    # Linux
start htmlcov\index.html       # Windows
```

### JSON Reports
```bash
# E2E отчет
cat test-results/e2e-report.json

# Итоговый отчет
cat test-results/final-report.json
```

Пример отчета:
```json
{
  "timestamp": "2024-01-15T10:30:00",
  "project": "sysaudit",
  "version": "0.1.0",
  "summary": {
    "total_tests": 50,
    "passed": 50,
    "failed": 0,
    "success_rate": "100.0%"
  }
}
```

## 🔧 Отдельные команды

### Только Unit тесты
```bash
docker build -t sysaudit:test .
docker run --rm \
  -v $(pwd)/test-results:/app/test-results \
  -v $(pwd)/htmlcov:/app/htmlcov \
  sysaudit:test \
  python run_tests.py --unit --coverage --html-coverage
```

### Только E2E тесты
```bash
docker run --rm \
  --user root \
  -v $(pwd)/test-results:/app/test-results \
  sysaudit:test \
  python tests/e2e/test_real_user_scenarios.py
```

### Интерактивная отладка
```bash
docker run -it --rm sysaudit:test /bin/bash
```

## 🎯 Makefile команды

Если у вас установлен Make:

```bash
make -f Makefile.docker help          # Справка
make -f Makefile.docker build         # Сборка образа
make -f Makefile.docker test          # Все тесты
make -f Makefile.docker test-unit     # Unit тесты
make -f Makefile.docker test-e2e      # E2E тесты
make -f Makefile.docker report        # Показать отчет
make -f Makefile.docker coverage      # Открыть coverage
make -f Makefile.docker clean         # Очистка
```

## 🔄 CI/CD

### GitHub Actions

Пайплайн запускается автоматически при:
- Push в `main` или `develop`
- Создании Pull Request
- Ручном запуске

Просмотр результатов:
1. Перейдите в **Actions** tab
2. Выберите последний workflow run
3. Скачайте артефакты с результатами

### Локальный запуск CI

```bash
# Установить act (опционально)
brew install act  # macOS
# или https://github.com/nektos/act

# Запустить workflow локально
act -j test-unit
```

## 📁 Структура результатов

```
test-results/
├── e2e-report.json          # E2E тесты
├── final-report.json        # Итоговый отчет
└── .coverage                # Coverage данные

htmlcov/
├── index.html               # Главная страница coverage
└── ...                      # Детальные отчеты по файлам
```

## ⚡ Быстрые проверки

### Проверка перед коммитом
```bash
# Быстрые тесты (без медленных)
docker run --rm sysaudit:test python run_tests.py --fast
```

### Проверка конкретного файла
```bash
docker run --rm sysaudit:test pytest tests/test_filter.py -v
```

### Проверка с verbose выводом
```bash
docker run --rm sysaudit:test python run_tests.py --verbose
```

## 🐛 Troubleshooting

### Ошибка сборки
```bash
# Пересборка без кеша
docker build --no-cache -t sysaudit:test .
```

### Тесты падают
```bash
# Запуск с отладкой
docker run --rm sysaudit:test pytest tests/ -v -s

# Интерактивная отладка
docker run -it --rm sysaudit:test /bin/bash
```

### Нет места на диске
```bash
# Очистка Docker
docker system prune -af --volumes
```

### Permission denied
```bash
# Запуск с root правами
docker run --rm --user root sysaudit:test <command>
```

## 📚 Дополнительная документация

- **README_DOCKER.md** - Полная документация по Docker
- **DOCKER_EXAMPLES.md** - Примеры использования
- **.github/workflows/README.md** - Документация по CI/CD
- **TESTING.md** - Общая документация по тестированию

## 💡 Полезные команды

```bash
# Размер образа
docker images sysaudit:test

# Статистика контейнера
docker stats sysaudit-test

# Логи контейнера
docker logs sysaudit-test

# Список запущенных контейнеров
docker ps -a | grep sysaudit

# Удаление всех контейнеров sysaudit
docker rm -f $(docker ps -a -q --filter "name=sysaudit")
```

## 🎉 Готово!

После успешного выполнения вы увидите:

```
╔════════════════════════════════════════════════════════╗
║  Все тесты успешно пройдены!                          ║
╚════════════════════════════════════════════════════════╝

Результаты тестов: test-results/
Coverage отчет: htmlcov/index.html
Итоговый отчет: test-results/final-report.json
```

## 🤝 Поддержка

Если возникли проблемы:
1. Проверьте **Troubleshooting** секцию
2. Посмотрите логи: `docker logs sysaudit-test`
3. Запустите интерактивный shell: `docker run -it --rm sysaudit:test /bin/bash`
4. Изучите детальную документацию в **README_DOCKER.md**
