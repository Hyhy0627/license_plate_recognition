"""Create one account explicitly using ALPR_SEED_NAME/EMAIL/PASSWORD."""

import argparse
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class SeedArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        # argparse normally echoes unknown arguments, which may contain a password.
        self.exit(2, "Invalid arguments. Use --help; supply credentials through environment variables.\n")


def main() -> int:
    parser = SeedArgumentParser(description=__doc__)
    parser.parse_args()

    from pydantic import ValidationError
    from sqlalchemy.exc import SQLAlchemyError

    try:
        from src.db.seed import SeedConfigurationError, read_seed_configuration, seed_user
    except (SQLAlchemyError, ValidationError):
        print("Invalid application/database configuration; no credentials are printed.", file=sys.stderr)
        return 1

    try:
        payload = read_seed_configuration(os.environ)
    except SeedConfigurationError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    from src.db.migrations import initialize_database
    from src.db.session import engine, SessionLocal

    try:
        initialize_database(engine)
        with SessionLocal.begin() as db:
            created = seed_user(db, payload)
    except SQLAlchemyError:
        # Database exceptions can contain credentials or inserted parameters.
        print("Account creation failed. Check database configuration; no credentials are printed.", file=sys.stderr)
        return 1
    finally:
        engine.dispose()

    print("Account created." if created else "Account already exists; left unchanged.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
