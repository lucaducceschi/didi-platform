"""API response models."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class SnippetPart(BaseModel):
    text: str
    match: bool


class ArticleSummary(BaseModel):
    id: str
    source: str
    source_label: str
    language: str
    language_label: str
    url: str
    title: str
    publish_date: str
    author: Optional[str] = None
    category: Optional[str] = None
    word_count: int
    snippet: List[SnippetPart]


class SearchResponse(BaseModel):
    total: int
    page: int
    page_size: int
    results: List[ArticleSummary]


class ArticleMetrics(BaseModel):
    net_sentiment: Optional[float] = None
    moral_density: Optional[float] = None
    moral_valence: Optional[float] = None
    care_density: Optional[float] = None
    fairness_density: Optional[float] = None
    loyalty_density: Optional[float] = None
    authority_density: Optional[float] = None
    sanctity_density: Optional[float] = None
    emotional_density: Optional[float] = None
    ttr: Optional[float] = None


class ArticleDetail(BaseModel):
    id: str
    source: str
    source_label: str
    language: str
    language_label: str
    url: str
    title: str
    publish_date: str
    author: Optional[str] = None
    category: Optional[str] = None
    word_count: int
    full_text: str
    metrics: ArticleMetrics
    metadata: Dict[str, Any] = {}


class Facet(BaseModel):
    id: str
    label: str
    count: int


class CorpusSummary(BaseModel):
    total_articles: int
    total_words: int
    min_date: str
    max_date: str
    sources: List[Facet]
    languages: List[Facet]


class HealthResponse(BaseModel):
    status: str
    build: Dict[str, str]
    checks: Dict[str, str]
