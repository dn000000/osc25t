# GitProc Documentation

Полная документация по GitProc - менеджеру процессов с Git-интеграцией.

## Содержание

### Основные документы

- **[README.md](../README.md)** - Обзор проекта, быстрый старт, основные возможности
- **[USAGE.md](USAGE.md)** - Полное руководство по использованию GitProc
- **[API.md](API.md)** - Справочник по API и примеры интеграции
- **[FAQ.md](FAQ.md)** - Часто задаваемые вопросы и ответы
- **[ARCHITECTURE.md](ARCHITECTURE.md)** - Детальное описание архитектуры системы
- **[TESTING.md](TESTING.md)** - Руководство по тестированию
- **[PERFORMANCE.md](PERFORMANCE.md)** - Оптимизация и профилирование

### Дополнительные документы

- **[DOCKER_TESTING.md](../DOCKER_TESTING.md)** - Docker-based тестирование
- **[KNOWN_TEST_LIMITATIONS.md](../KNOWN_TEST_LIMITATIONS.md)** - Известные ограничения тестов
- **[TEST_FIXES_SUMMARY.md](../TEST_FIXES_SUMMARY.md)** - История исправлений тестов

### Примеры

- **[examples/](../examples/)** - Готовые примеры unit-файлов сервисов
  - `simple-http-server.service` - Простой HTTP сервер
  - `app-with-healthcheck.service` - Приложение с health checks
  - `nginx.service` - Веб-сервер с ограничениями ресурсов
  - `dependent-services.service` - Сервисы с зависимостями

## Быстрая навигация

### Для начинающих

1. Прочитайте [README.md](../README.md) для общего понимания
2. Следуйте разделу "Quick Start" для первого запуска
3. Изучите [примеры](../examples/) для понимания формата unit-файлов
4. Прочитайте [USAGE.md](USAGE.md) для детального изучения возможностей

### Для разработчиков

1. Изучите [ARCHITECTURE.md](ARCHITECTURE.md) для понимания внутреннего устройства
2. Прочитайте [TESTING.md](TESTING.md) для запуска и написания тестов
3. Ознакомьтесь с [PERFORMANCE.md](PERFORMANCE.md) для оптимизации
4. Проверьте [tests/README.md](../tests/README.md) для структуры тестов

### Для DevOps

1. Изучите раздел "Configuration" в [README.md](../README.md)
2. Прочитайте "Best Practices" в [USAGE.md](USAGE.md)
3. Настройте мониторинг согласно [PERFORMANCE.md](PERFORMANCE.md)
4. Интегрируйте с CI/CD используя [TESTING.md](TESTING.md)

## Структура проекта

```
gitproc/
├── gitproc/                    # Основной код
│   ├── cli.py                 # CLI интерфейс
│   ├── daemon.py              # Демон процесс
│   ├── parser.py              # Парсер unit-файлов
│   ├── process_manager.py     # Управление процессами
│   ├── git_integration.py     # Git интеграция
│   ├── state_manager.py       # Управление состоянием
│   ├── resource_controller.py # Контроль ресурсов (cgroups)
│   ├── dependency_resolver.py # Разрешение зависимостей
│   ├── health_monitor.py      # Health checks
│   ├── git_monitor.py         # Мониторинг Git
│   └── config.py              # Конфигурация
│
├── tests/                      # Тесты
│   ├── test_*.py              # Unit и integration тесты
│   ├── test_e2e_integration.py # End-to-end тесты
│   └── test_helpers.py        # Вспомогательные утилиты
│
├── docs/                       # Документация
│   ├── README.md              # Этот файл
│   ├── USAGE.md               # Руководство пользователя
│   ├── ARCHITECTURE.md        # Архитектура
│   ├── TESTING.md             # Тестирование
│   └── PERFORMANCE.md         # Производительность
│
├── examples/                   # Примеры unit-файлов
│   ├── simple-http-server.service
│   ├── app-with-healthcheck.service
│   ├── nginx.service
│   └── dependent-services.service
│
├── requirements.txt            # Python зависимости
├── setup.sh / setup.bat       # Скрипты установки
├── run_tests.sh / .bat        # Скрипты запуска тестов
└── README.md                  # Главный README

```

## Основные концепции

### Unit-файлы

Конфигурационные файлы в INI-формате, описывающие сервисы:

```ini
[Service]
ExecStart=/usr/bin/python3 /app/server.py
Restart=always
User=appuser
Environment=PORT=8080
MemoryLimit=512M
CPUQuota=100%
HealthCheckURL=http://localhost:8080/health
After=database.service
```

### Git-интеграция

- Все unit-файлы хранятся в Git-репозитории
- Изменения отслеживаются автоматически
- Возможность отката к предыдущим версиям
- Полная история изменений конфигураций

### Демон

Фоновый процесс, который:
- Мониторит Git-репозиторий
- Управляет жизненным циклом сервисов
- Выполняет health checks
- Перезапускает упавшие сервисы
- Применяет ограничения ресурсов

### Изоляция

- **PID namespaces** (Linux): процессы изолированы друг от друга
- **Cgroups**: ограничение CPU и памяти
- **User separation**: сервисы запускаются от непривилегированных пользователей

## Системные требования

### Минимальные

- Python 3.8+
- Git 2.0+
- Linux/macOS/Windows

### Для полной функциональности

- Linux kernel 3.8+ (для PID namespaces и cgroups)
- Root права (для namespace и cgroup операций)
- Cgroups v2 (для ограничения ресурсов)

### Поддержка платформ

| Функция | Linux | macOS | Windows |
|---------|-------|-------|---------|
| Базовое управление процессами | ✅ | ✅ | ✅ |
| Git интеграция | ✅ | ✅ | ✅ |
| Health checks | ✅ | ✅ | ✅ |
| PID namespaces | ✅ | ❌ | ❌ |
| Cgroups | ✅ | ❌ | ❌ |
| User switching | ✅ | ✅ | ⚠️ |

✅ Полная поддержка | ⚠️ Частичная поддержка | ❌ Не поддерживается

## Часто задаваемые вопросы

### Чем GitProc отличается от systemd?

- **Git-интеграция**: конфигурации в Git с версионированием
- **Кроссплатформенность**: работает на Linux, macOS, Windows
- **Простота**: не требует системной интеграции
- **Гибкость**: легко расширяется и модифицируется

### Можно ли использовать в production?

GitProc находится в активной разработке. Текущая версия (0.1.0) подходит для:
- Разработки и тестирования
- Небольших проектов
- Прототипирования

Для production рекомендуется:
- Тщательное тестирование
- Мониторинг и алертинг
- Резервное копирование конфигураций

### Как мигрировать с systemd?

1. Конвертировать systemd unit-файлы в формат GitProc
2. Протестировать на dev-окружении
3. Постепенно мигрировать сервисы
4. Мониторить работу

См. раздел "Migration" в [USAGE.md](USAGE.md) (будет добавлен).

### Как получить помощь?

1. Проверьте раздел "Troubleshooting" в [README.md](../README.md)
2. Изучите [примеры](../examples/)
3. Проверьте логи: `python3 -m gitproc.cli logs <service>`
4. Создайте issue в репозитории проекта

## Вклад в проект

Мы приветствуем вклад в проект! См. раздел "Contributing" в [README.md](../README.md).

### Области для улучшения

- Увеличение покрытия тестами (цель: >80%)
- Улучшение документации
- Добавление новых функций
- Исправление багов
- Оптимизация производительности

### Процесс разработки

1. Fork репозитория
2. Создайте feature branch
3. Внесите изменения
4. Добавьте тесты
5. Обновите документацию
6. Создайте Pull Request

## Лицензия

См. LICENSE файл в корне репозитория.

## Контакты

- **Issues**: GitHub Issues
- **Discussions**: GitHub Discussions
- **Email**: [будет добавлен]

## История изменений

См. CHANGELOG.md (будет добавлен) для детальной истории изменений.
