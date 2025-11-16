#!/bin/bash

echo "╔════════════════════════════════════════════════════════╗"
echo "║     🚀 STARTING JOB TRACKER SYSTEM                     ║"
echo "╚════════════════════════════════════════════════════════╝"
echo ""

# ============================================================
# PHASE 1: Validate Project Structure
# ============================================================

echo "📂 Validating project structure..."

# Check for required directories
VALIDATION_FAILED=0

# Check docs/ folder
if [ ! -d "docs" ]; then
  echo "   ❌ Missing: docs/ folder"
  VALIDATION_FAILED=1
else
  echo "   ✅ docs/ folder exists"

  # Check for critical documentation files
  if [ ! -f "docs/INDEX.md" ]; then
    echo "      ⚠️  Warning: docs/INDEX.md not found"
  fi

  if [ ! -d "docs/guides" ]; then
    echo "      ⚠️  Warning: docs/guides/ subfolder not found"
  fi

  if [ ! -d "docs/reports" ]; then
    echo "      ⚠️  Warning: docs/reports/ subfolder not found"
  fi
fi

# Check tests/ folder
if [ ! -d "tests" ]; then
  echo "   ❌ Missing: tests/ folder"
  VALIDATION_FAILED=1
else
  echo "   ✅ tests/ folder exists"

  # Check for critical test scripts
  if [ ! -f "tests/test-complete-system.sh" ]; then
    echo "      ⚠️  Warning: tests/test-complete-system.sh not found"
  fi
fi

# Check data/ folder
if [ ! -d "data" ]; then
  echo "   ❌ Missing: data/ folder"
  VALIDATION_FAILED=1
else
  echo "   ✅ data/ folder exists"

  # Check for database
  if [ ! -f "data/jobs-tracker.db" ]; then
    echo "      ⚠️  Warning: data/jobs-tracker.db not found"
  fi
fi

# Check dashboard/ folder
if [ ! -d "dashboard" ]; then
  echo "   ❌ Missing: dashboard/ folder"
  VALIDATION_FAILED=1
else
  echo "   ✅ dashboard/ folder exists"
fi

# Check logs/ folder (create if missing)
if [ ! -d "logs" ]; then
  echo "   ⚠️  logs/ folder missing - creating..."
  mkdir -p logs
  echo "   ✅ logs/ folder created"
else
  echo "   ✅ logs/ folder exists"
fi

# Check core application files
if [ ! -f "api-server.py" ]; then
  echo "   ❌ Missing: api-server.py"
  VALIDATION_FAILED=1
else
  echo "   ✅ api-server.py exists"
fi

if [ ! -f "dashboard/server.py" ]; then
  echo "   ❌ Missing: dashboard/server.py"
  VALIDATION_FAILED=1
else
  echo "   ✅ dashboard/server.py exists"
fi

# Exit if validation failed
if [ $VALIDATION_FAILED -eq 1 ]; then
  echo ""
  echo "╔════════════════════════════════════════════════════════╗"
  echo "║     ❌ STRUCTURE VALIDATION FAILED                     ║"
  echo "╚════════════════════════════════════════════════════════╝"
  echo ""
  echo "Please ensure the project structure is correct."
  echo "Expected structure:"
  echo "  - docs/ (documentation)"
  echo "  - tests/ (test scripts)"
  echo "  - data/ (database)"
  echo "  - dashboard/ (frontend)"
  echo "  - api-server.py (backend)"
  echo ""
  exit 1
fi

echo "   ✅ All critical directories validated"
echo ""

# ============================================================
# PHASE 2: Start Services
# ============================================================

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
echo "📍 Access Points:"
echo "   🎨 Dashboard:  http://localhost:8082"
echo "   🔌 API Server: http://localhost:8081"
echo ""
echo "📚 Documentation:"
echo "   📖 Master Index:  file://$(pwd)/docs/INDEX.md"
echo "   📝 Quick Reference: file://$(pwd)/docs/guides/QUICK_REFERENCE.md"
echo "   🏗️  System Summary: file://$(pwd)/docs/SYSTEM_SUMMARY.md"
echo "   📋 Changelog: file://$(pwd)/CHANGELOG.md"
echo ""
echo "🧪 Quick Test:"
echo "   ./tests/test-complete-system.sh"
echo ""
echo "📂 Project Structure:"
echo "   ├── 📄 api-server.py          # REST API (20+ endpoints)"
echo "   ├── 🎨 dashboard/             # Frontend SPA"
echo "   ├── 🗄️  data/                 # SQLite database"
echo "   ├── 📚 docs/                  # Documentation"
echo "   │   ├── INDEX.md              # Master index"
echo "   │   ├── SYSTEM_SUMMARY.md     # Technical docs"
echo "   │   ├── guides/               # User guides"
echo "   │   └── reports/              # Implementation reports"
echo "   ├── 🧪 tests/                 # 8 test scripts"
echo "   └── 🤖 scrapers/              # Job scraping tools"
echo ""
echo "🛑 To Stop:"
echo "   ./stop-tracker.sh"
echo ""
echo "💡 Tip: Open docs/INDEX.md in your browser for complete navigation"
echo ""
