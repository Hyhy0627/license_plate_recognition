"""Compatibility command for the video plate detector and sequence OCR."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.download_models import main
from src.core.models.registry import VIDEO_PLATE_MODELS


if __name__ == "__main__":
    raise SystemExit(main(default_models=VIDEO_PLATE_MODELS))
