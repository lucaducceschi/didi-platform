from typing import Annotated, Optional

from fastapi import APIRouter, Cookie, Request, Response

from backend.app.deps import SESSION_COOKIE, CurrentUser, Db
from backend.app.schemas_work import ChangePasswordRequest, LoginRequest, UserOut
from backend.app.services import accounts
from backend.app.settings import get_settings

router = APIRouter(prefix="/api")


@router.post("/auth/login", response_model=UserOut)
def login(body: LoginRequest, request: Request, response: Response, db: Db):
    client_ip = request.client.host if request.client else "unknown"
    token = accounts.login(db, body.username, body.password, client_ip)
    settings = get_settings()
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=settings.session_hours * 3600,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )
    return accounts.find_user(db, body.username)


@router.post("/auth/logout", status_code=204)
def logout(response: Response, db: Db, didi_session: Annotated[Optional[str], Cookie()] = None) -> None:
    accounts.logout(db, didi_session)
    response.delete_cookie(SESSION_COOKIE, path="/")


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser):
    return user


@router.post("/me/password", status_code=204)
def change_password(body: ChangePasswordRequest, user: CurrentUser, db: Db) -> None:
    accounts.change_password(db, user, body.current_password, body.new_password)
    db.commit()
