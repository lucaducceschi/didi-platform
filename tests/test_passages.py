"""Reading coded passages across a project's articles."""

import csv
import io

from sqlalchemy.orm import Session

from backend.app.database import get_engine
from backend.app.models import Annotation
from tests.test_codebook import add_segment, make_code, merge


def passages(client, world, **params):
    response = client.get(f"{world.url}/passages", params=params)
    assert response.status_code == 200, response.text
    return response.json()


def quotes(body):
    return [(item["article_id"], item["quote"]) for item in body["results"]]


def full_text(world, article):
    return world.coder.get(f"/api/articles/{article}").json()["full_text"]


def test_filters_by_code_coder_variety_source_and_status(world):
    a, b = make_code(world, "A"), make_code(world, "B")
    first = add_segment(world.coder, world, a["id"], 0, 3, article="fx_de_1")
    add_segment(world.coder2, world, b["id"], 0, 3, article="fx_it_1")
    add_segment(world.coder, world, b["id"], 0, 3, article="fx_markup")

    assert passages(world.coder, world)["total"] == 3
    assert {item["article_id"] for item in passages(world.coder, world, code=b["id"])["results"]} == {"fx_it_1", "fx_markup"}
    assert [item["id"] for item in passages(world.coder, world, code=a["id"])["results"]] == [first["id"]]
    assert {item["article_id"] for item in passages(world.coder, world, coder=str(world.ids["coder"]))["results"]} == {"fx_de_1", "fx_markup"}
    assert [item["article_id"] for item in passages(world.coder, world, language="it")["results"]] == ["fx_it_1"]
    assert len(passages(world.coder, world, source="salto")["results"]) == 3
    assert len(passages(world.coder, world, type="journalism")["results"]) == 3
    assert len(passages(world.coder, world, type="official_press")["results"]) == 0
    assert passages(world.coder, world)["results"][0]["source_type"] == "journalism"
    assert passages(world.coder, world, status="stale")["total"] == 0


def test_counts_ignore_their_own_filter_only(world):
    a, b = make_code(world, "A"), make_code(world, "B")
    add_segment(world.coder, world, a["id"], 0, 3, article="fx_de_1")
    add_segment(world.coder2, world, b["id"], 0, 3, article="fx_it_1")

    body = passages(world.coder, world, language="de")
    assert body["total"] == 1 and body["project_total"] == 2
    # The variety count still offers Italian, but the code and coder counts respect the variety filter.
    assert {facet["id"]: facet["count"] for facet in body["languages"]} == {"de": 1, "it": 1}
    assert {item["id"]: item["direct"] for item in body["codes"]} == {a["id"]: 1, b["id"]: 0}
    assert {item["user"]["username"]: item["count"] for item in body["coders"]} == {"coder": 1}


def test_a_code_includes_its_subcodes_unless_turned_off(world):
    parent = make_code(world, "Parent")
    child = make_code(world, "Child", parent=parent["id"])
    grandchild = make_code(world, "Grandchild", parent=child["id"])
    add_segment(world.coder, world, parent["id"], 0, 3)
    add_segment(world.coder, world, child["id"], 4, 8)
    add_segment(world.coder, world, grandchild["id"], 0, 8)

    assert passages(world.coder, world, code=parent["id"])["total"] == 3
    assert passages(world.coder, world, code=parent["id"], subcodes="false")["total"] == 1
    assert passages(world.coder, world, code=child["id"])["total"] == 2
    counts = {item["id"]: (item["direct"], item["total"]) for item in passages(world.coder, world)["codes"]}
    assert counts[parent["id"]] == (1, 3) and counts[child["id"]] == (1, 2) and counts[grandchild["id"]] == (1, 1)
    paths = {item["id"]: item["code_path"] for item in passages(world.coder, world)["results"]}
    assert set(paths.values()) == {"Parent", "Parent > Child", "Parent > Child > Grandchild"}


def test_a_link_to_a_merged_code_follows_it(world):
    source, target = make_code(world, "Source"), make_code(world, "Target")
    add_segment(world.coder, world, source["id"], 0, 3)
    assert merge(world, source, target).status_code == 200
    body = passages(world.coder, world, code=source["id"])
    assert body["total"] == 1 and body["results"][0]["code_path"] == "Target"
    assert source["id"] not in {item["id"] for item in body["codes"]}


def test_sorted_newest_article_first_then_by_position(world):
    code = make_code(world, "A")
    add_segment(world.coder, world, code["id"], 4, 8, article="fx_de_1")
    add_segment(world.coder, world, code["id"], 0, 3, article="fx_de_1")
    add_segment(world.coder, world, code["id"], 0, 3, article="fx_it_1")
    articles = [(item["article_id"]) for item in passages(world.coder, world)["results"]]
    library = [item["id"] for item in world.coder.get(f"{world.url}/library").json()["results"] if item["id"] in articles]
    assert list(dict.fromkeys(articles)) == library
    first_article = [item["quote"] for item in passages(world.coder, world, language="de")["results"]]
    text = full_text(world, "fx_de_1")
    assert first_article == [text[0:3], text[4:8]]


def test_pages(world):
    code = make_code(world, "A")
    for start in range(0, 6, 2):
        add_segment(world.coder, world, code["id"], start, start + 1)
    first = passages(world.coder, world, page_size=2)
    second = passages(world.coder, world, page_size=2, page=2)
    assert first["total"] == 3 and len(first["results"]) == 2 and len(second["results"]) == 1
    assert not {item["id"] for item in first["results"]} & {item["id"] for item in second["results"]}


def test_context_is_cut_by_code_point_and_rejoins_the_text(world):
    code = make_code(world, "A")
    # Combining characters stay as they are in the corpus, and count one code point each.
    text = full_text(world, "fx_de_nfd")
    add_segment(world.coder, world, code["id"], 2, 8, article="fx_de_nfd")
    item = passages(world.coder, world)["results"][0]
    assert item["quote"] == text[2:8]
    assert item["before"] == text[:2]
    assert (item["before"] + item["quote"] + item["after"]).rstrip("…") == text[: 8 + 120]


def test_long_context_is_marked_as_shortened_and_cut_by_code_point(world, monkeypatch):
    code = make_code(world, "A")
    annotation = add_segment(world.coder, world, code["id"], 0, 3)
    from backend.app.corpus import get_corpus

    corpus = get_corpus()
    text = "😀" * 200 + "abc" + "y" * 200
    with Session(get_engine()) as db:
        row = db.get(Annotation, annotation["id"])
        row.start_pos, row.end_pos, row.quote = 200, 203, "abc"
        db.commit()
    monkeypatch.setattr(type(corpus), "get_article_texts", lambda self, ids: {"fx_de_1": text})
    item = passages(world.coder, world)["results"][0]
    assert item["before"] == "…" + "😀" * 120 and item["after"] == "y" * 120 + "…"


def test_no_context_when_the_position_cannot_be_trusted(world):
    code = make_code(world, "A")
    stale = add_segment(world.coder, world, code["id"], 0, 3)
    moved = add_segment(world.coder, world, code["id"], 4, 8)
    with Session(get_engine()) as db:
        db.get(Annotation, stale["id"]).status = "stale"
        db.get(Annotation, moved["id"]).quote = "not what the text says here"
        db.commit()
    for item in passages(world.coder, world)["results"]:
        assert item["before"] == "" and item["after"] == ""
    assert [item["id"] for item in passages(world.coder, world, status="stale")["results"]] == [stale["id"]]


def test_article_no_longer_in_the_corpus_stays_listed_and_sorts_last(world):
    code = make_code(world, "A")
    gone = add_segment(world.coder, world, code["id"], 0, 3)
    add_segment(world.coder, world, code["id"], 0, 3, article="fx_it_1")
    with Session(get_engine()) as db:
        row = db.get(Annotation, gone["id"])
        row.article_id = "gone_from_corpus"
        row.status = "stale"
        db.commit()
    body = passages(world.coder, world)
    last = body["results"][-1]
    assert last["article_id"] == "gone_from_corpus" and last["in_corpus"] is False and last["article_title"] == "gone_from_corpus"
    assert passages(world.coder, world, language="it")["total"] == 1


def test_markup_in_a_quote_comes_back_unchanged(world):
    code = make_code(world, "A")
    text = full_text(world, "fx_markup")
    add_segment(world.coder, world, code["id"], 0, len(text), article="fx_markup")
    assert passages(world.coder, world)["results"][0]["quote"] == text.strip()


def test_closed_to_other_projects_and_codes(world):
    assert world.outsider.get(f"{world.url}/passages").status_code == 404
    assert world.anonymous.get(f"{world.url}/passages").status_code == 401
    assert world.outsider.get(f"{world.url}/passages.csv").status_code == 404
    other = world.outsider.post(f"/api/projects/{world.ids['other_project']}/codes", json={"name": "Elsewhere", "parent_id": None}).json()
    assert world.coder.get(f"{world.url}/passages", params={"code": other["id"]}).status_code == 404


def test_a_non_member_admin_can_read(world):
    code = make_code(world, "A")
    add_segment(world.coder, world, code["id"], 0, 3)
    assert passages(world.admin, world)["total"] == 1


def test_csv_holds_exactly_what_the_filters_show(world):
    a, b = make_code(world, "A"), make_code(world, "B")
    kept = add_segment(world.coder, world, a["id"], 0, 3, memo="ñote")
    add_segment(world.coder, world, b["id"], 4, 8)
    response = world.coder.get(f"{world.url}/passages.csv", params={"code": a["id"]})
    assert response.status_code == 200 and "didi_passages.csv" in response.headers["content-disposition"]
    rows = list(csv.DictReader(io.StringIO(response.content.decode("utf-8-sig"), newline="")))
    assert [row["annotation_id"] for row in rows] == [kept["id"]]
    assert rows[0]["code_path"] == "A" and rows[0]["memo"] == "ñote"
    whole = world.coder.get(f"{world.url}/exports/annotations.csv").content.decode("utf-8-sig").splitlines()[0]
    assert response.content.decode("utf-8-sig").splitlines()[0] == whole
