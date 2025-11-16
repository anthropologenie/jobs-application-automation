# Documentation Index

**Complete guide to all documentation in the Job Application Tracker & Learning System**

Last Updated: November 16, 2025

---

## Quick Navigation

- [Getting Started](#getting-started) - New user guides and quick references
- [System Documentation](#system-documentation) - Architecture and design documentation
- [Feature Documentation](#feature-documentation) - Detailed feature guides and how-tos
- [Development Reports](#development-reports) - Implementation summaries and technical details
- [Testing Documentation](#testing-documentation) - Test reports and validation results
- [Troubleshooting Guides](#troubleshooting-guides) - Common issues and solutions
- [Documentation Status](#documentation-status) - Last updated dates and maintenance info

---

## Getting Started

Perfect for new users or quick lookups.

### [Quick Reference Guide](guides/QUICK_REFERENCE.md)
**What:** Command cheat sheet and feature overview
**When to use:** First-time setup, forgot a command, or need quick feature refresh
**Key topics:**
- Dynamic job sources (add custom sources like "Wellfound", "Indeed")
- Smart recruiter contact parsing (auto-detects phone vs email)
- New API endpoints reference
- Database schema changes
- Feature usage examples

**Quick peek:**
```bash
# Example: Get all job sources
GET http://localhost:8081/api/sources

# Example: Add new source
POST http://localhost:8081/api/add-source
{"source_name": "Wellfound"}
```

---

### [SQL Practice Guide](guides/SQL_PRACTICE_GUIDE.md)
**What:** Complete guide to the SQL practice tracking system
**When to use:** Learning SQL, tracking practice sessions, analyzing your weak areas
**Key topics:**
- How to log practice sessions from sql-practice.com, programiz, or DBeaver
- View weekly progress and keyword mastery
- Understand common mistakes and patterns
- API endpoints for practice analytics
- Interactive CLI tool usage (`log-sql-practice.py`)

**Quick peek:**
```bash
# Log a new practice session
./log-sql-practice.py

# View your practice summary
./tests/show-practice-summary.sh
```

---

## System Documentation

Deep technical documentation about architecture and design.

### [System Summary](SYSTEM_SUMMARY.md)
**What:** Complete system architecture, database schema, and technical implementation details
**When to use:** Understanding how the system works, onboarding new developers, making architectural decisions
**Key topics:**
- SQL practice tracking system components
- Database schema (tables, views, relationships)
- Python CLI tool architecture (OOP design with 3 classes)
- API server endpoints (5 new practice-related endpoints)
- Sample data and migration files
- OOP concepts demonstrated (encapsulation, SRP, dependency injection)

**Quick peek:**
```sql
-- New database objects created
sql_practice_sessions (table)
sql_keyword_mastery (view)
weekly_practice_summary (view)
common_practice_mistakes (view)
practice_progress_by_difficulty (view)
```

---

## Feature Documentation

Detailed guides for specific features.

### Core Features

The main README covers:
- **Job Tracking System** - Active/archived pipelines, inline editing, toast notifications
- **Learning System** - Interview questions, gap analysis, study priorities
- **Job Scraping** - RemoteOK integration with intelligent scoring (0-100 scale)
- **Sacred Work Tracking** - Pomodoro-style productivity logging

See: [`../README.md`](../README.md)

### Additional Feature Documentation

- **Dynamic Job Sources:** See [Quick Reference](guides/QUICK_REFERENCE.md#feature-1-dynamic-job-sources)
- **Smart Recruiter Parsing:** See [Quick Reference](guides/QUICK_REFERENCE.md#feature-2-smart-recruiter-contact)
- **SQL Practice System:** See [SQL Practice Guide](guides/SQL_PRACTICE_GUIDE.md)
- **Job Scoring Engine:** See [Scorer Implementation Summary](reports/SCORER_IMPLEMENTATION_SUMMARY.md)

---

## Development Reports

Technical implementation summaries and session reports.

### [New Features Report](reports/NEW_FEATURES_REPORT.md)
**Date:** November 14, 2025
**What:** Implementation details for Archived Pipeline and Inline Editing features
**Covers:**
- Archived Pipeline section (separate view for final status opportunities)
- Inline editing capabilities (status, remote flag, notes with auto-save)
- Backend changes: 2 new endpoints (`GET /api/archived-pipeline`, `PATCH /api/update-opportunity/:id`)
- Frontend changes: +250 lines across 3 files
- 8 new JavaScript functions for editing and auto-save
- Complete feature validation

**Quick stats:**
- Changes: 3 files modified, 2 endpoints added
- Code added: +250 lines
- Status: ✅ Fully operational

---

### [Session Changes Summary](reports/SESSION_CHANGES_SUMMARY.md)
**Date:** November 14, 2025
**What:** Detailed changelog of dynamic sources and smart contact parsing implementation
**Covers:**
- File-by-file breakdown of all code changes
- Line-by-line implementation details
- Database migration scripts
- API endpoint specifications
- Frontend JavaScript modifications
- Complete testing validation log

**Files modified:** 5 total
- `api-server.py` (3 changes)
- `dashboard/index.html` (2 changes)
- `dashboard/app.js` (4 changes)
- Database migration (1 new file)
- Test script (1 new file)

---

### [Scorer Implementation Summary](reports/SCORER_IMPLEMENTATION_SUMMARY.md)
**Date:** November 14, 2025
**What:** AI-powered job scoring engine technical documentation
**Covers:**
- Resume configuration system (`data/resume_config.json`)
- Weighted scoring algorithm (0-100 scale)
- SimpleJobScorer class with 9 methods
- Skills matching (59 skills across 3 importance levels)
- Red flag detection (36 negative indicators)
- Domain expertise matching (18 specializations)
- Classification system (Excellent/High/Medium/Low/No Fit)
- Auto-import threshold (75% score)

**Quick stats:**
- Skills tracked: 59 (Critical: 15, High-Value: 25, Nice-to-Have: 19)
- Red flags: 36 across 4 categories
- Domains: 18 specializations
- Scoring weights: Skills 40%, Experience 20%, Domain 20%, Location 10%, Red Flags 10%
- Auto-import: Jobs scoring ≥75%

**Features:**
- Regex pattern matching with word boundaries
- Weighted component scoring
- Detailed breakdown and recommendations
- Type hints and comprehensive error handling

---

## Testing Documentation

Test reports, validation results, and quality assurance.

### [Test Report](reports/TEST_REPORT.md)
**Date:** November 14, 2025
**What:** Comprehensive test results for dynamic sources and smart contact parsing
**Status:** ✅ ALL FEATURES WORKING (10/10 tests passed)
**Covers:**
- Feature 1 test results: Dynamic job sources (6 tests)
- Feature 2 test results: Smart recruiter contact parsing (4 tests)
- API endpoint validation
- Database constraint testing
- Edge case validation (duplicates, empty inputs, special characters)
- Integration testing results

**Test breakdown:**
- Dynamic Sources: 6/6 passed ✅
  - Add new source (Wellfound, Indeed, TestDevJobs)
  - List all sources
  - Use new source in opportunity
  - Duplicate source (error handling)
  - Empty source name (validation)
  - Special characters (sanitization)

- Smart Contact Parsing: 4/4 passed ✅
  - Email detection and storage
  - Phone number detection and storage
  - Empty field handling
  - Database column verification

---

### Additional Test Scripts

Located in [`../tests/`](../tests/):
- `test-complete-system.sh` - Full system validation (7 tests)
- `test-new-pipeline-features.sh` - Archived pipeline and inline editing tests
- `test-scraped-jobs-api.sh` - Job scraper and scoring tests
- `test-sql-practice-system.sh` - Learning system validation
- `validate-system.sh` - Health checks
- `final-validation-tests.sh` - Pre-deployment validation
- `show-practice-summary.sh` - SQL practice analytics viewer

See: [`../README.md#testing`](../README.md#testing)

---

## Troubleshooting Guides

Common issues and their solutions.

### Main Troubleshooting Guide

The main README includes troubleshooting for:
- Dashboard not loading (port conflicts, server restarts)
- API not responding (logs, port availability)
- Database locked errors (WAL mode, connection management)
- Job scraper issues (testing, database verification)

See: [`../README.md#troubleshooting`](../README.md#troubleshooting)

### Quick Fixes

**Dashboard won't start:**
```bash
lsof -ti:8082
pkill -f "dashboard/server.py"
./stop-tracker.sh && ./start-tracker.sh
```

**API returning errors:**
```bash
tail -f logs/api-server.log
curl http://localhost:8081/api/metrics
```

**Database locked:**
```bash
./stop-tracker.sh
sleep 2
sqlite3 data/jobs-tracker.db "PRAGMA journal_mode;"  # Should output: wal
./start-tracker.sh
```

---

## Documentation Status

### Last Updated Dates

| Document | Last Modified | Category | Status |
|----------|---------------|----------|--------|
| **SYSTEM_SUMMARY.md** | 2025-11-03 | System Docs | ✅ Current |
| **QUICK_REFERENCE.md** | 2025-11-14 | Getting Started | ✅ Current |
| **SQL_PRACTICE_GUIDE.md** | 2025-11-03 | Getting Started | ✅ Current |
| **NEW_FEATURES_REPORT.md** | 2025-11-14 | Development | ✅ Current |
| **SESSION_CHANGES_SUMMARY.md** | 2025-11-14 | Development | ✅ Current |
| **SCORER_IMPLEMENTATION_SUMMARY.md** | 2025-11-14 | Development | ✅ Current |
| **TEST_REPORT.md** | 2025-11-14 | Testing | ✅ Current |
| **INDEX.md** (this file) | 2025-11-16 | Navigation | ✅ Current |

### Documentation Coverage

| Area | Documentation | Status |
|------|---------------|--------|
| **Getting Started** | Quick Reference, SQL Practice Guide | ✅ Complete |
| **System Architecture** | System Summary, README | ✅ Complete |
| **Feature Guides** | README, Quick Reference | ✅ Complete |
| **API Reference** | README API section | ✅ Complete |
| **Database Schema** | System Summary, README | ✅ Complete |
| **Testing** | Test Report, Test Scripts | ✅ Complete |
| **Development** | Session Changes, Feature Reports | ✅ Complete |
| **Troubleshooting** | README Troubleshooting section | ✅ Complete |
| **Job Scoring** | Scorer Implementation Summary | ✅ Complete |

---

## How to Use This Index

### For New Users
1. Start with [Quick Reference](guides/QUICK_REFERENCE.md) to understand key features
2. Read the main [README](../README.md) for complete overview
3. Check [SQL Practice Guide](guides/SQL_PRACTICE_GUIDE.md) if using learning features

### For Developers
1. Review [System Summary](SYSTEM_SUMMARY.md) for architecture
2. Check [Session Changes Summary](reports/SESSION_CHANGES_SUMMARY.md) for recent changes
3. Read feature implementation reports for detailed technical specs
4. Review [Test Report](reports/TEST_REPORT.md) for validation details

### For Troubleshooting
1. Check main [README Troubleshooting section](../README.md#troubleshooting)
2. Review relevant feature documentation for specific issues
3. Check test reports to understand expected behavior

### For Feature Understanding
1. Read the feature's implementation report (e.g., [Scorer Implementation](reports/SCORER_IMPLEMENTATION_SUMMARY.md))
2. Check the [Quick Reference](guides/QUICK_REFERENCE.md) for usage examples
3. Review test cases in [Test Report](reports/TEST_REPORT.md)

---

## Document Templates

When adding new documentation:

1. **Feature Reports:** Use [NEW_FEATURES_REPORT.md](reports/NEW_FEATURES_REPORT.md) as template
2. **Test Reports:** Use [TEST_REPORT.md](reports/TEST_REPORT.md) as template
3. **User Guides:** Use [SQL_PRACTICE_GUIDE.md](guides/SQL_PRACTICE_GUIDE.md) as template
4. **Quick Refs:** Use [QUICK_REFERENCE.md](guides/QUICK_REFERENCE.md) as template

---

## Contributing to Documentation

### Documentation Standards

- Use clear, concise language
- Include code examples where relevant
- Add "Quick peek" sections for TL;DR
- Include last updated dates
- Use emoji sparingly for visual hierarchy
- Cross-link related documents

### File Organization

```
docs/
├── INDEX.md                    # This file - master navigation
├── SYSTEM_SUMMARY.md           # Architecture and system design
├── guides/
│   ├── QUICK_REFERENCE.md      # Command cheat sheet
│   └── SQL_PRACTICE_GUIDE.md   # Feature-specific guide
└── reports/
    ├── NEW_FEATURES_REPORT.md  # Implementation details
    ├── SESSION_CHANGES_SUMMARY.md  # Detailed changelogs
    ├── SCORER_IMPLEMENTATION_SUMMARY.md  # Technical specs
    └── TEST_REPORT.md          # Test validation results
```

### When to Create New Documentation

- **New Feature:** Create implementation report in `reports/`
- **User Guide:** Create guide in `guides/`
- **Major Changes:** Update existing docs and add changelog entry
- **New API Endpoint:** Update README API Reference section
- **Test Results:** Update or create test report in `reports/`

---

## Additional Resources

### External Documentation
- [SQLite Documentation](https://www.sqlite.org/docs.html) - Database reference
- [Python http.server](https://docs.python.org/3/library/http.server.html) - API server docs
- [n8n Documentation](https://docs.n8n.io/) - Workflow automation

### Project Files
- [`../README.md`](../README.md) - Main project documentation
- [`../CLAUDE.md`](../CLAUDE.md) - AI assistant instructions
- [`../data/SCORING_GUIDE.md`](../data/SCORING_GUIDE.md) - Job scoring methodology
- [`../queries/schema.sql`](../queries/schema.sql) - Database schema

### Tools
- DBeaver - Database management (for viewing schema and data)
- VSCode/Claude Code - Development environment
- curl/jq - API testing
- SQLite CLI - Database queries

---

## Feedback

Found an issue with the documentation? Have suggestions for improvement?

1. Check if the issue is already documented
2. Review related documentation for context
3. Create an issue in the project repository
4. Suggest specific improvements with examples

---

**Navigation Tip:** Use your editor's table of contents feature or Ctrl+F to quickly find specific topics in this index.

**Last Reviewed:** November 16, 2025
**Maintained by:** Karthik S R
**Version:** 1.0.0
