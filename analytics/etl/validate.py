"""Validate master data and their relationships."""
import pandas as pd

def validate_master(t):
    zones=t['zones'].copy()
    meters=t['meters'].copy()
    crews=t['crews'].copy()
    for name, df, key in [('zones',zones,'zone_id'),('meters',meters,'meter_id'),('crews',crews,'crew_id')]:
        if df[key].isna().any() or df[key].duplicated().any():
            raise ValueError(f'{name}: duplicate or missing {key}; fix master data first')
    if (~meters['zone_id'].isin(zones['zone_id'])).any():
        raise ValueError('meters.csv contains unknown zone_id')
    if (~crews['home_zone_id'].isin(zones['zone_id'])).any():
        raise ValueError('crews.csv contains unknown home_zone_id')
    for col in ('register_max_value','expected_reading_interval_hours','baseline_daily_litres'):
        meters[col]=pd.to_numeric(meters[col], errors='coerce')
    if (meters[['register_max_value','expected_reading_interval_hours','baseline_daily_litres']].isna().any().any() or
        (meters[['register_max_value','expected_reading_interval_hours','baseline_daily_litres']] <= 0).any().any()):
        raise ValueError('Meters must have positive register max, interval hours, and baseline daily litres')
    if (~meters['reading_unit'].eq('L')).any():
        raise ValueError('This example ETL supports cumulative litre registers only (reading_unit=L)')
    if meters.duplicated(['zone_id','location_id']).any():
        raise ValueError('meters.csv contains duplicate zone/location combinations')
    return zones, meters, crews

