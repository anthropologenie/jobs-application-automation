#!/bin/bash
# Migration runner for Parliament decisions table
#
# This script applies the parliament_decisions table migration to enable
# DIRECTION 2 (Training): Track Parliament advice → Real outcomes → Calibration
#
# Usage:
#   ./scripts/apply_parliament_migration.sh
#
# What it does:
#   1. Checks if database exists
#   2. Applies 004_add_parliament_decisions.sql migration
#   3. Verifies table was created successfully

set -e  # Exit on any error

DB_PATH="data/jobs-tracker.db"
MIGRATION="migrations/004_add_parliament_decisions.sql"

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Parliament Decisions Migration${NC}"
echo "================================"
echo ""

# Check if database exists
if [ ! -f "$DB_PATH" ]; then
    echo -e "${RED}Error: Database not found at $DB_PATH${NC}"
    echo "Please ensure jobs-tracker.db exists before running this migration."
    exit 1
fi

echo -e "${GREEN}✓${NC} Database found at $DB_PATH"

# Check if migration file exists
if [ ! -f "$MIGRATION" ]; then
    echo -e "${RED}Error: Migration file not found at $MIGRATION${NC}"
    exit 1
fi

echo -e "${GREEN}✓${NC} Migration file found at $MIGRATION"
echo ""

# Check if table already exists
TABLE_EXISTS=$(sqlite3 "$DB_PATH" "SELECT name FROM sqlite_master WHERE type='table' AND name='parliament_decisions';" 2>/dev/null || echo "")

if [ -n "$TABLE_EXISTS" ]; then
    echo -e "${YELLOW}⚠${NC}  Table 'parliament_decisions' already exists"
    echo "   Migration may have been applied previously."
    echo ""
    read -p "Do you want to re-apply the migration? (y/N): " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Migration cancelled."
        exit 0
    fi
fi

# Apply migration
echo "Applying Parliament decisions table migration..."
sqlite3 "$DB_PATH" < "$MIGRATION"

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Migration applied successfully${NC}"
    echo ""

    # Verify table was created
    TABLE_CHECK=$(sqlite3 "$DB_PATH" "SELECT name FROM sqlite_master WHERE type='table' AND name='parliament_decisions';" 2>/dev/null || echo "")

    if [ -n "$TABLE_CHECK" ]; then
        echo -e "${GREEN}✓${NC} Table 'parliament_decisions' verified"

        # Show table schema
        echo ""
        echo "Table schema:"
        echo "-------------"
        sqlite3 "$DB_PATH" ".schema parliament_decisions"

        echo ""
        echo -e "${GREEN}✓${NC} Migration complete!"
        echo ""
        echo "You can now:"
        echo "  1. Log Parliament decisions with jobs_db.log_parliament_decision(trace, job_id)"
        echo "  2. Update outcomes with jobs_db.update_decision_outcome(log_id, outcome)"
        echo "  3. Analyze accuracy with jobs_db.get_decision_accuracy_stats()"
        echo ""
    else
        echo -e "${RED}✗${NC} Error: Table was not created"
        exit 1
    fi
else
    echo -e "${RED}❌ Migration failed${NC}"
    exit 1
fi
