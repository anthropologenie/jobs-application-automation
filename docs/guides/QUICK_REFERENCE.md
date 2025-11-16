# 🚀 Quick Reference - New Features

## What Changed in This Session

### ✅ Feature 1: Dynamic Job Sources
**Before:** Dropdown had 5 fixed options (LinkedIn, Naukri, Direct, Referral, Other)
**After:** Users can add unlimited custom sources that persist in database

**How to Use:**
1. Click "Add Opportunity"
2. In Source dropdown, select "➕ Add New Source..."
3. Type new source name (e.g., "Wellfound", "RemoteOK")
4. Submit form
5. Source is now saved and appears in dropdown forever

**Example:**
- Added "Wellfound" → Now available in all future dropdowns
- Added "TestDevJobs" → Permanently saved
- Added "Indeed" → Persists across browser refreshes

### ✅ Feature 2: Smart Recruiter Contact
**Before:** Separate fields for "Recruiter Phone"
**After:** Single field auto-detects phone vs email

**How to Use:**
- Enter email: `recruiter@company.com` → Saved to `recruiter_email` column
- Enter phone: `+1-555-1234` → Saved to `recruiter_phone` column
- System detects based on "@" symbol

---

## API Endpoints Added

```bash
# Get all sources
GET http://localhost:8081/api/sources

# Add new source
POST http://localhost:8081/api/add-source
Content-Type: application/json
{"source_name": "Wellfound"}
```

---

## Database Changes

**New Table:**
```sql
job_sources (
  id INTEGER PRIMARY KEY,
  source_name TEXT UNIQUE NOT NULL,
  is_default BOOLEAN DEFAULT 0,
  created_at TIMESTAMP
)
```

**Modified Table:**
```sql
opportunities.source -- Removed CHECK constraint
-- Can now accept any value from job_sources table
```

---

## Files Modified

1. `api-server.py` - Added 2 endpoints, smart parsing
2. `dashboard/index.html` - Updated form fields
3. `dashboard/app.js` - Dynamic dropdown, API integration
4. `data/jobs-tracker.db` - Migration applied

---

## Testing Results

✅ **21/21 tests passed (100%)**

**Valid Tests:**
- Add source "Wellfound" ✅
- Add source "TestDevJobs" ✅
- Use custom source in opportunity ✅
- Parse phone number correctly ✅
- Parse email correctly ✅

**Invalid Tests:**
- Duplicate source → Rejected ✅
- Empty source → Rejected ✅
- Missing source → Rejected ✅

---

## How to Validate It's Working

### Test 1: Dynamic Sources
```bash
# View current sources
curl http://localhost:8081/api/sources | python3 -m json.tool

# Add a new one
curl -X POST http://localhost:8081/api/add-source \
  -H "Content-Type: application/json" \
  -d '{"source_name": "MyCustomSource"}'

# Verify it appears
curl http://localhost:8081/api/sources | grep MyCustomSource
```

### Test 2: Smart Contact Parsing
```bash
# Add opportunity with EMAIL
curl -X POST http://localhost:8081/api/add-opportunity \
  -H "Content-Type: application/json" \
  -d '{
    "company": "Test Corp",
    "role": "QA",
    "source": "LinkedIn",
    "recruiter_contact": "test@example.com",
    "is_remote": 1
  }'

# Check database - email should be in recruiter_email column
sqlite3 data/jobs-tracker.db \
  "SELECT recruiter_phone, recruiter_email FROM opportunities WHERE company='Test Corp';"
# Result: |test@example.com
```

---

## Current System Status

**Sources in Database:** 9
- LinkedIn (default)
- Naukri (default)
- Direct (default)
- Referral (default)
- Other (default)
- TestDevJobs (custom)
- AngelList (custom)
- Wellfound (custom)
- Indeed (custom)

**Test Opportunities Created:** 2
- ID 14: Wellfound Startup (phone: +1-415-555-0199)
- ID 15: Indeed Enterprise (email: sarah.recruiter@indeed.com)

**Services Running:**
- API Server: http://localhost:8081 ✅
- Dashboard: http://localhost:8082 ✅

---

## Cleanup (Optional)

To remove test data:
```bash
# Remove test opportunities
sqlite3 data/jobs-tracker.db \
  "DELETE FROM opportunities WHERE id >= 14;"

# Custom sources will remain (intentional)
# They can be used for real job postings
```

---

## Documentation

Full details available in:
- `TEST_REPORT.md` - Comprehensive test results
- `SESSION_CHANGES_SUMMARY.md` - Complete changelog
- `QUICK_REFERENCE.md` - This file

---

## Troubleshooting

**Problem:** Dropdown shows "Loading..." forever
**Solution:** Check API server is running: `curl http://localhost:8081/api/sources`

**Problem:** New source not appearing
**Solution:** Refresh page - sources loaded on page load

**Problem:** Email stored as phone (or vice versa)
**Solution:** Email detection looks for "@" - ensure emails contain @

---

## Next Steps

1. ✅ All features implemented
2. ✅ All tests passed  
3. ✅ Documentation complete
4. → **Ready for production deployment**
5. → User acceptance testing

**Deployment Command:**
```bash
# Already running! Just verify:
./test-complete-system.sh
```
