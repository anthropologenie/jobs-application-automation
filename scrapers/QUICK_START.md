# SimpleJobScorer - Quick Start Guide

## 5-Minute Setup

### 1. Verify Files
```bash
ls data/resume_config.json          # Configuration file
ls scrapers/simple_scorer.py        # Scoring engine
```

### 2. Run Test Suite
```bash
python3 scrapers/simple_scorer.py
```

### 3. Test Your Own Job
```bash
python3 << 'EOF_PYTHON'
from scrapers.simple_scorer import SimpleJobScorer

scorer = SimpleJobScorer("data/resume_config.json")

job = {
    'title': 'YOUR JOB TITLE HERE',
    'description': 'YOUR JOB DESCRIPTION HERE',
    'location': 'Remote',
    'company': 'Company Name',
    'experience_required': '5-8 years'
}

result = scorer.score_job(job)
print(f"Score: {result['final_score']:.1f}/100")
print(f"Classification: {result['classification']}")
print(f"Recommendation: {result['recommendation']}")
EOF_PYTHON
```

## Scoring Scale

| Score | Classification | Action |
|-------|---------------|--------|
| 85-100 | EXCELLENT | 🎯 Apply immediately |
| 75-84 | HIGH_FIT | ✅ Apply today (auto-import) |
| 65-74 | MEDIUM_FIT | ⚠️ Review carefully |
| 40-64 | LOW_FIT | ❌ Weak match |
| 0-39 | NO_FIT | 🚫 Skip |

## Common Use Cases

### Batch Score Multiple Jobs
```python
from scrapers.simple_scorer import SimpleJobScorer

scorer = SimpleJobScorer()
jobs = [...]  # Your list of jobs

for job in jobs:
    result = scorer.score_job(job)
    if result['should_auto_import']:
        # Import to database
        save_to_opportunities(result)
```

### Filter High-Fit Jobs
```python
high_fit_jobs = [
    scorer.score_job(job) 
    for job in jobs 
    if scorer.score_job(job)['final_score'] >= 75
]
```

### Check for Red Flags
```python
result = scorer.score_job(job)
if result['red_flags']:
    print("⚠️ Warning: Red flags found!")
    for flag in result['red_flags']:
        print(f"  - {flag['flag']} (penalty: {flag['penalty']})")
```

## Configuration Quick Edits

### Adjust Auto-Import Threshold
Edit `data/resume_config.json`:
```json
"auto_import_threshold": 80  // Change from 75 to 80
```

### Add a New Skill
```json
"skills": {
  "critical": {
    "items": {
      "Your New Skill": 9
    }
  }
}
```

### Add a Red Flag
```json
"red_flags": {
  "deal_breakers": {
    "items": {
      "New Red Flag": -15
    }
  }
}
```

## Troubleshooting

### "Configuration file not found"
```bash
# Check file exists
ls data/resume_config.json

# If missing, check path
pwd  # Should be in jobs-application-automation/
```

### "Invalid job data"
```python
# Ensure required fields are present
job_data = {
    'title': 'Required',        # ✅ Required
    'description': 'Required',  # ✅ Required
    'location': 'Optional',     # ⚠️ Optional
    'company': 'Optional'       # ⚠️ Optional
}
```

### Low Scores for Good Jobs
- Add more skills to `data/resume_config.json`
- Add synonyms to `keyword_synonyms` section
- Check skill names match job description exactly

## Next Steps

1. ✅ Test the scorer with your actual job postings
2. ⏳ Implement job scraping (LinkedIn, Naukri, Indeed)
3. ⏳ Create database tables for scored jobs
4. ⏳ Add API endpoints
5. ⏳ Build dashboard UI

## More Information

- **Full Documentation:** `scrapers/SCORER_USAGE.md`
- **Configuration Guide:** `data/SCORING_GUIDE.md`
- **Examples:** `scrapers/example_usage.py`
- **Summary:** `SCORER_IMPLEMENTATION_SUMMARY.md`

## Quick Reference

### Key Methods
```python
scorer = SimpleJobScorer(config_path="data/resume_config.json")
result = scorer.score_job(job_data)
scorer.calculate_skills_score(text)
scorer.calculate_red_flags(text)
scorer.calculate_domain_score(text)
```

### Result Structure
```python
result = {
    'final_score': 68.0,
    'classification': 'MEDIUM_FIT',
    'recommendation': '⚠️ REVIEW CAREFULLY...',
    'should_auto_import': False,
    'breakdown': {...},
    'matched_skills': [...],
    'matched_domains': [...],
    'red_flags': [...]
}
```

### Scoring Formula
```
Final = (Skills × 40%) + (Experience × 20%) + (Domain × 20%)
        + (Location × 10%) + (Red Flags × 10%)
```

---

**Ready to use!** Run `python3 scrapers/simple_scorer.py` to verify installation.
