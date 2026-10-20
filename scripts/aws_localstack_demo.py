#!/usr/bin/env python3
"""
AWS Cloud Architecture Local Emulation Demo for DIDI Platform.
Demonstrates S3 Object Storage, DynamoDB Metadata Registry, and Serverless Pipeline
running locally on port 4566 ($0 Cost) using Boto3.
"""

import argparse
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import boto3
from botocore.exceptions import ClientError
from src.nlp import LexicalAnalyzer, NRCEmotionAnalyzer

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("AWSDemo")

DEFAULT_ENDPOINT = "http://localhost:4566"
DEFAULT_REGION = "eu-central-1"

RAW_BUCKET = "didi-articles-raw"
HARMONIZED_BUCKET = "didi-articles-harmonized"
DYNAMO_TABLE = "didi-corpus-index"


def get_aws_client(service_name: str, endpoint_url: str):
    """Instantiate a Boto3 client targeting the local emulator."""
    return boto3.client(
        service_name,
        endpoint_url=endpoint_url,
        region_name=DEFAULT_REGION,
        aws_access_key_id="test",
        aws_secret_access_key="test",
    )


def setup_s3(s3_client):
    """Create S3 storage lake buckets."""
    print("\n" + "=" * 65)
    print("  [Step 1] Amazon S3: Data Lake Setup")
    print("=" * 65)
    for bucket in [RAW_BUCKET, HARMONIZED_BUCKET]:
        try:
            s3_client.head_bucket(Bucket=bucket)
            print(f"  ✓ S3 Bucket already exists: s3://{bucket}")
        except ClientError:
            try:
                # eu-central-1 requires LocationConstraint
                s3_client.create_bucket(
                    Bucket=bucket,
                    CreateBucketConfiguration={"LocationConstraint": DEFAULT_REGION},
                )
            except ClientError:
                # LocalStack / Moto us-east-1 compatibility fallback
                s3_client.create_bucket(Bucket=bucket)
            print(f"  ✓ Created S3 Bucket: s3://{bucket}")


def setup_dynamodb(dynamo_client):
    """Create DynamoDB NoSQL metadata catalog table."""
    print("\n" + "=" * 65)
    print("  [Step 2] Amazon DynamoDB: Metadata Catalog")
    print("=" * 65)
    try:
        dynamo_client.describe_table(TableName=DYNAMO_TABLE)
        print(f"  ✓ DynamoDB Table already exists: {DYNAMO_TABLE}")
    except ClientError:
        dynamo_client.create_table(
            TableName=DYNAMO_TABLE,
            KeySchema=[
                {"AttributeName": "article_id", "KeyType": "HASH"},  # Partition Key
                {"AttributeName": "publish_date", "KeyType": "RANGE"},  # Sort Key
            ],
            AttributeDefinitions=[
                {"AttributeName": "article_id", "AttributeType": "S"},
                {"AttributeName": "publish_date", "AttributeType": "S"},
                {"AttributeName": "language", "AttributeType": "S"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "LanguageIndex",
                    "KeySchema": [
                        {"AttributeName": "language", "KeyType": "HASH"},
                        {"AttributeName": "publish_date", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                    "ProvisionedThroughput": {"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
                }
            ],
            ProvisionedThroughput={"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
        )
        print(f"  ✓ Created DynamoDB Table: {DYNAMO_TABLE} (with LanguageIndex GSI)")


def simulate_event_driven_pipeline(s3_client, dynamo_client):
    """
    Simulate AWS Event-Driven ingestion:
    1. Raw article ingested into S3
    2. Event triggers Lambda processing (NLP profiling & normalization)
    3. Output saved to harmonized S3 bucket and indexed in DynamoDB
    """
    print("\n" + "=" * 65)
    print("  [Step 3] Event-Driven Processing Simulation (S3 → Lambda → DynamoDB)")
    print("=" * 65)

    sample_article = {
        "url": "https://salto.bz/it/article/13052025/autonomia-e-futuro-delle-valli",
        "title": "Autonomia e futuro delle valli alpine",
        "author": "Redazione Salto",
        "category": "Politica",
        "publish_date": "2025-05-13T12:00:00Z",
        "language": "it",
        "full_text": (
            "Il dibattito sull'autonomia speciale dell'Alto Adige / Südtirol entra in una fase cruciale. "
            "Le istituzioni provinciali ribadiscono la necessità di tutelare le minoranze linguistiche, "
            "inclusa la comunità ladina delle valli dolomitiche. Lo sviluppo economico e la coesione sociale "
            "rappresentano la chiave per garantire un futuro condiviso di prosperità e rispetto reciproco."
        ),
    }

    raw_key = "it/salto_sample_autonomia.json"
    print(f"  1. Ingesting raw article into S3: s3://{RAW_BUCKET}/{raw_key}")
    s3_client.put_object(
        Bucket=RAW_BUCKET,
        Key=raw_key,
        Body=json.dumps(sample_article, ensure_ascii=False).encode("utf-8"),
        ContentType="application/json",
    )

    # Lambda processing simulation
    print("  2. Simulating Lambda Handler Execution (NLP profiling)...")
    lex_analyzer = LexicalAnalyzer()
    emo_analyzer = NRCEmotionAnalyzer()

    text = sample_article["full_text"]
    lex_metrics = lex_analyzer.analyze(text)
    emo_metrics = emo_analyzer.analyze(text, sample_article["language"])

    harmonized_id = "salto_it_20250513_autonomia_e_futuro"
    harmonized_record = {
        "id": harmonized_id,
        "source": "salto",
        "language": sample_article["language"],
        "url": sample_article["url"],
        "title": sample_article["title"],
        "author": sample_article["author"],
        "category": sample_article["category"],
        "publish_date": sample_article["publish_date"],
        "full_text": text,
        "word_count": lex_metrics["word_count"],
        "lexical_metrics": lex_metrics,
        "emotion_metrics": emo_metrics,
        "processed_at": datetime.now(timezone.utc).isoformat(),
    }

    # Store harmonized JSON in Destination S3 Bucket
    out_key = f"it/{harmonized_id}.json"
    s3_client.put_object(
        Bucket=HARMONIZED_BUCKET,
        Key=out_key,
        Body=json.dumps(harmonized_record, ensure_ascii=False).encode("utf-8"),
        ContentType="application/json",
    )
    print(f"  ✓ Stored Harmonized Object in: s3://{HARMONIZED_BUCKET}/{out_key}")

    # Register in DynamoDB
    dynamo_client.put_item(
        TableName=DYNAMO_TABLE,
        Item={
            "article_id": {"S": harmonized_id},
            "publish_date": {"S": sample_article["publish_date"]},
            "language": {"S": sample_article["language"]},
            "title": {"S": sample_article["title"]},
            "source": {"S": "salto"},
            "word_count": {"N": str(lex_metrics["word_count"])},
            "net_sentiment": {"N": str(emo_metrics["net_sentiment"])},
            "s3_location": {"S": f"s3://{HARMONIZED_BUCKET}/{out_key}"},
        },
    )
    print(f"  ✓ Registered Record in DynamoDB: Table='{DYNAMO_TABLE}', ID='{harmonized_id}'")

    # Generate Pre-Signed URL (Key AWS Archiving / Security Pattern)
    print("\n" + "=" * 65)
    print("  [Step 4] AWS S3 Pre-Signed URL Generation (Secure Archival Access)")
    print("=" * 65)
    presigned_url = s3_client.generate_presigned_url(
        "get_object",
        Params={"Bucket": HARMONIZED_BUCKET, "Key": out_key},
        ExpiresIn=3600,
    )
    print(f"  Generated 1-hour pre-signed URL:\n  {presigned_url[:100]}...\n")

    # Verification: Query DynamoDB
    res = dynamo_client.get_item(
        TableName=DYNAMO_TABLE,
        Key={
            "article_id": {"S": harmonized_id},
            "publish_date": {"S": sample_article["publish_date"]},
        },
    )
    item = res.get("Item", {})
    print(f"  ✓ Verified DynamoDB Retrieval:")
    print(f"    - Title:         {item.get('title', {}).get('S')}")
    print(f"    - Language:      {item.get('language', {}).get('S')}")
    print(f"    - Net Sentiment: {item.get('net_sentiment', {}).get('N')}")
    print(f"    - S3 Location:   {item.get('s3_location', {}).get('S')}")


def main():
    parser = argparse.ArgumentParser(description="Test AWS local emulation")
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT, help="AWS endpoint URL (default: http://localhost:4566)")
    args = parser.parse_args()

    print("=" * 65)
    print("  DIDI Platform: AWS Cloud Architecture Local Emulation")
    print(f"  Target Endpoint: {args.endpoint}")
    print("=" * 65)

    s3_client = get_aws_client("s3", args.endpoint)
    dynamo_client = get_aws_client("dynamodb", args.endpoint)

    try:
        setup_s3(s3_client)
        setup_dynamodb(dynamo_client)
        simulate_event_driven_pipeline(s3_client, dynamo_client)
        print("\n" + "=" * 65)
        print("  ✓ AWS Local Emulation Pipeline Verification Successful!")
        print("=" * 65)
    except Exception as e:
        print(f"\n❌ Connection Error: {e}")
        print("\nEnsure the local AWS emulator is running. For example:")
        print("  - LocalStack: docker compose up -d localstack")
        print("  - Moto Server: moto_server -p 4566")
        sys.exit(1)


if __name__ == "__main__":
    main()
