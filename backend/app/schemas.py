"""API response models."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class SnippetPart(BaseModel):
    text: str
    match: bool


class QueryInterpretation(BaseModel):
    original_query: str
    normalized_query: str
    search_mode: str
    effective_fts: str
    expansion_terms: List[Dict[str, Any]] = []
    expansion_language: Optional[str] = None
    expansion_category: Optional[str] = None
    warnings: List[str] = []
    total_results: int = 0
    active_filters: Dict[str, Any] = {}


class ArticleSummary(BaseModel):
    id: str
    source: str
    source_label: str
    source_type: str = "journalism"
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
    hidden_articles: int = 0
    query_interpretation: Optional[QueryInterpretation] = None


class ConcordanceLine(BaseModel):
    article_id: str
    title: str
    source: str
    source_label: str
    source_type: str = "journalism"
    language: str
    language_label: str
    publish_date: str
    start_char: int
    end_char: int
    left_context: str
    keyword: str
    right_context: str


class ConcordanceResponse(BaseModel):
    total_lines: int
    total_articles: int
    page: int
    page_size: int
    items: List[ConcordanceLine]


class SearchDistribution(BaseModel):
    total: int
    by_language: Dict[str, int] = {}
    by_source: Dict[str, int] = {}
    by_source_type: Dict[str, int] = {}
    by_year: Dict[str, int] = {}


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
    readability_score: Optional[float] = None
    readability_metric: Optional[str] = None
    readability_grade: Optional[str] = None
    lix: Optional[float] = None


class ArticleDetail(BaseModel):
    id: str
    source: str
    source_label: str
    source_type: str = "journalism"
    twin_article_id: Optional[str] = None
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
    source_types: List[Facet] = []


class HealthResponse(BaseModel):
    status: str
    build: Dict[str, str]
    checks: Dict[str, str]
