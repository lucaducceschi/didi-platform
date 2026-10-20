"""
Local Filesystem Storage Adapter ($0 cost, offline development).
"""

from pathlib import Path
from typing import List
from .base import StorageAdapter


class LocalStorageAdapter(StorageAdapter):
    """Stores assets in a local directory tree simulating cloud object storage."""

    def __init__(self, base_dir: Path):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _resolve(self, target_key: str) -> Path:
        clean_key = target_key.lstrip("/")
        dest = self.base_dir / clean_key
        dest.parent.mkdir(parents=True, exist_ok=True)
        return dest

    def upload_file(self, local_path: Path, target_key: str) -> str:
        dest = self._resolve(target_key)
        import shutil
        shutil.copy2(local_path, dest)
        return f"file://{dest.resolve()}"

    def download_file(self, target_key: str, local_path: Path) -> Path:
        src = self._resolve(target_key)
        if not src.exists():
            raise FileNotFoundError(f"Key {target_key} not found at {src}")
        local_path.parent.mkdir(parents=True, exist_ok=True)
        import shutil
        shutil.copy2(src, local_path)
        return local_path

    def get_bytes(self, target_key: str) -> bytes:
        src = self._resolve(target_key)
        if not src.exists():
            raise FileNotFoundError(f"Key {target_key} not found")
        with open(src, "rb") as f:
            return f.read()

    def put_bytes(self, target_key: str, data: bytes, content_type: str = "application/json") -> str:
        dest = self._resolve(target_key)
        with open(dest, "wb") as f:
            f.write(data)
        return f"file://{dest.resolve()}"

    def list_objects(self, prefix: str = "") -> List[str]:
        clean_prefix = prefix.lstrip("/")
        results = []
        for p in self.base_dir.rglob("*"):
            if p.is_file():
                rel = str(p.relative_to(self.base_dir))
                if not clean_prefix or rel.startswith(clean_prefix):
                    results.append(rel)
        return sorted(results)
