"""Export transaction-safe reporting snapshots from Part 5/7 PostgreSQL to JSONL.
Run from project root: python -m warehouse.export_postgres --output warehouse/exports
"""
import argparse
import json
import os
from pathlib import Path
from datetime import datetime, timezone, date
from decimal import Decimal
from uuid import uuid4

# Column allowlists intentionally exclude usernames, passwords and resident identifiers.
QUERIES = {
    'zones': "SELECT zone_id, zone_name, city, ward_number, population_estimate, critical_facilities_count, pipe_age_years FROM zones",
    'leak_cases': "SELECT case_id, source_case_id, zone_id, meter_id, location_id, case_status, access_status, risk_band, detected_at, updated_at FROM leak_cases",
    'risk_scores': "SELECT risk_score_id, case_id, score, score_components, model_name, model_version, calculated_at FROM risk_scores",
    'work_orders': "SELECT work_order_id, case_id, work_type, status, estimated_duration_minutes, created_at, updated_at FROM work_orders",
    'crew_assignments': "SELECT assignment_id, work_order_id, crew_id, scheduled_start, scheduled_end, assignment_status, assigned_at FROM crew_assignments",
    'repair_outcomes': "SELECT outcome_id, work_order_id, outcome_type, leak_type, estimated_water_loss_litres, inspected_at, recorded_at FROM repair_outcomes",
    'work_order_events': "SELECT event_id, work_order_id, event_type, from_status, to_status, recorded_at FROM work_order_events",
    'meter_readings': "SELECT reading_id, meter_id, reading_timestamp, register_value_litres, quality_flag FROM meter_readings",
}

def json_default(v):
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    if isinstance(v, Decimal):
        return float(v)
    raise TypeError(f'Unsupported type: {type(v).__name__}')

def export_snapshot(conn, output: Path, snapshot_id: str):
    output.mkdir(parents=True, exist_ok=True)
    counts = {}
    now = datetime.now(timezone.utc).isoformat()
    # Repeatable read makes the eight tables consistent at a point in time.
    from psycopg.rows import dict_row
    with conn.transaction():
        conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        for table, sql in QUERIES.items():
            target = output / f'{table}.jsonl'
            n = 0
            with conn.cursor(name=f'export_{table}', row_factory=dict_row) as cur:
                cur.execute(sql)
                with target.open('w', encoding='utf-8', newline='\n') as f:
                    for rows in iter(lambda: cur.fetchmany(1000), []):
                        for data in rows:
                            event = {'dataset': table, 'snapshot_id': snapshot_id,
                                     'exported_at': now, 'data': data}
                            f.write(json.dumps(event, default=json_default, ensure_ascii=False)+'\n')
                            n += 1
            counts[table] = n
    (output / 'manifest.json').write_text(json.dumps({'snapshot_id': snapshot_id, 'exported_at': now, 'row_counts':counts}, indent=2),encoding='utf-8')
    return counts

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--output',default='warehouse/exports')
    ap.add_argument('--snapshot-id',default=None)
    args=ap.parse_args()
    snapshot=args.snapshot_id or datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'_'+uuid4().hex[:8]
    folder=Path(args.output)/snapshot
    dsn=os.getenv('DATABASE_URL', 'postgresql://wateruser:waterpass@127.0.0.1:5432/water_leak_db')
    import psycopg
    with psycopg.connect(dsn) as conn:
        counts=export_snapshot(conn,folder,snapshot)
    print(json.dumps({'folder':str(folder),'counts':counts},indent=2))

if __name__=='__main__': main()
