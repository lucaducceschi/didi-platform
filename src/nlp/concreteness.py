"""
Concreteness vs. Abstractness Analysis for DIDI Research Workbench.

Measures cognitive construal and grounding across German and Italian texts:
- Abstract derivational nominalization suffixes (German: -heit, -keit, -schaft, -ung, etc.;
  Italian: -zione, -mento, -ismo, -ità, etc.)
- Entity and numerical grounding (PER, LOC, ORG, NUM)
- Normative concreteness estimations (1.0 = highly abstract to 5.0 = highly concrete)
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Set

# Morphological suffixes denoting abstract concepts and nominalizations
DE_ABSTRACT_SUFFIXES = (
    "heit", "keit", "schaft", "ung", "ismus", "tät", "tum",
    "ion", "ur", "enz", "anz", "ität", "ik"
)

IT_ABSTRACT_SUFFIXES = (
    "zione", "zioni", "mento", "menti", "ismo", "ismi",
    "ità", "enza", "enze", "anza", "anze", "tà", "tudine"
)

# Core seed dictionaries for high-frequency concrete vs. abstract words
DE_CONCRETE_SEEDS: Set[str] = {
    "brot", "haus", "kind", "schule", "baum", "wasser", "straße", "auto", "berg",
    "wald", "geld", "tisch", "buch", "hand", "stadt", "dorf", "bauer", "apfel",
    "bahn", "zug", "spital", "krankenhaus", "arzt", "feuerwehr", "polizei", "brücke"
}
DE_ABSTRACT_SEEDS: Set[str] = {
    "autonomie", "freiheit", "gerechtigkeit", "zukunft", "politik", "demokratie",
    "verantwortung", "solidarität", "ordnung", "schutz", "gesetz", "kompetenz",
    "entwicklung", "kultur", "frieden", "identität", "recht", "grundsatz", "idee"
}

IT_CONCRETE_SEEDS: Set[str] = {
    "pane", "casa", "bambino", "scuola", "albero", "acqua", "strada", "auto", "montagna",
    "bosco", "denaro", "tavolo", "libro", "mano", "città", "paese", "contadino", "mela",
    "treno", "ospedale", "medico", "pompiere", "polizia", "ponte", "euro"
}
IT_ABSTRACT_SEEDS: Set[str] = {
    "autonomia", "libertà", "giustizia", "futuro", "politica", "democrazia",
    "responsabilità", "solidarietà", "ordine", "tutela", "legge", "competenza",
    "sviluppo", "cultura", "pace", "identità", "diritto", "principio", "idea"
}


@dataclass(frozen=True)
class ConcretenessResult:
    """Structured concreteness evaluation."""
    score: float  # 1.0 (abstract) to 5.0 (concrete)
    label: str    # "Concrete / Grounded", "Balanced", "Abstract / Conceptual"
    abstract_density: float  # abstract suffix hits per 1,000 words
    entity_density: float    # named entities/numbers per 1,000 words
    abstract_words_count: int
    concrete_words_count: int
    word_count: int
    components: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ConcretenessAnalyzer:
    """Computes cognitive construal and concreteness metrics."""

    @staticmethod
    def _is_abstract_de(word: str) -> bool:
        w = word.lower()
        if w in DE_ABSTRACT_SEEDS:
            return True
        if len(w) > 5 and any(w.endswith(suf) for suf in DE_ABSTRACT_SUFFIXES):
            return True
        return False

    @staticmethod
    def _is_concrete_de(word: str) -> bool:
        w = word.lower()
        return w in DE_CONCRETE_SEEDS

    @staticmethod
    def _is_abstract_it(word: str) -> bool:
        w = word.lower()
        if w in IT_ABSTRACT_SEEDS:
            return True
        if len(w) > 5 and any(w.endswith(suf) for suf in IT_ABSTRACT_SUFFIXES):
            return True
        return False

    @staticmethod
    def _is_concrete_it(word: str) -> bool:
        w = word.lower()
        return w in IT_CONCRETE_SEEDS

    def analyze_tokens(
        self,
        tokens: List[Dict[str, Any]],
        language: str = "de",
    ) -> ConcretenessResult:
        """
        Analyze a list of word-layer tokens (each with 'form', 'lemma', 'upos', 'ner').
        """
        lang = language.lower()[:2]
        is_abstract = self._is_abstract_it if lang == "it" else self._is_abstract_de
        is_concrete = self._is_concrete_it if lang == "it" else self._is_concrete_de

        n_words = len(tokens)
        if n_words == 0:
            return ConcretenessResult(
                score=3.0,
                label="Insufficient data",
                abstract_density=0.0,
                entity_density=0.0,
                abstract_words_count=0,
                concrete_words_count=0,
                word_count=0,
                components={},
            )

        n_abstract = 0
        n_concrete = 0
        n_entities = 0

        for t in tokens:
            form = t.get("form", "")
            lemma = t.get("lemma", form)
            upos = t.get("upos", "")
            ner = t.get("ner", "O")

            # Check entity / number grounding
            if upos in ("PROPN", "NUM") or (ner and ner != "O"):
                n_entities += 1
                n_concrete += 1
            elif is_concrete(lemma) or is_concrete(form):
                n_concrete += 1
            elif is_abstract(lemma) or is_abstract(form):
                n_abstract += 1

        # Baseline concreteness score: centered at 3.0, shifting up with concrete grounding, down with abstraction
        # Scaled to realistic 1.0 - 5.0 range
        abstract_rate = (n_abstract / n_words) * 100.0
        concrete_rate = (n_concrete / n_words) * 100.0

        raw_score = 3.0 + ((concrete_rate - abstract_rate) * 0.08)
        score = round(max(1.0, min(5.0, raw_score)), 2)

        if score >= 3.3:
            label = "Concrete / Grounded"
        elif score <= 2.7:
            label = "Abstract / Conceptual"
        else:
            label = "Balanced"

        abstract_density = round((n_abstract / n_words) * 1000.0, 2)
        entity_density = round((n_entities / n_words) * 1000.0, 2)

        return ConcretenessResult(
            score=score,
            label=label,
            abstract_density=abstract_density,
            entity_density=entity_density,
            abstract_words_count=n_abstract,
            concrete_words_count=n_concrete,
            word_count=n_words,
            components={
                "abstract_rate_pct": round(abstract_rate, 2),
                "concrete_rate_pct": round(concrete_rate, 2),
                "entities_count": n_entities,
            },
        )

    def analyze_text(self, text: str, language: str = "de") -> ConcretenessResult:
        """Lightweight text-based fallback tokenizer when tokens aren't pre-loaded."""
        words = re.findall(r"\b[^\W\d_]+(?:'[^\W\d_]+)?\b", text, re.UNICODE)
        synthetic_tokens = [{"form": w, "lemma": w.lower(), "upos": "NOUN" if w[:1].isupper() else "X", "ner": "O"} for w in words]
        return self.analyze_tokens(synthetic_tokens, language=language)


_concreteness_analyzer = ConcretenessAnalyzer()


def analyze_concreteness(tokens_or_text: Any, language: str = "de") -> ConcretenessResult:
    """Analyze concreteness for tokens (list of dicts) or raw text (str)."""
    if isinstance(tokens_or_text, str):
        return _concreteness_analyzer.analyze_text(tokens_or_text, language=language)
    return _concreteness_analyzer.analyze_tokens(tokens_or_text, language=language)

