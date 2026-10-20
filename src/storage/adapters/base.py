"""
Storage Adapter Interface for DIDI Platform.
Enables pluggable document storage across Local Disk ($0), AWS S3, and Microsoft Azure Foundry.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Optional


class StorageAdapter(ABC):
    """Abstract interface for storing raw and processed corpus assets."""

    @abstractmethod
    def upload_file(self, local_path: Path, target_key: str) -> str:
        """Upload a local file to the storage provider and return its URI."""
        pass

    @abstractmethod
    def download_file(self, target_key: str, local_path: Path) -> Path:
        """Download an object to the local filesystem."""
        pass

    @abstractmethod
    def get_bytes(self, target_key: str) -> bytes:
        """Retrieve raw bytes of an object."""
        pass

    @abstractmethod
    def put_bytes(self, target_key: str, data: bytes, content_type: str = "application/json") -> str:
        """Store bytes directly into the storage provider."""
        pass

    @abstractmethod
    def list_objects(self, prefix: str = "") -> List[str]:
        """List keys matching an optional prefix."""
        pass
