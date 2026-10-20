"""
Lexical & Syntactic Diversity Metrics for DIDI Research Workbench.
Computes quantitative stylistic metrics across German, Italian, and Ladin texts.
"""

import math
import re
from collections import Counter
from typing import Dict, List, Tuple


class LexicalAnalyzer:
    """Computes lexical diversity, syntactic density, and readability indicators."""

    @staticmethod
    def tokenize(text: str) -> List[str]:
        """Normalize and tokenize text into lowercase word tokens."""
        # Strip URLs and formatting
        text = re.sub(r"https?://\S+", "", text)
        tokens = re.findall(r"\b[^\W\d_]+(?:'[^\W\d_]+)?\b", text.lower(), re.UNICODE)
        return tokens

    @staticmethod
    def split_sentences(text: str) -> List[str]:
        """Split text into sentences using standard regex delimiters."""
        clean = re.sub(r"\s+", " ", text).strip()
        sentences = re.split(r"(?<=[.!?])\s+(?=[A-ZÄÖÜ\"])", clean)
        return [s.strip() for s in sentences if len(s.strip()) > 3]

    def analyze(self, text: str) -> Dict[str, float]:
        """
        Analyze a text and return comprehensive lexical metrics.
        Returns:
            - word_count: Total tokens
            - vocab_size: Number of unique tokens
            - sentence_count: Total detected sentences
            - mean_sentence_length: Tokens per sentence
            - ttr: Type-Token Ratio (V / N)
            - root_ttr: Guiraud's index (V / sqrt(N))
            - log_ttr: Herdan's C (log V / log N)
            - hapax_count: Words occurring exactly once
            - hapax_ratio: Hapax legomena / vocab_size
        """
        tokens = self.tokenize(text)
        n = len(tokens)
        if n == 0:
            return {
                "word_count": 0,
                "vocab_size": 0,
                "sentence_count": 0,
                "mean_sentence_length": 0.0,
                "ttr": 0.0,
                "root_ttr": 0.0,
                "log_ttr": 0.0,
                "hapax_count": 0,
                "hapax_ratio": 0.0,
            }

        counts = Counter(tokens)
        v = len(counts)
        sentences = self.split_sentences(text)
        s_count = max(len(sentences), 1)

        ttr = v / n
        root_ttr = v / math.sqrt(n)
        log_ttr = math.log(v) / math.log(n) if n > 1 and v > 1 else 1.0

        hapax = sum(1 for _, c in counts.items() if c == 1)
        hapax_ratio = hapax / v if v > 0 else 0.0

        return {
            "word_count": n,
            "vocab_size": v,
            "sentence_count": len(sentences),
            "mean_sentence_length": round(n / s_count, 2),
            "ttr": round(ttr, 4),
            "root_ttr": round(root_ttr, 4),
            "log_ttr": round(log_ttr, 4),
            "hapax_count": hapax,
            "hapax_ratio": round(hapax_ratio, 4),
        }
