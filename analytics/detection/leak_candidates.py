"""Create explainable, provisional leak candidates; never assert a confirmed leak."""
import pandas as pd
import numpy as np


def build_candidates(anomalies: pd.DataFrame,
                     nighttime: pd.DataFrame,
                     complaints: pd.DataFrame) -> tuple[pd.DataFrame,pd.DataFrame]:
    base=anomalies.merge(nighttime,on="meter_id",how="left",validate="one_to_one")
    # Location IDs come from meter metadata. Multiple meters can share a
    # location, so case evidence is consolidated to one candidate/location.
    base=base.merge(complaints,on=["zone_id","location_id"],how="left",validate="many_to_one")
    for col in ["recent_independent_complaints","recent_access_reports"]:
        base[col]=pd.to_numeric(base.get(col,0),errors="coerce").fillna(0).astype(int)
    base["persistent_night_flow"]=base["persistent_night_flow"].fillna(False).astype(bool)
    base["sustained_increase"]=base.anomaly_type.eq("SUSTAINED_INCREASE")
    base["temporary_spike"]=base.anomaly_type.eq("TEMPORARY_SPIKE")
    # Candidate if sustained meter evidence, persistent nighttime evidence,
    # or >=2 independent recent complaint reports. A temporary spike alone
    # is NOT enough to generate a candidate.
    base["candidate_trigger"]=(base.sustained_increase | base.persistent_night_flow
                                | base.recent_independent_complaints.ge(2))
    cases=base[base.candidate_trigger].copy()
    # Transparent provisional evidence score, NOT a leak probability.
    # All components, max values and weights are exposed in the saved table.
    cases["consumption_points"]=np.where(cases.sustained_increase,35,0)
    cases["night_points"]=np.where(cases.persistent_night_flow,25,0)
    cases["complaint_points"]=np.select([
        cases.recent_independent_complaints.ge(5),
        cases.recent_independent_complaints.ge(2),
        cases.recent_independent_complaints.eq(1)], [25,15,5], default=0)
    cases["persistence_points"]=np.where(cases.sustained_increase & cases.elevated_recent_days.fillna(0).ge(5),15,
                                     np.where(cases.sustained_increase & cases.elevated_recent_days.fillna(0).ge(3),10,0))
    cases["evidence_priority_score"]=(cases.consumption_points+cases.night_points+
        cases.complaint_points+cases.persistence_points).astype(int)
    cases["access_status"]=np.where(cases.recent_access_reports.gt(0),
                                    "REPORTED_RESTRICTION", "UNVERIFIED")
    cases["case_status"]="SUSPECTED_NOT_CONFIRMED"
    cases["review_priority"]=np.select([
        cases.evidence_priority_score.ge(70),cases.evidence_priority_score.ge(35)],
        ["HIGH","MEDIUM"],default="LOW")
    cases["case_id"]=(cases.zone_id.astype(str)+"-"+cases.location_id.astype(str))
    # In this simulator, each location is a uniquely identified service point.
    # If multiple meters share it, retain strongest meter evidence, and do
    # not double count the location-level complaint evidence.
    cases=cases.sort_values(["evidence_priority_score","meter_id"],ascending=[False,True])
    cases=cases.drop_duplicates(["zone_id","location_id"],keep="first")
    keep=["case_id","zone_id","location_id","meter_id","case_status",
          "anomaly_type","recent_to_baseline_ratio","elevated_recent_days",
          "persistent_night_flow","night_ratio","recent_independent_complaints",
          "consumption_points","night_points","complaint_points","persistence_points",
          "evidence_priority_score","review_priority","access_status","data_confidence"]
    cases=cases[keep].sort_values(["evidence_priority_score","case_id"],ascending=[False,True]).reset_index(drop=True)
    if cases.empty:
        zones=pd.DataFrame(columns=["zone_id","candidate_count","max_evidence_score","zone_rank"])
    else:
        zones=cases.groupby("zone_id",as_index=False).agg(candidate_count=("case_id","count"),
            max_evidence_score=("evidence_priority_score","max"))
        zones=zones.sort_values(["max_evidence_score","candidate_count","zone_id"],
                                ascending=[False,False,True]).reset_index(drop=True)
        zones["zone_rank"]=np.arange(1,len(zones)+1)
    return cases,zones
