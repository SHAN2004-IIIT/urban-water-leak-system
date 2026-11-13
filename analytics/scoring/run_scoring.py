"""Run from repository root: python -m analytics.scoring.run_scoring"""
import argparse
import json
from pathlib import Path
import pandas as pd
from .risk_scoring import score_cases, zone_scores
from .scheduling import recommend_dispatch

ROOT = Path(__file__).resolve().parents[2]

def run(detection_dir: Path, processed_dir: Path, output_dir: Path, restrictions_file: Path | None = None):
    cases_path = detection_dir / "leak_candidates.csv"
    crews_path = processed_dir / "crews_clean.csv"
    for p in (cases_path, crews_path):
        if not p.exists():
            raise FileNotFoundError(f"Missing {p}. Run ETL and detection first.")
    cases = pd.read_csv(cases_path)
    crews = pd.read_csv(crews_path)
    restrictions = pd.read_csv(restrictions_file) if restrictions_file and restrictions_file.exists() else None
    scored = score_cases(cases)
    zones = zone_scores(scored)
    dispatch, available_crews = recommend_dispatch(scored, crews, restrictions)
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, df in {"scored_cases.csv": scored, "zone_priority.csv": zones,
                     "dispatch_recommendations.csv": dispatch}.items():
        df.to_csv(output_dir / name, index=False)
        print(f"{name}: {len(df)} records")
    summary = {"candidates": len(scored), "zones": len(zones), "available_crews": len(available_crews),
               "dispatch_proposals": int(dispatch.dispatch_decision.eq("PROPOSE_ASSIGN").sum()),
               "deferred_blocked": int(dispatch.dispatch_decision.eq("DEFER_BLOCKED").sum()),
               "access_verification_required": int(dispatch.dispatch_decision.eq("VERIFY_ACCESS").sum()),
               "warning": "Planning suggestions only. No actual crew bookings. Score is not a probability."}
    (output_dir / "scoring_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return dispatch

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--detection", type=Path, default=ROOT / "data" / "detection")
    p.add_argument("--processed", type=Path, default=ROOT / "data" / "processed")
    p.add_argument("--output", type=Path, default=ROOT / "data" / "scoring")
    p.add_argument("--restrictions", type=Path, default=ROOT / "data" / "scoring" / "access_overrides.csv")
    args = p.parse_args()
    run(args.detection, args.processed, args.output, args.restrictions)

if __name__ == "__main__":
    main()
