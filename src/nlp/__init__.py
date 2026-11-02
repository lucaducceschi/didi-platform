"""
NLP Module for DIDI Platform
Provides quantitative metrics, discrete emotion analysis, and Moral Foundations scoring.
"""

from .lexical import LexicalAnalyzer
from .emotions import NRCEmotionAnalyzer
from .morality import MoralFoundationsAnalyzer

__all__ = ["LexicalAnalyzer", "NRCEmotionAnalyzer", "MoralFoundationsAnalyzer"]
