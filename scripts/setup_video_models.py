"""Install checksum-verified video weights; recognition code is already in src/core."""

import hashlib
from pathlib import Path
import shutil
import tempfile
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parent.parent
MODEL_BASE_URL = (
    "https://raw.githubusercontent.com/ddkhoa2605/LicensePlateDetection/"
    "f1c732e2270becc44df1de6529372f63ef251076/"
)
FILES = {
    "DetectLisence_YOLO11.pt": "83a6d061c2bcc83d2660b58b6353ded064b11282205000850d5692eefdb690cd",
    "cct_s_v1_vn.onnx": "99f0ac35f0dd3cf8231c8972d8ee6bd66672bde368c6481f070b164242f128fd",
}
CONFIG = "cct_s_v1_vn_plate_config.yaml"
CONFIG_SHA256 = "8ade332ef026520a3360a7c154cc10be664bee25482f3997bce34a7007b4786e"


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    config_bytes = (ROOT / "src/core/video_ocr.yaml").read_bytes().replace(b"\r\n", b"\n")
    if hashlib.sha256(config_bytes).hexdigest() != CONFIG_SHA256:
        raise SystemExit("OCR configuration checksum mismatch")
    destination = ROOT / "models/video"
    destination.mkdir(parents=True, exist_ok=True)
    for name, expected in FILES.items():
        target = destination / name
        if target.is_file() and sha256(target) == expected:
            print(f"Verified {target}")
            continue
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=destination, suffix=".download", delete=False) as output:
                temporary = Path(output.name)
                with urlopen(MODEL_BASE_URL + name, timeout=60) as response:
                    shutil.copyfileobj(response, output)
            if sha256(temporary) != expected:
                raise SystemExit(f"Model checksum mismatch: {name}")
            temporary.replace(target)
            print(f"Installed {target}")
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
    (destination / CONFIG).write_bytes(config_bytes)
    print(f"Installed {destination / CONFIG}")


if __name__ == "__main__":
    main()
