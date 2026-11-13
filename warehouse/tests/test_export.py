from datetime import datetime, timezone
from decimal import Decimal
from warehouse.export_postgres import QUERIES, json_default

def test_no_user_passwords_exported():
    assert 'app_users' not in QUERIES
    assert 'reporter_token' not in repr(QUERIES)

def test_decimal_and_datetime_serializable():
    assert json_default(Decimal('3.50')) == 3.5
    assert json_default(datetime(2026,1,1,tzinfo=timezone.utc)).startswith('2026-01-01')

def test_export_includes_outcomes():
    assert {'repair_outcomes','work_orders','leak_cases','risk_scores'} <= set(QUERIES)
