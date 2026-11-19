"""Replay fixed development images through the real API; keep before/after evidence.

Local mode disables cloud. Hybrid mode uses configured cloud, which is nondeterministic.
The in-process API uses a separate SQLite DB and output directory for every run.
This is a development regression check, not an independent accuracy benchmark.
"""
import argparse
import asyncio
from collections import Counter
from datetime import datetime, timezone
import hashlib
import io
import inspect
import os
import json
from pathlib import Path
import re
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def signature(text):
    """Ignore separators but retain observed prefix/serial grouping when present."""
    text = text.upper().strip()
    match = re.fullmatch(r"(\d{2}[- ]?(?:[A-Z][A-Z0-9]?|MD[0-9]))[ -](\d{3}\.\d{2}|\d{4,5})", text)
    if match:
        return tuple(re.sub(r"[^A-Z0-9]", "", part) for part in match.groups())
    return (re.sub(r"[^A-Z0-9]", "", text),)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--label", required=True)
    parser.add_argument("--mode", choices=["local", "hybrid"], default="local")
    parser.add_argument("--base-url", help="Use running HTTP backend instead of isolated API")
    parser.add_argument("--email", help="Account email for --base-url; password comes from ALPR_TEST_PASSWORD")
    parser.add_argument("--cases", type=Path)
    args = parser.parse_args()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    out = ROOT / "data" / "recognition_regression" / f"{stamp}_{args.label}"
    out.mkdir(parents=True)

    import cv2
    import numpy as np
    import torch
    torch.set_num_threads(2)
    if args.cases:
        cases = json.loads(args.cases.read_text(encoding="utf-8-sig"))["cases"]
    else:
        cases = json.loads((ROOT / "data/test_real_web/hard_cases_20261105/cases.json").read_text(encoding="utf-8-sig"))["cases"]
        for item in json.loads((ROOT / "data/test_real_web/ui_test_results.json").read_text(encoding="utf-8-sig")):
            cases.append({"id": Path(item["file"]).stem, "path": str(ROOT / "data/test_real_web" / item["file"]),
                          "kind": "real", "expected": [item["expected_plate"]]})
        for name, expected in [("xe 3.jpg", "88-G1 333.43"), ("xe 4.jpg", "29-AC 886.88")]:
            cases.append({"id": Path(name).stem, "path": str(Path("D:/ảnh") / name), "kind": "real", "expected": [expected]})
        for name in ["blank", "non_plate_text"]:
            path = out / f"{name}.png"
            canvas = np.full((480, 640, 3), 200, dtype=np.uint8)
            if name == "non_plate_text":
                cv2.putText(canvas, "PARKING 2026", (35, 220), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (20, 20, 20), 3)
            path.write_bytes(cv2.imencode(".png", canvas)[1].tobytes())
            cases.append({"id": name, "path": str(path), "kind": "negative_synthetic", "expected": []})
    for case in cases:
        case["sha256"] = digest(case["path"])
    (out / "cases.json").write_text(json.dumps({"cases": cases}, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.base_url:
        import requests
        client = requests.Session()
        if not args.email or not os.environ.get("ALPR_TEST_PASSWORD"):
            raise ValueError("HTTP mode requires --email and ALPR_TEST_PASSWORD")
        login = client.post(args.base_url.rstrip("/") + "/api/auth/login",
                            json={"email": args.email, "password": os.environ["ALPR_TEST_PASSWORD"]}, timeout=30)
        if login.status_code != 200:
            raise RuntimeError(f"Test account login failed: HTTP {login.status_code}")
        endpoint = args.base_url.rstrip("/") + "/api/license-plates/detect"
    else:
        from fastapi import UploadFile
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from src.config import settings
        from src.api import routes
        from src.db.session import Base, get_db
        from src.core.ocr_engine import PlateOCREngine
        from src.db.models import User
        for field, folder in [("CROPPED_PLATES_DIR", "crops"), ("FINAL_RESULTS_DIR", "results")]:
            target = out / folder
            target.mkdir()
            setattr(settings, field, str(target))
        db_engine = create_engine(f"sqlite:///{(out / 'history.db').as_posix()}", connect_args={"check_same_thread": False})
        Base.metadata.create_all(db_engine)
        sessions = sessionmaker(bind=db_engine)
        with sessions() as session:
            test_user = User(name="Regression test", email="regression@example.invalid", password_hash="disabled")
            session.add(test_user)
            session.commit()
            session.refresh(test_user)
            session.expunge(test_user)
        routes._ocr_engine = PlateOCREngine(engine_type="yolo" if args.mode == "local" else "hybrid")
        if routes.get_detector().model is None or routes._ocr_engine.yolo_ocr is None:
            raise RuntimeError("Required model failed to load; abort instead of measuring an empty detector")

    output = {"label": args.label, "mode": args.mode, "transport": "HTTP" if args.base_url else "direct API handler",
              "purpose": "development regression, not held-out accuracy", "threads": 2,
              "code_hashes": {str(p.relative_to(ROOT)): digest(p) for p in (ROOT / "src").rglob("*.py")},
              "model_hashes": {name: digest(ROOT / "models" / name) for name in ["best.pt", "LP_ocr.pt"]}, "cases": []}
    line_model = ROOT / "models/easyocr/english_g2.pth"
    if line_model.is_file():
        output["model_hashes"]["easyocr/english_g2.pth"] = digest(line_model)
    for case in cases:
        started = time.perf_counter()
        if args.base_url:
            with open(case["path"], "rb") as image_file:
                response = client.post(endpoint, files={"file": (Path(case["path"]).name, image_file, "image/jpeg")}, timeout=90)
            body, status_code = response.json(), response.status_code
        else:
            with sessions() as session:
                upload = UploadFile(filename=Path(case["path"]).name, file=io.BytesIO(Path(case["path"]).read_bytes()))
                result = routes.detect_license_plate(file=upload, db=session, user=test_user)
                response = asyncio.run(result) if inspect.isawaitable(result) else result
                body, status_code = response.model_dump(), 200
        actual = [p["plate_number"] for p in body.get("results", [])]
        record = {**case, "http_status": status_code, "response": body,
                  "wall_ms": round((time.perf_counter() - started) * 1000, 2),
                  "exact_grouping": status_code == 200 and Counter(map(signature, actual)) == Counter(map(signature, case["expected"]))}
        output["cases"].append(record)
        (out / "results.json").write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"id": case["id"], "expected": case["expected"], "actual": actual,
                          "exact_grouping": record["exact_grouping"], "wall_ms": record["wall_ms"]}, ensure_ascii=False), flush=True)
    if args.base_url:
        client.post(args.base_url.rstrip("/") + "/api/auth/logout", timeout=30)
        client.close()
    print(f"RESULTS: {out / 'results.json'}", flush=True)


if __name__ == "__main__":
    main()
