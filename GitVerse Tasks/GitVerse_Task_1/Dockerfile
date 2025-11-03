# Multi-stage build for sysaudit
# Stage 1: Builder - установка зависимостей и сборка
FROM python:3.11-slim as builder

LABEL maintainer="System Audit Team"
LABEL description="Git-based System Audit & Compliance Monitor"

# Установка системных зависимостей для сборки
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Создание виртуального окружения
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Установка зависимостей напрямую (без editable mode для ускорения)
RUN pip install --no-cache-dir \
    watchdog>=3.0.0 \
    GitPython>=3.1.0 \
    click>=8.0.0 \
    PyYAML>=6.0 \
    requests>=2.28.0 \
    pytest>=7.0.0 \
    pytest-cov>=4.0.0 \
    black>=23.0.0 \
    flake8>=6.0.0 \
    mypy>=1.0.0

# Stage 2: Runtime - финальный образ
FROM python:3.11-slim

# Установка только runtime зависимостей
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    procps \
    && rm -rf /var/lib/apt/lists/*

# Копирование виртуального окружения из builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Создание рабочих директорий
RUN mkdir -p /app /etc/sysaudit /var/lib/sysaudit/repo /var/log/sysaudit

WORKDIR /app

# Копирование исходного кода
COPY sysaudit/ ./sysaudit/
COPY tests/ ./tests/
COPY examples/ ./examples/
COPY run_tests.py pytest.ini ./
COPY sysaudit.service ./

# Установка пакета в PYTHONPATH (без установки для ускорения)
ENV PYTHONPATH=/app:$PYTHONPATH

# Создание пользователя для запуска (не root для безопасности в тестах)
RUN useradd -m -u 1000 -s /bin/bash sysaudit && \
    chown -R sysaudit:sysaudit /app /etc/sysaudit /var/lib/sysaudit /var/log/sysaudit

# Создание wrapper скрипта для sysaudit CLI
RUN printf '#!/bin/bash\nexec python -m sysaudit.cli "$@"\n' > /usr/local/bin/sysaudit && \
    chmod +x /usr/local/bin/sysaudit

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD sysaudit --version || exit 1

# Метаданные
LABEL version="0.1.0"
LABEL git.repo="https://github.com/sysaudit/sysaudit"

# По умолчанию запускаем тесты
CMD ["python", "run_tests.py", "--coverage"]
