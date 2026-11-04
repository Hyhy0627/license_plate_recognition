import sys
from loguru import logger

# Đảm bảo console UTF-8 trên Windows
try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

logger.remove()
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level="INFO"
)
logger.add(
    "logs/alpr.log",
    rotation="10 MB",
    retention="7 days",
    level="DEBUG",
    encoding="utf-8"
)

__all__ = ["logger"]
