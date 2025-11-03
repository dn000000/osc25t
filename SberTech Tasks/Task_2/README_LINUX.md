# uringKV - Быстрый старт для Linux

## Использование готового бинарника

### 1. Инициализация хранилища

```bash
./uringkv init --path /data
```

Это создаст:
- `/data/config.json` - конфигурация
- `/data/wal/` - директория для WAL файлов
- `/data/sst/` - директория для SST файлов

### 2. Базовые операции

```bash
# Добавить данные
./uringkv put mykey myvalue --path /data

# Получить данные
./uringkv get mykey --path /data

# Удалить данные
./uringkv delete mykey --path /data

# Сканировать диапазон
./uringkv scan key1 key9 --path /data
```

### 3. Запуск бенчмарка

```bash
# Маленький тест (100 ключей, 5 секунд)
./uringkv bench --keys 100 --duration 5 --path /data

# Средний тест (10,000 ключей, 30 секунд)
./uringkv bench --keys 10000 --duration 30 --path /data

# Полный тест (1,000,000 ключей, 60 секунд) - требует времени!
./uringkv bench --path /data
```

**Важно**: Бенчмарк сначала заполняет базу данными, что может занять время:
- 100 ключей: ~1 секунда
- 10,000 ключей: ~10 секунд
- 1,000,000 ключей: ~10-15 минут

## Решение проблемы из вашего примера

Вы столкнулись с этой проблемой:

```bash
root@DW-PC:/home/dd/uring# ./uringkv init --path /data/
# Успешно

root@DW-PC:/home/dd/uring# ./uringkv bench
# Ошибка: Configuration file not found at ./data/config.json
```

**Решение**: Нужно указать тот же путь, что и при инициализации:

```bash
# Правильно:
./uringkv init --path /data
./uringkv bench --path /data

# Или используйте путь по умолчанию:
./uringkv init --path ./data
./uringkv bench  # Использует ./data по умолчанию
```

## Параметры команд

### init
```bash
./uringkv init --path <PATH> [OPTIONS]

Опции:
  --queue-depth <N>     Глубина очереди io_uring (по умолчанию: 256)
  --segment-size <MB>   Размер сегмента WAL в MB (по умолчанию: 128)
  --enable-sqpoll       Включить SQPOLL режим
```

### bench
```bash
./uringkv bench [OPTIONS] --path <PATH>

Опции:
  --keys <N>           Количество ключей (по умолчанию: 1000000)
  --read-pct <N>       Процент чтения 0-100 (по умолчанию: 70)
  --write-pct <N>      Процент записи 0-100 (по умолчанию: 30)
  --duration <SEC>     Длительность в секундах (по умолчанию: 60)
```

**Важно**: `read-pct + write-pct` должно равняться 100!

## Требования

- Linux kernel 5.1+ (поддержка io_uring)
- liburing установлен:
  ```bash
  sudo apt-get install liburing-dev  # Debian/Ubuntu
  sudo yum install liburing-devel    # RHEL/CentOS
  ```

## Ограничения

- Максимальный размер ключа: 64 KB
- Максимальный размер значения: 1 MB
- Эти ограничения защищают от ошибок при чтении поврежденных данных

## Производительность

Типичная производительность на современном SSD:
- Запись: ~50,000-100,000 ops/sec
- Чтение: ~100,000-200,000 ops/sec
- Смешанная нагрузка (70/30): ~80,000-150,000 ops/sec

## Примеры использования

### Простой key-value store

```bash
# Инициализация
./uringkv init --path /var/lib/myapp

# Сохранение конфигурации
./uringkv put config:db_host "localhost" --path /var/lib/myapp
./uringkv put config:db_port "5432" --path /var/lib/myapp

# Чтение конфигурации
./uringkv get config:db_host --path /var/lib/myapp
```

### Кэш для веб-приложения

```bash
# Инициализация
./uringkv init --path /tmp/cache

# Сохранение кэша
./uringkv put "user:123:profile" '{"name":"John","age":30}' --path /tmp/cache

# Чтение кэша
./uringkv get "user:123:profile" --path /tmp/cache
```

### Тестирование производительности

```bash
# Быстрый тест
./uringkv init --path /tmp/perftest
./uringkv bench --keys 1000 --duration 10 --path /tmp/perftest

# Тест с большой нагрузкой на запись
./uringkv bench --keys 50000 --read-pct 30 --write-pct 70 --duration 30 --path /tmp/perftest

# Тест только на чтение
./uringkv bench --keys 50000 --read-pct 100 --write-pct 0 --duration 30 --path /tmp/perftest
```

## Troubleshooting

### Ошибка: "Operation not permitted"

Если вы видите ошибку при использовании io_uring:

```bash
# Попробуйте с sudo
sudo ./uringkv bench --path /data

# Или запустите в Docker с privileged режимом
docker run --rm --privileged -v /data:/data uringkv:latest ./uringkv bench --path /data
```

### Ошибка: "capacity overflow"

Эта ошибка была исправлена в последней версии. Убедитесь, что используете актуальный бинарник.

### Медленная работа

Если операции выполняются медленно:
1. Убедитесь, что используете SSD, а не HDD
2. Проверьте, что путь данных не на сетевом диске
3. Увеличьте `--queue-depth` при инициализации
4. Включите `--enable-sqpoll` для меньшей задержки

## Дополнительная информация

- [USAGE_EXAMPLES.md](USAGE_EXAMPLES.md) - Подробные примеры
- [BUILD_AND_DEPLOYMENT.md](BUILD_AND_DEPLOYMENT.md) - Сборка из исходников
- [TASK_13_SUMMARY.md](TASK_13_SUMMARY.md) - Технические детали
