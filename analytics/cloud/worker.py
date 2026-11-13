"""SQS worker: download new meter readings, invoke existing pipeline, archive outputs.
Run from the repository root: python -m analytics.cloud.worker

Designed for ONE worker process with local files and a single FIFO message group.
The worker refuses to process a batch if the input schema is wrong.
"""
import argparse
import csv
import json
import logging
import os
from pathlib import Path
import subprocess
import sys
import tempfile

import boto3

log = logging.getLogger("waterleak.cloud")
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
ROOT = Path(__file__).resolve().parents[2]
REQUIRED = {"reading_id", "meter_id", "reading_timestamp", "register_value_litres"}
OUTPUT_FOLDERS = ("processed", "detection", "scoring")


def validate_csv(path: Path):
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        columns = set(reader.fieldnames or [])
        missing = REQUIRED - columns
        if missing:
            raise ValueError(f"Uploaded readings CSV missing columns: {sorted(missing)}")
        if next(reader, None) is None:
            raise ValueError("Uploaded readings CSV is empty")


def execute_pipeline(root: Path, python_exec: str = sys.executable):
    for module in ("analytics.etl.run_etl", "analytics.detection.run_detection",
                   "analytics.scoring.run_scoring"):
        log.info("Running %s", module)
        subprocess.run([python_exec, "-m", module], cwd=root, check=True)


def process_job(job: dict, root: Path, s3, upload_results: bool = True):
    if job.get("action") not in ("ingest", "refresh"):
        raise ValueError("Unrecognized queue action")
    bucket = job.get("bucket")
    key = job.get("key")
    if not bucket or key != "raw/meter_readings.csv":
        raise ValueError("Unsupported S3 object; expected raw/meter_readings.csv")

    raw_dir = root / "data" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    dest = raw_dir / "meter_readings.csv"
    if not all((raw_dir / n).exists() for n in
               ("zones.csv", "meters.csv", "complaints.csv", "crews.csv")):
        raise FileNotFoundError("Keep four reference CSVs in data/raw before starting worker")

    # Download to temp file first so a failed download never destroys existing data.
    with tempfile.NamedTemporaryFile(dir=raw_dir, suffix=".csv", delete=False) as tmp:
        temp_path = Path(tmp.name)
    try:
        params = {"Bucket": bucket, "Key": key}
        if job.get("version_id"):
            params["VersionId"] = job["version_id"]
        response = s3.get_object(**params)
        with temp_path.open("wb") as out:
            while chunk := response["Body"].read(1024 * 1024):
                out.write(chunk)
        validate_csv(temp_path)
        temp_path.replace(dest)
    finally:
        temp_path.unlink(missing_ok=True)

    execute_pipeline(root)
    if upload_results:
        for name in OUTPUT_FOLDERS:
            folder = root / "data" / name
            if folder.exists():
                for file in folder.glob("*"):
                    if file.is_file() and file.suffix in (".csv", ".json"):
                        s3.upload_file(str(file), bucket, f"results/{name}/{file.name}")
    # NOTE: PostgreSQL case import remains a separate explicit step in Part 8.


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="Check queue once and exit")
    parser.add_argument("--no-upload", action="store_true")
    args = parser.parse_args()
    queue_url = os.environ["WATER_LEAK_QUEUE_URL"]
    sqs, s3 = boto3.client("sqs"), boto3.client("s3")
    while True:
        response = sqs.receive_message(QueueUrl=queue_url, MaxNumberOfMessages=1,
                                       WaitTimeSeconds=10, VisibilityTimeout=900)
        for msg in response.get("Messages", []):
            try:
                job = json.loads(msg["Body"])
                process_job(job, ROOT, s3, upload_results=not args.no_upload)
            except Exception:
                log.exception("Job failed; retaining SQS message for retry/DLQ")
                continue
            sqs.delete_message(QueueUrl=queue_url, ReceiptHandle=msg["ReceiptHandle"])
            log.info("Completed job and acknowledged SQS message")
        if args.once:
            break

if __name__ == "__main__":
    main()
