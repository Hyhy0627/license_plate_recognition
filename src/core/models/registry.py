"""Baseline model catalog. Artifact versions are pinned by models/checksums.txt."""

from dataclasses import dataclass
import hashlib
from pathlib import Path
import re


PROJECT_ROOT = Path(__file__).resolve().parents[3]
MODEL_SET_VERSION = "baseline-v1"
_VIDEO_SOURCE = (
    "https://raw.githubusercontent.com/ddkhoa2605/LicensePlateDetection/"
    "f1c732e2270becc44df1de6529372f63ef251076/"
)


@dataclass(frozen=True)
class ModelArtifact:
    path: str
    url: str | None = None
    bundled_path: str | None = None


MODELS = {
    "image-detector": ModelArtifact("models/best.pt"),
    "image-ocr": ModelArtifact("models/LP_ocr.pt"),
    "vehicle-detector": ModelArtifact(
        "models/yolov8n.pt",
        url="https://github.com/ultralytics/assets/releases/download/v8.3.0/yolov8n.pt",
    ),
    "video-detector": ModelArtifact(
        "models/video/DetectLisence_YOLO11.pt",
        url=_VIDEO_SOURCE + "DetectLisence_YOLO11.pt",
    ),
    "sequence-ocr": ModelArtifact(
        "models/video/cct_s_v1_vn.onnx", url=_VIDEO_SOURCE + "cct_s_v1_vn.onnx",
    ),
    "sequence-config": ModelArtifact(
        "models/video/cct_s_v1_vn_plate_config.yaml",
        bundled_path="src/core/video/video_ocr.yaml",
    ),
    "line-ocr": ModelArtifact("models/easyocr/english_g2.pth"),
}
IMAGE_MODELS = ("image-detector", "image-ocr")
VIDEO_PLATE_MODELS = ("video-detector", "sequence-ocr", "sequence-config")
VIDEO_MODELS = ("vehicle-detector", *VIDEO_PLATE_MODELS)


def resolve_path(value: str | Path) -> Path:
    return PROJECT_ROOT / value


def default_path(model_id: str) -> Path:
    return resolve_path(MODELS[model_id].path)


def file_sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read_checksums(path: Path) -> dict[str, str]:
    checksums = {}
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        fields = line.split(maxsplit=1)
        if len(fields) != 2 or fields[1] in checksums or not re.fullmatch("[0-9a-fA-F]{64}", fields[0]):
            raise ValueError(f"Invalid checksum entry on line {number} of {path.name}")
        digest, name = fields
        checksums[name] = digest.lower()
    return checksums
