-- Migration 004: Add Parliament Decisions Tracking Table
-- This enables DIRECTION 2 (Training): Parliament advice → Real outcomes → Calibration
--
-- Purpose: Track Kragentic Parliament decisions and their real-world outcomes
-- to enable accuracy measurement and agent threshold calibration.
--
-- Usage:
--   1. Parliament makes recommendation → Log decision with log_parliament_decision()
--   2. User takes action (apply/don't apply)
--   3. Outcome becomes known (callback/no callback, etc.)
--   4. Update with update_decision_outcome()
--   5. Analyze accuracy with get_decision_accuracy_stats()
--   6. Calibrate agent thresholds based on accuracy patterns

CREATE TABLE IF NOT EXISTS parliament_decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Decision identification
    decision_id TEXT UNIQUE NOT NULL,
    timestamp TEXT NOT NULL,
    query TEXT NOT NULL,
    job_id INTEGER,

    -- Decision details
    agents_active TEXT,  -- JSON array of agent names that activated
    decision_text TEXT,  -- The synthesized parliamentary decision
    sparsity REAL,       -- Sparsity ratio (how many agents activated)
    confidence REAL,     -- Parliament's confidence in decision (0-1)
    dharmic_alignment REAL,  -- Dharmic alignment score (0-1)
    integration_used INTEGER DEFAULT 0,  -- Was jobs DB integration used?

    -- Outcome tracking (filled in later)
    applied INTEGER DEFAULT 0,      -- Did user apply to this job?
    callback INTEGER DEFAULT 0,     -- Did user get callback/response?
    interview INTEGER DEFAULT 0,    -- Did user get interview?
    offer INTEGER DEFAULT 0,        -- Did user get offer?
    outcome_notes TEXT,             -- Free-form notes about outcome
    outcome_date TEXT,              -- When outcome was recorded

    FOREIGN KEY (job_id) REFERENCES scraped_jobs(id)
);

-- Indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_parliament_decision_id
    ON parliament_decisions(decision_id);

CREATE INDEX IF NOT EXISTS idx_parliament_timestamp
    ON parliament_decisions(timestamp);

CREATE INDEX IF NOT EXISTS idx_parliament_job_id
    ON parliament_decisions(job_id);

CREATE INDEX IF NOT EXISTS idx_parliament_outcome_date
    ON parliament_decisions(outcome_date);

-- Index for accuracy analysis queries
CREATE INDEX IF NOT EXISTS idx_parliament_confidence_outcome
    ON parliament_decisions(confidence, outcome_date);

-- Comments for documentation
-- This table enables the training loop:
--   1. Parliament → Advice (logged here)
--   2. User → Action (applied field)
--   3. Reality → Outcome (callback/interview/offer fields)
--   4. System → Learning (accuracy stats → threshold calibration)
