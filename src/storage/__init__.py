"""
Storage Module for DIDI Platform
Provides SQLite database engine and pluggable cloud/local storage adapters.
"""

from .database import DIDICorpusDB
from .adapters import StorageAdapter, LocalStorageAdapter, S3StorageAdapter, AzureBlobStorageAdapter

__all__ = [
    "DIDICorpusDB",
    "StorageAdapter",
    "LocalStorageAdapter",
    "S3StorageAdapter",
    "AzureBlobStorageAdapter",
]
