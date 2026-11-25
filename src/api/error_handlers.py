"""Translate domain and request validation errors into the public HTTP contract."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from src.core import exceptions


DOMAIN_STATUS = {
    exceptions.InvalidPayloadException: 400,
    exceptions.AuthenticationException: 401,
    exceptions.PermissionDeniedException: 403,
    exceptions.EntityNotFoundException: 404,
    exceptions.ResourceConflictException: 409,
    exceptions.PayloadTooLargeException: 413,
    exceptions.RateLimitExceededException: 429,
    exceptions.ServiceUnavailableException: 503,
}


async def domain_error(request: Request, exc: exceptions.ALPRDomainException):
    headers = {}
    if isinstance(exc, exceptions.RateLimitExceededException) and exc.retry_after is not None:
        headers["Retry-After"] = str(exc.retry_after)
    return JSONResponse({"detail": str(exc)}, status_code=DOMAIN_STATUS[type(exc)], headers=headers)


async def validation_error(request: Request, exc: RequestValidationError):
    # Do not echo submitted passwords in Pydantic's default input error field.
    return JSONResponse(status_code=422, content={
        "detail": "Thông tin chưa hợp lệ. Kiểm tra email, tên (2–60 ký tự) và mật khẩu (8–128 ký tự khi đăng ký)."
        if request.url.path.startswith("/api/auth/") else "Dữ liệu yêu cầu không hợp lệ.",
        "fields": [str(error["loc"][-1]) for error in exc.errors()],
    })


def configure_error_handlers(app: FastAPI):
    app.add_exception_handler(exceptions.ALPRDomainException, domain_error)
    app.add_exception_handler(RequestValidationError, validation_error)
