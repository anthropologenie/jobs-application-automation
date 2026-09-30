-- 0100_v2_core: JobOps v2 core schema (Phase B).
-- Facts (observation, evidence) are append-only; judgments (evaluation) are immutable.
-- Only PASS / FAIL / UNKNOWN can be stored as an eligibility verdict.

CREATE TABLE company (
  company_id TEXT PRIMARY KEY,
  canonical_name TEXT NOT NULL,
  normalized_name TEXT NOT NULL UNIQUE,
  official_domain TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE company_ats_identity (
  ats_type TEXT NOT NULL,
  ats_slug TEXT NOT NULL,
  company_id TEXT NOT NULL REFERENCES company(company_id),
  discovered_via_observation_id TEXT,
  verified_at TEXT,
  PRIMARY KEY (ats_type, ats_slug)
);

CREATE TABLE company_classification (
  classification_id TEXT PRIMARY KEY,
  company_id TEXT NOT NULL REFERENCES company(company_id),
  classification TEXT NOT NULL CHECK (classification IN
    ('PRODUCT','AI_NATIVE','GCC','ENGINEERING_LED','ENTERPRISE_DIRECT','STAFFING','CONSULTANCY','IT_SERVICES','UNKNOWN')),
  basis TEXT NOT NULL CHECK (basis IN ('INFERRED_FROM_EVIDENCE','REGISTRY_LIST','OWNER_CONFIRMED')),
  evidence_json TEXT,
  decided_by TEXT NOT NULL,
  decided_at TEXT NOT NULL,
  supersedes TEXT REFERENCES company_classification(classification_id)
);
CREATE TRIGGER company_classification_no_update BEFORE UPDATE ON company_classification
  BEGIN SELECT RAISE(ABORT, 'company_classification is append-only'); END;
CREATE TRIGGER company_classification_no_delete BEFORE DELETE ON company_classification
  BEGIN SELECT RAISE(ABORT, 'company_classification is append-only'); END;

CREATE TABLE run (
  run_id TEXT PRIMARY KEY,
  started_at TEXT NOT NULL,
  finished_at TEXT,
  terminating_condition TEXT,
  note TEXT
);

CREATE TABLE requisition (
  requisition_id TEXT PRIMARY KEY,
  company_id TEXT REFERENCES company(company_id),
  canonical_title TEXT,
  canonical_url TEXT,
  canonical_url_authority INTEGER,
  normalized_location TEXT,
  l3_key TEXT,
  first_seen_at TEXT NOT NULL,
  last_seen_at TEXT NOT NULL,
  first_seen_run_id TEXT NOT NULL,
  last_seen_run_id TEXT NOT NULL,
  source_first_seen_json TEXT NOT NULL DEFAULT '{}',
  canonical_posting_date TEXT,
  date_precision TEXT CHECK (date_precision IN ('DATE','TIMESTAMP','NONE')),
  newness_state TEXT NOT NULL CHECK (newness_state IN ('NEW','UPDATED','SEEN_BEFORE')),
  newness_confidence TEXT,
  newness_reason_json TEXT,
  identity_confidence TEXT NOT NULL DEFAULT 'DEFINITE',
  identity_flags_json TEXT NOT NULL DEFAULT '[]',
  duplicate_of TEXT REFERENCES requisition(requisition_id),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE INDEX ix_requisition_l3 ON requisition(l3_key);

CREATE TABLE requisition_key (
  key_type TEXT NOT NULL CHECK (key_type IN ('L1','L2','L4')),
  key_value TEXT NOT NULL,
  requisition_id TEXT NOT NULL REFERENCES requisition(requisition_id),
  PRIMARY KEY (key_type, key_value)
);

CREATE TABLE observation (
  observation_id TEXT PRIMARY KEY,
  requisition_id TEXT NOT NULL REFERENCES requisition(requisition_id),
  run_id TEXT NOT NULL REFERENCES run(run_id),
  source TEXT NOT NULL,
  source_kind TEXT NOT NULL,
  source_external_id TEXT,
  source_url TEXT,
  apply_url TEXT,
  observed_at TEXT NOT NULL,
  raw_title TEXT, raw_company TEXT, raw_location TEXT, raw_salary TEXT,
  raw_employment_type TEXT, raw_text TEXT,
  source_posted_date TEXT, source_updated_date TEXT,
  date_precision TEXT,
  completeness TEXT NOT NULL CHECK (completeness IN ('FULL_JD','PARTIAL','SEARCH_ONLY')),
  source_authority_tier INTEGER NOT NULL,
  language_detection_json TEXT,
  content_hash TEXT NOT NULL,
  seq INTEGER NOT NULL
);
CREATE INDEX ix_observation_req ON observation(requisition_id);
CREATE TRIGGER observation_no_update BEFORE UPDATE ON observation
  BEGIN SELECT RAISE(ABORT, 'observation is immutable'); END;
CREATE TRIGGER observation_no_delete BEFORE DELETE ON observation
  BEGIN SELECT RAISE(ABORT, 'observation is immutable'); END;

CREATE TABLE evidence (
  evidence_id TEXT PRIMARY KEY,
  requisition_id TEXT NOT NULL REFERENCES requisition(requisition_id),
  observation_id TEXT NOT NULL REFERENCES observation(observation_id),
  extractor_version TEXT NOT NULL,
  ordinal INTEGER NOT NULL,
  dimension TEXT NOT NULL,
  evidence_type TEXT NOT NULL,
  strength TEXT NOT NULL CHECK (strength IN ('PRIMARY','CONTEXT')),
  state TEXT NOT NULL DEFAULT 'STATED' CHECK (state IN ('STATED','STATED_NONE')),
  source TEXT NOT NULL,
  source_field TEXT NOT NULL,
  quoted_span TEXT,
  normalized_value_json TEXT NOT NULL,
  extracted_at TEXT NOT NULL,
  content_hash TEXT NOT NULL,
  supersedes_evidence_id TEXT REFERENCES evidence(evidence_id),
  UNIQUE (observation_id, extractor_version, ordinal)
);
CREATE INDEX ix_evidence_obs ON evidence(observation_id, extractor_version);
CREATE TRIGGER evidence_no_update BEFORE UPDATE ON evidence
  BEGIN SELECT RAISE(ABORT, 'evidence is append-only'); END;
CREATE TRIGGER evidence_no_delete BEFORE DELETE ON evidence
  BEGIN SELECT RAISE(ABORT, 'evidence is append-only'); END;

CREATE TABLE evaluation (
  evaluation_id TEXT PRIMARY KEY,
  requisition_id TEXT NOT NULL REFERENCES requisition(requisition_id),
  policy_version TEXT NOT NULL,
  evidence_hash TEXT NOT NULL,
  evaluated_at TEXT NOT NULL,
  eligibility_overall TEXT NOT NULL CHECK (eligibility_overall IN ('PASS','FAIL','UNKNOWN')),
  relevance_label TEXT NOT NULL CHECK (relevance_label IN ('STRONG','MODERATE','WEAK','NOT_ASSESSED')),
  queue_lane TEXT NOT NULL,
  flags_json TEXT NOT NULL,
  result_json TEXT NOT NULL,
  evaluator_version TEXT NOT NULL,
  seq INTEGER NOT NULL,
  UNIQUE (requisition_id, policy_version, evidence_hash)
);
CREATE TRIGGER evaluation_no_update BEFORE UPDATE ON evaluation
  BEGIN SELECT RAISE(ABORT, 'evaluations are immutable'); END;
CREATE TRIGGER evaluation_no_delete BEFORE DELETE ON evaluation
  BEGIN SELECT RAISE(ABORT, 'evaluations are immutable'); END;

CREATE TABLE evaluation_dimension (
  evaluation_id TEXT NOT NULL REFERENCES evaluation(evaluation_id),
  dimension TEXT NOT NULL,
  verdict TEXT NOT NULL CHECK (verdict IN ('PASS','FAIL','UNKNOWN')),
  rule_id TEXT NOT NULL,
  flags_json TEXT NOT NULL,
  PRIMARY KEY (evaluation_id, dimension)
);

CREATE TABLE identity_link (
  link_id TEXT PRIMARY KEY,
  requisition_a TEXT NOT NULL REFERENCES requisition(requisition_id),
  requisition_b TEXT NOT NULL REFERENCES requisition(requisition_id),
  outcome TEXT NOT NULL CHECK (outcome IN ('DEFINITE_DUPLICATE','PROBABLE_DUPLICATE','IDENTITY_UNCERTAIN')),
  layer TEXT,
  reason TEXT,
  decided_by TEXT NOT NULL,
  decided_at TEXT NOT NULL
);

CREATE TABLE review_decision (
  decision_id TEXT PRIMARY KEY,
  requisition_id TEXT NOT NULL REFERENCES requisition(requisition_id),
  kind TEXT NOT NULL CHECK (kind IN ('ACCEPT','SKIP','DEFER','RESOLVE_UNKNOWN','CONFIRM_DUPLICATE','REJECT_DUPLICATE','REOPEN')),
  actor TEXT NOT NULL CHECK (actor = 'human'),
  decided_at TEXT NOT NULL,
  note TEXT,
  machine_context_json TEXT
);
CREATE TRIGGER review_decision_no_update BEFORE UPDATE ON review_decision
  BEGIN SELECT RAISE(ABORT, 'review decisions are append-only'); END;

CREATE TABLE application (
  application_event_id TEXT PRIMARY KEY,
  requisition_id TEXT NOT NULL REFERENCES requisition(requisition_id),
  event TEXT NOT NULL CHECK (event IN ('PROMOTED','SUBMITTED_BY_HUMAN','WITHDRAWN','OUTCOME')),
  actor TEXT NOT NULL CHECK (actor = 'human'),
  event_at TEXT NOT NULL,
  recorded_at TEXT NOT NULL,
  method TEXT,
  note TEXT
);
CREATE TRIGGER application_no_update BEFORE UPDATE ON application
  BEGIN SELECT RAISE(ABORT, 'application events are append-only'); END;

CREATE TABLE fx_rate (
  fx_id TEXT PRIMARY KEY,
  base_currency TEXT NOT NULL,
  quote_currency TEXT NOT NULL DEFAULT 'INR' CHECK (quote_currency = 'INR'),
  rate REAL NOT NULL CHECK (rate > 0),
  snapshot_date TEXT NOT NULL,
  source TEXT NOT NULL,
  entered_by TEXT NOT NULL,
  entered_at TEXT NOT NULL,
  UNIQUE (base_currency, quote_currency, snapshot_date, source)
);

CREATE TABLE queue_state (
  requisition_id TEXT PRIMARY KEY REFERENCES requisition(requisition_id),
  carry_days INTEGER NOT NULL DEFAULT 0,
  first_review_day TEXT,
  last_planned_day TEXT,
  last_surfaced_day TEXT,
  overflow_parked_on TEXT
);
