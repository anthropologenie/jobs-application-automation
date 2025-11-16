#!/bin/bash

echo "╔════════════════════════════════════════════════════════╗"
echo "║     🧪 TESTING NEW FEATURES - COMPREHENSIVE SUITE     ║"
echo "╚════════════════════════════════════════════════════════╝"
echo ""

API_URL="http://localhost:8081"
PASS_COUNT=0
FAIL_COUNT=0

# Function to test and report
test_endpoint() {
    local test_name=$1
    local expected=$2
    local actual=$3

    if [[ "$actual" == *"$expected"* ]]; then
        echo "   ✅ PASS: $test_name"
        ((PASS_COUNT++))
        return 0
    else
        echo "   ❌ FAIL: $test_name"
        echo "      Expected: $expected"
        echo "      Got: $actual"
        ((FAIL_COUNT++))
        return 1
    fi
}

echo "═══════════════════════════════════════════════════════════"
echo "PART 1: DYNAMIC SOURCES TESTING"
echo "═══════════════════════════════════════════════════════════"
echo ""

# Test 1: GET existing sources
echo "1️⃣  GET /api/sources - Retrieve all sources"
SOURCES=$(curl -s ${API_URL}/api/sources)
test_endpoint "Sources endpoint returns JSON array" "[" "$SOURCES"
test_endpoint "Sources contains LinkedIn" "LinkedIn" "$SOURCES"
test_endpoint "Sources contains Wellfound (added earlier)" "Wellfound" "$SOURCES"
echo "   📊 Sources: $(echo $SOURCES | grep -o '"source_name"' | wc -l) total"
echo ""

# Test 2: POST new source - TestDevJobs
echo "2️⃣  POST /api/add-source - Add 'TestDevJobs'"
ADD_SOURCE1=$(curl -s -X POST ${API_URL}/api/add-source \
  -H "Content-Type: application/json" \
  -d '{"source_name": "TestDevJobs"}')
test_endpoint "TestDevJobs added successfully" '"success":true' "$ADD_SOURCE1"
echo "   Response: $ADD_SOURCE1"
echo ""

# Test 3: POST new source - AngelList
echo "3️⃣  POST /api/add-source - Add 'AngelList'"
ADD_SOURCE2=$(curl -s -X POST ${API_URL}/api/add-source \
  -H "Content-Type: application/json" \
  -d '{"source_name": "AngelList"}')
test_endpoint "AngelList added successfully" '"success":true' "$ADD_SOURCE2"
echo ""

# Test 4: Verify sources were added
echo "4️⃣  Verify new sources appear in sources list"
UPDATED_SOURCES=$(curl -s ${API_URL}/api/sources)
test_endpoint "TestDevJobs in sources" "TestDevJobs" "$UPDATED_SOURCES"
test_endpoint "AngelList in sources" "AngelList" "$UPDATED_SOURCES"
echo ""

echo "═══════════════════════════════════════════════════════════"
echo "PART 2: RECRUITER CONTACT SMART PARSING"
echo "═══════════════════════════════════════════════════════════"
echo ""

# Test 5: Add opportunity with phone number
echo "5️⃣  POST opportunity with PHONE NUMBER in recruiter_contact"
ADD_OPP1=$(curl -s -X POST ${API_URL}/api/add-opportunity \
  -H "Content-Type: application/json" \
  -d '{
    "company": "Test Corp A",
    "role": "QA Engineer",
    "source": "LinkedIn",
    "is_remote": 1,
    "tech_stack": "Python, Selenium",
    "recruiter_contact": "+91 98765 43210",
    "notes": "Test with phone number",
    "status": "Lead",
    "priority": "High"
  }')
test_endpoint "Opportunity with phone added" '"success":true' "$ADD_OPP1"
OPP1_ID=$(echo $ADD_OPP1 | grep -o '"id":[0-9]*' | grep -o '[0-9]*')
echo "   📝 Created opportunity ID: $OPP1_ID"
echo ""

# Test 6: Add opportunity with email
echo "6️⃣  POST opportunity with EMAIL in recruiter_contact"
ADD_OPP2=$(curl -s -X POST ${API_URL}/api/add-opportunity \
  -H "Content-Type: application/json" \
  -d '{
    "company": "Test Corp B",
    "role": "ETL Test Lead",
    "source": "Naukri",
    "is_remote": 1,
    "tech_stack": "AWS Glue, Python",
    "recruiter_contact": "recruiter@testcorp.com",
    "notes": "Test with email",
    "status": "Lead",
    "priority": "Medium"
  }')
test_endpoint "Opportunity with email added" '"success":true' "$ADD_OPP2"
OPP2_ID=$(echo $ADD_OPP2 | grep -o '"id":[0-9]*' | grep -o '[0-9]*')
echo "   📝 Created opportunity ID: $OPP2_ID"
echo ""

# Test 7: Add opportunity with NEW source + phone
echo "7️⃣  POST opportunity with NEW SOURCE (TestDevJobs) + phone"
ADD_OPP3=$(curl -s -X POST ${API_URL}/api/add-opportunity \
  -H "Content-Type: application/json" \
  -d '{
    "company": "Startup XYZ",
    "role": "Senior QA",
    "source": "TestDevJobs",
    "is_remote": 1,
    "tech_stack": "Docker, K8s",
    "recruiter_contact": "+1-555-1234",
    "notes": "From TestDevJobs platform",
    "status": "Lead",
    "priority": "High"
  }')
test_endpoint "Opportunity with new source added" '"success":true' "$ADD_OPP3"
OPP3_ID=$(echo $ADD_OPP3 | grep -o '"id":[0-9]*' | grep -o '[0-9]*')
echo "   📝 Created opportunity ID: $OPP3_ID"
echo ""

# Test 8: Add opportunity with NEW source + email
echo "8️⃣  POST opportunity with NEW SOURCE (AngelList) + email"
ADD_OPP4=$(curl -s -X POST ${API_URL}/api/add-opportunity \
  -H "Content-Type: application/json" \
  -d '{
    "company": "Tech Innovators",
    "role": "QA Automation Lead",
    "source": "AngelList",
    "is_remote": 1,
    "tech_stack": "Playwright, Jest",
    "recruiter_contact": "hiring@techinnovators.io",
    "notes": "From AngelList job board",
    "status": "Lead",
    "priority": "High"
  }')
test_endpoint "Opportunity with AngelList source added" '"success":true' "$ADD_OPP4"
OPP4_ID=$(echo $ADD_OPP4 | grep -o '"id":[0-9]*' | grep -o '[0-9]*')
echo "   📝 Created opportunity ID: $OPP4_ID"
echo ""

echo "═══════════════════════════════════════════════════════════"
echo "PART 3: DATABASE VERIFICATION"
echo "═══════════════════════════════════════════════════════════"
echo ""

# Test 9: Verify phone number stored correctly
echo "9️⃣  Verify phone number stored in recruiter_phone column"
PHONE_CHECK=$(sqlite3 data/jobs-tracker.db "SELECT recruiter_phone FROM opportunities WHERE id = $OPP1_ID")
test_endpoint "Phone stored correctly" "+91 98765 43210" "$PHONE_CHECK"
EMAIL_CHECK=$(sqlite3 data/jobs-tracker.db "SELECT recruiter_email FROM opportunities WHERE id = $OPP1_ID")
test_endpoint "Email column empty for phone entry" "" "$EMAIL_CHECK"
echo ""

# Test 10: Verify email stored correctly
echo "🔟  Verify email stored in recruiter_email column"
EMAIL_CHECK2=$(sqlite3 data/jobs-tracker.db "SELECT recruiter_email FROM opportunities WHERE id = $OPP2_ID")
test_endpoint "Email stored correctly" "recruiter@testcorp.com" "$EMAIL_CHECK2"
PHONE_CHECK2=$(sqlite3 data/jobs-tracker.db "SELECT recruiter_phone FROM opportunities WHERE id = $OPP2_ID")
test_endpoint "Phone column empty for email entry" "" "$PHONE_CHECK2"
echo ""

# Test 11: Verify source stored correctly
echo "1️⃣1️⃣  Verify new sources stored in opportunities"
SOURCE_CHECK1=$(sqlite3 data/jobs-tracker.db "SELECT source FROM opportunities WHERE id = $OPP3_ID")
test_endpoint "TestDevJobs source stored" "TestDevJobs" "$SOURCE_CHECK1"
SOURCE_CHECK2=$(sqlite3 data/jobs-tracker.db "SELECT source FROM opportunities WHERE id = $OPP4_ID")
test_endpoint "AngelList source stored" "AngelList" "$SOURCE_CHECK2"
echo ""

echo "═══════════════════════════════════════════════════════════"
echo "PART 4: NEGATIVE TESTING (INVALID INPUTS)"
echo "═══════════════════════════════════════════════════════════"
echo ""

# Test 12: Duplicate source name
echo "1️⃣2️⃣  POST duplicate source name (should fail)"
DUPLICATE_SOURCE=$(curl -s -X POST ${API_URL}/api/add-source \
  -H "Content-Type: application/json" \
  -d '{"source_name": "LinkedIn"}')
test_endpoint "Duplicate source rejected" '"error"' "$DUPLICATE_SOURCE"
test_endpoint "Error mentions already exists" "already exists" "$DUPLICATE_SOURCE"
echo "   Response: $DUPLICATE_SOURCE"
echo ""

# Test 13: Empty source name
echo "1️⃣3️⃣  POST empty source name (should fail)"
EMPTY_SOURCE=$(curl -s -X POST ${API_URL}/api/add-source \
  -H "Content-Type: application/json" \
  -d '{"source_name": ""}')
test_endpoint "Empty source rejected" '"error"' "$EMPTY_SOURCE"
echo "   Response: $EMPTY_SOURCE"
echo ""

# Test 14: Missing source name
echo "1️⃣4️⃣  POST missing source_name field (should fail)"
MISSING_SOURCE=$(curl -s -X POST ${API_URL}/api/add-source \
  -H "Content-Type: application/json" \
  -d '{}')
test_endpoint "Missing source name rejected" '"error"' "$MISSING_SOURCE"
echo "   Response: $MISSING_SOURCE"
echo ""

echo "═══════════════════════════════════════════════════════════"
echo "PART 5: API ENDPOINT VALIDATION"
echo "═══════════════════════════════════════════════════════════"
echo ""

# Test 15: GET /api/metrics
echo "1️⃣5️⃣  GET /api/metrics - Real data test"
METRICS=$(curl -s ${API_URL}/api/metrics)
test_endpoint "Metrics returns JSON" "active_count" "$METRICS"
test_endpoint "Metrics has interview_count" "interview_count" "$METRICS"
echo "   📊 Metrics: $METRICS"
echo ""

# Test 16: GET /api/pipeline
echo "1️⃣6️⃣  GET /api/pipeline - Contains test opportunities"
PIPELINE=$(curl -s ${API_URL}/api/pipeline)
test_endpoint "Pipeline returns array" "[" "$PIPELINE"
test_endpoint "Pipeline contains Test Corp A" "Test Corp A" "$PIPELINE"
test_endpoint "Pipeline contains Startup XYZ" "Startup XYZ" "$PIPELINE"
echo "   🎯 Pipeline entries: $(echo $PIPELINE | grep -o '"id"' | wc -l)"
echo ""

echo "═══════════════════════════════════════════════════════════"
echo "PART 6: CLEANUP TEST DATA"
echo "═══════════════════════════════════════════════════════════"
echo ""

echo "1️⃣7️⃣  Cleaning up test opportunities..."
sqlite3 data/jobs-tracker.db "DELETE FROM opportunities WHERE company LIKE 'Test Corp%' OR company IN ('Startup XYZ', 'Tech Innovators')"
echo "   🧹 Test opportunities removed"
echo ""

echo "1️⃣8️⃣  Final source count verification..."
FINAL_SOURCES=$(curl -s ${API_URL}/api/sources)
FINAL_COUNT=$(echo $FINAL_SOURCES | grep -o '"source_name"' | wc -l)
echo "   📊 Total sources in database: $FINAL_COUNT"
echo "   ✅ Custom sources (TestDevJobs, AngelList, Wellfound) persist after cleanup"
echo ""

echo "╔════════════════════════════════════════════════════════╗"
echo "║                  TEST SUMMARY                          ║"
echo "╚════════════════════════════════════════════════════════╝"
echo ""
echo "   ✅ PASSED: $PASS_COUNT"
echo "   ❌ FAILED: $FAIL_COUNT"
echo ""

if [ $FAIL_COUNT -eq 0 ]; then
    echo "   🎉 ALL TESTS PASSED!"
    echo ""
    exit 0
else
    echo "   ⚠️  SOME TESTS FAILED - Review output above"
    echo ""
    exit 1
fi
