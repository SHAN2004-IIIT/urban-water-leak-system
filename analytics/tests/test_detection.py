import pandas as pd
from analytics.detection.anomaly_detection import detect_anomalies
from analytics.detection.complaint_correlation import correlate_complaints
from analytics.detection.leak_candidates import build_candidates


def test_spike_alone_does_not_create_case():
    anomalies=pd.DataFrame([{"meter_id":"M1","zone_id":"Z1","location_id":"L1",
        "anomaly_type":"TEMPORARY_SPIKE","elevated_recent_days":0,
        "recent_to_baseline_ratio":1.0,"data_confidence":"SUFFICIENT"}])
    night=pd.DataFrame([{"meter_id":"M1","persistent_night_flow":False,"night_ratio":1.0}])
    complaints=pd.DataFrame(columns=["zone_id","location_id","recent_independent_complaints",
                                     "recent_access_reports"])
    cases,zones=build_candidates(anomalies,night,complaints)
    assert cases.empty and zones.empty


def test_sustained_plus_complaints_is_candidate():
    anomalies=pd.DataFrame([{"meter_id":"M1","zone_id":"Z1","location_id":"L1",
        "anomaly_type":"SUSTAINED_INCREASE","elevated_recent_days":6,
        "recent_to_baseline_ratio":2.1,"data_confidence":"SUFFICIENT"}])
    night=pd.DataFrame([{"meter_id":"M1","persistent_night_flow":True,"night_ratio":2.0}])
    complaints=pd.DataFrame([{"zone_id":"Z1","location_id":"L1",
        "recent_independent_complaints":8,"recent_access_reports":2}])
    cases,zones=build_candidates(anomalies,night,complaints)
    assert len(cases)==1 and cases.iloc[0].evidence_priority_score==100
    assert cases.iloc[0].access_status=="REPORTED_RESTRICTION"
    assert cases.iloc[0].case_status=="SUSPECTED_NOT_CONFIRMED"


def test_repeat_reports_do_not_inflate_evidence():
    c=pd.DataFrame([
        {"zone_id":"Z1","location_id":"L1","reported_at":"2026-11-08 10:00:00",
         "complaint_id":"C1","reporter_token":"R1","etl_quality":"VALID",
         "is_repeat_report":False,"access_issue_reported":"None"},
        {"zone_id":"Z1","location_id":"L1","reported_at":"2026-11-08 11:00:00",
         "complaint_id":"C2","reporter_token":"R1","etl_quality":"VALID",
         "is_repeat_report":True,"access_issue_reported":"None"},
        {"zone_id":"Z1","location_id":"L1","reported_at":"2026-11-08 12:00:00",
         "complaint_id":"C3","reporter_token":"R2","etl_quality":"VALID",
         "is_repeat_report":False,"access_issue_reported":"Road closed"},
    ])
    summary=pd.DataFrame([{"zone_id":"Z1","location_id":"L1","independent_complaint_count":2}])
    out=correlate_complaints(c,summary,pd.Timestamp("2026-11-09"))
    assert int(out.iloc[0].recent_independent_complaints)==2
    assert int(out.iloc[0].recent_access_reports)==1


def test_sustained_temporal_increase_detected():
    rows=[]
    start=pd.Timestamp("2026-10-01")
    for day in range(22):
        for hour in range(1,25):
            ts=start+pd.Timedelta(days=day,hours=hour)
            rows.append({"meter_id":"M1","zone_id":"Z1","location_id":"L1",
                "end_timestamp":ts,"interval_status":"OK","hourly_consumption_litres":
                30.0 if day<15 else 80.0,"elapsed_hours":1.0})
    d=pd.DataFrame(rows)
    a=detect_anomalies(d,pd.DataFrame(columns=["meter_id"]))
    assert a.iloc[0].anomaly_type=="SUSTAINED_INCREASE"
