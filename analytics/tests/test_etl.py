import pandas as pd
from analytics.etl.transform import calculate_intervals


def test_rollover_and_normal_delta():
    rows = []
    for idx, (t, register) in enumerate([
        ('2026-10-01 00:00:00', 99990),
        ('2026-10-01 01:00:00', 5),
        ('2026-10-01 02:00:00', 35),
    ], 1):
        rows.append(dict(meter_id='M1', zone_id='Z1', location_id='LOC1',
                         reading_id=f'R{idx}', reading_timestamp=pd.Timestamp(t),
                         register_value_litres=register, etl_quality='VALID',
                         expected_reading_interval_hours=1,
                         register_max_value=99999, baseline_daily_litres=600))
    result = calculate_intervals(pd.DataFrame(rows))
    assert result['interval_status'].tolist() == ['ROLLOVER', 'OK']
    assert result['consumption_litres'].tolist() == [15, 30]


def test_gap_is_not_interpreted_as_hourly_consumption():
    rows = []
    for idx, (t, register) in enumerate([
        ('2026-10-01 00:00:00', 1000),
        ('2026-10-01 03:00:00', 1090),
    ], 1):
        rows.append(dict(meter_id='M1', zone_id='Z1', location_id='LOC1',
                         reading_id=f'R{idx}', reading_timestamp=pd.Timestamp(t),
                         register_value_litres=register, etl_quality='VALID',
                         expected_reading_interval_hours=1,
                         register_max_value=99999, baseline_daily_litres=600))
    result = calculate_intervals(pd.DataFrame(rows))
    assert result.iloc[0]['interval_status'] == 'GAP_INTERVAL'
    assert pd.isna(result.iloc[0]['consumption_litres'])
