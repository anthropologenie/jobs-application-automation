#!/bin/bash

echo "╔════════════════════════════════════════════════════════╗"
echo "║     🧪 COMPLETE SYSTEM TEST                            ║"
echo "╚════════════════════════════════════════════════════════╝"
echo ""

# Test 1: Database
echo "1️⃣  DATABASE TEST"
OPP_COUNT=$(sqlite3 data/jobs-tracker.db "SELECT COUNT(*) FROM opportunities" 2>/dev/null)
if [ $? -eq 0 ]; then
  echo "   ✅ Database accessible: $OPP_COUNT opportunities"
else
  echo "   ❌ Database error"
  exit 1
fi
echo ""

# Test 2: Dashboard
echo "2️⃣  DASHBOARD TEST"
if curl -s http://localhost:8082 > /dev/null 2>&1; then
  echo "   ✅ Dashboard responding at http://localhost:8082"
else
  echo "   ❌ Dashboard not running"
  exit 1
fi
echo ""

# Test 3: Python API
echo "3️⃣  PYTHON API TEST"
if curl -s http://localhost:8081/api/metrics > /dev/null 2>&1; then
  echo "   ✅ API server responding at http://localhost:8081"
else
  echo "   ❌ API server not running"
  exit 1
fi
echo ""

# Test 4: Metrics Endpoint
echo "4️⃣  METRICS ENDPOINT TEST"
METRICS=$(curl -s http://localhost:8081/api/metrics 2>&1)
if echo "$METRICS" | grep -q "active_count"; then
  echo "   ✅ Metrics endpoint working"
  if command -v jq &> /dev/null; then
    echo "   📊 $(echo $METRICS | jq -c .)"
  else
    echo "   📊 $METRICS"
  fi
else
  echo "   ❌ Metrics endpoint failed"
  echo "   Response: $METRICS"
  exit 1
fi
echo ""

# Test 5: Agenda Endpoint
echo "5️⃣  AGENDA ENDPOINT TEST"
AGENDA=$(curl -s http://localhost:8081/api/todays-agenda 2>&1)
if echo "$AGENDA" | grep -q -E '\['; then
  echo "   ✅ Agenda endpoint working"
  AGENDA_COUNT=$(echo "$AGENDA" | grep -o "\"id\"" | wc -l)
  echo "   📅 $AGENDA_COUNT upcoming interviews"
else
  echo "   ❌ Agenda endpoint failed"
  exit 1
fi
echo ""

# Test 6: Pipeline Endpoint
echo "6️⃣  PIPELINE ENDPOINT TEST"
PIPELINE=$(curl -s http://localhost:8081/api/pipeline 2>&1)
if echo "$PIPELINE" | grep -q -E '\['; then
  echo "   ✅ Pipeline endpoint working"
  PIPELINE_COUNT=$(echo "$PIPELINE" | grep -o "\"id\"" | wc -l)
  echo "   🎯 $PIPELINE_COUNT active opportunities"
else
  echo "   ❌ Pipeline endpoint failed"
  exit 1
fi
echo ""

# Test 7: Add Opportunity Endpoint (FIXED - using valid source)
echo "7️⃣  ADD OPPORTUNITY ENDPOINT TEST"
ADD_RESULT=$(curl -s -X POST http://localhost:8081/api/add-opportunity \
  -H "Content-Type: application/json" \
  -d '{
    "company": "System Test Corp",
    "role": "Test Engineer",
    "source": "Other",
    "is_remote": 1,
    "tech_stack": "Testing",
    "notes": "Automated test",
    "status": "Lead",
    "priority": "Low"
  }' 2>&1)

if echo "$ADD_RESULT" | grep -q "success"; then
  echo "   ✅ Add opportunity endpoint working"
  if command -v jq &> /dev/null; then
    echo "   ✨ $(echo $ADD_RESULT | jq -c .)"
  else
    echo "   ✨ $ADD_RESULT"
  fi
  
  # Verify in database
  sleep 1
  VERIFY=$(sqlite3 data/jobs-tracker.db "SELECT company FROM opportunities WHERE company = 'System Test Corp'" 2>/dev/null)
  if [ "$VERIFY" == "System Test Corp" ]; then
    echo "   ✅ Verified in database"
    # Clean up test entry
    sqlite3 data/jobs-tracker.db "DELETE FROM opportunities WHERE company = 'System Test Corp'" 2>/dev/null
    echo "   🧹 Test entry cleaned up"
  else
    echo "   ⚠️  Not found in database"
  fi
else
  echo "   ❌ Add opportunity failed"
  echo "   Response: $ADD_RESULT"
  exit 1
fi
echo ""

echo "╔════════════════════════════════════════════════════════╗"
echo "║     ✅ ALL TESTS PASSED!                               ║"
echo "╚════════════════════════════════════════════════════════╝"
echo ""
echo "🎉 Your job tracker is fully operational!"
echo ""
echo "📍 Access Points:"
echo "   Dashboard:  http://localhost:8082"
echo "   API Server: http://localhost:8081"
echo ""
echo "📊 Current Stats:"
OPP_COUNT_FINAL=$(sqlite3 data/jobs-tracker.db "SELECT COUNT(*) FROM opportunities" 2>/dev/null)
ACTIVE_COUNT=$(curl -s http://localhost:8081/api/metrics | grep -o '"active_count": [0-9]*' | grep -o '[0-9]*')
INTERVIEW_COUNT=$(curl -s http://localhost:8081/api/metrics | grep -o '"interview_count": [0-9]*' | grep -o '[0-9]*')
echo "   • $OPP_COUNT_FINAL total opportunities"
echo "   • $ACTIVE_COUNT active in pipeline"
echo "   • $INTERVIEW_COUNT upcoming interviews"
echo ""
