#!/bin/bash

echo "╔════════════════════════════════════════════════════════╗"
echo "║     🚀 STARTING JOB TRACKER SYSTEM                     ║"
echo "╚════════════════════════════════════════════════════════╝"
echo ""

# Check if already running
if [ -f "api-server.pid" ] && kill -0 $(cat api-server.pid) 2>/dev/null; then
  echo "⚠️  API server already running (PID: $(cat api-server.pid))"
else
  echo "🔧 Starting API server..."
  python3 api-server.py > logs/api-server.log 2>&1 &
  echo $! > api-server.pid
  sleep 2
  if kill -0 $(cat api-server.pid) 2>/dev/null; then
    echo "   ✅ API server started (PID: $(cat api-server.pid))"
  else
    echo "   ❌ API server failed to start"
    cat logs/api-server.log
    exit 1
  fi
fi

if [ -f "dashboard/dashboard.pid" ] && kill -0 $(cat dashboard/dashboard.pid) 2>/dev/null; then
  echo "⚠️  Dashboard already running (PID: $(cat dashboard/dashboard.pid))"
else
  echo "🎨 Starting dashboard..."
  cd dashboard
  python3 server.py > ../logs/dashboard.log 2>&1 &
  echo $! > dashboard.pid
  cd ..
  sleep 2
  if kill -0 $(cat dashboard/dashboard.pid) 2>/dev/null; then
    echo "   ✅ Dashboard started (PID: $(cat dashboard/dashboard.pid))"
  else
    echo "   ❌ Dashboard failed to start"
    cat logs/dashboard.log
    exit 1
  fi
fi

echo ""
echo "╔════════════════════════════════════════════════════════╗"
echo "║     ✅ JOB TRACKER SYSTEM RUNNING                      ║"
echo "╚════════════════════════════════════════════════════════╝"
echo ""
echo "📍 Access your tracker:"
echo "   Dashboard:  http://localhost:8082"
echo "   API Server: http://localhost:8081"
echo ""
echo "🛑 To stop:"
echo "   ./stop-tracker.sh"
echo ""
