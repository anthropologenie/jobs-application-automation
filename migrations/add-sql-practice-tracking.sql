-- Migration: Add SQL Practice Tracking System
-- Purpose: Track your daily SQL practice from sql-practice.com, programiz, DBeaver
-- Date: 2025-11-03

-- ======================================
-- Main Practice Sessions Table
-- ======================================
CREATE TABLE IF NOT EXISTS sql_practice_sessions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,

  -- Session metadata
  practice_date DATE NOT NULL DEFAULT (DATE('now')),
  platform TEXT NOT NULL CHECK(platform IN ('sql-practice.com', 'programiz', 'dbeaver', 'other')),
  database_used TEXT CHECK(database_used IN ('Hospital', 'Northwind', 'Custom', 'None')),

  -- The question and solution
  question_text TEXT NOT NULL,
  my_query TEXT NOT NULL,
  correct_query TEXT,

  -- Performance tracking
  is_correct BOOLEAN DEFAULT 0,
  time_spent_minutes INTEGER,
  difficulty TEXT CHECK(difficulty IN ('Easy', 'Medium', 'Hard')) DEFAULT 'Medium',

  -- Learning insights
  error_made TEXT,           -- What went wrong? (Syntax error, wrong logic, etc.)
  lesson_learned TEXT,        -- Key takeaway from this practice

  -- SQL Concepts used (to track mastery)
  keywords_used TEXT,         -- Comma-separated: WHERE, JOIN, GROUP BY, HAVING, WINDOW, CTE

  -- Optional notes
  notes TEXT,

  -- Auto-timestamps
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

  -- Link to interview questions if this practice was inspired by one
  related_question_id INTEGER REFERENCES interview_questions(id) ON DELETE SET NULL
);

-- ======================================
-- Indexes for Fast Queries
-- ======================================
CREATE INDEX IF NOT EXISTS idx_practice_date ON sql_practice_sessions(practice_date);
CREATE INDEX IF NOT EXISTS idx_practice_platform ON sql_practice_sessions(platform);
CREATE INDEX IF NOT EXISTS idx_practice_difficulty ON sql_practice_sessions(difficulty);
CREATE INDEX IF NOT EXISTS idx_practice_correct ON sql_practice_sessions(is_correct);

-- ======================================
-- View: SQL Keywords Mastery Tracker
-- ======================================
-- This shows which SQL concepts you've practiced and your accuracy with them
-- Uses recursive CTE to split comma-separated keywords
CREATE VIEW IF NOT EXISTS sql_keyword_mastery AS
WITH RECURSIVE split_keywords AS (
  -- Base case: get first keyword
  SELECT
    id,
    is_correct,
    time_spent_minutes,
    TRIM(SUBSTR(keywords_used || ',', 1, INSTR(keywords_used || ',', ',') - 1)) as keyword,
    SUBSTR(keywords_used || ',', INSTR(keywords_used || ',', ',') + 1) as remaining
  FROM sql_practice_sessions
  WHERE keywords_used IS NOT NULL AND keywords_used != ''

  UNION ALL

  -- Recursive case: get next keyword
  SELECT
    id,
    is_correct,
    time_spent_minutes,
    TRIM(SUBSTR(remaining, 1, INSTR(remaining, ',') - 1)) as keyword,
    SUBSTR(remaining, INSTR(remaining, ',') + 1) as remaining
  FROM split_keywords
  WHERE LENGTH(remaining) > 0 AND INSTR(remaining, ',') > 0
)
SELECT
  keyword,
  COUNT(*) as practice_count,
  SUM(CASE WHEN is_correct = 1 THEN 1 ELSE 0 END) as correct_count,
  ROUND(100.0 * SUM(CASE WHEN is_correct = 1 THEN 1 ELSE 0 END) / COUNT(*), 1) as accuracy_percentage,
  ROUND(AVG(time_spent_minutes), 1) as avg_time_minutes
FROM split_keywords
WHERE keyword != ''
GROUP BY keyword
ORDER BY practice_count DESC, accuracy_percentage ASC;

-- ======================================
-- View: Weekly Practice Summary
-- ======================================
CREATE VIEW IF NOT EXISTS weekly_practice_summary AS
SELECT
  strftime('%Y-W%W', practice_date) as week,
  COUNT(*) as total_sessions,
  COUNT(DISTINCT platform) as platforms_used,
  SUM(CASE WHEN is_correct = 1 THEN 1 ELSE 0 END) as correct_answers,
  ROUND(100.0 * SUM(CASE WHEN is_correct = 1 THEN 1 ELSE 0 END) / COUNT(*), 1) as accuracy_percentage,
  SUM(time_spent_minutes) as total_minutes,
  COUNT(CASE WHEN difficulty = 'Easy' THEN 1 END) as easy_questions,
  COUNT(CASE WHEN difficulty = 'Medium' THEN 1 END) as medium_questions,
  COUNT(CASE WHEN difficulty = 'Hard' THEN 1 END) as hard_questions
FROM sql_practice_sessions
GROUP BY strftime('%Y-W%W', practice_date)
ORDER BY week DESC;

-- ======================================
-- View: Common Mistakes Pattern
-- ======================================
CREATE VIEW IF NOT EXISTS common_practice_mistakes AS
SELECT
  error_made,
  COUNT(*) as occurrence_count,
  GROUP_CONCAT(DISTINCT keywords_used) as concepts_affected,
  ROUND(AVG(time_spent_minutes), 1) as avg_recovery_time
FROM sql_practice_sessions
WHERE error_made IS NOT NULL AND error_made != ''
GROUP BY error_made
ORDER BY occurrence_count DESC
LIMIT 10;

-- ======================================
-- View: Practice Progress by Difficulty
-- ======================================
CREATE VIEW IF NOT EXISTS practice_progress_by_difficulty AS
SELECT
  difficulty,
  COUNT(*) as total_attempted,
  SUM(CASE WHEN is_correct = 1 THEN 1 ELSE 0 END) as correct,
  ROUND(100.0 * SUM(CASE WHEN is_correct = 1 THEN 1 ELSE 0 END) / COUNT(*), 1) as accuracy_percentage,
  AVG(time_spent_minutes) as avg_time_minutes,
  MIN(practice_date) as first_attempt,
  MAX(practice_date) as latest_attempt
FROM sql_practice_sessions
GROUP BY difficulty
ORDER BY
  CASE difficulty
    WHEN 'Easy' THEN 1
    WHEN 'Medium' THEN 2
    WHEN 'Hard' THEN 3
  END;

-- ======================================
-- Sample Data Insert (for testing)
-- ======================================
-- Uncomment to insert sample data:
/*
INSERT INTO sql_practice_sessions (
  platform, database_used, question_text, my_query, correct_query,
  is_correct, time_spent_minutes, difficulty, error_made, lesson_learned, keywords_used
) VALUES
(
  'sql-practice.com',
  'Hospital',
  'Find all patients admitted after 2020 with diagnosis containing "COVID"',
  'SELECT * FROM patients WHERE admission_date > 2020 AND diagnosis LIKE "%COVID%"',
  'SELECT * FROM patients WHERE admission_date > "2020-01-01" AND diagnosis LIKE "%COVID%"',
  0,
  15,
  'Medium',
  'Date comparison without proper date format - compared year (int) to date column',
  'Always use proper date format in SQL: "YYYY-MM-DD" for comparisons',
  'WHERE, LIKE, DATE'
);
*/
