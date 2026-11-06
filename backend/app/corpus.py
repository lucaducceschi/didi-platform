"""Read-only access to the corpus, reusing the DataService shared with the Streamlit demo."""

import re
from typing import Dict, List

from src.ui.data_service import DataService

from backend.app.settings import get_settings

_SNIPPET_MARK_RE = re.compile(r'<mark class="fts-hl">(.*?)</mark>', re.DOTALL)


def get_corpus() -> DataService:
    """Return a service for one request. It holds per-query state, so it must not be shared."""
    return DataService(get_settings().corpus_path, read_only=True, enable_hybrid=False)


def snippet_parts(snippet: str) -> List[Dict[str, object]]:
    """Split an FTS snippet into text parts, so clients never have to insert HTML from the corpus."""
    parts = _SNIPPET_MARK_RE.split(snippet or "")
    return [{"text": text, "match": index % 2 == 1} for index, text in enumerate(parts) if text]
