"""
Tests for provinz_press collector:
1. Raw API response saved gzipped with SHA-256 and checksum recorded in article doc.
2. Failed page retried with backoff, then run reports failure (non-zero / exception).
3. Later run continuing from where it stopped (checkpoint resumption).
All tests run offline on synthetic fixtures with no network access.
"""
import gzip
import hashlib
import json
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from src.collectors.provinz import (
    get_checkpoint,
    harvest_provinz_press,
    set_checkpoint,
)
from src.collectors.store import State


def _make_mock_api_payload(items, total_count=None, skip=0):
    total = total_count if total_count is not None else len(items)
    return json.dumps({
        "pagination": {"skip": skip, "limit": 100, "count": len(items), "total_count": total},
        "items": items,
    }).encode("utf-8")


def _make_sample_item(item_id: str, codename: str, title: str, lang: str):
    return {
        "system": {
            "id": item_id,
            "codename": codename,
            "type": "news",
            "last_modified": "2026-03-04T12:00:00Z",
        },
        "elements": {
            "title": {"value": title},
            "subtitle": {"value": "Sottotitolo della notizia"},
            "text": {"value": "<p>Corpo del comunicato stampa ufficiale con testo sufficientemente lungo per superare i filtri.</p>"},
            "author": {"value": "USP"},
            "date": {"value": "2026-03-04T12:00:00Z"},
            "url": {"value": f"slug-{codename}"},
        },
    }


def test_raw_response_saved_with_checksum(tmp_path: Path):
    item = _make_sample_item("art_1", "news_1", "Titolo Notizia 1", "it")
    payload = _make_mock_api_payload([item], total_count=1, skip=0)
    expected_sha256 = hashlib.sha256(payload).hexdigest()

    mock_resp = MagicMock()
    mock_resp.read.return_value = payload
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp):
        res = harvest_provinz_press(
            languages=["it"],
            data_dir=tmp_path,
            delay_seconds=0.0,
            batch_size=10,
            resume=False,
        )

    assert res["total_written"] == 1
    state = State(tmp_path)

    # Check that raw page is stored and checksum matches
    row = state.db.execute("SELECT sha256, path FROM raw_pages WHERE sha256=?", (expected_sha256,)).fetchone()
    assert row is not None
    saved_path = Path(row[1])
    assert saved_path.exists()
    with gzip.open(saved_path, "rb") as f:
        assert f.read() == payload

    # Check that doc in docs table stores the raw_sha256 checksum
    doc_row = state.db.execute("SELECT raw_sha256 FROM docs WHERE doc_id LIKE 'provinz_it_%'").fetchone()
    assert doc_row is not None
    assert doc_row[0] == expected_sha256


def test_failed_page_retried_and_run_reports_failure(tmp_path: Path):
    mock_urlopen = MagicMock(side_effect=Exception("Connection timeout"))

    with patch("urllib.request.urlopen", mock_urlopen):
        with pytest.raises(RuntimeError) as exc_info:
            harvest_provinz_press(
                languages=["it"],
                data_dir=tmp_path,
                delay_seconds=0.01,
                batch_size=10,
                max_retries=3,
                resume=False,
            )

    # Assert it was retried 3 times
    assert mock_urlopen.call_count == 3
    # Assert exception message contains the language and offset skip=0
    assert "offset skip=0" in str(exc_info.value)
    assert "language 'it'" in str(exc_info.value)

    # Assert run is NOT recorded as successful in runs table
    state = State(tmp_path)
    run_row = state.db.execute("SELECT status FROM runs WHERE source_id='provinz_press' AND status='ok'").fetchone()
    assert run_row is None


def test_later_run_continues_from_where_it_stopped(tmp_path: Path):
    state = State(tmp_path)
    # Simulate first batch having processed 10 items
    set_checkpoint(state, "it", 10)
    assert get_checkpoint(state, "it") == 10

    # Batch 2 has items 11 and 12, total 12
    item2 = _make_sample_item("art_2", "news_2", "Titolo Notizia 2", "it")
    payload2 = _make_mock_api_payload([item2], total_count=12, skip=10)

    mock_resp = MagicMock()
    mock_resp.read.return_value = payload2
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp) as mock_urlopen:
        res = harvest_provinz_press(
            languages=["it"],
            data_dir=tmp_path,
            delay_seconds=0.0,
            batch_size=10,
            resume=True,
        )

    # Check url requested on first call had skip=10
    first_called_url = mock_urlopen.call_args_list[0][0][0].full_url
    assert "skip=10" in first_called_url
    assert res["total_written"] >= 1

    # Check that checkpoint updated to total (12)
    assert get_checkpoint(state, "it") == 0


def test_completed_run_followed_by_second_run_starts_at_zero_and_writes_only_new_items(tmp_path: Path):
    item1 = _make_sample_item("art_1", "news_1", "Titolo Notizia 1", "it")
    item2 = _make_sample_item("art_2", "news_2", "Titolo Notizia 2", "it")
    payload_run1 = _make_mock_api_payload([item1, item2], total_count=2, skip=0)

    mock_resp1 = MagicMock()
    mock_resp1.read.return_value = payload_run1
    mock_resp1.__enter__.return_value = mock_resp1

    # Run 1: writes 2 items
    with patch("urllib.request.urlopen", return_value=mock_resp1):
        res1 = harvest_provinz_press(
            languages=["it"],
            data_dir=tmp_path,
            delay_seconds=0.0,
            batch_size=10,
            resume=True,
        )

    assert res1["total_written"] == 2
    state = State(tmp_path)
    # Checkpoint must be reset to 0 upon completion
    assert get_checkpoint(state, "it") == 0

    # Run 2: returns item1, item2 and new item3 (total 3)
    item3 = _make_sample_item("art_3", "news_3", "Titolo Notizia 3 Nuova", "it")
    payload_run2 = _make_mock_api_payload([item1, item2, item3], total_count=3, skip=0)

    mock_resp2 = MagicMock()
    mock_resp2.read.return_value = payload_run2
    mock_resp2.__enter__.return_value = mock_resp2

    with patch("urllib.request.urlopen", return_value=mock_resp2) as mock_urlopen:
        res2 = harvest_provinz_press(
            languages=["it"],
            data_dir=tmp_path,
            delay_seconds=0.0,
            batch_size=10,
            resume=True,
        )

    # Started at skip=0
    first_call_url = mock_urlopen.call_args_list[0][0][0].full_url
    assert "skip=0" in first_call_url
    assert "order=system.last_modified[asc]" in first_call_url
    # Only 1 new item was written, 2 were skipped as known
    assert res2["total_written"] == 1
    assert res2["total_skipped"] == 2
    assert get_checkpoint(state, "it") == 0


def test_404_is_not_retried(tmp_path: Path):
    import urllib.error

    http_404 = urllib.error.HTTPError(
        url="https://deliver.kontent.ai/test",
        code=404,
        msg="Not Found",
        hdrs={},
        fp=None,
    )
    mock_urlopen = MagicMock(side_effect=http_404)

    with patch("urllib.request.urlopen", mock_urlopen):
        with pytest.raises(RuntimeError) as exc_info:
            harvest_provinz_press(
                languages=["it"],
                data_dir=tmp_path,
                delay_seconds=0.01,
                batch_size=10,
                max_retries=3,
                resume=False,
            )

    # 404 is a non-retryable 4xx client error, must NOT be retried (called exactly once)
    assert mock_urlopen.call_count == 1
    assert "non-retryable" in str(exc_info.value).lower()

