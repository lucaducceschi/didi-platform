#!/usr/bin/env python3
"""Create a throwaway database for browser tests, so they never touch real data."""

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

ADMIN_URL = "postgresql+psycopg://didi:didi_dev@localhost:5433/didi"
E2E_URL = "postgresql+psycopg://didi:didi_dev@localhost:5433/didi_e2e"


def main() -> None:
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import Session

    engine = create_engine(ADMIN_URL, isolation_level="AUTOCOMMIT")
    with engine.connect() as connection:
        connection.execute(text("DROP DATABASE IF EXISTS didi_e2e WITH (FORCE)"))
        connection.execute(text("CREATE DATABASE didi_e2e"))
    engine.dispose()

    os.environ["DIDI_DATABASE_URL"] = E2E_URL
    command.upgrade(Config(str(PROJECT_ROOT / "backend" / "alembic.ini")), "head")

    from backend.app.database import get_engine
    from backend.app.services.accounts import create_user

    with Session(get_engine()) as db:
        create_user(db, "e2e_admin", "Admin Person", "e2e-test-password", is_admin=True)
        db.commit()


if __name__ == "__main__":
    main()
