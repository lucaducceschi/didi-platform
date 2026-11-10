"""
Source registry configuration and loader for DIDI collectors.
Loads and validates sources.yaml.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import List, Literal, Optional

import yaml
from pydantic import BaseModel, Field, field_validator

DEFAULT_SOURCES = Path(__file__).with_name("sources.yaml")


class ArchiveConfig(BaseModel):
    url_template: str
    link_selector: str = "article a[href]"
    start_page: int = 1
    max_pages: int = 50


class Source(BaseModel):
    id: str
    name: str
    language: Literal["de", "it", "lld", "multi"]
    kind: Literal["newspaper", "online", "broadcaster", "agency", "institution", "magazine"]
    owner: str = ""
    tier: int = 1
    enabled: bool = True
    base_url: str
    sitemaps: List[str] = Field(default_factory=list)
    use_robots_sitemaps: bool = True
    rss: List[str] = Field(default_factory=list)
    archive: Optional[ArchiveConfig] = None
    include: List[str] = Field(default_factory=list)
    exclude: List[str] = Field(default_factory=list)
    body_selector: Optional[str] = None
    skip_subscription: bool = True
    delay_seconds: float = 3.0
    respect_robots: bool = True
    notes: str = ""

    @field_validator("include", "exclude")
    @classmethod
    def _valid_regex(cls, v: List[str]) -> List[str]:
        for p in v:
            re.compile(p)
        return v

    def url_allowed(self, url: str) -> bool:
        if self.include and not any(re.search(p, url) for p in self.include):
            return False
        return not any(re.search(p, url) for p in self.exclude)


class Registry(BaseModel):
    user_agent: str
    sources: List[Source]

    def get(self, source_id: str) -> Source:
        for s in self.sources:
            if s.id == source_id:
                return s
        raise KeyError(f"Unknown source '{source_id}'")

    def select(
        self,
        ids: Optional[List[str]] = None,
        language: Optional[str] = None,
        max_tier: Optional[int] = None,
        include_disabled: bool = False,
    ) -> List[Source]:
        out = []
        for s in self.sources:
            if ids and s.id not in ids:
                continue
            if not ids and not include_disabled and not s.enabled:
                continue
            if language and s.language != language:
                continue
            if max_tier and s.tier > max_tier:
                continue
            out.append(s)
        return out


def load_registry(path: Path | str | None = None) -> Registry:
    data = yaml.safe_load(Path(path or DEFAULT_SOURCES).read_text(encoding="utf-8"))
    reg = Registry(**data)
    ids = [s.id for s in reg.sources]
    dupes = {i for i in ids if ids.count(i) > 1}
    if dupes:
        raise ValueError(f"Duplicate source ids: {dupes}")
    return reg

