-- Apply after Parts 5/6. Idempotent, preserves existing data.
BEGIN;
CREATE EXTENSION IF NOT EXISTS btree_gist;
CREATE TABLE IF NOT EXISTS crew_availability (
 availability_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 crew_id VARCHAR(12) NOT NULL REFERENCES crews(crew_id),
 available_date DATE NOT NULL,
 shift_start TIME NOT NULL,
 shift_end TIME NOT NULL,
 availability_status VARCHAR(20) NOT NULL DEFAULT 'AVAILABLE'
  CHECK (availability_status IN ('AVAILABLE','LEAVE','UNAVAILABLE')),
 notes TEXT,
 updated_at TIMESTAMP NOT NULL DEFAULT now(),
 UNIQUE(crew_id,available_date),
 CHECK(shift_end>shift_start)
);
CREATE TABLE IF NOT EXISTS work_order_events (
 event_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 work_order_id BIGINT NOT NULL REFERENCES work_orders(work_order_id),
 event_type VARCHAR(40) NOT NULL,
 from_status VARCHAR(30),
 to_status VARCHAR(30),
 actor VARCHAR(80) NOT NULL,
 reason TEXT NOT NULL,
 recorded_at TIMESTAMP NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_work_order_events_order ON work_order_events(work_order_id,recorded_at);
CREATE TABLE IF NOT EXISTS access_restrictions (
 restriction_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 case_id BIGINT NOT NULL REFERENCES leak_cases(case_id),
 restriction_type VARCHAR(40) NOT NULL DEFAULT 'ACCESS_BLOCKED',
 details TEXT NOT NULL,
 active BOOLEAN NOT NULL DEFAULT TRUE,
 reported_by VARCHAR(80) NOT NULL,
 reported_at TIMESTAMP NOT NULL DEFAULT now(),
 resolved_at TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_access_restrictions_case ON access_restrictions(case_id,active);
-- Database-level protection against overlapping bookings for the same crew.
-- Requires btree_gist. Existing conflicting active assignments must be resolved first.
DO $$ BEGIN
 IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='no_active_crew_overlap') THEN
  ALTER TABLE crew_assignments ADD CONSTRAINT no_active_crew_overlap EXCLUDE USING gist
    (crew_id WITH =, tsrange(scheduled_start,scheduled_end,'[)') WITH &&)
    WHERE (assignment_status='ACTIVE');
 END IF;
END $$;
COMMIT;
