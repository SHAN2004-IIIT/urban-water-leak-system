-- Part 1: PostgreSQL operational schema. Source CSV timestamps are local time.
-- Run this on a NEW empty water_leak_db database.
BEGIN;

CREATE TABLE zones (
    zone_id VARCHAR(12) PRIMARY KEY,
    zone_name VARCHAR(120) NOT NULL,
    ward_number INTEGER,
    city VARCHAR(100) NOT NULL,
    latitude NUMERIC(10,6),
    longitude NUMERIC(10,6),
    population_estimate INTEGER CHECK (population_estimate >= 0),
    critical_facilities_count INTEGER CHECK (critical_facilities_count >= 0),
    pipe_age_years INTEGER CHECK (pipe_age_years >= 0),
    dominant_pipe_material VARCHAR(30),
    average_pressure_bar NUMERIC(6,2),
    zone_status VARCHAR(30) NOT NULL
);

CREATE TABLE meters (
    meter_id VARCHAR(12) PRIMARY KEY,
    zone_id VARCHAR(12) NOT NULL REFERENCES zones(zone_id),
    location_id VARCHAR(30) NOT NULL,
    customer_category VARCHAR(40) NOT NULL,
    meter_type VARCHAR(30) NOT NULL,
    installation_date DATE,
    reading_unit VARCHAR(10) NOT NULL,
    register_max_value BIGINT NOT NULL CHECK (register_max_value > 0),
    expected_reading_interval_hours INTEGER NOT NULL CHECK (expected_reading_interval_hours > 0),
    baseline_daily_litres NUMERIC(14,3),
    latitude NUMERIC(10,6),
    longitude NUMERIC(10,6),
    meter_status VARCHAR(30) NOT NULL,
    last_service_date DATE,
    UNIQUE (zone_id, location_id)
);

CREATE TABLE meter_readings (
    reading_id VARCHAR(16) PRIMARY KEY,
    meter_id VARCHAR(12) NOT NULL REFERENCES meters(meter_id),
    reading_timestamp TIMESTAMP NOT NULL,
    -- Nullable by design: a raw missing reading is not zero water consumption.
    -- Do NOT constrain to the register maximum: bad raw readings must be ingestible.
    register_value_litres BIGINT,
    reading_source VARCHAR(30) NOT NULL,
    quality_flag VARCHAR(30) NOT NULL,
    ingested_at TIMESTAMP NOT NULL,
    note TEXT,
    UNIQUE (meter_id, reading_timestamp)
);
CREATE INDEX idx_readings_meter_time ON meter_readings(meter_id, reading_timestamp);

CREATE TABLE complaints (
    complaint_id VARCHAR(16) PRIMARY KEY,
    zone_id VARCHAR(12) NOT NULL REFERENCES zones(zone_id),
    location_id VARCHAR(30),
    meter_id VARCHAR(12) REFERENCES meters(meter_id),
    reported_at TIMESTAMP NOT NULL,
    complaint_type VARCHAR(60) NOT NULL,
    severity_reported VARCHAR(20) NOT NULL,
    description TEXT,
    reporter_token VARCHAR(30),
    latitude NUMERIC(10,6),
    longitude NUMERIC(10,6),
    report_channel VARCHAR(40),
    complaint_status VARCHAR(30) NOT NULL,
    access_issue_reported VARCHAR(120)
);
CREATE INDEX idx_complaints_zone_time ON complaints(zone_id, reported_at);
CREATE INDEX idx_complaints_location_time ON complaints(location_id, reported_at);

CREATE TABLE crews (
    crew_id VARCHAR(12) PRIMARY KEY,
    crew_name VARCHAR(100) NOT NULL,
    home_zone_id VARCHAR(12) NOT NULL REFERENCES zones(zone_id),
    specialization VARCHAR(60) NOT NULL,
    crew_size INTEGER NOT NULL CHECK (crew_size > 0),
    shift_start TIME NOT NULL,
    shift_end TIME NOT NULL,
    availability_date DATE NOT NULL,
    availability_status VARCHAR(30) NOT NULL,
    vehicle_id VARCHAR(20),
    max_jobs_per_day INTEGER NOT NULL CHECK (max_jobs_per_day > 0),
    has_excavation_equipment VARCHAR(3) NOT NULL CHECK (has_excavation_equipment IN ('Yes', 'No')),
    supervisor_ref VARCHAR(20)
);

-- System-generated records: not imported from the five input CSVs.
CREATE TABLE leak_cases (
    case_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    zone_id VARCHAR(12) NOT NULL REFERENCES zones(zone_id),
    location_id VARCHAR(30),
    case_status VARCHAR(30) NOT NULL DEFAULT 'SUSPECTED',
    access_status VARCHAR(30) NOT NULL DEFAULT 'UNKNOWN',
    access_reason TEXT,
    detected_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_leak_cases_zone_status ON leak_cases(zone_id, case_status);

CREATE TABLE case_evidence (
    evidence_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    case_id BIGINT NOT NULL REFERENCES leak_cases(case_id),
    reading_id VARCHAR(16) REFERENCES meter_readings(reading_id),
    complaint_id VARCHAR(16) REFERENCES complaints(complaint_id),
    evidence_type VARCHAR(40) NOT NULL,
    details JSONB NOT NULL DEFAULT '{}'::jsonb,
    added_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK ((reading_id IS NOT NULL)::int + (complaint_id IS NOT NULL)::int <= 1)
);

CREATE TABLE risk_scores (
    risk_score_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    case_id BIGINT NOT NULL REFERENCES leak_cases(case_id),
    score NUMERIC(5,2) NOT NULL CHECK (score >= 0 AND score <= 100),
    score_components JSONB NOT NULL,
    model_name VARCHAR(100) NOT NULL,
    model_version VARCHAR(30) NOT NULL,
    data_quality_notes TEXT,
    calculated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE work_orders (
    work_order_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    case_id BIGINT NOT NULL REFERENCES leak_cases(case_id),
    work_type VARCHAR(30) NOT NULL DEFAULT 'INSPECTION',
    status VARCHAR(30) NOT NULL DEFAULT 'CREATED',
    estimated_duration_minutes INTEGER CHECK (estimated_duration_minutes > 0),
    scheduling_reason TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE crew_assignments (
    assignment_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    work_order_id BIGINT NOT NULL REFERENCES work_orders(work_order_id),
    crew_id VARCHAR(12) NOT NULL REFERENCES crews(crew_id),
    scheduled_start TIMESTAMP NOT NULL,
    scheduled_end TIMESTAMP NOT NULL,
    assignment_status VARCHAR(30) NOT NULL DEFAULT 'ACTIVE',
    reason TEXT,
    assigned_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (scheduled_end > scheduled_start)
);
CREATE INDEX idx_crew_assignments_crew_start ON crew_assignments(crew_id, scheduled_start);
-- Overlap checks and assignment authorization belong in the scheduling service.

CREATE TABLE repair_outcomes (
    outcome_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    work_order_id BIGINT NOT NULL REFERENCES work_orders(work_order_id),
    outcome_type VARCHAR(30) NOT NULL CHECK (outcome_type IN ('CONFIRMED_LEAK', 'NO_LEAK', 'INCONCLUSIVE')),
    leak_type VARCHAR(60),
    estimated_water_loss_litres NUMERIC(14,2),
    repair_notes TEXT,
    inspected_at TIMESTAMP NOT NULL,
    recorded_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

COMMIT;
