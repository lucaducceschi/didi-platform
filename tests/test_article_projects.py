"""The corpus article page learns which of the caller's projects hold an article."""

from sqlalchemy.orm import Session

from backend.app.database import get_engine
from backend.app.models import Project


def listing(client, article_id):
    response = client.get(f"/api/articles/{article_id}/projects")
    assert response.status_code == 200, response.text
    return {item["name"]: (item["role"], item["in_project"]) for item in response.json()}


def test_lists_only_the_callers_projects_with_role_and_membership_of_the_article(world):
    assert listing(world.coder, "fx_de_1") == {"Autonomy": ("coder", True), "Language rights": ("lead", False)}
    assert listing(world.lead, "fx_de_1") == {"Autonomy": ("lead", True)}
    assert listing(world.outsider, "fx_de_1") == {"Language rights": ("lead", False)}


def test_being_an_admin_does_not_list_projects_you_are_not_in(world):
    assert listing(world.admin, "fx_de_1") == {}


def test_adding_the_article_shows_up_in_the_listing(world):
    other = f"/api/projects/{world.ids['other_project']}"
    assert world.outsider.post(f"{other}/articles", json={"article_ids": ["fx_de_1"]}).status_code == 200
    assert listing(world.outsider, "fx_de_1") == {"Language rights": ("lead", True)}


def test_archived_projects_are_flagged(world):
    with Session(get_engine()) as db:
        db.get(Project, world.ids["project"]).archived = True
        db.commit()
    assert world.lead.get("/api/articles/fx_de_1/projects").json()[0]["archived"] is True


def test_needs_a_login_and_a_real_article(world):
    assert world.anonymous.get("/api/articles/fx_de_1/projects").status_code == 401
    assert world.lead.get("/api/articles/no_such_article/projects").status_code == 404
