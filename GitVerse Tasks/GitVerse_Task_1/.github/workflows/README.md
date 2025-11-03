# GitHub Actions Workflows

## docker-ci.yml

Основной CI/CD пайплайн для Docker тестирования.

### Триггеры

- Push в ветки `main` и `develop`
- Pull Request в ветки `main` и `develop`
- Ручной запуск через GitHub UI (workflow_dispatch)

### Jobs

#### 1. Build
- Собирает Docker образ
- Использует BuildKit для оптимизации
- Кеширует слои в GitHub Actions cache
- Сохраняет образ как артефакт

#### 2. Test Unit
- Запускает unit тесты
- Генерирует coverage отчет
- Сохраняет результаты как артефакты

#### 3. Test Integration
- Запускает integration тесты
- Проверяет взаимодействие компонентов

#### 4. Test Compliance
- Запускает compliance тесты
- Проверяет соответствие требованиям безопасности

#### 5. Test E2E
- Запускает E2E тесты
- Симулирует реальные пользовательские сценарии

#### 6. Report
- Собирает результаты всех тестов
- Генерирует итоговый отчет (JSON и Markdown)
- Комментирует PR с результатами

#### 7. Publish
- Публикует образ в GitHub Container Registry
- Только для main ветки
- Тегирует как `latest` и по SHA коммита

### Артефакты

Все артефакты доступны в GitHub Actions UI:

- `docker-image` - Docker образ (1 день)
- `unit-test-results` - Результаты unit тестов
- `integration-test-results` - Результаты integration тестов
- `compliance-test-results` - Результаты compliance тестов
- `e2e-test-results` - Результаты E2E тестов
- `coverage-report` - HTML coverage отчет
- `final-test-report` - Итоговый отчет

### Использование

#### Просмотр результатов

1. Перейдите в Actions tab
2. Выберите workflow run
3. Просмотрите логи каждого job
4. Скачайте артефакты

#### Ручной запуск

1. Actions → Docker CI/CD Pipeline
2. Run workflow
3. Выберите ветку
4. Run workflow

#### Отладка

Добавьте в workflow для отладки:

```yaml
- name: Setup tmate session
  uses: mxschmitt/action-tmate@v3
  if: failure()
```

### Оптимизация

#### Кеширование

Workflow использует GitHub Actions cache для:
- Docker слоев (BuildKit cache)
- pip пакетов
- pytest cache

#### Параллелизм

Тесты запускаются параллельно:
- Unit, Integration, Compliance, E2E - одновременно
- Экономия времени ~50%

#### Условное выполнение

- Publish job - только для main
- Report job - всегда (даже при ошибках)

### Секреты

Workflow использует встроенные секреты:
- `GITHUB_TOKEN` - для публикации образов

Дополнительные секреты не требуются.

### Мониторинг

#### Status Badge

Добавьте в README.md:

```markdown
![Docker CI](https://github.com/yourorg/sysaudit/workflows/Docker%20CI%2FCD%20Pipeline/badge.svg)
```

#### Notifications

Настройте уведомления в Settings → Notifications:
- Email при провале
- Slack/Discord webhook

### Troubleshooting

#### Workflow не запускается

- Проверьте права доступа (Settings → Actions → General)
- Убедитесь что workflow файл в `.github/workflows/`

#### Тесты падают в CI, но работают локально

- Проверьте переменные окружения
- Убедитесь в детерминированности тестов
- Проверьте таймауты

#### Артефакты не загружаются

- Проверьте пути к файлам
- Убедитесь что файлы существуют
- Проверьте размер (лимит 2GB)

### Расширение

#### Добавление нового job

```yaml
test-performance:
  name: Performance Tests
  needs: build
  runs-on: ubuntu-latest
  steps:
    - name: Download Docker image
      uses: actions/download-artifact@v4
      with:
        name: docker-image
    
    - name: Load Docker image
      run: docker load < sysaudit-image.tar.gz
    
    - name: Run performance tests
      run: |
        docker run --rm sysaudit:test \
          python run_tests.py --performance
```

#### Добавление матрицы версий

```yaml
test-unit:
  strategy:
    matrix:
      python-version: ['3.8', '3.9', '3.10', '3.11']
  steps:
    - name: Build with Python ${{ matrix.python-version }}
      run: |
        docker build \
          --build-arg PYTHON_VERSION=${{ matrix.python-version }} \
          -t sysaudit:test .
```
