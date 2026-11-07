"""Email/password authentication with revocable opaque sessions."""
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import re
import secrets

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.config import settings
from src.db.models import AuthAttempt, User, UserSession
from src.db.session import get_db

router = APIRouter(prefix="/auth", tags=["Authentication"])
COOKIE_NAME = "platesight_session"


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def token_digest(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def hash_password(password, salt=None):
    salt = salt or secrets.token_bytes(16)
    key = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=32768, r=8, p=3, maxmem=64 * 1024 * 1024, dklen=32)
    return f"scrypt$32768$8$3${salt.hex()}${key.hex()}"


def verify_password(password, stored):
    try:
        kind, n, r, p, salt, key = stored.split("$")
        if (kind, n, r, p) != ("scrypt", "32768", "8", "3"):
            return False
        candidate = hash_password(password, bytes.fromhex(salt))
        return hmac.compare_digest(candidate, stored)
    except (ValueError, TypeError):
        return False


# Equal-cost password verification for an email that does not exist.
DUMMY_HASH = hash_password(secrets.token_urlsafe(32))


class Credentials(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value):
        value = value.strip().lower()
        if not re.fullmatch(r"[a-z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?\.[a-z]{2,63}", value):
            raise ValueError("Địa chỉ email không hợp lệ")
        return value


class Registration(Credentials):
    name: str = Field(min_length=2, max_length=60)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value):
        value = value.strip()
        if len(value) < 2 or any(ord(char) < 32 for char in value):
            raise ValueError("Tên cần có từ 2 đến 60 ký tự")
        return value


def public_user(user):
    return {"id": user.id, "name": user.name, "email": user.email}


def throttle(db, request, action, email):
    now = utcnow()
    since = now - timedelta(minutes=15)
    db.query(AuthAttempt).filter(AuthAttempt.created_at < since).delete(synchronize_session=False)
    ip = request.client.host if request.client else "unknown"
    limits = [(token_digest(f"ip:{action}:{ip}"), 30), (token_digest(f"email:{action}:{email}"), 10)]
    for key, limit in limits:
        if db.query(AuthAttempt).filter(AuthAttempt.key == key, AuthAttempt.created_at >= since).count() >= limit:
            db.commit()
            raise HTTPException(429, "Bạn đã thử quá nhiều lần. Vui lòng thử lại sau 15 phút.", headers={"Retry-After": "900"})
    for key, _ in limits:
        db.add(AuthAttempt(key=key, created_at=now))
    db.commit()


def get_current_user(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get(COOKIE_NAME, "")
    if not token or len(token) > 128:
        raise HTTPException(401, "Vui lòng đăng nhập để tiếp tục.")
    session = db.get(UserSession, token_digest(token))
    if session is None or session.expires_at <= utcnow():
        raise HTTPException(401, "Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.")
    user = db.get(User, session.user_id)
    if user is None:
        raise HTTPException(401, "Phiên đăng nhập không hợp lệ.")
    return user


def start_session(db, request, response, user):
    old_token = request.cookies.get(COOKIE_NAME)
    if old_token:
        db.query(UserSession).filter(UserSession.token_hash == token_digest(old_token)).delete()
    db.query(UserSession).filter(UserSession.expires_at <= utcnow()).delete()
    token = secrets.token_urlsafe(32)
    seconds = max(1, settings.AUTH_SESSION_DAYS) * 86400
    db.add(UserSession(token_hash=token_digest(token), user_id=user.id, expires_at=utcnow() + timedelta(seconds=seconds)))
    db.commit()
    response.set_cookie(COOKIE_NAME, token, max_age=seconds, httponly=True,
                        secure=settings.AUTH_COOKIE_SECURE or settings.APP_ENV == "production", samesite="lax", path="/")
    response.headers["Cache-Control"] = "no-store"
    return {"user": public_user(user)}


@router.post("/register", status_code=201)
def register(payload: Registration, request: Request, response: Response, db: Session = Depends(get_db)):
    throttle(db, request, "register", payload.email)
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(409, "Email này đã được đăng ký. Hãy đăng nhập bằng tài khoản của bạn.")
    user = User(name=payload.name, email=payload.email, password_hash=hash_password(payload.password))
    db.add(user)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Email này đã được đăng ký.")
    return start_session(db, request, response, user)


@router.post("/login")
def login(payload: Credentials, request: Request, response: Response, db: Session = Depends(get_db)):
    throttle(db, request, "login", payload.email)
    user = db.query(User).filter(User.email == payload.email).first()
    valid = verify_password(payload.password, user.password_hash if user else DUMMY_HASH)
    if user is None or not valid:
        raise HTTPException(401, "Email hoặc mật khẩu không đúng.")
    return start_session(db, request, response, user)


@router.get("/me")
def me(response: Response, user: User = Depends(get_current_user)):
    response.headers["Cache-Control"] = "no-store"
    return {"user": public_user(user)}


@router.post("/logout")
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    token = request.cookies.get(COOKIE_NAME)
    if token:
        db.query(UserSession).filter(UserSession.token_hash == token_digest(token)).delete()
        db.commit()
    response.delete_cookie(COOKIE_NAME, path="/", httponly=True, samesite="lax",
                           secure=settings.AUTH_COOKIE_SECURE or settings.APP_ENV == "production")
    return {"message": "Đã đăng xuất."}
