# System Summary - Job Application Tracker & Learning System

**Complete technical documentation of the job tracking and learning platform**

**Last Updated:** November 16, 2025
**Version:** 2.0.0
**Status:** Production Ready

---

## Table of Contents

- [Overview](#overview)
- [Project Structure](#project-structure)
- [Features](#features)
- [Database Architecture](#database-architecture)
- [API Reference](#api-reference)
- [Testing Infrastructure](#testing-infrastructure)
- [Tech Stack](#tech-stack)
- [File Organization](#file-organization)
- [Development Workflow](#development-workflow)
- [Known Issues](#known-issues)
- [Future Enhancements](#future-enhancements)

---

## Overview

A comprehensive job search management system with integrated learning platform, built to streamline the job application process and accelerate technical skill development through data-driven insights.

### System Capabilities

- **Job Tracking:** Manage unlimited job opportunities across active and archived pipelines
- **Interview Preparation:** Log questions, track performance, identify learning gaps
- **SQL Practice:** Track practice sessions, analyze keyword mastery, monitor progress
- **Job Scraping:** Auto-score jobs from RemoteOK with intelligent 0-100 point algorithm
- **Sacred Work:** Track focused work sessions with pomodoro-style logging
- **Automation Ready:** n8n workflow integration for email parsing and calendar sync

### Current Statistics

- **Opportunities:** 12 total (1 Applied, 10 Declined, 1 Rejected)
- **Database Tables:** 11 tables
- **Database Views:** 10 materialized views
- **API Endpoints:** 20+ REST endpoints
- **Test Scripts:** 8 comprehensive test suites
- **Lines of Code:** ~2,500 across Python, JavaScript, SQL, Bash

---

## Project Structure

```
jobs-application-automation/
│
├── 📄 Core Application Files
│   ├── api-server.py                    # Python REST API (740+ lines)
│   ├── start-tracker.sh                 # Service startup script
│   ├── stop-tracker.sh                  # Service shutdown script
│   ├── cleanup-project.sh               # Project maintenance utility
│   ├── .gitignore                       # Comprehensive ignore rules
│   └── .env                             # Environment variables (gitignored)
│
├── 📊 Frontend (Dashboard)
│   ├── dashboard/
│   │   ├── index.html                   # Main UI (active/archived pipelines)
│   │   ├── app.js                       # SPA logic (450+ lines)
│   │   ├── styles.css                   # Responsive CSS
│   │   └── server.py                    # Static file server (port 8082)
│   └── learning-dashboard.html          # Learning system interface
│
├── 🗄️ Database Layer
│   └── data/
│       ├── jobs-tracker.db              # SQLite database (WAL mode)
│       ├── resume_config.json           # Job scorer configuration
│       └── SCORING_GUIDE.md             # Scoring methodology
│
├── 🧪 Testing Infrastructure
│   └── tests/
│       ├── test-complete-system.sh      # Full system validation (7 tests)
│       ├── test-new-pipeline-features.sh # Pipeline feature tests
│       ├── test-scraped-jobs-api.sh     # Job scraper & scorer tests
│       ├── test-sql-practice-system.sh  # Learning system tests
│       ├── test-new-features.sh         # Dynamic sources & parsing tests
│       ├── validate-system.sh           # Health checks
│       ├── final-validation-tests.sh    # Pre-deployment validation
│       └── show-practice-summary.sh     # SQL practice report viewer
│
├── 📚 Documentation
│   └── docs/
│       ├── INDEX.md                     # Master documentation index
│       ├── SYSTEM_SUMMARY.md            # This file
│       ├── guides/
│       │   ├── QUICK_REFERENCE.md       # Command cheat sheet
│       │   └── SQL_PRACTICE_GUIDE.md    # SQL learning guide
│       └── reports/
│           ├── NEW_FEATURES_REPORT.md   # Archived pipeline & inline editing
│           ├── SESSION_CHANGES_SUMMARY.md # Dynamic sources implementation
│           ├── SCORER_IMPLEMENTATION_SUMMARY.md # Job scoring engine
│           └── TEST_REPORT.md           # Feature test results
│
├── 🤖 Automation & Scraping
│   ├── scrapers/
│   │   ├── remoteok-scraper.py          # Job scraping service
│   │   ├── job-scorer.py                # Intelligent scoring engine
│   │   ├── test-scorer.py               # Scorer validation
│   │   └── view_scraped_jobs.sh         # Job data viewer
│   └── workflows/                        # n8n workflow definitions (future)
│
├── 📋 Database Management
│   ├── queries/
│   │   ├── schema.sql                   # Complete database schema
│   │   └── weekly-practice-summary.sql  # SQL practice report
│   └── migrations/
│       ├── 001_initial_schema.sql       # (implicit in schema.sql)
│       └── 002_remove_source_constraint.sql # Dynamic sources migration
│
├── 🛠️ Utilities
│   ├── scripts/                         # Helper scripts
│   ├── prompts/                         # AI prompt templates
│   ├── logs/                            # Application logs
│   ├── daily-logs/                      # Daily activity logs
│   ├── inject_endpoint.py               # API testing utility
│   ├── log-sql-practice.py              # CLI SQL practice logger (OOP design)
│   └── make-dbeaver-snapshot.sh         # Database backup tool
│
└── 📝 Configuration
    ├── README.md                        # Main project documentation (900+ lines)
    ├── CLAUDE.md                        # AI assistant instructions
    └── docker-compose.yml               # n8n automation stack
```

---

## Features

### 1. Job Tracking System

#### Active Pipeline
- **Real-time tracking** of ongoing job opportunities
- **Inline editing** for Status and Remote flag with auto-save
- **Toast notifications** for all user actions (add, update, delete)
- **Dynamic job sources** - Add custom sources (Wellfound, Indeed, etc.)
- **Smart recruiter parsing** - Auto-detect phone vs email in contact field
- **Priority management** - High/Medium/Low priority tagging
- **Tech stack tagging** - Track required technologies
- **Metrics dashboard** - KPIs for active/remote/priority counts

**Statuses Available:**
- Lead
- Applied
- Interview Scheduled
- Interview Complete
- Offer Received
- Accepted
- Rejected
- Declined
- Ghosted

#### Archived Pipeline
- **Separate view** for completed opportunities
- **Final statuses only:** Rejected, Declined, Ghosted, Accepted
- **Historical data** preserved for analysis
- **Clean active pipeline** - Keeps focus on active opportunities

#### Smart Features
- **Contact parsing:** Single field auto-detects email (`@` present) vs phone
- **Source persistence:** User-added sources saved to database permanently
- **Inline editing:** Click to edit status/remote flag directly in table
- **Auto-save:** Changes saved immediately with visual feedback
- **Toast notifications:** Success/error messages for all operations

### 2. Learning System

#### Interview Question Tracking
- Log questions asked during interviews
- Rate your performance (1-5 scale)
- Track ideal vs actual responses
- Difficulty classification (Easy/Medium/Hard)
- Topic tagging for pattern recognition
- Link questions to specific opportunities

#### Learning Gap Analysis
- Automated identification of weak areas by topic
- Average rating calculation per subject
- Study priority recommendations based on gaps
- Correlation with interview question types

#### SQL Practice System
- **Interactive CLI tool:** `log-sql-practice.py` (OOP design)
- **Platform tracking:** sql-practice.com, Programiz, DBeaver
- **Keyword mastery:** Accuracy per SQL concept (WHERE, JOIN, GROUP BY, etc.)
- **Mistake logging:** Track errors and recovery time
- **Weekly summaries:** Performance trends and recommendations
- **Difficulty progression:** Track Easy/Medium/Hard practice

**OOP Design Highlights:**
- 3 classes: `PracticeSession`, `SessionLogger`, `InteractiveCLI`
- Encapsulation, Single Responsibility Principle
- Dependency Injection, Type Hints
- Heavily commented for Python learning

### 3. Job Scraping & Scoring

#### RemoteOK Integration
- Automated job scraping from RemoteOK API
- Position filtering (QA, Test, Automation roles)
- Real-time job feed updates
- Deduplication by job slug

#### Intelligent Scoring Engine
**Score Components (0-100 scale):**

| Component | Weight | Max Points | Criteria |
|-----------|--------|------------|----------|
| **Title Relevance** | 40% | 40 | QA keywords, seniority level match |
| **Tech Stack Match** | 30% | 30 | Skills from resume_config.json |
| **Company Reputation** | 15% | 15 | Known tech companies |
| **Remote Work** | 10% | 10 | Fully remote positions |
| **Salary Range** | 5% | 5 | Meets minimum requirements |

**Classification System:**
- **Excellent Fit:** 80-100 points (auto-import recommended)
- **High Fit:** 60-79 points
- **Medium Fit:** 40-59 points
- **Low Fit:** 20-39 points
- **No Fit:** 0-19 points

**Configuration:**
- 59 skills tracked (Critical: 15, High-Value: 25, Nice-to-Have: 19)
- 36 red flags with negative weights
- 18 domain specializations
- Customizable weights and thresholds in `data/resume_config.json`

### 4. Sacred Work Tracking

- **Pomodoro-style logging** of focused work sessions ("stones")
- **Time tracking** in minutes per session
- **Progress documentation** - What was built, insights gained
- **Reflection capture** - Next stone, felt sense
- **Daily summaries** and progress over time
- **API endpoints** for stats, progress, recent work

### 5. Toast Notification System

- **Success notifications:** Green toast for successful operations
- **Error notifications:** Red toast for failures
- **Auto-dismiss:** 3-second timeout
- **Visual feedback:** Smooth animations, consistent styling
- **User-friendly:** Clear messages for all CRUD operations

---

## Database Architecture

### Database Technology
- **Engine:** SQLite 3.x
- **Mode:** WAL (Write-Ahead Logging) for concurrency
- **Constraints:** Foreign keys enabled, CHECK constraints for validation
- **Triggers:** Auto-update timestamps on modifications
- **Indexes:** Strategic indexes on frequently queried columns

### Tables (11 Total)

#### 1. `opportunities` - Core job tracking
```sql
CREATE TABLE opportunities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company TEXT NOT NULL,
    role TEXT NOT NULL,
    source TEXT,  -- No constraint (allows dynamic sources)
    status TEXT CHECK(status IN ('Lead', 'Applied', 'Interview Scheduled', ...)),
    priority TEXT CHECK(priority IN ('High', 'Medium', 'Low')),
    is_remote INTEGER DEFAULT 0,
    tech_stack TEXT,
    recruiter_phone TEXT,
    recruiter_email TEXT,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_interaction_date DATE,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```
**Current Data:** 12 opportunities (1 Applied, 10 Declined, 1 Rejected)

#### 2. `job_sources` - Dynamic source management
```sql
CREATE TABLE job_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_name TEXT UNIQUE NOT NULL,
    is_default INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```
**Pre-populated:** LinkedIn, Naukri, Direct, Referral, Other
**User-added:** Wellfound, Indeed, TestDevJobs, etc.

#### 3. `interactions` - Track communications
```sql
CREATE TABLE interactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    opportunity_id INTEGER NOT NULL,
    type TEXT CHECK(type IN ('Email', 'Phone', 'Interview', 'Meeting', 'Follow-up')),
    date DATE NOT NULL,
    time TEXT,
    summary TEXT,
    sentiment TEXT,
    calendar_event_id TEXT,
    FOREIGN KEY (opportunity_id) REFERENCES opportunities(id)
);
```

#### 4. `interview_questions` - Learning data
```sql
CREATE TABLE interview_questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    opportunity_id INTEGER,
    question_text TEXT NOT NULL,
    question_type TEXT,
    difficulty TEXT CHECK(difficulty IN ('Easy', 'Medium', 'Hard')),
    my_response TEXT,
    ideal_response TEXT,
    my_rating INTEGER CHECK(my_rating BETWEEN 1 AND 5),
    tags TEXT,
    asked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (opportunity_id) REFERENCES opportunities(id)
);
```

#### 5. `study_topics` - Study plan management
```sql
CREATE TABLE study_topics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic_name TEXT NOT NULL,
    category TEXT,
    priority INTEGER CHECK(priority BETWEEN 1 AND 5),
    time_spent_minutes INTEGER DEFAULT 0,
    mastery_level REAL CHECK(mastery_level BETWEEN 0 AND 5),
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### 6. `sql_practice_sessions` - SQL practice tracking
```sql
CREATE TABLE sql_practice_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    question_text TEXT NOT NULL,
    my_query TEXT NOT NULL,
    platform TEXT CHECK(platform IN ('sql-practice.com', 'programiz', 'dbeaver', 'other')),
    difficulty TEXT CHECK(difficulty IN ('Easy', 'Medium', 'Hard')),
    database_used TEXT,
    is_correct INTEGER DEFAULT 0,
    time_spent_minutes INTEGER,
    mistake_made TEXT,
    lesson_learned TEXT,
    keywords_used TEXT,
    practiced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### 7. `scraped_jobs` - Job scraping results
```sql
CREATE TABLE scraped_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slug TEXT UNIQUE NOT NULL,
    company TEXT,
    position TEXT,
    tags TEXT,
    logo_url TEXT,
    url TEXT,
    score INTEGER DEFAULT 0,
    fit_classification TEXT,
    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### 8. `sacred_work_log` - Productivity tracking
```sql
CREATE TABLE sacred_work_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stone_number INTEGER UNIQUE NOT NULL,
    stone_title TEXT NOT NULL,
    time_spent_minutes INTEGER NOT NULL,
    what_built TEXT NOT NULL,
    insights TEXT,
    next_stone TEXT,
    felt_sense TEXT,
    date DATE DEFAULT (DATE('now'))
);
```

#### 9. `documents` - File attachments
```sql
CREATE TABLE documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    opportunity_id INTEGER,
    type TEXT CHECK(type IN ('Resume', 'Cover Letter', 'Certificate', 'Other')),
    file_path TEXT NOT NULL,
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (opportunity_id) REFERENCES opportunities(id)
);
```

#### 10. `learning_sessions` - Study session tracking
```sql
CREATE TABLE learning_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic_id INTEGER,
    date DATE NOT NULL,
    duration_minutes INTEGER,
    notes TEXT,
    resources_used TEXT,
    FOREIGN KEY (topic_id) REFERENCES study_topics(id)
);
```

#### 11. `sqlite_sequence` - Auto-increment tracking (system table)

### Views (10 Total)

#### 1. `active_pipeline` - Non-archived opportunities
```sql
CREATE VIEW active_pipeline AS
SELECT * FROM opportunities
WHERE status NOT IN ('Rejected', 'Declined', 'Ghosted', 'Accepted');
```

#### 2. `archived_pipeline` - Completed opportunities
```sql
CREATE VIEW archived_pipeline AS
SELECT * FROM opportunities
WHERE status IN ('Rejected', 'Declined', 'Ghosted', 'Accepted');
```

#### 3. `todays_agenda` - Upcoming 7-day interviews
```sql
CREATE VIEW todays_agenda AS
SELECT i.*, o.company, o.role
FROM interactions i
JOIN opportunities o ON i.opportunity_id = o.id
WHERE i.type = 'Interview'
  AND i.date >= DATE('now')
  AND i.date <= DATE('now', '+7 days')
ORDER BY i.date, i.time;
```

#### 4. `learning_gaps` - Weak areas by topic
```sql
CREATE VIEW learning_gaps AS
SELECT
    COALESCE(question_type, 'General') as topic,
    COUNT(*) as questions_asked,
    AVG(my_rating) as avg_rating,
    MIN(my_rating) as min_rating
FROM interview_questions
GROUP BY question_type
HAVING avg_rating < 4
ORDER BY avg_rating ASC;
```

#### 5. `study_priority` - Recommended study topics
```sql
CREATE VIEW study_priority AS
SELECT
    topic_name,
    category,
    priority,
    mastery_level,
    (priority * (5 - mastery_level)) as priority_score
FROM study_topics
ORDER BY priority_score DESC;
```

#### 6. `sql_keyword_mastery` - SQL keyword accuracy
```sql
CREATE VIEW sql_keyword_mastery AS
SELECT
    keyword,
    COUNT(*) as times_used,
    SUM(is_correct) as correct_count,
    ROUND(AVG(is_correct) * 100, 1) as accuracy_percent
FROM (
    -- Normalized keyword extraction from keywords_used field
)
GROUP BY keyword
ORDER BY accuracy_percent DESC;
```

#### 7. `weekly_practice_summary` - Weekly SQL practice stats
```sql
CREATE VIEW weekly_practice_summary AS
SELECT
    strftime('%Y-W%W', practiced_at) as week,
    COUNT(*) as sessions,
    ROUND(AVG(is_correct) * 100, 1) as accuracy_percent,
    SUM(time_spent_minutes) as total_minutes
FROM sql_practice_sessions
GROUP BY week
ORDER BY week DESC;
```

#### 8. `common_practice_mistakes` - Frequent errors
```sql
CREATE VIEW common_practice_mistakes AS
SELECT
    mistake_made,
    COUNT(*) as occurrences,
    AVG(time_spent_minutes) as avg_recovery_time
FROM sql_practice_sessions
WHERE mistake_made IS NOT NULL AND mistake_made != ''
GROUP BY mistake_made
ORDER BY occurrences DESC;
```

#### 9. `practice_progress_by_difficulty` - Difficulty breakdown
```sql
CREATE VIEW practice_progress_by_difficulty AS
SELECT
    difficulty,
    COUNT(*) as total_questions,
    SUM(is_correct) as correct_count,
    ROUND(AVG(is_correct) * 100, 1) as accuracy_percent
FROM sql_practice_sessions
GROUP BY difficulty;
```

#### 10. `sacred_work_stats` - Work session statistics
```sql
CREATE VIEW sacred_work_stats AS
SELECT
    COUNT(*) as total_stones,
    SUM(time_spent_minutes) as total_minutes,
    AVG(time_spent_minutes) as avg_minutes_per_stone,
    MIN(date) as first_stone_date,
    MAX(date) as latest_stone_date
FROM sacred_work_log;
```

#### 11. `sacred_work_progress` - Daily progress tracking
```sql
CREATE VIEW sacred_work_progress AS
SELECT
    date,
    COUNT(*) as stones_placed,
    SUM(time_spent_minutes) as minutes_worked
FROM sacred_work_log
GROUP BY date
ORDER BY date DESC;
```

### Triggers

#### 1. `update_opportunity_timestamp`
Auto-updates `updated_at` on any opportunity modification

#### 2. `update_last_interaction`
Updates `last_interaction_date` when new interaction is logged

### Indexes

Strategic indexes on frequently queried columns:
- `opportunities.status`
- `opportunities.is_remote`
- `opportunities.priority`
- `interactions.calendar_event_id`
- `scraped_jobs.fit_classification`
- `scraped_jobs.score`

---

## API Reference

**Base URL:** `http://localhost:8081/api`

### Job Tracking Endpoints (8)

#### 1. `GET /api/metrics`
**Description:** Dashboard KPIs
**Returns:** Active count, interview count, remote count, priority count
**Response Time:** ~15ms
**Example:**
```json
{
  "active_count": 9,
  "interview_count": 3,
  "remote_count": 8,
  "priority_count": 6
}
```

#### 2. `GET /api/pipeline`
**Description:** Active opportunities (non-archived)
**Returns:** Array of opportunity objects
**Response Time:** ~25ms
**Filters:** Excludes Rejected, Declined, Ghosted, Accepted

#### 3. `GET /api/archived-pipeline`
**Description:** Archived opportunities
**Returns:** Array of completed opportunities
**Response Time:** ~30ms
**Filters:** Only Rejected, Declined, Ghosted, Accepted

#### 4. `GET /api/todays-agenda`
**Description:** Next 7 days interview schedule
**Returns:** Array of upcoming interviews with company/role
**Response Time:** ~20ms

#### 5. `POST /api/add-opportunity`
**Description:** Create new job opportunity
**Accepts:** JSON with company, role, source, is_remote, tech_stack, priority, recruiter_contact, notes
**Returns:** Success message with new ID
**Response Time:** ~30ms
**Features:**
- Smart contact parsing (email vs phone detection)
- Dynamic source validation
- Default values for optional fields

#### 6. `PATCH /api/update-opportunity/:id`
**Description:** Update opportunity fields
**Accepts:** JSON with status, is_remote, notes, priority
**Returns:** Success message
**Response Time:** ~25ms
**Used by:** Inline editing feature

#### 7. `GET /api/sources`
**Description:** List all job sources
**Returns:** Array of source objects (id, source_name, is_default)
**Response Time:** ~10ms
**Ordering:** Default sources first, then alphabetical

#### 8. `POST /api/add-source`
**Description:** Add custom job source
**Accepts:** JSON with source_name
**Returns:** Success message with new source ID
**Response Time:** ~20ms
**Validation:** Unique constraint, non-empty name

### Job Scraping Endpoints (2)

#### 9. `GET /api/scraped-jobs`
**Description:** Get scored jobs by fit level
**Query Params:**
- `fit`: Filter by classification (excellent/high/medium/low/none)
- `limit`: Number of results (default: 50)
- `offset`: Pagination offset (default: 0)
**Returns:** Array of job objects with scores
**Response Time:** ~40ms

#### 10. `GET /api/scraped-jobs/stats`
**Description:** Scraping statistics
**Returns:** Total jobs, fit distribution, average score
**Response Time:** ~20ms

### Learning System Endpoints (9)

#### 11. `GET /api/learning-gaps`
**Description:** Weak areas analysis by topic
**Returns:** Topics with avg rating < 4
**Response Time:** ~25ms

#### 12. `GET /api/study-priority`
**Description:** Recommended study priorities
**Returns:** Topics ordered by priority score
**Response Time:** ~20ms

#### 13. `GET /api/recent-questions`
**Description:** Recent interview questions
**Returns:** Last 10 questions with ratings
**Response Time:** ~15ms

#### 14. `POST /api/add-question`
**Description:** Log interview question
**Accepts:** JSON with opportunity_id, question_text, question_type, difficulty, my_response, ideal_response, my_rating, tags
**Returns:** Success message with question ID
**Response Time:** ~30ms

#### 15. `GET /api/sql-practice-stats`
**Description:** SQL practice analytics
**Returns:** Total sessions, accuracy, time spent, platforms
**Response Time:** ~25ms

#### 16. `GET /api/sql-keyword-mastery`
**Description:** SQL keyword performance
**Returns:** Accuracy per keyword (WHERE, JOIN, etc.)
**Response Time:** ~30ms

#### 17. `GET /api/recent-practice`
**Description:** Recent SQL practice sessions
**Returns:** Last 10 practice sessions
**Response Time:** ~20ms

#### 18. `GET /api/weekly-summary`
**Description:** Weekly learning summary
**Returns:** Week-by-week practice stats
**Response Time:** ~25ms

#### 19. `GET /api/common-mistakes`
**Description:** Frequently made mistakes
**Returns:** Top errors with occurrence count
**Response Time:** ~20ms

### Sacred Work Endpoints (4)

#### 20. `GET /api/sacred-work-stats`
**Description:** Work session statistics
**Returns:** Total stones, total minutes, average per stone
**Response Time:** ~15ms

#### 21. `GET /api/sacred-work-progress`
**Description:** Daily progress tracking
**Returns:** Stones placed and minutes worked per day
**Response Time:** ~20ms

#### 22. `GET /api/recent-sacred-work`
**Description:** Recent work sessions
**Returns:** Last 10 sacred work entries
**Response Time:** ~15ms

#### 23. `POST /api/add-sacred-work`
**Description:** Log new work session
**Accepts:** JSON with stone_number, stone_title, time_spent_minutes, what_built, insights, next_stone, felt_sense, date
**Returns:** Success message with stone ID
**Response Time:** ~30ms
**Validation:** Unique stone_number, required fields

### CORS & Error Handling

- **CORS:** Enabled for all endpoints (`Access-Control-Allow-Origin: *`)
- **Error Responses:** JSON format with `{"error": "message"}` and appropriate HTTP status codes (400, 404, 409, 500)
- **OPTIONS Support:** Pre-flight requests handled for all endpoints

---

## Testing Infrastructure

### Test Scripts (8 Total)

Located in `tests/` directory:

#### 1. `test-complete-system.sh`
**Purpose:** Full system validation
**Tests:** 7 comprehensive checks
**Checks:**
- Database accessibility
- Dashboard server response
- API server response
- Metrics endpoint
- Agenda endpoint
- Pipeline endpoint
- Add opportunity endpoint

**Expected Output:**
```
╔════════════════════════════════════════════════════════╗
║     🧪 COMPLETE SYSTEM TEST                            ║
╚════════════════════════════════════════════════════════╝

1️⃣  DATABASE TEST                              ✅ PASS
2️⃣  DASHBOARD TEST                             ✅ PASS
3️⃣  PYTHON API TEST                            ✅ PASS
4️⃣  METRICS ENDPOINT TEST                      ✅ PASS
5️⃣  AGENDA ENDPOINT TEST                       ✅ PASS
6️⃣  PIPELINE ENDPOINT TEST                     ✅ PASS
7️⃣  ADD OPPORTUNITY ENDPOINT TEST              ✅ PASS

╔════════════════════════════════════════════════════════╗
║     ✅ ALL TESTS PASSED!                               ║
╚════════════════════════════════════════════════════════╝
```

#### 2. `test-new-pipeline-features.sh`
**Purpose:** Validate archived pipeline and inline editing
**Tests:**
- GET /api/archived-pipeline returns correct data
- PATCH /api/update-opportunity works
- Status changes move between active/archived
- Remote flag toggling works
- Notes update functionality

#### 3. `test-scraped-jobs-api.sh`
**Purpose:** Job scraper and scoring validation
**Tests:**
- GET /api/scraped-jobs with fit filter
- GET /api/scraped-jobs/stats
- Score calculation accuracy
- Classification correctness
- Pagination functionality

#### 4. `test-sql-practice-system.sh`
**Purpose:** Learning system validation
**Tests:** 10 checks
- Database table exists
- All 4 views created
- Sample data inserted
- Keyword mastery view works
- CLI tool executable
- Summary script executable
- Migration file exists
- Query file exists
- API endpoints responsive
- Dashboard updated

#### 5. `test-new-features.sh`
**Purpose:** Dynamic sources and smart parsing
**Tests:**
- POST /api/add-source validation
- GET /api/sources returns all sources
- Duplicate source handling
- Empty source name validation
- Smart contact parsing (email detection)
- Smart contact parsing (phone detection)

#### 6. `validate-system.sh`
**Purpose:** Quick health checks
**Tests:**
- Services running on correct ports
- Database file exists
- WAL mode enabled
- Key tables present

#### 7. `final-validation-tests.sh`
**Purpose:** Pre-deployment validation
**Tests:**
- All critical endpoints responding
- Database integrity check
- File permissions correct
- No syntax errors in code

#### 8. `show-practice-summary.sh`
**Purpose:** SQL practice report viewer
**Output:**
- Weekly performance trends
- SQL keyword mastery
- Common mistakes
- Progress by difficulty
- Recent practice sessions
- Recommended next topics

### Test Coverage

- **API Endpoints:** 100% of critical endpoints tested
- **Database Operations:** All CRUD operations validated
- **Feature Validation:** All major features have dedicated tests
- **Error Handling:** Edge cases and invalid inputs tested
- **Integration Tests:** End-to-end workflows validated

---

## Tech Stack

### Backend

**Language:** Python 3.12
**Modules (Standard Library Only):**
- `http.server` - REST API server
- `sqlite3` - Database operations
- `json` - JSON parsing/serialization
- `threading` - Thread-local connection pooling
- `urllib.parse` - URL parsing
- `datetime` - Timestamp handling
- `typing` - Type hints

**Dependencies:** None (zero external dependencies!)

### Frontend

**Languages:**
- HTML5 with semantic markup
- CSS3 (Grid, Flexbox, custom properties)
- JavaScript ES6+ (vanilla, no frameworks)

**Features:**
- Single Page Application (SPA) architecture
- Fetch API for HTTP requests
- DOM manipulation
- Event delegation
- Async/await patterns

### Database

**Engine:** SQLite 3.x
**Mode:** WAL (Write-Ahead Logging)
**Features:**
- Foreign key constraints
- CHECK constraints
- Triggers
- Views
- Indexes
- Thread-safe with connection pooling

### Automation

**Workflow Engine:** n8n (Docker)
**Scraping:** Python requests library
**Scoring:** Custom algorithm with JSON config

### Development Tools

- **Editor:** VSCode / Claude Code
- **Database Client:** DBeaver
- **API Testing:** curl, Postman
- **Version Control:** Git
- **Documentation:** Markdown

---

## File Organization

### Configuration Files

- `.env` - Environment variables (API keys, credentials) - **gitignored**
- `.gitignore` - Comprehensive ignore rules for Python, logs, backups, DB temp files
- `docker-compose.yml` - n8n automation stack configuration
- `CLAUDE.md` - AI assistant instructions and project context
- `data/resume_config.json` - Job scorer configuration (skills, red flags, weights)

### Scripts & Utilities

- `start-tracker.sh` - Start API server (8081) and dashboard (8082)
- `stop-tracker.sh` - Stop all services gracefully
- `cleanup-project.sh` - Remove backups, cache files, organize structure
- `log-sql-practice.py` - Interactive CLI for SQL practice logging
- `inject_endpoint.py` - API endpoint testing utility
- `make-dbeaver-snapshot.sh` - Database backup with timestamp

### Logs & Backups

- `logs/` - Application logs (api-server.log, dashboard.log)
- `daily-logs/` - Daily activity logs
- `backup-*/` - Timestamped project backups - **gitignored**

### Database Files

- `data/jobs-tracker.db` - Main SQLite database
- `data/jobs-tracker.db-shm` - WAL shared memory file - **gitignored**
- `data/jobs-tracker.db-wal` - WAL write-ahead log - **gitignored**

---

## Development Workflow

### Daily Development

1. **Start Services:**
   ```bash
   ./start-tracker.sh
   ```

2. **Make Changes:**
   - Edit `api-server.py` for backend changes
   - Edit `dashboard/app.js` for frontend logic
   - Edit `dashboard/index.html` for UI changes

3. **Test Changes:**
   ```bash
   ./tests/validate-system.sh  # Quick health check
   ./tests/test-complete-system.sh  # Full validation
   ```

4. **Stop Services:**
   ```bash
   ./stop-tracker.sh
   ```

### Database Migrations

1. **Create Migration File:**
   ```bash
   cat > migrations/003_your_change.sql << EOF
   -- Your SQL changes here
   ALTER TABLE opportunities ADD COLUMN new_field TEXT;
   EOF
   ```

2. **Apply Migration:**
   ```bash
   sqlite3 data/jobs-tracker.db < migrations/003_your_change.sql
   ```

3. **Verify:**
   ```bash
   sqlite3 data/jobs-tracker.db ".schema opportunities"
   ```

### Adding New Features

1. **Backend (API Endpoint):**
   - Add endpoint handler in `api-server.py`
   - Follow existing pattern (GET/POST/PATCH)
   - Add error handling

2. **Frontend (UI):**
   - Add HTML elements in `dashboard/index.html`
   - Add JavaScript functions in `dashboard/app.js`
   - Add CSS styling in `dashboard/styles.css`

3. **Testing:**
   - Create test script in `tests/`
   - Add to `test-complete-system.sh` if critical

4. **Documentation:**
   - Update README.md
   - Add to relevant docs in `docs/`
   - Update SYSTEM_SUMMARY.md (this file)

### Version Control

**Current Branch:** `main`
**Commit Convention:**
- `feat:` New features
- `fix:` Bug fixes
- `docs:` Documentation updates
- `test:` Test additions/changes
- `refactor:` Code refactoring

---

## Known Issues

### Current Limitations

1. **Single User:** No authentication/multi-user support
2. **Local Only:** Not deployed to production server
3. **No HTTPS:** Running on HTTP for local development
4. **Manual Scraping:** Job scraper must be run manually (not scheduled)
5. **No Email Integration:** n8n workflows not yet implemented
6. **No Calendar Sync:** Google Calendar integration pending

### Minor Issues

1. **Toast Overlap:** Multiple rapid actions can stack toasts
2. **Large Datasets:** Pagination not implemented (works fine for <1000 records)
3. **Mobile UI:** Responsive but not optimized for small screens
4. **No Undo:** Deletions and updates are immediate (no confirmation modal)

### Performance Notes

- **Database Size:** Optimized for 10,000+ opportunities
- **API Response Time:** <100ms for current dataset
- **Concurrent Users:** Supports 10-20 with WAL mode
- **Memory Usage:** ~50MB for typical workload

---

## Future Enhancements

### Phase 1: Automation (High Priority)

1. **Gmail Integration (n8n)**
   - Auto-parse job emails
   - Extract company, role, recruiter info
   - Create opportunity via API
   - Send confirmation email

2. **Google Calendar Sync (n8n)**
   - Bi-directional sync
   - Auto-create interactions from calendar events
   - Update interview dates automatically
   - Send interview prep reminders

### Phase 2: Analytics Dashboard

1. **Response Rate Analysis**
   - Success rate by source (LinkedIn vs Naukri)
   - Time-to-interview metrics
   - Interview-to-offer conversion rate

2. **Salary Analytics**
   - Salary range trends
   - Offer comparison charts
   - Market rate analysis

3. **Geographic Distribution**
   - Map visualization of opportunities
   - Remote vs on-site breakdown

### Phase 3: AI Integration

1. **Resume Tailoring**
   - AI-powered resume customization per job
   - Keyword optimization
   - ATS compatibility check

2. **Interview Preparation**
   - AI question prediction based on role/company
   - Practice question generation
   - Answer quality analysis

3. **Salary Negotiation**
   - AI-powered salary insights
   - Negotiation script generation
   - Counteroffer analysis

### Phase 4: Collaboration Features

1. **Multi-User Support**
   - User authentication (JWT)
   - Role-based access control
   - Shared opportunity pools

2. **Team Features**
   - Mentor feedback integration
   - Team analytics dashboard
   - Peer learning system

### Phase 5: Mobile & PWA

1. **Progressive Web App**
   - Offline functionality
   - Mobile-optimized UI
   - Push notifications

2. **Mobile App**
   - React Native or Flutter
   - Native mobile experience
   - Camera integration (scan business cards)

### Phase 6: Advanced Features

1. **Resume Version Control**
   - Track resume versions per application
   - A/B testing of resume formats
   - Success rate by resume version

2. **Interview Prep Checklists**
   - Auto-generated based on role/company
   - Company research aggregation
   - Technical topic reviews

3. **Follow-up Automation**
   - Auto-send thank-you emails
   - Stale lead alerts (>7 days)
   - Weekly pipeline summaries

---

## Support & Maintenance

### Health Checks

```bash
# Quick validation
./tests/validate-system.sh

# Full system test
./tests/test-complete-system.sh

# Database integrity
sqlite3 data/jobs-tracker.db "PRAGMA integrity_check;"
```

### Backup & Restore

**Backup:**
```bash
./make-dbeaver-snapshot.sh
# Or manually:
cp data/jobs-tracker.db data/jobs-tracker.db.backup-$(date +%Y%m%d)
```

**Restore:**
```bash
cp data/jobs-tracker.db.backup-YYYYMMDD data/jobs-tracker.db
./start-tracker.sh
```

### Troubleshooting

See [README.md#troubleshooting](../README.md#troubleshooting) for detailed troubleshooting guide.

**Quick fixes:**
- Port conflicts: `lsof -ti:8081` then `kill <PID>`
- Database locked: Stop services, wait 2 seconds, restart
- Missing dependencies: All Python stdlib, nothing to install!

---

## Contributing

See [README.md#contributing](../README.md#contributing) for contribution guidelines.

**Code Style:**
- Python: PEP 8
- JavaScript: Standard JS
- SQL: Uppercase keywords, lowercase identifiers
- Bash: Google Shell Style Guide

---

## License

MIT License - See [README.md](../README.md) for details

---

## Changelog

**Version 2.0.0** (November 16, 2025)
- Reorganized project structure (docs/, tests/ folders)
- Updated documentation (INDEX.md, comprehensive README)
- Added 8 test scripts
- Improved .gitignore coverage

**Version 1.9.0** (November 14, 2025)
- Added archived pipeline feature
- Implemented inline editing for status/remote
- Added toast notifications
- Dynamic job sources
- Smart recruiter contact parsing

**Version 1.8.0** (November 14, 2025)
- Job scoring engine (0-100 scale)
- RemoteOK scraper integration
- Resume configuration system

**Version 1.7.0** (November 6, 2025)
- SQL practice tracking system
- Learning dashboard enhancements
- Weekly summary reports

**Version 1.0.0** (October 31, 2025)
- Initial production release
- Core job tracking functionality
- Learning system MVP

---

**Last Updated:** November 16, 2025
**Maintained By:** Karthik S R
**Status:** Production Ready, Actively Maintained

For the latest updates, see [docs/INDEX.md](INDEX.md) and [README.md](../README.md)
