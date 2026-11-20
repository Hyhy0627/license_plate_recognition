"""Clone the pinned upstream repo and install its paired video models."""

import hashlib
from pathlib import Path
import shutil
import subprocess


ROOT = Path(__file__).resolve().parent.parent
REPOSITORY = "https://github.com/ddkhoa2605/LicensePlateDetection.git"
REVISION = "f1c732e2270becc44df1de6529372f63ef251076"
FILES = {
    "DetectLisence_YOLO11.pt": "83a6d061c2bcc83d2660b58b6353ded064b11282205000850d5692eefdb690cd",
    "cct_s_v1_vn.onnx": "99f0ac35f0dd3cf8231c8972d8ee6bd66672bde368c6481f070b164242f128fd",
}
CONFIG = "cct_s_v1_vn_plate_config.yaml"
CONFIG_SHA256 = "8ade332ef026520a3360a7c154cc10be664bee25482f3997bce34a7007b4786e"


def main():
    upstream = ROOT / "external/LicensePlateDetection"
    if not upstream.exists():
        upstream.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "clone", "--no-checkout", REPOSITORY, str(upstream)], check=True)
        subprocess.run(["git", "-C", str(upstream), "checkout", "--detach", REVISION], check=True)
    revision = subprocess.check_output(["git", "-C", str(upstream), "rev-parse", "HEAD"], text=True).strip()
    if revision != REVISION:
        raise SystemExit(f"Unexpected upstream revision: {revision}. Expected {REVISION}.")
    for name, expected in FILES.items():
        if hashlib.sha256((upstream / name).read_bytes()).hexdigest() != expected:
            raise SystemExit(f"Model checksum mismatch: {name}")
    config_bytes = (upstream / CONFIG).read_bytes().replace(b"\r\n", b"\n")
    if hashlib.sha256(config_bytes).hexdigest() != CONFIG_SHA256:
        raise SystemExit("OCR configuration checksum mismatch")
    destination = ROOT / "models/video"
    destination.mkdir(parents=True, exist_ok=True)
    for name in (*FILES, CONFIG):
        shutil.copy2(upstream / name, destination / name)
        print(f"Installed {destination / name}")


if __name__ == "__main__":
    main()
