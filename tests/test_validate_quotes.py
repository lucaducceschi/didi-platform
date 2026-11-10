import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "validate_quotes", Path(__file__).resolve().parent.parent / "scripts" / "validate_quotes.py"
)
vq = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vq)


def row(sample_type, label, language="it", source_type="journalism"):
    return {"sample_type": sample_type, "label": label,
            "language": language, "source_type": source_type}


def test_score_counts_precision_boundaries_and_misses():
    rows = [
        row("candidate_quote", "correct"),
        row("candidate_quote", "correct"),
        row("candidate_quote", "boundary"),
        row("candidate_quote", "not_speech"),
        row("candidate_quote", ""),  # unlabelled rows are ignored
        row("non_quote_paragraph", "missed"),
        row("non_quote_paragraph", "ok"),
        row("non_quote_paragraph", "ok", language="de"),
    ]
    res = vq.score(rows)
    it = res["it/journalism"]
    assert it["precision"] == (3, 4)
    assert it["exact_boundaries"] == (2, 3)
    assert it["miss_rate"] == (1, 2)
    assert res["de/journalism"]["miss_rate"] == (0, 1)
    assert res["all"]["miss_rate"] == (1, 3)


def test_wilson_interval_brackets_the_rate():
    lo, hi = vq.wilson(45, 50)
    assert lo < 0.9 < hi
    assert vq.wilson(0, 10)[0] == 0.0
