-- Run AFTER 01_schema.sql and the original raw-data import.
BEGIN;
ALTER TABLE leak_cases ADD COLUMN IF NOT EXISTS source_case_id VARCHAR(100);
CREATE UNIQUE INDEX IF NOT EXISTS ux_leak_cases_source ON leak_cases(source_case_id);
ALTER TABLE leak_cases ADD COLUMN IF NOT EXISTS meter_id VARCHAR(12) REFERENCES meters(meter_id);
ALTER TABLE leak_cases ADD COLUMN IF NOT EXISTS risk_band VARCHAR(12);
ALTER TABLE leak_cases ADD COLUMN IF NOT EXISTS score_explanation TEXT;
-- Detailed score history remains in the original risk_scores table.
CREATE TABLE IF NOT EXISTS application_events (
 event_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 event_type VARCHAR(60) NOT NULL,
 entity_type VARCHAR(40) NOT NULL,
 entity_id BIGINT NOT NULL,
 details JSONB NOT NULL DEFAULT '{}'::jsonb,
 recorded_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_work_order_case ON work_orders(case_id);
CREATE INDEX IF NOT EXISTS ix_assignment_work_order ON crew_assignments(work_order_id);
COMMIT;
