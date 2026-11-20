"""Explicit account creation; never called by application startup or migration."""

from collections.abc import Mapping

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.services.authentication import Registration, hash_password
from src.db.models import User


class SeedConfigurationError(ValueError):
    """A seed configuration error safe to display without submitted values."""


def read_seed_configuration(environ: Mapping[str, str]) -> Registration:
    """Read process environment only, using the registration validation policy."""
    names = ("ALPR_SEED_NAME", "ALPR_SEED_EMAIL", "ALPR_SEED_PASSWORD")
    missing = [name for name in names if not environ.get(name)]
    if missing:
        raise SeedConfigurationError("Missing environment variables: " + ", ".join(missing))
    try:
        return Registration(
            name=environ["ALPR_SEED_NAME"],
            email=environ["ALPR_SEED_EMAIL"],
            password=environ["ALPR_SEED_PASSWORD"],
        )
    except ValidationError:
        # Pydantic's default exception includes the submitted password in input.
        raise SeedConfigurationError(
            "Invalid seed configuration: name must contain 2–60 characters, "
            "email must be valid and password must contain 8–128 characters."
        ) from None


def seed_user(db: Session, payload: Registration) -> bool:
    """Create one account within the caller's transaction; preserve existing users.

    Returns True for a new user and False when the normalized email exists.
    No session/cookie is created and no existing password/name is overwritten.
    """
    if db.scalar(select(User.id).where(User.email == payload.email)) is not None:
        return False
    db.add(User(
        name=payload.name,
        email=payload.email,
        password_hash=hash_password(payload.password),
    ))
    db.flush()
    return True
