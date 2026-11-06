import sqlite3

from fastapi import APIRouter, Response, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from backend.app.database import get_engine
from backend.app.schemas import HealthResponse
from backend.app.settings import get_settings

router = APIRouter()


def _check_postgres() -> str:
    try:
        with get_engine().connect() as connection:
            connection.execute(text("SELECT 1"))
        return "ok"
    except SQLAlchemyError:
        return "unavailable"


def _check_corpus() -> str:
    path = get_settings().corpus_path
    try:
        connection = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
        try:
            connection.execute("SELECT 1 FROM articles LIMIT 1").fetchone()
        finally:
            connection.close()
        return "ok"
    except sqlite3.Error:
        return "unavailable"


@router.get("/api/health", response_model=HealthResponse)
def health(response: Response) -> HealthResponse:
    checks = {"database": _check_postgres(), "corpus": _check_corpus()}
    healthy = all(value == "ok" for value in checks.values())
    if not healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return HealthResponse(
        status="ok" if healthy else "unavailable",
        build={"version": get_settings().build_version},
        checks=checks,
    )
