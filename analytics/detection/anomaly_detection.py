"""Meter-level temporal anomaly screening (not leak confirmation)."""
import numpy as np
import pandas as pd

ACCEPTED = {"OK", "ROLLOVER"}


def detect_anomalies(intervals: pd.DataFrame, missing_slots: pd.DataFrame) -> pd.DataFrame:
    """Compare recent complete days with each meter's earlier daily history.

    Baselines are estimated from an earlier part of each meter's own available
    history, never from other customers' absolute consumption. A persistent
    increase means >=3 sufficiently covered recent days above 1.5x baseline.
    Thresholds are illustrative and must be validated with operational labels.
    """
    needed = {"meter_id", "zone_id", "location_id", "end_timestamp",
              "interval_status", "hourly_consumption_litres", "elapsed_hours"}
    if missing := needed - set(intervals.columns):
        raise ValueError(f"consumption_intervals.csv missing columns: {sorted(missing)}")
    df = intervals.copy()
    df["end_timestamp"] = pd.to_datetime(df["end_timestamp"], errors="coerce")
    df["hourly_consumption_litres"] = pd.to_numeric(df["hourly_consumption_litres"], errors="coerce")
    df["elapsed_hours"] = pd.to_numeric(df["elapsed_hours"], errors="coerce")
    df = df[df.interval_status.isin(ACCEPTED) & df.end_timestamp.notna()
            & df.hourly_consumption_litres.ge(0) & df.elapsed_hours.gt(0)]
    if df.empty:
        return pd.DataFrame(columns=["meter_id", "zone_id", "location_id", "baseline_lph",
            "recent_lph", "recent_to_baseline_ratio", "elevated_recent_days", "recent_days",
            "peak_daily_ratio", "anomaly_type", "anomaly_detected", "data_confidence",
            "missing_observations"])

    df["date"] = df.end_timestamp.dt.normalize()
    # Intervals are expected hourly. A daily value is used only when >=18h
    # of valid observations; no imputation of missing observations.
    # Correct total = sum over each interval's consumption, not sum of rates.
    df["litres"] = df["hourly_consumption_litres"] * df["elapsed_hours"]
    daily = df.groupby(["meter_id", "date"], as_index=False).agg(
        total_litres=("litres", "sum"), valid_hours=("elapsed_hours", "sum"))
    daily["mean_lph"] = daily.total_litres / daily.valid_hours
    daily = daily[daily.valid_hours.ge(18) & daily.valid_hours.le(24.2)]

    id_columns = df.sort_values("end_timestamp").drop_duplicates("meter_id", keep="last")
    meta = id_columns.set_index("meter_id")[["zone_id", "location_id"]]
    missing_counts = (missing_slots.groupby("meter_id").size().to_dict()
                      if not missing_slots.empty and "meter_id" in missing_slots else {})
    records = []
    for meter_id, g in daily.groupby("meter_id", sort=True):
        g = g.sort_values("date")
        # Avoid reference contamination from suspected later events: baseline
        # is the first 60% of complete observed days, at least 7 days.
        n_base = max(7, int(len(g) * .6))
        baseline = g.iloc[:n_base].mean_lph.median() if len(g) >= 10 else np.nan
        recent = g.tail(7)
        recent_lph = float(recent.mean_lph.median()) if len(recent) else np.nan
        ratio = (recent_lph / baseline if pd.notna(baseline) and baseline > 0 else np.nan)
        daily_ratio = recent.mean_lph / baseline if pd.notna(baseline) and baseline > 0 else pd.Series(dtype=float)
        elevated = int(daily_ratio.ge(1.5).sum())
        peak = float(daily_ratio.max()) if len(daily_ratio) else np.nan
        enough = len(g) >= 10 and len(recent) >= 5
        anomaly_type = ("INSUFFICIENT_DATA" if not enough else
                        "SUSTAINED_INCREASE" if elevated >= 3 and ratio >= 1.4 else
                        "TEMPORARY_SPIKE" if peak >= 2.0 else "NORMAL")
        records.append({"meter_id": meter_id, "zone_id": meta.at[meter_id, "zone_id"],
            "location_id": meta.at[meter_id, "location_id"],
            "baseline_lph": round(float(baseline), 3) if pd.notna(baseline) else np.nan,
            "recent_lph": round(recent_lph, 3) if pd.notna(recent_lph) else np.nan,
            "recent_to_baseline_ratio": round(float(ratio), 3) if pd.notna(ratio) else np.nan,
            "elevated_recent_days": elevated, "recent_days": len(recent),
            "peak_daily_ratio": round(peak, 3) if pd.notna(peak) else np.nan,
            "anomaly_type": anomaly_type,
            "anomaly_detected": anomaly_type in ("SUSTAINED_INCREASE", "TEMPORARY_SPIKE"),
            "data_confidence": "SUFFICIENT" if enough else "LOW",
            "missing_observations": int(missing_counts.get(meter_id, 0))})
    return pd.DataFrame(records)
