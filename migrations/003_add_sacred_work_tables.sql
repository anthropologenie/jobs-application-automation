-- Migration 003: Add Sacred Work Tracking
-- Date: 2025-11-12

CREATE TABLE IF NOT EXISTS sacred_work_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date DATE DEFAULT CURRENT_DATE,
    stone_number INTEGER NOT NULL,
    stone_title TEXT NOT NULL,
    time_spent_minutes INTEGER NOT NULL,
    what_built TEXT NOT NULL,
    insights TEXT,
    next_stone TEXT,
    felt_sense TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(stone_number)
);

CREATE TRIGGER IF NOT EXISTS update_sacred_work_timestamp
AFTER UPDATE ON sacred_work_log
BEGIN
    UPDATE sacred_work_log SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

CREATE INDEX IF NOT EXISTS idx_sacred_work_date ON sacred_work_log(date);
CREATE INDEX IF NOT EXISTS idx_sacred_work_stone ON sacred_work_log(stone_number);

CREATE VIEW IF NOT EXISTS sacred_work_progress AS
SELECT
    stone_number,
    stone_title,
    date,
    time_spent_minutes,
    what_built,
    insights,
    CASE
        WHEN next_stone IS NOT NULL AND next_stone != '' THEN 'Complete'
        ELSE 'In Progress'
    END as status,
    created_at
FROM sacred_work_log
ORDER BY stone_number ASC;

CREATE VIEW IF NOT EXISTS sacred_work_stats AS
SELECT
    COUNT(*) as total_stones,
    SUM(time_spent_minutes) as total_minutes,
    ROUND(AVG(time_spent_minutes), 1) as avg_minutes_per_stone,
    MIN(date) as first_stone_date,
    MAX(date) as latest_stone_date,
    ROUND(SUM(time_spent_minutes) / 60.0, 1) as total_hours
FROM sacred_work_log;
