# Примеры использования uringKV

## Базовые операции

### Инициализация хранилища

```bash
# Linux
./uringkv init --path /data

# Windows (WSL)
wsl ./build/uringkv init --path /data
```

Параметры:
- `--path` - путь к директории данных (обязательный)
- `--queue-depth` - глубина очереди io_uring (по умолчанию: 256)
- `--segment-size` - размер сегмента WAL в MB (по умолчанию: 128)
- `--enable-sqpoll` - включить SQPOLL режим для io_uring (по умолчанию: false)

### Добавление данных (PUT)

```bash
# Простой пример
./uringkv put mykey myvalue --path /data

# С указанием пути
./uringkv put hello world --path /data

# Примечание: если путь не указан, используется ./data по умолчанию
./uringkv put test value
```

### Получение данных (GET)

```bash
# Получить значение по ключу
./uringkv get mykey --path /data

# Если ключ не найден, выведет: "Key not found: mykey"
./uringkv get nonexistent --path /data
```

### Удаление данных (DELETE)

```bash
# Удалить ключ
./uringkv delete mykey --path /data
```

### Сканирование диапазона (SCAN)

```bash
# Сканировать ключи от key1 до key9 (key9 не включается)
./uringkv scan key1 key9 --path /data

# Сканировать все ключи с префиксом "user_"
./uringkv scan user_ user_zzzz --path /data
```

## Бенчмарк

### Базовый бенчмарк

```bash
# Запустить с параметрами по умолчанию:
# - 1,000,000 ключей
# - 70% операций чтения
# - 30% операций записи
# - 60 секунд
./uringkv bench --path /data
```

### Настраиваемый бенчмарк

```bash
# Небольшой быстрый тест
./uringkv bench --keys 10000 --read-pct 70 --write-pct 30 --duration 10 --path /data

# Тест с большой нагрузкой на запись
./uringkv bench --keys 1000000 --read-pct 30 --write-pct 70 --duration 60 --path /data

# Тест только на чтение
./uringkv bench --keys 100000 --read-pct 100 --write-pct 0 --duration 30 --path /data
```

Параметры бенчмарка:
- `--keys` - количество ключей для тестирования
- `--read-pct` - процент операций чтения (0-100)
- `--write-pct` - процент операций записи (0-100)
- `--duration` - длительность теста в секундах
- `--path` - путь к данным

**Важно**: `read-pct + write-pct` должно равняться 100!

## Полный пример сценария

```bash
# 1. Инициализация
./uringkv init --path /tmp/mydb

# 2. Добавление данных
./uringkv put user:1 "John Doe" --path /tmp/mydb
./uringkv put user:2 "Jane Smith" --path /tmp/mydb
./uringkv put user:3 "Bob Johnson" --path /tmp/mydb
./uringkv put config:timeout "30" --path /tmp/mydb
./uringkv put config:retries "3" --path /tmp/mydb

# 3. Чтение данных
./uringkv get user:1 --path /tmp/mydb
# Вывод: John Doe

# 4. Сканирование пользователей
./uringkv scan user: user:zzzz --path /tmp/mydb
# Вывод:
# Found 3 entries:
#   user:1 = John Doe
#   user:2 = Jane Smith
#   user:3 = Bob Johnson

# 5. Сканирование конфигурации
./uringkv scan config: config:zzzz --path /tmp/mydb
# Вывод:
# Found 2 entries:
#   config:retries = 3
#   config:timeout = 30

# 6. Удаление
./uringkv delete user:2 --path /tmp/mydb

# 7. Проверка удаления
./uringkv get user:2 --path /tmp/mydb
# Вывод: Key not found: user:2

# 8. Бенчмарк
./uringkv bench --keys 50000 --duration 30 --path /tmp/mydb
```

## Использование с разными путями

```bash
# Разработка
./uringkv init --path ./dev-data
./uringkv put test value --path ./dev-data

# Тестирование
./uringkv init --path ./test-data
./uringkv put test value --path ./test-data

# Продакшн
./uringkv init --path /var/lib/uringkv
./uringkv put test value --path /var/lib/uringkv
```

## Просмотр справки

```bash
# Общая справка
./uringkv --help

# Справка по конкретной команде
./uringkv init --help
./uringkv put --help
./uringkv bench --help
```

## Решение проблем

### Ошибка: "Configuration file not found"

```bash
# Проблема: вы не инициализировали хранилище
./uringkv get mykey --path /data
# Error: Configuration file not found at /data/config.json

# Решение: сначала инициализируйте
./uringkv init --path /data
```

### Ошибка: "Operation not permitted" (io_uring)

```bash
# Проблема: недостаточно прав для io_uring
# Решение: запустите с sudo или в Docker с privileged режимом

sudo ./uringkv bench --path /data
```

### Ошибка: "Read and write percentages must sum to 100"

```bash
# Проблема: неправильные проценты
./uringkv bench --read-pct 60 --write-pct 30 --path /data
# Error: Read and write percentages must sum to 100 (got 90)

# Решение: убедитесь, что сумма равна 100
./uringkv bench --read-pct 60 --write-pct 40 --path /data
```
