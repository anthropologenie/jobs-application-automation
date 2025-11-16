# SQL Practice Tracking System - User Guide

## Overview
Track your SQL practice sessions from sql-practice.com, programiz, and DBeaver. Analyze patterns in your mistakes, monitor keyword mastery, and get personalized recommendations.

---

## Quick Start

### 1. Log Your Practice Session
After completing a SQL question, run:
```bash
./log-sql-practice.py
```

**What it asks you:**
- Question text
- Your SQL query
- Platform (sql-practice.com, programiz, dbeaver)
- Difficulty (Easy, Medium, Hard)
- Database used (Hospital, Northwind, etc.)
- Was it correct? (y/n)
- Time spent (minutes)
- What error did you make?
- Key lesson learned
- SQL keywords used (WHERE, JOIN, GROUP BY, etc.)

**Example Session:**
```
Question text: Find all patients admitted after 2020
Your SQL query: SELECT * FROM patients WHERE year > 2020
Platform: sql-practice.com
Difficulty: Medium
Database: Hospital
Did you get it correct? n
Time spent: 15 minutes
Error: Used year comparison without proper date format
Lesson: Always use 'YYYY-MM-DD' format for date comparisons
Keywords: WHERE, DATE
```

### 2. View Your Progress
```bash
./show-practice-summary.sh
```

Shows:
- Weekly performance trends
- SQL keyword mastery (accuracy per concept)
- Common mistakes to avoid
- Progress by difficulty
- Correlation with interview questions
- Actionable insights

### 3. View Dashboard
```bash
# Start API server (if not running)
python3 api-server.py

# Open in browser
http://localhost:8081/learning-dashboard.html
```

**Dashboard Features:**
- 💻 SQL Practice Stats (total sessions, accuracy, time)
- 🔑 Keyword Mastery (visual badges with accuracy)
- ⚠️ Common Mistakes (with occurrence count)
- 📊 Difficulty breakdown (Easy/Medium/Hard)

---

## Database Schema

### Main Table: `sql_practice_sessions`
Stores every practice session with:
- Question text and your query
- Platform and database used
- Correctness and time spent
- Error made and lesson learned
- SQL keywords used

### Views Created
1. **sql_keyword_mastery** - Accuracy per SQL concept (JOIN, WHERE, etc.)
2. **weekly_practice_summary** - Week-by-week progress
3. **common_practice_mistakes** - Most frequent errors
4. **practice_progress_by_difficulty** - Easy/Medium/Hard breakdown

---

## API Endpoints (Port 8081)

### SQL Practice Endpoints
- `GET /api/sql-practice-stats` - Overall stats
- `GET /api/sql-keyword-mastery` - Keyword accuracy
- `GET /api/recent-practice` - Last 10 sessions
- `GET /api/weekly-summary` - Weekly trends
- `GET /api/common-mistakes` - Error patterns

---

## Python OOP Learning Notes

The CLI tool (`log-sql-practice.py`) demonstrates key OOP concepts:

### 1. **Classes & Objects**
```python
class PracticeSession:
    """Represents ONE practice session (data model)"""

class SessionLogger:
    """Handles database operations (persistence layer)"""

class InteractiveCLI:
    """Manages user interaction (presentation layer)"""
```

### 2. **Encapsulation**
- Data validation in methods (`_validate_platform`, `_validate_difficulty`)
- Private methods (prefix `_`) for internal logic
- Public methods for external interface

### 3. **Single Responsibility Principle**
- `PracticeSession` = data + validation
- `SessionLogger` = database operations
- `InteractiveCLI` = user interface

### 4. **Dependency Injection**
```python
logger = SessionLogger(db_path='./data/jobs-tracker.db')
cli = InteractiveCLI(logger)  # CLI doesn't create its own logger
```

**Why?** Makes testing easier, reduces coupling, improves flexibility.

### 5. **Magic Methods**
- `__init__`: Constructor (called when creating object)
- `__str__`: String representation (for `print()`)

### 6. **Type Hints**
```python
def save(self, session: PracticeSession) -> int:
```
Improves code clarity and catches bugs early.

---

## SQL Learning Notes

### Recursive CTEs (used in keyword mastery view)
```sql
WITH RECURSIVE split_keywords AS (
  -- Base case: get first keyword
  SELECT ... FROM sql_practice_sessions

  UNION ALL

  -- Recursive case: continue splitting
  SELECT ... FROM split_keywords
  WHERE LENGTH(remaining) > 0
)
SELECT * FROM split_keywords
```

**Why?** SQLite doesn't have `SPLIT()` function, so we use recursion to split comma-separated values.

### Window Functions for Weekly Aggregation
```sql
strftime('%Y-W%W', practice_date) as week
```
Groups sessions by ISO week number.

---

## Tips for Effective Practice

### 1. Log Immediately After Practice
Don't wait! Fresh memory = better insights into your mistakes.

### 2. Be Honest About Errors
The system learns from your mistakes to give better recommendations.

### 3. Use Specific Keywords
Instead of: `SQL`
Use: `WHERE, INNER JOIN, GROUP BY, HAVING`

### 4. Track Time Realistically
Helps identify which concepts slow you down.

### 5. Review Weekly Summary
Every Sunday, run `./show-practice-summary.sh` to plan next week.

---

## Correlation with Interview Performance

The system connects your practice with interview questions:

```sql
SELECT
  iq.question_type as InterviewTopic,
  AVG(iq.my_rating) as InterviewRating,
  COUNT(practice_sessions) as PracticeSessions
FROM interview_questions iq
LEFT JOIN sql_practice_sessions sps ...
```

**Insight:** If you struggled with "Data Warehouse" interviews (rating ≤ 2), but have low practice in WINDOW functions, the system recommends practicing window functions.

---

## Files Reference

### Core Files
- `log-sql-practice.py` - CLI tool to log sessions
- `show-practice-summary.sh` - View weekly summary
- `test-sql-practice-system.sh` - Integration tests

### Database
- `migrations/add-sql-practice-tracking.sql` - Schema migration
- `queries/weekly-practice-summary.sql` - Detailed weekly report

### Web Interface
- `api-server.py` - Backend API (enhanced with practice endpoints)
- `learning-dashboard.html` - Frontend dashboard

---

## Troubleshooting

### Problem: Can't run log-sql-practice.py
**Solution:** Make it executable
```bash
chmod +x log-sql-practice.py
```

### Problem: Dashboard shows 0 sessions
**Solution:**
1. Log at least one practice session: `./log-sql-practice.py`
2. Restart API server: `python3 api-server.py`
3. Refresh dashboard

### Problem: Views not showing data
**Solution:** Re-run migration
```bash
sqlite3 data/jobs-tracker.db < migrations/add-sql-practice-tracking.sql
```

---

## Next Steps

1. **Daily**: Log practice after each session
2. **Weekly**: Run summary to review progress
3. **Monthly**: Correlate with interview performance and adjust study plan

Happy practicing! Remember: consistency > intensity. 🚀
