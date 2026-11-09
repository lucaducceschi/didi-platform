"""Word layer service providing token-level linguistic annotations."""

from typing import Any, Dict, List
from src.ui.data_service import DataService


def get_article_words(article_id: str) -> List[Dict[str, Any]]:
    """Retrieve all token annotations for an article."""
    return DataService().get_article_words(article_id)


def get_passage_words(article_id: str, start_char: int, end_char: int) -> List[Dict[str, Any]]:
    """Retrieve token annotations within or intersecting a character span."""
    return DataService().get_passage_words(article_id, start_char, end_char)

