# Job Scrapers & Scoring System

**Version:** 1.0.0
**Status:** ✅ Production-Ready
**Last Updated:** 2025-11-14

---

## Overview

This directory contains the AI-powered job matching and scraping system that automatically finds, scores, and stores relevant job opportunities based on your resume profile.

---

## Components

### 🎯 Core Scoring Engine

**`simple_scorer.py`** - AI-powered job scoring algorithm
- Evaluates jobs based on skills (40%), experience (20%), domain (20%), location (10%), red flags (10%)
- Scores 0-100 with classifications: EXCELLENT, HIGH_FIT, MEDIUM_FIT, LOW_FIT, NO_FIT
- Uses resume_config.json for personalized matching
- **Performance:** 100-200 jobs/second

### 🌐 Job Source Integrations

**`remoteok_integration.py`** - RemoteOK job scraper
- Fetches from https://remoteok.com/api (free, no auth)
- Filters by QA/Data/Testing keywords
- Scores and stores in database
- **Status:** ✅ Production-ready

**Future Integrations:**
- `linkedin_scraper.py` - LinkedIn job scraper (Playwright)
- `naukri_scraper.py` - Naukri.com scraper (India focus)
- `indeed_scraper.py` - Indeed job scraper

### 🛠️ Utilities

**`view_scraped_jobs.sh`** - Quick database viewer
- Shows top matches with scores
- Classification summary
- Filter examples

**`example_usage.py`** - Working code examples
- Demonstrates scorer API usage
- Batch scoring patterns
- Result processing

---

## Quick Start

### 1. Score a Job (Manual)

```python
from simple_scorer import SimpleJobScorer

scorer = SimpleJobScorer("../data/resume_config.json")

job = {
    'title': 'Data QA Engineer',
    'description': 'SQL, Python, ETL testing, AWS...',
    'location': 'Remote',
    'company': 'TechCorp',
    'experience_required': '5-8 years'
}

result = scorer.score_job(job)
print(f"Score: {result['final_score']:.1f}%")
print(f"Recommendation: {result['recommendation']}")
```

### 2. Scrape RemoteOK Jobs

```bash
# Run the scraper
python3 remoteok_integration.py

# View results
./view_scraped_jobs.sh 10
```

### 3. Query Scraped Jobs

```bash
# Top matches
sqlite3 ../data/jobs-tracker.db "SELECT company, job_title, match_score FROM scraped_jobs ORDER BY match_score DESC LIMIT 10;"

# High-fit jobs only
sqlite3 ../data/jobs-tracker.db "SELECT * FROM scraped_jobs WHERE match_score >= 75;"
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Job Scraping & Scoring Pipeline                           │
└─────────────────────────────────────────────────────────────┘

1. FETCH JOBS
   ├─ RemoteOK API
   ├─ LinkedIn (future)
   ├─ Naukri (future)
   └─ Indeed (future)

2. FILTER BY KEYWORDS
   ├─ qa, test, quality, automation
   ├─ etl, data, sql, analytics
   └─ backend, api, validation

3. SCORE JOBS (SimpleJobScorer)
   ├─ Skills match (40%)
   ├─ Experience match (20%)
   ├─ Domain match (20%)
   ├─ Location match (10%)
   └─ Red flags (10%, negative)

4. STORE IN DATABASE
   ├─ scraped_jobs table
   ├─ Prevent duplicates
   └─ Track import status

5. DISPLAY RESULTS
   ├─ Console output
   ├─ Database queries
   └─ Dashboard (future)
```

---

## Database Schema

### `scraped_jobs` Table

```sql
id                  INTEGER PRIMARY KEY
external_id         TEXT UNIQUE          -- Job ID from source
source              TEXT                 -- 'RemoteOK', 'LinkedIn', etc.
job_title           TEXT
company             TEXT
job_url             TEXT
location            TEXT
description         TEXT (2000 chars)
tags                TEXT (comma-separated)
salary_range        TEXT
posted_date         TEXT
match_score         REAL (0-100)
classification      TEXT                 -- EXCELLENT, HIGH_FIT, etc.
matched_skills      TEXT (JSON)
matched_domains     TEXT (JSON)
red_flags           TEXT (JSON)
recommendation      TEXT
scraped_at          TIMESTAMP
imported_to_opportunities  BOOLEAN
```

**Indexes:**
- `idx_scraped_jobs_score` (match_score DESC)
- `idx_scraped_jobs_classification`
- `idx_scraped_jobs_date` (scraped_at DESC)

---

## Configuration

### Resume Config (`../data/resume_config.json`)

- **59 skills** with weights (Critical: 15, High-Value: 25, Nice-to-Have: 19)
- **36 red flags** with negative penalties
- **18 domains** (AI/ML Testing, Data Quality, ETL/DWH, etc.)
- **Scoring weights:** Skills 40%, Experience 20%, Domain 20%, Location 10%, Red Flags 10%
- **Auto-import threshold:** 75%

### Keyword Filters (RemoteOK)

Edit `remoteok_integration.py`:

```python
keywords = [
    'qa', 'test', 'quality', 'automation', 'sdet',
    'etl', 'data', 'sql', 'analytics', 'validation',
    # Add custom keywords
]
```

---

## File Reference

| File | Size | Purpose | Status |
|------|------|---------|--------|
| `simple_scorer.py` | 22 KB | Core scoring engine | ✅ Ready |
| `remoteok_integration.py` | 22 KB | RemoteOK scraper | ✅ Ready |
| `view_scraped_jobs.sh` | 1.5 KB | Database viewer | ✅ Ready |
| `example_usage.py` | 6 KB | Usage examples | ✅ Ready |
| `__init__.py` | 428 B | Package init | ✅ Ready |
| `SCORER_USAGE.md` | 12 KB | API documentation | ✅ Complete |
| `QUICK_START.md` | 4 KB | Quick reference | ✅ Complete |
| `REMOTEOK_INTEGRATION_GUIDE.md` | 15 KB | Integration docs | ✅ Complete |
| `README.md` | - | This file | ✅ Complete |

---

## Performance

| Metric | Value |
|--------|-------|
| **Scoring Speed** | 100-200 jobs/second |
| **API Request** | 2-3 seconds (RemoteOK) |
| **Filtering** | <100ms for 100 jobs |
| **Database Storage** | 1-2ms per job |
| **Total Pipeline** | ~8 seconds for 100 jobs |
| **Memory Usage** | <100 MB |

---

## Usage Examples

### Example 1: Batch Score Jobs

```python
from simple_scorer import SimpleJobScorer

scorer = SimpleJobScorer()
jobs = [...]  # Your job list

high_fit_jobs = []
for job in jobs:
    result = scorer.score_job(job)
    if result['final_score'] >= 75:
        high_fit_jobs.append(result)

print(f"Found {len(high_fit_jobs)} high-fit jobs")
```

### Example 2: Run RemoteOK Scraper

```python
from remoteok_integration import RemoteOKIntegration

integrator = RemoteOKIntegration()
stored, high_fit = integrator.run(limit=100, show_stats=True)
```

### Example 3: Query Database

```python
import sqlite3

conn = sqlite3.connect('../data/jobs-tracker.db')
cursor = conn.cursor()

cursor.execute("""
    SELECT company, job_title, match_score
    FROM scraped_jobs
    WHERE match_score >= 70
    ORDER BY match_score DESC
""")

for company, title, score in cursor.fetchall():
    print(f"{score:.0f}% - {company}: {title}")
```

---

## Automation

### Daily Scraping with Cron

```bash
# Edit crontab
crontab -e

# Add line (runs daily at 8 AM)
0 8 * * * cd /home/katte/projects/jobs-application-automation && python3 scrapers/remoteok_integration.py >> logs/remoteok.log 2>&1
```

### Shell Script Wrapper

```bash
#!/bin/bash
cd /home/katte/projects/jobs-application-automation

python3 scrapers/remoteok_integration.py

# Check for high-fit jobs
HIGH_FIT=$(sqlite3 data/jobs-tracker.db "SELECT COUNT(*) FROM scraped_jobs WHERE classification IN ('EXCELLENT', 'HIGH_FIT') AND DATE(scraped_at) = DATE('now');")

if [ "$HIGH_FIT" -gt 0 ]; then
    echo "🎉 Found $HIGH_FIT high-fit jobs today!"
    # Send email notification
fi
```

---

## Troubleshooting

### Issue: No jobs found
**Solution:**
- Check internet connection
- Verify API is accessible: `curl https://remoteok.com/api`
- Check logs for errors

### Issue: Low scores for all jobs
**Solution:**
- Review resume_config.json skills
- Adjust keyword filters
- Lower auto_import_threshold

### Issue: Database locked
**Solution:**
- Close other database connections
- Wait and retry (30s timeout already configured)

---

## Next Steps

### Immediate
- ✅ RemoteOK integration complete
- ✅ Scoring engine tested with real data
- ✅ Database schema created

### Week 1
- ☐ Add LinkedIn scraper (Playwright)
- ☐ Set up daily cron job
- ☐ Email notifications for high-fit jobs

### Week 2
- ☐ Add Naukri scraper (India focus)
- ☐ Add Indeed scraper
- ☐ Unified scraping scheduler

### Week 3
- ☐ API endpoint: `GET /api/scraped-jobs`
- ☐ Dashboard tab: "Job Matches"
- ☐ Import to opportunities feature

---

## Documentation

- **API Reference:** `SCORER_USAGE.md`
- **Quick Start:** `QUICK_START.md`
- **RemoteOK Guide:** `REMOTEOK_INTEGRATION_GUIDE.md`
- **Implementation Summary:** `../SCORER_IMPLEMENTATION_SUMMARY.md`
- **Scoring Algorithm:** `../data/SCORING_GUIDE.md`

---

## Testing

```bash
# Test scorer
python3 simple_scorer.py

# Test RemoteOK integration
python3 remoteok_integration.py

# Test examples
python3 example_usage.py

# View results
./view_scraped_jobs.sh 10
```

---

## Support

For issues or questions:
1. Check documentation files listed above
2. Review test output for errors
3. Check database for data integrity
4. Verify configuration files exist

---

**Status:** ✅ Production-Ready
**Last Test:** 2025-11-14 (77 jobs scraped successfully)
**Next Milestone:** LinkedIn integration
