"""HTTP access to private recognition images."""

from mimetypes import guess_type

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from src.api.auth import get_current_user
from src.api.storage_responses import media_response
from src.db.models import User
from src.db.session import get_db
from src.services import result_media


router = APIRouter()


@router.get("/static/{category}/{filename}", include_in_schema=False)
def private_result_image(
    category: str,
    filename: str,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    media = result_media.private_result_image(category, filename, user, db)
    return media_response(request, media, guess_type(filename)[0] or "application/octet-stream")
