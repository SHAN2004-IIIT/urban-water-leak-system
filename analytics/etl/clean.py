"""Validate and label readings and complaints."""
import pandas as pd

def clean_readings(raw, meters):
    r=raw.copy()
    r['reading_timestamp']=pd.to_datetime(r['reading_timestamp'], errors='coerce')
    r['ingested_at']=pd.to_datetime(r['ingested_at'], errors='coerce')
    r['register_value_litres']=pd.to_numeric(r['register_value_litres'], errors='coerce')
    r['source_quality_flag']=r['quality_flag']
    r=r.merge(meters[['meter_id','zone_id','location_id','register_max_value',
                      'expected_reading_interval_hours','baseline_daily_litres']],on='meter_id',how='left',validate='many_to_one')
    # Preserve records but quarantine malformed IDs/timestamps/duplicate timestamps.
    r['etl_quality']='VALID'
    r.loc[r['meter_id'].isna() | r['zone_id'].isna() | r['reading_id'].isna() | r['reading_timestamp'].isna(), 'etl_quality']='REJECTED'
    bad_range=(r['register_value_litres'].notna() &
               ((r['register_value_litres'] < 0) | (r['register_value_litres'] > r['register_max_value'])))
    r.loc[(r['etl_quality']=='VALID') & bad_range,'etl_quality']='INVALID_REGISTER'
    missing=r['register_value_litres'].isna()
    r.loc[(r['etl_quality']=='VALID') & missing,'etl_quality']='MISSING_VALUE'
    # Source SUSPECT flags should be reviewed rather than used to generate usage.
    r.loc[(r['etl_quality']=='VALID') & r['source_quality_flag'].eq('SUSPECT'),'etl_quality']='SOURCE_SUSPECT'
    duplicate=(r['reading_id'].duplicated(keep='first') |
               r.duplicated(['meter_id','reading_timestamp'], keep='first'))
    r.loc[duplicate,'etl_quality']='DUPLICATE'
    r=r.sort_values(['meter_id','reading_timestamp','reading_id'],na_position='last').reset_index(drop=True)
    return r

def clean_complaints(raw, meters, zones):
    c=raw.copy()
    c['reported_at']=pd.to_datetime(c['reported_at'],errors='coerce')
    c['etl_quality']='VALID'
    bad=(c['complaint_id'].isna()|c['zone_id'].isna()|c['reported_at'].isna()|
         ~c['zone_id'].isin(zones['zone_id']))
    c.loc[bad,'etl_quality']='REJECTED'
    # Validate optional meter references and zone consistency without rejecting a location-only complaint.
    linked=c.merge(meters[['meter_id','zone_id','location_id']].rename(columns={
        'zone_id':'meter_zone_id','location_id':'meter_location_id'}),on='meter_id',how='left',validate='many_to_one')
    mismatch=linked['meter_id'].notna() & (linked['meter_zone_id'].isna() |
              (linked['zone_id']!=linked['meter_zone_id']) |
              (linked['location_id'].notna() & (linked['location_id']!=linked['meter_location_id'])))
    c.loc[mismatch.fillna(False),'etl_quality']='REJECTED'
    c.loc[c['complaint_id'].duplicated(keep='first'),'etl_quality']='DUPLICATE_ID'
    # A repeat from same reporter, same location and complaint type in a 24-hour
    # window is treated as a repeated report. Different reporters count separately.
    c=c.sort_values(['zone_id','location_id','reporter_token','complaint_type','reported_at'],na_position='last').reset_index(drop=True)
    c['is_repeat_report']=False
    good=c['etl_quality'].eq('VALID') & c['reporter_token'].notna() & c['location_id'].notna()
    grouped=c[good].groupby(['zone_id','location_id','reporter_token','complaint_type'],dropna=False)
    for _,g in grouped:
        last_kept=None
        for idx,ts in zip(g.index,g['reported_at']):
            if last_kept is not None and (ts-last_kept).total_seconds()<24*3600:
                c.at[idx,'is_repeat_report']=True
            else:
                last_kept=ts
    # Preserve every complaint; repeat flag is analysis metadata only.
    valid=c[(c['etl_quality']=='VALID') & (~c['is_repeat_report'])].copy()
    summary=valid.groupby(['zone_id','location_id'],dropna=False).agg(
        independent_complaint_count=('complaint_id','count'),
        distinct_reporter_count=('reporter_token',lambda x:x.dropna().nunique()),
        first_reported_at=('reported_at','min'),last_reported_at=('reported_at','max'),
        access_issue_reports=('access_issue_reported',lambda x:int(x.fillna('None').str.lower().ne('none').sum()))
    ).reset_index()
    return c,summary

