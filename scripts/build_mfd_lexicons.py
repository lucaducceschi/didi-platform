#!/usr/bin/env python3
"""
Builds unified Stanza-lemmatized Moral Foundations Dictionaries (MFD) for:
  - German (`de`): Husson & Palma (2025) GE ∪ Simonsen & Widmann (2023) mMPD_de
  - Italian (`it`): Husson & Palma (2025) IT ∪ Rizzoli et al. (2026) it-MFD
  - Ladin (`lld_gherd`, `lld_badia`, `lld_fascia`):
      1. Triangulation (`IT ∩ DE`) across `dls_dictionary.db` (Dicziunari dl Ladin Standard)
      2. Validated legal/civic concepts from `bistro.jsonl` (Eurac BISTRO)
      3. Inflectional surface-to-lemma lookup tables from `ladin_dictionary.db` (Forni, 337k forms)
         and `apertium-lld.lld.dix` for pre-Stanza Ladin morphological normalization.

Outputs `assets/mfd_compiled_lemmas.json`.
"""

import csv
import html
import json
import re
import sqlite3
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Set, Tuple

import stanza
import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ASSETS_DIR = PROJECT_ROOT / "assets"
DLS_DB_PATH = Path.home() / "Gits" / "digi-rlf" / "text_corpus" / "dictionary_scraper" / "dls_dictionary.db"
FORNI_DB_PATH = Path.home() / "Gits" / "digi-rlf" / "text_corpus" / "dictionary_scraper" / "ladin_dictionary.db"
APERTIUM_DIX_PATH = Path.home() / "Gits" / "digi-rlf" / "vendor" / "apertium-lld" / "apertium-lld.lld.dix"
BISTRO_PATH = Path.home() / "Desktop" / "BISTRO" / "bistro" / "bistro.jsonl"
OUTPUT_PATH = ASSETS_DIR / "mfd_compiled_lemmas.json"

FOUNDATION_POLES = [
    "care.virtue", "care.vice",
    "fairness.virtue", "fairness.vice",
    "loyalty.virtue", "loyalty.vice",
    "authority.virtue", "authority.vice",
    "sanctity.virtue", "sanctity.vice",
]

# Known MFD 1.0 stem-expansion and translation artifacts to exclude
DE_STOP_LEMMAS = {
    "bleiben", "bleibt", "gemeinde", "gemeinden", "angeklagte", "angeklagten",
    "angeklagter", "verbriefung", "motherboard", "sein", "haben", "werden",
    "der", "die", "das", "ein", "eine", "und", "oder", "aber", "von", "zu", "mit",
}
IT_STOP_LEMMAS = {
    "dei", "degli", "delle", "del", "dello", "della", "dal", "dalla", "da", "di",
    "in", "su", "per", "con", "tra", "fra", "il", "lo", "la", "i", "gli", "le",
    "un", "uno", "una", "essere", "avere", "imputato", "imputati", "imputata",
    "cartolarizzazione", "motherboard", "fare", "dire", "potere", "volere",
}
LLD_STOP_LEMMAS = {
    "nia", "nëus", "iö", "ie", "tu", "ël", "ëila", "ëra", "chësc", "chël",
    "ëster", "ester", "avëi", "avei", "de", "da", "te", "tl", "tla", "ti", "tles",
    "sun", "su", "per", "cun", "con", "y", "e", "o", "ma", "che", "co", "plu",
    "sciche", "sciöche", "nce", "inca", "bën", "ben", "bel", "bela", "bon", "bona",
}

CONTENT_UPOS = {"NOUN", "VERB", "ADJ", "ADV"}


def parse_husson_palma(rmd_path: Path) -> Dict[str, Dict[str, Set[str]]]:
    """Parse Husson & Palma (2025) Rmd dictionary for GE and IT."""
    text = rmd_path.read_text(encoding="utf-8")
    out: Dict[str, Dict[str, Set[str]]] = {
        "de": defaultdict(set),
        "it": defaultdict(set),
    }
    lang_map = {"GE": "de", "IT": "it"}
    cat_map = {
        "Care": "care.virtue",
        "Harm": "care.vice",
        "Fairness": "fairness.virtue",
        "Cheating": "fairness.vice",
        "Loyalty": "loyalty.virtue",
        "Betrayal": "loyalty.vice",
        "Authority": "authority.virtue",
        "Subversion": "authority.vice",
        "Sanctity": "sanctity.virtue",
        "Degradation": "sanctity.vice",
    }
    pattern = re.compile(
        r"\b(Care|Harm|Fairness|Cheating|Loyalty|Betrayal|Authority|Subversion|Sanctity|Degradation)_(GE|IT)\s*<-\s*c\((.*?)\)",
        re.S,
    )
    for m in pattern.finditer(text):
        pole = cat_map[m.group(1)]
        lang_code = lang_map[m.group(2)]
        words = re.findall(r'"([^"]+)"', m.group(3))
        for w in words:
            w_clean = re.sub(r"^(l'|un')", "", w.strip().lower()).strip()
            if w_clean and " " not in w_clean and len(w_clean) > 2:
                out[lang_code][pole].add(w_clean)
    return out


def parse_mmpd_de(yml_path: Path) -> Dict[str, Set[str]]:
    """Parse Simonsen & Widmann (2023) mMPD_de.yml into 10 poles."""
    data = yaml.safe_load(yml_path.read_text(encoding="utf-8"))
    out: Dict[str, Set[str]] = defaultdict(set)
    if "mMPD_de" in data:
        data = data["mMPD_de"]
    elif "dictionary" in data:
        data = data["dictionary"]
    key_map = {
        "care": "care.virtue",
        "harm": "care.vice",
        "fairness": "fairness.virtue",
        "cheating": "fairness.vice",
        "loyalty": "loyalty.virtue",
        "betrayal": "loyalty.vice",
        "authority": "authority.virtue",
        "subversion": "authority.vice",
        "sanctity": "sanctity.virtue",
        "degradation": "sanctity.vice",
    }
    for k, words in data.items():
        pole = key_map.get(k.lower().strip())
        if not pole or not isinstance(words, list):
            continue
        for w in words:
            w_clean = str(w).strip().lower()
            if w_clean and " " not in w_clean and len(w_clean) > 2:
                out[pole].add(w_clean)
    return out


def parse_it_mfd(dicx_path: Path) -> Dict[str, Set[str]]:
    """Parse Rizzoli et al. (2026) it-MFD.dicx (CSV with Entry and 10 Italian pole columns)."""
    out: Dict[str, Set[str]] = defaultdict(set)
    col_map = {
        "cura.pro": "care.virtue",
        "cura.contro": "care.vice",
        "correttezza.pro": "fairness.virtue",
        "correttezza.contro": "fairness.vice",
        "lealta.pro": "loyalty.virtue",
        "lealta.contro": "loyalty.vice",
        "autorita.pro": "authority.virtue",
        "autorita.contro": "authority.vice",
        "santita.pro": "sanctity.virtue",
        "santita.contro": "sanctity.vice",
    }
    with open(dicx_path, "r", encoding="utf-8", errors="ignore") as f:
        reader = csv.DictReader(f)
        for row in reader:
            raw_term = (row.get("Entry") or row.get("DicTerm") or "").strip().lower()
            if not raw_term or " " in raw_term:
                continue
            # Expand slash variants like "adulteri/e" and wildcard stems like "adulter*"
            candidates: List[str] = []
            if "/" in raw_term:
                base, suf = raw_term.split("/", 1)
                candidates.append(base)
                if len(base) > len(suf):
                    candidates.append(base[: -len(suf)] + suf)
            elif raw_term.endswith("*"):
                stem = raw_term[:-1]
                if len(stem) >= 4:
                    for suf in ("o", "a", "i", "e", "are", "ire", "ato", "ata", "ito", "ita"):
                        candidates.append(stem + suf)
            else:
                candidates.append(raw_term)

            for term in candidates:
                if len(term) <= 2:
                    continue
                for col, pole in col_map.items():
                    if (row.get(col) or "").strip() == "1":
                        out[pole].add(term)
    return out


def lemmatize_terms_stanza(terms: Set[str], lang: str) -> Dict[str, Tuple[str, str]]:
    """Run Stanza on a batch of single-word terms and return surface -> (lemma, upos)."""
    nlp = stanza.Pipeline(lang=lang, processors="tokenize,mwt,pos,lemma", tokenize_no_ssplit=True, verbose=False)
    sorted_terms = sorted(terms)
    mapping: Dict[str, Tuple[str, str]] = {}
    batch_size = 500
    for i in range(0, len(sorted_terms), batch_size):
        chunk = sorted_terms[i : i + batch_size]
        # Join with newline so each word is tokenized cleanly
        doc = nlp("\n".join(chunk))
        all_words = [w for s in doc.sentences for w in s.words]
        # Align by matching word text or fallback per-item if MWT split occurred
        if len(all_words) == len(chunk):
            for surf, w in zip(chunk, all_words):
                lemma = (w.lemma or surf).lower().strip()
                upos = w.upos or "NOUN"
                if upos in ("PROPN", "X"):
                    upos = "NOUN"
                mapping[surf] = (lemma, upos)
        else:
            # Word-by-word fallback for chunks with MWT expansion (e.g. "dei" -> "di" + "il")
            for surf in chunk:
                d_single = nlp(surf)
                words = [w for s in d_single.sentences for w in s.words]
                if len(words) == 1:
                    w = words[0]
                    lemma = (w.lemma or surf).lower().strip()
                    upos = w.upos or "NOUN"
                    if upos in ("PROPN", "X"):
                        upos = "NOUN"
                    mapping[surf] = (lemma, upos)
                else:
                    # Multi-word token expansion (e.g., articulated preposition like "dei", "degli") -> ADP
                    mapping[surf] = (surf, "ADP")
    return mapping


def clean_gloss_words(gloss: str) -> List[str]:
    """Extract clean single-word equivalents from a DLS dictionary gloss."""
    if not gloss:
        return []
    txt = html.unescape(gloss)
    # Remove parenthetical explanations, grammar markers, domain markers
    txt = re.sub(r"\([^)]*\)", " ", txt)
    txt = re.sub(r"\[[^\]]*\]", " ", txt)
    txt = re.sub(r"\b(s\.m\.|s\.f\.|agg\.|v\.tr\.|v\.intr\.|avv\.|pl\.|fig\.|fam\.|jur\.|rel\.)\b", " ", txt, flags=re.I)
    parts = re.split(r"[;,/]", txt)
    words = []
    for p in parts:
        p_clean = p.strip().lower()
        # Strip leading articles/reflexive pronouns
        p_clean = re.sub(r"^(il|lo|la|i|gli|le|un|una|der|die|das|ein|eine|sich|zu)\s+", "", p_clean).strip()
        p_clean = p_clean.strip(" .!?\"'«»‡*")
        if p_clean and re.match(r"^[^\W\d_]+(?:-[^\W\d_]+)?$", p_clean, re.UNICODE) and len(p_clean) > 2:
            words.append(p_clean)
    return words


def build_ladin_projection(
    it_lemma_to_poles: Dict[str, Set[str]],
    de_lemma_to_poles: Dict[str, Set[str]],
    it_surface_to_poles: Dict[str, Set[str]],
    de_surface_to_poles: Dict[str, Set[str]],
) -> Dict[str, Dict[str, Set[str]]]:
    """
    Triangulate Ladin MFD lemmas across `lld_gherd`, `lld_badia`, `lld_fascia` using:
      1. `dls_dictionary.db` where IT and DE glosses agree on the same moral foundation (or strong single-word gloss)
      2. `bistro.jsonl` validated legal/civic concepts
    """
    ladin_poles: Dict[str, Dict[str, Set[str]]] = {
        "lld_gherd": defaultdict(set),
        "lld_badia": defaultdict(set),
        "lld_fascia": defaultdict(set),
    }

    def get_it_poles(w: str) -> Set[str]:
        return it_lemma_to_poles.get(w, set()) | it_surface_to_poles.get(w, set())

    def get_de_poles(w: str) -> Set[str]:
        return de_lemma_to_poles.get(w, set()) | de_surface_to_poles.get(w, set())

    def clean_ladin_headword(hw: str) -> List[str]:
        hw = re.sub(r"‡", "", hw or "")
        hw = re.sub(r"\([^)]*\)", "", hw)
        # Split gender suffixes like "bon, -a" -> base "bon"
        base = hw.split(",")[0].strip().lower()
        base = re.sub(r"^(se|s')\s+", "", base).strip()
        if re.match(r"^[^\W\d_]+$", base, re.UNICODE) and len(base) > 2 and base not in LLD_STOP_LEMMAS:
            return [base]
        return []

    if DLS_DB_PATH.exists():
        conn = sqlite3.connect(DLS_DB_PATH)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        # Preload dialect varieties: lemma_id -> dialect -> list of forms
        cur.execute("SELECT lemma_id, dialect, spelling_form FROM varieties WHERE dialect IN ('gherdëina', 'badiot', 'fascian')")
        var_map: Dict[int, Dict[str, List[str]]] = defaultdict(lambda: defaultdict(list))
        for r in cur.fetchall():
            for w in clean_ladin_headword(r["spelling_form"]):
                var_map[r["lemma_id"]][r["dialect"]].append(w)

        cur.execute("SELECT id, lemma, pos, translation_it, translation_de FROM lemmas WHERE id > 1")
        for r in cur.fetchall():
            pos = (r["pos"] or "").lower()
            if any(p in pos for p in ["prep", "cong", "pron", "art", "inter"]):
                continue
            it_words = clean_gloss_words(r["translation_it"] or "")
            de_words = clean_gloss_words(r["translation_de"] or "")
            if not it_words or not de_words:
                continue

            it_p: Set[str] = set()
            for w in it_words:
                it_p |= get_it_poles(w)
            de_p: Set[str] = set()
            for w in de_words:
                de_p |= get_de_poles(w)

            # Strict intersection on foundation pole (or same foundation dimension)
            shared_poles = it_p & de_p
            if not shared_poles:
                # Check if they agree on foundation family + polarity when one gloss has 1 single-word translation
                continue

            lid = r["id"]
            std_words = clean_ladin_headword(r["lemma"] or "")
            gherd_words = var_map[lid].get("gherdëina") or std_words
            badia_words = var_map[lid].get("badiot") or std_words
            fascia_words = var_map[lid].get("fascian") or std_words

            for pole in shared_poles:
                for w in gherd_words:
                    ladin_poles["lld_gherd"][pole].add(w)
                for w in badia_words:
                    ladin_poles["lld_badia"][pole].add(w)
                for w in fascia_words:
                    ladin_poles["lld_fascia"][pole].add(w)
        conn.close()

    # 2. Enrich with BISTRO validated legal/civic concepts
    if BISTRO_PATH.exists():
        with open(BISTRO_PATH, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    entry = json.loads(line)
                except Exception:
                    continue
                lang_obj = entry.get("language", {})
                if "Ladin" not in lang_obj:
                    continue

                it_terms = list(lang_obj.get("IT", {}).get("terms", {}).keys())
                de_terms = []
                for reg_dict in lang_obj.get("DE", {}).get("sprachgebrauch", {}).values():
                    if isinstance(reg_dict, dict):
                        de_terms.extend(reg_dict.keys())
                de_terms.extend(lang_obj.get("DE", {}).get("terms", {}).keys())

                it_p = set()
                for t in it_terms:
                    t_low = t.strip().lower()
                    if " " not in t_low:
                        it_p |= get_it_poles(t_low)
                de_p = set()
                for t in de_terms:
                    t_low = t.strip().lower()
                    if " " not in t_low:
                        de_p |= get_de_poles(t_low)
                shared = it_p & de_p
                if not shared:
                    continue

                lad_ador = lang_obj.get("Ladin", {}).get("adoranza_linguistica", {})
                for v_type, t_dict in lad_ador.items():
                    if not isinstance(t_dict, dict):
                        continue
                    for t_raw in t_dict.keys():
                        for w in clean_ladin_headword(t_raw):
                            for pole in shared:
                                if "Gherdëina" in v_type:
                                    ladin_poles["lld_gherd"][pole].add(w)
                                if "Val Badia" in v_type:
                                    ladin_poles["lld_badia"][pole].add(w)
                                if "Fascia" in v_type:
                                    ladin_poles["lld_fascia"][pole].add(w)
                                if not any(x in v_type for x in ("Gherdëina", "Val Badia", "Fascia")):
                                    ladin_poles["lld_gherd"][pole].add(w)
                                    ladin_poles["lld_badia"][pole].add(w)
                                    ladin_poles["lld_fascia"][pole].add(w)

    return ladin_poles


def build_ladin_inflection_map(target_lemmas: Set[str]) -> Dict[str, str]:
    """
    Build surface_form -> lemma lookup table for Ladin MFD lemmas from:
      1. `ladin_dictionary.db` (Forni Gherdëina inflections, 337,532 forms)
      2. `apertium-lld.lld.dix`
    """
    surface_to_lemma: Dict[str, str] = {}
    if FORNI_DB_PATH.exists():
        conn = sqlite3.connect(FORNI_DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT id, lemma FROM lemmas")
        id_to_lemma: Dict[int, str] = {}
        for lid, l_raw in cur.fetchall():
            l_clean = (l_raw or "").split(",")[0].strip().lower()
            if l_clean in target_lemmas and l_clean not in LLD_STOP_LEMMAS:
                id_to_lemma[lid] = l_clean
        if id_to_lemma:
            placeholders = ",".join("?" for _ in id_to_lemma)
            cur.execute(
                f"SELECT lemma_id, inflected_form FROM inflections WHERE lemma_id IN ({placeholders})",
                list(id_to_lemma.keys()),
            )
            for lid, form in cur.fetchall():
                f_clean = (form or "").strip().lower()
                if f_clean and len(f_clean) > 2 and " " not in f_clean and f_clean not in LLD_STOP_LEMMAS:
                    surface_to_lemma[f_clean] = id_to_lemma[lid]
        conn.close()

    # Also add regular Ladin plural/participle suffixes (-s, -es, -i, -eda, -edes, -à, -ei, -on, -un)
    # and parse Apertium dix if available
    if APERTIUM_DIX_PATH.exists():
        try:
            tree = ET.parse(APERTIUM_DIX_PATH)
            root = tree.getroot()
            for e in root.iter("e"):
                lm = (e.attrib.get("lm") or "").strip().lower()
                if lm in target_lemmas and lm not in LLD_STOP_LEMMAS:
                    for p in e.iter("p"):
                        l_node = p.find("l")
                        if l_node is not None and l_node.text:
                            stem = l_node.text.strip().lower()
                            if len(stem) >= 3:
                                for suf in ("", "s", "es", "i", "a", "eda", "edes", "on", "un"):
                                    cand = stem + suf
                                    if len(cand) > 2 and cand not in LLD_STOP_LEMMAS:
                                        surface_to_lemma.setdefault(cand, lm)
        except Exception:
            pass

    return surface_to_lemma


def main():
    print("1. Parsing raw MFD dictionaries...")
    hp = parse_husson_palma(ASSETS_DIR / "MFD_Fr_Ge_Sp_It.Rmd")
    mmpd_de = parse_mmpd_de(ASSETS_DIR / "mMPD_de.yml")
    it_mfd = parse_it_mfd(ASSETS_DIR / "it-MFD.dicx")

    raw_de: Dict[str, Set[str]] = defaultdict(set)
    raw_it: Dict[str, Set[str]] = defaultdict(set)
    for pole in FOUNDATION_POLES:
        raw_de[pole] = (hp["de"][pole] | mmpd_de[pole]) - DE_STOP_LEMMAS
        raw_it[pole] = (hp["it"][pole] | it_mfd[pole]) - IT_STOP_LEMMAS

    # Polarity fix for harmlos / innocuo (must only be care.virtue, not care.vice)
    raw_de["care.vice"].discard("harmlos")
    raw_de["care.vice"].discard("harmlose")
    raw_de["care.vice"].discard("harmlosen")
    raw_de["care.virtue"].add("harmlos")
    raw_it["care.vice"].discard("innocuo")
    raw_it["care.vice"].discard("innocua")
    raw_it["care.vice"].discard("innocui")
    raw_it["care.virtue"].add("innocuo")

    all_de_terms = set().union(*raw_de.values())
    all_it_terms = set().union(*raw_it.values())
    print(f"   Unique raw DE surface terms: {len(all_de_terms):,}")
    print(f"   Unique raw IT surface terms: {len(all_it_terms):,}")

    print("2. Lemmatizing DE and IT terms with Stanza (tokenize,mwt,pos,lemma)...")
    de_stanza_map = lemmatize_terms_stanza(all_de_terms, "de")
    it_stanza_map = lemmatize_terms_stanza(all_it_terms, "it")

    # Build cleaned (lemma, upos) -> poles and lemma -> poles
    de_lemma_upos: Dict[str, Dict[str, List[str]]] = defaultdict(lambda: defaultdict(list))
    it_lemma_upos: Dict[str, Dict[str, List[str]]] = defaultdict(lambda: defaultdict(list))
    de_lemma_to_poles: Dict[str, Set[str]] = defaultdict(set)
    it_lemma_to_poles: Dict[str, Set[str]] = defaultdict(set)
    de_surface_to_poles: Dict[str, Set[str]] = defaultdict(set)
    it_surface_to_poles: Dict[str, Set[str]] = defaultdict(set)

    for pole in FOUNDATION_POLES:
        for surf in sorted(raw_de[pole]):
            lemma, upos = de_stanza_map.get(surf, (surf, "NOUN"))
            if lemma in DE_STOP_LEMMAS or upos not in CONTENT_UPOS:
                continue
            # Disambiguate homographs: "würde" is only valid as NOUN (Würde = dignity), never AUX/VERB
            if surf == "würde" or lemma == "würde":
                lemma, upos = "würde", "NOUN"
            if pole not in de_lemma_upos[lemma][upos]:
                de_lemma_upos[lemma][upos].append(pole)
            de_lemma_to_poles[lemma].add(pole)
            de_surface_to_poles[surf].add(pole)

        for surf in sorted(raw_it[pole]):
            lemma, upos = it_stanza_map.get(surf, (surf, "NOUN"))
            if lemma in IT_STOP_LEMMAS or surf in IT_STOP_LEMMAS or upos not in CONTENT_UPOS:
                continue
            # Disambiguate Italian homographs:
            # - "stato"/"stati" only as NOUN (state), never AUX/VERB (participle of essere)
            if surf in ("stato", "stati") or lemma == "stato":
                if pole in ("authority.virtue", "loyalty.virtue"):
                    lemma, upos = "stato", "NOUN"
                else:
                    continue
            # - "serie" -> only adjective "serio" (ADJ), never noun "serie" (TV/math series)
            if surf == "serie" or lemma == "serie":
                lemma, upos = "serio", "ADJ"
            # - "fine" -> only adjective "fine" (ADJ), exclude noun "fine" (end) in loyalty/care
            if surf == "fine" and upos == "NOUN" and pole in ("loyalty.virtue", "care.virtue"):
                upos = "ADJ"
            if pole not in it_lemma_upos[lemma][upos]:
                it_lemma_upos[lemma][upos].append(pole)
            it_lemma_to_poles[lemma].add(pole)
            it_surface_to_poles[surf].add(pole)

    print(f"   Cleaned DE Stanza lemmas: {len(de_lemma_upos):,}")
    print(f"   Cleaned IT Stanza lemmas: {len(it_lemma_upos):,}")

    print("3. Projecting MFD to Ladin (lld_gherd, lld_badia, lld_fascia) via DLS (IT ∩ DE) + BISTRO...")
    ladin_poles = build_ladin_projection(
        it_lemma_to_poles, de_lemma_to_poles, it_surface_to_poles, de_surface_to_poles
    )
    all_lld_lemmas: Set[str] = set()
    lld_lemma_to_poles: Dict[str, Dict[str, List[str]]] = {
        "lld_gherd": defaultdict(list),
        "lld_badia": defaultdict(list),
        "lld_fascia": defaultdict(list),
    }
    for var in ("lld_gherd", "lld_badia", "lld_fascia"):
        for pole in FOUNDATION_POLES:
            for lemma in sorted(ladin_poles[var][pole]):
                if lemma in LLD_STOP_LEMMAS:
                    continue
                if pole not in lld_lemma_to_poles[var][lemma]:
                    lld_lemma_to_poles[var][lemma].append(pole)
                all_lld_lemmas.add(lemma)
        print(f"   {var}: {len(lld_lemma_to_poles[var]):,} triangulated MFD lemmas")

    print("4. Building Ladin inflection lookup table (Forni ladin_dictionary.db + Apertium)...")
    lld_surface_to_lemma = build_ladin_inflection_map(all_lld_lemmas)
    print(f"   Ladin inflected surface forms mapped to MFD lemmas: {len(lld_surface_to_lemma):,}")

    payload = {
        "metadata": {
            "description": "Unified Stanza-lemmatized Multilingual Moral Foundations Dictionary (DE, IT, LLD)",
            "foundations": FOUNDATION_POLES,
            "sources": [
                "Husson & Palma (2025) Multilingual MFD (GE, IT)",
                "Simonsen & Widmann (2023) mMPD (DE)",
                "Rizzoli et al. (2026) it-MFD (IT)",
                "DLS (Dicziunari dl Ladin Standard) + Eurac BISTRO + Forni Inflections (LLD)",
            ],
        },
        "de": {
            "lemma_upos": de_lemma_upos,
            "lemma_poles": {k: sorted(v) for k, v in de_lemma_to_poles.items()},
            "surface_poles": {k: sorted(v) for k, v in de_surface_to_poles.items()},
        },
        "it": {
            "lemma_upos": it_lemma_upos,
            "lemma_poles": {k: sorted(v) for k, v in it_lemma_to_poles.items()},
            "surface_poles": {k: sorted(v) for k, v in it_surface_to_poles.items()},
        },
        "lld": {
            "lld_gherd": dict(lld_lemma_to_poles["lld_gherd"]),
            "lld_badia": dict(lld_lemma_to_poles["lld_badia"]),
            "lld_fascia": dict(lld_lemma_to_poles["lld_fascia"]),
            "surface_to_lemma": lld_surface_to_lemma,
        },
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"5. Saved compiled lexicon to {OUTPUT_PATH} ({OUTPUT_PATH.stat().st_size / 1024:.1f} KB)")


if __name__ == "__main__":
    main()
