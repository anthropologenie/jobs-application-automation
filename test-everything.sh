#!/bin/bash

echo "╔════════════════════════════════════════════════════════╗"
echo "║     🧪 END-TO-END SYSTEM VALIDATION                    ║"
echo "╚════════════════════════════════════════════════════════╝"
echo ""

# Test 1: Project Structure
echo "1️⃣  Verifying Project Structure..."
for dir in docs docs/reports docs/guides tests data dashboard workflows; do
  if [ -d "$dir" ]; then
    echo "   ✅ $dir exists"
  else
    echo "   ❌ $dir missing"
    exit 1
  fi
done
echo ""

# Test 2: Documentation Files
echo "2️⃣  Verifying Documentation..."
docs=(
  "README.md"
  "CHANGELOG.md"
  "docs/INDEX.md"
  "docs/SYSTEM_SUMMARY.md"
  "docs/guides/QUICK_REFERENCE.md"
  "docs/guides/TESTING.md"
)
for doc in "${docs[@]}"; do
  if [ -f "$doc" ]; then
    echo "   ✅ $doc exists"
  else
    echo "   ❌ $doc missing"
  fi
done
echo ""

# Test 3: Test Scripts
echo "3️⃣  Verifying Test Scripts..."
if [ -x "tests/test-complete-system.sh" ]; then
  echo "   ✅ Running complete system test..."
  ./tests/test-complete-system.sh
else
  echo "   ❌ test-complete-system.sh not executable"
  exit 1
fi
echo ""

# Test 4: API Endpoints
echo "4️⃣  Testing All API Endpoints..."
endpoints=(
  "metrics"
  "pipeline"
  "archived-pipeline"
  "todays-agenda"
  "sources"
  "sacred-work-stats"
)
for endpoint in "${endpoints[@]}"; do
  if curl -s "http://localhost:8081/api/$endpoint" > /dev/null 2>&1; then
    echo "   ✅ /api/$endpoint responding"
  else
    echo "   ❌ /api/$endpoint failed"
  fi
done
echo ""

# Test 5: UI Features (Manual Check Prompt)
echo "5️⃣  Manual UI Testing Required..."
echo "   Please verify in browser (http://localhost:8082):"
echo "   □ Active Pipeline shows 1 job (YipitData)"
echo "   □ Archived Pipeline shows 11 jobs"
echo "   □ Click Status dropdown - changes and saves"
echo "   □ Click Remote toggle - switches ✅/❌ and saves"
echo "   □ Click 📝 Notes - modal opens and saves"
echo "   □ Toast notifications appear for actions"
echo "   □ Source dropdown includes custom sources"
echo "   □ Add new source works"
echo ""
read -p "   Press Enter after manual testing..."
echo ""

# Test 6: Database Integrity Check (FIXED)
echo "6️⃣  Database Integrity Check..."
sqlite3 data/jobs-tracker.db << 'SQL'
.mode column
.headers on
SELECT 'Total' as category, COUNT(*) as count FROM opportunities
UNION ALL
SELECT 'Active', COUNT(*) FROM opportunities 
  WHERE status NOT IN ('Rejected', 'Declined', 'Ghosted', 'Accepted')
UNION ALL
SELECT 'Archived', COUNT(*) FROM opportunities
  WHERE status IN ('Rejected', 'Declined', 'Ghosted', 'Accepted')
UNION ALL
SELECT 'Sources', COUNT(*) FROM job_sources;
SQL
echo ""

# Additional detailed breakdown
echo "   Detailed Status Breakdown:"
sqlite3 data/jobs-tracker.db << 'SQL'
.mode column
.headers on
SELECT status, COUNT(*) as count 
FROM opportunities 
GROUP BY status 
ORDER BY count DESC;
SQL
echo ""

echo "╔════════════════════════════════════════════════════════╗"
echo "║     ✅ END-TO-END VALIDATION COMPLETE                  ║"
echo "╚════════════════════════════════════════════════════════╝"
echo ""
echo "📋 Next Step: Review and commit to git"
echo "   git status"
echo "   git add -A"
echo "   git commit -m 'Major milestone: Project reorganization + inline editing'"
echo "   git push origin main"
echo ""
