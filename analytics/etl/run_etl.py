"""Entry point: run from the repository root using python -m analytics.etl.run_etl."""
import argparse
import json
from pathlib import Path

from .extract import load_csvs
from .validate import validate_master
from .clean import clean_readings, clean_complaints
from .transform import calculate_intervals, detect_missing_slots
from .load import export

ROOT = Path(__file__).resolve().parents[2]


def run(input_folder: Path, output_folder: Path):
    if input_folder.resolve() == output_folder.resolve():
        raise ValueError('Input and output folders cannot be the same')
    output_folder.mkdir(parents=True, exist_ok=True)
    tables = load_csvs(input_folder)
    zones, meters, crews = validate_master(tables)
    readings = clean_readings(tables['meter_readings'], meters)
    intervals = calculate_intervals(readings)
    gaps = detect_missing_slots(readings, meters)
    complaints, complaint_summary = clean_complaints(tables['complaints'], meters, zones)

    outputs = {
        'zones_clean.csv': zones,
        'meters_clean.csv': meters,
        'crews_clean.csv': crews,
        'readings_validated.csv': readings,
        'consumption_intervals.csv': intervals,
        'missing_slots.csv': gaps,
        'complaints_validated.csv': complaints,
        'complaint_location_summary.csv': complaint_summary,
    }
    for filename, df in outputs.items():
        export(df, output_folder, filename)
    rejected = readings.loc[~readings['etl_quality'].eq('VALID')]
    rejected_dir = ROOT / 'data' / 'rejected'
    rejected_dir.mkdir(parents=True, exist_ok=True)
    rejected.to_csv(rejected_dir / 'readings_flagged.csv', index=False)
    complaints.loc[~complaints['etl_quality'].eq('VALID')].to_csv(
        rejected_dir / 'complaints_rejected.csv', index=False
    )
    metrics = {
        'source_rows': {name: int(len(df)) for name, df in tables.items()},
        'reading_quality_counts': {str(k): int(v) for k, v in readings['etl_quality'].value_counts().items()},
        'interval_status_counts': {str(k): int(v) for k, v in intervals['interval_status'].value_counts().items()},
        'missing_slot_counts': {str(k): int(v) for k, v in gaps['missing_type'].value_counts().items()},
        'repeated_complaints': int(complaints['is_repeat_report'].sum()),
        'distinct_complaint_locations': int(len(complaint_summary)),
    }
    (output_folder / 'etl_summary.json').write_text(json.dumps(metrics, indent=2))
    print('ETL finished:', json.dumps(metrics, indent=2))
    return metrics


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', type=Path, default=ROOT / 'data' / 'raw')
    parser.add_argument('--output', type=Path, default=ROOT / 'data' / 'processed')
    args = parser.parse_args()
    run(args.input, args.output)


if __name__ == '__main__':
    main()
