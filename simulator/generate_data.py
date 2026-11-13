"""Synthetic urban water utility input dataset generator (standard library only).

Run: python generate_data.py
Optional: python generate_data.py --seed 20261109 --days 30 --meters 120 --zones 16 --complaints 320 --crews 6

Generates the FIVE input files. Leak cases, work orders, crew assignments, and
repair outcomes belong in the operational database, not the raw input files.
All timestamps are local Chennai time (Asia/Kolkata), with no timezone suffix.
Readings are cumulative litre-register readings, not hourly consumption.
"""
import argparse
import csv
import random
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

BASE_DATE = datetime(2026, 10, 10, 0, 0, 0)
AREA_NAMES = [
    'Anna Nagar', 'T Nagar', 'Adyar', 'Velachery', 'Mylapore', 'Porur',
    'Guindy', 'Perambur', 'Nungambakkam', 'Tambaram', 'Kodambakkam',
    'Ambattur', 'Kilpauk', 'Royapettah', 'Besant Nagar', 'Pallavaram',
    'Alandur', 'Egmore', 'Sholinganallur', 'Saidapet',
]


def stamp(dt):
    return dt.strftime('%Y-%m-%d %H:%M:%S')


def write_csv(out, file, rows):
    path = out / file
    with path.open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]), extrasaction='raise')
        writer.writeheader()
        writer.writerows(rows)
    print(f'{file:22} {len(rows):>7,} records | {len(rows[0])} columns')


def build(out, seed, days, n_meters, n_zones, n_complaints, n_crews):
    if not (6 <= n_zones <= 100 and n_meters >= 30 and n_complaints >= 35 and 2 <= n_crews <= 50):
        raise ValueError('Use zones 6–100, meters >=30, complaints >=35, crews 2–50')
    rng = random.Random(seed)
    out.mkdir(parents=True, exist_ok=True)

    # Geographical reference / zone attributes.
    zones = []
    for i in range(1, n_zones+1):
        lat = round(13.065 + rng.uniform(-0.095, 0.075), 6)
        lon = round(80.225 + rng.uniform(-0.07, 0.075), 6)
        zones.append(dict(zone_id=f'Z{i:03}', zone_name=AREA_NAMES[(i-1) % len(AREA_NAMES)] + (f' Sector {(i-1)//len(AREA_NAMES)+1}' if i > len(AREA_NAMES) else ''),
                          ward_number=10+i, city='Chennai', latitude=lat, longitude=lon,
                          population_estimate=rng.randint(5000, 26000), critical_facilities_count=rng.randint(0, 5),
                          pipe_age_years=rng.randint(2, 55), dominant_pipe_material=rng.choice(['DI','PVC','HDPE','GI']),
                          average_pressure_bar=round(rng.uniform(1.0,4.5),2), zone_status='Active'))

    # Meters distributed across zones, with first three dedicated scenario locations.
    meters=[]
    for i in range(1, n_meters+1):
        zi = 0 if i == 1 else 1 if i in (2,3) else (i-1) % n_zones
        zone = zones[zi]
        cat = rng.choices(['Residential','Commercial','Institutional'],weights=[75,20,5])[0]
        baseline = rng.randint(250,1000) if cat == 'Residential' else rng.randint(1200, 4200)
        if i in (1,2,3): baseline = [600,700,550][i-1]
        meter_type = rng.choice(['Digital','Mechanical'])
        meters.append(dict(meter_id=f'M{i:04}', zone_id=zone['zone_id'],location_id=f'LOC{i:04}',
                           customer_category=cat, meter_type=meter_type,
                           installation_date=(datetime(2016,1,1)+timedelta(days=rng.randint(0,3200))).date().isoformat(),
                           reading_unit='L', register_max_value=99999,expected_reading_interval_hours=1,
                           baseline_daily_litres=baseline,
                           latitude=round(zone['latitude']+rng.uniform(-0.003,0.003),6),
                           longitude=round(zone['longitude']+rng.uniform(-0.003,0.003),6),meter_status='Active',
                           last_service_date=(datetime(2024,1,1)+timedelta(days=rng.randint(0,950))).date().isoformat()))

    # 24 readings per meter per day, with recognizable diurnal use and true counter rollover.
    # M0001: high-risk sustained leak, restricted access. M0002: another plausible leak.
    # M0003: legitimate temporary high demand, a potential false alarm.
    # M0004: intentionally near counter max on day one. M0005: missing observations.
    # M0006: deliberately implausible raw reading.
    hour_weights=[0.35]*5+[0.60,1.25,1.70,1.40,1.10,1.0,0.9,0.95,0.95,1.0,1.1,1.25,1.55,1.6,1.25,1.0,0.8,0.65,0.5]
    norm=sum(hour_weights)
    readings=[]
    for ix,m in enumerate(meters):
        register=99978 if ix==3 else rng.randint(500,85000)
        for day in range(days):
            day_factor=rng.uniform(0.85,1.16)
            for hour in range(24):
                ts=BASE_DATE+timedelta(days=day,hours=hour)
                base=m['baseline_daily_litres']*hour_weights[hour]/norm*day_factor
                usage=max(1,round(base*rng.uniform(0.80,1.20)))
                note=''
                if ix==0 and day>=days-8:
                    usage+=42   # continuous leakage including at night
                elif ix==1 and day>=days-5:
                    usage+=18
                elif ix==2 and days-7<=day<=days-5 and 7<=hour<=21:
                    usage+=105  # a known simulated temporary-demand event, NOT a leak
                if ix==3 and day==0 and hour==0:
                    usage+=60  # forces known rollover right away
                before=register
                register=(register+usage)%(int(m['register_max_value'])+1)
                quality='OK'
                val=register
                if register<before:
                    note='Cumulative register wrapped; investigate rollover'
                # Missing reading: some explicitly blank, others fully absent (telemetry gap).
                if (ix==4 and day in (9,10) and hour in (2,3,4)) or rng.random()<0.002:
                    if rng.random()<0.35:
                        continue
                    val=''
                    quality='MISSING'
                    note='No telemetry received'
                # Erroneous read never changes the simulated physical counter.
                elif (ix==5 and day==11 and hour==12) or rng.random()<0.0005:
                    val=register+45000
                    quality='SUSPECT'
                    note='Possible faulty or mistyped raw register value'
                readings.append(dict(reading_id=f'R{len(readings)+1:07}',meter_id=m['meter_id'],
                                     reading_timestamp=stamp(ts),register_value_litres=val,
                                     reading_source=rng.choices(['AMI','Manual'], weights=[92,8])[0],
                                     quality_flag=quality,ingested_at=stamp(ts+timedelta(minutes=rng.randint(1,40))),note=note))

    # Numerous reports, including multiple independent residents and exact duplicates.
    complaints=[]
    kinds=['Visible leakage','Low pressure','Water pooling','Pipe noise','Continuous flow']
    for i in range(n_complaints):
        if i<45: mi=0
        elif i<80: mi=1
        elif i<108: mi=2
        else: mi=rng.randrange(n_meters)
        m=meters[mi]
        ct=rng.choice(kinds)
        reported=BASE_DATE+timedelta(days=rng.randint(max(0,days-10),days-1),hours=rng.randint(0,23),minutes=rng.randint(0,59))
        reporter=f'RES{rng.randint(1,500):05}'
        # Truly duplicated rows retain the same reporter, timestamp and issue.
        if i in (1,2,46,47,81,82):
            prev=complaints[-1]
            reporter,ct,reported=prev['reporter_token'],prev['complaint_type'],datetime.strptime(prev['reported_at'],'%Y-%m-%d %H:%M:%S')
        complaints.append(dict(complaint_id=f'C{i+1:05}',zone_id=m['zone_id'],location_id=m['location_id'],
                               meter_id=m['meter_id'],reported_at=stamp(reported),complaint_type=ct,
                               severity_reported=rng.choices(['Low','Medium','High'],[20,50,30])[0],
                               description=f'Resident reports {ct.lower()} near service location.',
                               reporter_token=reporter,latitude=m['latitude'],longitude=m['longitude'],
                               report_channel=rng.choice(['Phone','Web','Mobile app']),
                               complaint_status=rng.choice(['New','Under review']),
                               access_issue_reported='Road closed' if mi==0 else 'None'))

    # Snapshot of crew availability; detailed calendar and reassignments go in DB.
    crews=[]
    for i in range(1,n_crews+1):
        crews.append(dict(crew_id=f'CR{i:03}',crew_name=f'Repair Crew {i:02}',home_zone_id=zones[(i-1)%n_zones]['zone_id'],
                          specialization=rng.choice(['Leak inspection','Pipe repair','Valve repair']),crew_size=rng.randint(2,5),
                          shift_start='08:00',shift_end='16:00',availability_date='2026-11-10',
                          availability_status='Available' if i<=2 else 'Assigned' if i==3 else 'OffDuty',
                          vehicle_id=f'VEH{i:03}',max_jobs_per_day=rng.choice([1,2]),
                          has_excavation_equipment=rng.choice(['Yes','No']),supervisor_ref=f'SUP{((i-1)%3)+1:02}'))

    # Integrity and intentionally injected signal validation.
    meter_lookup={m['meter_id']:m for m in meters}
    zone_ids={z['zone_id'] for z in zones}
    assert all(m['zone_id'] in zone_ids for m in meters)
    assert all(r['meter_id'] in meter_lookup for r in readings)
    assert all(c['meter_id'] in meter_lookup and c['zone_id']==meter_lookup[c['meter_id']]['zone_id']
               and c['location_id']==meter_lookup[c['meter_id']]['location_id'] for c in complaints)
    assert all(c['home_zone_id'] in zone_ids for c in crews)
    assert any(r['quality_flag']=='MISSING' for r in readings)
    assert any(r['quality_flag']=='SUSPECT' for r in readings)
    for file,rows in [('zones.csv',zones),('meters.csv',meters),('meter_readings.csv',readings),
                      ('complaints.csv',complaints),('crews.csv',crews)]:
        write_csv(out,file,rows)
    print('Quality flags:',dict(Counter(r['quality_flag'] for r in readings)))
    print('Validation passed: references, deliberate missing/suspect readings, and 5 CSV outputs.')


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--seed',type=int,default=20261109)
    p.add_argument('--days',type=int,default=30)
    p.add_argument('--meters',type=int,default=120)
    p.add_argument('--zones',type=int,default=16)
    p.add_argument('--complaints',type=int,default=320)
    p.add_argument('--crews',type=int,default=6)
    a=p.parse_args()
    if a.days<15: p.error('--days must be at least 15 to include all test scenarios')
    build(Path(__file__).resolve().parent/'sample_data',a.seed,a.days,a.meters,a.zones,a.complaints,a.crews)
