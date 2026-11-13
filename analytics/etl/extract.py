"""Extract source CSVs without modifying their contents."""
from pathlib import Path
import pandas as pd

SCHEMA = {
    'zones.csv': ['zone_id','zone_name','ward_number','city','latitude','longitude','population_estimate','critical_facilities_count','pipe_age_years','dominant_pipe_material','average_pressure_bar','zone_status'],
    'meters.csv': ['meter_id','zone_id','location_id','customer_category','meter_type','installation_date','reading_unit','register_max_value','expected_reading_interval_hours','baseline_daily_litres','latitude','longitude','meter_status','last_service_date'],
    'meter_readings.csv': ['reading_id','meter_id','reading_timestamp','register_value_litres','reading_source','quality_flag','ingested_at','note'],
    'complaints.csv': ['complaint_id','zone_id','location_id','meter_id','reported_at','complaint_type','severity_reported','description','reporter_token','latitude','longitude','report_channel','complaint_status','access_issue_reported'],
    'crews.csv': ['crew_id','crew_name','home_zone_id','specialization','crew_size','shift_start','shift_end','availability_date','availability_status','vehicle_id','max_jobs_per_day','has_excavation_equipment','supervisor_ref'],
}

def load_csvs(folder):
    tables={}
    for filename, columns in SCHEMA.items():
        path=folder / filename
        if not path.is_file():
            raise FileNotFoundError(f'Missing {path}. Extract the five CSVs into this folder.')
        df=pd.read_csv(path, dtype='string', keep_default_na=False, encoding='utf-8')
        absent=[c for c in columns if c not in df.columns]
        if absent:
            raise ValueError(f'{filename} is missing columns: {absent}')
        # Keep explicit source-column contracts; ignore any unexpected extra columns.
        df=df[columns].copy()
        for c in columns:
            df[c]=df[c].str.strip().replace('', pd.NA)
        tables[filename.removesuffix('.csv')]=df
        print(f'EXTRACT  {filename}: {len(df):,} rows')
    return tables

