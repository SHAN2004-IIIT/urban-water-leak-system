"""AWS Lambda: translate S3/EventBridge notifications into FIFO SQS jobs.

Lambda never runs the heavy Pandas ETL; the long-lived worker handles that.
"""
import hashlib
import json
import logging
import os
from urllib.parse import unquote_plus

import boto3

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)


def make_jobs(event: dict, bucket_name: str) -> list[dict]:
    # EventBridge delivers S3 Object Created events; the scheduled rule uses a custom detail.
    if event.get("source") == "aws.events" or event.get("detail", {}).get("action") == "refresh":
        return [{"action": "refresh", "bucket": bucket_name, "key": "raw/meter_readings.csv"}]

    if event.get("source") != "aws.s3" or event.get("detail-type") != "Object Created":
        return []

    detail = event.get("detail", {})
    bucket = detail.get("bucket", {}).get("name")
    key = detail.get("object", {}).get("key", "")
    if bucket != bucket_name or key != "raw/meter_readings.csv":
        return []

    obj = detail.get("object", {})
    return [{"action": "ingest", "bucket": bucket,
             "key": key, "version_id": obj.get("version-id"),
             "etag": obj.get("etag")}]


def lambda_handler(event, context):
    bucket = os.environ["RAW_BUCKET"]
    queue_url = os.environ["QUEUE_URL"]
    jobs = make_jobs(event, bucket)
    sqs = boto3.client("sqs")
    for job in jobs:
        job_id = hashlib.sha256(json.dumps(job, sort_keys=True).encode()).hexdigest()
        # FIFO de-duplication window is only five minutes; worker must also be idempotent.
        sqs.send_message(QueueUrl=queue_url, MessageBody=json.dumps(job),
                         MessageGroupId="water-leak-ingestion",
                         MessageDeduplicationId=job_id)
        log.info("Enqueued %s for %s", job["action"], job["key"])
    return {"queued": len(jobs)}
