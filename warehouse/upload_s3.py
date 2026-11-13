"""Upload one full snapshot under warehouse/exports/ (NOT the raw/ trigger prefix)."""
import argparse
import json
from pathlib import Path
import boto3

def upload_snapshot(folder:Path,bucket:str):
    manifest=json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
    sid=manifest['snapshot_id']
    client=boto3.client('s3')
    for path in sorted(folder.glob('*.jsonl')):
        key=f'warehouse/exports/{sid}/{path.name}'
        client.upload_file(str(path),bucket,key,ExtraArgs={'ContentType':'application/x-ndjson'})
        print('Uploaded',f's3://{bucket}/{key}')
    # manifest is intentionally not loaded into raw records
    key=f'warehouse/manifests/{sid}.json'
    client.upload_file(str(folder/'manifest.json'),bucket,key,ExtraArgs={'ContentType':'application/json'})
    print('Uploaded manifest',f's3://{bucket}/{key}')

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--folder',required=True); ap.add_argument('--bucket',required=True)
    a=ap.parse_args(); upload_snapshot(Path(a.folder),a.bucket)
if __name__=='__main__': main()
