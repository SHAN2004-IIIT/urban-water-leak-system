"""Count recent unique reporting people at each location; don't double-count repeats."""
import pandas as pd


def correlate_complaints(complaints: pd.DataFrame,
                         location_summary: pd.DataFrame,
                         reference_time: pd.Timestamp,
                         lookback_days: int = 14) -> pd.DataFrame:
    needed={"zone_id","location_id","reported_at","complaint_id","reporter_token",
            "etl_quality","is_repeat_report","access_issue_reported"}
    if missing := needed - set(complaints.columns):
        raise ValueError(f"complaints_validated.csv missing columns: {sorted(missing)}")
    c=complaints.copy()
    c["reported_at"]=pd.to_datetime(c.reported_at,errors="coerce")
    c["is_repeat_report"]=(c.is_repeat_report.astype(str).str.lower()
                            .isin(["true","1","yes"]))
    c=c[(c.etl_quality=="VALID") & (~c.is_repeat_report)
        & c.reported_at.between(reference_time-pd.Timedelta(days=lookback_days),
                                 reference_time)]
    c["access_restriction_reported"]=(c.access_issue_reported.fillna("None")
        .astype(str).str.strip().str.lower().isin(
            ["road closed", "inaccessible", "access denied", "blocked", "restricted access"]))
    # For known reporters, count each reporter once per location in window.
    # Anonymous reports cannot be reliably linked to distinct persons.
    known=c[c.reporter_token.notna()].drop_duplicates(
        ["zone_id","location_id","reporter_token"])
    anonymous=c[c.reporter_token.isna()].copy()
    grouped=pd.concat([known,anonymous],ignore_index=True)
    if grouped.empty:
        return pd.DataFrame(columns=["zone_id","location_id","recent_independent_complaints",
            "distinct_reporters","recent_access_reports","latest_complaint_at",
            "historical_independent_complaints"])
    res=grouped.groupby(["zone_id","location_id"],dropna=False).agg(
        recent_independent_complaints=("complaint_id","count"),
        distinct_reporters=("reporter_token","nunique"),
        recent_access_reports=("access_restriction_reported","sum"),
        latest_complaint_at=("reported_at","max")
    ).reset_index()
    # The ETL summary contains historical totals, useful for audit, but only
    # recent unique reporters affect current evidence.
    if {"zone_id","location_id","independent_complaint_count"}.issubset(location_summary.columns):
        summary=location_summary[["zone_id","location_id","independent_complaint_count"]].rename(
            columns={"independent_complaint_count":"historical_independent_complaints"})
        res=res.merge(summary,on=["zone_id","location_id"],how="left",validate="one_to_one")
    else:
        res["historical_independent_complaints"]=pd.NA
    return res
