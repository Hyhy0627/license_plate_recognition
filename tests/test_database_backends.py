"""Database configuration and optional integration tests against PostgreSQL."""

from concurrent.futures import ThreadPoolExecutor
from os import getenv
from uuid import uuid4

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.schema import CreateSchema, DropSchema

from src.config import settings
from src.db.migrations import initialize_database
from src.db.models import User, VideoJob
from src.db.session import build_engine
from src.services import video_jobs


def test_sqlite_memory_database_is_shared_by_sessions_on_another_thread():
    engine = build_engine("sqlite:///:memory:")
    try:
        assert isinstance(engine.pool, StaticPool)
        initialize_database(engine)
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT COUNT(*) FROM users")) == 0

        def count_users():
            with engine.connect() as connection:
                return connection.scalar(text("SELECT COUNT(*) FROM users"))

        with ThreadPoolExecutor(max_workers=1) as pool:
            assert pool.submit(count_users).result(timeout=5) == 0
    finally:
        engine.dispose()


@pytest.fixture
def postgres_engine():
    url = getenv("ALPR_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("ALPR_TEST_POSTGRES_URL is required for PostgreSQL integration")
    schema = f"alpr_test_{uuid4().hex}"
    admin = build_engine(url)
    try:
        with admin.begin() as connection:
            connection.execute(CreateSchema(schema))
        engine = build_engine(make_url(url).update_query_dict({"options": f"-csearch_path={schema}"}))
        try:
            yield engine
        finally:
            engine.dispose()
            with admin.begin() as connection:
                connection.execute(DropSchema(schema, cascade=True))
    finally:
        admin.dispose()


@pytest.mark.parametrize("legacy", [False, True])
def test_postgres_migrations_are_safe_to_repeat_from_two_connections(postgres_engine, legacy):
    engine = postgres_engine
    assert engine.pool.size() == settings.DB_POOL_SIZE
    if legacy:
        with engine.begin() as connection:
            connection.execute(text(
                "CREATE TABLE plate_history (id SERIAL PRIMARY KEY, plate_number VARCHAR(50), confidence FLOAT, "
                "plate_type VARCHAR(50), engine_used VARCHAR(50), cropped_plate_url VARCHAR(255), "
                "annotated_image_url VARCHAR(255), created_at TIMESTAMP)"
            ))
            connection.execute(text("INSERT INTO plate_history (plate_number, confidence) VALUES ('30A-123.45', 0.9)"))

    with ThreadPoolExecutor(max_workers=2) as pool:
        first, second = (pool.submit(initialize_database, engine) for _ in range(2))
        first.result(timeout=15)
        second.result(timeout=15)

    with engine.connect() as connection:
        schema = inspect(connection)
        assert {"users", "user_sessions", "plate_history", "video_jobs"}.issubset(schema.get_table_names())
        index_names = {item["name"] for item in schema.get_indexes("plate_history")}
        assert {"ix_plate_history_owner_id", "ix_plate_history_plate_number_clean"} <= index_names
        assert any(key["referred_table"] == "users" for key in schema.get_foreign_keys("plate_history"))
        rows = connection.execute(text("SELECT plate_number_clean, owner_id FROM plate_history")).all()
        assert rows == ([("30A12345", None)] if legacy else [])


def test_postgres_job_lease_is_visible_to_other_api_connections(postgres_engine, monkeypatch):
    initialize_database(postgres_engine)
    sessions = sessionmaker(bind=postgres_engine)
    monkeypatch.setattr(video_jobs, "SessionLocal", sessions)
    with sessions.begin() as db:
        db.add(User(id=41, name="Test owner", email="test@example.com", password_hash="disabled"))
        db.flush()
        db.add_all([
            VideoJob(id="live", owner_id=41, filename="clip.mp4", status="running"),
            VideoJob(id="interrupted", owner_id=41, filename="clip.mp4", status="running"),
        ])
    lease = video_jobs._job_lock("live")
    lease.acquire()
    owner = User(id=41)
    try:
        video_jobs._reserve_job("next", owner.id, "next.mp4", "fast")
        assert video_jobs.get_video_job("live", owner)["status"] == "running"
        assert video_jobs.get_video_job("interrupted", owner)["status"] == "failed"
    finally:
        lease.release()
    assert video_jobs.get_video_job("live", owner)["status"] == "failed"
    video_jobs._set_job("live", status="completed")
    assert video_jobs.get_video_job("live", owner)["status"] == "failed"
