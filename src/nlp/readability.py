"""
Language-aware Readability Metrics for DIDI Research Workbench.

Computes scientifically calibrated readability indices for multilingual corpus analysis:
- Italian (it): Gulpease Index (Lucisano & Piemontese 1988) and Flesch-Vacca (1972)
- German (de): Wiener Sachtextformel WSTF (Bamberger & Vanecek 1984) and Flesch-Amstad (1978)
- Cross-linguistic: LIX (Björnsson 1968) and structural syntactic indicators
"""

from __future__ import annotations

import math
import re
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional


# Regex patterns for sentence and word segmentation
_URL_RE = re.compile(r"https?://\S+|www\.\S+", re.UNICODE)
_WORD_RE = re.compile(r"\b[^\W\d_]+(?:'[^\W\d_]+)?\b", re.UNICODE)
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-ZÄÖÜ\"])", re.UNICODE)

# Vowels and diphthongs for syllable estimation
_DE_VOWELS = set("aeiouäöüy")
_DE_DIPHTHONGS = ("ei", "ey", "ai", "ay", "eu", "äu", "au", "ie")

_IT_VOWELS = set("aeiouàèéìòóù")
_IT_DIPHTHONGS = ("ia", "ie", "io", "iu", "ua", "ue", "uo", "ui", "ai", "ei", "oi", "au", "eu")


def count_syllables_de(word: str) -> int:
    """
    Estimate syllables in a German word based on vowel nuclei and diphthongs.
    Ensures at least 1 syllable for non-empty words.
    """
    w = word.lower()
    if not w:
        return 0

    # Replace known diphthongs with single placeholder character to avoid double counting
    for d in _DE_DIPHTHONGS:
        w = w.replace(d, "_")

    count = 0
    in_vowel = False
    for ch in w:
        if ch in _DE_VOWELS or ch == "_":
            if not in_vowel:
                count += 1
                in_vowel = True
        else:
            in_vowel = False

    return max(1, count)


def count_syllables_it(word: str) -> int:
    """
    Estimate syllables in an Italian word based on vowel nuclei and common diphthongs.
    Ensures at least 1 syllable for non-empty words.
    """
    w = word.lower()
    if not w:
        return 0

    # Replace common diphthongs with placeholder
    for d in _IT_DIPHTHONGS:
        w = w.replace(d, "_")

    count = 0
    in_vowel = False
    for ch in w:
        if ch in _IT_VOWELS or ch == "_":
            if not in_vowel:
                count += 1
                in_vowel = True
        else:
            in_vowel = False

    return max(1, count)


def count_syllables(word: str, language: str = "de") -> int:
    """Count syllables according to language phonotactics."""
    lang = language.lower()[:2]
    if lang == "it":
        return count_syllables_it(word)
    return count_syllables_de(word)


@dataclass(frozen=True)
class ReadabilityResult:
    """Structured readability scores and component values."""
    primary_metric: str
    score: float
    grade_level: str
    reading_ease: float
    lix: float
    avg_sentence_length: float
    avg_word_length: float
    avg_syllables_per_word: float
    word_count: int
    sentence_count: int
    components: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ReadabilityAnalyzer:
    """
    Computes linguistic and structural readability metrics calibrated
    specifically for German and Italian corpora.
    """

    @staticmethod
    def tokenize(text: str) -> List[str]:
        """Normalize and tokenize text into word tokens."""
        clean = _URL_RE.sub(" ", text)
        return _WORD_RE.findall(clean)

    @staticmethod
    def split_sentences(text: str) -> List[str]:
        """Split text into sentences, stripping boilerplate and headings."""
        clean = re.sub(r"\s+", " ", text).strip()
        if not clean:
            return []
        sentences = _SENTENCE_SPLIT_RE.split(clean)
        # Filter out tiny artefacts
        return [s.strip() for s in sentences if len(s.strip()) > 3]

    def analyze(self, text: str, language: str = "de") -> ReadabilityResult:
        """
        Analyze text readability using language-appropriate formulas.

        - Italian (it):
            * Gulpease Index (0-100, official standard for Italian PA)
            * Flesch-Vacca (0-100)
        - German (de):
            * Wiener Sachtextformel WSTF (school grade equivalent 4-15)
            * Flesch-Amstad (0-100)
        - Cross-linguistic:
            * LIX (Läsbarhetsindex)
            * Average Sentence Length (ASL)
            * Average Word Length (AWL in characters)
        """
        lang = language.lower()[:2]
        words = self.tokenize(text)
        sentences = self.split_sentences(text)

        n_words = len(words)
        n_sentences = max(len(sentences), 1)

        # Handle degenerate/empty texts gracefully
        if n_words < 5:
            return ReadabilityResult(
                primary_metric="Gulpease" if lang == "it" else "Wiener Sachtextformel",
                score=0.0,
                grade_level="Insufficient text",
                reading_ease=0.0,
                lix=0.0,
                avg_sentence_length=round(n_words / n_sentences, 2),
                avg_word_length=0.0,
                avg_syllables_per_word=0.0,
                word_count=n_words,
                sentence_count=len(sentences),
                components={},
            )

        asl = n_words / n_sentences
        letters_total = sum(len(w) for w in words)
        awl = letters_total / n_words

        # Syllables
        syllables = [count_syllables(w, language=lang) for w in words]
        total_syllables = sum(syllables)
        asw = total_syllables / n_words

        # LIX calculation: ASL + percentage of words > 6 letters
        long_words = sum(1 for w in words if len(w) > 6)
        pct_long_words = (long_words / n_words) * 100.0
        lix = round(asl + pct_long_words, 2)

        components: Dict[str, Any] = {
            "n_words": n_words,
            "n_sentences": len(sentences),
            "asl": round(asl, 2),
            "awl": round(awl, 2),
            "asw": round(asw, 2),
            "lix": lix,
        }

        if lang == "it":
            # --- Italian: Gulpease & Flesch-Vacca ---
            # Gulpease = 89 + (300 * sentences - 10 * letters) / words
            gulpease = 89.0 + ((300.0 * n_sentences - 10.0 * letters_total) / n_words)
            gulpease = round(max(0.0, min(100.0, gulpease)), 2)

            # Flesch-Vacca = 217 - (1.3 * ASL) - (0.6 * syllables_per_100_words)
            s_100 = asw * 100.0
            flesch_vacca = 217.0 - (1.3 * asl) - (0.6 * s_100)
            flesch_vacca = round(max(0.0, min(100.0, flesch_vacca)), 2)

            # Grade level categorization based on standard Gulpease benchmarks
            if gulpease >= 80:
                grade = "Easy (elementary school)"
            elif gulpease >= 60:
                grade = "Medium (middle school)"
            elif gulpease >= 40:
                grade = "Difficult (high school)"
            else:
                grade = "Very difficult (university)"

            components.update({
                "gulpease": gulpease,
                "flesch_vacca": flesch_vacca,
            })

            return ReadabilityResult(
                primary_metric="Gulpease",
                score=gulpease,
                grade_level=grade,
                reading_ease=flesch_vacca,
                lix=lix,
                avg_sentence_length=round(asl, 2),
                avg_word_length=round(awl, 2),
                avg_syllables_per_word=round(asw, 2),
                word_count=n_words,
                sentence_count=len(sentences),
                components=components,
            )

        else:
            # --- German: Wiener Sachtextformel (WSTF 1) & Flesch-Amstad ---
            # MS: % of words with >= 3 syllables
            ms_count = sum(1 for s in syllables if s >= 3)
            ms_pct = (ms_count / n_words) * 100.0

            # SL: Average sentence length (ASL)
            sl = asl

            # IW: % of words with >= 6 letters
            iw_count = sum(1 for w in words if len(w) >= 6)
            iw_pct = (iw_count / n_words) * 100.0

            # ES: % of monosyllabic words
            es_count = sum(1 for s in syllables if s == 1)
            es_pct = (es_count / n_words) * 100.0

            # WSTF Formula 1 (standard for non-fiction/journalism)
            # WSTF = 0.1935 * MS + 0.1672 * SL + 0.1297 * IW - 0.0327 * ES - 0.8749
            wstf = (0.1935 * ms_pct) + (0.1672 * sl) + (0.1297 * iw_pct) - (0.0327 * es_pct) - 0.8749
            wstf = round(max(3.0, min(16.0, wstf)), 2)

            # Flesch-Amstad = 180 - ASL - (58.5 * ASW)
            flesch_amstad = 180.0 - asl - (58.5 * asw)
            flesch_amstad = round(max(0.0, min(100.0, flesch_amstad)), 2)

            # Grade level categorization based on WSTF school grade benchmarks
            if wstf <= 6.0:
                grade = "Very easy (Grade 4–6)"
            elif wstf <= 8.0:
                grade = "Easy (Grade 7–8)"
            elif wstf <= 10.0:
                grade = "Standard non-fiction (Grade 9–10)"
            elif wstf <= 12.0:
                grade = "Demanding non-fiction (Grade 11–12 / Abitur)"
            else:
                grade = "Very demanding / academic (University level)"

            components.update({
                "wstf": wstf,
                "flesch_amstad": flesch_amstad,
                "ms_pct": round(ms_pct, 2),
                "iw_pct": round(iw_pct, 2),
                "es_pct": round(es_pct, 2),
            })

            return ReadabilityResult(
                primary_metric="Wiener Sachtextformel",
                score=wstf,
                grade_level=grade,
                reading_ease=flesch_amstad,
                lix=lix,
                avg_sentence_length=round(asl, 2),
                avg_word_length=round(awl, 2),
                avg_syllables_per_word=round(asw, 2),
                word_count=n_words,
                sentence_count=len(sentences),
                components=components,
            )


# Global singleton helper
_analyzer = ReadabilityAnalyzer()


def analyze_readability(text: str, language: str = "de") -> ReadabilityResult:
    """Convenience function to compute readability for text in German or Italian."""
    return _analyzer.analyze(text, language=language)

