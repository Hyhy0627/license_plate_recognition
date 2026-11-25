"""Owner isolation and request admission for the new history operations."""

from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.core.exceptions import EntityNotFoundException, RateLimitExceededException
from src.db.models import PlateHistory, VideoJob
from src.db.session import Base
from src.services import history, video_jobs
from src.services.inference_rate_limit import InferenceRateLimiter
from src.core.video.tracker import associate_plates


def test_history_export_and_delete_only_touch_owner(tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'history.db').as_posix()}")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add_all([
            PlateHistory(owner_id=1, plate_number="30A-123.45", confidence=.9),
            PlateHistory(owner_id=2, plate_number="59-G2 777.77", confidence=.8),
        ])
        db.commit()
        own = SimpleNamespace(id=1)
        other = SimpleNamespace(id=2)
        item = history.export_history(db, own)[0]
        assert [row.plate_number for row in history.export_history(db, other)] == ["59-G2 777.77"]
        with pytest.raises(EntityNotFoundException):
            history.delete_detection(item.id, db, other)
        history.delete_detection(item.id, db, own)
        assert history.delete_history(db, own) == 0
        assert len(history.export_history(db, other)) == 1
    engine.dispose()


def test_inference_limit_is_scoped_to_kind_and_user(monkeypatch):
    from src.services import inference_rate_limit as limits
    monkeypatch.setattr(limits.settings, "REDIS_URL", "")
    limiter = InferenceRateLimiter()
    for _ in range(3):
        limiter.check("video", 1)
    with pytest.raises(RateLimitExceededException):
        limiter.check("video", 1)
    limiter.check("image", 1)
    limiter.check("video", 2)


def test_video_list_and_delete_respect_owner_and_active_jobs(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{(tmp_path / 'video.db').as_posix()}")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    with sessions.begin() as db:
        db.add_all([
            VideoJob(id="finished", owner_id=1, filename="one.mp4", status="completed"),
            VideoJob(id="working", owner_id=1, filename="two.mp4", status="running"),
            VideoJob(id="private", owner_id=2, filename="other.mp4", status="completed"),
        ])
    deleted = []
    monkeypatch.setattr(video_jobs, "SessionLocal", sessions)
    monkeypatch.setattr(video_jobs, "get_storage", lambda **kwargs: SimpleNamespace(
        delete_file=lambda category, filename: deleted.append(filename)))
    own = SimpleNamespace(id=1)
    assert video_jobs.list_video_jobs(1, 10, own)["total"] == 2
    with pytest.raises(EntityNotFoundException):
        video_jobs.delete_video_job("private", own)
    with pytest.raises(Exception, match="đã kết thúc"):
        video_jobs.delete_video_job("working", own)
    video_jobs.delete_video_job("finished", own)
    assert deleted == ["finished.mp4"]
    assert video_jobs.list_video_jobs(1, 10, own)["total"] == 1
    engine.dispose()


def test_motorcycle_plate_is_not_attached_to_upper_overlapping_vehicle():
    vehicles = [
        {"track_id": 1, "vehicle_type": "Xe máy", "bbox": [0, 30, 100, 130]},
        {"track_id": 2, "vehicle_type": "Xe máy", "bbox": [0, 0, 100, 100]},
    ]
    plate = {"bbox": [35, 40, 70, 60]}
    assigned = associate_plates(vehicles, [plate])
    assert sum(len(group) for group in assigned.values()) == 1
    assert assigned[2] == [plate]


def test_plate_association_prefers_consistent_position_in_existing_track():
    vehicles = [
        {"track_id": 1, "vehicle_type": "Xe máy", "bbox": [0, 0, 100, 100]},
        {"track_id": 2, "vehicle_type": "Xe máy", "bbox": [0, 0, 100, 100]},
    ]
    plate = {"bbox": [40, 65, 60, 85]}
    assigned = associate_plates(vehicles, [plate], {1: (.1, .4), 2: (.5, .75)})
    assert assigned[2] == [plate]
