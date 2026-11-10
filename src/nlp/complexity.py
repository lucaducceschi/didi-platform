"""
Text Complexity and Stylistic Analysis for DIDI Research Workbench.

Measures syntactic complexity, clausal structure, and register:
- Biber's Nominal Ratio (Nominalstil: (NOUN + PROPN + ADP) / (VERB + AUX + ADV))
- Syntactic subordination density (SCONJ density)
- Guiraud's Lexical Richness Index (V / sqrt(N))
"""

from __future__ import annotations

import math
import re
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class ComplexityResult:
    """Structured text complexity evaluation."""
    nominal_ratio: float       # Noun+ADP / Verb+ADV (> 2.0 = heavy administrative/nominal)
    style_label: str           # "Administrative / Nominal", "Standard Journalistic", "Verbal / Dynamic"
    guiraud_richness: float    # V / sqrt(N)
    subordination_density: float # SCONJ per 1,000 words
    noun_count: int
    verb_count: int
    adp_count: int
    word_count: int
    components: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ComplexityAnalyzer:
    """Computes syntactic complexity and stylistic indices from UPOS tokens."""

    def analyze_tokens(self, tokens: List[Dict[str, Any]]) -> ComplexityResult:
        """
        Analyze Stanza word tokens with 'upos' tags.
        """
        n_words = len(tokens)
        if n_words < 5:
            return ComplexityResult(
                nominal_ratio=0.0,
                style_label="Insufficient text",
                guiraud_richness=0.0,
                subordination_density=0.0,
                noun_count=0,
                verb_count=0,
                adp_count=0,
                word_count=n_words,
                components={},
            )

        nouns = 0
        verbs = 0
        adps = 0
        advs = 0
        sconjs = 0
        lemmas = set()

        for t in tokens:
            upos = t.get("upos", "")
            lemma = t.get("lemma", t.get("form", "")).lower()
            if lemma:
                lemmas.add(lemma)

            if upos in ("NOUN", "PROPN"):
                nouns += 1
            elif upos in ("VERB", "AUX"):
                verbs += 1
            elif upos == "ADP":
                adps += 1
            elif upos == "ADV":
                advs += 1
            elif upos == "SCONJ":
                sconjs += 1

        # Nominal Ratio = (NOUN + PROPN + ADP) / (VERB + AUX + ADV)
        verbal_block = max(verbs + advs, 1)
        nominal_block = nouns + adps
        nominal_ratio = round(nominal_block / verbal_block, 2)

        if nominal_ratio >= 2.2:
            style_label = "Administrative / Nominal"
        elif nominal_ratio <= 1.4:
            style_label = "Verbal / Dynamic"
        else:
            style_label = "Standard Journalistic"

        # Guiraud's Index of Lexical Richness: V / sqrt(N)
        guiraud = round(len(lemmas) / math.sqrt(n_words), 2)

        # Subordination density per 1,000 words
        subordination_density = round((sconjs / n_words) * 1000.0, 2)

        return ComplexityResult(
            nominal_ratio=nominal_ratio,
            style_label=style_label,
            guiraud_richness=guiraud,
            subordination_density=subordination_density,
            noun_count=nouns,
            verb_count=verbs,
            adp_count=adps,
            word_count=n_words,
            components={
                "nouns_and_adp": nominal_block,
                "verbs_and_adv": verbal_block,
                "sconj_count": sconjs,
                "vocab_size": len(lemmas),
            },
        )

    def analyze_text(self, text: str) -> ComplexityResult:
        """Heuristic text analyzer when tokens aren't pre-loaded."""
        # Split tokens
        words = re.findall(r"\b[^\W\d_]+(?:'[^\W\d_]+)?\b", text, re.UNICODE)
        synthetic_tokens = []
        for w in words:
            # Capitalized words in German/Italian are likely nouns/propn
            upos = "NOUN" if w[:1].isupper() else "VERB" if w.lower().endswith(("en", "are", "ere", "ire")) else "X"
            synthetic_tokens.append({"form": w, "lemma": w.lower(), "upos": upos})
        return self.analyze_tokens(synthetic_tokens)


_complexity_analyzer = ComplexityAnalyzer()


def analyze_complexity(tokens_or_text: Any) -> ComplexityResult:
    """Analyze complexity for tokens (list of dicts) or raw text (str)."""
    if isinstance(tokens_or_text, str):
        return _complexity_analyzer.analyze_text(tokens_or_text)
    return _complexity_analyzer.analyze_tokens(tokens_or_text)

