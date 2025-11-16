# RemoteOK Integration - Complete Guide

**Created:** 2025-11-14
**Status:** ✅ Production-Ready
**Version:** 1.0.0

---

## Overview

The RemoteOK integration automatically fetches remote job postings, scores them using your resume profile, and stores high-quality matches in the database. It combines web scraping with AI-powered job matching to find relevant opportunities.

---

## Features

✅ **Automatic Job Fetching**
- Fetches up to 100 jobs from RemoteOK API
- Real-time data with no rate limiting needed
- Free public API (no authentication required)

✅ **Smart Filtering**
- Filters by QA, Data, Testing, Automation keywords
- Reduces noise from irrelevant jobs
- Configurable keyword list

✅ **AI-Powered Scoring**
- Uses SimpleJobScorer for consistent evaluation
- Scores based on skills, experience, domain, location
- Detects red flags (frontend, consultancy, etc.)

✅ **Database Storage**
- Stores all scraped jobs with scores
- Prevents duplicates (external_id unique constraint)
- Efficient querying with indexes
- Tracks import status

✅ **Summary Statistics**
- Classification distribution (Excellent, High Fit, Medium, Low, No Fit)
- Top 5 best matches
- Average scores by category

---

## Quick Start

### 1. Run the Scraper

```bash
# Basic usage
python3 scrapers/remoteok_integration.py

# The scraper will:
# 1. Fetch 100 jobs from RemoteOK API
# 2. Filter by QA/Data/Testing keywords
# 3. Score each job using your resume profile
# 4. Store results in database
# 5. Display summary statistics
```

### 2. View Results

```bash
# Use the provided viewer script
./scrapers/view_scraped_jobs.sh 10

# Or query directly
sqlite3 data/jobs-tracker.db "SELECT * FROM scraped_jobs ORDER BY match_score DESC LIMIT 10;"
```

---

## Database Schema

### scraped_jobs Table

```sql
CREATE TABLE scraped_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    external_id TEXT UNIQUE NOT NULL,           -- RemoteOK job ID
    source TEXT DEFAULT 'RemoteOK',             -- Job source
    job_title TEXT NOT NULL,                    -- Position title
    company TEXT NOT NULL,                      -- Company name
    job_url TEXT NOT NULL,                      -- Link to job posting
    location TEXT,                              -- Remote, Hybrid, City
    description TEXT,                           -- Full job description (2000 char limit)
    tags TEXT,                                  -- Comma-separated skill tags
    salary_range TEXT,                          -- Salary (if provided)
    posted_date TEXT,                           -- When job was posted
    match_score REAL,                           -- 0-100 score
    classification TEXT,                        -- EXCELLENT, HIGH_FIT, MEDIUM_FIT, LOW_FIT, NO_FIT
    matched_skills TEXT,                        -- JSON array of matched skills
    matched_domains TEXT,                       -- JSON array of matched domains
    red_flags TEXT,                             -- JSON array of red flags
    recommendation TEXT,                        -- Actionable recommendation
    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,  -- When scraped
    imported_to_opportunities BOOLEAN DEFAULT 0      -- Whether imported to pipeline
);
```

### Indexes

```sql
-- For fast score-based queries
CREATE INDEX idx_scraped_jobs_score ON scraped_jobs(match_score DESC);

-- For filtering by classification
CREATE INDEX idx_scraped_jobs_classification ON scraped_jobs(classification);

-- For finding recent scrapes
CREATE INDEX idx_scraped_jobs_date ON scraped_jobs(scraped_at DESC);
```

---

## Configuration

### Keyword Filtering

Edit `scrapers/remoteok_integration.py` to customize filtering keywords:

```python
def filter_relevant_jobs(self, jobs: List[Dict]) -> List[Dict]:
    keywords = [
        'qa', 'test', 'quality', 'automation', 'sdet',
        'etl', 'data', 'sql', 'analytics', 'validation',
        # Add your custom keywords here
        'your_custom_keyword'
    ]
```

### Fetch Limit

Change the number of jobs to fetch:

```python
# Fetch 200 jobs instead of 100
integrator.run(limit=200, show_stats=True)
```

---

## Usage Examples

### Example 1: Basic Scraping

```python
from scrapers.remoteok_integration import RemoteOKIntegration

# Initialize
integrator = RemoteOKIntegration(db_path="data/jobs-tracker.db")

# Run scraping pipeline
stored, high_fit = integrator.run(limit=100, show_stats=True)

print(f"Stored {stored} jobs, {high_fit} are high-fit")
```

### Example 2: Fetch and Filter Only

```python
integrator = RemoteOKIntegration()

# Fetch jobs
jobs = integrator.fetch_jobs(limit=100)
print(f"Fetched {len(jobs)} jobs")

# Filter relevant jobs
relevant = integrator.filter_relevant_jobs(jobs)
print(f"Found {len(relevant)} relevant jobs")
```

### Example 3: Score Without Storing

```python
integrator = RemoteOKIntegration()
jobs = integrator.fetch_jobs(limit=50)
relevant = integrator.filter_relevant_jobs(jobs)

# Score jobs manually
for job in relevant:
    job_data = {
        'title': job.get('position', ''),
        'description': job.get('description', ''),
        'location': 'Remote',
        'company': job.get('company', ''),
        'tags': ', '.join(job.get('tags', []))
    }

    result = integrator.scorer.score_job(job_data)

    if result['final_score'] >= 75:
        print(f"High fit: {job_data['company']} - {job_data['title']}")
```

### Example 4: Query Database Results

```bash
# View high-scoring jobs only (60%+)
sqlite3 data/jobs-tracker.db << EOF
SELECT
    company,
    job_title,
    CAST(match_score AS INTEGER) || '%' as score,
    classification,
    location
FROM scraped_jobs
WHERE match_score >= 60
ORDER BY match_score DESC;
EOF

# View jobs with specific skills
sqlite3 data/jobs-tracker.db << EOF
SELECT
    company,
    job_title,
    match_score,
    matched_skills
FROM scraped_jobs
WHERE matched_skills LIKE '%SQL%'
ORDER BY match_score DESC
LIMIT 10;
EOF

# View jobs by location
sqlite3 data/jobs-tracker.db << EOF
SELECT *
FROM scraped_jobs
WHERE location LIKE '%Remote%'
  AND match_score >= 50
ORDER BY match_score DESC;
EOF
```

---

## Output Example

```
======================================================================
🚀 RemoteOK Job Scraping Pipeline
======================================================================

🔍 Step 1/3: Fetching jobs from RemoteOK API...
   ✅ Fetched 99 jobs

🎯 Step 2/3: Filtering relevant jobs...
   ✅ Found 77 relevant jobs (filtered by QA/Data/Testing keywords)

⚖️  Step 3/3: Scoring and storing jobs in database...
   Database: data/jobs-tracker.db

   ✅ Stored 77 jobs (0 high-fit candidates)

======================================================================
📊 Scraping Summary
======================================================================

Total Jobs Scraped: 77

📈 Score Distribution:
   🎯 Excellent (85-100):    0 jobs
   ✅ High Fit (75-84):      0 jobs
   ⚠️  Medium Fit (65-74):    0 jobs
   ❌ Low Fit (40-64):       9 jobs
   🚫 No Fit (<40):         68 jobs

🏆 Top 5 Matches:
   1. [64.0%] YLD - Contract Senior Software Engineer
   2. [62.4%] Loop - Data Engineer
   3. [59.2%] TextNow - Senior Data Analyst
   4. [58.4%] Tether Operations Limited - Technical Project Manager
   5. [51.0%] Adyen - Senior Data Engineer Reporting

💡 Next Steps:
   • No high-fit jobs found in this batch
   • Try scraping more jobs or adjust filters

📂 Database Location: data/jobs-tracker.db
```

---

## Automation

### Cron Job Setup

Run scraper daily at 8 AM:

```bash
# Edit crontab
crontab -e

# Add this line:
0 8 * * * cd /home/katte/projects/jobs-application-automation && python3 scrapers/remoteok_integration.py >> logs/remoteok_scraper.log 2>&1
```

### Shell Script Wrapper

Create `scripts/run_remoteok_scraper.sh`:

```bash
#!/bin/bash
cd /home/katte/projects/jobs-application-automation

echo "Starting RemoteOK scraper at $(date)"
python3 scrapers/remoteok_integration.py

# Send notification if high-fit jobs found
HIGH_FIT=$(sqlite3 data/jobs-tracker.db "SELECT COUNT(*) FROM scraped_jobs WHERE classification IN ('EXCELLENT', 'HIGH_FIT') AND DATE(scraped_at) = DATE('now');")

if [ "$HIGH_FIT" -gt 0 ]; then
    echo "🎉 Found $HIGH_FIT high-fit jobs today!"
    # Add email notification here
fi
```

---

## Error Handling

The integration handles common errors gracefully:

### API Errors
```python
# Timeout (15 seconds)
requests.exceptions.Timeout
→ Prints: "❌ Error: Request timed out. Please check your internet connection."

# Connection Error
requests.exceptions.ConnectionError
→ Prints: "❌ Error: Could not connect to RemoteOK API. Please check your internet."

# HTTP Error (4xx, 5xx)
requests.exceptions.HTTPError
→ Prints: "❌ Error: RemoteOK API returned error: [error details]"
```

### Database Errors
```python
# Database locked
sqlite3.OperationalError: database is locked
→ Uses timeout=30.0 to wait for lock release

# Permission denied
sqlite3.OperationalError: unable to open database file
→ Prints helpful error message
```

### Data Errors
```python
# Malformed job data
→ Skips job and continues processing
→ Logs warning with job details
```

---

## Performance

### Metrics
- **API Request Time:** 2-3 seconds
- **Filtering Time:** <100ms for 100 jobs
- **Scoring Time:** 5-10ms per job
- **Database Storage:** 1-2ms per job
- **Total Time:** ~5-10 seconds for 100 jobs

### Optimization Tips

1. **Reduce API Calls:**
   - Cache results locally
   - Only fetch new jobs (check last scraped date)

2. **Faster Scoring:**
   - Pre-compile regex patterns
   - Batch database inserts

3. **Database Performance:**
   - Use WAL mode (already enabled)
   - Vacuum database periodically
   - Add more indexes if needed

---

## Integration with Dashboard

### Future: API Endpoint

Add to `api-server.py`:

```python
@app.route('/api/scraped-jobs')
def get_scraped_jobs():
    conn = sqlite3.connect('data/jobs-tracker.db')
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, company, job_title, match_score, classification,
               location, job_url, scraped_at
        FROM scraped_jobs
        WHERE match_score >= 60
        ORDER BY match_score DESC
        LIMIT 50
    """)

    jobs = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return jsonify(jobs)
```

### Future: Dashboard Tab

Add "Scraped Jobs" tab to dashboard:

```html
<section id="scraped-jobs" class="tab-content">
    <h2>🔍 Recently Scraped Jobs</h2>
    <div id="scraped-jobs-list">
        <!-- Dynamically loaded -->
    </div>
</section>
```

---

## Troubleshooting

### Issue: No jobs fetched
**Cause:** API timeout or connection error
**Solution:**
- Check internet connection
- Try again later (API might be down)
- Increase timeout: `timeout=30`

### Issue: All jobs score low
**Cause:** Keyword filter too broad
**Solution:**
- Refine keywords in `filter_relevant_jobs()`
- Add more specific skills to resume_config.json
- Lower auto_import_threshold

### Issue: Database locked error
**Cause:** Another process accessing database
**Solution:**
- Close other database connections
- Increase timeout (already 30s)
- Use WAL mode (already enabled)

### Issue: Duplicate jobs
**Cause:** Running scraper multiple times
**Solution:**
- `INSERT OR IGNORE` already handles this
- Duplicates are automatically skipped
- Check `external_id` uniqueness

---

## Comparison with Other Sources

| Feature | RemoteOK | LinkedIn | Naukri | Indeed |
|---------|----------|----------|--------|--------|
| API Access | ✅ Free | ❌ Requires auth | ❌ No API | ❌ No API |
| Scraping Difficulty | ⭐ Easy | ⭐⭐⭐⭐⭐ Hard | ⭐⭐⭐ Medium | ⭐⭐⭐ Medium |
| Job Quality | ⭐⭐⭐ Good | ⭐⭐⭐⭐⭐ Excellent | ⭐⭐⭐⭐ Very Good | ⭐⭐⭐⭐ Very Good |
| Remote Focus | ✅ 100% | ⭐⭐⭐ Some | ⭐⭐ Limited | ⭐⭐⭐ Some |
| Update Frequency | Daily | Real-time | Real-time | Real-time |

---

## Next Steps

1. ✅ RemoteOK integration complete
2. ⏳ Add LinkedIn scraper (requires Playwright)
3. ⏳ Add Naukri scraper (India-focused)
4. ⏳ Add Indeed scraper
5. ⏳ Create unified scraping scheduler
6. ⏳ Add email notifications for high-fit jobs
7. ⏳ Build dashboard tab for scraped jobs

---

## Files

```
scrapers/
├── remoteok_integration.py      # Main integration script
├── view_scraped_jobs.sh          # Quick viewer for results
├── simple_scorer.py              # Scoring engine
└── REMOTEOK_INTEGRATION_GUIDE.md # This file

data/
└── jobs-tracker.db               # SQLite database
    └── scraped_jobs              # Table with scraped jobs
```

---

## Example Queries

### Find Data Engineering Jobs

```sql
SELECT company, job_title, match_score, tags
FROM scraped_jobs
WHERE (job_title LIKE '%Data%' OR tags LIKE '%data%')
  AND match_score >= 50
ORDER BY match_score DESC;
```

### Find Remote Jobs in Your Location Preference

```sql
SELECT company, job_title, match_score, location
FROM scraped_jobs
WHERE location LIKE '%Remote%'
  AND match_score >= 60
ORDER BY match_score DESC;
```

### Find Jobs Scraped Today

```sql
SELECT company, job_title, match_score
FROM scraped_jobs
WHERE DATE(scraped_at) = DATE('now')
ORDER BY match_score DESC;
```

### Export High-Fit Jobs to CSV

```bash
sqlite3 -header -csv data/jobs-tracker.db \
  "SELECT company, job_title, match_score, job_url, location
   FROM scraped_jobs
   WHERE match_score >= 70
   ORDER BY match_score DESC;" > high_fit_jobs.csv
```

---

## Summary

**What Works:**
- ✅ Fetches real jobs from RemoteOK API
- ✅ Filters by QA/Data/Testing keywords
- ✅ Scores using SimpleJobScorer
- ✅ Stores in database with proper schema
- ✅ Provides summary statistics
- ✅ Handles errors gracefully
- ✅ Performance: ~5-10 seconds for 100 jobs

**Limitations:**
- RemoteOK tends to have general developer roles
- May not have many Data QA specific positions
- Supplement with LinkedIn, Naukri scrapers for better coverage

**Next Priority:**
- Implement LinkedIn scraper for higher-quality matches
- Add automated daily scraping
- Build dashboard integration

---

**Version:** 1.0.0
**Author:** Karthik Shetty
**Created:** 2025-11-14
**Status:** ✅ Production-Ready
