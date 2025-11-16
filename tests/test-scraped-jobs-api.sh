#!/bin/bash
# Test script for scraped jobs API endpoints

API_URL="http://localhost:8081"

echo "========================================================================"
echo "🧪 TESTING SCRAPED JOBS API ENDPOINTS"
echo "========================================================================"

echo -e "\n1️⃣ Testing /api/scraped-jobs/stats"
echo "Command: curl \"$API_URL/api/scraped-jobs/stats\""
curl -s "$API_URL/api/scraped-jobs/stats" | tail -1 | python3 -m json.tool

echo -e "\n========================================================================"
echo "2️⃣ Testing /api/scraped-jobs with default params"
echo "Command: curl \"$API_URL/api/scraped-jobs\""
curl -s "$API_URL/api/scraped-jobs" | tail -1 | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f'Success: {data[\"success\"]}')
print(f'Count: {data[\"count\"]}')
print(f'Filters: {data[\"filters_applied\"]}')
print(f'\nTop 5 Jobs:')
for i, job in enumerate(data['jobs'][:5], 1):
    print(f'  {i}. [{job[\"match_score\"]}%] {job[\"company\"]} - {job[\"job_title\"]}')
"

echo -e "\n========================================================================"
echo "3️⃣ Testing /api/scraped-jobs with min_score=60"
echo "Command: curl \"$API_URL/api/scraped-jobs?min_score=60&limit=10\""
curl -s "$API_URL/api/scraped-jobs?min_score=60&limit=10" | tail -1 | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f'Found {data[\"count\"]} jobs with score >= 60%')
for job in data['jobs']:
    print(f'  • [{job[\"match_score\"]}%] {job[\"company\"]} - {job[\"job_title\"]} ({job[\"location\"]})')
"

echo -e "\n========================================================================"
echo "4️⃣ Testing /api/scraped-jobs with classification filter"
echo "Command: curl \"$API_URL/api/scraped-jobs?classification=LOW_FIT&limit=5\""
curl -s "$API_URL/api/scraped-jobs?classification=LOW_FIT&limit=5" | tail -1 | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f'Found {data[\"count\"]} LOW_FIT jobs')
for job in data['jobs']:
    skills = ', '.join([s['skill'] for s in job['matched_skills'][:3]])
    print(f'  • [{job[\"match_score\"]}%] {job[\"company\"]} - {job[\"job_title\"]}')
    print(f'    Skills: {skills}')
"

echo -e "\n========================================================================"
echo "5️⃣ Testing /api/scraped-jobs with source filter"
echo "Command: curl \"$API_URL/api/scraped-jobs?source=RemoteOK&limit=3\""
curl -s "$API_URL/api/scraped-jobs?source=RemoteOK&limit=3" | tail -1 | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f'Found {data[\"count\"]} jobs from RemoteOK')
for job in data['jobs']:
    print(f'  • [{job[\"match_score\"]}%] {job[\"company\"]} - {job[\"job_title\"]}')
    print(f'    URL: {job[\"job_url\"]}')
"

echo -e "\n========================================================================"
echo "6️⃣ Testing combined filters"
echo "Command: curl \"$API_URL/api/scraped-jobs?min_score=50&classification=LOW_FIT&source=RemoteOK&limit=5\""
curl -s "$API_URL/api/scraped-jobs?min_score=50&classification=LOW_FIT&source=RemoteOK&limit=5" | tail -1 | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f'Applied Filters: {data[\"filters_applied\"]}')
print(f'Results: {data[\"count\"]} jobs\n')
for job in data['jobs']:
    domains = ', '.join([d['domain'] for d in job['matched_domains'][:2]]) if job['matched_domains'] else 'None'
    print(f'  [{job[\"match_score\"]}%] {job[\"company\"]} - {job[\"job_title\"]}')
    print(f'  Domains: {domains}')
    print(f'  Recommendation: {job[\"recommendation\"]}')
    print()
"

echo "========================================================================"
echo "✅ ALL TESTS COMPLETED"
echo "========================================================================"
echo ""
echo "📚 AVAILABLE QUERY PARAMETERS:"
echo "   • min_score    - Minimum match score (default: 70)"
echo "   • limit        - Maximum number of results (default: 50)"
echo "   • classification - Filter by classification (EXCELLENT, HIGH_FIT, MEDIUM_FIT, LOW_FIT, NO_FIT)"
echo "   • source       - Filter by source (RemoteOK, LinkedIn, etc.)"
echo ""
echo "📖 EXAMPLE QUERIES:"
echo "   # Get all high-scoring jobs"
echo "   curl \"$API_URL/api/scraped-jobs?min_score=75\""
echo ""
echo "   # Get top 10 jobs from any source"
echo "   curl \"$API_URL/api/scraped-jobs?limit=10\""
echo ""
echo "   # Get statistics"
echo "   curl \"$API_URL/api/scraped-jobs/stats\""
echo ""
