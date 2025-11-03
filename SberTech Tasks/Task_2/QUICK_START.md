# Быстрый старт - uringKV

## Сборка проекта 

```batch
build-docker.bat \ build.sh
```

Бинарник будет в папке `build/uringkv`

## Запуск

```bash
# Инициализация
wsl ./build/uringkv init --path ./mydata

# Добавить данные
wsl ./build/uringkv put hello world --path ./mydata

# Получить данные
wsl ./build/uringkv get hello --path ./mydata

# Удалить данные
wsl ./build/uringkv delete hello --path ./mydata

# Сканирование диапазона
wsl ./build/uringkv scan key1 key9 --path ./mydata

# Бенчмарк
wsl ./build/uringkv bench --keys 10000 --path ./mydata
```

## Тестирование

```batch
test-docker.bat \ build.sh
```

## Подробности

- [BUILD_AND_DEPLOYMENT.md](BUILD_AND_DEPLOYMENT.md) - Полная документация по сборке
- [BINARY_EXTRACTION.md](BINARY_EXTRACTION.md) - Извлечение бинарников из Docker
