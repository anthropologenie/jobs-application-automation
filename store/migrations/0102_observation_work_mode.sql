-- P3 (2026-09-30): a source's structured work-mode field ("Remote", "Hybrid (2 days WFO)")
-- is stored separately from its location string, so the evaluator can apply the
-- work-mode source precedence of jobops-policy@0.2.2 (work mode > location > title > JD).
-- Nullable and additive: existing observations keep NULL (not captured) and replay
-- unchanged under 0.2.0 / 0.2.1, which never read this column.
ALTER TABLE observation ADD COLUMN raw_work_mode TEXT;
