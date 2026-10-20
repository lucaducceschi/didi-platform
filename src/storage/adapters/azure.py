"""
Microsoft Azure Blob Storage Adapter for DIDI Platform.
Target deployment interface for Microsoft Azure AI Foundry migration.
"""

import logging
from pathlib import Path
from typing import List, Optional
from .base import StorageAdapter

logger = logging.getLogger("AzureBlobStorageAdapter")


class AzureBlobStorageAdapter(StorageAdapter):
    """Interacts with Azure Blob Storage / Azure AI Foundry data lakes."""

    def __init__(
        self,
        container_name: str,
        connection_string: Optional[str] = None,
        account_url: Optional[str] = None,
    ):
        self.container_name = container_name
        self.connection_string = connection_string
        self.account_url = account_url

        try:
            from azure.storage.blob import BlobServiceClient
            if connection_string:
                self.client = BlobServiceClient.from_connection_string(connection_string)
            elif account_url:
                from azure.identity import DefaultAzureCredential
                self.client = BlobServiceClient(account_url, credential=DefaultAzureCredential())
            else:
                self.client = None
            self.container_client = self.client.get_container_client(container_name) if self.client else None
        except ImportError:
            self.client = None
            self.container_client = None
            logger.info("azure-storage-blob not installed. Adapter running in portable contract mode.")

    def upload_file(self, local_path: Path, target_key: str) -> str:
        clean_key = target_key.lstrip("/")
        if not self.container_client:
            raise RuntimeError("azure-storage-blob required. Install: pip install azure-storage-blob azure-identity")
        with open(local_path, "rb") as data:
            self.container_client.upload_blob(name=clean_key, data=data, overwrite=True)
        return f"azure://{self.container_name}/{clean_key}"

    def download_file(self, target_key: str, local_path: Path) -> Path:
        clean_key = target_key.lstrip("/")
        if not self.container_client:
            raise RuntimeError("azure-storage-blob required.")
        local_path.parent.mkdir(parents=True, exist_ok=True)
        with open(local_path, "wb") as f:
            blob_data = self.container_client.download_blob(clean_key)
            f.write(blob_data.readall())
        return local_path

    def get_bytes(self, target_key: str) -> bytes:
        clean_key = target_key.lstrip("/")
        if not self.container_client:
            raise RuntimeError("azure-storage-blob required.")
        blob_data = self.container_client.download_blob(clean_key)
        return blob_data.readall()

    def put_bytes(self, target_key: str, data: bytes, content_type: str = "application/json") -> str:
        clean_key = target_key.lstrip("/")
        if not self.container_client:
            raise RuntimeError("azure-storage-blob required.")
        self.container_client.upload_blob(name=clean_key, data=data, overwrite=True)
        return f"azure://{self.container_name}/{clean_key}"

    def list_objects(self, prefix: str = "") -> List[str]:
        clean_prefix = prefix.lstrip("/")
        if not self.container_client:
            return []
        return [b.name for b in self.container_client.list_blobs(name_starts_with=clean_prefix)]
