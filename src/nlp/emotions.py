"""
NRC Multilingual Emotion & Sentiment Analyzer for DIDI Platform.
Computes discrete emotional distributions (Plutchik's 8 basic emotions)
and sentiment valence for South Tyrolean regional news corpora.
"""

import csv
import logging
import os
import re
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger("NRCEmotionAnalyzer")

EMOTION_NAMES = [
    "anger",
    "anticipation",
    "disgust",
    "fear",
    "joy",
    "negative",
    "positive",
    "sadness",
    "surprise",
    "trust",
]

DEFAULT_LEXICON_DIR = Path(
    os.environ.get("NRC_LEXICON_DIR", str(Path.home() / "Downloads" / "NRC-Emotion-Lexicon" / "OneFilePerLanguage"))
)


class NRCEmotionAnalyzer:
    """Multilingual discrete emotion and sentiment scoring using NRC EmoLex."""

    def __init__(self, lexicon_dir: Optional[Path] = None):
        self.lexicon_dir = lexicon_dir or DEFAULT_LEXICON_DIR
        self._lexicons: Dict[str, Dict[str, List[int]]] = {}
        self._load_available_lexicons()

    def _load_lexicon_file(self, file_path: Path) -> Dict[str, List[int]]:
        """Load tab-delimited NRC multilingual file into word -> [0/1 flag list]."""
        lexicon = {}
        if not file_path.exists():
            logger.warning(f"Lexicon file not found: {file_path}")
            return lexicon

        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            reader = csv.reader(f, delimiter="\t")
            try:
                header = next(reader)
            except StopIteration:
                return lexicon

            for row in reader:
                if len(row) >= 12:
                    word = row[11].strip().lower()
                    if word and word not in lexicon:
                        lexicon[word] = [int(x) if x in ("0", "1") else 0 for x in row[1:11]]
        return lexicon

    def _load_available_lexicons(self):
        """Preload German and Italian lexicons."""
        de_path = self.lexicon_dir / "German-NRC-EmoLex.txt"
        it_path = self.lexicon_dir / "Italian-NRC-EmoLex.txt"

        if de_path.exists():
            self._lexicons["de"] = self._load_lexicon_file(de_path)
            logger.info(f"Loaded {len(self._lexicons['de'])} German NRC entries.")
        if it_path.exists():
            self._lexicons["it"] = self._load_lexicon_file(it_path)
            logger.info(f"Loaded {len(self._lexicons['it'])} Italian NRC entries.")

    def tokenize(self, text: str) -> List[str]:
        """Simple lowercase word tokenization."""
        return re.findall(r"\b[^\W\d_]+(?:'[^\W\d_]+)?\b", text.lower(), re.UNICODE)

    def analyze(self, text: str, language: str = "de") -> Dict[str, float]:
        """
        Score text for 8 basic emotions and positive/negative polarity.
        Normalizes scores per 1,000 words.
        """
        # Fallback for Ladin: try Italian cognates if language is lld
        lang_key = "it" if (language == "it" or language.startswith("lld")) else "de"
        lexicon = self._lexicons.get(lang_key, {})

        tokens = self.tokenize(text)
        n = len(tokens)
        if n == 0 or not lexicon:
            res = {emo: 0.0 for emo in EMOTION_NAMES}
            res["net_sentiment"] = 0.0
            res["emotional_density"] = 0.0
            return res

        counts = [0] * len(EMOTION_NAMES)
        matches = 0

        for tok in tokens:
            if tok in lexicon:
                flags = lexicon[tok]
                matches += 1
                for i in range(len(EMOTION_NAMES)):
                    counts[i] += flags[i]

        results = {}
        # Per 1,000 words density
        scale = 1000.0 / n
        for i, emo in enumerate(EMOTION_NAMES):
            results[f"{emo}_density"] = round(counts[i] * scale, 3)
            results[f"{emo}_count"] = counts[i]

        pos = results["positive_count"]
        neg = results["negative_count"]
        total_valence = pos + neg
        results["net_sentiment"] = round((pos - neg) / total_valence, 3) if total_valence > 0 else 0.0
        results["emotional_density"] = round(matches * scale, 3)
        results["matched_emotion_tokens"] = matches

        return results
