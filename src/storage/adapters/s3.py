"""
AWS S3 & LocalStack Storage Adapter.
Supports both real AWS S3 and LocalStack ($0 local emulation).
"""

import logging
from pathlib import Path
from typing import List, Optional
from .base import StorageAdapter

logger = logging.getLogger("S3StorageAdapter")


class S3StorageAdapter(StorageAdapter):
    """Interacts with AWS S3 or LocalStack S3 buckets."""

    def __init__(
        self,
        bucket_name: str,
        endpoint_url: Optional[str] = None,
        region_name: str = "eu-central-1",
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
    ):
        self.bucket_name = bucket_name
        self.endpoint_url = endpoint_url
        self.region_name = region_name

        try:
            import boto3
            self.s3 = boto3.client(
                "s3",
                endpoint_url=endpoint_url,
                region_name=region_name,
                aws_access_key_id=aws_access_key_id or "test",
                aws_secret_access_key=aws_secret_access_key or "test",
            )
        except ImportError:
            self.s3 = None
            logger.warning("boto3 is not installed. S3StorageAdapter is running in stub/dry-run mode.")

    def upload_file(self, local_path: Path, target_key: str) -> str:
        clean_key = target_key.lstrip("/")
        if not self.s3:
            raise RuntimeError("boto3 required for live S3 upload. Install with: pip install boto3")
        self.s3.upload_file(str(local_path), self.bucket_name, clean_key)
        return f"s3://{self.bucket_name}/{clean_key}"

    def download_file(self, target_key: str, local_path: Path) -> Path:
        clean_key = target_key.lstrip("/")
        if not self.s3:
            raise RuntimeError("boto3 required for live S3 download.")
        local_path.parent.mkdir(parents=True, exist_ok=True)
        self.s3.download_file(self.bucket_name, clean_key, str(local_path))
        return local_path

    def get_bytes(self, target_key: str) -> bytes:
        clean_key = target_key.lstrip("/")
        if not self.s3:
            raise RuntimeError("boto3 required for S3 get_bytes.")
        response = self.s3.get_object(Bucket=self.bucket_name, Key=clean_key)
        return response["Body"].read()

    def put_bytes(self, target_key: str, data: bytes, content_type: str = "application/json") -> str:
        clean_key = target_key.lstrip("/")
        if not self.s3:
            raise RuntimeError("boto3 required for S3 put_bytes.")
        self.s3.put_object(
            Bucket=self.bucket_name,
            Key=clean_key,
            Body=data,
            ContentType=content_type,
        )
        return f"s3://{self.bucket_name}/{clean_key}"

    def list_objects(self, prefix: str = "") -> List[str]:
        clean_prefix = prefix.lstrip("/")
        if not self.s3:
            return []
        paginator = self.s3.get_paginator("list_objects_v2")
        keys = []
        for page in paginator.paginate(Bucket=self.bucket_name, Prefix=clean_prefix):
            for obj in page.get("Contents", []):
                keys.append(obj["Key"])
        return keys
