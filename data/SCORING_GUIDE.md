# Resume Scoring Configuration Guide

## Overview
This configuration file (`resume_config.json`) powers the AI-driven job matching system to automatically score and filter job postings based on your skills, experience, and preferences.

## Configuration Structure

### 1. Profile Section
Basic information about your background and requirements:
- **years_experience**: 7 years (used for experience matching)
- **min_salary_inr**: ₹18,00,000 (jobs below this are penalized)
- **location_preference**: Remote (non-remote jobs lose points)

### 2. Skills Section (40% of total score)

#### Critical Skills (Weight 8-10)
Must-have skills with highest impact. Missing these significantly lowers the match score.
- **Top Skills**: ETL Testing (10), Data Warehouse Testing (10), SQL (10), Python (9), AWS (9)
- **Total**: 15 critical skills

#### High-Value Skills (Weight 6-7)
Strong differentiators that boost your profile.
- **Examples**: API Testing, Postman, GenAI Testing, Kafka, BigQuery
- **Total**: 25 high-value skills

#### Nice-to-Have Skills (Weight 4-5)
Beneficial but not critical.
- **Examples**: Power BI, Tableau, Pandas, Git
- **Total**: 19 nice-to-have skills

### 3. Red Flags Section (10% of total score, NEGATIVE)

#### Deal Breakers (-10 to -15)
Frontend/UI-heavy roles to avoid:
- Cypress (-15), React (-15), Angular (-15), Frontend Testing (-12)

#### Consultancy Signals (-15 to -20)
Strong indicators of body shopping/consulting:
- Client Placement (-20), Third Party (-20), Bench Sales (-20)

#### Manual Testing Only (-5 to -8)
Roles without automation/technical depth:
- Manual Testing Only (-8), Excel-based Testing (-7)

#### Outdated Tech (-3 to -5)
Legacy tools to avoid:
- QTP (-5), UFT (-5), LoadRunner (-4)

### 4. Domains Section (20% of total score)
Industry domains and specializations (Weight 7-8):
- AI/ML Testing, LLM Validation, Data Quality, ETL/DWH
- **Total**: 18 domain categories

### 5. Scoring Weights
Formula for calculating overall match score:

```
Match Score = (Skills × 40%) + (Experience × 20%) + (Domain × 20%) 
              + (Location × 10%) + (Red Flags × 10%)
```

### 6. Filters & Thresholds

- **Auto-import threshold**: 75% (jobs scoring ≥75 are automatically added to pipeline)
- **Min match score**: 65% (jobs below this are not shown)
- **Experience range**: 5-10 years (outside this range loses points)
- **Salary range**: ₹18L - ₹40L

### 7. Job Title Preferences

#### Preferred Titles (Boost +10 points)
- QA Lead, Data QA Engineer, ETL Test Lead, Data Quality Engineer

#### Acceptable Titles (Neutral)
- Senior QA Engineer, Test Automation Engineer, SDET

#### Avoid Titles (Penalty -10 to -15)
- Manual Tester, Junior QA, UI Tester, Cypress Engineer

### 8. Keyword Synonyms
Fuzzy matching for skills with multiple names:
- **ETL** = ETL, Extract Transform Load, Data Pipeline, Data Integration
- **SQL** = SQL, T-SQL, PL/SQL, PostgreSQL, MySQL
- **GenAI** = GenAI, Generative AI, LLM, AI/ML

## How the Scoring Works

### Step 1: Skills Matching (40 points max)
```python
# For each skill in job description:
if skill in critical_skills:
    points += skill_weight * 4  # Max 10 * 4 = 40 points
elif skill in high_value_skills:
    points += skill_weight * 4
elif skill in nice_to_have:
    points += skill_weight * 4

# Normalize to 40 points max
skills_score = min(total_points, 40)
```

### Step 2: Experience Matching (20 points max)
```python
if min_years <= your_experience <= max_years:
    experience_score = 20  # Perfect match
elif your_experience > max_years:
    experience_score = 15  # Overqualified
else:
    experience_score = 10  # Underqualified
```

### Step 3: Domain Matching (20 points max)
```python
# Check job description for domain keywords
matched_domains = [d for d in domains if d in job_description]
domain_score = min(len(matched_domains) * 4, 20)
```

### Step 4: Location Matching (10 points max)
```python
if "remote" in job_location.lower():
    location_score = 10
elif "hybrid" in job_location.lower():
    location_score = 5
else:
    location_score = 0
```

### Step 5: Red Flags (Can go negative!)
```python
red_flag_score = 0
for keyword, penalty in red_flags.items():
    if keyword in job_description:
        red_flag_score += penalty  # Negative values

# Cap at -50 to avoid extreme negatives
red_flag_score = max(red_flag_score, -50)
```

### Step 6: Calculate Final Score
```python
final_score = (skills_score * 0.40) + \
              (experience_score * 0.20) + \
              (domain_score * 0.20) + \
              (location_score * 0.10) + \
              (red_flag_score * 0.10)

# Convert to percentage (0-100)
final_percentage = max(0, min(100, final_score))
```

## Usage in Job Scraping Pipeline

### Automated Workflow:
```
1. Scrape job postings from LinkedIn, Naukri, Indeed, RemoteOK
2. Extract: title, company, description, requirements, salary, location
3. Load resume_config.json
4. Calculate match score using formula above
5. Store in scraped_jobs_archive table with score
6. If score >= 75: Auto-import to opportunities table
7. Display on dashboard "Job Matches" tab
```

### Manual Review:
- **90-100**: Excellent matches (top priority)
- **80-89**: Very good matches (strong consideration)
- **75-79**: Good matches (worth reviewing)
- **65-74**: Acceptable matches (manual review needed)
- **<65**: Poor matches (hidden from view)

## Customization

To adjust the configuration:

1. **Add new skills**: Edit `skills.critical/high_value/nice_to_have.items`
2. **Change weights**: Modify numeric values (1-10 for skills, negative for red flags)
3. **Add red flags**: Add to `red_flags.deal_breakers/consultancy_signals`
4. **Adjust thresholds**: Modify `auto_import_threshold` or `filters.min_match_score`
5. **Change scoring formula**: Update `scoring_weights` (must sum to 1.0)

## Example Modifications

### Make SQL even more critical:
```json
"SQL": 11  // Increase from 10 to 11
```

### Be more strict about consultancies:
```json
"auto_import_threshold": 80  // Increase from 75 to 80
```

### Add new red flag:
```json
"Offshore": -15  // Add to consultancy_signals
```

### Adjust scoring weights (must sum to 1.0):
```json
"scoring_weights": {
  "skills_match": 0.50,      // Increase skills importance
  "experience_match": 0.15,  // Decrease experience
  "domain_match": 0.20,
  "location_match": 0.10,
  "red_flags": 0.05          // Decrease red flag impact
}
```

## Files Generated

- **resume_config.json**: Main configuration file (created)
- **resume_profile.json**: Parsed resume data (to be created by resume_parser.py)
- **scraped_jobs_archive**: Database table storing all scraped jobs with scores
- **job_match_breakdown**: Detailed breakdown of scoring for each job

## Next Steps

1. ✅ Configuration created
2. ⏳ Implement resume_parser.py to generate resume_profile.json
3. ⏳ Create scoring_engine.py to calculate match scores
4. ⏳ Build job scrapers for LinkedIn, Naukri, Indeed
5. ⏳ Add "Job Matches" tab to dashboard

---

**Version**: 1.0.0
**Created**: 2025-11-14
**Last Updated**: 2025-11-14
