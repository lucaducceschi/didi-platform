"""
Direct Quotes Detection Engine for the DIDI Platform.

Detects direct speech quotes in journalistic and official press texts
using language-specific quotation marks (German and Italian):
- German: „…“, »…«, "…", ‚…‘
- Italian: «…», “…”, „…“, "…"

Discards scare quotes and short citations (<= 2 words with no verb)
to isolate actual spoken discourse from ironical citations or titles.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Set, Tuple

from src.languages import LANGUAGES, get_language

RULE_VERSION = "quote_rules_v2"  # v2: Italian “…” and „…“

# Closers allowed for specific openers
_CLOSER_ALIASES: Dict[str, Set[str]] = {
    "„": {"“", "”"},       # German low double quote closed by high double quotes
    "»": {"«"},            # German guillemets / chevrons (point inward)
    "«": {"»"},            # Italian caporali (point outward)
    '"': {'"'},            # ASCII straight double quote
    "‚": {"‘", "’"},       # German low single quote closed by high single quotes
    "'": {"'"},            # ASCII straight single quote
    "“": {"”", "“"},       # English/typographical curly double quote
}

# Verbs and auxiliaries UPOS tags
VERB_UPOS = {"VERB", "AUX"}


@dataclass(frozen=True)
class QuoteSpan:
    start_char: int
    end_char: int
    text: str
    quote_type: str = "direct_speech"
    rule_version: str = RULE_VERSION

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def get_language_quote_marks(language: str = "de") -> List[Tuple[str, str]]:
    """Retrieve configured quotation mark pairs for a language."""
    lang_def = LANGUAGES.get(language)
    if lang_def and lang_def.quotation_marks:
        return lang_def.quotation_marks
    if language == "it":
        return [("«", "»"), ('"', '"')]
    return [("„", "“"), ("»", "«"), ('"', '"'), ("‚", "‘")]


def _extract_candidate_spans(text: str, language: str = "de") -> List[Tuple[int, int, str]]:
    """
    Scan text and find candidate quote character spans [start_char, end_char].
    Handles paired marks, straight marks, nesting, and cross-paragraph quotes.
    Returns list of (start_char, end_char, opener).
    """
    pairs = get_language_quote_marks(language)
    
    # Map opener to set of valid closers
    openers: Dict[str, Set[str]] = {}
    for op, cl in pairs:
        openers[op] = set(_CLOSER_ALIASES.get(op, {cl}))

    # Set of all closer characters
    all_closers: Set[str] = set()
    for cl_set in openers.values():
        all_closers.update(cl_set)

    candidates: List[Tuple[int, int, str]] = []
    stack: List[Tuple[str, int]] = []

    i = 0
    n = len(text)

    while i < n:
        ch = text[i]

        # Check if current character matches top of stack as a closer
        if stack:
            top_op, top_pos = stack[-1]
            valid_closers = openers.get(top_op, set())

            if ch in valid_closers:
                # Matched closer!
                if top_op == ch:
                    # Symmetrical quote (e.g. '"')
                    # Make sure it's not a zero-length quote right at the start
                    if i > top_pos:
                        stack.pop()
                        candidates.append((top_pos, i + 1, top_op))
                        i += 1
                        continue
                else:
                    # Paired closer (e.g. '“' closing '„', or '»' closing '«')
                    stack.pop()
                    candidates.append((top_pos, i + 1, top_op))
                    i += 1
                    continue

        # Check if current char is an opener
        if ch in openers:
            # If it's a symmetrical quote already at top of stack, it was handled above
            stack.append((ch, i))
            i += 1
            continue

        # Handle unmatched closer: check if it closes an opener deeper in stack
        if stack and ch in all_closers:
            # Look backwards in stack
            matched_idx = -1
            for s_idx in range(len(stack) - 1, -1, -1):
                s_op, _ = stack[s_idx]
                if ch in openers.get(s_op, set()):
                    matched_idx = s_idx
                    break
            if matched_idx >= 0:
                top_op, top_pos = stack[matched_idx]
                # Drop unclosed inner openers
                stack = stack[:matched_idx]
                candidates.append((top_pos, i + 1, top_op))
                i += 1
                continue

        i += 1

    # Any unclosed marks in stack are dropped as unbalanced marks
    return candidates


def _is_direct_speech(
    span_text: str,
    span_tokens: Optional[List[Dict[str, Any]]] = None,
) -> bool:
    """
    Determine whether a candidate quote span represents direct speech or a scare quote / title.
    Rule:
    - Exclude quotes with <= 2 words and no verb.
    - Quotes with >= 3 words are retained (including headline quotes and complete utterances).
    - Quotes with 1-2 words are retained ONLY if they contain a finite verb or auxiliary.
    """
    inner_text = span_text.strip("„“”»«\"'‚‘ \t\n\r")
    if not inner_text:
        return False

    if span_tokens is not None:
        words = [t for t in span_tokens if t.get("upos") != "PUNCT"]
        n_words = len(words)
        if n_words == 0:
            return False
        has_verb = any(t.get("upos") in VERB_UPOS for t in words)
        if n_words <= 2 and not has_verb:
            return False
        return True

    # Fallback when token annotations are not provided (word splitting)
    words = re.findall(r"\b\w+\b", inner_text)
    n_words = len(words)
    if n_words == 0:
        return False
    if n_words <= 2:
        # Heuristic check for common short verbs in de and it
        short_verbs = {
            "ist", "war", "hat", "wird", "kann", "muss", "soll", "geht", "halt", "sei",
            "è", "ha", "fu", "va", "può", "deve", "dice", "fate", "stop", "basta"
        }
        if not any(w.lower() in short_verbs for w in words):
            return False
    return True


def detect_direct_quotes(
    text: str,
    language: str = "de",
    tokens: Optional[List[Dict[str, Any]]] = None,
) -> List[QuoteSpan]:
    """
    Detect all direct speech quotes in text according to language quotation marks.
    Returns QuoteSpan objects with 0-based character offsets [start_char:end_char].
    """
    if not text:
        return []

    raw_spans = _extract_candidate_spans(text, language=language)
    if not raw_spans:
        return []

    # Sort spans by start_char ASC, end_char DESC
    raw_spans.sort(key=lambda s: (s[0], -s[1]))

    results: List[QuoteSpan] = []

    for start_char, end_char, opener in raw_spans:
        span_str = text[start_char:end_char]

        # Extract tokens falling into this span
        span_tokens = None
        if tokens is not None:
            span_tokens = [
                t for t in tokens
                if t.get("start_char", 0) >= start_char and t.get("end_char", 0) <= end_char
            ]

        if _is_direct_speech(span_str, span_tokens):
            results.append(
                QuoteSpan(
                    start_char=start_char,
                    end_char=end_char,
                    text=span_str,
                    quote_type="direct_speech",
                    rule_version=RULE_VERSION,
                )
            )

    return results


def split_tokens_by_quotes(
    tokens: List[Dict[str, Any]],
    quote_spans: List[Tuple[int, int]],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Partition token list into inside-quotes tokens and outside-quotes tokens.
    Guarantees that inside_tokens + outside_tokens == tokens.
    """
    if not quote_spans:
        return [], list(tokens)

    inside: List[Dict[str, Any]] = []
    outside: List[Dict[str, Any]] = []

    for t in tokens:
        t_start = t.get("start_char", 0)
        t_end = t.get("end_char", 0)

        # Check if token falls inside any quote span
        is_inside = any(
            max(t_start, qs) < min(t_end, qe)
            for qs, qe in quote_spans
        )

        if is_inside:
            inside.append(t)
        else:
            outside.append(t)

    return inside, outside

