-- ========================================
-- WEEKLY SQL PRACTICE SUMMARY
-- ========================================
-- Purpose: Review your weekly practice progress, identify patterns, and plan next steps
-- How to use: sqlite3 data/jobs-tracker.db < queries/weekly-practice-summary.sql

.mode box
.headers on

-- ========================================
-- 1. OVERVIEW: Last 4 Weeks Performance
-- ========================================
SELECT
  '📊 WEEKLY PERFORMANCE' as section,
  '' as blank1,
  '' as blank2,
  '' as blank3,
  '' as blank4;

SELECT
  week as Week,
  total_sessions as Sessions,
  accuracy_percentage || '%' as Accuracy,
  total_minutes || 'min' as Time,
  easy_questions || 'E / ' || medium_questions || 'M / ' || hard_questions || 'H' as Difficulty
FROM weekly_practice_summary
ORDER BY week DESC
LIMIT 4;

-- ========================================
-- 2. KEYWORDS MASTERY: What SQL Concepts You've Practiced
-- ========================================
SELECT '' as blank;
SELECT
  '🔑 SQL KEYWORDS MASTERY' as section,
  '' as blank1,
  '' as blank2,
  '' as blank3;

SELECT
  keyword as Keyword,
  practice_count as Practices,
  accuracy_percentage || '%' as Accuracy,
  ROUND(avg_time_minutes, 1) || 'min' as AvgTime
FROM sql_keyword_mastery
WHERE practice_count > 0
ORDER BY practice_count DESC, accuracy_percentage ASC
LIMIT 10;

-- ========================================
-- 3. COMMON MISTAKES: What to Watch Out For
-- ========================================
SELECT '' as blank;
SELECT
  '⚠️  COMMON MISTAKES' as section,
  '' as blank1,
  '' as blank2;

SELECT
  error_made as Mistake,
  occurrence_count as Count,
  ROUND(avg_recovery_time, 1) || 'min' as AvgRecovery
FROM common_practice_mistakes
WHERE error_made IS NOT NULL
LIMIT 5;

-- ========================================
-- 4. PROGRESS BY DIFFICULTY
-- ========================================
SELECT '' as blank;
SELECT
  '📈 PROGRESS BY DIFFICULTY' as section,
  '' as blank1,
  '' as blank2,
  '' as blank3,
  '' as blank4;

SELECT
  difficulty as Level,
  total_attempted as Attempted,
  correct as Correct,
  accuracy_percentage || '%' as Accuracy,
  ROUND(avg_time_minutes, 1) || 'min' as AvgTime,
  latest_attempt as LatestPractice
FROM practice_progress_by_difficulty;

-- ========================================
-- 5. RECENT PRACTICE SESSIONS (Last 7 days)
-- ========================================
SELECT '' as blank;
SELECT
  '📝 RECENT PRACTICE (Last 7 Days)' as section,
  '' as blank1,
  '' as blank2,
  '' as blank3,
  '' as blank4;

SELECT
  practice_date as Date,
  platform as Platform,
  difficulty as Level,
  CASE WHEN is_correct = 1 THEN '✅' ELSE '❌' END as Result,
  SUBSTR(question_text, 1, 60) || '...' as Question,
  time_spent_minutes || 'min' as Time
FROM sql_practice_sessions
WHERE practice_date >= DATE('now', '-7 days')
ORDER BY practice_date DESC, created_at DESC;

-- ========================================
-- 6. RECOMMENDED NEXT TOPICS
-- ========================================
SELECT '' as blank;
SELECT
  '🎯 RECOMMENDED NEXT TOPICS' as section,
  '' as blank1,
  '' as blank2;

SELECT
  'Practice: ' || keyword as Recommendation,
  'Current Accuracy: ' || accuracy_percentage || '%' as Reason
FROM sql_keyword_mastery
WHERE accuracy_percentage < 70 AND practice_count >= 2
ORDER BY practice_count DESC
LIMIT 5;

-- ========================================
-- 7. CORRELATION: Interview Questions vs Practice
-- ========================================
SELECT '' as blank;
SELECT
  '🔗 INTERVIEW VS PRACTICE CORRELATION' as section,
  '' as blank1,
  '' as blank2,
  '' as blank3;

SELECT
  iq.question_type as InterviewTopic,
  COUNT(DISTINCT iq.id) as InterviewQuestions,
  AVG(iq.my_rating) as InterviewRating,
  COALESCE(
    (SELECT COUNT(*)
     FROM sql_practice_sessions sps
     WHERE sps.keywords_used LIKE '%' ||
       CASE iq.question_type
         WHEN 'Technical SQL' THEN 'JOIN'
         WHEN 'Data Warehouse' THEN 'WINDOW'
         ELSE 'SQL'
       END || '%'),
    0
  ) as PracticeSessions
FROM interview_questions iq
WHERE iq.question_type IN ('Technical SQL', 'Data Warehouse')
GROUP BY iq.question_type
ORDER BY AVG(iq.my_rating) ASC;

-- ========================================
-- 8. ACTIONABLE INSIGHTS
-- ========================================
SELECT '' as blank;
SELECT
  '💡 ACTIONABLE INSIGHTS' as section,
  '' as blank1;

WITH stats AS (
  SELECT
    AVG(CASE WHEN is_correct = 1 THEN 1.0 ELSE 0.0 END) as accuracy,
    COUNT(*) as total,
    SUM(time_spent_minutes) as total_time
  FROM sql_practice_sessions
  WHERE practice_date >= DATE('now', '-7 days')
)
SELECT
  CASE
    WHEN total = 0 THEN 'No practice this week - Start with 3 Easy questions'
    WHEN total < 5 THEN 'Good start! Aim for 5+ sessions per week'
    WHEN accuracy < 0.6 THEN 'Focus on quality over quantity - Review mistakes'
    WHEN accuracy >= 0.8 THEN 'Great accuracy! Try harder questions'
    ELSE 'Consistent practice - Keep going!'
  END as Insight,
  total || ' sessions, ' || ROUND(accuracy * 100, 1) || '% accuracy' as ThisWeek
FROM stats;

.print ""
.print "════════════════════════════════════════════════════════"
.print "Use ./log-sql-practice.py to log your next practice!"
.print "════════════════════════════════════════════════════════"
