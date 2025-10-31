#!/bin/bash

echo "🛑 Stopping Job Tracker System..."
echo ""

if [ -f "api-server.pid" ]; then
  PID=$(cat api-server.pid)
  if kill -0 $PID 2>/dev/null; then
    kill $PID
    echo "   ✅ API server stopped (PID: $PID)"
  fi
  rm api-server.pid
fi

if [ -f "dashboard/dashboard.pid" ]; then
  PID=$(cat dashboard/dashboard.pid)
  if kill -0 $PID 2>/dev/null; then
    kill $PID
    echo "   ✅ Dashboard stopped (PID: $PID)"
  fi
  rm dashboard/dashboard.pid
fi

echo ""
echo "✅ All services stopped"
