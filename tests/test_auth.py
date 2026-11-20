"""HTTP regression tests for auth, owner isolation, migration and session revocation."""
from datetime import timedelta
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from main import app
from src.services.authentication import LoginRateLimiter, COOKIE_NAME, token_digest, utcnow, verify_password
from src.config import settings
from src.db.models import User, UserSession, PlateHistory
from src.db.session import get_db
from src.db.migrations import initialize_database


class AuthTests(unittest.TestCase):
    def setUp(self):
        self.enterContext(patch("src.services.authentication.rate_limiter", LoginRateLimiter()))
        self.engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
        initialize_database(self.engine)
        self.sessions = sessionmaker(bind=self.engine)
        def db_override():
            with self.sessions() as session:
                yield session
        app.dependency_overrides[get_db] = db_override
        self.client = TestClient(app)
        self.other = TestClient(app)
        self.payload = {"name": "Người thử", "email": "tester@example.com", "password": "Example phrase 123"}

    def tearDown(self):
        self.client.close()
        self.other.close()
        app.dependency_overrides.clear()
        self.engine.dispose()

    def register(self, client=None, email=None):
        return (client or self.client).post("/api/auth/register", json={**self.payload, "email": email or self.payload["email"]})

    def test_register_hash_cookie_and_reload(self):
        response = self.register(email="  Tester@Example.com  ")
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()["user"]["email"], "tester@example.com")
        cookie = response.headers["set-cookie"].lower()
        self.assertIn("httponly", cookie)
        self.assertIn("samesite=lax", cookie)
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertNotIn("password", response.text)
        with self.sessions() as db:
            user = db.query(User).one()
            self.assertNotIn(self.payload["password"], user.password_hash)
            self.assertTrue(verify_password(self.payload["password"], user.password_hash))
            self.assertNotEqual(db.query(UserSession).one().token_hash, self.client.cookies.get(COOKIE_NAME))
        self.assertEqual(self.client.get("/api/auth/me").status_code, 200)

    def test_duplicate_email_and_invalid_input(self):
        self.register()
        self.assertEqual(self.register(email="TESTER@example.com").status_code, 409)
        response = self.client.post("/api/auth/register", json={**self.payload, "password": "secret"})
        self.assertEqual(response.status_code, 422)
        self.assertNotIn("secret", response.text)
        self.assertEqual(self.client.post("/api/auth/register", json={**self.payload, "email": "not-an-email"}).status_code, 422)
        self.assertEqual(self.client.post("/api/auth/register", json={**self.payload, "name": "  "}).status_code, 422)

    def test_wrong_password_logout_and_revoked_cookie(self):
        self.register()
        token = self.client.cookies.get(COOKIE_NAME)
        self.assertEqual(self.client.post("/api/auth/logout").status_code, 200)
        self.assertEqual(self.client.get("/api/auth/me").status_code, 401)
        self.other.cookies.set(COOKIE_NAME, token)
        self.assertEqual(self.other.get("/api/auth/me").status_code, 401)
        wrong = self.client.post("/api/auth/login", json={**self.payload, "password": "Wrong password"})
        missing = self.client.post("/api/auth/login", json={**self.payload, "email": "missing@example.com"})
        self.assertEqual(wrong.status_code, 401)
        self.assertEqual(wrong.json(), missing.json())
        self.assertEqual(self.client.post("/api/auth/login", json=self.payload).status_code, 200)

    def test_expired_and_forged_sessions(self):
        self.register()
        with self.sessions() as db:
            session = db.get(UserSession, token_digest(self.client.cookies.get(COOKIE_NAME)))
            session.expires_at = utcnow() - timedelta(seconds=1)
            db.commit()
        self.assertEqual(self.client.get("/api/auth/me").status_code, 401)
        self.other.cookies.set(COOKIE_NAME, "forged-session")
        self.assertEqual(self.other.get("/api/license-plates/history").status_code, 401)

    def test_protected_endpoints_and_csrf(self):
        for path in ["/api/license-plates/history", "/api/license-plates/search?plate=30", "/api/license-plates/1", "/static/cropped_plates/test.jpg"]:
            self.assertEqual(self.client.get(path).status_code, 401, path)
        self.assertEqual(self.client.post("/api/license-plates/detect", files={"file": ("test.jpg", b"test", "image/jpeg")}).status_code, 401)
        self.assertEqual(self.client.post("/api/auth/register", json=self.payload, headers={"Origin": "https://foreign.example"}).status_code, 403)
        response = self.client.post("/api/auth/register", json=self.payload, headers={"Origin": "http://localhost:3000"})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.headers["access-control-allow-origin"], "http://localhost:3000")
        self.assertEqual(response.headers["access-control-allow-credentials"], "true")

    def test_history_search_detail_and_images_are_private(self):
        owner = self.register().json()["user"]["id"]
        other = self.register(self.other, "second@example.com").json()["user"]["id"]
        with self.sessions() as db:
            for user_id in [owner, other, None]:
                db.add(PlateHistory(owner_id=user_id, plate_number="30A-123.45", confidence=.8,
                                    cropped_plate_url=f"/static/cropped_plates/private_{user_id}.jpg"))
            db.commit()
            first_id = db.query(PlateHistory).filter(PlateHistory.owner_id == owner).one().id
        self.assertEqual(self.client.get("/api/license-plates/history").json()["total"], 1)
        self.assertEqual(self.other.get("/api/license-plates/search?plate=30A").json()["total"], 1)
        self.assertEqual(self.other.get(f"/api/license-plates/{first_id}").status_code, 404)
        self.assertEqual(self.client.get(f"/api/license-plates/{first_id}").status_code, 200)
        original = settings.CROPPED_PLATES_DIR
        try:
            with tempfile.TemporaryDirectory() as directory:
                settings.CROPPED_PLATES_DIR = directory
                Path(directory, f"private_{owner}.jpg").write_bytes(b"test-image")
                path = f"/static/cropped_plates/private_{owner}.jpg"
                self.assertEqual(self.client.get(path).status_code, 200)
                self.assertEqual(self.other.get(path).status_code, 404)
        finally:
            settings.CROPPED_PLATES_DIR = original

    def test_search_normalizes_plate_and_paginates_owned_records(self):
        owner = self.register().json()["user"]["id"]
        other = self.register(self.other, "second@example.com").json()["user"]["id"]
        with self.sessions() as db:
            db.add_all([
                PlateHistory(owner_id=owner, plate_number="30A-123.45", confidence=.8)
                for _ in range(25)
            ])
            db.add(PlateHistory(owner_id=owner, plate_number="29B-888.88", confidence=.8))
            db.add(PlateHistory(owner_id=other, plate_number="30A-123.45", confidence=.8))
            db.commit()

        pages = []
        for page, expected_count in [(1, 10), (2, 10), (3, 5)]:
            response = self.client.get(f"/api/license-plates/search?plate=30a12345&page={page}&page_size=10")
            self.assertEqual(response.status_code, 200)
            body = response.json()
            self.assertEqual((body["total"], body["page"], body["page_size"]), (25, page, 10))
            self.assertEqual(len(body["results"]), expected_count)
            pages.extend(item["id"] for item in body["results"])
        self.assertEqual(len(set(pages)), 25)
        self.assertEqual(pages, sorted(pages, reverse=True))
        self.assertEqual(self.client.get("/api/license-plates/search?plate=30A-123.45").json()["total"], 25)
        self.assertEqual(self.client.get("/api/license-plates/search?plate=---").status_code, 400)
        self.assertEqual(self.client.get("/api/license-plates/search?plate=30A&page=0").status_code, 422)

    def test_login_rate_limit(self):
        for _ in range(10):
            self.assertEqual(self.client.post("/api/auth/login", json=self.payload).status_code, 401)
        response = self.client.post("/api/auth/login", json=self.payload)
        self.assertEqual(response.status_code, 429)
        self.assertIn("retry-after", response.headers)
        self.assertEqual(response.headers["retry-after"], "900")

    def test_migration_preserves_legacy_records(self):
        legacy = create_engine("sqlite://")
        with legacy.begin() as connection:
            connection.execute(text("CREATE TABLE plate_history (id INTEGER PRIMARY KEY, plate_number VARCHAR(50), confidence FLOAT, plate_type VARCHAR(50), engine_used VARCHAR(50), cropped_plate_url VARCHAR(255), annotated_image_url VARCHAR(255), created_at DATETIME)"))
            connection.execute(text("INSERT INTO plate_history(id, plate_number, confidence) VALUES (1, '30A-123.45', 0.9)"))
        initialize_database(legacy)
        initialize_database(legacy)
        with legacy.connect() as connection:
            self.assertEqual(tuple(connection.execute(text("SELECT plate_number, owner_id FROM plate_history")).one()), ("30A-123.45", None))
            self.assertEqual(connection.scalar(text("SELECT plate_number_clean FROM plate_history")), "30A12345")
        legacy.dispose()


if __name__ == "__main__":
    unittest.main()


def test_rate_limiter_ip_window_and_parallel_email(monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from src.core.exceptions import RateLimitExceededException

    limiter = LoginRateLimiter()
    monkeypatch.setattr("src.services.authentication.monotonic", lambda: 1000)
    for index in range(30):
        limiter.check("login", "ip-a", str(index))
    with unittest.TestCase().assertRaises(RateLimitExceededException):
        limiter.check("login", "ip-a", "new")
    limiter.check("register", "ip-a", "new")
    monkeypatch.setattr("src.services.authentication.monotonic", lambda: 1900)
    limiter.check("login", "ip-a", "new")

    def attempt(index):
        try:
            limiter.check("login", str(index), "same-email")
        except RateLimitExceededException:
            return False
        return True

    with ThreadPoolExecutor(max_workers=8) as pool:
        assert sum(pool.map(attempt, range(30))) == 10
