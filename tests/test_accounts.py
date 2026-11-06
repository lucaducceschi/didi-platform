import logging
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.database import get_engine
from backend.app.models import Session as DbSession
from backend.app.models import User
from tests.conftest import PASSWORD


def test_login_sets_a_protected_cookie_and_me_works(world):
    client = world.make_client()
    response = client.post("/api/auth/login", json={"username": "coder", "password": PASSWORD})
    assert response.status_code == 200
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie
    assert client.get("/api/me").json()["username"] == "coder"


def test_username_ignores_case(world):
    assert world.make_client().post("/api/auth/login", json={"username": "CODER", "password": PASSWORD}).status_code == 200


def test_session_token_is_stored_hashed(world):
    client = world.make_client("coder")
    token = client.cookies["didi_session"]
    with Session(get_engine()) as db:
        hashes = db.scalars(select(DbSession.token_hash)).all()
    assert token not in hashes


def test_wrong_password_and_unknown_user_look_the_same(world):
    client = world.make_client()
    wrong = client.post("/api/auth/login", json={"username": "coder", "password": "nope-nope-nope"})
    unknown = client.post("/api/auth/login", json={"username": "ghost", "password": "nope-nope-nope"})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()


def test_repeated_failures_are_limited_even_with_the_right_password(world):
    client = world.make_client()
    for _ in range(5):
        assert client.post("/api/auth/login", json={"username": "coder", "password": "wrong-wrong-wrong"}).status_code == 401
    assert client.post("/api/auth/login", json={"username": "coder", "password": PASSWORD}).status_code == 429


def test_passwords_are_never_returned(world):
    for response in [world.admin.get("/api/users"), world.coder.get("/api/me")]:
        assert "password" not in response.text.lower() and "argon2" not in response.text


def test_passwords_are_never_logged(world, caplog):
    caplog.set_level(logging.DEBUG)
    secret = "very-secret-password-123"
    world.admin.post("/api/users", json={"username": "new", "display_name": "New", "password": secret})
    world.make_client().post("/api/auth/login", json={"username": "new", "password": secret})
    assert secret not in caplog.text


def test_expired_session_is_refused(world):
    client = world.make_client("coder")
    assert client.get("/api/me").status_code == 200
    with Session(get_engine()) as db:
        for session in db.scalars(select(DbSession).where(DbSession.user_id == world.ids["coder"])):
            session.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()
    assert client.get("/api/me").status_code == 401


def test_logout_ends_the_session(world):
    client = world.make_client("coder")
    token = client.cookies["didi_session"]
    assert client.post("/api/auth/logout").status_code == 204
    client.cookies.set("didi_session", token)
    assert client.get("/api/me").status_code == 401


def test_deactivating_a_user_ends_access_but_keeps_their_work(world):
    code = world.lead.post(f"{world.url}/codes", json={"name": "A"}).json()
    created = world.coder.post(
        f"{world.url}/articles/fx_de_1/annotations", json={"start": 0, "end": 3, "code_id": code["id"]}
    ).json()
    response = world.admin.patch(f"/api/users/{world.ids['coder']}", json={"active": False})
    assert response.status_code == 200
    assert world.coder.get("/api/me").status_code == 401
    assert world.make_client().post("/api/auth/login", json={"username": "coder", "password": PASSWORD}).status_code == 401
    segments = world.lead.get(f"{world.url}/articles/fx_de_1/annotations", params={"scope": "all"}).json()
    assert [segment["id"] for segment in segments] == [created["id"]]


def test_admin_reset_ends_existing_sessions(world):
    assert world.admin.patch(f"/api/users/{world.ids['coder']}", json={"password": "a-brand-new-password"}).status_code == 200
    assert world.coder.get("/api/me").status_code == 401
    assert world.make_client().post("/api/auth/login", json={"username": "coder", "password": "a-brand-new-password"}).status_code == 200


def test_admin_cannot_lock_themselves_out(world):
    assert world.admin.patch(f"/api/users/{world.ids['admin']}", json={"active": False}).status_code == 409
    assert world.admin.patch(f"/api/users/{world.ids['admin']}", json={"is_admin": False}).status_code == 409


def test_change_own_password(world):
    bad = world.coder.post("/api/me/password", json={"current_password": "wrong", "new_password": "a-brand-new-password"})
    assert bad.status_code == 403
    short = world.coder.post("/api/me/password", json={"current_password": PASSWORD, "new_password": "short"})
    assert short.status_code == 422
    good = world.coder.post("/api/me/password", json={"current_password": PASSWORD, "new_password": "a-brand-new-password"})
    assert good.status_code == 204
    assert world.make_client().post("/api/auth/login", json={"username": "coder", "password": "a-brand-new-password"}).status_code == 200


@pytest.mark.parametrize("username", ["coder", "CODER", " coder "])
def test_duplicate_usernames_are_refused(world, username):
    response = world.admin.post("/api/users", json={"username": username, "display_name": "X", "password": PASSWORD})
    assert response.status_code == 409


def test_create_admin_command(clean_database, monkeypatch, capsys):
    from backend.app import cli

    monkeypatch.setenv("DIDI_ADMIN_PASSWORD", PASSWORD)
    monkeypatch.setattr("sys.argv", ["cli", "create-admin", "root", "--display-name", "Root"])
    assert cli.main() == 0
    with Session(get_engine()) as db:
        user = db.scalar(select(User).where(User.username == "root"))
    assert user.is_admin and user.password_hash != PASSWORD
