#!/bin/bash
set -e

SOCKET="/tmp/secmem-test-$(date +%s).sock"
echo "Using socket: $SOCKET"

# Start agent in background
echo "Starting agent..."
./build/secmem-agent --socket "$SOCKET" --allow-uid $(id -u) > /tmp/agent.log 2>&1 &
AGENT_PID=$!
echo "Agent PID: $AGENT_PID"

# Wait for agent to start
sleep 1

# Test PUT
echo ""
echo "Testing PUT..."
./build/secmemctl --socket "$SOCKET" put "test_secret=my_super_secret_password" --ttl 30s
echo "✓ PUT successful"

# Test GET
echo ""
echo "Testing GET..."
SECRET=$(./build/secmemctl --socket "$SOCKET" get test_secret)
echo "Retrieved secret: $SECRET"

if [ "$SECRET" = "my_super_secret_password" ]; then
    echo "✓ GET successful - secret matches!"
else
    echo "✗ GET failed - secret doesn't match"
    kill $AGENT_PID 2>/dev/null || true
    exit 1
fi

# Test GET non-existent key
echo ""
echo "Testing GET for non-existent key..."
RESULT=$(./build/secmemctl --socket "$SOCKET" get nonexistent 2>&1 || true)
echo "Result: $RESULT"

if echo "$RESULT" | grep -q "ERR no such key"; then
    echo "✓ Correctly returned error for non-existent key"
else
    echo "✗ Expected error message not found"
fi

# Cleanup
echo ""
echo "Cleaning up..."
kill $AGENT_PID 2>/dev/null || true
rm -f "$SOCKET"

echo ""
echo "All tests passed! ✓"
