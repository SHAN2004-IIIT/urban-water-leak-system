"""Transform cumulative readings into interval consumption and identify gaps."""
import pandas as pd
import numpy as np

def calculate_intervals(readings):
    """Compute hourly-equivalent usage. Suspicious/invalid observations never anchor intervals.

    Rollover only accepted when prior register >=80% max and current <=20% max,
    with physically plausible consumption under a demonstration safeguard of
    <= max(10x baseline, 2000 L/hour) and no unobserved intervals between values.
    This heuristic is not a universal rollover rule.
    """
    results=[]
    for meter_id, g in readings.groupby('meter_id', sort=False, dropna=True):
        if not isinstance(meter_id,str):
            continue
        meta=g.iloc[0]
        if pd.isna(meta['expected_reading_interval_hours']):
            continue
        expected=float(meta['expected_reading_interval_hours'])
        max_reg=float(meta['register_max_value'])
        base=float(meta['baseline_daily_litres'])
        anchor=None
        for row in g.itertuples(index=False):
            valid=row.etl_quality=='VALID'
            if not valid:
                # Do not bridge over explicit bad/missing readings.
                anchor=None
                continue
            if anchor is None:
                anchor=row
                continue
            elapsed=(row.reading_timestamp-anchor.reading_timestamp).total_seconds()/3600
            if elapsed <= 0:
                anchor=row
                continue
            prev=float(anchor.register_value_litres)
            curr=float(row.register_value_litres)
            delta=curr-prev
            status='OK'
            if elapsed > expected*1.1:
                status='GAP_INTERVAL'
                delta=np.nan
            elif delta < 0:
                proposed=(max_reg+1-prev)+curr
                plausible=(prev>=0.8*max_reg and curr<=0.2*max_reg and
                           proposed/elapsed <= max(10*(base/24),2000))
                if plausible:
                    delta=proposed
                    status='ROLLOVER'
                else:
                    delta=np.nan
                    status='UNEXPLAINED_DROP'
            elif delta/elapsed > max(10*(base/24),2000):
                delta=np.nan
                status='IMPLAUSIBLE_JUMP'
            results.append(dict(meter_id=meter_id,zone_id=row.zone_id,location_id=row.location_id,
                                previous_reading_id=anchor.reading_id,reading_id=row.reading_id,
                                start_timestamp=anchor.reading_timestamp,end_timestamp=row.reading_timestamp,
                                elapsed_hours=round(elapsed,3),previous_register_litres=prev,current_register_litres=curr,
                                consumption_litres=round(delta,3) if pd.notna(delta) else np.nan,
                                hourly_consumption_litres=round(delta/elapsed,3) if pd.notna(delta) else np.nan,
                                expected_hourly_litres=round(base/24,3),interval_status=status))
            anchor=row if status not in ('UNEXPLAINED_DROP','IMPLAUSIBLE_JUMP') else None
    return pd.DataFrame(results,columns=['meter_id','zone_id','location_id','previous_reading_id','reading_id',
        'start_timestamp','end_timestamp','elapsed_hours','previous_register_litres','current_register_litres',
        'consumption_litres','hourly_consumption_litres','expected_hourly_litres','interval_status'])

def detect_missing_slots(readings, meters):
    """Find wholly absent timestamps within each meter's observed window.
    Avoid inventing readings before the first or after the last observed timestamp.
    """
    output=[]
    for meter_id,g in readings.groupby('meter_id',dropna=True):
        g=g[g['reading_timestamp'].notna()]
        if g.empty or pd.isna(g.iloc[0]['expected_reading_interval_hours']):
            continue
        interval=int(g.iloc[0]['expected_reading_interval_hours'])
        expected=pd.date_range(g['reading_timestamp'].min(),g['reading_timestamp'].max(),freq=f'{interval}h')
        observed=pd.DatetimeIndex(g['reading_timestamp'].drop_duplicates())
        absent=expected.difference(observed)
        for ts in absent:
            output.append({'meter_id':meter_id,'zone_id':g.iloc[0]['zone_id'],
                           'expected_timestamp':ts,'missing_type':'ABSENT_ROW'})
    # Empty register is a separate, explicit missing observation.
    for row in readings.loc[readings['etl_quality']=='MISSING_VALUE'].itertuples(index=False):
        output.append({'meter_id':row.meter_id,'zone_id':row.zone_id,
                       'expected_timestamp':row.reading_timestamp,'missing_type':'BLANK_VALUE'})
    return pd.DataFrame(output,columns=['meter_id','zone_id','expected_timestamp','missing_type'])

