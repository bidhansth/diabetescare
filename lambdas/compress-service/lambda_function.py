"""diabetescare-compress-pdf Lambda.

Triggered via SQS from an S3 ``ObjectCreated`` event notification on the
resource bucket (suffix filter ``pdf``). Compresses each PDF in place with
pikepdf and writes it back to the SAME key with
``Metadata.compressed=true`` so a re-notification is a no-op. This breaks the
``PutObject`` -> re-notification -> reprocess loop without needing a
dead-letter queue.

S3 -> SQS delivers the notification JSON as the message body:
    {"Records": [{"s3": {"bucket": {"name": ...}, "object": {"key": ...}}}]}
"""
import os
import io
import json
import logging

import boto3
import pikepdf

logger = logging.getLogger()
logger.setLevel(logging.INFO)

REGION = os.environ.get("AWS_REGION", "us-east-1")
BUCKET = os.environ["S3_BUCKET"]
s3 = boto3.client("s3", region_name=REGION)


def _compress(raw: bytes) -> bytes:
    out = io.BytesIO()
    pdf = pikepdf.open(io.BytesIO(raw))
    pdf.save(
        out,
        linearize=True,
        object_stream_mode=pikepdf.ObjectStreamMode.generate,
        recompress_flate=True,
    )
    pdf.close()
    return out.getvalue()


def _already_compressed(head: dict) -> bool:
    return head.get("Metadata", {}).get("compressed") == "true"


def _process_record(s3rec: dict) -> dict:
    bucket = s3rec["s3"]["bucket"]["name"]
    key = s3rec["s3"]["object"]["key"]

    head = s3.head_object(Bucket=bucket, Key=key)
    if _already_compressed(head):
        return {"bucket": bucket, "key": key, "status": "skipped"}

    obj = s3.get_object(Bucket=bucket, Key=key)
    raw = obj["Body"].read()
    content_type = obj.get("ContentType") or "application/pdf"
    content_disposition = obj.get("ContentDisposition") or ""

    if raw[:4] != b"%PDF":
        # Defensive: suffix filter should already keep this to PDFs.
        # Stamp the guard so the key is not reprocessed on the next notification.
        s3.copy_object(
            CopySource={"Bucket": bucket, "Key": key},
            Bucket=bucket,
            Key=key,
            Metadata={"compressed": "true"},
            MetadataDirective="REPLACE",
            ContentType=content_type,
            ContentDisposition=content_disposition,
        )
        return {"bucket": bucket, "key": key, "status": "skipped_not_pdf"}

    compressed = _compress(raw)
    best = compressed if len(compressed) < len(raw) else raw
    replaced = len(compressed) < len(raw)
    logger.info(
        "compress %s/%s orig=%d comp=%d -> %s",
        bucket, key, len(raw), len(compressed),
        "replaced" if replaced else "no_gain_kept_original",
    )
    s3.put_object(
        Bucket=bucket,
        Key=key,
        Body=best,
        ContentType=content_type,
        ContentDisposition=content_disposition,
        Metadata={"compressed": "true"},
    )
    return {
        "bucket": bucket,
        "key": key,
        "status": "replaced" if replaced else "no_gain",
        "orig_size": len(raw),
        "size": len(best),
    }


def lambda_handler(event, context):
    failures = []
    results = []
    for rec in event.get("Records", []):
        try:
            body = json.loads(rec["body"])
        except (KeyError, ValueError, TypeError):
            failures.append(rec.get("messageId", "unknown"))
            continue
        for s3rec in body.get("Records", []):
            try:
                results.append(_process_record(s3rec))
            except Exception as e:  # noqa: BLE001 - keep retrying other records
                logger.exception(
                    "failed record bucket=%s key=%s: %s",
                    s3rec.get("s3", {}).get("bucket", {}).get("name"),
                    s3rec.get("s3", {}).get("object", {}).get("key"),
                    e,
                )
                failures.append(rec.get("messageId", "unknown"))
    logger.info("results=%s failures=%s", results, failures)
    return {"batchItemFailures": [{"itemIdentifier": f} for f in failures]}
