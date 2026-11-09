"""
Language Configuration & Registry for the DIDI Platform.

Defines per-language properties for active languages (German and Italian)
and deferred languages (Ladin varieties). All language-specific behavior
(labels, active scope, search synonyms, dictionaries, pronoun lists,
quotation marks, available measures, and word layer provenance) is centralized here.

Adding or re-enabling a language requires only updating or adding its definition here,
with zero application code changes.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple


@dataclass(frozen=True)
class LanguageDefinition:
    code: str
    label: str
    active: bool
    quotation_marks: List[Tuple[str, str]]
    ingroup_pronouns: List[str]
    available_measures: List[str]
    word_layer_source: Dict[str, Any]
    caution: Optional[str] = None
    search_synonyms: Dict[str, str] = field(default_factory=dict)


LANGUAGES: Dict[str, LanguageDefinition] = {
    "de": LanguageDefinition(
        code="de",
        label="German (de)",
        active=True,
        quotation_marks=[("„", "“"), ("»", "«"), ('"', '"'), ("‚", "‘")],
        ingroup_pronouns=[
            "wir", "uns", "unser", "unsere", "unserem", "unseren", "unserer", "unseres"
        ],
        available_measures=[
            "mfd", "nrc", "sentiment", "ingroup_pronouns", "konjunktiv_1", "keyness"
        ],
        word_layer_source={
            "engine": "Stanza",
            "model": "de",
            "processors": "tokenize,lemma,pos,ner,depparse",
            "storage": "didi_words.db",
        },
        caution=None,
        search_synonyms={
            "schule": "scuola* OR scuole* OR scolast* OR schule* OR schul* OR scola* OR bildung* OR istruzion*",
            "schulen": "scuola* OR scuole* OR scolast* OR schule* OR schul* OR scola* OR bildung* OR istruzion*",
            "bildung": "scuola* OR scuole* OR scolast* OR schule* OR schul* OR scola* OR bildung* OR istruzion*",
            "autonomie": "autonom* OR zuständig* OR competenz* OR cumpetënz* OR statut*",
            "statut": "autonom* OR zuständig* OR competenz* OR cumpetënz* OR statut*",
            "zuständigkeit": "autonom* OR zuständig* OR competenz* OR cumpetënz* OR statut*",
            "zuständigkeiten": "autonom* OR zuständig* OR competenz* OR cumpetënz* OR statut*",
            "wolf": "wolf* OR wölfe* OR lupo* OR lupi* OR bär* OR bären* OR orso* OR orsi* OR großraubwild* OR lfs* OR urs*",
            "wölfe": "wolf* OR wölfe* OR lupo* OR lupi* OR bär* OR bären* OR orso* OR orsi* OR großraubwild* OR lfs* OR urs*",
            "bär": "wolf* OR wölfe* OR lupo* OR lupi* OR bär* OR bären* OR orso* OR orsi* OR großraubwild* OR lfs* OR urs*",
            "bären": "wolf* OR wölfe* OR lupo* OR lupi* OR bär* OR bären* OR orso* OR orsi* OR großraubwild* OR lfs* OR urs*",
            "großraubwild": "wolf* OR wölfe* OR lupo* OR lupi* OR bär* OR bären* OR orso* OR orsi* OR großraubwild* OR lfs* OR urs*",
            "brenner": "brenner* OR brennero* OR transit* OR lueg* OR autobahn* OR autostrad*",
            "transit": "brenner* OR brennero* OR transit* OR lueg* OR autobahn* OR autostrad*",
            "lueg": "brenner* OR brennero* OR transit* OR lueg* OR autobahn* OR autostrad*",
            "koalition": "koalition* OR coalizion* OR regierung* OR giunta* OR jonta* OR kompatscher*",
            "landesregierung": "koalition* OR coalizion* OR regierung* OR giunta* OR jonta* OR kompatscher*",
            "kompatscher": "kompatscher* OR svp*",
            "svp": "svp* OR volkspartei*",
            "minderheit": "minderheit* OR minoranz* OR minorit* OR proporz* OR sprachgrupp* OR censiment*",
            "minderheiten": "minderheit* OR minoranz* OR minorit* OR proporz* OR sprachgrupp* OR censiment*",
            "proporz": "minderheit* OR minoranz* OR minorit* OR proporz* OR sprachgrupp* OR censiment*",
            "sprachgruppe": "minderheit* OR minoranz* OR minorit* OR proporz* OR sprachgrupp* OR censiment*",
            "zweisprachigkeit": "zweisprachig* OR bilingu* OR muttersprach* OR madrelingu* OR lingaz*",
            "muttersprache": "zweisprachig* OR bilingu* OR muttersprach* OR madrelingu* OR lingaz*",
        },
    ),
    "it": LanguageDefinition(
        code="it",
        label="Italian (it)",
        active=True,
        quotation_marks=[("«", "»"), ('"', '"')],
        ingroup_pronouns=["noi", "ci", "nostro", "nostra", "nostri", "nostre"],
        available_measures=[
            "mfd", "nrc", "sentiment", "ingroup_pronouns", "keyness"
        ],
        word_layer_source={
            "engine": "Stanza",
            "model": "it",
            "processors": "tokenize,lemma,pos,ner,depparse",
            "storage": "pending_stage_2",
        },
        caution=None,
        search_synonyms={
            "scuola": "scuola* OR scuole* OR scolast* OR schule* OR schul* OR scola* OR bildung* OR istruzion*",
            "scuole": "scuola* OR scuole* OR scolast* OR schule* OR schul* OR scola* OR bildung* OR istruzion*",
            "scolastica": "scuola* OR scuole* OR scolast* OR schule* OR schul* OR scola* OR bildung* OR istruzion*",
            "scolastico": "scuola* OR scuole* OR scolast* OR schule* OR schul* OR scola* OR bildung* OR istruzion*",
            "istruzione": "scuola* OR scuole* OR scolast* OR schule* OR schul* OR scola* OR bildung* OR istruzion*",
            "autonomia": "autonom* OR zuständig* OR competenz* OR cumpetënz* OR statut*",
            "statuto": "autonom* OR zuständig* OR competenz* OR cumpetënz* OR statut*",
            "competenza": "autonom* OR zuständig* OR competenz* OR cumpetënz* OR statut*",
            "competenze": "autonom* OR zuständig* OR competenz* OR cumpetënz* OR statut*",
            "lupo": "wolf* OR wölfe* OR lupo* OR lupi* OR bär* OR bären* OR orso* OR orsi* OR großraubwild* OR lfs* OR urs*",
            "lupi": "wolf* OR wölfe* OR lupo* OR lupi* OR bär* OR bären* OR orso* OR orsi* OR großraubwild* OR lfs* OR urs*",
            "orso": "wolf* OR wölfe* OR lupo* OR lupi* OR bär* OR bären* OR orso* OR orsi* OR großraubwild* OR lfs* OR urs*",
            "orsi": "wolf* OR wölfe* OR lupo* OR lupi* OR bär* OR bären* OR orso* OR orsi* OR großraubwild* OR lfs* OR urs*",
            "brennero": "brenner* OR brennero* OR transit* OR lueg* OR autobahn* OR autostrad*",
            "transit": "brenner* OR brennero* OR transit* OR lueg* OR autobahn* OR autostrad*",
            "coalizione": "koalition* OR coalizion* OR regierung* OR giunta* OR jonta* OR kompatscher*",
            "giunta": "koalition* OR coalizion* OR regierung* OR giunta* OR jonta* OR kompatscher*",
            "minoranza": "minderheit* OR minoranz* OR minorit* OR proporz* OR sprachgrupp* OR censiment*",
            "minoranze": "minderheit* OR minoranz* OR minorit* OR proporz* OR sprachgrupp* OR censiment*",
            "proporz": "minderheit* OR minoranz* OR minorit* OR proporz* OR sprachgrupp* OR censiment*",
            "bilinguismo": "zweisprachig* OR bilingu* OR muttersprach* OR madrelingu* OR lingaz*",
            "madrelingua": "zweisprachig* OR bilingu* OR muttersprach* OR madrelingu* OR lingaz*",
        },
    ),
    "lld_gherd": LanguageDefinition(
        code="lld_gherd",
        label="Ladin Gherdëina (lld_gherd)",
        active=False,
        quotation_marks=[("«", "»"), ('"', '"')],
        ingroup_pronouns=["nos", "nost"],
        available_measures=[],
        word_layer_source={"engine": "deferred", "reason": "Ladin NLP pipeline pending"},
        caution="No Ladin speaker has reviewed the Ladin variety labels yet, so check them before comparing varieties.",
        search_synonyms={
            "scola": "scuola* OR scuole* OR scolast* OR schule* OR schul* OR scola* OR bildung* OR istruzion*",
            "scoles": "scuola* OR scuole* OR scolast* OR schule* OR schul* OR scola* OR bildung* OR istruzion*",
            "jonta": "koalition* OR coalizion* OR regierung* OR giunta* OR jonta* OR kompatscher*",
        },
    ),
    "lld_badia": LanguageDefinition(
        code="lld_badia",
        label="Ladin Val Badia (lld_badia)",
        active=False,
        quotation_marks=[("«", "»"), ('"', '"')],
        ingroup_pronouns=["nos", "nost"],
        available_measures=[],
        word_layer_source={"engine": "deferred", "reason": "Ladin NLP pipeline pending"},
        caution="No Ladin speaker has reviewed the Ladin variety labels yet, so check them before comparing varieties.",
        search_synonyms={
            "scola": "scuola* OR scuole* OR scolast* OR schule* OR schul* OR scola* OR bildung* OR istruzion*",
            "scoles": "scuola* OR scuole* OR scolast* OR schule* OR schul* OR scola* OR bildung* OR istruzion*",
            "jonta": "koalition* OR coalizion* OR regierung* OR giunta* OR jonta* OR kompatscher*",
        },
    ),
    "lld_fascia": LanguageDefinition(
        code="lld_fascia",
        label="Ladin Fascia (lld_fascia)",
        active=False,
        quotation_marks=[("«", "»"), ('"', '"')],
        ingroup_pronouns=["nos", "nost"],
        available_measures=[],
        word_layer_source={"engine": "deferred", "reason": "Ladin NLP pipeline pending"},
        caution="No Ladin speaker has reviewed the Ladin variety labels yet, so check them before comparing varieties.",
        search_synonyms={
            "scola": "scuola* OR scuole* OR scolast* OR schule* OR schul* OR scola* OR bildung* OR istruzion*",
            "scoles": "scuola* OR scuole* OR scolast* OR schule* OR schul* OR scola* OR bildung* OR istruzion*",
            "jonta": "koalition* OR coalizion* OR regierung* OR giunta* OR jonta* OR kompatscher*",
        },
    ),
}

# Mapping for backwards compatibility
LANGUAGE_LABELS: Dict[str, str] = {code: lang.label for code, lang in LANGUAGES.items()}


def get_language(code: str) -> Optional[LanguageDefinition]:
    """Retrieve language definition by code."""
    return LANGUAGES.get(code)


def is_language_active(code: str) -> bool:
    """Check if language is currently configured as active in the application."""
    lang = LANGUAGES.get(code)
    return bool(lang and lang.active)


def get_active_language_codes() -> Set[str]:
    """Return set of active language codes (currently {'de', 'it'})."""
    return {code for code, lang in LANGUAGES.items() if lang.active}


def get_all_language_codes() -> Set[str]:
    """Return set of all registered language codes including deferred varieties."""
    return set(LANGUAGES.keys())


def get_active_languages() -> List[LanguageDefinition]:
    """Return list of active LanguageDefinition objects."""
    return [lang for lang in LANGUAGES.values() if lang.active]


def get_language_label(code: str) -> str:
    """Return display label for a language code, with fallback to raw code."""
    lang = LANGUAGES.get(code)
    return lang.label if lang else code


def get_language_caution(code: str) -> Optional[str]:
    """Return caution note for a language if defined."""
    lang = LANGUAGES.get(code)
    return lang.caution if lang else None


def get_available_measures(code: str) -> List[str]:
    """Return list of available measure IDs for a language."""
    lang = LANGUAGES.get(code)
    return lang.available_measures if lang else []


def get_thesaurus(active_only: bool = False) -> Dict[str, str]:
    """Combine concept search synonyms across registered language definitions.
    
    If active_only is True, only active languages (de, it) are included.
    Otherwise all registered languages (including deferred Ladin varieties) are included.
    """
    thesaurus: Dict[str, str] = {}
    for lang in LANGUAGES.values():
        if not active_only or lang.active:
            thesaurus.update(lang.search_synonyms)
    return thesaurus


