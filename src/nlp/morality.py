"""
Multilingual Moral Foundations Analyzer (MFD 2.0 / mMPD / it-MFD / Ladin DLS+BISTRO)
for the DIDI Platform.

Supports:
  - German (`de`): Husson & Palma (2025) ∪ Simonsen & Widmann (2023) mMPD_de
  - Italian (`it`): Husson & Palma (2025) ∪ Rizzoli et al. (2026) it-MFD
  - Ladin (`lld_gherd`, `lld_badia`, `lld_fascia`, `lld`): Triangulated DLS (IT ∩ DE)
    + Eurac BISTRO validated legal/civic concepts + Forni/Apertium inflectional lookup.

Can operate in full Stanza `(lemma, upos)` mode (`use_stanza=True`) or fast pre-compiled
morphological lookup mode (`use_stanza=False`, default for large batch ingestion).
"""

import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger("MoralFoundationsAnalyzer")

FOUNDATIONS = ["care", "fairness", "loyalty", "authority", "sanctity"]
FOUNDATION_POLES = [
    "care.virtue", "care.vice",
    "fairness.virtue", "fairness.vice",
    "loyalty.virtue", "loyalty.vice",
    "authority.virtue", "authority.vice",
    "sanctity.virtue", "sanctity.vice",
]

DEFAULT_MFD_PATH = Path(
    os.environ.get(
        "MFD_LEXICON_PATH",
        str(Path(__file__).resolve().parent.parent.parent / "assets" / "mfd_compiled_lemmas.json"),
    )
)

# Ladin auxiliaries preceding "stat" (participle of ëster = "been", not noun "Stat" = State)
LLD_AUX_BEFORE_STAT = {
    "ie", "iel", "iël", "é", "el", "ël", "son", "sun", "sëis", "seis",
    "fova", "fô", "sarà", "sara", "foss", "fossa", "ester", "ëster",
}


class MoralFoundationsAnalyzer:
    """Computes Moral Foundations Theory (MFT) virtue/vice densities across DE, IT, and Ladin."""

    def __init__(self, lexicon_path: Optional[Path] = None, use_stanza: bool = False):
        self.lexicon_path = Path(lexicon_path) if lexicon_path else DEFAULT_MFD_PATH
        self.use_stanza = use_stanza
        self._data: Dict[str, Any] = {}
        self._de_compound_heads: List[Tuple[str, List[str]]] = []
        self._stanza_pipelines: Dict[str, Any] = {}
        self._load_lexicon()

    def _load_lexicon(self):
        if not self.lexicon_path.exists():
            logger.warning(f"Compiled MFD lexicon not found at {self.lexicon_path}. Returning zero scores.")
            return
        try:
            with open(self.lexicon_path, "r", encoding="utf-8") as f:
                self._data = json.load(f)
            # Precompute German noun lemmas (>= 5 chars) for compound-head decomposition
            de_lemma_upos = self._data.get("de", {}).get("lemma_upos", {})
            heads = []
            for lemma, upos_dict in de_lemma_upos.items():
                if len(lemma) >= 5 and "NOUN" in upos_dict:
                    heads.append((lemma, upos_dict["NOUN"]))
            # Sort longest-first so most specific compound head wins
            self._de_compound_heads = sorted(heads, key=lambda x: len(x[0]), reverse=True)
        except Exception as e:
            logger.error(f"Failed to load MFD lexicon from {self.lexicon_path}: {e}")
            self._data = {}

    def _get_stanza_pipeline(self, lang: str):
        if lang not in self._stanza_pipelines:
            import stanza

            self._stanza_pipelines[lang] = stanza.Pipeline(
                lang=lang,
                processors="tokenize,mwt,pos,lemma",
                verbose=False,
            )
        return self._stanza_pipelines[lang]

    def _match_de_compound_head(self, word_lower: str) -> List[str]:
        """Fallback for German nominal compounds (e.g. 'Autonomieverletzung' -> 'verletzung')."""
        if len(word_lower) < 9:
            return []
        for head_lemma, poles in self._de_compound_heads:
            if len(word_lower) >= len(head_lemma) + 3 and word_lower.endswith(head_lemma):
                return poles
        return []

    def tokenize_with_case(self, text: str) -> List[str]:
        """Extract word tokens preserving original casing for homograph/toponym disambiguation."""
        return re.findall(r"\b[^\W\d_]+(?:'[^\W\d_]+)?\b", text, re.UNICODE)

    def _empty_result(self) -> Dict[str, float]:
        res: Dict[str, float] = {}
        for pole in FOUNDATION_POLES:
            col = pole.replace(".", "_")
            res[f"{col}_density"] = 0.0
            res[f"{col}_count"] = 0
        for f in FOUNDATIONS:
            res[f"{f}_density"] = 0.0
        res["moral_density"] = 0.0
        res["moral_valence"] = 0.0
        res["matched_moral_tokens"] = 0
        return res

    def _score_stanza_de_it(self, text: str, lang: str) -> Tuple[int, int, Dict[str, int]]:
        """Score German or Italian text using Stanza `(lemma, upos)` disambiguation."""
        nlp = self._get_stanza_pipeline(lang)
        doc = nlp(text)
        lang_data = self._data.get(lang, {})
        lemma_upos_map = lang_data.get("lemma_upos", {})
        lemma_poles_map = lang_data.get("lemma_poles", {})

        counts = {p: 0 for p in FOUNDATION_POLES}
        matched_tokens = 0
        total_tokens = 0

        for sent in doc.sentences:
            for w in sent.words:
                if w.upos in ("PUNCT", "SYM", "NUM"):
                    continue
                total_tokens += 1
                lemma = (w.lemma or w.text).lower().strip()
                upos = w.upos or "NOUN"
                if upos == "PROPN":
                    continue

                poles: List[str] = []
                if lemma in lemma_upos_map:
                    if upos in lemma_upos_map[lemma]:
                        poles = lemma_upos_map[lemma][upos]
                    elif upos in ("NOUN", "VERB", "ADJ", "ADV") and lemma not in ("würde", "stato", "serie", "fine"):
                        poles = lemma_poles_map.get(lemma, [])
                elif lang == "de" and upos == "NOUN":
                    poles = self._match_de_compound_head(lemma)

                if poles:
                    matched_tokens += 1
                    for p in poles:
                        counts[p] += 1

        return total_tokens, matched_tokens, counts

    def _score_fast_lookup(self, text: str, language: str) -> Tuple[int, int, Dict[str, int]]:
        """Fast token + pre-compiled Stanza/Forni morphological lookup with casing disambiguation."""
        raw_tokens = self.tokenize_with_case(text)
        total_tokens = len(raw_tokens)
        counts = {p: 0 for p in FOUNDATION_POLES}
        matched_tokens = 0
        if total_tokens == 0 or not self._data:
            return 0, 0, counts

        if language.startswith("lld"):
            lld_data = self._data.get("lld", {})
            var_key = language if language in ("lld_gherd", "lld_badia", "lld_fascia") else "lld_gherd"
            var_lex = lld_data.get(var_key, {})
            surf_to_lemma = lld_data.get("surface_to_lemma", {})

            for idx, tok in enumerate(raw_tokens):
                low = tok.lower()
                # Strip apostrophe prefixes like "l'", "d'", "dl'", "un'"
                if "'" in low:
                    low = low.split("'")[-1]
                if len(low) <= 2:
                    continue

                # Toponym filter: skip capitalized "San", "Santa", "Sant" before a capitalized proper name
                if low in ("san", "santa", "sant") and tok[0].isupper():
                    if idx + 1 < total_tokens and raw_tokens[idx + 1][0].isupper():
                        continue

                # Auxiliary participle filter: "stat"/"stada"/"stai" is only NOUN when capitalized ("Stat") or preceded by article "l"/"dl"/"un"
                if low in ("stat", "stada", "stai", "states"):
                    prev_low = raw_tokens[idx - 1].lower() if idx > 0 else ""
                    if prev_low in LLD_AUX_BEFORE_STAT or not (tok[0].isupper() or prev_low in ("l", "dl", "tl", "un", "n", " chësc")):
                        continue

                lemma = low if low in var_lex else surf_to_lemma.get(low, low)
                poles = var_lex.get(lemma)
                if poles:
                    matched_tokens += 1
                    for p in poles:
                        counts[p] += 1

        else:
            lang_key = "it" if language == "it" else "de"
            lang_data = self._data.get(lang_key, {})
            surf_map = lang_data.get("surface_poles", {})
            lemma_map = lang_data.get("lemma_poles", {})

            for idx, tok in enumerate(raw_tokens):
                low = tok.lower()
                if "'" in low:
                    low = low.split("'")[-1]
                if len(low) <= 2:
                    continue

                # Homograph disambiguation using casing & local context
                if lang_key == "de" and low == "würde":
                    # Only match noun "Würde" (capitalized mid-sentence), not subjunctive auxiliary "würde"
                    if not (tok[0].isupper() and idx > 0):
                        continue
                if lang_key == "it" and low in ("stato", "stati"):
                    # In Italian news, "Stato"/"Stati" (the State) is capitalized or preceded by "lo"/"dello"/"allo"/"uno"/"gli"/"degli"
                    prev_low = raw_tokens[idx - 1].lower() if idx > 0 else ""
                    if not (tok[0].isupper() or prev_low in ("lo", "dello", "allo", "nello", "uno", "gli", "degli", "agli", "negli", "questo")):
                        continue

                poles = surf_map.get(low) or lemma_map.get(low)
                if not poles and lang_key == "de" and tok[0].isupper():
                    poles = self._match_de_compound_head(low)

                if poles:
                    matched_tokens += 1
                    for p in poles:
                        counts[p] += 1

        return total_tokens, matched_tokens, counts

    def analyze(self, text: str, language: str = "de", use_stanza: Optional[bool] = None) -> Dict[str, float]:
        """
        Score text across the 5 Moral Foundations (10 virtue/vice poles).
        Normalizes densities per 1,000 words.
        """
        if not text or not self._data:
            return self._empty_result()

        run_stanza = self.use_stanza if use_stanza is None else use_stanza
        if run_stanza and language in ("de", "it"):
            total_tokens, matched_tokens, counts = self._score_stanza_de_it(text, language)
        else:
            total_tokens, matched_tokens, counts = self._score_fast_lookup(text, language)

        if total_tokens == 0:
            return self._empty_result()

        scale = 1000.0 / total_tokens
        res: Dict[str, float] = {}
        total_virtues = 0
        total_vices = 0

        for pole in FOUNDATION_POLES:
            col = pole.replace(".", "_")
            c = counts[pole]
            res[f"{col}_density"] = round(c * scale, 3)
            res[f"{col}_count"] = c
            if pole.endswith(".virtue"):
                total_virtues += c
            else:
                total_vices += c

        for f in FOUNDATIONS:
            f_count = counts[f"{f}.virtue"] + counts[f"{f}.vice"]
            res[f"{f}_density"] = round(f_count * scale, 3)

        total_moral = total_virtues + total_vices
        res["moral_density"] = round(matched_tokens * scale, 3)
        res["moral_valence"] = round((total_virtues - total_vices) / total_moral, 3) if total_moral > 0 else 0.0
        res["matched_moral_tokens"] = matched_tokens
        return res

