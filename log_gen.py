#!/usr/bin/env python3
"""
Raw log generator for S3 -> Lambda -> Glue pipeline
- Defaults to your raw bucket: sal-raw-log
- Emits NDJSON (.json or .json.gz) under prefix raw/
- Field names match ETL expectations: method, status, latency_ms, ip
"""

import argparse
import datetime as dt
import gzip
import io
import json
import random
import time
import uuid
from typing import Dict, List, Tuple, Optional

import boto3
from botocore.exceptions import ClientError
from faker import Faker

fake = Faker()

# ------------------------ Config ------------------------
LOG_LEVELS = {"INFO": 0.7, "WARN": 0.15, "ERROR": 0.1, "DEBUG": 0.05}
SERVICES = [
    "api-gateway",
    "authentication",
    "payment-service",
    "user-service",
    "notification-service",
]
ENDPOINTS = [
    "/api/users",
    "/api/products",
    "/api/orders",
    "/api/payments",
    "/api/login",
    "/api/logout",
    "/api/register",
    "/api/profile",
    "/api/settings",
]
HTTP_METHODS = ["GET", "POST", "PUT", "DELETE"]
STATUS_CODES = {200: 0.75, 201: 0.05, 400: 0.08, 401: 0.05, 403: 0.02, 404: 0.03, 500: 0.02}


# --------------------- Log generation -------------------
def generate_log_entry(ts: dt.datetime) -> Dict:
    level = random.choices(list(LOG_LEVELS.keys()), weights=list(LOG_LEVELS.values()))[0]
    service = random.choice(SERVICES)
    method = random.choice(HTTP_METHODS)
    endpoint = random.choice(ENDPOINTS)
    status = random.choices(list(STATUS_CODES.keys()), weights=list(STATUS_CODES.values()))[0]
    latency_ms = random.randint(5, 2000)
    request_id = str(uuid.uuid4())
    user_agent = fake.user_agent()
    ip = fake.ipv4()

    if level == "ERROR" and status >= 500:
        message = "Request failed with internal server error: database connection timeout"
    elif level == "ERROR" or status >= 400:
        message = f"Request failed with client error: {fake.sentence()}"
    elif level == "WARN":
        message = f"Performance warning: operation took {latency_ms}ms which exceeds threshold"
    else:
        message = f"Successfully processed {method} request to {endpoint}"

    # NOTE: keys aligned to ETL expectations
    return {
        "timestamp": ts.isoformat(),  # ETL can parse ISO8601
        "level": level,
        "service": service,
        "request_id": request_id,
        "method": method,
        "endpoint": endpoint,
        "status": status,
        "latency_ms": latency_ms,
        "ip": ip,
        "user_agent": user_agent,
        "message": message,
    }


# -------------------- S3 upload helpers -----------------
def _serialize_lines(logs: List[Dict], compress: bool) -> Tuple[bytes, Dict[str, str], str]:
    """Return (payload bytes, extra headers, extension)."""
    body = "\n".join(json.dumps(rec, separators=(",", ":")) for rec in logs).encode("utf-8")
    if compress:
        buf = io.BytesIO()
        with gzip.GzipFile(fileobj=buf, mode="wb") as gz:
            gz.write(body)
        return buf.getvalue(), {"ContentEncoding": "gzip"}, ".json.gz"
    return body, {}, ".json"


def put_batch_to_s3(
    s3,
    bucket: str,
    key_prefix: str,
    logs: List[Dict],
    compress: bool,
    sse: Optional[str] = None,
    kms_key_id: Optional[str] = None,
):
    payload, extra_headers, ext = _serialize_lines(logs, compress)
    put_kwargs = {
        "Bucket": bucket,
        "Key": f"{key_prefix}{ext}",
        "Body": payload,
        "ContentType": "application/x-ndjson",
        **extra_headers,
    }
    if sse:
        put_kwargs["ServerSideEncryption"] = sse
    if kms_key_id:
        put_kwargs["SSEKMSKeyId"] = kms_key_id
    s3.put_object(**put_kwargs)


# --------------- Streaming / rolling uploader ----------
def stream_logs_to_s3(
    bucket: str,
    prefix: str,
    start_date: dt.date,
    days: int,
    entries_per_day: int,
    batch_size: int,
    sleep_ms_between_batches: int,
    include_hour_partition: bool,
    compress: bool,
    region_name: Optional[str] = None,
    sse: Optional[str] = None,
    kms_key_id: Optional[str] = None,
):
    """
    Streams logs as rolling S3 objects partitioned by service/year/month/day[/hour].
    Each batch becomes one S3 object (.json or .json.gz).
    """
    s3 = boto3.client("s3", region_name=region_name) if region_name else boto3.client("s3")
    current_date = start_date

    for _ in range(days):
        year = f"{current_date.year:04d}"
        month = f"{current_date.month:02d}"
        day = f"{current_date.day:02d}"

        per_service = max(1, entries_per_day // max(1, len(SERVICES)))

        for service in SERVICES:
            buffer: List[Dict] = []
            objects_emitted = 0

            for _i in range(per_service):
                hour = random.randint(0, 23)
                minute = random.randint(0, 59)
                second = random.randint(0, 59)
                microsecond = random.randint(0, 999_999)
                ts = dt.datetime(current_date.year, current_date.month, current_date.day, hour, minute, second, microsecond)

                log = generate_log_entry(ts)
                log["service"] = service  # ensure path aligns with record
                buffer.append(log)

                if len(buffer) >= batch_size:
                    parts = [prefix.rstrip("/"), service, f"year={year}", f"month={month}", f"day={day}"]
                    if include_hour_partition:
                        parts.append(f"hour={hour:02d}")

                    file_stamp = dt.datetime.utcnow().strftime("%Y%m%dT%H%M%S%fZ")
                    base_key = "/".join(parts) + f"/logs_{service}_{year}{month}{day}_{file_stamp}_{objects_emitted:05d}"

                    try:
                        put_batch_to_s3(s3, bucket, base_key, buffer, compress, sse=sse, kms_key_id=kms_key_id)
                        print(f"Uploaded {len(buffer)} logs -> s3://{bucket}/{base_key}*")
                    except ClientError as e:
                        print(f"[ERROR] Failed to upload batch to s3://{bucket}/{base_key}*: {e}")
                    buffer.clear()
                    objects_emitted += 1

                    if sleep_ms_between_batches > 0:
                        time.sleep(sleep_ms_between_batches / 1000.0)

            # Flush any remaining logs for this service/day
            if buffer:
                parts = [prefix.rstrip("/"), service, f"year={year}", f"month={month}", f"day={day}"]
                if include_hour_partition:
                    last_hour = dt.datetime.fromisoformat(buffer[-1]["timestamp"]).hour
                    parts.append(f"hour={last_hour:02d}")

                file_stamp = dt.datetime.utcnow().strftime("%Y%m%dT%H%M%S%fZ")
                base_key = "/".join(parts) + f"/logs_{service}_{year}{month}{day}_{file_stamp}_{objects_emitted:05d}"
                try:
                    put_batch_to_s3(s3, bucket, base_key, buffer, compress, sse=sse, kms_key_id=kms_key_id)
                    print(f"Uploaded {len(buffer)} logs -> s3://{bucket}/{base_key}*")
                except ClientError as e:
                    print(f"[ERROR] Failed to upload final batch to s3://{bucket}/{base_key}*: {e}")

        current_date += dt.timedelta(days=1)


# ------------------------- CLI -------------------------
def parse_args():
    p = argparse.ArgumentParser(description="Stream dummy application logs to S3 as NDJSON")
    p.add_argument("--bucket", default="sal-raw-log", help="Target S3 bucket (default: sal-raw-log)")
    p.add_argument("--prefix", default="raw/", help="S3 key prefix/folder (default: raw/)")
    p.add_argument("--start-date", default=dt.date.today().strftime("%Y-%m-%d"), help="Start date YYYY-MM-DD (default: today)")
    p.add_argument("--days", type=int, default=1, help="Number of days to simulate (default: 1)")
    p.add_argument("--entries", type=int, default=10000, help="Approx number of log entries per day (default: 10000)")
    p.add_argument("--batch-size", type=int, default=2000, help="Records per S3 object (default: 2000)")
    p.add_argument("--sleep-ms-between-batches", type=int, default=0, help="Sleep time between uploads in ms (default: 0)")
    p.add_argument("--include-hour-partition", action="store_true", help="Add hour=HH to raw path")
    p.add_argument("--no-compress", action="store_true", help="Disable gzip (default is gzip ON)")
    p.add_argument("--region", default="us-east-2", help="AWS region (default: us-east-2)")
    p.add_argument("--sse", default="AES256", choices=["AES256", "aws:kms", None], help="SSE mode (default: AES256)")
    p.add_argument("--kms-key-id", default=None, help="KMS KeyId when --sse aws:kms is used")
    return p.parse_args()


def main():
    args = parse_args()
    start_date = dt.datetime.strptime(args.start_date, "%Y-%m-%d").date()
    stream_logs_to_s3(
        bucket=args.bucket,
        prefix=args.prefix,
        start_date=start_date,
        days=args.days,
        entries_per_day=args.entries,
        batch_size=args.batch_size,
        sleep_ms_between_batches=args.sleep_ms_between_batches,
        include_hour_partition=args.include_hour_partition,
        compress=not args.no_compress,
        region_name=args.region,
        sse=args.sse,
        kms_key_id=args.kms_key_id,
    )
    print("Log streaming complete.")


if __name__ == "__main__":
    main()
