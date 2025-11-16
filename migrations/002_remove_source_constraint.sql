-- Migration: Remove CHECK constraint from opportunities.source column
-- This allows dynamic sources from job_sources table

PRAGMA foreign_keys=OFF;

BEGIN TRANSACTION;

-- Step 0: Drop trigger that references opportunities table
DROP TRIGGER IF EXISTS update_last_interaction;

-- Step 1: Create new table without source CHECK constraint
CREATE TABLE opportunities_migrated (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  company TEXT NOT NULL,
  role TEXT NOT NULL,
  job_url TEXT,
  source TEXT DEFAULT 'Other',  -- No CHECK constraint
  is_remote BOOLEAN DEFAULT 0,
  domain_match TEXT CHECK(domain_match IN ('Perfect', 'Good', 'Moderate', 'Poor')) DEFAULT 'Good',
  tech_stack TEXT,
  salary_range TEXT,
  status TEXT DEFAULT 'Lead' CHECK(status IN (
    'Lead', 'Applied', 'Screening', 'Technical', 'Manager',
    'Assignment', 'Offer', 'Negotiation', 'Accepted',
    'Rejected', 'Declined', 'Ghosted'
  )),
  discovered_date DATE DEFAULT (DATE('now')),
  applied_date DATE,
  first_contact_date DATE,
  last_interaction_date DATE,
  offer_date DATE,
  expected_start_date DATE,
  recruiter_name TEXT,
  recruiter_email TEXT,
  recruiter_phone TEXT,
  hiring_manager TEXT,
  notes TEXT,
  priority TEXT CHECK(priority IN ('High', 'Medium', 'Low')) DEFAULT 'Medium',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Step 2: Copy all existing data
INSERT INTO opportunities_migrated
SELECT * FROM opportunities;

-- Step 3: Drop old table
DROP TABLE opportunities;

-- Step 4: Rename new table to original name
ALTER TABLE opportunities_migrated RENAME TO opportunities;

-- Step 5: Recreate trigger
CREATE TRIGGER update_last_interaction
AFTER INSERT ON interactions
BEGIN
  UPDATE opportunities
  SET last_interaction_date = NEW.date
  WHERE id = NEW.opportunity_id;
END;

COMMIT;

PRAGMA foreign_keys=ON;
