#!/bin/bash

echo "╔════════════════════════════════════════════════════════╗"
echo "║     📋 FINAL VALIDATION - COMPREHENSIVE REPORT         ║"
echo "╚════════════════════════════════════════════════════════╝"
echo ""

API="http://localhost:8081"

echo "═══════════════════════════════════════════════════════════"
echo "TEST 1: Add New Source 'Wellfound'"
echo "═══════════════════════════════════════════════════════════"
curl -s -X POST ${API}/api/add-source \
  -H "Content-Type: application/json" \
  -d '{"source_name": "Wellfound"}' | python3 -m json.tool
echo ""

echo "═══════════════════════════════════════════════════════════"
echo "TEST 2: Add New Source 'Indeed'"
echo "═══════════════════════════════════════════════════════════"
curl -s -X POST ${API}/api/add-source \
  -H "Content-Type: application/json" \
  -d '{"source_name": "Indeed"}' | python3 -m json.tool
echo ""

echo "═══════════════════════════════════════════════════════════"
echo "TEST 3: Get All Sources (Should Include New Ones)"
echo "═══════════════════════════════════════════════════════════"
curl -s ${API}/api/sources | python3 -m json.tool
echo ""

echo "═══════════════════════════════════════════════════════════"
echo "TEST 4: Add Opportunity with PHONE (Wellfound source)"
echo "═══════════════════════════════════════════════════════════"
curl -s -X POST ${API}/api/add-opportunity \
  -H "Content-Type: application/json" \
  -d '{
    "company": "Wellfound Startup",
    "role": "Senior QA Engineer",
    "source": "Wellfound",
    "is_remote": 1,
    "tech_stack": "React, Node.js, PostgreSQL",
    "recruiter_contact": "+1-415-555-0199",
    "notes": "Testing phone number parsing",
    "status": "Lead",
    "priority": "High"
  }' | python3 -m json.tool
echo ""

echo "═══════════════════════════════════════════════════════════"
echo "TEST 5: Add Opportunity with EMAIL (Indeed source)"
echo "═══════════════════════════════════════════════════════════"
curl -s -X POST ${API}/api/add-opportunity \
  -H "Content-Type: application/json" \
  -d '{
    "company": "Indeed Enterprise",
    "role": "QA Automation Lead",
    "source": "Indeed",
    "is_remote": 1,
    "tech_stack": "Selenium, Cypress, Jenkins",
    "recruiter_contact": "sarah.recruiter@indeed.com",
    "notes": "Testing email parsing",
    "status": "Lead",
    "priority": "Medium"
  }' | python3 -m json.tool
echo ""

echo "═══════════════════════════════════════════════════════════"
echo "TEST 6: Verify Data in Database"
echo "═══════════════════════════════════════════════════════════"
sqlite3 data/jobs-tracker.db << 'EOF'
.mode column
.headers on
SELECT id, company, source, recruiter_phone, recruiter_email
FROM opportunities
WHERE company IN ('Wellfound Startup', 'Indeed Enterprise')
ORDER BY id DESC;
EOF
echo ""

echo "═══════════════════════════════════════════════════════════"
echo "TEST 7: Try to Add Duplicate Source (Should Fail)"
echo "═══════════════════════════════════════════════════════════"
curl -s -X POST ${API}/api/add-source \
  -H "Content-Type: application/json" \
  -d '{"source_name": "Wellfound"}' | python3 -m json.tool
echo ""

echo "═══════════════════════════════════════════════════════════"
echo "TEST 8: Try Empty Source Name (Should Fail)"
echo "═══════════════════════════════════════════════════════════"
curl -s -X POST ${API}/api/add-source \
  -H "Content-Type: application/json" \
  -d '{"source_name": ""}' | python3 -m json.tool
echo ""

echo "═══════════════════════════════════════════════════════════"
echo "TEST 9: Verify Pipeline API Returns New Opportunities"
echo "═══════════════════════════════════════════════════════════"
curl -s ${API}/api/pipeline | python3 -m json.tool | grep -A 5 "Wellfound Startup"
echo ""

echo "═══════════════════════════════════════════════════════════"
echo "TEST 10: Verify Metrics API"
echo "═══════════════════════════════════════════════════════════"
curl -s ${API}/api/metrics | python3 -m json.tool
echo ""

echo "╔════════════════════════════════════════════════════════╗"
echo "║              VALIDATION COMPLETE                       ║"
echo "╚════════════════════════════════════════════════════════╝"
