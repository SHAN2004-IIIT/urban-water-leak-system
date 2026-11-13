"""Import Part 4 scored_cases.csv into PostgreSQL as UPSERTed cases plus score history.
Run from project root: python scripts/load_scoring.py --input data/scoring/scored_cases.csv
Requires: pip install 'psycopg[binary]>=3.2,<4'  (or pip install -r scripts/requirements.txt)
"""
import argparse, csv, json, os
from pathlib import Path
import psycopg

def import_cases(path: Path, url: str):
    if not path.exists(): raise FileNotFoundError(path)
    count=0
    with psycopg.connect(url) as conn:
        with conn.cursor() as cur, path.open(newline='', encoding='utf-8-sig') as f:
            for row in csv.DictReader(f):
                source=(row.get('case_id') or '').strip()
                if not source: raise ValueError('Missing case_id in scored_cases.csv')
                try: score=float(row['risk_score'])
                except (ValueError,KeyError) as e: raise ValueError(f'Invalid score in {source}') from e
                if not 0<=score<=100:raise ValueError(f'Out-of-range score {source}')
                components={k:float(row.get(k) or 0) for k in ('consumption_points','night_points','complaint_points','persistence_points')}
                if abs(sum(components.values())-score)>0.01:raise ValueError(f'Component mismatch for {source}')
                cur.execute('''INSERT INTO leak_cases
                (source_case_id,zone_id,location_id,meter_id,case_status,access_status,risk_band,score_explanation)
                VALUES (%s,%s,%s,%s,'SUSPECTED',%s,%s,%s)
                ON CONFLICT (source_case_id) DO UPDATE SET
                    risk_band=EXCLUDED.risk_band, score_explanation=EXCLUDED.score_explanation,
                    updated_at=CURRENT_TIMESTAMP
                RETURNING case_id''',(
                    source,row['zone_id'],row.get('location_id') or None,row.get('meter_id') or None,
                    'UNKNOWN',row.get('risk_band','LOW'),row.get('score_explanation','')))
                case_id=cur.fetchone()[0]
                # No duplicated score-history record for identical latest score/version.
                cur.execute('''SELECT 1 FROM risk_scores WHERE case_id=%s AND score=%s
                     AND model_version=%s AND score_components=%s::jsonb LIMIT 1''',
                     (case_id,score,row.get('score_version','rules-v1'),json.dumps(components)))
                if not cur.fetchone():
                    cur.execute('''INSERT INTO risk_scores
                    (case_id,score,score_components,model_name,model_version,data_quality_notes)
                    VALUES (%s,%s,%s::jsonb,'explainable-rules',%s,%s)''',
                    (case_id,score,json.dumps(components),row.get('score_version','rules-v1'),
                    f"Source candidate: {source}; case is suspected, not confirmed"))
                count+=1
    print(f'Upserted {count} candidates into PostgreSQL')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--input',type=Path,default=Path('data/scoring/scored_cases.csv'))
    p.add_argument('--url',default=os.getenv('DATABASE_URL','postgresql://wateruser:waterpass@localhost:5432/water_leak_db'))
    a=p.parse_args();import_cases(a.input,a.url)
