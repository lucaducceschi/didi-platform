#!/usr/bin/env python3
"""
Lightweight AWS CLI Utility for DIDI Platform Local Emulation.
Enables rapid interaction with local S3 and DynamoDB without needing the bulky official AWS CLI package.
"""

import argparse
import json
import os
import sys
from pathlib import Path
import boto3

ENDPOINT = os.environ.get("AWS_ENDPOINT_URL", "http://127.0.0.1:4566")
REGION = os.environ.get("AWS_DEFAULT_REGION", "eu-central-1")

s3 = boto3.client("s3", endpoint_url=ENDPOINT, region_name=REGION, aws_access_key_id="test", aws_secret_access_key="test")
dynamo = boto3.client("dynamodb", endpoint_url=ENDPOINT, region_name=REGION, aws_access_key_id="test", aws_secret_access_key="test")


def main():
    parser = argparse.ArgumentParser(description="DIDI Local AWS CLI Tool")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # s3-ls
    s3_ls = subparsers.add_parser("s3-ls", help="List S3 buckets or objects")
    s3_ls.add_argument("bucket", nargs="?", help="Bucket name")

    # s3-cp
    s3_cp = subparsers.add_parser("s3-cp", help="Upload local file to S3")
    s3_cp.add_argument("local_path", help="Local file path")
    s3_cp.add_argument("bucket", help="Target bucket")
    s3_cp.add_argument("key", help="Target object key")

    # presign
    presign = subparsers.add_parser("presign", help="Generate pre-signed URL")
    presign.add_argument("bucket", help="Bucket name")
    presign.add_argument("key", help="Object key")
    presign.add_argument("--expires", type=int, default=3600, help="Expiration in seconds")

    # dynamo-scan
    dynamo_scan = subparsers.add_parser("dynamo-scan", help="Scan DynamoDB table")
    dynamo_scan.add_argument("table", default="didi-corpus-index", nargs="?", help="Table name")

    args = parser.parse_args()

    if args.command == "s3-ls":
        if not args.bucket:
            buckets = s3.list_buckets().get("Buckets", [])
            print(f"Buckets on {ENDPOINT}:")
            for b in buckets:
                print(f"  s3://{b['Name']} (Created: {b['CreationDate']})")
        else:
            objs = s3.list_objects_v2(Bucket=args.bucket).get("Contents", [])
            print(f"Objects in s3://{args.bucket}:")
            for o in objs:
                print(f"  {o['LastModified']}  {o['Size']:>8} bytes  {o['Key']}")

    elif args.command == "s3-cp":
        s3.upload_file(args.local_path, args.bucket, args.key)
        print(f"Uploaded {args.local_path} -> s3://{args.bucket}/{args.key}")

    elif args.command == "presign":
        url = s3.generate_presigned_url("get_object", Params={"Bucket": args.bucket, "Key": args.key}, ExpiresIn=args.expires)
        print(f"Pre-signed URL (Valid for {args.expires}s):\n{url}")

    elif args.command == "dynamo-scan":
        items = dynamo.scan(TableName=args.table).get("Items", [])
        print(f"Table '{args.table}' contains {len(items)} record(s):")
        for item in items:
            clean_item = {k: list(v.values())[0] for k, v in item.items()}
            print(" ", json.dumps(clean_item, ensure_ascii=False))


if __name__ == "__main__":
    main()
