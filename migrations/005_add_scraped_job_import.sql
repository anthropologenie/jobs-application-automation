-- Migration 005: FEATURE-001 — Scraped Job Import provenance column
-- Renumbered from the prepared 006 -> 005: live migrations/ only has
-- 002, 003, 004 (no 001, no 005) so 005 is the actual next free number.
--
-- Additive only — nullable, no FK constraint, no data touched.

ALTER TABLE opportunities ADD COLUMN scraped_job_id INTEGER;
