#!/bin/bash
set -e

SOCKET="/tmp/secmem-ttl-test-$(date +%s).sock"
echo "Testing TTL functionality..."
echo "Using socket: $SOCKET"

# Start agent in background
echo ""
echo "Starting agent..."
./build/secmem-agent --socket "$SOCKET" --allow-uid $(id -u) > /tmp/agent-ttl.log 2>&1 &
AGENT_PID=$!
echo "Agent PID: $AGENT_PID"

# Wait for agent to start
sleep 1

# Test PUT with short TTL
echo ""
echo "Storing secret with 2 second TTL..."
./build/secmemctl --socket "$SOCKET" put "short_lived=temporary_data" --ttl 2s
echo "✓ Secret stored"

# Immediately retrieve it
echo ""
echo "Retrieving secret immediately..."
SECRET=$(./build/secmemctl --socket "$SOCKET" get short_lived)
echo "Retrieved: $SECRET"

if [ "$SECRET" = "temporary_data" ]; then
    echo "✓ Secret retrieved successfully"
else
    echo "✗ Failed to retrieve secret"
    kill $AGENT_PID 2>/dev/null || true
    exit 1
fi

# Wait for TTL to expire
echo ""
echo "Waiting 3 seconds for TTL to expire..."
sleep 3

# Try to retrieve expired secret
echo ""
echo "Attempting to retrieve expired secret..."
RESULT=$(./build/secmemctl --socket "$SOCKET" get short_lived 2>&1 || true)
echo "Result: $RESULT"

if echo "$RESULT" | grep -q "ERR no such key"; then
    echo "✓ Secret correctly expired and is no longer accessible"
else
    echo "✗ Secret should have expired but is still accessible"
    kill $AGENT_PID 2>/dev/null || true
    exit 1
fi

# Cleanup
echo ""
echo "Cleaning up..."
kill $AGENT_PID 2>/dev/null || true
rm -f "$SOCKET"

echo ""
echo "TTL test passed! ✓"
