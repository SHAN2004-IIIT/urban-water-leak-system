CREATE UNIQUE INDEX IF NOT EXISTS uq_one_login_per_crew
ON app_users (crew_id)
WHERE role = 'CREW';