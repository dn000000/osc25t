# 🚀 Docker Testing Pipeline - Начните здесь!

## Что это?

Полный Docker пайплайн для сборки и тестирования проекта **sysaudit** с детальными отчетами.

## ⚡ Быстрый запуск (30 секунд)

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

## 📋 Что будет протестировано?

✅ **Unit Tests** (~40 тестов) - отдельные компоненты  
✅ **Integration Tests** (~15 тестов) - взаимодействие компонентов  
✅ **Compliance Tests** (~10 тестов) - требования безопасности  
✅ **E2E Tests** (~20 проверок) - реальные пользовательские сценарии  

**Итого:** ~85 тестов за ~65 секунд

## 📊 Результаты

После выполнения вы получите:

1. **Coverage Report** - `htmlcov/index.html` (~85% покрытие)
2. **E2E Report** - `test-results/e2e-report.json`
3. **Final Report** - `test-results/final-report.json`

```bash
# Открыть coverage отчет
open htmlcov/index.html        # macOS
xdg-open htmlcov/index.html    # Linux
start htmlcov\index.html       # Windows

# Посмотреть JSON отчет
cat test-results/final-report.json | python -m json.tool
```

## 📚 Документация

### Для начинающих
- **[QUICK_START_DOCKER.md](QUICK_START_DOCKER.md)** ⭐ - Начните отсюда!
- **[DOCKER_PIPELINE_SUMMARY.md](DOCKER_PIPELINE_SUMMARY.md)** - Итоговая сводка

### Для разработчиков
- **[README_DOCKER.md](README_DOCKER.md)** - Полная документация
- **[DOCKER_EXAMPLES.md](DOCKER_EXAMPLES.md)** - Примеры использования
- **[TESTING.md](TESTING.md)** - Документация по тестам

### Для DevOps
- **[PIPELINE_OVERVIEW.md](PIPELINE_OVERVIEW.md)** - Архитектура пайплайна
- **[.github/workflows/README.md](.github/workflows/README.md)** - CI/CD документация

## 🎯 Основные команды

```bash
# Сборка образа
docker build -t sysaudit:test .

# Все тесты
./scripts/run-docker-tests.sh

# Только unit тесты
docker run --rm sysaudit:test python run_tests.py --unit

# Только E2E тесты
docker run --rm --user root sysaudit:test \
  python tests/e2e/test_real_user_scenarios.py

# Интерактивный shell
docker run -it --rm sysaudit:test /bin/bash
```

## 🔧 Makefile (если установлен Make)

```bash
make -f Makefile.docker help          # Справка
make -f Makefile.docker test          # Все тесты
make -f Makefile.docker test-unit     # Unit тесты
make -f Makefile.docker test-e2e      # E2E тесты
make -f Makefile.docker coverage      # Открыть coverage
make -f Makefile.docker clean         # Очистка
```

## 🤖 CI/CD

GitHub Actions автоматически запускает все тесты при:
- Push в `main` или `develop`
- Создании Pull Request
- Ручном запуске

Просмотр результатов: **Actions** → **Docker CI/CD Pipeline**

## 📦 Структура файлов

```
.
├── Dockerfile                          # Многоступенчатая сборка
├── docker-compose.yml                  # Оркестрация тестов
├── .dockerignore                       # Оптимизация сборки
├── .github/workflows/
│   ├── docker-ci.yml                  # GitHub Actions пайплайн
│   └── README.md                      # CI/CD документация
├── scripts/
│   ├── run-docker-tests.sh            # Скрипт для Linux/macOS
│   └── run-docker-tests.ps1           # Скрипт для Windows
├── tests/e2e/
│   └── test_real_user_scenarios.py    # E2E тесты
├── Makefile.docker                     # Make команды
├── START_HERE.md                       # Этот файл
├── QUICK_START_DOCKER.md              # Быстрый старт
├── README_DOCKER.md                   # Полная документация
├── DOCKER_EXAMPLES.md                 # Примеры
├── PIPELINE_OVERVIEW.md               # Обзор пайплайна
└── DOCKER_PIPELINE_SUMMARY.md         # Итоговая сводка
```

## 🎓 Что дальше?

1. **Запустите тесты:**
   ```bash
   ./scripts/run-docker-tests.sh
   ```

2. **Изучите отчеты:**
   ```bash
   open htmlcov/index.html
   ```

3. **Прочитайте документацию:**
   - [QUICK_START_DOCKER.md](QUICK_START_DOCKER.md) - детальный быстрый старт
   - [README_DOCKER.md](README_DOCKER.md) - полная документация

4. **Интегрируйте в workflow:**
   - Настройте pre-commit hook
   - Используйте в CI/CD
   - Запускайте перед каждым коммитом

## ❓ Вопросы?

- **Troubleshooting:** См. секцию в [README_DOCKER.md](README_DOCKER.md)
- **Примеры:** См. [DOCKER_EXAMPLES.md](DOCKER_EXAMPLES.md)

## ✨ Особенности

✅ Многоступенчатая сборка (образ ~200MB)  
✅ Параллельное выполнение тестов  
✅ Детальные отчеты (HTML, JSON, Markdown)  
✅ Реальные пользовательские сценарии  
✅ CI/CD интеграция из коробки  
✅ Полная документация  

## 🎉 Готово!

Пайплайн готов к использованию. Запустите тесты и изучите результаты!

```bash
./scripts/run-docker-tests.sh
```

---

**Следующий шаг:** [QUICK_START_DOCKER.md](QUICK_START_DOCKER.md) ⭐
