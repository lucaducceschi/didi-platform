"""
NLP Module for DIDI Platform
Provides quantitative metrics and discrete emotion analysis.
"""

from .lexical import LexicalAnalyzer
from .emotions import NRCEmotionAnalyzer

__all__ = ["LexicalAnalyzer", "NRCEmotionAnalyzer"]
