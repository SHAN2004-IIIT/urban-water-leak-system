"""Compare the 00:00–05:59 flow with each meter's own historic nights."""
import numpy as np
import pandas as pd
from .anomaly_detection import ACCEPTED


def detect_nighttime_flow(intervals: pd.DataFrame) -> pd.DataFrame:
    required = {"meter_id", "end_timestamp", "interval_status", "elapsed_hours",
                "hourly_consumption_litres"}
    if missing := required - set(intervals.columns):
        raise ValueError(f"consumption_intervals.csv missing columns: {sorted(missing)}")
    df = intervals.copy()
    df["end_timestamp"] = pd.to_datetime(df.end_timestamp, errors="coerce")
    df["hourly_consumption_litres"] = pd.to_numeric(df.hourly_consumption_litres, errors="coerce")
    df["elapsed_hours"] = pd.to_numeric(df.elapsed_hours, errors="coerce")
    # Intervals ENDING 01:00 through 06:00 approximate midnight–06:00 coverage
    # with hourly source readings; excludes irregular/multi-hour intervals.
    df = df[df.interval_status.isin(ACCEPTED) & df.end_timestamp.notna()
            & df.hourly_consumption_litres.ge(0)
            & df.elapsed_hours.between(.9, 1.1)
            & df.end_timestamp.dt.hour.between(1, 6)]
    cols = ["meter_id", "night_baseline_lph", "recent_night_lph", "night_ratio",
            "elevated_recent_nights", "recent_nights", "persistent_night_flow", "night_data_quality"]
    if df.empty:
        return pd.DataFrame(columns=cols)
    df["night_date"] = df.end_timestamp.dt.normalize()
    nights = df.groupby(["meter_id", "night_date"], as_index=False).agg(
        mean_night_lph=("hourly_consumption_litres", "mean"),
        observed_hours=("hourly_consumption_litres", "size"))
    nights = nights[nights.observed_hours >= 5]
    records=[]
    for meter_id, g in nights.groupby("meter_id"):
        g=g.sort_values("night_date")
        sufficient=len(g)>=10
        baseline = g.iloc[:max(7,int(len(g)*.6))].mean_night_lph.median() if sufficient else np.nan
        recent=g.tail(7)
        recent_mean=float(recent.mean_night_lph.median()) if len(recent) else np.nan
        # A meaningful baseline is necessary to compute an interpretable ratio.
        ratio=(recent_mean/baseline if pd.notna(baseline) and baseline>=1 else np.nan)
        elevated=(int((recent.mean_night_lph >= max(1.6*baseline, baseline+8)).sum())
                  if pd.notna(baseline) else 0)
        persistent=bool(sufficient and len(recent)>=5 and elevated>=3
                        and pd.notna(ratio) and ratio>=1.5)
        records.append({"meter_id":meter_id,
            "night_baseline_lph":round(float(baseline),3) if pd.notna(baseline) else np.nan,
            "recent_night_lph":round(recent_mean,3) if pd.notna(recent_mean) else np.nan,
            "night_ratio":round(float(ratio),3) if pd.notna(ratio) else np.nan,
            "elevated_recent_nights":elevated,"recent_nights":int(len(recent)),
            "persistent_night_flow":persistent,
            "night_data_quality":"SUFFICIENT" if sufficient and len(recent)>=5 else "LOW"})
    return pd.DataFrame(records,columns=cols)
