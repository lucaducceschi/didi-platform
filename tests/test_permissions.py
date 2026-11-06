"""Every rule in docs/coding/PRD.md, Section 6, called directly against the API."""

import pytest

ROLES = ("coder", "lead", "member_admin", "admin", "outsider", "anonymous")


def expect(coder, lead, member_admin, admin, outsider, anonymous=401):
    return dict(zip(ROLES, (coder, lead, member_admin, admin, outsider, anonymous)))


READS = {
    "project": ("GET", "", expect(200, 200, 200, 200, 404)),
    "members": ("GET", "/members", expect(200, 200, 200, 200, 404)),
    "codes": ("GET", "/codes", expect(200, 200, 200, 200, 404)),
    "segments": ("GET", "/articles/fx_de_1/annotations?scope=all", expect(200, 200, 200, 200, 404)),
    "activity": ("GET", "/activity", expect(200, 200, 200, 200, 404)),
    "export_segments": ("GET", "/exports/annotations.csv", expect(200, 200, 200, 200, 404)),
    "export_codes": ("GET", "/exports/codes.csv", expect(200, 200, 200, 200, 404)),
}


@pytest.mark.parametrize("name", READS)
@pytest.mark.parametrize("role", ROLES)
def test_reading_a_project(world, name, role):
    method, path, statuses = READS[name]
    assert getattr(world, role).request(method, world.url + path).status_code == statuses[role]


@pytest.mark.parametrize("role, status", expect(201, 201, 201, 403, 404).items())
def test_adding_a_segment(world, role, status):
    code = world.lead.post(f"{world.url}/codes", json={"name": "A"}).json()
    response = getattr(world, role).post(
        f"{world.url}/articles/fx_de_1/annotations", json={"start": 0, "end": 3, "code_id": code["id"]}
    )
    assert response.status_code == status


@pytest.mark.parametrize("role, status", expect(201, 201, 201, 403, 404).items())
def test_creating_a_code(world, role, status):
    assert getattr(world, role).post(f"{world.url}/codes", json={"name": f"New {role}"}).status_code == status


@pytest.mark.parametrize("role, status", expect(403, 200, 403, 403, 404).items())
def test_editing_a_code(world, role, status):
    code = world.lead.post(f"{world.url}/codes", json={"name": "A"}).json()
    response = getattr(world, role).patch(f"{world.url}/codes/{code['id']}", json={"revision": code["revision"], "name": "B"})
    assert response.status_code == status


@pytest.mark.parametrize("role, status", expect(403, 204, 403, 403, 404).items())
def test_deleting_a_code(world, role, status):
    code = world.lead.post(f"{world.url}/codes", json={"name": "A"}).json()
    assert getattr(world, role).delete(f"{world.url}/codes/{code['id']}", params={"revision": code["revision"]}).status_code == status


@pytest.mark.parametrize("role, status", expect(403, 200, 403, 403, 404).items())
def test_merging_codes(world, role, status):
    source = world.lead.post(f"{world.url}/codes", json={"name": "A"}).json()
    target = world.lead.post(f"{world.url}/codes", json={"name": "B"}).json()
    body = {"target_id": target["id"], "source_revision": 1, "target_revision": 1}
    assert getattr(world, role).post(f"{world.url}/codes/{source['id']}/merge", json=body).status_code == status



@pytest.mark.parametrize("role, status", expect(403, 201, 201, 201, 404).items())
def test_adding_a_member(world, role, status):
    assert getattr(world, role).post(f"{world.url}/members", json={"user_id": str(world.ids["admin"])}).status_code == status


@pytest.mark.parametrize("role, status", expect(403, 200, 200, 200, 404).items())
def test_adding_articles(world, role, status):
    response = getattr(world, role).post(f"{world.url}/articles", json={"article_ids": ["fx_de_1"]})
    assert response.status_code == status


@pytest.mark.parametrize("role, status", {"admin": 201, "member_admin": 201, "lead": 403, "coder": 403, "outsider": 403, "anonymous": 401}.items())
def test_creating_a_project(world, role, status):
    assert getattr(world, role).post("/api/projects", json={"name": f"Study {role}"}).status_code == status


@pytest.mark.parametrize("role, status", {"admin": 200, "member_admin": 200, "lead": 403, "coder": 403, "outsider": 403, "anonymous": 401}.items())
def test_listing_users(world, role, status):
    assert getattr(world, role).get("/api/users").status_code == status


@pytest.mark.parametrize("role, status", {"admin": 200, "lead": 403, "coder": 403, "anonymous": 401}.items())
def test_changing_a_user(world, role, status):
    assert getattr(world, role).patch(f"/api/users/{world.ids['coder2']}", json={"display_name": "Changed"}).status_code == status


def test_only_leads_and_admins_see_the_user_directory(world):
    assert world.lead.get("/api/users/directory").status_code == 200
    assert world.admin.get("/api/users/directory").status_code == 200
    assert world.coder2.get("/api/users/directory").status_code == 403


def test_a_user_can_be_a_lead_in_one_project_and_a_coder_in_another(world):
    other = f"/api/projects/{world.ids['other_project']}"
    assert world.coder.post(f"{other}/codes", json={"name": "Mine"}).status_code == 201
    code = world.coder.get(f"{other}/codes").json()[0]
    assert world.coder.patch(f"{other}/codes/{code['id']}", json={"revision": 1, "name": "Renamed"}).status_code == 200
    lead_code = world.lead.post(f"{world.url}/codes", json={"name": "A"}).json()
    assert world.coder.patch(f"{world.url}/codes/{lead_code['id']}", json={"revision": 1, "name": "B"}).status_code == 403
    roles = {project["name"]: project["role"] for project in world.coder.get("/api/projects").json()}
    assert roles == {"Autonomy": "coder", "Language rights": "lead"}


def test_projects_are_isolated(world):
    other = f"/api/projects/{world.ids['other_project']}"
    foreign = world.outsider.post(f"{other}/codes", json={"name": "Foreign"}).json()
    # A code from another project can't be used, edited or merged here.
    assert world.lead.post(f"{world.url}/articles/fx_de_1/annotations", json={"start": 0, "end": 3, "code_id": foreign["id"]}).status_code == 404
    assert world.lead.patch(f"{world.url}/codes/{foreign['id']}", json={"revision": 1, "name": "X"}).status_code == 404
    mine = world.lead.post(f"{world.url}/codes", json={"name": "Mine"}).json()
    assert world.lead.post(f"{world.url}/codes/{mine['id']}/merge", json={"target_id": foreign["id"], "source_revision": 1, "target_revision": 1}).status_code == 404
    assert world.lead.post(f"{world.url}/codes", json={"name": "Child", "parent_id": foreign["id"]}).status_code == 404
    assert "Foreign" not in world.lead.get(f"{world.url}/codes").text
    assert world.outsider.get(f"{world.url}/exports/annotations.csv").status_code == 404
    assert "Autonomy" not in world.outsider.get("/api/projects").text


def test_a_segment_cannot_be_changed_through_another_project(world):
    other = f"/api/projects/{world.ids['other_project']}"
    code = world.lead.post(f"{world.url}/codes", json={"name": "A"}).json()
    segment = world.coder.post(f"{world.url}/articles/fx_de_1/annotations", json={"start": 0, "end": 3, "code_id": code["id"]}).json()
    # This coder is a lead in the other project, but the segment doesn't belong there.
    assert world.coder.patch(f"{other}/annotations/{segment['id']}", json={"revision": 1, "memo": "x"}).status_code == 404


def test_archived_project_is_read_only_but_can_be_restored(world):
    project = world.lead.get(world.url).json()
    assert world.lead.patch(world.url, json={"revision": project["revision"], "archived": True}).status_code == 200
    assert world.coder.post(f"{world.url}/codes", json={"name": "Late"}).status_code == 409
    assert world.coder.get(f"{world.url}/codes").status_code == 200
    archived = world.lead.get(world.url).json()
    assert world.lead.patch(world.url, json={"revision": archived["revision"], "name": "New"}).status_code == 409
    assert world.lead.patch(world.url, json={"revision": archived["revision"], "archived": False}).status_code == 200
    assert world.coder.post(f"{world.url}/codes", json={"name": "Late"}).status_code == 201


def test_a_project_always_keeps_a_lead(world):
    lead_id = world.ids["lead"]
    assert world.lead.delete(f"{world.url}/members/{lead_id}").status_code == 409
    assert world.lead.patch(f"{world.url}/members/{lead_id}", json={"role": "coder"}).status_code == 409
    assert world.lead.patch(f"{world.url}/members/{world.ids['coder']}", json={"role": "lead"}).status_code == 200
    assert world.lead.delete(f"{world.url}/members/{lead_id}").status_code == 204
    assert world.lead.get(world.url).status_code == 404


def test_removing_a_member_keeps_their_segments(world):
    code = world.lead.post(f"{world.url}/codes", json={"name": "A"}).json()
    world.coder.post(f"{world.url}/articles/fx_de_1/annotations", json={"start": 0, "end": 3, "code_id": code["id"]})
    assert world.lead.delete(f"{world.url}/members/{world.ids['coder']}").status_code == 204
    assert len(world.lead.get(f"{world.url}/articles/fx_de_1/annotations", params={"scope": "all"}).json()) == 1


def test_unknown_articles_cannot_be_added(world):
    response = world.lead.post(f"{world.url}/articles", json={"article_ids": ["fx_de_1", "nope"]})
    assert response.status_code == 422
