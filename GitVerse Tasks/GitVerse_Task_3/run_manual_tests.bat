@echo off
setlocal enabledelayedexpansion

echo ========================================
echo GitProc Manual Testing Script (Docker)
echo ========================================
echo.

set PASSED=0
set FAILED=0
set CONTAINER_NAME=gitproc-manual-test

:: Build and start container
echo [TEST] Building and starting Docker container...
docker-compose up -d --build >nul 2>&1
if %errorlevel% neq 0 (
    echo [FAIL] Failed to start Docker container
    set /a FAILED+=1
    goto :summary
)
echo [PASS] Container started successfully
set /a PASSED+=1

:: Wait for container to be ready
timeout /t 3 /nobreak >nul

:: Test 1: CLI help
echo.
echo [TEST] Testing CLI help command...
docker exec %CONTAINER_NAME% python -m gitproc.cli --help >nul 2>&1
if %errorlevel% neq 0 (
    echo [FAIL] CLI help command failed
    set /a FAILED+=1
) else (
    echo [PASS] CLI help command works
    set /a PASSED+=1
)

:: Test 2: Initialize GitProc
echo.
echo [TEST] Initializing GitProc...
docker exec %CONTAINER_NAME% python -m gitproc.cli init >nul 2>&1
if %errorlevel% neq 0 (
    echo [FAIL] GitProc initialization failed
    set /a FAILED+=1
) else (
    echo [PASS] GitProc initialized successfully
    set /a PASSED+=1
)

:: Test 3: Create test service file
echo.
echo [TEST] Creating test service file...
docker exec %CONTAINER_NAME% bash -c "{ echo '[Service]'; echo 'ExecStart=/etc/gitproc/services/test-script.sh'; echo 'Restart=always'; } > /etc/gitproc/services/test-service.service" >nul 2>&1
docker exec %CONTAINER_NAME% bash -c "printf '%%b\n' '\x23\x21/bin/bash' > /etc/gitproc/services/test-script.sh" >nul 2>&1
docker exec %CONTAINER_NAME% bash -c "echo 'while true; do' >> /etc/gitproc/services/test-script.sh" >nul 2>&1
docker exec %CONTAINER_NAME% bash -c "echo '  echo Service running at \$(date)' >> /etc/gitproc/services/test-script.sh" >nul 2>&1
docker exec %CONTAINER_NAME% bash -c "echo '  sleep 3' >> /etc/gitproc/services/test-script.sh" >nul 2>&1
docker exec %CONTAINER_NAME% bash -c "echo 'done' >> /etc/gitproc/services/test-script.sh" >nul 2>&1
docker exec %CONTAINER_NAME% chmod +x /etc/gitproc/services/test-script.sh >nul 2>&1

if %errorlevel% neq 0 (
    echo [FAIL] Failed to create test service
    set /a FAILED+=1
) else (
    echo [PASS] Test service created
    set /a PASSED+=1
)

:: Test 4: Commit service to Git
echo.
echo [TEST] Committing service to Git...
docker exec %CONTAINER_NAME% bash -c "cd /etc/gitproc/services && git config user.email 'test@test.com' && git config user.name 'Test' && git add . && git commit -m 'Add test service'" >nul 2>&1
if %errorlevel% neq 0 (
    echo [FAIL] Failed to commit service
    set /a FAILED+=1
) else (
    echo [PASS] Service committed to Git
    set /a PASSED+=1
)

:: Test 5: Start daemon
echo.
echo [TEST] Starting GitProc daemon...
docker exec -d %CONTAINER_NAME% python -m gitproc.cli daemon >nul 2>&1
timeout /t 3 /nobreak >nul

docker exec %CONTAINER_NAME% python -m gitproc.cli list >nul 2>&1
if %errorlevel% neq 0 (
    echo [FAIL] Daemon failed to start
    set /a FAILED+=1
) else (
    echo [PASS] Daemon started successfully
    set /a PASSED+=1
)

:: Test 6: Start service
echo.
echo [TEST] Starting test service...
docker exec %CONTAINER_NAME% python -m gitproc.cli start test-service >nul 2>&1
if %errorlevel% neq 0 (
    echo [FAIL] Failed to start service
    set /a FAILED+=1
) else (
    echo [PASS] Service started successfully
    set /a PASSED+=1
)

timeout /t 5 /nobreak >nul

:: Test 7: Check service status
echo.
echo [TEST] Checking service status...
docker exec %CONTAINER_NAME% python -m gitproc.cli status test-service | findstr "running" >nul 2>&1
if %errorlevel% neq 0 (
    echo [FAIL] Service is not running
    set /a FAILED+=1
) else (
    echo [PASS] Service is running
    set /a PASSED+=1
)

:: Test 8: Check service logs
echo.
echo [TEST] Checking service logs...
docker exec %CONTAINER_NAME% python -m gitproc.cli logs test-service --lines 5 | findstr "Service running" >nul 2>&1
if %errorlevel% neq 0 (
    echo [FAIL] Service logs not found
    set /a FAILED+=1
) else (
    echo [PASS] Service logs are working
    set /a PASSED+=1
)

:: Test 9: Restart service
echo.
echo [TEST] Restarting service...
docker exec %CONTAINER_NAME% python -m gitproc.cli restart test-service >nul 2>&1
timeout /t 3 /nobreak >nul
docker exec %CONTAINER_NAME% python -m gitproc.cli status test-service | findstr "running" >nul 2>&1
if %errorlevel% neq 0 (
    echo [FAIL] Service not running after restart
    set /a FAILED+=1
) else (
    echo [PASS] Service restarted successfully
    set /a PASSED+=1
)

:: Test 10: Update service and test rollback
echo.
echo [TEST] Testing Git rollback...
docker exec %CONTAINER_NAME% bash -c "printf '%%b\n' '\x23\x21/bin/bash' > /etc/gitproc/services/test-script.sh" >nul 2>&1
docker exec %CONTAINER_NAME% bash -c "echo 'while true; do' >> /etc/gitproc/services/test-script.sh" >nul 2>&1
docker exec %CONTAINER_NAME% bash -c "echo '  echo UPDATED Service running at \$(date)' >> /etc/gitproc/services/test-script.sh" >nul 2>&1
docker exec %CONTAINER_NAME% bash -c "echo '  sleep 3' >> /etc/gitproc/services/test-script.sh" >nul 2>&1
docker exec %CONTAINER_NAME% bash -c "echo 'done' >> /etc/gitproc/services/test-script.sh" >nul 2>&1
docker exec %CONTAINER_NAME% bash -c "cd /etc/gitproc/services && git add . && git commit -m Update" >nul 2>&1
docker exec %CONTAINER_NAME% python -m gitproc.cli restart test-service >nul 2>&1
timeout /t 5 /nobreak >nul

docker exec %CONTAINER_NAME% python -m gitproc.cli logs test-service --lines 3 | findstr "UPDATED" >nul 2>&1
if %errorlevel% neq 0 (
    echo [FAIL] Service update not detected
    set /a FAILED+=1
    goto :test11
)

for /f "tokens=1" %%i in ('docker exec %CONTAINER_NAME% bash -c "cd /etc/gitproc/services && git log --oneline | head -2 | tail -1"') do set PREV_COMMIT=%%i
docker exec %CONTAINER_NAME% python -m gitproc.cli rollback %PREV_COMMIT% >nul 2>&1
timeout /t 5 /nobreak >nul

docker exec %CONTAINER_NAME% python -m gitproc.cli logs test-service --lines 3 | findstr "UPDATED" >nul 2>&1
if %errorlevel% equ 0 (
    echo [FAIL] Rollback did not work
    set /a FAILED+=1
) else (
    echo [PASS] Rollback successful
    set /a PASSED+=1
)

:test11
:: Test 11: Stop service
echo.
echo [TEST] Stopping service...
docker exec %CONTAINER_NAME% python -m gitproc.cli stop test-service >nul 2>&1
if %errorlevel% neq 0 (
    echo [FAIL] Failed to stop service
    set /a FAILED+=1
) else (
    docker exec %CONTAINER_NAME% python -m gitproc.cli status test-service | findstr "stopped" >nul 2>&1
    if %errorlevel% neq 0 (
        echo [FAIL] Service still running after stop
        set /a FAILED+=1
    ) else (
        echo [PASS] Service stopped successfully
        set /a PASSED+=1
    )
)

:: Test 12: List services
echo.
echo [TEST] Listing all services...
docker exec %CONTAINER_NAME% python -m gitproc.cli list | findstr "test-service" >nul 2>&1
if %errorlevel% neq 0 (
    echo [FAIL] Service not listed
    set /a FAILED+=1
) else (
    echo [PASS] Service list working
    set /a PASSED+=1
)

:: Cleanup (no local files to delete)

:summary
echo.
echo ========================================
echo TEST SUMMARY
echo ========================================
echo Total Passed: %PASSED%
echo Total Failed: %FAILED%
echo ========================================

if %FAILED% equ 0 (
    echo Result: ALL TESTS PASSED
) else (
    echo Result: SOME TESTS FAILED
)

echo.
echo To clean up, run: docker-compose down -v

if %FAILED% equ 0 (
    exit /b 0
) else (
    exit /b 1
)
