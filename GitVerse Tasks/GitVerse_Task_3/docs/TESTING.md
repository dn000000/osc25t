# GitProc Testing Guide

Полное руководство по тестированию GitProc - запуск тестов, написание новых тестов, CI/CD интеграция.

## Содержание

- [Обзор тестовой системы](#обзор-тестовой-системы)
- [Быстрый старт](#быстрый-старт)
- [Структура тестов](#структура-тестов)
- [Запуск тестов](#запуск-тестов)
- [Покрытие кода](#покрытие-кода)
- [Написание тестов](#написание-тестов)
- [Docker-тестирование](#docker-тестирование)
- [CI/CD интеграция](#cicd-интеграция)
- [Известные ограничения](#известные-ограничения)

## Обзор тестовой системы

GitProc использует комплексную систему тестирования:

- **Фреймворк**: pytest
- **Покрытие**: pytest-cov
- **Типы тестов**: unit, integration, end-to-end, manual-user-tests (отдельные, если нужно прямое взаимодействие)
- **Общее количество**: 146 тестов
- **Текущее покрытие**: ~59% (цель: >80%)
- **Время выполнения**: ~143 секунды

### Статистика тестов

```
Всего тестов: 146
Успешных: 120 (100%)
Неудачных: 0 (0%)
```

**Покрытие по модулям:**
- `config.py`: 100%
- `dependency_resolver.py`: 100%
- `parser.py`: 93%
- `health_monitor.py`: 89%
- `state_manager.py`: 88%
- `resource_controller.py`: 87%
- `git_integration.py`: 80%
- `process_manager.py`: 65%
- `daemon.py`: 45%
- `cli.py`: 40%

## Быстрый старт

### Установка зависимостей

```bash
# Установить все зависимости включая тестовые
pip install -r requirements.txt
```

Зависимости для тестирования:
```
pytest>=7.4.0          # Тестовый фреймворк
pytest-timeout>=2.1.0  # Таймауты для тестов
pytest-cov>=4.1.0      # Измерение покрытия
```

### Запуск всех тестов

**Linux/Unix:**
```bash
chmod +x run_tests.sh
./run_tests.sh
```

**Windows:**
```cmd
run_tests.bat
```

**Напрямую через pytest:**
```bash
python -m pytest tests/ -v
```

### Быстрая проверка

```bash
# Запустить только быстрые тесты (без e2e)
python -m pytest tests/ -v -m "not slow"

# Запустить только unit-тесты
python -m pytest tests/test_parser.py tests/test_config.py -v
```

## Структура тестов

```
tests/
├── __init__.py                    # Инициализация тестового пакета
├── README.md                      # Документация тестов
├── test_helpers.py                # Вспомогательные утилиты
│   ├── TestHelper                 # Создание тестовых файлов
│   ├── MockHTTPServer             # Mock HTTP сервер
│   └── ProcessHelper              # Управление тестовыми процессами
│
├── test_parser.py                 # Unit-тесты парсера (100%)
├── test_config.py                 # Unit-тесты конфигурации (100%)
├── test_dependency_resolver.py    # Unit-тесты зависимостей (100%)
├── test_state_manager.py          # Unit-тесты состояния (88%)
├── test_git_integration.py        # Integration-тесты Git (80%)
├── test_resource_controller.py    # Integration-тесты ресурсов (87%)
├── test_health_monitor.py         # Integration-тесты health checks (89%)
├── test_process_manager.py        # Integration-тесты процессов (65%)
├── test_daemon.py                 # Integration-тесты демона (45%)
├── test_cli.py                    # Integration-тесты CLI (40%)
└── test_e2e_integration.py        # End-to-end тесты (полные сценарии)
```

### Типы тестов

#### Unit-тесты

Тестируют отдельные компоненты в изоляции:

```python
# test_parser.py
def test_parse_valid_unit_file():
    """Тест парсинга корректного unit-файла"""
    content = """
    [Service]
    ExecStart=/usr/bin/python3 server.py
    Restart=always
    """
    unit = UnitFileParser.parse("test.service", content)
    assert unit.exec_start == "/usr/bin/python3 server.py"
    assert unit.restart == "always"
```

#### Integration-тесты

Тестируют взаимодействие компонентов:

```python
# test_git_integration.py
def test_detect_changes():
    """Тест обнаружения изменений в Git"""
    git = GitIntegration(repo_path)
    
    # Создать и закоммитить файл
    create_file("test.service")
    git.commit("Add test service")
    
    # Проверить обнаружение изменений
    changes = git.get_changed_files()
    assert "test.service" in changes
```

#### End-to-end тесты

Тестируют полные пользовательские сценарии:

```python
# test_e2e_integration.py
def test_complete_workflow():
    """Тест полного workflow: init → daemon → start → stop"""
    # 1. Инициализация
    cli.init(repo_path)
    
    # 2. Создание сервиса
    create_service_file("web.service")
    
    # 3. Запуск демона
    daemon = start_daemon()
    
    # 4. Запуск сервиса
    cli.start("web")
    assert service_is_running("web")
    
    # 5. Остановка сервиса
    cli.stop("web")
    assert service_is_stopped("web")
```

## Запуск тестов

### Все тесты

```bash
# С подробным выводом
python -m pytest tests/ -v

# С очень подробным выводом
python -m pytest tests/ -vv

# С кратким выводом
python -m pytest tests/ -q
```

### Конкретный файл

```bash
python -m pytest tests/test_parser.py -v
```

### Конкретный тест

```bash
python -m pytest tests/test_parser.py::TestUnitFileParser::test_parse_valid_unit_file -v
```

### По паттерну имени

```bash
# Все тесты содержащие "restart"
python -m pytest tests/ -k "restart" -v

# Все тесты содержащие "git" или "sync"
python -m pytest tests/ -k "git or sync" -v

# Все тесты НЕ содержащие "slow"
python -m pytest tests/ -k "not slow" -v
```

### По маркерам

```bash
# Только быстрые тесты
python -m pytest tests/ -m "not slow" -v

# Только медленные тесты
python -m pytest tests/ -m "slow" -v

# Только Linux-специфичные тесты
python -m pytest tests/ -m "linux" -v
```

### С таймаутом

```bash
# Прервать тесты, выполняющиеся дольше 10 секунд
python -m pytest tests/ --timeout=10 -v
```

### Остановка на первой ошибке

```bash
python -m pytest tests/ -x -v
```

### Повторный запуск только упавших тестов

```bash
# Первый запуск
python -m pytest tests/ -v

# Повторить только упавшие
python -m pytest tests/ --lf -v

# Сначала упавшие, потом остальные
python -m pytest tests/ --ff -v
```

### Параллельный запуск

```bash
# Установить pytest-xdist
pip install pytest-xdist

# Запустить в 4 процессах
python -m pytest tests/ -n 4 -v
```

## Покрытие кода

### Измерение покрытия

```bash
# С отчётом в терминале
python -m pytest tests/ --cov=gitproc --cov-report=term

# С HTML отчётом
python -m pytest tests/ --cov=gitproc --cov-report=html

# С XML отчётом (для CI/CD)
python -m pytest tests/ --cov=gitproc --cov-report=xml

# Все форматы сразу
python -m pytest tests/ --cov=gitproc --cov-report=term --cov-report=html --cov-report=xml
```

### Просмотр HTML отчёта

```bash
# После запуска с --cov-report=html
# Открыть в браузере
firefox htmlcov/index.html  # Linux
open htmlcov/index.html     # macOS
start htmlcov/index.html    # Windows
```

### Покрытие конкретного модуля

```bash
python -m pytest tests/test_parser.py --cov=gitproc.parser --cov-report=term
```

### Показать непокрытые строки

```bash
python -m pytest tests/ --cov=gitproc --cov-report=term-missing
```

### Минимальное покрытие

```bash
# Упасть если покрытие < 80%
python -m pytest tests/ --cov=gitproc --cov-fail-under=80
```

## Написание тестов

### Использование TestHelper

```python
import pytest
from tests.test_helpers import TestHelper

class TestMyFeature:
    @pytest.fixture
    def helper(self, tmp_path):
        """Создать helper для тестов"""
        return TestHelper(tmp_path)
    
    def test_something(self, helper):
        # Создать тестовый unit-файл
        unit_file = helper.create_unit_file(
            "test.service",
            exec_start="/usr/bin/python3 server.py",
            restart="always"
        )
        
        # Создать тестовый скрипт
        script = helper.create_test_script(
            "server.py",
            "print('Hello')"
        )
        
        # Создать Git репозиторий
        repo = helper.create_git_repo()
```

### Использование MockHTTPServer

```python
from tests.test_helpers import MockHTTPServer

def test_health_check():
    # Запустить mock HTTP сервер
    with MockHTTPServer(port=8080, response_code=200) as server:
        # Тестировать health check
        response = requests.get("http://localhost:8080/health")
        assert response.status_code == 200
```

### Использование ProcessHelper

```python
from tests.test_helpers import ProcessHelper

def test_process_management():
    helper = ProcessHelper()
    
    # Запустить тестовый процесс
    proc = helper.start_process(["/usr/bin/python3", "server.py"])
    
    try:
        # Проверить что процесс запущен
        assert helper.is_running(proc.pid)
        
        # Подождать завершения
        helper.wait_for_exit(proc.pid, timeout=5)
    finally:
        # Очистка
        helper.cleanup()
```

### Пропуск тестов на Windows

```python
import pytest
import sys

SKIP_ON_WINDOWS = pytest.mark.skipif(
    sys.platform == "win32",
    reason="Requires Unix-specific features"
)

@SKIP_ON_WINDOWS
def test_pid_namespace():
    """Тест PID namespace (только Linux)"""
    # Тест использующий PID namespaces
    pass
```

### Маркировка медленных тестов

```python
import pytest

@pytest.mark.slow
def test_long_running_operation():
    """Медленный тест (>5 секунд)"""
    # Долгая операция
    time.sleep(10)
```

### Параметризованные тесты

```python
import pytest

@pytest.mark.parametrize("restart_policy,expected", [
    ("always", True),
    ("on-failure", True),
    ("no", False),
])
def test_restart_policies(restart_policy, expected):
    """Тест различных политик перезапуска"""
    unit = UnitFile(restart=restart_policy)
    assert unit.should_restart() == expected
```

### Фикстуры

```python
import pytest

@pytest.fixture
def temp_repo(tmp_path):
    """Создать временный Git репозиторий"""
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    
    # Инициализировать Git
    git = GitIntegration(str(repo_path))
    git.init()
    
    yield str(repo_path)
    
    # Очистка (автоматическая для tmp_path)

def test_with_repo(temp_repo):
    """Тест использующий временный репозиторий"""
    # temp_repo содержит путь к репозиторию
    assert os.path.exists(temp_repo)
```

### Моки и патчи

```python
from unittest.mock import Mock, patch

def test_with_mock():
    """Тест с mock объектом"""
    mock_process = Mock()
    mock_process.pid = 12345
    mock_process.poll.return_value = None
    
    # Использовать mock
    assert mock_process.pid == 12345
    assert mock_process.poll() is None

@patch('gitproc.process_manager.subprocess.Popen')
def test_with_patch(mock_popen):
    """Тест с патчем subprocess"""
    mock_popen.return_value.pid = 12345
    
    # Код использующий subprocess.Popen
    manager = ProcessManager()
    proc = manager.start_process(...)
    
    # Проверить что Popen был вызван
    mock_popen.assert_called_once()
```

### Тестирование исключений

```python
import pytest

def test_invalid_unit_file():
    """Тест обработки невалидного unit-файла"""
    with pytest.raises(ValueError, match="Missing ExecStart"):
        UnitFileParser.parse("test.service", "[Service]\n")
```

### Тестирование логов

```python
import logging

def test_logging(caplog):
    """Тест логирования"""
    with caplog.at_level(logging.INFO):
        logger.info("Test message")
    
    assert "Test message" in caplog.text
```

## Docker-тестирование

### Зачем использовать Docker

- Изолированная Linux-среда на любой ОС
- Воспроизводимые результаты
- Тестирование Linux-специфичных функций
- CI/CD совместимость

### Запуск тестов в Docker

**Windows:**
```cmd
run_tests_docker.bat
```

**Linux/Mac:**
```bash
chmod +x run_tests_docker.sh
./run_tests_docker.sh
```

### Опции Docker-тестирования

```bash
# Без пересборки контейнера
./run_tests_docker.sh --no-build

# Конкретные тесты
./run_tests_docker.sh -k test_parser

# С подробным выводом
./run_tests_docker.sh -vv

# Остановка на первой ошибке
./run_tests_docker.sh -x
```

### Ручной запуск в Docker

```bash
# Собрать контейнер
docker-compose -f docker-compose.test.yml build

# Запустить тесты
docker-compose -f docker-compose.test.yml run --rm test

# Интерактивная оболочка
docker-compose -f docker-compose.test.yml run --rm test bash

# Внутри контейнера
pytest tests/ -v
```

### Структура Docker-тестирования

```
Dockerfile.test              # Определение контейнера
docker-compose.test.yml      # Оркестрация тестов
.dockerignore               # Исключения для Docker
```

**Dockerfile.test:**
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Установить зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Скопировать код
COPY . .

# Запустить тесты
CMD ["pytest", "tests/", "-v", "--cov=gitproc", "--cov-report=term", "--cov-report=html"]
```

## CI/CD интеграция

### GitHub Actions

```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
    
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
    
    - name: Run tests
      run: |
        pytest tests/ -v --cov=gitproc --cov-report=xml
    
    - name: Upload coverage
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml
```

### GitLab CI

```yaml
# .gitlab-ci.yml
test:
  image: python:3.11
  
  before_script:
    - pip install -r requirements.txt
  
  script:
    - pytest tests/ -v --cov=gitproc --cov-report=xml
  
  coverage: '/TOTAL.*\s+(\d+%)$/'
  
  artifacts:
    reports:
      coverage_report:
        coverage_format: cobertura
        path: coverage.xml
```

### Jenkins

```groovy
// Jenkinsfile
pipeline {
    agent any
    
    stages {
        stage('Setup') {
            steps {
                sh 'pip install -r requirements.txt'
            }
        }
        
        stage('Test') {
            steps {
                sh 'pytest tests/ -v --cov=gitproc --cov-report=xml --junitxml=junit.xml'
            }
        }
        
        stage('Report') {
            steps {
                junit 'junit.xml'
                cobertura coberturaReportFile: 'coverage.xml'
            }
        }
    }
}
```

### Travis CI

```yaml
# .travis.yml
language: python
python:
  - "3.8"
  - "3.9"
  - "3.10"
  - "3.11"

install:
  - pip install -r requirements.txt

script:
  - pytest tests/ -v --cov=gitproc --cov-report=xml

after_success:
  - bash <(curl -s https://codecov.io/bash)
```

## Известные ограничения

### Windows

Некоторые тесты автоматически пропускаются на Windows:

- **PID namespaces**: не поддерживаются Windows
- **Cgroups**: не поддерживаются Windows
- **Unix signals**: ограниченная поддержка
- **User switching**: работает по-другому

**Пропущенные тесты на Windows:**
```
tests/test_process_manager.py::test_pid_namespace
tests/test_resource_controller.py::test_cgroup_creation
tests/test_daemon.py::test_signal_handling
```

### Текущие проблемы

См. `KNOWN_TEST_LIMITATIONS.md` для деталей:

1. **Daemon tests** (26 неудачных)
   - Проблемы с Unix socket на некоторых системах
   - Race conditions в многопоточных тестах
   - Таймауты при запуске демона

2. **Process isolation tests**
   - Требуют root прав для полного тестирования
   - Могут быть нестабильны в контейнерах

3. **Git integration tests**
   - Зависят от конфигурации Git
   - Могут требовать настройки user.name/user.email

### Решение проблем

**Таймауты:**
```bash
# Увеличить таймаут для медленных систем
pytest tests/ --timeout=30 -v
```

**Права доступа:**
```bash
# Запустить с sudo для тестов требующих root
sudo pytest tests/test_process_manager.py -v
```

**Git конфигурация:**
```bash
# Настроить Git для тестов
git config --global user.name "Test User"
git config --global user.email "test@example.com"
```

## Отладка тестов

### Подробный вывод

```bash
# Максимальная детализация
pytest tests/ -vv -s

# Показать print() вывод
pytest tests/ -s

# Показать локальные переменные при ошибках
pytest tests/ -l
```

### Отладчик

```bash
# Запустить pdb при ошибке
pytest tests/ --pdb

# Запустить pdb в начале теста
pytest tests/ --trace
```

```python
# В коде теста
def test_something():
    import pdb; pdb.set_trace()
    # Отладка здесь
```

### Логирование

```bash
# Показать все логи
pytest tests/ --log-cli-level=DEBUG -v

# Логи только для конкретного модуля
pytest tests/ --log-cli-level=DEBUG --log-cli-format="%(name)s: %(message)s" -v
```

### Профилирование

```bash
# Установить pytest-profiling
pip install pytest-profiling

# Профилировать тесты
pytest tests/ --profile -v

# Показать 10 самых медленных тестов
pytest tests/ --durations=10 -v
```

## Лучшие практики

### 1. Изолируйте тесты

```python
# Плохо: тесты зависят друг от друга
class TestBad:
    shared_state = None
    
    def test_first(self):
        self.shared_state = "value"
    
    def test_second(self):
        assert self.shared_state == "value"  # Зависит от test_first

# Хорошо: каждый тест независим
class TestGood:
    @pytest.fixture
    def state(self):
        return "value"
    
    def test_first(self, state):
        assert state == "value"
    
    def test_second(self, state):
        assert state == "value"
```

### 2. Используйте фикстуры

```python
# Плохо: дублирование setup кода
def test_one():
    repo = create_repo()
    # тест

def test_two():
    repo = create_repo()
    # тест

# Хорошо: переиспользуемая фикстура
@pytest.fixture
def repo():
    return create_repo()

def test_one(repo):
    # тест

def test_two(repo):
    # тест
```

### 3. Очищайте ресурсы

```python
# Плохо: ресурсы не очищаются
def test_process():
    proc = start_process()
    assert proc.is_running()
    # Процесс остаётся запущенным!

# Хорошо: гарантированная очистка
def test_process():
    proc = start_process()
    try:
        assert proc.is_running()
    finally:
        proc.kill()
```

### 4. Тестируйте граничные случаи

```python
def test_memory_limit():
    # Нормальные значения
    assert parse_memory("100M") == 100 * 1024 * 1024
    
    # Граничные случаи
    assert parse_memory("0M") == 0
    assert parse_memory("1K") == 1024
    
    # Ошибочные значения
    with pytest.raises(ValueError):
        parse_memory("invalid")
    with pytest.raises(ValueError):
        parse_memory("-100M")
```

### 5. Используйте понятные имена

```python
# Плохо
def test_1():
    pass

def test_stuff():
    pass

# Хорошо
def test_parser_handles_valid_unit_file():
    pass

def test_parser_raises_error_on_missing_exec_start():
    pass
```

### 6. Один assert на концепцию

```python
# Плохо: много asserts в одном тесте
def test_unit_file():
    unit = parse_unit_file(content)
    assert unit.exec_start == "/usr/bin/python3"
    assert unit.restart == "always"
    assert unit.user == "nobody"
    assert unit.memory_limit == 100 * 1024 * 1024

# Хорошо: отдельные тесты для каждой концепции
def test_unit_file_exec_start():
    unit = parse_unit_file(content)
    assert unit.exec_start == "/usr/bin/python3"

def test_unit_file_restart_policy():
    unit = parse_unit_file(content)
    assert unit.restart == "always"
```

### 7. Документируйте тесты

```python
def test_health_check_triggers_restart():
    """
    Тест проверяет что неудачный health check вызывает перезапуск сервиса.
    
    Сценарий:
    1. Запустить сервис с health check
    2. Сервис возвращает HTTP 500
    3. Демон должен перезапустить сервис
    4. Проверить что PID изменился
    """
    # Реализация теста
```

## Дополнительные ресурсы

- [pytest документация](https://docs.pytest.org/)
- [pytest-cov документация](https://pytest-cov.readthedocs.io/)
- [Docker testing best practices](https://docs.docker.com/develop/dev-best-practices/)
- [CI/CD testing patterns](https://martinfowler.com/articles/continuousIntegration.html)
