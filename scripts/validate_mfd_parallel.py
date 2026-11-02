#!/usr/bin/env python3
"""
Parallel Corpus Validation for the Multilingual Moral Foundations Dictionary (DE, IT, LLD).
Implements Husson & Palma's (2025) cross-lingual validation protocol:
  - Pearson correlation (r) of moral density & foundation hits across aligned text pairs
  - Mean difference (Delta mu) per 1,000 words across languages

Evaluates on:
  1. Eurac BISTRO trilingual legal/administrative context sentences (`bistro.jsonl`)
  2. University of Innsbruck (`sfrontull/*`) Ladin-Italian parallel corpora from Hugging Face
"""

import json
import math
import sys
import urllib.request
from pathlib import Path
from typing import Dict, List, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.nlp.morality import MoralFoundationsAnalyzer

BISTRO_PATH = Path.home() / "Desktop" / "BISTRO" / "bistro" / "bistro.jsonl"
VAL_DIR = PROJECT_ROOT / "assets" / "parallel_validation"


def pearson_r(x: List[float], y: List[float]) -> float:
    n = len(x)
    if n < 3:
        return 0.0
    mx = sum(x) / n
    my = sum(y) / n
    num = sum((a - mx) * (b - my) for a, b in zip(x, y))
    den_x = math.sqrt(sum((a - mx) ** 2 for a in x))
    den_y = math.sqrt(sum((b - my) ** 2 for b in y))
    if den_x == 0 or den_y == 0:
        return 0.0
    return round(num / (den_x * den_y), 4)


def evaluate_pairs(
    analyzer: MoralFoundationsAnalyzer,
    pairs: List[Tuple[str, str]],
    lang_a: str,
    lang_b: str,
) -> Dict[str, float]:
    scores_a = []
    scores_b = []
    active_a = []
    active_b = []
    for txt_a, txt_b in pairs:
        ra = analyzer.analyze(txt_a, lang_a)
        rb = analyzer.analyze(txt_b, lang_b)
        da = ra["moral_density"]
        db = rb["moral_density"]
        scores_a.append(da)
        scores_b.append(db)
        if da > 0 or db > 0:
            active_a.append(da)
            active_b.append(db)

    n = len(pairs)
    mean_a = round(sum(scores_a) / n, 2) if n else 0.0
    mean_b = round(sum(scores_b) / n, 2) if n else 0.0
    return {
        "n_pairs": n,
        "n_active_pairs": len(active_a),
        f"mean_density_{lang_a}": mean_a,
        f"mean_density_{lang_b}": mean_b,
        "delta_mu": round(mean_a - mean_b, 2),
        "pearson_r_all": pearson_r(scores_a, scores_b),
        "pearson_r_active": pearson_r(active_a, active_b),
    }


def fetch_hf_rows(dataset: str, limit: int = 100) -> List[Dict]:
    """Fetch rows from Hugging Face Datasets Server API and cache locally in assets/parallel_validation/."""
    VAL_DIR.mkdir(parents=True, exist_ok=True)
    slug = dataset.replace("/", "__")
    cache_file = VAL_DIR / f"{slug}.json"
    if cache_file.exists():
        try:
            return json.loads(cache_file.read_text(encoding="utf-8"))
        except Exception:
            pass

    url = f"https://datasets-server.huggingface.co/rows?dataset={dataset}&config=default&split=train&offset=0&length={limit}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            rows = [r.get("row", {}) for r in data.get("rows", [])]
            if rows:
                cache_file.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
            return rows
    except Exception:
        return []


def main():
    analyzer = MoralFoundationsAnalyzer(use_stanza=False)
    results = {}

    # 1. BISTRO Trilingual Context Sentences
    if BISTRO_PATH.exists():
        it_de_pairs = []
        it_gherd_pairs = []
        it_badia_pairs = []
        with open(BISTRO_PATH, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    entry = json.loads(line)
                except Exception:
                    continue
                lang_obj = entry.get("language", {})
                it_ctx = ""
                for meta in lang_obj.get("IT", {}).get("terms", {}).values():
                    if isinstance(meta, dict) and meta.get("contesto"):
                        it_ctx = meta["contesto"]
                        break

                de_ctx = ""
                for reg_dict in lang_obj.get("DE", {}).get("sprachgebrauch", {}).values():
                    if isinstance(reg_dict, dict):
                        for meta in reg_dict.values():
                            if isinstance(meta, dict) and meta.get("kontext_IT"):
                                de_ctx = meta["kontext_IT"]
                                break
                    if de_ctx:
                        break

                gherd_ctx = ""
                badia_ctx = ""
                for t_dict in lang_obj.get("Ladin", {}).get("adoranza_linguistica", {}).values():
                    if isinstance(t_dict, dict):
                        for meta in t_dict.values():
                            if isinstance(meta, dict):
                                for k, v in meta.items():
                                    if "Cuntest-Gherdëina" in k and v:
                                        gherd_ctx = v
                                    elif "Contest-Val Badia" in k and v:
                                        badia_ctx = v
                if it_ctx and de_ctx:
                    it_de_pairs.append((it_ctx, de_ctx))
                if it_ctx and gherd_ctx:
                    it_gherd_pairs.append((it_ctx, gherd_ctx))
                if it_ctx and badia_ctx:
                    it_badia_pairs.append((it_ctx, badia_ctx))

        results["bistro_it_de"] = evaluate_pairs(analyzer, it_de_pairs, "it", "de")
        results["bistro_it_lld_gherd"] = evaluate_pairs(analyzer, it_gherd_pairs, "it", "lld_gherd")
        results["bistro_it_lld_badia"] = evaluate_pairs(analyzer, it_badia_pairs, "it", "lld_badia")

    # 2. Hugging Face University of Innsbruck Parallel Corpora (sfrontull/*)
    for ds, lang_a, lang_b, col_a, col_b in [
        ("sfrontull/autonomia-lld_valbadia-ita", "it", "lld_badia", "ita", "lld_valbadia"),
        ("sfrontull/lld_gherd-ita", "it", "lld_gherd", "ita", "lld_gherd"),
        ("sfrontull/lld_valbadia-lld_gherd", "lld_badia", "lld_gherd", "lld_valbadia", "lld_gherd"),
    ]:
        rows = fetch_hf_rows(ds, limit=100)
        pairs = []
        for r in rows:
            if "translation" in r and isinstance(r["translation"], dict):
                ta = r["translation"].get(col_a) or r["translation"].get("it") or ""
                tb = r["translation"].get(col_b) or ""
            else:
                ta = r.get(col_a) or r.get("it") or ""
                tb = r.get(col_b) or ""
            if ta and tb:
                pairs.append((ta, tb))
        if pairs:
            results[ds] = evaluate_pairs(analyzer, pairs, lang_a, lang_b)

    VAL_DIR.mkdir(parents=True, exist_ok=True)
    out_file = VAL_DIR / "validation_summary.json"
    out_file.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    print("=" * 70)
    print("  Multilingual MFD Parallel Corpus Validation (Husson & Palma Protocol)")
    print("=" * 70)
    for name, m in results.items():
        print(f"  - {name}:")
        print(f"      Pairs: {m['n_pairs']} (active: {m['n_active_pairs']}) | r(all)={m['pearson_r_all']:+.3f} | r(active)={m['pearson_r_active']:+.3f} | Δμ={m['delta_mu']:+.2f}/1k")


if __name__ == "__main__":
    main()
