"""Load the existing five source CSV files into a fresh PostgreSQL database.
Usage: python scripts/import_csv.py /path/to/sample_data
Requires: pip install 'psycopg[binary]>=3.2,<4'
Environment: DATABASE_URL (default: postgresql://wateruser:waterpass@localhost:5432/water_leak_db)
"""
import csv
import os
import sys
from pathlib import Path

import psycopg
from psycopg import sql

SCHEMAS = {
    "zones": "zone_id zone_name ward_number city latitude longitude population_estimate critical_facilities_count pipe_age_years dominant_pipe_material average_pressure_bar zone_status",
    "meters": "meter_id zone_id location_id customer_category meter_type installation_date reading_unit register_max_value expected_reading_interval_hours baseline_daily_litres latitude longitude meter_status last_service_date",
    "meter_readings": "reading_id meter_id reading_timestamp register_value_litres reading_source quality_flag ingested_at note",
    "complaints": "complaint_id zone_id location_id meter_id reported_at complaint_type severity_reported description reporter_token latitude longitude report_channel complaint_status access_issue_reported",
    "crews": "crew_id crew_name home_zone_id specialization crew_size shift_start shift_end availability_date availability_status vehicle_id max_jobs_per_day has_excavation_equipment supervisor_ref",
}
ORDER = ("zones", "meters", "meter_readings", "complaints", "crews")


def validate_files(folder):
    for table in ORDER:
        path = folder / f"{table}.csv"
        if not path.is_file():
            raise ValueError(f"Missing file: {path}")
        with path.open(encoding="utf-8-sig", newline="") as file:
            header = next(csv.reader(file), None)
        expected = SCHEMAS[table].split()
        if header != expected:
            raise ValueError(f"Wrong columns in {path.name}.\nExpected: {expected}\nFound: {header}")


def main():
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python scripts/import_csv.py /path/to/sample_data")
    folder = Path(sys.argv[1]).expanduser().resolve()
    validate_files(folder)
    db_url = os.getenv("DATABASE_URL", "postgresql://wateruser:waterpass@localhost:5432/water_leak_db")
    with psycopg.connect(db_url) as connection:
        # All five files import together or none do, avoiding partial loads.
        with connection.cursor() as cursor:
            for table in ORDER:
                cursor.execute(sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(table)))
                if cursor.fetchone()[0]:
                    raise RuntimeError(f"Table {table} is not empty. Use a NEW database, rather than importing twice.")
            for table in ORDER:
                columns = SCHEMAS[table].split()
                command = sql.SQL("COPY {} ({}) FROM STDIN WITH (FORMAT csv, HEADER true, NULL '')").format(
                    sql.Identifier(table), sql.SQL(", ").join(map(sql.Identifier, columns))
                )
                with (folder / f"{table}.csv").open("rb") as src:
                    with cursor.copy(command) as copy:
                        while chunk := src.read(1024 * 1024):
                            copy.write(chunk)
                cursor.execute(sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(table)))
                print(f"{table:18} loaded: {cursor.fetchone()[0]:,} rows")
        connection.commit()
    print("Success. Five CSVs imported. System-generated tables are still empty.")


if __name__ == "__main__":
    main()
