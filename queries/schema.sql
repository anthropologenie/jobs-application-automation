-- jobs-tracker.db schema v1.0

-- Table 1: Opportunities
CREATE TABLE IF NOT EXISTS opportunities (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  company TEXT NOT NULL,
  role TEXT NOT NULL,
  job_url TEXT,
  source TEXT CHECK(source IN ('LinkedIn', 'Naukri', 'Indeed', 'Referral', 'Direct', 'Gmail', 'Other')) DEFAULT 'Other',
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

-- Table 2: Interactions
CREATE TABLE IF NOT EXISTS interactions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  opportunity_id INTEGER NOT NULL,
  type TEXT CHECK(type IN ('Call', 'Email', 'Interview', 'Assessment', 'Offer Discussion', 'Follow-up', 'Rejection')) NOT NULL,
  date DATE NOT NULL DEFAULT (DATE('now')),
  time TIME,
  duration_minutes INTEGER,
  calendar_event_id TEXT UNIQUE,
  meet_link TEXT,
  location TEXT,
  participants TEXT,
  summary TEXT,
  action_items TEXT,
  sentiment TEXT CHECK(sentiment IN ('Positive', 'Neutral', 'Negative', 'Unknown')) DEFAULT 'Unknown',
  requires_followup BOOLEAN DEFAULT 0,
  followup_date DATE,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (opportunity_id) REFERENCES opportunities(id) ON DELETE CASCADE
);

-- Table 3: Documents
CREATE TABLE IF NOT EXISTS documents (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  opportunity_id INTEGER,
  type TEXT CHECK(type IN ('Resume', 'Cover Letter', 'Assignment', 'Assessment', 'Offer Letter', 'Contract', 'Other')) NOT NULL,
  file_path TEXT NOT NULL,
  file_name TEXT NOT NULL,
  file_size_kb INTEGER,
  uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  notes TEXT,
  FOREIGN KEY (opportunity_id) REFERENCES opportunities(id) ON DELETE SET NULL
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_status ON opportunities(status);
CREATE INDEX IF NOT EXISTS idx_discovered_date ON opportunities(discovered_date);
CREATE INDEX IF NOT EXISTS idx_remote ON opportunities(is_remote);
CREATE INDEX IF NOT EXISTS idx_priority ON opportunities(priority);
CREATE INDEX IF NOT EXISTS idx_opportunity_interactions ON interactions(opportunity_id);
CREATE INDEX IF NOT EXISTS idx_interaction_date ON interactions(date);
CREATE INDEX IF NOT EXISTS idx_calendar_event ON interactions(calendar_event_id);

-- Triggers
CREATE TRIGGER IF NOT EXISTS update_opportunity_timestamp 
AFTER UPDATE ON opportunities
BEGIN
  UPDATE opportunities SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS update_last_interaction 
AFTER INSERT ON interactions
BEGIN
  UPDATE opportunities 
  SET last_interaction_date = NEW.date 
  WHERE id = NEW.opportunity_id;
END;

-- Views
CREATE VIEW IF NOT EXISTS active_pipeline AS
SELECT 
  o.id,
  o.company,
  o.role,
  o.status,
  o.is_remote,
  o.priority,
  o.tech_stack,
  o.discovered_date,
  o.last_interaction_date,
  COUNT(i.id) as interaction_count,
  MAX(i.date) as latest_interaction,
  o.updated_at
FROM opportunities o
LEFT JOIN interactions i ON o.id = i.opportunity_id
WHERE o.status NOT IN ('Rejected', 'Declined', 'Ghosted', 'Accepted')
GROUP BY o.id
ORDER BY o.priority DESC, o.updated_at DESC;

CREATE VIEW IF NOT EXISTS todays_agenda AS
SELECT 
  i.id,
  i.type,
  i.date,
  i.time,
  i.meet_link,
  o.company,
  o.role,
  o.status,
  i.participants,
  i.summary
FROM interactions i
JOIN opportunities o ON i.opportunity_id = o.id
WHERE i.date = DATE('now')
ORDER BY i.time ASC;
