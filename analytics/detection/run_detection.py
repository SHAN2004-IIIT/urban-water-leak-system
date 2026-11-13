"""Run with: python -m analytics.detection.run_detection (from project root)."""
import argparse
import json
from pathlib import Path
import pandas as pd
from .anomaly_detection import detect_anomalies
from .nighttime_flow import detect_nighttime_flow
from .complaint_correlation import correlate_complaints
from .leak_candidates import build_candidates

ROOT=Path(__file__).resolve().parents[2]


def run(processed_dir: Path, output_dir: Path):
    needed=["consumption_intervals.csv","missing_slots.csv",
            "complaints_validated.csv","complaint_location_summary.csv"]
    for name in needed:
        if not (processed_dir/name).is_file():
            raise FileNotFoundError(f"Missing ETL output: {processed_dir/name}. Run ETL first.")
    intervals=pd.read_csv(processed_dir/needed[0])
    gaps=pd.read_csv(processed_dir/needed[1])
    complaints=pd.read_csv(processed_dir/needed[2])
    summary=pd.read_csv(processed_dir/needed[3])
    timestamps=pd.to_datetime(intervals.end_timestamp,errors="coerce")
    if not timestamps.notna().any():
        raise ValueError("No valid reading timestamps available")
    reference_time=timestamps.max()
    anomalies=detect_anomalies(intervals,gaps)
    nighttime=detect_nighttime_flow(intervals)
    complaint_evidence=correlate_complaints(complaints,summary,reference_time)
    candidates,zones=build_candidates(anomalies,nighttime,complaint_evidence)
    output_dir.mkdir(parents=True,exist_ok=True)
    datasets={"meter_anomalies.csv":anomalies,"nighttime_flow.csv":nighttime,
              "complaint_evidence.csv":complaint_evidence,
              "leak_candidates.csv":candidates,"zone_risk_summary.csv":zones}
    for name,df in datasets.items():
        df.to_csv(output_dir/name,index=False)
        print(f"{name}: {len(df)} rows")
    result={"analysis_as_of":str(reference_time),"meter_count":int(len(anomalies)),
            "sustained_increase_meters":int(anomalies.anomaly_type.eq("SUSTAINED_INCREASE").sum()),
            "temporary_spike_meters":int(anomalies.anomaly_type.eq("TEMPORARY_SPIKE").sum()),
            "persistent_night_meters":int(nighttime.persistent_night_flow.sum()),
            "candidate_cases":int(len(candidates)),"zones_with_candidates":int(len(zones)),
            "note":"Suspected candidates only; no repair confirmation or calibrated probability."}
    (output_dir/"detection_summary.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
    print(json.dumps(result,indent=2))
    return datasets


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--input",type=Path,default=ROOT/"data"/"processed")
    parser.add_argument("--output",type=Path,default=ROOT/"data"/"detection")
    args=parser.parse_args()
    run(args.input,args.output)

if __name__=="__main__":
    main()
