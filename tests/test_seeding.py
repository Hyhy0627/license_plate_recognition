"""Account seeding must be explicit, idempotent and keep credentials private."""

import os
from pathlib import Path
import secrets
import subprocess
import sys
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from src.services.authentication import verify_password
from src.db.migrations import initialize_database
from src.db.models import AuthAttempt, User, UserSession
from src.db.seed import SeedConfigurationError, read_seed_configuration, seed_user


ROOT = Path(__file__).resolve().parents[1]


def seed_environment():
    return {
        "ALPR_SEED_NAME": "  Seed user  ",
        "ALPR_SEED_EMAIL": "  Seed@Example.invalid  ",
        "ALPR_SEED_PASSWORD": secrets.token_urlsafe(24),
    }


def test_schema_initialization_never_creates_accounts():
    engine = create_engine("sqlite://")
    try:
        initialize_database(engine)
        initialize_database(engine)
        with Session(engine) as db:
            for model in (User, UserSession, AuthAttempt):
                assert db.scalar(select(func.count()).select_from(model)) == 0
    finally:
        engine.dispose()


def test_seed_configuration_requires_all_values_and_never_echoes_bad_password():
    with pytest.raises(SeedConfigurationError, match="ALPR_SEED_NAME"):
        read_seed_configuration({})
    environ = seed_environment()
    invalid_password = secrets.token_hex(2)
    environ["ALPR_SEED_PASSWORD"] = invalid_password
    with pytest.raises(SeedConfigurationError) as error:
        read_seed_configuration(environ)
    assert invalid_password not in str(error.value)
    environ["ALPR_SEED_PASSWORD"] = secrets.token_urlsafe(24)
    environ["ALPR_SEED_EMAIL"] = "invalid"
    with pytest.raises(SeedConfigurationError):
        read_seed_configuration(environ)


def test_seed_hashes_password_and_repeated_seed_preserves_existing_account():
    engine = create_engine("sqlite://")
    initialize_database(engine)
    environ = seed_environment()
    first = read_seed_configuration(environ)
    try:
        with Session(engine) as db, db.begin():
            assert seed_user(db, first) is True
        with Session(engine) as db:
            user = db.scalar(select(User))
            original = (user.id, user.name, user.email, user.password_hash)
            assert user.email == "seed@example.invalid"
            assert user.name == "Seed user"
            assert verify_password(first.password, user.password_hash)
            assert first.password not in user.password_hash
        environ.update(ALPR_SEED_NAME="Different name", ALPR_SEED_PASSWORD=secrets.token_urlsafe(24))
        with Session(engine) as db, db.begin():
            assert seed_user(db, read_seed_configuration(environ)) is False
        with Session(engine) as db:
            user = db.scalar(select(User))
            assert (user.id, user.name, user.email, user.password_hash) == original
            assert db.scalar(select(func.count()).select_from(User)) == 1
            assert db.scalar(select(func.count()).select_from(UserSession)) == 0
    finally:
        engine.dispose()


def run_seed(database, values):
    environ = {key: value for key, value in os.environ.items() if not key.startswith("ALPR_SEED_")}
    environ.update(values, DATABASE_URL=f"sqlite:///{database.as_posix()}", PYTHONUTF8="1")
    return subprocess.run(
        [sys.executable, "-B", str(ROOT / "scripts/seed_user.py")],
        cwd=ROOT, env=environ, capture_output=True, text=True, encoding="utf-8", timeout=15,
    )


def test_cli_with_missing_configuration_does_not_create_database(tmp_path):
    database = tmp_path / "uncreated.db"
    result = run_seed(database, {})
    assert result.returncode == 2
    assert "ALPR_SEED_PASSWORD" in result.stderr
    assert not database.exists()


def test_cli_creates_only_requested_user_and_does_not_print_credentials(tmp_path):
    database = tmp_path / "seed.db"
    values = seed_environment()
    result = run_seed(database, values)
    assert result.returncode == 0, result.stderr
    assert values["ALPR_SEED_PASSWORD"] not in result.stdout + result.stderr
    assert "scrypt$" not in result.stdout + result.stderr
    second = run_seed(database, values)
    assert second.returncode == 0
    assert "left unchanged" in second.stdout
    engine = create_engine(f"sqlite:///{database.as_posix()}")
    try:
        with Session(engine) as db:
            assert db.scalar(select(func.count()).select_from(User)) == 1
            user = db.scalar(select(User))
            assert verify_password(values["ALPR_SEED_PASSWORD"], user.password_hash)
            assert db.scalar(select(func.count()).select_from(UserSession)) == 0
    finally:
        engine.dispose()


def test_cli_database_failure_does_not_echo_secret_parameters(monkeypatch, capsys):
    from sqlalchemy.exc import SQLAlchemyError
    from scripts.seed_user import main
    from src.db import migrations, session

    values = seed_environment()
    for key, value in values.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(sys, "argv", ["seed_user.py"])
    monkeypatch.setattr(session, "engine", SimpleNamespace(dispose=lambda: None))

    def fail_initialization(_engine):
        raise SQLAlchemyError("private database parameters: " + values["ALPR_SEED_PASSWORD"])

    monkeypatch.setattr(migrations, "initialize_database", fail_initialization)
    assert main() == 1
    output = capsys.readouterr()
    assert "Account creation failed" in output.err
    assert "private database parameters" not in output.err
    assert values["ALPR_SEED_PASSWORD"] not in output.out + output.err


@pytest.mark.parametrize("argument", ["--password", "--help="])
def test_cli_invalid_arguments_do_not_echo_values(argument, tmp_path):
    private_value = secrets.token_urlsafe(24)
    args = [argument + private_value] if argument.endswith("=") else [argument, private_value]
    result = subprocess.run(
        [sys.executable, "-B", str(ROOT / "scripts/seed_user.py"), *args],
        cwd=tmp_path, capture_output=True, text=True, encoding="utf-8", timeout=15,
    )
    assert result.returncode == 2
    assert private_value not in result.stdout + result.stderr
