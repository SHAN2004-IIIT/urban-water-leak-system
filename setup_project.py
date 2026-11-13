
from pathlib import Path

root = Path(__file__).resolve().parent

folders = [
    "simulator",
    "data/raw",
    "data/processed",
    "data/rejected",
    "analytics/etl",
    "analytics/tests",
]

files = [
    "analytics/etl/__init__.py",
    "analytics/etl/extract.py",
    "analytics/etl/validate.py",
    "analytics/etl/clean.py",
    "analytics/etl/transform.py",
    "analytics/etl/load.py",
    "analytics/etl/run_etl.py",
    "analytics/tests/test_etl.py",
    "analytics/requirements.txt",
    ".gitignore",
    "README.md",
]

for folder in folders:
    (root / folder).mkdir(parents=True, exist_ok=True)

for filename in files:
    (root / filename).touch(exist_ok=True)

print("Project folders created successfully!")
