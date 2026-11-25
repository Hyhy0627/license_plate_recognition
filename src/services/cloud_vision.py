"""Bind the cloud vision port for OCR modes that allow remote fallback."""

from functools import lru_cache

from src.config import settings
from src.core.integrations.base import ICloudVisionClient
from src.utils.logger import logger


@lru_cache(maxsize=1)
def _get_ninerouter_client() -> ICloudVisionClient | None:
    try:
        from src.infrastructure.ninerouter_vision import NineRouterVisionClient

        client = NineRouterVisionClient()
    except Exception as exc:
        logger.warning(f"Chưa khởi tạo 9Router Vision Client: {exc}")
        return None
    logger.info(f"9Router Vision Client initialized (Model: {settings.NINEROUTER_MODEL})")
    return client


def get_cloud_vision_client(engine_type: str) -> ICloudVisionClient | None:
    if engine_type in {"hybrid", "9router"}:
        return _get_ninerouter_client()
    return None
