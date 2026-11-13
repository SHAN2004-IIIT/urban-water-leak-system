"""Create explicitly simulated access decisions for top two ranked cases.
Run AFTER detection; review the CSV before using it as a planning input.
"""
from pathlib import Path
import pandas as pd
from .risk_scoring import score_cases

ROOT = Path(__file__).resolve().parents[2]

def main():
    src = ROOT / "data" / "detection" / "leak_candidates.csv"
    out = ROOT / "data" / "scoring" / "access_overrides.csv"
    s = score_cases(pd.read_csv(src))
    if len(s) < 2:
        raise ValueError("Need at least two candidate cases for demo")
    out.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([
        {"case_id": s.iloc[0].case_id, "access_status": "BLOCKED", "access_note": "DEMO ONLY: simulated road closure; supervisor to verify"},
        {"case_id": s.iloc[1].case_id, "access_status": "OPEN", "access_note": "DEMO ONLY: simulated confirmed access; supervisor to verify"},
    ]).to_csv(out, index=False)
    print("Created", out)
    print("Example only; do not treat simulated access as verified field data")

if __name__ == "__main__":
    main()
