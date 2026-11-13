"""Review existing detected candidates and produce an auditable risk ledger.

The detection module already computes the four component scores; recomputing
from the original evidence fields here prevents treating a prior score as truth.
"""
import numpy as np
import pandas as pd
from .config import SCORE_VERSION, WEIGHTS

REQUIRED = {"case_id", "zone_id", "location_id", "meter_id", "anomaly_type",
            "persistent_night_flow", "recent_independent_complaints", "elevated_recent_days"}

def score_cases(candidates: pd.DataFrame) -> pd.DataFrame:
    missing = REQUIRED - set(candidates.columns)
    if missing:
        raise ValueError(f"Candidate input missing: {sorted(missing)}")
    if candidates.case_id.duplicated().any():
        raise ValueError("Duplicate case_id in candidates")
    d = candidates.copy()
    d["recent_independent_complaints"] = pd.to_numeric(d.recent_independent_complaints, errors="coerce").fillna(0)
    d["elevated_recent_days"] = pd.to_numeric(d.elevated_recent_days, errors="coerce").fillna(0)
    night = d.persistent_night_flow.astype(str).str.lower().isin(["true", "1", "yes"])
    sustained = d.anomaly_type.eq("SUSTAINED_INCREASE")
    n = d.recent_independent_complaints
    d["consumption_points"] = np.where(sustained, WEIGHTS["consumption"], 0)
    d["night_points"] = np.where(night, WEIGHTS["nighttime"], 0)
    d["complaint_points"] = np.select([n.ge(5), n.ge(2), n.eq(1)], [25, 15, 5], default=0)
    days = d.elevated_recent_days
    d["persistence_points"] = np.where(sustained & days.ge(5), 15,
                                        np.where(sustained & days.ge(3), 10, 0))
    parts = ["consumption_points", "night_points", "complaint_points", "persistence_points"]
    d["risk_score"] = d[parts].sum(axis=1).astype(int)
    d["risk_band"] = np.select([d.risk_score.ge(70), d.risk_score.ge(35)], ["HIGH", "MEDIUM"], default="LOW")
    d["score_version"] = SCORE_VERSION
    d["score_explanation"] = d.apply(lambda r: (
        f"sustained anomaly {r.consumption_points}/35; persistent night flow {r.night_points}/25; "
        f"independent complaints {int(r.recent_independent_complaints)} -> {r.complaint_points}/25; "
        f"elevated days {int(r.elevated_recent_days)} -> {r.persistence_points}/15"), axis=1)
    d["case_status"] = "SUSPECTED_NOT_CONFIRMED"
    return d.sort_values(["risk_score", "case_id"], ascending=[False, True]).reset_index(drop=True)

def zone_scores(scored: pd.DataFrame) -> pd.DataFrame:
    if scored.empty:
        return pd.DataFrame(columns=["zone_id", "candidate_count", "highest_risk_score", "high_risk_cases", "zone_rank"])
    z = scored.groupby("zone_id", as_index=False).agg(
        candidate_count=("case_id", "nunique"),
        highest_risk_score=("risk_score", "max"),
        high_risk_cases=("risk_band", lambda x: int(x.eq("HIGH").sum())))
    z = z.sort_values(["highest_risk_score", "high_risk_cases", "candidate_count", "zone_id"],
                      ascending=[False, False, False, True]).reset_index(drop=True)
    z["zone_rank"] = np.arange(1, len(z) + 1)
    return z
