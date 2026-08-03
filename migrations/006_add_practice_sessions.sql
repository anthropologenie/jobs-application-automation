-- ==========================================================
-- Migration: 006_add_practice_sessions.sql
--
-- Purpose:
--   Introduce a unified practice_sessions table for recording
--   interview preparation across multiple domains including
--   SQL, Python, ETL, Data Warehouse, AI Quality and
--   System Design.
--
-- Notes:
--   - Existing sql_practice_sessions remains unchanged and
--     continues to represent historical SQL-specific practice.
--   - This migration introduces a generalized practice model
--     for future learning sessions.
--
-- Author: Karthik Kattemane
-- Date: 2026-08-03
-- ==========================================================

BEGIN TRANSACTION;

-- ==========================================================
-- Main Practice Sessions Table
-- ==========================================================

CREATE TABLE IF NOT EXISTS practice_sessions (

    -- Primary Key
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- ------------------------------------------------------
    -- Identity
    -- ------------------------------------------------------
    practice_date DATE NOT NULL
        DEFAULT (DATE('now')),

    created_at TIMESTAMP NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    -- ------------------------------------------------------
    -- Context
    -- ------------------------------------------------------
    source TEXT NOT NULL
        DEFAULT 'Practice'
        CHECK (
            source IN (
                'Practice',
                'Interview'
            )
        ),

    domain TEXT NOT NULL
        CHECK (
            domain IN (
                'SQL',
                'Python',
                'ETL',
                'Data Warehouse',
                'AI Quality',
                'System Design',
                'Other'
            )
        ),

    platform TEXT,

    related_opportunity_id INTEGER,

    -- ------------------------------------------------------
    -- Problem
    -- ------------------------------------------------------
    question_text TEXT NOT NULL,

    my_solution TEXT NOT NULL,

    correct_solution TEXT,

    -- ------------------------------------------------------
    -- Outcome
    -- ------------------------------------------------------
    is_correct BOOLEAN NOT NULL
        DEFAULT 0,

    difficulty TEXT
        CHECK (
            difficulty IN (
                'Easy',
                'Medium',
                'Hard'
            )
        ),

    time_spent_minutes INTEGER,

    -- ------------------------------------------------------
    -- Reflection
    -- ------------------------------------------------------
    error_made TEXT,

    lesson_learned TEXT,

    concepts_used TEXT,

    notes TEXT,

    -- ------------------------------------------------------
    -- Relationships
    -- ------------------------------------------------------
    FOREIGN KEY (related_opportunity_id)
        REFERENCES opportunities(id)
        ON DELETE SET NULL
);

-- ==========================================================
-- Indexes
-- ==========================================================

CREATE INDEX IF NOT EXISTS idx_practice_sessions_date
ON practice_sessions(practice_date);

CREATE INDEX IF NOT EXISTS idx_practice_sessions_domain
ON practice_sessions(domain);

CREATE INDEX IF NOT EXISTS idx_practice_sessions_source
ON practice_sessions(source);

CREATE INDEX IF NOT EXISTS idx_practice_sessions_difficulty
ON practice_sessions(difficulty);

CREATE INDEX IF NOT EXISTS idx_practice_sessions_correct
ON practice_sessions(is_correct);

CREATE INDEX IF NOT EXISTS idx_practice_sessions_opportunity
ON practice_sessions(related_opportunity_id);

COMMIT;

-- ==========================================================
-- Verification (Optional)
--
-- SELECT name
-- FROM sqlite_master
-- WHERE type = 'table'
--   AND name = 'practice_sessions';
-- ==========================================================