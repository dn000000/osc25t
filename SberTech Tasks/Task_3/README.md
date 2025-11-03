# secmem-agent

Прототип агента безопасного хранения секретов в RAM с AF_UNIX + SCM_RIGHTS, memfd + SEAL, AES-256-GCM, TTL, аутентификацией по SO_PEERCRED и аудитом.

Особенности:
- mlockall(MCL_CURRENT|MCL_FUTURE), zeroize буферов, FD_CLOEXEC
- Хранение шифртекста в запечатанных memfd (WRITE/SHRINK/GROW/SEAL)
- Дешифрация только при выдаче — в отдельный memfd, сразу перед передачей
- IPC: локальный AF_UNIX сокет, передача дескрипторов по SCM_RIGHTS
- Аутентификация клиентов через SO_PEERCRED (UID/GID)
- TTL: удаление секрета по таймеру, обнуление и закрытие memfd
- Аудит: логирование PUT/GET/TTL с UID/GID
- Полный запрет записи секретов на диск (используйте tmpfs: `/run` или `/dev/shm` для сокета)

## Быстрый старт

Требования: Linux (Docker подойдёт), Rust (в Docker)

### Сборка и тесты через Docker:

```bash
# Linux/macOS
./scripts/install_and_build.sh

# Windows
scripts\install_and_build.bat
```

Это соберёт образ и запустит unit+integration тесты.

### Сборка и извлечение бинарников:

```bash
# Linux/macOS
./scripts/build_and_extract.sh

# Windows
scripts\build_and_extract.bat
```

Это соберёт проект и извлечёт готовые бинарники в папку `build/`:
- `build/secmem-agent` - агент для хранения секретов
- `build/secmemctl` - CLI клиент для управления секретами

**Примечание:** Бинарники собраны для Linux и требуют Linux окружение (WSL на Windows или нативный Linux).

## Запуск вручную

После сборки бинарники находятся в папке `build/`. Для запуска в WSL (Windows) или Linux:

```bash
# Запуск агента (рекомендуется сокет на tmpfs: /dev/shm или /tmp)
./build/secmem-agent --socket /tmp/secmem.sock --allow-uid $(id -u)

# В другом терминале:

# Сохранить секрет на 10 минут
./build/secmemctl --socket /tmp/secmem.sock put db_password=supersecret --ttl 10m

# Получить секрет
./build/secmemctl --socket /tmp/secmem.sock get db_password

# Секрет будет выведен в stdout:
# supersecret
```

### Тестовые скрипты

Для быстрой проверки работоспособности в WSL:

```bash
# Базовый тест PUT/GET
wsl bash test_wsl.sh

# Тест TTL (истечение времени жизни секрета)
wsl bash test_ttl_wsl.sh
```

Политики доступа:
- Передавайте `--allow-uid` и/или `--allow-gid` для белых списков.
- По завершении TTL секрет недоступен к получению (GET), сервер удаляет запечатанный memfd.

Безопасность/ограничения:
- Ключ AES-256 генерируется при запуске, хранится в mlock-памяти, обнуляется при завершении.
- Плейнтекст существует только в заблокированных буферах на время шифрования/дешифрования и обнуляется (`zeroize`).
- memfd закрыты от наследования (CLOEXEC), защищены SEAL’ами; дескрипторы передаются только после аутентификации UID/GID.
- Логи идут в stderr/stdout; на диск не пишутся.

## Тесты

Интеграционные тесты запускают агент на `/dev/shm/secmem.sock`, проверяют put/get и истечение TTL.

## Замечания

- TTL относится к хранению на стороне сервера; клиент, получив секрет, сам отвечает за дальнейшую судьбу своего memfd.
- Для лучшей защиты процесса отключается `PR_SET_DUMPABLE` и включается `PR_SET_NO_NEW_PRIVS`.
- Убедитесь, что сокет расположен на tmpfs (`/run`, `/dev/shm`).