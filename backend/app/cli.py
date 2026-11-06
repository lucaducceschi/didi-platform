"""Administrative commands: python -m backend.app.cli <command>."""

import argparse
import getpass
import os
import sys

from sqlalchemy.orm import Session

from backend.app.database import get_engine
from backend.app.services import accounts
from backend.app.services.reconcile import reconcile_annotations
from backend.app.settings import get_settings


def create_admin(args: argparse.Namespace) -> int:
    password = os.environ.get("DIDI_ADMIN_PASSWORD") or getpass.getpass("Password: ")
    with Session(get_engine()) as db:
        try:
            accounts.create_user(db, args.username, args.display_name or args.username, password, is_admin=True)
        except Exception as error:
            print(getattr(error, "detail", error), file=sys.stderr)
            return 1
        db.commit()
    print(f"Created admin '{args.username}'.")
    return 0


def reconcile(_: argparse.Namespace) -> int:
    with Session(get_engine()) as db:
        outcome = reconcile_annotations(db, get_settings().corpus_path)
        db.commit()
    for result in ("unchanged", "reanchored", "restored", "stale"):
        print(f"{result}: {outcome[result]}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(required=True)
    admin = commands.add_parser("create-admin", help="Create an admin account")
    admin.add_argument("username")
    admin.add_argument("--display-name")
    admin.set_defaults(run=create_admin)
    commands.add_parser("reconcile-annotations", help="Check annotations after a corpus rebuild").set_defaults(run=reconcile)
    args = parser.parse_args()
    return args.run(args)


if __name__ == "__main__":
    sys.exit(main())
