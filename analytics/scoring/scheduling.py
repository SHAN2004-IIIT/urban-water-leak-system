"""Non-destructive, explainable dispatch suggestions; not actual assignments.

Access and crew skills require supervisor verification. Only the Spring Boot
transactional scheduler should commit work orders/crew assignments.
"""
import pandas as pd
from .config import ALLOWED_ACCESS


def recommend_dispatch(scored: pd.DataFrame, crews: pd.DataFrame,
                       restrictions: pd.DataFrame | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    s = scored.copy()
    if "case_id" not in s or "risk_score" not in s:
        raise ValueError("Scored cases require case_id and risk_score")
    if not {"crew_id", "availability_status"}.issubset(crews.columns):
        raise ValueError("Crews require crew_id and availability_status")
    if restrictions is None:
        restrictions = pd.DataFrame(columns=["case_id", "access_status", "access_note"])
    else:
        restrictions = restrictions.copy()
        need = {"case_id", "access_status", "access_note"}
        if not need.issubset(restrictions.columns):
            raise ValueError(f"Restrictions missing: {sorted(need - set(restrictions.columns))}")
        if restrictions.case_id.duplicated().any():
            raise ValueError("Repeated case_id in restrictions")
        if not restrictions.access_status.isin(ALLOWED_ACCESS).all():
            raise ValueError(f"access_status must be one of {ALLOWED_ACCESS}")
    s = s.merge(restrictions, on="case_id", how="left", validate="one_to_one")
    # A reported restriction is NOT verification of a block; manual review required.
    reported = s.get("access_status_x", pd.Series(index=s.index, dtype="object"))
    detected = s.get("access_status_y", pd.Series(index=s.index, dtype="object"))
    # Explicit restriction column from CSV shadows detection access_status.
    if "access_status_y" in s.columns:
        explicit = s["access_status_y"]
        original = s["access_status_x"]
        s = s.drop(columns=["access_status_x", "access_status_y"])
    else:
        explicit = s.get("access_status", pd.Series(index=s.index, dtype="object"))
        original = pd.Series(index=s.index, dtype="object")
    s["access_status"] = explicit.fillna("UNKNOWN")
    reported_restriction = original.eq("REPORTED_RESTRICTION")
    s.loc[reported_restriction & s.access_status.eq("UNKNOWN"), "access_status"] = "REPORTED_NEEDS_CHECK"
    s["access_note"] = s["access_note"].fillna("")
    available = crews[crews.availability_status.astype(str).str.lower().eq("available")].copy()
    available = available.sort_values("crew_id").reset_index(drop=True)
    # Order by raw leak risk, not accessibility; avoid hiding dangerous inaccessible cases.
    s = s.sort_values(["risk_score", "case_id"], ascending=[False, True]).reset_index(drop=True)
    s["risk_rank"] = range(1, len(s) + 1)
    s["dispatch_decision"] = "WAITING_CAPACITY"
    s["suggested_crew_id"] = ""
    s["dispatch_reason"] = "No eligible crew remains in this snapshot"
    index = 0
    for i, row in s.iterrows():
        access = row.access_status
        if access == "BLOCKED":
            decision, reason = "DEFER_BLOCKED", "Verified blocked access; retain risk rank and escalate access resolution"
        elif access in ("UNKNOWN", "REPORTED_NEEDS_CHECK"):
            decision, reason = "VERIFY_ACCESS", "Access not verified; supervisor must confirm before dispatch"
        elif index >= len(available):
            decision, reason = "WAITING_CAPACITY", "No available crew in this planning snapshot"
        else:
            decision, reason = "PROPOSE_ASSIGN", "Accessible case selected by descending risk; verify crew skills and travel"
            s.at[i, "suggested_crew_id"] = available.loc[index, "crew_id"]
            index += 1
        s.at[i, "dispatch_decision"] = decision
        s.at[i, "dispatch_reason"] = reason
    # Include every candidate, and a crew snapshot, without changing crew state.
    return s, available
