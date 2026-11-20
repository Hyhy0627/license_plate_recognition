import sys
from loguru import logger

# Đảm bảo console UTF-8 trên Windows
try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

logger.remove()
logger.configure(extra={"request_id": "-"})
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | {extra[request_id]} | <cyan>{name}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level="INFO"
)
logger.add(
    "logs/alpr.log",
    format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {extra[request_id]} | {name}:{line} - {message}",
    rotation="10 MB",
    retention="7 days",
    level="DEBUG",
    encoding="utf-8"
)

__all__ = ["logger"]
