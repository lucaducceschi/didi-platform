"""
NLP Module for DIDI Platform
Provides quantitative metrics, discrete emotion analysis, and Moral Foundations scoring.
"""

from .lexical import LexicalAnalyzer
from .emotions import NRCEmotionAnalyzer
from .morality import MoralFoundationsAnalyzer
from .readability import ReadabilityAnalyzer, analyze_readability
from .concreteness import ConcretenessAnalyzer, analyze_concreteness
from .complexity import ComplexityAnalyzer, analyze_complexity
from .quotes import QuoteSpan, RULE_VERSION, detect_direct_quotes, split_tokens_by_quotes

__all__ = [
    "LexicalAnalyzer",
    "NRCEmotionAnalyzer",
    "MoralFoundationsAnalyzer",
    "ReadabilityAnalyzer",
    "analyze_readability",
    "ConcretenessAnalyzer",
    "analyze_concreteness",
    "ComplexityAnalyzer",
    "analyze_complexity",
    "QuoteSpan",
    "RULE_VERSION",
    "detect_direct_quotes",
    "split_tokens_by_quotes",
]
