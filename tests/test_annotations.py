import csv
import io

import pytest
from sqlalchemy.orm import Session

from backend.app.database import get_engine
from backend.app.models import Annotation
from tests.test_codebook import add_segment, make_code

ARTICLE_URL = "{}/articles/{}/annotations"


@pytest.fixture
def code(world):
    return make_code(world, "A")


def post(client, world, code_id, start, end, article="fx_de_1"):
    return client.post(ARTICLE_URL.format(world.url, article), json={"start": start, "end": end, "code_id": code_id})


def test_quote_comes_from_the_server_and_whitespace_is_trimmed(world, code, fixture_records):
    text = next(r for r in fixture_records if r["id"] == "fx_de_1")["full_text"]
    start = text.index("Der") + 3  # The space before "Landtag"
    end = text.index("Landtag") + len("Landtag") + 1  # And the space after
    saved = post(world.coder, world, code["id"], start, end).json()
    assert saved["quote"] == "Landtag"
    assert text[saved["start_pos"] : saved["end_pos"]] == "Landtag"


@pytest.mark.parametrize("start, end", [(-1, 3), (0, 100000), (5, 5), (9, 3)])
def test_out_of_range_or_empty_positions_are_refused(world, code, start, end):
    assert post(world.coder, world, code["id"], start, end).status_code == 422


def test_selection_of_only_whitespace_is_refused(world, code, fixture_records):
    text = next(r for r in fixture_records if r["id"] == "fx_de_1")["full_text"]
    position = text.index("\n\n")
    response = post(world.coder, world, code["id"], position, position + 2)
    assert response.status_code == 422 and "spaces" in response.json()["detail"]


@pytest.mark.parametrize("article, target", [("fx_lld_nfd", "val ladina"), ("fx_lld_crlf", "Le teater"), ("fx_markup", "Museumsbericht"), ("fx_markup", "*Sterne*")])
def test_positions_are_python_code_points(world, code, fixture_records, article, target):
    text = next(r for r in fixture_records if r["id"] == article)["full_text"]
    start = text.index(target)
    saved = post(world.coder, world, code["id"], start, start + len(target), article).json()
    assert saved["quote"] == target and (saved["start_pos"], saved["end_pos"]) == (start, start + len(target))


def test_article_must_be_in_the_project(world, code):
    other = f"/api/projects/{world.ids['other_project']}"
    foreign = world.outsider.post(f"{other}/codes", json={"name": "F"}).json()
    assert post(world.outsider, type("W", (), {"url": other}), foreign["id"], 0, 3).status_code == 404


def test_identical_segment_returns_the_existing_one(world, code):
    first = post(world.coder, world, code["id"], 0, 3)
    second = post(world.coder, world, code["id"], 0, 3)
    assert first.status_code == 201 and first.json()["created"] is True
    assert second.status_code == 200 and second.json()["created"] is False
    assert first.json()["id"] == second.json()["id"]
    # The same span by another coder is a separate segment.
    assert post(world.coder2, world, code["id"], 0, 3).json()["id"] != first.json()["id"]


def test_only_the_author_can_change_a_segment_even_a_lead_or_admin(world, code):
    segment = add_segment(world.coder, world, code["id"])
    for client in (world.coder2, world.lead, world.member_admin):
        assert client.patch(f"{world.url}/annotations/{segment['id']}", json={"revision": 1, "memo": "x"}).status_code == 403
        assert client.delete(f"{world.url}/annotations/{segment['id']}", params={"revision": 1}).status_code == 403
    assert world.coder.patch(f"{world.url}/annotations/{segment['id']}", json={"revision": 1, "memo": "mine"}).json()["memo"] == "mine"


def test_stale_revision_gets_a_conflict_and_changes_nothing(world, code):
    segment = add_segment(world.coder, world, code["id"], memo="first")
    url = f"{world.url}/annotations/{segment['id']}"
    assert world.coder.patch(url, json={"revision": 1, "memo": "second"}).json()["revision"] == 2
    stale = world.coder.patch(url, json={"revision": 1, "memo": "third"})
    assert stale.status_code == 409
    assert world.coder.delete(url, params={"revision": 1}).status_code == 409
    assert world.coder.get(ARTICLE_URL.format(world.url, "fx_de_1")).json()[0]["memo"] == "second"
    assert world.coder.delete(url, params={"revision": 2}).status_code == 204


def test_changing_to_a_code_that_already_covers_the_span_is_a_conflict(world, code):
    other = make_code(world, "B")
    add_segment(world.coder, world, code["id"])
    segment = add_segment(world.coder, world, other["id"])
    response = world.coder.patch(f"{world.url}/annotations/{segment['id']}", json={"revision": 1, "code_id": code["id"]})
    assert response.status_code == 409


def test_scope_mine_and_all(world, code):
    add_segment(world.coder, world, code["id"], 0, 3)
    add_segment(world.coder2, world, code["id"], 4, 8)
    url = ARTICLE_URL.format(world.url, "fx_de_1")
    assert len(world.coder.get(url).json()) == 1
    assert len(world.coder.get(url, params={"scope": "all"}).json()) == 2


def _read_csv(response):
    assert response.headers["content-type"].startswith("text/csv")
    return list(csv.DictReader(io.StringIO(response.content.decode("utf-8-sig"))))


def test_exports_include_everything_with_exact_text(world, fixture_records):
    parent = make_code(world, "Autonomy", definition="About autonomy")
    child = make_code(world, "Finanzen", parent["id"])
    text = next(r for r in fixture_records if r["id"] == "fx_lld_nfd")["full_text"]
    add_segment(world.coder, world, child["id"], 0, 9, memo="Ein Memo, mit Komma", article="fx_lld_nfd")

    rows = _read_csv(world.lead.get(f"{world.url}/exports/annotations.csv"))
    assert len(rows) == 1
    row = rows[0]
    assert row["coder_username"] == "coder" and row["code_path"] == "Autonomy > Finanzen"
    assert row["quote"] == text[0:9] and row["memo"] == "Ein Memo, mit Komma"
    assert (row["start_pos"], row["end_pos"], row["status"]) == ("0", "9", "active")
    assert row["language"] == "lld_gherd" and row["project"] == "Autonomy"

    codes = {code["name"]: code for code in _read_csv(world.lead.get(f"{world.url}/exports/codes.csv"))}
    assert codes["Finanzen"]["code_path"] == "Autonomy > Finanzen"
    assert codes["Finanzen"]["segments"] == "1" and codes["Autonomy"]["definition"] == "About autonomy"


def test_export_keeps_merged_codes_on_record(world):
    source = make_code(world, "Source")
    target = make_code(world, "Target")
    world.lead.post(f"{world.url}/codes/{source['id']}/merge", json={"target_id": target["id"], "source_revision": 1, "target_revision": 1})
    codes = {code["name"]: code for code in _read_csv(world.lead.get(f"{world.url}/exports/codes.csv"))}
    assert codes["Source"]["merged_into"] == target["id"]


def _rewrite_corpus(path, article_id, new_text):
    import sqlite3

    connection = sqlite3.connect(path)
    if new_text is None:
        connection.execute("DELETE FROM articles WHERE id = ?", (article_id,))
    else:
        connection.execute("UPDATE articles SET full_text = ? WHERE id = ?", (new_text, article_id))
    connection.commit()
    connection.close()


@pytest.fixture
def private_corpus(world, fixture_corpus, tmp_path, monkeypatch):
    import shutil

    from backend.app.settings import get_settings

    copy = tmp_path / "corpus.db"
    shutil.copy(fixture_corpus, copy)
    monkeypatch.setenv("DIDI_CORPUS_PATH", str(copy))
    get_settings.cache_clear()
    return copy


def _reconcile(path):
    from backend.app.services.reconcile import reconcile_annotations

    with Session(get_engine()) as db:
        outcome = reconcile_annotations(db, path)
        db.commit()
    return outcome


def _load(segment):
    with Session(get_engine()) as db:
        return db.get(Annotation, segment["id"])


def test_reconcile_reanchors_a_unique_quote(world, code, private_corpus, fixture_records):
    text = next(r for r in fixture_records if r["id"] == "fx_de_1")["full_text"]
    start = text.index("Landtag")
    segment = post(world.coder, world, code["id"], start, start + 7).json()
    _rewrite_corpus(private_corpus, "fx_de_1", "Neuer Anfang. " + text)
    outcome = _reconcile(private_corpus)
    assert outcome["reanchored"] == 1
    stored = _load(segment)
    assert stored.status == "active" and stored.start_pos == start + len("Neuer Anfang. ")
    assert stored.revision == 2


def test_reconcile_marks_missing_or_repeated_quotes_stale_and_keeps_the_row(world, code, private_corpus, fixture_records):
    text = next(r for r in fixture_records if r["id"] == "fx_de_1")["full_text"]
    start = text.index("Landtag")
    repeated = post(world.coder, world, code["id"], start, start + 7).json()
    removed = add_segment(world.coder, world, code["id"], 0, 8, article="fx_it_1")
    gone = add_segment(world.coder, world, code["id"], 0, 5, article="fx_markup")
    _rewrite_corpus(private_corpus, "fx_de_1", "Landtag und Landtag.")
    _rewrite_corpus(private_corpus, "fx_it_1", "Testo completamente nuovo.")
    _rewrite_corpus(private_corpus, "fx_markup", None)
    assert _reconcile(private_corpus)["stale"] == 3
    for segment in (repeated, removed, gone):
        assert _load(segment).status == "stale"


def test_reconcile_leaves_unchanged_text_alone_and_restores_when_text_returns(world, code, private_corpus, fixture_records):
    text = next(r for r in fixture_records if r["id"] == "fx_de_1")["full_text"]
    segment = post(world.coder, world, code["id"], 0, 3).json()
    assert _reconcile(private_corpus)["unchanged"] == 1
    assert _load(segment).revision == 1
    _rewrite_corpus(private_corpus, "fx_de_1", "Etwas ganz anderes ohne Treffer.")
    assert _reconcile(private_corpus)["stale"] == 1
    _rewrite_corpus(private_corpus, "fx_de_1", text)
    assert _reconcile(private_corpus)["restored"] == 1
    assert _load(segment).status == "active"
