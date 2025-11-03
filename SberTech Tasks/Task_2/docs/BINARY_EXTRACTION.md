# Автоматическое извлечение бинарников из Docker

## Обзор

Проект настроен для автоматического извлечения скомпилированных бинарников из Docker контейнера в локальную папку `build/`.

## Использование

### Windows

Запустите скрипт `build-docker.bat`:

```batch
build-docker.bat
```

Этот скрипт:
1. Собирает Docker образ с проектом
2. Извлекает бинарник `uringkv` в папку `build/`
3. Запускает тесты в привилегированном режиме
4. Показывает результаты сборки

### Linux/WSL

Используйте `build.sh` с флагом Docker:

```bash
USE_DOCKER=true ./build.sh
```

Или используйте отдельный скрипт для извлечения:

```bash
./extract-binaries.sh
```

### Docker Compose

Для извлечения бинарников через docker-compose:

```bash
docker-compose run --rm build
```

Это скопирует бинарники в папку `./build/`.

## Структура папок

После сборки:

```
.
├── build/              # Извлеченные бинарники
│   └── uringkv        # Основной исполняемый файл
├── target/            # Локальная сборка (если используется)
│   └── release/
│       └── uringkv
└── ...
```

## Запуск бинарника

### В WSL (из Windows)

```bash
wsl ./build/uringkv --help
```

### В Linux

```bash
./build/uringkv --help
```

### Примеры команд

```bash
# Инициализация хранилища
wsl ./build/uringkv init --path ./data

# Добавление ключа
wsl ./build/uringkv put mykey myvalue --path ./data

# Получение значения
wsl ./build/uringkv get mykey --path ./data

# Удаление ключа
wsl ./build/uringkv delete mykey --path ./data

# Сканирование диапазона
wsl ./build/uringkv scan key1 key9 --path ./data

# Бенчмарк (по умолчанию: 1M ключей, 70% чтение, 30% запись, 60 секунд)
wsl ./build/uringkv bench --path ./data

# Бенчмарк с параметрами
wsl ./build/uringkv bench --keys 10000 --read-pct 70 --write-pct 30 --duration 30 --path ./data
```

## Тестирование

### Запуск всех тестов

```batch
test-docker.bat
```

### Запуск конкретного теста

```batch
test-docker.bat test_name
```

### Запуск тестов с выводом

```batch
docker run --rm --privileged uringkv:latest cargo test --release -- --nocapture
```

## Автоматизация

Скрипт `build-docker.bat` автоматически:
- ✅ Устанавливает зависимости (liburing-dev)
- ✅ Компилирует проект в release режиме
- ✅ Извлекает бинарники в `./build/`
- ✅ Запускает тесты с правильными привилегиями
- ✅ Показывает размер и расположение бинарника

## Размер бинарника

Типичный размер скомпилированного бинарника: **~2.7 MB**

## Зависимости

Бинарник требует:
- Linux kernel с поддержкой io_uring (5.1+)
- liburing.so (устанавливается автоматически в Docker)

Для запуска в WSL убедитесь, что у вас WSL 2 с современным ядром Linux.

## Troubleshooting

### Ошибка "Permission denied"

Если бинарник не запускается:

```bash
chmod +x ./build/uringkv
```

### Ошибка "liburing.so not found"

В WSL установите liburing:

```bash
sudo apt-get update
sudo apt-get install liburing-dev
```

### Docker не найден

Убедитесь, что Docker \ Docker Desktop запущен и доступен из командной строки:

```batch
docker --version
```
