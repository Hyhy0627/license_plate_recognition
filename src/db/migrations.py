"""Small idempotent migration for the existing SQLite project database."""
from sqlalchemy import inspect, text
from src.db.session import Base
from src.db import models  # register all tables


def initialize_database(engine):
    Base.metadata.create_all(bind=engine)
    columns = {column["name"] for column in inspect(engine).get_columns("plate_history")}
    if "owner_id" not in columns:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE plate_history ADD COLUMN owner_id INTEGER REFERENCES users(id)"))
    for index in models.PlateHistory.__table__.indexes:
        index.create(bind=engine, checkfirst=True)
