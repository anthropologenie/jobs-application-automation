#!/bin/bash
# Test script for SQL Practice Tracking System

echo "=========================================="
echo "  SQL Practice System - Integration Test"
echo "=========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test counter
PASSED=0
FAILED=0

# Test 1: Database table exists
echo -n "1. Checking if sql_practice_sessions table exists... "
if sqlite3 data/jobs-tracker.db "SELECT name FROM sqlite_master WHERE type='table' AND name='sql_practice_sessions';" | grep -q "sql_practice_sessions"; then
  echo -e "${GREEN}✓ PASS${NC}"
  ((PASSED++))
else
  echo -e "${RED}✗ FAIL${NC}"
  ((FAILED++))
fi

# Test 2: Views exist
echo -n "2. Checking if views exist... "
VIEWS=$(sqlite3 data/jobs-tracker.db "SELECT COUNT(*) FROM sqlite_master WHERE type='view' AND name IN ('sql_keyword_mastery', 'weekly_practice_summary', 'common_practice_mistakes', 'practice_progress_by_difficulty');")
if [ "$VIEWS" -eq "4" ]; then
  echo -e "${GREEN}✓ PASS${NC}"
  ((PASSED++))
else
  echo -e "${RED}✗ FAIL (found $VIEWS/4 views)${NC}"
  ((FAILED++))
fi

# Test 3: Sample data exists
echo -n "3. Checking if sample data was inserted... "
COUNT=$(sqlite3 data/jobs-tracker.db "SELECT COUNT(*) FROM sql_practice_sessions;")
if [ "$COUNT" -ge "1" ]; then
  echo -e "${GREEN}✓ PASS ($COUNT sessions)${NC}"
  ((PASSED++))
else
  echo -e "${RED}✗ FAIL (no data)${NC}"
  ((FAILED++))
fi

# Test 4: Keyword mastery view works
echo -n "4. Testing sql_keyword_mastery view... "
KEYWORDS=$(sqlite3 data/jobs-tracker.db "SELECT COUNT(*) FROM sql_keyword_mastery;")
if [ "$KEYWORDS" -ge "1" ]; then
  echo -e "${GREEN}✓ PASS ($KEYWORDS keywords)${NC}"
  ((PASSED++))
else
  echo -e "${RED}✗ FAIL${NC}"
  ((FAILED++))
fi

# Test 5: CLI tool exists and is executable
echo -n "5. Checking if log-sql-practice.py is executable... "
if [ -x "log-sql-practice.py" ]; then
  echo -e "${GREEN}✓ PASS${NC}"
  ((PASSED++))
else
  echo -e "${RED}✗ FAIL${NC}"
  ((FAILED++))
fi

# Test 6: Weekly summary script exists
echo -n "6. Checking if show-practice-summary.sh exists... "
if [ -x "show-practice-summary.sh" ]; then
  echo -e "${GREEN}✓ PASS${NC}"
  ((PASSED++))
else
  echo -e "${RED}✗ FAIL${NC}"
  ((FAILED++))
fi

# Test 7: Migration file exists
echo -n "7. Checking migration file... "
if [ -f "migrations/add-sql-practice-tracking.sql" ]; then
  echo -e "${GREEN}✓ PASS${NC}"
  ((PASSED++))
else
  echo -e "${RED}✗ FAIL${NC}"
  ((FAILED++))
fi

# Test 8: Weekly summary query exists
echo -n "8. Checking weekly summary query... "
if [ -f "queries/weekly-practice-summary.sql" ]; then
  echo -e "${GREEN}✓ PASS${NC}"
  ((PASSED++))
else
  echo -e "${RED}✗ FAIL${NC}"
  ((FAILED++))
fi

# Test 9: API server has new endpoints (check file content)
echo -n "9. Checking if API server has practice endpoints... "
if grep -q "sql-practice-stats" api-server.py; then
  echo -e "${GREEN}✓ PASS${NC}"
  ((PASSED++))
else
  echo -e "${RED}✗ FAIL${NC}"
  ((FAILED++))
fi

# Test 10: Dashboard has practice stats section
echo -n "10. Checking if dashboard has practice section... "
if grep -q "SQL Practice Stats" learning-dashboard.html; then
  echo -e "${GREEN}✓ PASS${NC}"
  ((PASSED++))
else
  echo -e "${RED}✗ FAIL${NC}"
  ((FAILED++))
fi

# Summary
echo ""
echo "=========================================="
echo "  Test Results"
echo "=========================================="
echo -e "${GREEN}Passed: $PASSED${NC}"
echo -e "${RED}Failed: $FAILED${NC}"
echo ""

if [ "$FAILED" -eq "0" ]; then
  echo -e "${GREEN}✓ All tests passed! System is ready to use.${NC}"
  echo ""
  echo "Next steps:"
  echo "  1. Start API server: python3 api-server.py"
  echo "  2. Open dashboard: http://localhost:8081/learning-dashboard.html"
  echo "  3. Log practice: ./log-sql-practice.py"
  echo "  4. View summary: ./show-practice-summary.sh"
  exit 0
else
  echo -e "${RED}✗ Some tests failed. Please review errors above.${NC}"
  exit 1
fi
