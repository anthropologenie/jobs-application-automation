-- ==========================================================
-- Migration: 006_add_practice_sessions.sql
--
-- Purpose:
--   Introduce a unified practice_sessions table for recording
--   interview preparation across SQL, Python, ETL,
--   Data Warehouse, AI Quality, System Design and other
--   learning domains.
--
-- Design Philosophy:
--   Keep the schema intentionally simple. Capture evidence
--   first, refine later based on actual usage.
--
-- Notes:
--   - Existing sql_practice_sessions remains unchanged.
--   - No CHECK constraints in v1.
--   - No FOREIGN KEY relationships in v1.
--   - Validation will be driven by usage before introducing
--     stricter schema constraints.
--
-- Author: Karthik Kattemane
-- Date: 2026-08-03
-- ==========================================================
-- Version History
--
-- v1.0 (2026-08-03)
--   Initial simplified schema validated against SQLite.
--   Constraints intentionally deferred until sufficient
--   practice data has been collected.
-- ==========================================================
-- ==========================================================

BEGIN TRANSACTION;

-- ==========================================================
-- Main Practice Sessions Table
-- ==========================================================

CREATE TABLE IF NOT EXISTS practice_sessions (

    -- ------------------------------------------------------
    -- Identity
    -- ------------------------------------------------------

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    practice_date DATE
        DEFAULT (DATE('now')),

    created_at TIMESTAMP
        DEFAULT CURRENT_TIMESTAMP,

    -- ------------------------------------------------------
    -- Context
    -- ------------------------------------------------------

    source TEXT,

    domain TEXT,

    platform TEXT,

    -- ------------------------------------------------------
    -- Problem
    -- ------------------------------------------------------

    question_text TEXT,

    my_solution TEXT,

    correct_solution TEXT,

    -- ------------------------------------------------------
    -- Outcome
    -- ------------------------------------------------------

    is_correct INTEGER
        DEFAULT 0,

    difficulty TEXT,

    time_spent_minutes INTEGER,

    -- ------------------------------------------------------
    -- Reflection
    -- ------------------------------------------------------

    error_made TEXT,

    lesson_learned TEXT,

    concepts_used TEXT,

    notes TEXT

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

COMMIT;