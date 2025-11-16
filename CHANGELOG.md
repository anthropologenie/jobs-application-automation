# Changelog

All notable changes to the Job Application Tracker & Learning System will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Planned
- Gmail integration via n8n for auto-opportunity creation from job emails
- Google Calendar bidirectional sync for interview tracking
- Enhanced analytics dashboard with response rate analysis
- Mobile-optimized Progressive Web App (PWA)
- AI-powered resume tailoring per job application
- Multi-user support with authentication

---

## [2.0.0] - 2025-11-16

### Added - Major Milestone: Project Reorganization & Documentation Overhaul

#### Pipeline Features
- **Inline editing** for Status and Remote columns in both Active and Archived pipelines
- **Archived Pipeline section** showing Rejected/Declined/Ghosted/Accepted opportunities separately
- **Actions column** with Notes editing and Archive buttons for quick operations
- **Auto-save functionality** with optimistic UI updates (no page refresh needed)
- **Toast notification system** with success/error messages for all CRUD operations
  - Green toast for successful operations (3-second auto-dismiss)
  - Red toast for error notifications
  - Smooth animations and consistent styling

#### Dynamic Source Management
- **Dynamic source dropdown** allowing users to add custom job sources
- User can add unlimited custom sources (e.g., Wellfound, TestDevJobs, Indeed, AngelList)
- Sources persist in database and appear in dropdown permanently
- Pre-populated with default sources: LinkedIn, Naukri, Direct, Referral, Other

#### Smart Features
- **Smart recruiter contact parsing** (auto-detects phone numbers vs emails)
  - Single "Recruiter Contact" field replaces separate phone/email fields
  - Automatically stores in correct database column based on `@` symbol
  - Email detected: saved to `recruiter_email` column
  - Phone detected: saved to `recruiter_phone` column

#### API Endpoints
- `PATCH /api/update-opportunity/:id` - Update opportunity fields (status, is_remote, notes, priority)
- `GET /api/archived-pipeline` - Retrieve archived opportunities
- `POST /api/add-source` - Add custom job source with validation
- `GET /api/sources` - List all job sources (default + custom)

#### Documentation & Organization
- **Master documentation index** (`docs/INDEX.md`) with complete navigation
- **Comprehensive system summary** (`docs/SYSTEM_SUMMARY.md`, 1,233 lines)
- **Professional README** (908 lines) with full API reference, testing guide, troubleshooting
- **Documentation organized** into `docs/reports/` and `docs/guides/` folders
- **All test scripts** consolidated into `tests/` folder (8 scripts)
- **Quick reference guide** for new features and commands
- **SQL practice guide** for learning system

### Changed

#### Project Structure
- Reorganized project structure with dedicated `docs/` and `tests/` folders
- Moved all documentation to `docs/reports/` (implementation reports) and `docs/guides/` (user guides)
- Moved all test scripts from project root to `tests/` folder
- Created clear separation between application code, tests, and documentation

#### Database
- Removed CHECK constraint from `opportunities.source` column to allow dynamic sources
- Created new `job_sources` table for source management
- Updated database schema to support user-added sources

#### Configuration
- Updated `.gitignore` with comprehensive rules:
  - Python cache files (`__pycache__/`, `*.pyc`)
  - Process IDs (`*.pid`)
  - Logs (`logs/*.log`, `daily-logs/*.log`)
  - Database WAL files (`*.db-shm`, `*.db-wal`)
  - Backup files (`*.backup*`, `backup-*/`)
  - Environment files (`.env`, `.env.local`)
- Added extensive documentation standards and templates

### Removed

#### Cleanup
- Removed backup files (`api-server.py.backup`, `api-server.py.backup2`, `dashboard.py.backup`)
- Removed database backup files (`jobs-tracker.db.backup-*`, `jobs-tracker.db.pre-migration`)
- Removed Python cache directories (`__pycache__/`)
- Removed redundant test result logs and temporary files
- Removed process ID files from version control (`api-server.pid`, `dashboard.pid`)
- Removed old documentation files from root (moved to `docs/`)

### Fixed

#### API & Server
- Fixed scraped jobs endpoint path from `/scraped-jobs` to `/api/scraped-jobs` for consistency
- Improved BrokenPipeError handling in API server (graceful client disconnect)
- Enhanced database connection management across requests
- Fixed database locking issues with proper WAL mode configuration
- Improved error handling for all API endpoints with proper HTTP status codes

#### Frontend
- Fixed toast notification overlap issue with z-index and positioning
- Improved inline editing UX with immediate visual feedback
- Fixed pipeline reload after status changes to ensure data consistency
- Enhanced table responsiveness for better mobile experience

### Security
- Added comprehensive `.gitignore` to prevent committing sensitive data
- Ensured `.env` files are properly gitignored
- Parameterized all SQL queries (SQL injection prevention)
- Input validation on all API endpoints

---

## [1.9.0] - 2025-11-14

### Added - Pipeline Management Revolution

#### Archived Pipeline Feature
- Separate view for completed opportunities (Rejected, Declined, Ghosted, Accepted)
- Automatic filtering of final status opportunities from active pipeline
- Read-only archived view preserving historical data
- Sort by most recently updated

#### Inline Editing Capabilities
- Click-to-edit status dropdown directly in pipeline table
- One-click remote flag toggle (✅/❌)
- Inline notes editing with modal popup
- Immediate save via PATCH API (no page refresh)
- Optimistic UI updates for smooth user experience

#### Toast Notifications
- Real-time success/error feedback for all operations
- Auto-dismiss after 3 seconds
- Color-coded: green for success, red for errors
- Positioned top-right for non-intrusive notifications

#### Backend APIs
- `GET /api/archived-pipeline` endpoint
- `PATCH /api/update-opportunity/:id` for inline updates
- Dynamic query building based on provided fields
- Comprehensive error handling (400, 404, 500 status codes)

### Changed
- Active pipeline now excludes archived statuses automatically
- Pipeline table includes new Actions column
- Status changes trigger automatic pipeline re-categorization
- Improved UI with better visual hierarchy

### Fixed
- Database connection handling for concurrent requests
- Frontend error handling for failed API calls
- Table refresh mechanism after updates

---

## [1.8.0] - 2025-11-14

### Added - Intelligent Job Scoring System

#### Job Scoring Engine
- **0-100 point scoring algorithm** with weighted components:
  - Title Relevance: 40 points (QA keywords, seniority match)
  - Tech Stack Match: 30 points (skills from resume)
  - Company Reputation: 15 points (known tech companies)
  - Remote Work: 10 points (fully remote positions)
  - Salary Range: 5 points (meets minimum requirements)
- **Auto-classification system:**
  - Excellent Fit: 80-100 points (auto-import recommended)
  - High Fit: 60-79 points
  - Medium Fit: 40-59 points
  - Low Fit: 20-39 points
  - No Fit: 0-19 points

#### RemoteOK Integration
- Automated job scraping from RemoteOK API
- Position filtering for QA, Test, Automation roles
- Real-time job feed updates
- Deduplication by job slug
- Scraped jobs stored in `scraped_jobs` table

#### Resume Configuration System
- `data/resume_config.json` for customizable scoring
- **59 skills tracked** across 3 importance levels:
  - Critical: 15 skills (Selenium, Python, SQL, etc.)
  - High-Value: 25 skills (Pytest, CI/CD, AWS, etc.)
  - Nice-to-Have: 19 skills (Docker, Kubernetes, etc.)
- **36 red flags** with negative weights:
  - Deal Breakers (Unpaid, Manual Testing Only, etc.)
  - Consultancy Signals (Staff Augmentation, Body Shopping)
  - Outdated Technologies (VB6, Flash, etc.)
- **18 domain specializations** (AI/ML Testing, ETL/DWH, Data Quality, etc.)
- Configurable weights and thresholds

#### Scraper Tools
- `scrapers/remoteok-scraper.py` - Job scraping service
- `scrapers/job-scorer.py` - SimpleJobScorer class with 9 methods
- `scrapers/test-scorer.py` - Scorer validation tool
- `scrapers/view_scraped_jobs.sh` - Job data viewer

#### API Endpoints
- `GET /api/scraped-jobs` with query parameters (fit, limit, offset)
- `GET /api/scraped-jobs/stats` for scraping analytics

### Changed
- Enhanced database schema with `scraped_jobs` table
- Added fit_classification and score columns
- Improved job discovery workflow

### Documentation
- Added `data/SCORING_GUIDE.md` with methodology
- Created `docs/reports/SCORER_IMPLEMENTATION_SUMMARY.md`

---

## [1.7.0] - 2025-11-06

### Added - SQL Practice Tracking System

#### Database Enhancements
- **New table:** `sql_practice_sessions` for practice tracking
- **4 new views:**
  - `sql_keyword_mastery` - Accuracy per SQL keyword
  - `weekly_practice_summary` - Week-by-week trends
  - `common_practice_mistakes` - Error pattern analysis
  - `practice_progress_by_difficulty` - Easy/Medium/Hard stats

#### Python CLI Tool
- `log-sql-practice.py` - Interactive practice logger (OOP design)
- **3 classes:** PracticeSession, SessionLogger, InteractiveCLI
- **OOP concepts demonstrated:**
  - Encapsulation (public/private methods)
  - Single Responsibility Principle
  - Dependency Injection
  - Type hints and magic methods
- Validates input (platform, difficulty, database)
- Auto-saves to database with timestamp
- Shows recent sessions after logging

#### Learning Dashboard
- Enhanced `learning-dashboard.html` with practice stats
- **4 new sections:**
  - SQL Practice Stats (gradient cards)
  - SQL Keywords Mastery (color-coded badges)
  - Common Mistakes (red alert boxes)
  - Difficulty Breakdown (Easy/Medium/Hard counts)
- Real-time progress visualization

#### Weekly Reports
- `queries/weekly-practice-summary.sql` - Detailed SQL report
- `show-practice-summary.sh` - One-command summary script
- **8 report sections:**
  - Weekly Performance (last 4 weeks)
  - SQL Keywords Mastery (top 10 concepts)
  - Common Mistakes (top 5 errors)
  - Progress by Difficulty
  - Recent Practice (last 7 days)
  - Recommended Next Topics
  - Interview vs Practice Correlation
  - Actionable Insights

#### API Endpoints
- `GET /api/sql-practice-stats` - Overall practice statistics
- `GET /api/sql-keyword-mastery` - Keyword-level accuracy
- `GET /api/recent-practice` - Last 10 practice sessions
- `GET /api/weekly-summary` - Weekly aggregated data
- `GET /api/common-mistakes` - Most frequent errors

### Changed
- Enhanced `api-server.py` with 5 new learning endpoints
- Updated database schema with practice tracking tables

### Documentation
- Added `docs/guides/SQL_PRACTICE_GUIDE.md` user manual
- Created migration file `migrations/add-sql-practice-tracking.sql`
- Added test suite `test-sql-practice-system.sh` (10 tests)

---

## [1.0.0] - 2025-10-31

### Added - Initial Production Release

#### Core Job Tracking System
- **Opportunities management** with full CRUD operations
- **Status tracking:** Lead, Applied, Interview Scheduled, Interview Complete, Offer Received, Accepted, Rejected, Declined, Ghosted
- **Priority management:** High, Medium, Low
- **Remote work tracking** (is_remote flag)
- **Tech stack tagging** for required technologies
- **Recruiter contact tracking** (phone and email)
- **Notes field** for additional context

#### Database Architecture
- **SQLite 3.x** with WAL (Write-Ahead Logging) mode for concurrency
- **Core tables:**
  - `opportunities` - Main job tracking table
  - `interactions` - Communication history
  - `interview_questions` - Question logging
  - `study_topics` - Study plan management
  - `documents` - File attachments
  - `learning_sessions` - Study session tracking
- **Views:**
  - `active_pipeline` - Non-archived opportunities
  - `todays_agenda` - Next 7 days interviews
  - `learning_gaps` - Weak areas analysis
  - `study_priority` - Recommended study topics
- **Triggers:**
  - `update_opportunity_timestamp` - Auto-update modified date
  - `update_last_interaction` - Track last contact date
- **Foreign key constraints** enabled
- **CHECK constraints** for data validation

#### REST API Server
- **Python 3.12** HTTP server on port 8081
- **Core endpoints:**
  - `GET /api/metrics` - Dashboard KPIs
  - `GET /api/pipeline` - Active opportunities
  - `GET /api/todays-agenda` - Upcoming interviews
  - `POST /api/add-opportunity` - Create new job
- **CORS enabled** for local development
- **Thread-safe** database connections
- **Comprehensive error handling** with proper HTTP status codes
- **<100ms** average response time

#### Frontend Dashboard
- **Vanilla JavaScript SPA** (no frameworks)
- **Responsive design** with CSS Grid and Flexbox
- **Real-time metrics dashboard:**
  - Active opportunities count
  - Interview pipeline stats
  - Remote job percentage
  - High-priority leads
- **Pipeline view** with sortable/filterable table
- **7-day interview agenda**
- **Add opportunity form** with validation
- **Static file server** on port 8082

#### Learning System MVP
- **Interview question logging** with performance ratings (1-5 scale)
- **Learning gap analysis** by topic
- **Study priority recommendations**
- **Topic tracking** with mastery levels
- **Learning session logging** with duration and notes
- Basic learning dashboard

#### Sacred Work Tracking
- **Pomodoro-style work logging** ("stones" system)
- **Time tracking** in minutes per session
- **Progress documentation** (what was built, insights)
- **Reflection capture** (next stone, felt sense)
- **Daily summaries** with API endpoints

#### Testing & Quality
- **7 automated tests** in test suite
- **100% test coverage** on critical API endpoints
- **Execution time:** ~3 seconds
- **Database integrity validation**
- **API endpoint validation**

#### Documentation
- Comprehensive README with quickstart guide
- Database schema documentation
- API endpoint reference
- Troubleshooting guide
- Architecture overview

#### Utilities & Scripts
- `start-tracker.sh` - Start all services
- `stop-tracker.sh` - Stop all services
- `test-complete-system.sh` - Run full test suite
- `make-dbeaver-snapshot.sh` - Database backup tool

### Technical Highlights
- **Zero external dependencies** (Python standard library only)
- **Zero database lock errors** in production (WAL mode)
- **Optimized for 10,000+ opportunities**
- **Concurrent operation support** for 10-20 users
- **Parameterized SQL queries** (SQL injection safe)
- **Clean architecture** with separation of concerns

---

## Version History Summary

| Version | Date | Key Feature |
|---------|------|-------------|
| **2.0.0** | 2025-11-16 | Project reorganization, inline editing, toast notifications |
| **1.9.0** | 2025-11-14 | Archived pipeline, dynamic sources, smart parsing |
| **1.8.0** | 2025-11-14 | Job scoring engine, RemoteOK scraper |
| **1.7.0** | 2025-11-06 | SQL practice tracking system |
| **1.0.0** | 2025-10-31 | Initial production release |

---

## Links

- [Documentation Index](docs/INDEX.md)
- [System Summary](docs/SYSTEM_SUMMARY.md)
- [Quick Reference Guide](docs/guides/QUICK_REFERENCE.md)
- [SQL Practice Guide](docs/guides/SQL_PRACTICE_GUIDE.md)
- [Test Reports](docs/reports/TEST_REPORT.md)
- [README](README.md)

---

## Release Types

This project follows [Semantic Versioning](https://semver.org/):

- **MAJOR** version (X.0.0): Incompatible API changes or major architectural changes
- **MINOR** version (0.X.0): New features, backward-compatible functionality
- **PATCH** version (0.0.X): Bug fixes, backward-compatible improvements

---

**Maintained by:** Karthik S R
**Status:** Production Ready, Actively Maintained
**Last Updated:** November 16, 2025
