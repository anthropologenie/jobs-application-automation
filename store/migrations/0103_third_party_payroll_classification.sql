-- P5 (2026-09-30), Owner Addendum E5: THIRD_PARTY_PAYROLL is an explicit employer
-- classification (third-party payroll / body shop / client placement -> employer_type FAIL
-- under jobops-policy@0.2.3). SQLite cannot alter a CHECK constraint in place, so the
-- append-only table is rebuilt with every row copied verbatim (same ids, same order).
-- Policies before 0.2.3 have no rule for the new value and fall through to their
-- catch-all (UNKNOWN + EMPLOYER_UNCLASSIFIED); existing rows are unchanged.
DROP TRIGGER company_classification_no_update;
DROP TRIGGER company_classification_no_delete;
ALTER TABLE company_classification RENAME TO company_classification_pre0103;
CREATE TABLE company_classification (
  classification_id TEXT PRIMARY KEY,
  company_id TEXT NOT NULL REFERENCES company(company_id),
  classification TEXT NOT NULL CHECK (classification IN
    ('PRODUCT','AI_NATIVE','GCC','ENGINEERING_LED','ENTERPRISE_DIRECT','STAFFING','CONSULTANCY','IT_SERVICES',
     'THIRD_PARTY_PAYROLL','UNKNOWN')),
  basis TEXT NOT NULL CHECK (basis IN ('INFERRED_FROM_EVIDENCE','REGISTRY_LIST','OWNER_CONFIRMED')),
  evidence_json TEXT,
  decided_by TEXT NOT NULL,
  decided_at TEXT NOT NULL,
  supersedes TEXT REFERENCES company_classification(classification_id)
);
INSERT INTO company_classification
  SELECT classification_id, company_id, classification, basis, evidence_json, decided_by, decided_at, supersedes
  FROM company_classification_pre0103 ORDER BY rowid;
DROP TABLE company_classification_pre0103;
CREATE TRIGGER company_classification_no_update BEFORE UPDATE ON company_classification
  BEGIN SELECT RAISE(ABORT, 'company_classification is append-only'); END;
CREATE TRIGGER company_classification_no_delete BEFORE DELETE ON company_classification
  BEGIN SELECT RAISE(ABORT, 'company_classification is append-only'); END;
