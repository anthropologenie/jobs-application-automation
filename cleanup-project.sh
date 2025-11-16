#!/bin/bash

echo "╔════════════════════════════════════════════════════════╗"
echo "║     🧹 PROJECT CLEANUP & REORGANIZATION                ║"
echo "╚════════════════════════════════════════════════════════╝"
echo ""

# Backup current state
echo "📦 Creating backup of current state..."
BACKUP_DIR="backup-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BACKUP_DIR"
cp -r . "$BACKUP_DIR/" 2>/dev/null
echo "   ✅ Backup created: $BACKUP_DIR"
echo ""

# Create new directory structure
echo "📁 Creating new directory structure..."
mkdir -p docs/reports docs/guides tests
echo "   ✅ Created: docs/reports, docs/guides, tests"
echo ""

# Move documentation
echo "📄 Organizing documentation..."
mv TEST_REPORT.md docs/reports/ 2>/dev/null && echo "   ✅ Moved TEST_REPORT.md"
mv SESSION_CHANGES_SUMMARY.md docs/reports/ 2>/dev/null && echo "   ✅ Moved SESSION_CHANGES_SUMMARY.md"
mv NEW_FEATURES_REPORT.md docs/reports/ 2>/dev/null && echo "   ✅ Moved NEW_FEATURES_REPORT.md"
mv SCORER_IMPLEMENTATION_SUMMARY.md docs/reports/ 2>/dev/null && echo "   ✅ Moved SCORER_IMPLEMENTATION_SUMMARY.md"
mv QUICK_REFERENCE.md docs/guides/ 2>/dev/null && echo "   ✅ Moved QUICK_REFERENCE.md"
mv SQL_PRACTICE_GUIDE.md docs/guides/ 2>/dev/null && echo "   ✅ Moved SQL_PRACTICE_GUIDE.md"
mv SYSTEM_SUMMARY.md docs/ 2>/dev/null && echo "   ✅ Moved SYSTEM_SUMMARY.md"
echo ""

# Move test scripts
echo "🧪 Organizing test scripts..."
mv test-complete-system.sh tests/ 2>/dev/null && echo "   ✅ Moved test-complete-system.sh"
mv test-new-features.sh tests/ 2>/dev/null && echo "   ✅ Moved test-new-features.sh"
mv test-new-pipeline-features.sh tests/ 2>/dev/null && echo "   ✅ Moved test-new-pipeline-features.sh"
mv test-scraped-jobs-api.sh tests/ 2>/dev/null && echo "   ✅ Moved test-scraped-jobs-api.sh"
mv test-sql-practice-system.sh tests/ 2>/dev/null && echo "   ✅ Moved test-sql-practice-system.sh"
mv final-validation-tests.sh tests/ 2>/dev/null && echo "   ✅ Moved final-validation-tests.sh"
mv validate-system.sh tests/ 2>/dev/null && echo "   ✅ Moved validate-system.sh"
mv show-practice-summary.sh tests/ 2>/dev/null && echo "   ✅ Moved show-practice-summary.sh"
echo ""

# Remove backups and redundant files
echo "🗑️  Removing backups and redundant files..."
rm -f api-server.py.backup && echo "   ✅ Removed api-server.py.backup"
rm -f api-server.py.backup2 && echo "   ✅ Removed api-server.py.backup2"
rm -f docker-compose.yml.backup && echo "   ✅ Removed docker-compose.yml.backup"
rm -f data/jobs-tracker.db.backup-broken && echo "   ✅ Removed db backup (broken)"
rm -f data/jobs-tracker.db.pre-migration && echo "   ✅ Removed db backup (pre-migration)"
rm -f test-results.log && echo "   ✅ Removed test-results.log"
echo ""

# Remove process files
echo "🔧 Removing process-specific files..."
rm -f api-server.pid && echo "   ✅ Removed api-server.pid"
rm -f dashboard/dashboard.pid && echo "   ✅ Removed dashboard/dashboard.pid"
echo ""

# Remove Python cache
echo "🐍 Removing Python cache..."
rm -rf __pycache__ && echo "   ✅ Removed __pycache__"
rm -rf dashboard/__pycache__ && echo "   ✅ Removed dashboard/__pycache__"
echo ""

# Create .gitignore
echo "📝 Creating .gitignore..."
cat > .gitignore << 'EOF'
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
env/
venv/
*.egg-info/

# Process IDs
*.pid

# Logs
logs/*.log
daily-logs/*.log

# Database WAL files (SQLite temp files)
*.db-shm
*.db-wal

# Backups
*.backup*
*.pre-migration
backup-*/

# IDE
.vscode/
.idea/
*.swp
*.swo
*.sublime-*

# OS
.DS_Store
Thumbs.db
.AppleDouble
.LSOverride

# Test results
test-results.log

# Environment
.env
.env.local
EOF
echo "   ✅ Created .gitignore"
echo ""

# Make test scripts executable
echo "⚙️  Making test scripts executable..."
chmod +x tests/*.sh 2>/dev/null
chmod +x start-tracker.sh stop-tracker.sh 2>/dev/null
echo "   ✅ Scripts are now executable"
echo ""

# Summary
echo "╔════════════════════════════════════════════════════════╗"
echo "║     ✅ CLEANUP COMPLETE                                ║"
echo "╚════════════════════════════════════════════════════════╝"
echo ""
echo "📊 New Project Structure:"
echo "   docs/"
echo "   ├── reports/              (4 files)"
echo "   ├── guides/               (2 files)"
echo "   └── SYSTEM_SUMMARY.md"
echo ""
echo "   tests/                    (8 test scripts)"
echo ""
echo "🗑️  Removed:"
echo "   • 3 backup files"
echo "   • 2 PID files"
echo "   • Python cache directories"
echo "   • Test result logs"
echo ""
echo "📋 Next Steps:"
echo "   1. Run: git status"
echo "   2. Review changes"
echo "   3. Run Claude Code to update documentation"
echo "   4. Test system end-to-end"
echo "   5. Commit to git"
echo ""
