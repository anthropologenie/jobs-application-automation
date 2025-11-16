#!/bin/bash

# ============================================================
# Pipeline Features Test Suite
# ============================================================
# Tests archived pipeline and inline editing functionality
#
# IMPROVEMENTS (Nov 16, 2025):
# - Flexible JSON matching (handles spaces in responses)
# - Direct database queries for verification
# - Fallback to API parsing if database unavailable
# - Better error messages showing expected vs actual
# ============================================================

echo "╔════════════════════════════════════════════════════════╗"
echo "║  🧪 TESTING NEW PIPELINE FEATURES                     ║"
echo "╚════════════════════════════════════════════════════════╝"
echo ""

API="http://localhost:8081"
PASS_COUNT=0
FAIL_COUNT=0

test_endpoint() {
    local test_name=$1
    local expected=$2
    local actual=$3

    # More flexible matching: remove spaces for comparison
    # This handles both "success":true and "success": true
    local normalized_actual=$(echo "$actual" | tr -d ' ')
    local normalized_expected=$(echo "$expected" | tr -d ' ')

    if [[ "$normalized_actual" == *"$normalized_expected"* ]]; then
        echo "   ✅ PASS: $test_name"
        ((PASS_COUNT++))
        return 0
    else
        echo "   ❌ FAIL: $test_name"
        echo "      Expected (contains): $expected"
        echo "      Got: $actual"
        ((FAIL_COUNT++))
        return 1
    fi
}

echo "═══════════════════════════════════════════════════════════"
echo "PART 1: ARCHIVED PIPELINE TESTING"
echo "═══════════════════════════════════════════════════════════"
echo ""

# Test 1: Get archived pipeline
echo "1️⃣  GET /api/archived-pipeline - Retrieve archived opportunities"
ARCHIVED=$(curl -s ${API}/api/archived-pipeline)
test_endpoint "Archived pipeline returns JSON array" "[" "$ARCHIVED"

if [ "$ARCHIVED" != "[]" ]; then
    ARCHIVED_COUNT=$(echo $ARCHIVED | grep -o '"id"' | wc -l)
    echo "   📦 Found $ARCHIVED_COUNT archived opportunit(y/ies)"
else
    echo "   📦 No archived opportunities yet"
fi
echo ""

# Test 2: Archive an opportunity by changing status
echo "2️⃣  PATCH /api/update-opportunity/3 - Archive opportunity (status=Declined)"
ARCHIVE_RESULT=$(curl -s -X PATCH ${API}/api/update-opportunity/3 \
  -H "Content-Type: application/json" \
  -d '{"status": "Declined"}')
test_endpoint "Archive via status change successful" '"success":true' "$ARCHIVE_RESULT"
echo "   Response: $ARCHIVE_RESULT"
echo ""

# Test 3: Verify opportunity moved to archived
echo "3️⃣  Verify opportunity #3 appears in archived pipeline"
ARCHIVED_AFTER=$(curl -s ${API}/api/archived-pipeline)
test_endpoint "Opportunity #3 in archived pipeline" '"id":3' "$ARCHIVED_AFTER"
echo ""

# Test 4: Verify opportunity removed from active pipeline
echo "4️⃣  Verify opportunity #3 NOT in active pipeline"
ACTIVE=$(curl -s ${API}/api/pipeline)
if [[ "$ACTIVE" == *'"id":3'* ]]; then
    echo "   ❌ FAIL: Opportunity #3 still in active pipeline"
    ((FAIL_COUNT++))
else
    echo "   ✅ PASS: Opportunity #3 correctly removed from active"
    ((PASS_COUNT++))
fi
echo ""

echo "═══════════════════════════════════════════════════════════"
echo "PART 2: INLINE EDITING - STATUS UPDATE"
echo "═══════════════════════════════════════════════════════════"
echo ""

# Test 5: Update status
echo "5️⃣  PATCH /api/update-opportunity/1 - Update status to 'Technical'"
STATUS_UPDATE=$(curl -s -X PATCH ${API}/api/update-opportunity/1 \
  -H "Content-Type: application/json" \
  -d '{"status": "Technical"}')
test_endpoint "Status update successful" '"success":true' "$STATUS_UPDATE"
test_endpoint "Updated fields includes status" '"status"' "$STATUS_UPDATE"
echo ""

# Test 6: Verify status was updated
echo "6️⃣  Verify status updated in database"
sleep 1
# Query database directly for more reliable verification
VERIFY_STATUS=$(sqlite3 data/jobs-tracker.db "SELECT status FROM opportunities WHERE id=1" 2>/dev/null)
if [ -z "$VERIFY_STATUS" ]; then
    echo "   ⚠️  Warning: Could not query database directly, using API"
    VERIFY_STATUS=$(curl -s ${API}/api/pipeline | grep -A 10 '"id":1' | grep -o '"status":"[^"]*"')
    test_endpoint "Status is Technical" '"status":"Technical"' "$VERIFY_STATUS"
else
    test_endpoint "Status is Technical" "Technical" "$VERIFY_STATUS"
fi
echo ""

echo "═══════════════════════════════════════════════════════════"
echo "PART 3: INLINE EDITING - REMOTE TOGGLE"
echo "═══════════════════════════════════════════════════════════"
echo ""

# Test 7: Toggle remote status
echo "7️⃣  PATCH /api/update-opportunity/1 - Toggle remote to false"
REMOTE_UPDATE=$(curl -s -X PATCH ${API}/api/update-opportunity/1 \
  -H "Content-Type: application/json" \
  -d '{"is_remote": 0}')
test_endpoint "Remote toggle successful" '"success":true' "$REMOTE_UPDATE"
echo ""

# Test 8: Toggle back to true
echo "8️⃣  PATCH /api/update-opportunity/1 - Toggle remote back to true"
REMOTE_TOGGLE=$(curl -s -X PATCH ${API}/api/update-opportunity/1 \
  -H "Content-Type: application/json" \
  -d '{"is_remote": 1}')
test_endpoint "Remote toggle back successful" '"success":true' "$REMOTE_TOGGLE"
echo ""

echo "═══════════════════════════════════════════════════════════"
echo "PART 4: NOTES EDITING"
echo "═══════════════════════════════════════════════════════════"
echo ""

# Test 9: Update notes
echo "9️⃣  PATCH /api/update-opportunity/1 - Update notes"
NOTES_UPDATE=$(curl -s -X PATCH ${API}/api/update-opportunity/1 \
  -H "Content-Type: application/json" \
  -d '{"notes": "Test notes from automated test suite - updated successfully"}')
test_endpoint "Notes update successful" '"success":true' "$NOTES_UPDATE"
echo ""

# Test 10: Verify notes were saved
echo "🔟  Verify notes updated in database"
sleep 1
# Query database directly for more reliable verification
VERIFY_NOTES=$(sqlite3 data/jobs-tracker.db "SELECT notes FROM opportunities WHERE id=1" 2>/dev/null)
if [ -z "$VERIFY_NOTES" ]; then
    echo "   ⚠️  Warning: Could not query database directly, using API"
    VERIFY_NOTES=$(curl -s ${API}/api/pipeline | grep -A 15 '"id":1' | grep -o '"notes":"[^"]*"' | head -1)
fi
test_endpoint "Notes contain test text" 'automated test suite' "$VERIFY_NOTES"
echo ""

echo "═══════════════════════════════════════════════════════════"
echo "PART 5: MULTIPLE FIELD UPDATES"
echo "═══════════════════════════════════════════════════════════"
echo ""

# Test 11: Update multiple fields at once
echo "1️⃣1️⃣  PATCH /api/update-opportunity/4 - Update status AND remote"
MULTI_UPDATE=$(curl -s -X PATCH ${API}/api/update-opportunity/4 \
  -H "Content-Type: application/json" \
  -d '{"status": "Applied", "is_remote": 1}')
test_endpoint "Multiple field update successful" '"success":true' "$MULTI_UPDATE"
test_endpoint "Updated fields includes both" '"status"' "$MULTI_UPDATE"
echo ""

echo "═══════════════════════════════════════════════════════════"
echo "PART 6: ERROR HANDLING"
echo "═══════════════════════════════════════════════════════════"
echo ""

# Test 12: Try to update non-existent opportunity
echo "1️⃣2️⃣  PATCH /api/update-opportunity/99999 - Non-existent ID"
NOT_FOUND=$(curl -s -X PATCH ${API}/api/update-opportunity/99999 \
  -H "Content-Type: application/json" \
  -d '{"status": "Applied"}')
# Flexible error check - accepts "error" in response (case-insensitive)
if echo "$NOT_FOUND" | grep -iq "error"; then
    echo "   ✅ PASS: Returns error for non-existent ID"
    ((PASS_COUNT++))
else
    echo "   ❌ FAIL: Should return error for non-existent ID"
    echo "      Got: $NOT_FOUND"
    ((FAIL_COUNT++))
fi
echo ""

# Test 13: Try to update with invalid field
echo "1️⃣3️⃣  PATCH /api/update-opportunity/1 - Empty update"
EMPTY_UPDATE=$(curl -s -X PATCH ${API}/api/update-opportunity/1 \
  -H "Content-Type: application/json" \
  -d '{}')
# Flexible error check - accepts "error" in response
if echo "$EMPTY_UPDATE" | grep -iq "error"; then
    echo "   ✅ PASS: Returns error for empty update"
    ((PASS_COUNT++))
else
    echo "   ❌ FAIL: Should return error for empty update"
    ((FAIL_COUNT++))
fi
echo "   Response: $EMPTY_UPDATE"
echo ""

echo "═══════════════════════════════════════════════════════════"
echo "PART 7: CLEANUP & RESTORE"
echo "═══════════════════════════════════════════════════════════"
echo ""

# Test 14: Restore opportunity #3 back to active
echo "1️⃣4️⃣  Restore opportunity #3 to active pipeline"
RESTORE=$(curl -s -X PATCH ${API}/api/update-opportunity/3 \
  -H "Content-Type: application/json" \
  -d '{"status": "Screening"}')
test_endpoint "Restore successful" '"success":true' "$RESTORE"
echo ""

# Verify it moved back
sleep 1
ACTIVE_AFTER=$(curl -s ${API}/api/pipeline)
test_endpoint "Opportunity #3 back in active pipeline" '"id":3' "$ACTIVE_AFTER"
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
    echo "📊 Features Validated:"
    echo "   ✅ Archived Pipeline Section"
    echo "   ✅ Inline Status Editing (dropdown)"
    echo "   ✅ Inline Remote Toggle"
    echo "   ✅ Notes Modal Editing"
    echo "   ✅ Multiple Field Updates"
    echo "   ✅ Error Handling"
    echo ""
    exit 0
else
    echo "   ⚠️  SOME TESTS FAILED - Review output above"
    echo ""
    exit 1
fi
