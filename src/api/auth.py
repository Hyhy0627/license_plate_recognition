"""HTTP adapters and authentication dependency for account endpoints."""

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from src.config import settings
from src.db.models import User
from src.db.session import get_db
from src.services import authentication
from src.services.authentication import COOKIE_NAME, Credentials, Registration


router = APIRouter(prefix="/auth", tags=["Authentication"])


def get_current_user(request: Request, db: Session = Depends(get_db)):
    return authentication.get_current_user(request.cookies.get(COOKIE_NAME), db)


def _secure_cookie():
    return settings.AUTH_COOKIE_SECURE or settings.APP_ENV == "production"


def _session_response(response, grant):
    response.set_cookie(COOKIE_NAME, grant.token, max_age=grant.seconds, httponly=True,
                        secure=_secure_cookie(), samesite="lax", path="/")
    response.headers["Cache-Control"] = "no-store"
    return {"user": grant.user}


@router.post('/register', status_code=201)
def register(
    payload: Registration,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    ip = request.client.host if request.client else "unknown"
    grant = authentication.register(payload, ip, request.cookies.get(COOKIE_NAME), db)
    return _session_response(response, grant)


@router.post('/login')
def login(
    payload: Credentials,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    ip = request.client.host if request.client else "unknown"
    grant = authentication.login(payload, ip, request.cookies.get(COOKIE_NAME), db)
    return _session_response(response, grant)


@router.get('/me')
def me(response: Response, user: User = Depends(get_current_user)):
    response.headers["Cache-Control"] = "no-store"
    return {"user": authentication.public_user(user)}


@router.post('/logout')
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    authentication.logout(request.cookies.get(COOKIE_NAME), db)
    response.delete_cookie(COOKIE_NAME, path="/", httponly=True, samesite="lax", secure=_secure_cookie())
    return {"message": "Đã đăng xuất."}
