import os, json, urllib.parse, time, hashlib
import boto3
from botocore.exceptions import ClientError

glue = boto3.client("glue")
dynamodb = boto3.resource("dynamodb")

GLUE_JOB_NAME = os.environ["GLUE_JOB_NAME"]
OUTPUT_PREFIX = os.environ["OUTPUT_PREFIX"]
USE_DDB       = os.environ.get("USE_DDB","true").lower() == "true"
DDB_TABLE     = os.environ.get("DDB_TABLE")

table = dynamodb.Table(DDB_TABLE) if (USE_DDB and DDB_TABLE) else None

def _dedupe(bucket, key, etag):
    if not table:
        return True
    item_key = f"{bucket}/{key}"
    try:
        resp = table.get_item(Key={"object_key": item_key})
        if "Item" in resp:
            return False
        ttl = int(time.time()) + 7*24*3600
        table.put_item(Item={"object_key": item_key, "etag": etag, "ttl": ttl})
        return True
    except ClientError:
        return True

def handler(event, context):
    for r in event.get("Records", []):
        s3i = r["s3"]
        bucket = s3i["bucket"]["name"]
        key = urllib.parse.unquote_plus(s3i["object"]["key"])
        etag = s3i["object"].get("eTag","")

        if not key.startswith("raw/") or not (key.endswith(".json") or key.endswith(".gz")):
            continue
        if not _dedupe(bucket, key, etag):
            print(f"SKIP duplicate {bucket}/{key}")
            continue

        run_id = hashlib.md5(f"{bucket}/{key}/{time.time()}".encode()).hexdigest()[:12]
        args = {
            "--INPUT_PATH": f"s3://{bucket}/{key}",
            "--OUTPUT_PREFIX": OUTPUT_PREFIX.rstrip("/") + "/",
            "--RUN_ID": run_id
        }
        try:
            resp = glue.start_job_run(JobName=GLUE_JOB_NAME, Arguments=args)
            print(f"Started Glue run {resp['JobRunId']} for {bucket}/{key}")
        except ClientError as e:
            print(f"Glue start failed for {bucket}/{key}: {e}")
            if table:
                table.delete_item(Key={"object_key": f"{bucket}/{key}"})
            raise
    return {"status": "ok"}
