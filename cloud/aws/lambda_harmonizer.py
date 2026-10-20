"""
AWS Lambda S3-Event Trigger Function.
Runs on S3 object creation in bucket 'didi-articles-raw', harmonizes article,
and writes to 'didi-articles-harmonized' while emitting an EventBridge event.
"""

import json
import logging
import os
import urllib.parse
from datetime import datetime, timezone
import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

TARGET_BUCKET = os.environ.get("TARGET_BUCKET", "didi-articles-harmonized")
s3 = boto3.client("s3")


def lambda_handler(event, context):
    """Triggered by s3:ObjectCreated:*."""
    for record in event.get("Records", []):
        src_bucket = record["s3"]["bucket"]["name"]
        raw_key = urllib.parse.unquote_plus(record["s3"]["object"]["key"])
        logger.info(f"Processing object: {raw_key} from bucket: {src_bucket}")

        # 1. Download raw payload
        resp = s3.get_object(Bucket=src_bucket, Key=raw_key)
        raw_data = json.loads(resp["Body"].read().decode("utf-8"))

        # 2. Canonical Harmonization
        url = raw_data.get("url", "")
        lang = raw_data.get("language") or ("it" if "/it/" in url else "de")
        title = raw_data.get("title", "Untitled")
        full_text = raw_data.get("full_text", "")
        word_count = len(full_text.split())

        harmonized_record = {
            "id": f"cloud_{lang}_{raw_key.replace('/', '_').replace('.json', '')}",
            "source": "salto" if "salto" in url else "tageszeitung",
            "language": lang,
            "url": url,
            "title": title,
            "publish_date": raw_data.get("publish_date", datetime.now(timezone.utc).isoformat()),
            "author": raw_data.get("author", "Redaktion"),
            "category": raw_data.get("category", "News"),
            "full_text": full_text,
            "word_count": word_count,
            "metadata": raw_data.get("metadata", {}),
            "harmonized_at": datetime.now(timezone.utc).isoformat(),
        }

        # 3. Store into destination bucket
        out_key = f"{lang}/{harmonized_record['id']}.json"
        s3.put_object(
            Bucket=TARGET_BUCKET,
            Key=out_key,
            Body=json.dumps(harmonized_record, ensure_ascii=False).encode("utf-8"),
            ContentType="application/json",
        )
        logger.info(f"Successfully stored harmonized record: s3://{TARGET_BUCKET}/{out_key}")

    return {"statusCode": 200, "body": json.dumps("Harmonization completed")}
