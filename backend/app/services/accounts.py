"""Users, passwords, sessions and login limits."""

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session as DbSession

from backend.app.errors import conflict, invalid
from backend.app.models import LoginAttempt, Session, User
from backend.app.security import (
    MIN_PASSWORD_LENGTH,
    burn_verification,
    hash_password,
    hash_token,
    new_session_token,
    verify_password,
)
from backend.app.services.activity import log_activity
from backend.app.settings import get_settings


def check_password_strength(password: str) -> None:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise invalid(f"Passwords need at least {MIN_PASSWORD_LENGTH} characters.")


def find_user(db: DbSession, username: str) -> Optional[User]:
    return db.scalar(select(User).where(func.lower(User.username) == username.strip().lower()))


def create_user(db: DbSession, username: str, display_name: str, password: str, is_admin: bool, created_by=None) -> User:
    username = username.strip()
    display_name = display_name.strip()
    if not username or not display_name:
        raise invalid("A username and a display name are required.")
    check_password_strength(password)
    if find_user(db, username):
        raise conflict(f"The username '{username}' is already taken.")
    user = User(username=username, display_name=display_name, password_hash=hash_password(password), is_admin=is_admin)
    db.add(user)
    db.flush()
    log_activity(db, "user.created", username, user_id=created_by, is_admin=is_admin)
    return user


def _attempt_key(username: str, client_ip: str) -> str:
    return f"{username.strip().lower()}|{client_ip}"


def login(db: DbSession, username: str, password: str, client_ip: str) -> str:
    """Return a new session token, or raise. The caller must not roll back: failures are recorded here."""
    settings = get_settings()
    now = datetime.now(timezone.utc)
    window = timedelta(minutes=settings.login_window_minutes)
    key = _attempt_key(username, client_ip)

    attempt = db.get(LoginAttempt, key)
    if attempt and now - attempt.first_failure_at >= window:
        db.delete(attempt)
        db.flush()
        attempt = None
    if attempt and attempt.failures >= settings.login_max_failures:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many failed attempts. Please wait and try again.")

    user = find_user(db, username)
    if user:
        valid = verify_password(user.password_hash, password)
    else:
        burn_verification(password)
        valid = False

    if not valid or not user.active:
        if attempt:
            attempt.failures += 1
        else:
            db.add(LoginAttempt(key=key, failures=1, first_failure_at=now))
        db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "The username or password is incorrect.")

    if attempt:
        db.delete(attempt)
    db.execute(delete(Session).where(Session.expires_at <= now))
    token = new_session_token()
    db.add(Session(token_hash=hash_token(token), user_id=user.id, expires_at=now + timedelta(hours=settings.session_hours)))
    db.commit()
    return token


def logout(db: DbSession, token: Optional[str]) -> None:
    if token:
        db.execute(delete(Session).where(Session.token_hash == hash_token(token)))
        db.commit()


def end_all_sessions(db: DbSession, user: User) -> None:
    db.execute(delete(Session).where(Session.user_id == user.id))


def change_password(db: DbSession, user: User, current_password: str, new_password: str) -> None:
    if not verify_password(user.password_hash, current_password):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Your current password is incorrect.")
    check_password_strength(new_password)
    user.password_hash = hash_password(new_password)
    log_activity(db, "user.password_changed", user.username, user_id=user.id)


def update_user(db: DbSession, target: User, admin: User, changes: dict) -> User:
    if "display_name" in changes:
        name = (changes["display_name"] or "").strip()
        if not name:
            raise invalid("A display name is required.")
        target.display_name = name
    if changes.get("password") is not None:
        check_password_strength(changes["password"])
        target.password_hash = hash_password(changes["password"])
        end_all_sessions(db, target)
    if changes.get("active") is not None and changes["active"] != target.active:
        if target.id == admin.id:
            raise conflict("You can't deactivate your own account.")
        target.active = changes["active"]
        if not target.active:
            end_all_sessions(db, target)
    if changes.get("is_admin") is not None and changes["is_admin"] != target.is_admin:
        if target.id == admin.id:
            raise conflict("You can't change your own admin rights.")
        target.is_admin = changes["is_admin"]
    logged = sorted(key for key in changes if key != "password") + (["password"] if changes.get("password") else [])
    log_activity(db, "user.updated", target.username, user_id=admin.id, fields=logged)
    return target

