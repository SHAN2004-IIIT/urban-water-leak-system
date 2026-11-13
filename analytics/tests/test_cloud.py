import tempfile
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

from analytics.cloud.worker import validate_csv, process_job
from deployment.aws.lambda_handler import make_jobs


class TestCloudStage(unittest.TestCase):
    def test_s3_event_enqueues_exact_raw_readings_file(self):
        event = {"source":"aws.s3", "detail-type":"Object Created",
                 "detail":{"bucket":{"name":"test-bucket"},
                           "object":{"key":"raw/meter_readings.csv", "version-id":"v1"}}}
        jobs = make_jobs(event, "test-bucket")
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["version_id"], "v1")
        event["detail"]["object"]["key"] = "results/meter_readings.csv"
        self.assertEqual(make_jobs(event, "test-bucket"), [])

    def test_schedule_refresh(self):
        e = {"source":"aws.events", "detail":{"action":"refresh"}}
        self.assertEqual(make_jobs(e, "test-bucket")[0]["action"], "refresh")

    def test_csv_schema(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "reading.csv"
            p.write_text("reading_id,meter_id,reading_timestamp,register_value_litres\n1,M1,2026-01-01,10\n")
            validate_csv(p)
            p.write_text("meter_id,value\nM1,5\n")
            with self.assertRaises(ValueError):
                validate_csv(p)

    def test_pipeline_invoked_after_download(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            raw = root / "data" / "raw"
            raw.mkdir(parents=True)
            for n in ("zones.csv", "meters.csv", "complaints.csv", "crews.csv"):
                (raw / n).write_text("dummy\n")
            s3 = MagicMock()
            s3.get_object.return_value = {"Body": MagicMock()}
            s3.get_object.return_value["Body"].read.side_effect = [
                b"reading_id,meter_id,reading_timestamp,register_value_litres\n1,M1,2026-01-01,10\n", b""]
            with patch("analytics.cloud.worker.execute_pipeline") as pipeline:
                process_job({"action":"ingest", "bucket":"test-bucket",
                             "key":"raw/meter_readings.csv"}, root, s3, False)
                pipeline.assert_called_once_with(root)
                self.assertTrue((raw / "meter_readings.csv").exists())

if __name__ == "__main__":
    unittest.main()
