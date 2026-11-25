"""HTTP transport for synchronous recognition on the private worker service."""

import requests

from src.config import settings
from src.core.exceptions import ServiceUnavailableException


def recognize_image(contents: bytes, session_token: str, cookie_name: str) -> requests.Response:
    url = settings.INFERENCE_WORKER_URL.rstrip("/") + "/api/license-plates/detect"
    try:
        with requests.Session() as session:
            session.trust_env = False  # Internal credentials must stay on the worker network.
            return session.post(url, files={"file": ("upload", contents)}, cookies={cookie_name: session_token},
                                timeout=(3, 120), allow_redirects=False)
    except requests.RequestException as exc:
        raise ServiceUnavailableException("Worker nhận diện ảnh tạm thời không khả dụng.") from exc


def worker_ready() -> bool:
    try:
        with requests.Session() as session:
            session.trust_env = False
            response = session.get(settings.INFERENCE_WORKER_URL.rstrip("/") + "/api/health",
                                   timeout=(2, 3), allow_redirects=False)
        return response.status_code == 200 and response.json().get("models_loaded") is True
    except (requests.RequestException, ValueError):
        return False
