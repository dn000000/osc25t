#!/bin/bash

echo "========================================"
echo "GitProc Manual Testing Script (Docker)"
echo "========================================"
echo ""

PASSED=0
FAILED=0
CONTAINER_NAME="gitproc-manual-test"

# Build and start container
echo "[TEST] Building and starting Docker container..."
if docker-compose up -d --build > /dev/null 2>&1; then
    echo "[PASS] Container started successfully"
    ((PASSED++))
else
    echo "[FAIL] Failed to start Docker container"
    ((FAILED++))
    exit 1
fi

# Wait for container to be ready
sleep 3

# Test 1: CLI help
echo ""
echo "[TEST] Testing CLI help command..."
if docker exec $CONTAINER_NAME python -m gitproc.cli --help > /dev/null 2>&1; then
    echo "[PASS] CLI help command works"
    ((PASSED++))
else
    echo "[FAIL] CLI help command failed"
    ((FAILED++))
fi

# Test 2: Initialize GitProc
echo ""
echo "[TEST] Initializing GitProc..."
if docker exec $CONTAINER_NAME python -m gitproc.cli init > /dev/null 2>&1; then
    echo "[PASS] GitProc initialized successfully"
    ((PASSED++))
else
    echo "[FAIL] GitProc initialization failed"
    ((FAILED++))
fi

# Test 3: Create test service file
echo ""
echo "[TEST] Creating test service file..."
cat > test-service.service << 'EOF'
[Service]
ExecStart=/etc/gitproc/services/test-script.sh
Restart=always
EOF

cat > test-script.sh << 'EOF'
#!/bin/bash
while true; do
  echo "Service running at $(date)"
  sleep 3
done
EOF

if docker cp test-service.service $CONTAINER_NAME:/etc/gitproc/services/test-service.service > /dev/null 2>&1 && \
   docker cp test-script.sh $CONTAINER_NAME:/etc/gitproc/services/test-script.sh > /dev/null 2>&1 && \
   docker exec $CONTAINER_NAME chmod +x /etc/gitproc/services/test-script.sh > /dev/null 2>&1; then
    echo "[PASS] Test service created"
    ((PASSED++))
else
    echo "[FAIL] Failed to create test service"
    ((FAILED++))
fi

# Test 4: Commit service to Git
echo ""
echo "[TEST] Committing service to Git..."
if docker exec $CONTAINER_NAME bash -c "cd /etc/gitproc/services && git config user.email 'test@test.com' && git config user.name 'Test' && git add . && git commit -m 'Add test service'" > /dev/null 2>&1; then
    echo "[PASS] Service committed to Git"
    ((PASSED++))
else
    echo "[FAIL] Failed to commit service"
    ((FAILED++))
fi

# Test 5: Start daemon
echo ""
echo "[TEST] Starting GitProc daemon..."
docker exec -d $CONTAINER_NAME python -m gitproc.cli daemon > /dev/null 2>&1
sleep 3

if docker exec $CONTAINER_NAME python -m gitproc.cli list > /dev/null 2>&1; then
    echo "[PASS] Daemon started successfully"
    ((PASSED++))
else
    echo "[FAIL] Daemon failed to start"
    ((FAILED++))
fi

# Test 6: Start service
echo ""
echo "[TEST] Starting test service..."
if docker exec $CONTAINER_NAME python -m gitproc.cli start test-service > /dev/null 2>&1; then
    echo "[PASS] Service started successfully"
    ((PASSED++))
else
    echo "[FAIL] Failed to start service"
    ((FAILED++))
fi

sleep 5

# Test 7: Check service status
echo ""
echo "[TEST] Checking service status..."
if docker exec $CONTAINER_NAME python -m gitproc.cli status test-service 2>&1 | grep -q "running"; then
    echo "[PASS] Service is running"
    ((PASSED++))
else
    echo "[FAIL] Service is not running"
    ((FAILED++))
fi

# Test 8: Check service logs
echo ""
echo "[TEST] Checking service logs..."
if docker exec $CONTAINER_NAME python -m gitproc.cli logs test-service --lines 5 2>&1 | grep -q "Service running"; then
    echo "[PASS] Service logs are working"
    ((PASSED++))
else
    echo "[FAIL] Service logs not found"
    ((FAILED++))
fi

# Test 9: Restart service
echo ""
echo "[TEST] Restarting service..."
docker exec $CONTAINER_NAME python -m gitproc.cli restart test-service > /dev/null 2>&1
sleep 3
if docker exec $CONTAINER_NAME python -m gitproc.cli status test-service 2>&1 | grep -q "running"; then
    echo "[PASS] Service restarted successfully"
    ((PASSED++))
else
    echo "[FAIL] Service not running after restart"
    ((FAILED++))
fi

# Test 10: Update service and test rollback
echo ""
echo "[TEST] Testing Git rollback..."

# Create updated script directly in container to avoid file copy issues
docker exec $CONTAINER_NAME bash -c 'cat > /etc/gitproc/services/test-script.sh << "EOFSCRIPT"
#!/bin/bash
while true; do
  echo "UPDATED Service running at $(date)"
  sleep 3
done
EOFSCRIPT
' > /dev/null 2>&1

docker exec $CONTAINER_NAME bash -c "cd /etc/gitproc/services && git add . && git commit -m 'Update service'" > /dev/null 2>&1
docker exec $CONTAINER_NAME python -m gitproc.cli restart test-service > /dev/null 2>&1
sleep 5

if docker exec $CONTAINER_NAME python -m gitproc.cli logs test-service --lines 5 2>&1 | grep -q "UPDATED"; then
    PREV_COMMIT=$(docker exec $CONTAINER_NAME bash -c "cd /etc/gitproc/services && git log --oneline | head -2 | tail -1 | cut -d' ' -f1")
    docker exec $CONTAINER_NAME python -m gitproc.cli rollback $PREV_COMMIT > /dev/null 2>&1
    sleep 8
    
    # Check the actual script file content after rollback, not old logs
    if docker exec $CONTAINER_NAME cat /etc/gitproc/services/test-script.sh 2>&1 | grep -q "UPDATED"; then
        echo "[FAIL] Rollback did not work"
        ((FAILED++))
    else
        echo "[PASS] Rollback successful"
        ((PASSED++))
    fi
else
    echo "[FAIL] Service update not detected"
    ((FAILED++))
fi

# Test 11: Stop service
echo ""
echo "[TEST] Stopping service..."
if docker exec $CONTAINER_NAME python -m gitproc.cli stop test-service > /dev/null 2>&1; then
    if docker exec $CONTAINER_NAME python -m gitproc.cli status test-service 2>&1 | grep -q "stopped"; then
        echo "[PASS] Service stopped successfully"
        ((PASSED++))
    else
        echo "[FAIL] Service still running after stop"
        ((FAILED++))
    fi
else
    echo "[FAIL] Failed to stop service"
    ((FAILED++))
fi

# Test 12: List services
echo ""
echo "[TEST] Listing all services..."
if docker exec $CONTAINER_NAME python -m gitproc.cli list 2>&1 | grep -q "test-service"; then
    echo "[PASS] Service list working"
    ((PASSED++))
else
    echo "[FAIL] Service not listed"
    ((FAILED++))
fi

# Cleanup
rm -f test-service.service test-script.sh

echo ""
echo "========================================"
echo "TEST SUMMARY"
echo "========================================"
echo "Total Passed: $PASSED"
echo "Total Failed: $FAILED"
echo "========================================"

if [ $FAILED -eq 0 ]; then
    echo "Result: ALL TESTS PASSED"
else
    echo "Result: SOME TESTS FAILED"
fi

echo ""
echo "To clean up, run: docker-compose down -v"

if [ $FAILED -eq 0 ]; then
    exit 0
else
    exit 1
fi
