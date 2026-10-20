"""
Canonical Data Schema for the DIDI Platform.
Harmonizes multi-source news media (Tageszeitung, Salto, La Usc).
Supports Pydantic v2 if available, with graceful fallback to standard dataclasses.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any, Literal

try:
    from pydantic import BaseModel, Field, model_validator

    class DIDIArticle(BaseModel):
        id: str
        source: Literal["tageszeitung", "la_usc", "salto"]
        language: str  # "de", "it", "lld", "lld_gherd", "lld_badia"
        url: str
        title: str
        publish_date: datetime
        author: str = "Redaktion"
        category: Optional[str] = None
        breadcrumbs: List[str] = Field(default_factory=list)
        full_text: str
        word_count: int = 0
        metadata: Dict[str, Any] = Field(default_factory=dict)

        @model_validator(mode="before")
        @classmethod
        def calculate_word_count(cls, values: Any) -> Any:
            if isinstance(values, dict):
                text = values.get("full_text", "")
                if text and ("word_count" not in values or not values["word_count"]):
                    values["word_count"] = len(text.split())
            return values

        def to_dict(self) -> Dict[str, Any]:
            d = self.model_dump()
            d["publish_date"] = self.publish_date.isoformat()
            return d

except ImportError:
    from dataclasses import dataclass, field, asdict

    @dataclass
    class DIDIArticle:
        id: str
        source: str
        language: str
        url: str
        title: str
        publish_date: datetime
        full_text: str
        author: str = "Redaktion"
        category: Optional[str] = None
        breadcrumbs: List[str] = field(default_factory=list)
        word_count: int = 0
        metadata: Dict[str, Any] = field(default_factory=dict)

        def __post_init__(self):
            if not self.word_count and self.full_text:
                self.word_count = len(self.full_text.split())

        def to_dict(self) -> Dict[str, Any]:
            d = asdict(self)
            d["publish_date"] = self.publish_date.isoformat()
            return d
