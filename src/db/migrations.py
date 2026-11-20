"""Idempotent schema initialization for the existing SQLite database.

This module never seeds accounts or changes user passwords. Explicit account
creation is handled by scripts/seed_user.py and src/db/seed.py.
"""
from sqlalchemy import inspect, text
from src.core.ocr.postprocessor import PlatePostprocessor
from src.db.session import Base
from src.db import models  # register all tables


def initialize_database(engine):
    """Create missing schema/indexes and preserve existing account data."""
    with engine.begin() as connection:
        if engine.dialect.name == "sqlite":
            connection.exec_driver_sql("BEGIN IMMEDIATE")
        Base.metadata.create_all(bind=connection)
        columns = {column["name"] for column in inspect(connection).get_columns("plate_history")}
        if "owner_id" not in columns:
            connection.execute(text("ALTER TABLE plate_history ADD COLUMN owner_id INTEGER REFERENCES users(id)"))
        if "plate_number_clean" not in columns:
            connection.execute(text("ALTER TABLE plate_history ADD COLUMN plate_number_clean VARCHAR(50)"))
        for index in models.PlateHistory.__table__.indexes:
            index.create(bind=connection, checkfirst=True)
        # Handle upgrades and any rows inserted by an older version during rollout.
        while rows := connection.execute(text(
            "SELECT id, plate_number FROM plate_history WHERE plate_number_clean IS NULL LIMIT 500"
        )).all():
            connection.execute(text("UPDATE plate_history SET plate_number_clean=:clean WHERE id=:id"), [
                {"id": row.id, "clean": PlatePostprocessor.clean_text(row.plate_number)} for row in rows
            ])
