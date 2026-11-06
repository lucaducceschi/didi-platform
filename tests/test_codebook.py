import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.database import get_engine
from backend.app.models import ActivityLog, Annotation, Code


def make_code(world, name, parent=None, **fields):
    response = world.lead.post(f"{world.url}/codes", json={"name": name, "parent_id": parent, **fields})
    assert response.status_code == 201, response.text
    return response.json()


def code_by_id(world, code_id):
    return next(code for code in world.lead.get(f"{world.url}/codes").json() if code["id"] == code_id)


def add_segment(client, world, code_id, start=0, end=3, memo="", article="fx_de_1"):
    response = client.post(f"{world.url}/articles/{article}/annotations", json={"start": start, "end": end, "code_id": code_id, "memo": memo})
    assert response.status_code in (200, 201), response.text
    return response.json()


def merge(world, source, target):
    return world.lead.post(
        f"{world.url}/codes/{source['id']}/merge",
        json={"target_id": target["id"], "source_revision": source["revision"], "target_revision": target["revision"]},
    )


def fresh(world, code):
    return code_by_id(world, code["id"])


def test_names_are_required_and_unique_among_siblings_ignoring_case(world):
    parent = make_code(world, "Parent")
    make_code(world, "Child", parent["id"])
    assert world.lead.post(f"{world.url}/codes", json={"name": "   "}).status_code == 422
    assert world.lead.post(f"{world.url}/codes", json={"name": "CHILD", "parent_id": parent["id"]}).status_code == 409
    # The same name is fine at a different level.
    make_code(world, "child")


def test_sibling_names_cannot_collide_through_rename_or_move(world):
    make_code(world, "Taken")
    other = make_code(world, "Other")
    assert world.lead.patch(f"{world.url}/codes/{other['id']}", json={"revision": 1, "name": "taken"}).status_code == 409
    parent = make_code(world, "Parent")
    child = make_code(world, "Taken", parent["id"])
    assert world.lead.patch(f"{world.url}/codes/{child['id']}", json={"revision": 1, "parent_id": None}).status_code == 409


def test_case_only_rename_works(world):
    code = make_code(world, "code")
    assert world.lead.patch(f"{world.url}/codes/{code['id']}", json={"revision": 1, "name": "Code"}).json()["name"] == "Code"


def test_rename_keeps_segments_attached(world):
    code = make_code(world, "Old")
    segment = add_segment(world.coder, world, code["id"])
    assert world.lead.patch(f"{world.url}/codes/{code['id']}", json={"revision": 1, "name": "New"}).status_code == 200
    segments = world.coder.get(f"{world.url}/articles/fx_de_1/annotations").json()
    assert segments[0]["code_id"] == code["id"] and segments[0]["id"] == segment["id"]


def test_moves_that_create_cycles_are_refused(world):
    top = make_code(world, "Top")
    middle = make_code(world, "Middle", top["id"])
    bottom = make_code(world, "Bottom", middle["id"])
    assert world.lead.patch(f"{world.url}/codes/{top['id']}", json={"revision": 1, "parent_id": bottom["id"]}).status_code == 409
    assert world.lead.patch(f"{world.url}/codes/{top['id']}", json={"revision": 1, "parent_id": top["id"]}).status_code == 409
    assert world.lead.patch(f"{world.url}/codes/{bottom['id']}", json={"revision": 1, "parent_id": top["id"]}).status_code == 200


def test_stale_revision_gets_a_conflict_and_changes_nothing(world):
    code = make_code(world, "A", definition="first")
    assert world.lead.patch(f"{world.url}/codes/{code['id']}", json={"revision": 1, "definition": "second"}).status_code == 200
    stale = world.lead.patch(f"{world.url}/codes/{code['id']}", json={"revision": 1, "definition": "third"})
    assert stale.status_code == 409 and "someone else" in stale.json()["detail"]
    assert fresh(world, code)["definition"] == "second"
    assert world.lead.delete(f"{world.url}/codes/{code['id']}", params={"revision": 1}).status_code == 409


def test_delete_refused_with_segments_or_children(world):
    used = make_code(world, "Used")
    add_segment(world.coder, world, used["id"])
    response = world.lead.delete(f"{world.url}/codes/{used['id']}", params={"revision": 1})
    assert response.status_code == 409 and "Merge" in response.json()["detail"]
    parent = make_code(world, "Parent")
    make_code(world, "Child", parent["id"])
    assert world.lead.delete(f"{world.url}/codes/{parent['id']}", params={"revision": 1}).status_code == 409


def test_merge_moves_segments_reparents_children_and_hides_the_source(world):
    source = make_code(world, "Source")
    target = make_code(world, "Target")
    child = make_code(world, "Child", source["id"])
    first = add_segment(world.coder, world, source["id"], 0, 3)
    second = add_segment(world.coder2, world, source["id"], 4, 8)
    preview = world.lead.get(f"{world.url}/codes/{source['id']}/merge-preview", params={"into": target["id"]}).json()
    assert preview == {"segments": 2, "duplicates": 0, "coders": 2, "name_conflicts": []}

    assert merge(world, source, target).status_code == 200
    codes = {code["id"]: code for code in world.lead.get(f"{world.url}/codes").json()}
    assert source["id"] not in codes
    assert codes[target["id"]]["segment_count"] == 2
    assert codes[child["id"]]["parent_id"] == target["id"]
    segments = world.lead.get(f"{world.url}/articles/fx_de_1/annotations", params={"scope": "all"}).json()
    assert {s["id"] for s in segments} == {first["id"], second["id"]}
    assert all(s["code_id"] == target["id"] for s in segments)


def test_merge_duplicates_keep_targets_row_and_append_a_different_memo(world):
    source = make_code(world, "Source")
    target = make_code(world, "Target")
    kept = add_segment(world.coder, world, target["id"], 0, 3, memo="target memo")
    add_segment(world.coder, world, source["id"], 0, 3, memo="source memo")
    same_memo = add_segment(world.coder, world, target["id"], 5, 9, memo="same")
    add_segment(world.coder, world, source["id"], 5, 9, memo="same")
    # Another coder's identical span isn't a duplicate.
    others = add_segment(world.coder2, world, source["id"], 0, 3, memo="coder2 memo")
    preview = world.lead.get(f"{world.url}/codes/{source['id']}/merge-preview", params={"into": target["id"]}).json()
    assert preview["segments"] == 3 and preview["duplicates"] == 2

    assert merge(world, source, target).status_code == 200
    segments = {s["id"]: s for s in world.lead.get(f"{world.url}/articles/fx_de_1/annotations", params={"scope": "all"}).json()}
    assert set(segments) == {kept["id"], same_memo["id"], others["id"]}
    assert segments[kept["id"]]["memo"] == "target memo\n\nsource memo"
    assert segments[same_memo["id"]]["memo"] == "same"
    assert segments[others["id"]]["memo"] == "coder2 memo"


def test_merge_logs_moved_segments(world):
    source = make_code(world, "Source")
    target = make_code(world, "Target")
    moved = add_segment(world.coder, world, source["id"])
    merge(world, source, target)
    with Session(get_engine()) as db:
        entry = db.scalar(select(ActivityLog).where(ActivityLog.action == "code.merged"))
    assert entry.details["moved_segments"] == [moved["id"]]


def test_merge_rolls_back_fully_on_failure(world, monkeypatch):
    from backend.app.services import codebook

    source = make_code(world, "Source")
    target = make_code(world, "Target")
    child = make_code(world, "Child", source["id"])
    add_segment(world.coder, world, source["id"])

    real_log = codebook.log_activity

    def fail_at_the_end(db, action, *args, **kwargs):
        if action == "code.merged":
            raise RuntimeError("Simulated failure")
        return real_log(db, action, *args, **kwargs)

    monkeypatch.setattr(codebook, "log_activity", fail_at_the_end)
    with pytest.raises(RuntimeError):
        merge(world, source, target)
    monkeypatch.undo()

    with Session(get_engine()) as db:
        assert db.get(Code, source["id"]).merged_into is None
        assert str(db.get(Code, child["id"]).parent_id) == source["id"]
        assert {str(code_id) for code_id in db.scalars(select(Annotation.code_id))} == {source["id"]}


def test_merge_refuses_stale_revisions_self_and_colliding_children(world):
    source = make_code(world, "Source")
    target = make_code(world, "Target")
    assert world.lead.post(f"{world.url}/codes/{source['id']}/merge", json={"target_id": source["id"], "source_revision": 1, "target_revision": 1}).status_code == 422
    world.lead.patch(f"{world.url}/codes/{target['id']}", json={"revision": 1, "definition": "changed"})
    assert merge(world, source, target).status_code == 409

    target = fresh(world, target)
    make_code(world, "Same", source["id"])
    make_code(world, "same", target["id"])
    preview = world.lead.get(f"{world.url}/codes/{source['id']}/merge-preview", params={"into": target["id"]}).json()
    assert preview["name_conflicts"] == ["Same"]
    assert merge(world, source, target).status_code == 409


def test_merging_into_a_descendant_keeps_the_tree_valid(world):
    top = make_code(world, "Top")
    source = make_code(world, "Source", top["id"])
    target = make_code(world, "Target", source["id"])
    sibling = make_code(world, "Sibling", source["id"])
    assert merge(world, source, target).status_code == 200
    codes = {code["id"]: code for code in world.lead.get(f"{world.url}/codes").json()}
    assert codes[target["id"]]["parent_id"] == top["id"]
    assert codes[sibling["id"]]["parent_id"] == target["id"]


def test_saving_with_a_merged_code_goes_to_the_current_code_and_says_so(world):
    first = make_code(world, "First")
    second = make_code(world, "Second")
    third = make_code(world, "Third")
    merge(world, first, second)
    merge(world, fresh(world, second), third)
    saved = add_segment(world.coder, world, first["id"])
    assert saved["code_id"] == third["id"]
    assert saved["merged_from"] == "First"


def test_merged_codes_cannot_be_edited_or_used_as_parents(world):
    source = make_code(world, "Source")
    target = make_code(world, "Target")
    merge(world, source, target)
    assert world.lead.patch(f"{world.url}/codes/{source['id']}", json={"revision": 2, "name": "X"}).status_code == 409
    assert world.lead.post(f"{world.url}/codes", json={"name": "Child", "parent_id": source["id"]}).status_code == 409
    # The name of a merged code is free again.
    make_code(world, "Source")


def test_merge_target_cannot_be_deleted_because_it_holds_the_record(world):
    source = make_code(world, "Source")
    target = make_code(world, "Target")
    merge(world, source, target)
    current = fresh(world, target)
    response = world.lead.delete(f"{world.url}/codes/{target['id']}", params={"revision": current["revision"]})
    assert response.status_code == 409


def test_new_project_codebook_options(world):
    def create(name, **codebook):
        response = world.admin.post("/api/projects", json={"name": name, "lead_user_id": str(world.ids["lead"]), "codebook": codebook})
        assert response.status_code == 201, response.text
        return f"/api/projects/{response.json()['id']}"

    assert world.lead.get(f"{create('Empty', mode='empty')}/codes").json() == []

    starter = world.lead.get(f"{create('Starter', mode='starter')}/codes").json()
    names = {code["name"]: code for code in starter}
    assert names["Competences"]["parent_id"] == names["Autonomy"]["id"]
    assert "Custom Tag" not in names and len(starter) == 16

    top = make_code(world, "Top", definition="A definition", color="#112233")
    child = make_code(world, "Child", top["id"])
    make_code(world, "Grandchild", child["id"])
    gone = make_code(world, "Gone")
    merge(world, gone, top)
    add_segment(world.coder, world, top["id"])
    copied = world.lead.get(f"{create('Copy', mode='copy', source_project_id=str(world.ids['project']))}/codes").json()
    copied_names = {code["name"]: code for code in copied}
    assert set(copied_names) == {"Top", "Child", "Grandchild"}
    assert copied_names["Top"]["definition"] == "A definition" and copied_names["Top"]["color"] == "#112233"
    assert copied_names["Grandchild"]["parent_id"] == copied_names["Child"]["id"]
    assert copied_names["Top"]["id"] != top["id"] and copied_names["Top"]["segment_count"] == 0


def test_invalid_color_is_refused(world):
    assert world.lead.post(f"{world.url}/codes", json={"name": "A", "color": "red"}).status_code == 422


def test_codebook_changes_are_logged(world):
    code = make_code(world, "A")
    world.lead.patch(f"{world.url}/codes/{code['id']}", json={"revision": 1, "name": "B"})
    world.lead.delete(f"{world.url}/codes/{code['id']}", params={"revision": 2})
    actions = [entry["action"] for entry in world.coder.get(f"{world.url}/activity").json()]
    assert actions == ["code.deleted", "code.updated", "code.created"]
