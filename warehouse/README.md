# Part 9 — Snowflake + Power BI

## Folder placement
Extract at `D:\DevOps Project` root. All new files live under `warehouse/` and do not replace Parts 1–8.

## Run order
1. Install: `python -m pip install -r warehouse/requirements.txt`
2. Export from PostgreSQL (running in Docker): `python -m warehouse.export_postgres`
3. Record the new folder name from output: `warehouse/exports/<snapshot_id>`
4. Upload **only this snapshot**: `python -m warehouse.upload_s3 --folder warehouse/exports/<snapshot_id> --bucket YOUR_BUCKET`
5. In Snowflake Snowsight worksheet: run `sql/01_database.sql`.
6. Create an AWS IAM role that permits `s3:ListBucket` on your bucket with warehouse/exports/ restriction and `s3:GetObject` on `warehouse/exports/*`. Configure Snowflake role-trust policy. In Snowflake run `sql/02_storage_integration_template.sql` after replacing placeholders. Run `DESC INTEGRATION` and update trust relationship using the IAM user ARN and external ID returned by Snowflake. Run `LIST @WATER_LEAK_EXPORT_STAGE`.
7. Load: `sql/03_load.sql` then create views using `sql/04_reporting_views.sql`, and verify with `sql/05_verify.sql`.
8. Power BI: follow `powerbi/README.md`.

## Notes
- Use `warehouse/exports/` S3 prefix, **not** `raw/`, so your Part 8 S3 trigger does not run again.
- Snapshot exports are consistent (PostgreSQL repeatable-read transaction). Each export has a unique snapshot ID; re-export for updated outcomes.
- Snowflake COPY history prevents duplicate loading of the same file (do not use FORCE=TRUE).
- The reporting views pick the most recent snapshot and the latest risk/outcome per case; ensure a snapshot uploads fully before loading. Do not mix partial snapshots.
- `V_CASE_EVALUATION` separates `NOT_YET_VERIFIED` from `FALSE_ALARM`.
- No personally identifying resident or user/password data are exported.
- Store all timestamps consistently in the long-term system. Previous raw PostgreSQL data uses naive local timestamps; for demo, interpret them consistently and document your local timezone.
- Snowflake, S3, Power BI and AWS usage can incur charges. Suspend warehouse between tests.
