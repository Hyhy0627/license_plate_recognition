"""Image recognition orchestration, inference locking and result persistence."""

import os
import time
import uuid

import cv2
import numpy as np
from typing import BinaryIO
from src.core.exceptions import InvalidPayloadException, PayloadTooLargeException
from sqlalchemy.orm import Session

from src.services.schemas import DetectionResult, PlateDetectionResponse
from src.core.ocr.postprocessor import PlatePostprocessor
from src.core.image.plate_regions import quadrilateral_plate_regions
from src.core.image.character_regions import _ocr_character_regions
from src.services.model_runtime import get_detector, get_ocr_engine, _inference_lock
from src.config import settings
from src.db.models import PlateHistory, User
from src.utils.visualizer import draw_plate_box
from src.utils.logger import logger


def detect_license_plate(file: BinaryIO, db: Session, user: User):
    """Read local candidates, permit at most one cloud recognition call, and save
    accepted results for the authenticated owner. Regex checks structure only.
    """
    start_time = time.perf_counter()

    # Đọc file ảnh từ request
    contents = file.read(10 * 1024 * 1024 + 1)
    if len(contents) > 10 * 1024 * 1024:
        raise PayloadTooLargeException("Ảnh quá lớn. Vui lòng chọn ảnh dưới 10 MB.")
    if not contents or len(contents) == 0:
        raise InvalidPayloadException(
            "Tập tin tải lên rỗng (0 bytes). Vui lòng chọn một file ảnh hợp lệ."
        )

    try:
        nparr = np.frombuffer(contents, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    except Exception as e:
        raise InvalidPayloadException(
            f"Lỗi khi giải mã ảnh: {str(e)}"
        )

    if image is None:
        raise InvalidPayloadException(
            "Tập tin tải lên không phải là ảnh hợp lệ hoặc định dạng không được hỗ trợ"
        )

    detector = get_detector()
    ocr_engine = get_ocr_engine()

    # 1. Phát hiện biển số bằng Local YOLO Detector chính thức (tối đa 2 box tiềm năng)
    with _inference_lock:
        detections = detector.detect(image, include_low_confidence=True)

    # 2. Xử lý OCR cục bộ siêu tốc cho từng box phát hiện
    candidates = []
    has_valid_plate = False
    has_strong_plate = False
    remote_ocr = getattr(ocr_engine, "ninerouter_client", None)
    remote_ocr_available = False
    remote_calls = 0
    warnings = []
    if remote_ocr is not None:
        try:
            remote_ocr_available = remote_ocr.is_available()
        except Exception as exc:
            logger.warning(f"Không kiểm tra được 9Router Vision: {exc}")

    for det in detections:
        bbox = det["bbox"]
        conf = det["confidence"]
        plate_crop = detector.crop_plate(image, bbox)
        if plate_crop is None or plate_crop.size == 0:
            continue

        # Chạy Local YOLO OCR siêu tốc (~20ms)
        with _inference_lock:
            ocr_res = ocr_engine.recognize_local_yolo(plate_crop)
        cleaned_text = PlatePostprocessor.clean_text(ocr_res.get("raw_text", ""))
        formatted = PlatePostprocessor.format_vietnamese_plate(cleaned_text, plate_type=ocr_res.get("plate_type"), text_lines=ocr_res.get("text_lines"))
        is_valid = PlatePostprocessor.validate_plate(formatted)
        ocr_conf = float(ocr_res.get("avg_conf", 0.0))
        engine_used = ocr_res.get("engine_used", "local_yolo")

        has_valid_plate = has_valid_plate or is_valid
        # Four serial digits may be a truncated five-digit plate (regression
        # test_complete_character_crop_replaces_truncated_valid_read_without_cloud).
        serial = formatted.replace(".", "").rsplit("-", 1)[-1].rsplit(" ", 1)[-1]
        strong_candidate = is_valid and ocr_conf >= 0.70 and len(serial) == 5
        # A clear plate must not suppress rescue for another unresolved vehicle.
        has_strong_plate = strong_candidate if not candidates else has_strong_plate and strong_candidate

        candidates.append({
            "bbox": bbox,
            "conf": ocr_conf if ocr_conf > 0 else conf,
            "plate_crop": plate_crop,
            "ocr_res": ocr_res,
            "cleaned_text": cleaned_text,
            "formatted_plate": formatted,
            "is_valid": is_valid,
            "engine_used": engine_used
        })

    # Bổ sung các cụm ký tự OCR để tìm biển mà detector bỏ sót trong ảnh nhiều xe.
    # Bỏ qua cụm trùng với các box đã tìm thấy; chỉ nhận kết quả qua regex biển VN.
    if not has_strong_plate and getattr(ocr_engine, "yolo_ocr", None) is not None:
        with _inference_lock:
            proposals = _ocr_character_regions(image, ocr_engine)
        for proposal in proposals:
            x1, y1, x2, y2 = proposal["bbox"]
            proposal_area = max(1, (x2 - x1) * (y2 - y1))
            overlaps_existing = False
            for existing in candidates:
                # Cụm ký tự có thể cứu một box detector đã tìm thấy nhưng OCR bị trượt.
                if not existing["is_valid"]:
                    continue
                ex1, ey1, ex2, ey2 = existing["bbox"]
                intersection = max(0, min(x2, ex2) - max(x1, ex1)) * max(
                    0, min(y2, ey2) - max(y1, ey1)
                )
                # A detector may cut off the last character yet produce a
                # plausible four-digit plate. Only skip a character proposal
                # when nearly all of its extent was already read.
                if intersection / proposal_area >= 0.90:
                    overlaps_existing = True
                    break
            if overlaps_existing:
                continue

            plate_crop = detector.crop_plate(image, proposal["bbox"], padding=8)
            with _inference_lock:
                ocr_res = ocr_engine.recognize_local_yolo(plate_crop)
            cleaned_text = PlatePostprocessor.clean_text(ocr_res.get("raw_text", ""))
            formatted = PlatePostprocessor.format_vietnamese_plate(
                cleaned_text, plate_type=ocr_res.get("plate_type"), text_lines=ocr_res.get("text_lines")
            )
            if not PlatePostprocessor.validate_plate(formatted):
                continue
            # A complete character-supported crop supersedes a truncated read
            # of the same plate. Require spatial overlap AND contained text,
            # so nearby independent plates are never removed just for proximity.
            proposal_conf = float(ocr_res.get("avg_conf", proposal["confidence"]))
            kept = []
            for existing in candidates:
                ex1, ey1, ex2, ey2 = existing["bbox"]
                intersection = max(0, min(x2, ex2) - max(x1, ex1)) * max(0, min(y2, ey2) - max(y1, ey1))
                old_area = max(1, (ex2 - ex1) * (ey2 - ey1))
                old_text = existing["cleaned_text"]
                same_text = old_text == cleaned_text
                extended_text = len(cleaned_text) > len(old_text) and old_text in cleaned_text
                if intersection / min(old_area, proposal_area) >= 0.45 and (same_text or extended_text) and proposal_conf >= existing["conf"] - 0.10:
                    continue
                kept.append(existing)
            candidates = kept
            candidates.append({
                "bbox": proposal["bbox"],
                "conf": proposal_conf,
                "plate_crop": plate_crop,
                "ocr_res": ocr_res,
                "cleaned_text": cleaned_text,
                "formatted_plate": formatted,
                "is_valid": True,
                "engine_used": ("cct_vn_onnx" if ocr_res.get("engine_used") == "cct_vn_onnx"
                                else "local_yolo_ocr_fallback"),
            })
            has_valid_plate = True

    # A bright quadrilateral supplies real geometry when the learned detector
    # misses a rotated plate. Require observed valid OCR before accepting it.
    if not has_valid_plate and getattr(ocr_engine, "yolo_ocr", None) is not None:
        with _inference_lock:
            regions = quadrilateral_plate_regions(image)
        for region in regions:
            with _inference_lock:
                ocr_res = ocr_engine.recognize_local_yolo(region["crop"])
            region_engine = ("cct_vn_onnx" if ocr_res.get("engine_used") == "cct_vn_onnx"
                             else "local_yolo_rectified")
            cleaned_text = PlatePostprocessor.clean_text(ocr_res.get("raw_text", ""))
            formatted = PlatePostprocessor.format_vietnamese_plate(cleaned_text, ocr_res.get("plate_type"), ocr_res.get("text_lines"))
            valid = PlatePostprocessor.validate_plate(formatted) and float(ocr_res.get("avg_conf", 0)) >= 0.60
            if not valid:
                line_ocr = getattr(ocr_engine, "line_ocr", None)
                # LocalLineOCR owns a separate reader lock; its lazy disk load
                # must not block YOLO/ONNX inference in other requests.
                alternative = line_ocr.recognize(region["crop"]) if line_ocr else {}
                alternative_text = PlatePostprocessor.clean_text(alternative.get("raw_text", ""))
                alternative_formatted = PlatePostprocessor.format_vietnamese_plate(alternative_text, alternative.get("plate_type"), alternative.get("text_lines"))
                if alternative_text and PlatePostprocessor.validate_plate(alternative_formatted):
                    ocr_res, cleaned_text, formatted = alternative, alternative_text, alternative_formatted
                    valid, region_engine = True, "local_easyocr"
            candidates.append({"bbox": region["bbox"], "conf": float(ocr_res.get("avg_conf", 0)),
                               "plate_crop": region["crop"], "ocr_res": ocr_res, "cleaned_text": cleaned_text,
                               "formatted_plate": formatted, "is_valid": valid, "engine_used": region_engine})
            has_valid_plate = has_valid_plate or valid

    # Với ảnh chụp cận biển số, OCR có thể đọc tốt toàn ảnh dù chưa tạo được box ký tự.
    if not has_valid_plate and (getattr(ocr_engine, "yolo_ocr", None) is not None
                                or getattr(ocr_engine, "sequence_ocr", None) is not None):
        with _inference_lock:
            full_ocr = ocr_engine.recognize_local_yolo(image, full_scene=True)
        full_clean = PlatePostprocessor.clean_text(full_ocr.get("raw_text", ""))
        full_formatted = PlatePostprocessor.format_vietnamese_plate(
            full_clean, plate_type=full_ocr.get("plate_type"), text_lines=full_ocr.get("text_lines")
        )
        if PlatePostprocessor.validate_plate(full_formatted) and float(full_ocr.get("avg_conf", 0)) >= 0.85:
            height, width = image.shape[:2]
            candidates.append({
                "bbox": [0, 0, width, height],
                "conf": float(full_ocr["avg_conf"]),
                "plate_crop": image,
                "ocr_res": full_ocr,
                "cleaned_text": full_clean,
                "formatted_plate": full_formatted,
                "is_valid": True,
                "engine_used": ("cct_vn_onnx" if full_ocr.get("engine_used") == "cct_vn_onnx"
                                else "local_yolo_ocr_full_image"),
            })
            has_valid_plate = True

    # Spend the single remote call only after all local crops have been tried.
    # Earlier crop calls could exhaust the budget on a truncated detector box.
    if not has_valid_plate and candidates and remote_ocr_available:
        candidate = max(candidates, key=lambda c: (c["engine_used"] == "local_yolo_rectified",
                                                  c["ocr_res"].get("chars_count", 0), c["conf"]))
        try:
            remote_calls += 1
            remote_res = remote_ocr.recognize_plate(candidate["plate_crop"])
            if remote_res.get("error"):
                warnings.append("Dịch vụ OCR hỗ trợ hết thời gian chờ hoặc không phản hồi; chưa đọc được biển số từ ảnh này.")
            remote_clean = PlatePostprocessor.clean_text(remote_res.get("raw_text", ""))
            formatted = PlatePostprocessor.format_vietnamese_plate(remote_clean, remote_res.get("plate_type"), remote_res.get("text_lines"))
            if PlatePostprocessor.validate_plate(formatted) and float(remote_res.get("confidence", 0)) >= 0.65:
                candidate.update(cleaned_text=remote_clean, formatted_plate=formatted, ocr_res=remote_res,
                                 conf=float(remote_res["confidence"]), is_valid=True, engine_used="9router_vision")
                has_valid_plate = True
        except Exception as exc:
            warnings.append("Dịch vụ OCR hỗ trợ không phản hồi; chưa đọc được biển số từ ảnh này.")
            logger.warning(f"9Router không đọc được crop biển số: {type(exc).__name__}")

    # 3. Cơ chế Cứu trợ Thông minh (Self-Healing Fallback) - CHỈ GỌI DUY NHẤT 1 LẦN:
    # Chỉ gọi Vision khi các đường local chưa tìm được chuỗi biển số hợp lệ.
    if not has_valid_plate and remote_calls < 1 and remote_ocr_available:
        try:
            if remote_ocr_available:
                logger.info("Local AI không tìm thấy biển số hợp lệ. Kích hoạt Cloud Vision AI quét ảnh toàn cảnh (1 lần duy nhất)...")
                remote_calls += 1
                ai_fullimg = remote_ocr.detect_and_recognize_plate(image)
                if ai_fullimg.get("error"):
                    warnings.append("Dịch vụ OCR hỗ trợ hết thời gian chờ hoặc không phản hồi; chưa đọc được biển số từ ảnh này.")
                ai_clean = PlatePostprocessor.clean_text(ai_fullimg.get("raw_text", ""))

                # Nếu Cloud AI tìm thấy biển số chuẩn:
                if len(ai_clean) >= 6 and ai_fullimg.get("bbox"):
                    ai_bbox = ai_fullimg.get("bbox")

                    plate_crop_ai = detector.crop_plate(image, ai_bbox)
                    ai_formatted = PlatePostprocessor.format_vietnamese_plate(ai_clean, plate_type=ai_fullimg.get("plate_type"), text_lines=ai_fullimg.get("text_lines"))
                    ai_valid = PlatePostprocessor.validate_plate(ai_formatted)

                    # Thay thế hoàn toàn bằng 1 kết quả duy nhất, chính xác từ Cloud AI
                    candidates = [{
                        "bbox": ai_bbox,
                        "conf": float(ai_fullimg.get("confidence", 0.0)),
                        "plate_crop": plate_crop_ai if plate_crop_ai is not None and plate_crop_ai.size > 0 else image,
                        "ocr_res": ai_fullimg,
                        "cleaned_text": ai_clean,
                        "formatted_plate": ai_formatted,
                        "is_valid": ai_valid,
                        "engine_used": "9router_vision"
                    }]
                    logger.info(f"Cloud Vision AI cứu trợ thành công: {ai_formatted}")
        except Exception as e:
            warnings.append("Dịch vụ OCR hỗ trợ không phản hồi; chưa đọc được biển số từ ảnh này.")
            logger.warning(f"Lỗi khi gọi Cloud Vision AI: {e}")

    # 4. Lọc bỏ các box rác: nếu có ít nhất 1 box hợp lệ thì loại bỏ ngay các box trống/UNKNOWN
    if not has_valid_plate and remote_ocr is not None and not remote_ocr_available:
        warnings.append("Dịch vụ OCR hỗ trợ chưa kết nối; ảnh đã được kiểm tra bằng mô hình local.")
    valid_candidates = [c for c in candidates if c["is_valid"]]
    # Không hiện chuỗi OCR rác như một biển số nếu không qua kiểm tra cấu trúc.
    final_candidates = valid_candidates

    results = []
    created_db_items = []
    annotated_img = image.copy()

    for item in final_candidates:
        bbox = item["bbox"]
        conf = item["conf"]
        plate_crop = item["plate_crop"]
        ocr_res = item["ocr_res"]
        formatted_plate = item["formatted_plate"]
        is_valid = item["is_valid"]
        engine_used = item["engine_used"]

        # Lưu ảnh crop
        crop_filename = f"crop_{uuid.uuid4().hex}.jpg"
        crop_path = os.path.join(settings.CROPPED_PLATES_DIR, crop_filename)
        cv2.imwrite(crop_path, plate_crop)

        # Vẽ lên ảnh kết quả
        annotated_img = draw_plate_box(annotated_img, bbox, formatted_plate if formatted_plate else "LP", conf)

        res_item = DetectionResult(
            plate_number=formatted_plate or "UNKNOWN",
            confidence=round(conf, 4),
            plate_type=ocr_res.get("plate_type", "unknown"),
            bbox=bbox,
            engine_used=engine_used,
            cropped_image_url=f"/static/cropped_plates/{crop_filename}",
            annotated_image_url=None,
            is_valid_format=is_valid
        )
        results.append(res_item)

        # Lưu bản ghi vĩnh viễn vào SQLite (data/alpr.db)
        history_record = PlateHistory(
            owner_id=user.id,
            plate_number=formatted_plate or "UNKNOWN",
            confidence=conf,
            plate_type=ocr_res.get("plate_type", "unknown"),
            engine_used=engine_used,
            cropped_plate_url=f"/static/cropped_plates/{crop_filename}",
            annotated_image_url=None
        )
        db.add(history_record)
        created_db_items.append(history_record)

    # Lưu ảnh annotated
    annotated_filename = f"result_{uuid.uuid4().hex}.jpg"
    annotated_path = os.path.join(settings.FINAL_RESULTS_DIR, annotated_filename)
    cv2.imwrite(annotated_path, annotated_img)

    for r in results:
        r.annotated_image_url = f"/static/final_results/{annotated_filename}"

    # Cập nhật đường dẫn ảnh annotated vào database và commit
    if created_db_items:
        for db_item in created_db_items:
            db_item.annotated_image_url = f"/static/final_results/{annotated_filename}"
        db.commit()

    total_time_ms = round((time.perf_counter() - start_time) * 1000, 2)

    return PlateDetectionResponse(
        success=True,
        message="Nhận diện biển số thành công" if results else "Không tìm thấy biển số trong ảnh",
        total_detected=len(results),
        processing_time_ms=total_time_ms,
        results=results,
        warnings=list(dict.fromkeys(warnings)),
        cloud_attempts=remote_calls,
    )
