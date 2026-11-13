from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def test_expected_files():
    for file in [
        'database/06_scheduling_migration.sql',
        'backend/src/main/java/com/waterleak/scheduling/SchedulingController.java',
        'backend/src/main/java/com/waterleak/scheduling/SchedulingService.java',
        'frontend/src/pages/SchedulingPage.jsx',
        'frontend/src/components/CrewCalendar.jsx',
        'frontend/src/components/AssignmentModal.jsx',
        'frontend/src/components/RiskExplanation.jsx',
    ]:
        assert (ROOT/file).exists()

def test_migration_has_overlap_guard():
    sql=(ROOT/'database/06_scheduling_migration.sql').read_text()
    assert 'EXCLUDE USING gist' in sql
    assert 'work_order_events' in sql
    assert 'access_restrictions' in sql

def test_old_endpoints_delegate_to_new_logic():
    api=(ROOT/'backend/src/main/java/com/waterleak/ApiController.java').read_text()
    assert 'schedule.assign(' in api
    assert 'schedule.setAccess(' in api
