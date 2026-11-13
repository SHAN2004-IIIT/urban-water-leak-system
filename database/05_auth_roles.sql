-- Apply AFTER Part 5 schema and migration. Never drops data.
BEGIN;
CREATE TABLE IF NOT EXISTS app_users (
 user_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 username VARCHAR(80) NOT NULL UNIQUE,
 password_hash VARCHAR(100) NOT NULL,
 role VARCHAR(20) NOT NULL CHECK (role IN ('ADMIN','SUPERVISOR','CREW')),
 crew_id VARCHAR(12) REFERENCES crews(crew_id),
 enabled BOOLEAN NOT NULL DEFAULT TRUE,
 created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
 CONSTRAINT crew_link_required CHECK ((role='CREW' AND crew_id IS NOT NULL) OR (role <> 'CREW' AND crew_id IS NULL))
);
CREATE INDEX IF NOT EXISTS idx_app_users_crew ON app_users(crew_id);
COMMIT;
