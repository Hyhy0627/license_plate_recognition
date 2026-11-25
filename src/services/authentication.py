"""Registration, opaque sessions, validation and authentication policy."""

from collections import Counter, deque
from threading import Lock
from time import monotonic
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import re
import secrets

from dataclasses import dataclass
from pydantic import BaseModel, Field, field_validator
from redis.exceptions import RedisError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.config import settings
from src.core.exceptions import (AuthenticationException, RateLimitExceededException, ResourceConflictException,
                                 ServiceUnavailableException)
from src.db.models import User, UserSession
from src.services.redis_runtime import redis_client


COOKIE_NAME = 'platesight_session'
LOGIN_WINDOW = 900
IP_ATTEMPT_LIMIT = 30
EMAIL_ATTEMPT_LIMIT = 10
LIMIT_MESSAGE = "Bạn đã thử quá nhiều lần. Vui lòng thử lại sau 15 phút."


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def token_digest(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def hash_password(password, salt=None):
    salt = salt or secrets.token_bytes(16)
    key = hashlib.scrypt(password.encode('utf-8'), salt=salt, n=32768, r=8, p=3, maxmem=64 * 1024 * 1024, dklen=32)
    return f'scrypt$32768$8$3${salt.hex()}${key.hex()}'


def verify_password(password, stored):
    try:
        kind, n, r, p, salt, key = stored.split('$')
        if (kind, n, r, p) != ('scrypt', '32768', '8', '3'):
            return False
        candidate = hash_password(password, bytes.fromhex(salt))
        return hmac.compare_digest(candidate, stored)
    except (ValueError, TypeError):
        return False


DUMMY_HASH = hash_password(secrets.token_urlsafe(32))


class Credentials(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128)

    @field_validator('email')
    @classmethod
    def normalize_email(cls, value):
        value = value.strip().lower()
        if not re.fullmatch("[a-z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?\\.[a-z]{2,63}", value):
            raise ValueError('Địa chỉ email không hợp lệ')
        return value


class Registration(Credentials):
    name: str = Field(min_length=2, max_length=60)
    password: str = Field(min_length=8, max_length=128)

    @field_validator('name')
    @classmethod
    def normalize_name(cls, value):
        value = value.strip()
        if len(value) < 2 or any((ord(char) < 32 for char in value)):
            raise ValueError('Tên cần có từ 2 đến 60 ký tự')
        return value


def public_user(user):
    return {'id': user.id, 'name': user.name, 'email': user.email}


class LoginRateLimiter:
    """Each accepted attempt expires once, in time order, across both keys."""

    window = LOGIN_WINDOW

    def __init__(self):
        self._attempts = deque()
        self._counts = Counter()
        self._lock = Lock()

    def check(self, action, ip, email):
        keys = ((action, "ip", ip), (action, "email", email))
        with self._lock:
            now = monotonic()
            while self._attempts and self._attempts[0][0] <= now - self.window:
                _, expired = self._attempts.popleft()
                for key in expired:
                    self._counts[key] -= 1
                    if not self._counts[key]:
                        del self._counts[key]
            if self._counts[keys[0]] >= IP_ATTEMPT_LIMIT or self._counts[keys[1]] >= EMAIL_ATTEMPT_LIMIT:
                raise RateLimitExceededException(LIMIT_MESSAGE, retry_after=self.window)
            self._counts.update(keys)
            self._attempts.append((now, keys))


_SLIDING_WINDOW = """
local time = redis.call('TIME')
local now = time[1] * 1000 + math.floor(time[2] / 1000)
local window = tonumber(ARGV[1])
for i = 1, #KEYS do
    redis.call('ZREMRANGEBYSCORE', KEYS[i], '-inf', now - window)
end
for i = 1, #KEYS do
    if redis.call('ZCARD', KEYS[i]) >= tonumber(ARGV[i + 2]) then return 0 end
end
for i = 1, #KEYS do
    redis.call('ZADD', KEYS[i], now, ARGV[2])
    redis.call('PEXPIRE', KEYS[i], window)
end
return 1
"""


class RedisLoginRateLimiter:
    """Count accepted attempts for both keys in one Redis transaction."""

    window = LOGIN_WINDOW

    def __init__(self, client, namespace):
        self.prefix = f"{{{namespace}}}:auth"
        self.check_window = client.register_script(_SLIDING_WINDOW)

    def check(self, action, ip, email):
        keys = [f"{self.prefix}:{action}:{kind}:{token_digest(value or '')}"
                for kind, value in (("ip", ip), ("email", email))]
        try:
            allowed = self.check_window(
                keys=keys, args=[self.window * 1000, secrets.token_hex(16), IP_ATTEMPT_LIMIT, EMAIL_ATTEMPT_LIMIT],
            )
        except RedisError as exc:
            raise ServiceUnavailableException("Tạm thời không thể kiểm tra giới hạn xác thực.") from exc
        if not allowed:
            raise RateLimitExceededException(LIMIT_MESSAGE, retry_after=self.window)


rate_limiter = (RedisLoginRateLimiter(redis_client(settings.REDIS_URL), settings.REDIS_NAMESPACE)
                if settings.REDIS_URL else LoginRateLimiter())


def _session_key(token: str) -> str:
    return f"{{{settings.REDIS_NAMESPACE}}}:session:{token_digest(token)}"


def get_current_user(token: str | None, db: Session):
    if not token or len(token) > 128:
        raise AuthenticationException('Vui lòng đăng nhập để tiếp tục.')
    if settings.SESSION_BACKEND == "redis":
        try:
            user_id = redis_client(settings.REDIS_URL).get(_session_key(token))
        except RedisError as exc:
            raise ServiceUnavailableException("Tạm thời không thể kiểm tra phiên đăng nhập.") from exc
        user_id = int(user_id) if user_id is not None else None
    else:
        session = db.get(UserSession, token_digest(token))
        user_id = session.user_id if session is not None and session.expires_at > utcnow() else None
    if user_id is None:
        raise AuthenticationException('Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.')
    user = db.get(User, user_id)
    if user is None:
        raise AuthenticationException('Phiên đăng nhập không hợp lệ.')
    return user


@dataclass
class SessionGrant:
    user: dict
    token: str
    seconds: int


def start_session(db, old_token, user):
    token = secrets.token_urlsafe(32)
    seconds = max(1, settings.AUTH_SESSION_DAYS) * 86400
    if settings.SESSION_BACKEND == "redis":
        owner = public_user(user)
        db.commit()
        try:
            with redis_client(settings.REDIS_URL).pipeline(transaction=True) as tx:
                tx.set(_session_key(token), owner["id"], ex=seconds)
                if old_token:
                    tx.delete(_session_key(old_token))
                tx.execute()
        except RedisError as exc:
            raise ServiceUnavailableException("Tạm thời không thể tạo phiên đăng nhập.") from exc
        return SessionGrant(owner, token, seconds)

    if old_token:
        db.query(UserSession).filter(UserSession.token_hash == token_digest(old_token)).delete()
    db.query(UserSession).filter(UserSession.expires_at <= utcnow()).delete()
    db.add(UserSession(token_hash=token_digest(token), user_id=user.id, expires_at=utcnow() + timedelta(seconds=seconds)))
    db.commit()
    return SessionGrant(public_user(user), token, seconds)


def register(payload: Registration, ip: str, old_token: str | None, db: Session):
    rate_limiter.check('register', ip, payload.email)
    if db.query(User).filter(User.email == payload.email).first():
        raise ResourceConflictException('Email này đã được đăng ký. Hãy đăng nhập bằng tài khoản của bạn.')
    user = User(name=payload.name, email=payload.email, password_hash=hash_password(payload.password))
    db.add(user)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise ResourceConflictException('Email này đã được đăng ký.')
    return start_session(db, old_token, user)


def login(payload: Credentials, ip: str, old_token: str | None, db: Session):
    rate_limiter.check('login', ip, payload.email)
    user = db.query(User).filter(User.email == payload.email).first()
    valid = verify_password(payload.password, user.password_hash if user else DUMMY_HASH)
    if user is None or not valid:
        raise AuthenticationException('Email hoặc mật khẩu không đúng.')
    return start_session(db, old_token, user)


def logout(token: str | None, db: Session):
    if token:
        if settings.SESSION_BACKEND == "redis":
            try:
                redis_client(settings.REDIS_URL).delete(_session_key(token))
            except RedisError as exc:
                raise ServiceUnavailableException("Tạm thời không thể kết thúc phiên đăng nhập.") from exc
        else:
            db.query(UserSession).filter(UserSession.token_hash == token_digest(token)).delete()
            db.commit()
