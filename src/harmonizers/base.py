"""
Base Harmonizer Interface.
"""

from abc import ABC, abstractmethod
from typing import Optional, List
from pathlib import Path
from ..models.schema import DIDIArticle


class BaseHarmonizer(ABC):
    """Abstract base class for news source harmonizers."""

    @abstractmethod
    def parse_file(self, file_path: Path) -> Optional[DIDIArticle]:
        """Parse a single raw article file into a standardized DIDIArticle."""
        pass

    @abstractmethod
    def parse_directory(self, dir_path: Path, limit: Optional[int] = None) -> List[DIDIArticle]:
        """Parse all articles in a directory."""
        pass
