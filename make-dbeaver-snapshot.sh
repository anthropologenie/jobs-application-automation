#!/bin/bash

# Configuration
DB_SOURCE="./data/jobs-tracker.db"

# Try to find Windows user directory
if [ -d "/mnt/c/Users/$USER" ]; then
    WIN_USER="$USER"
elif [ -d "/mnt/c/Users/katte" ]; then
    WIN_USER="katte"
else
    # Find first non-system user
    WIN_USER=$(ls /mnt/c/Users/ | grep -v "Public\|Default\|All Users" | head -1)
fi

# Try Desktop first, fall back to Documents or home
if [ -d "/mnt/c/Users/$WIN_USER/Desktop" ]; then
    SNAPSHOT_DIR="/mnt/c/Users/$WIN_USER/Desktop"
elif [ -d "/mnt/c/Users/$WIN_USER/Documents" ]; then
    SNAPSHOT_DIR="/mnt/c/Users/$WIN_USER/Documents"
    echo "⚠️  Desktop not accessible, using Documents folder"
else
    # Fall back to project directory
    SNAPSHOT_DIR="./snapshots"
    mkdir -p "$SNAPSHOT_DIR"
    echo "⚠️  Windows folders not accessible, using local ./snapshots/"
fi

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
SNAPSHOT_NAME="jobs-tracker-inspect_${TIMESTAMP}.db"
SNAPSHOT_PATH="${SNAPSHOT_DIR}/${SNAPSHOT_NAME}"
LATEST_LINK="${SNAPSHOT_DIR}/jobs-tracker-latest.db"

echo "📸 Creating DBeaver-safe snapshot..."
echo "📂 Target: $SNAPSHOT_DIR"

# Ensure WAL mode for safe backups
sqlite3 "$DB_SOURCE" "PRAGMA journal_mode=WAL;" > /dev/null 2>&1

# Create snapshot using sqlite3 backup
sqlite3 "$DB_SOURCE" << SQL
.output /dev/null
.backup '${SNAPSHOT_PATH}'
SQL

# Check if backup was successful
if [ ! -f "$SNAPSHOT_PATH" ]; then
    echo "❌ Snapshot creation failed. Trying alternative method..."
    # Try direct copy as fallback
    cp "$DB_SOURCE" "$SNAPSHOT_PATH"
fi

# Create/update 'latest' symlink for convenience
rm -f "$LATEST_LINK" 2>/dev/null
cp "$SNAPSHOT_PATH" "$LATEST_LINK"

# Convert to Windows path
if [[ "$SNAPSHOT_DIR" == /mnt/c/* ]]; then
    WIN_PATH=$(echo "$LATEST_LINK" | sed 's|/mnt/c|C:|' | sed 's|/|\\|g')
else
    WIN_PATH=$(wslpath -w "$LATEST_LINK" 2>/dev/null || echo "$LATEST_LINK")
fi

echo "✅ Snapshot created successfully!"
echo ""
echo "📍 Open in DBeaver (Windows):"
echo "   $WIN_PATH"
echo ""
echo "📊 Database stats:"
sqlite3 "$SNAPSHOT_PATH" << SQL
SELECT 
  (SELECT COUNT(*) FROM opportunities) as opportunities,
  (SELECT COUNT(*) FROM interview_questions) as questions,
  (SELECT COUNT(*) FROM study_topics) as study_topics,
  (SELECT COUNT(*) FROM interactions) as interactions;
SQL

# Show latest questions
echo ""
echo "❓ Latest 3 questions:"
sqlite3 "$SNAPSHOT_PATH" << SQL
.mode column
.headers on
SELECT 
  substr(question_text, 1, 50) || '...' as question,
  question_type,
  difficulty,
  my_rating
FROM interview_questions 
ORDER BY created_at DESC 
LIMIT 3;
SQL

echo ""
echo "💡 TIP: Set DBeaver connection to READ-ONLY for safety"
echo ""
echo "🔗 Or use WSL path in DBeaver:"
echo "   \\\\wsl.localhost\\Ubuntu$(pwd)/snapshots/jobs-tracker-latest.db"
