import time
import os
import uuid
from threading import Lock
import cv2
import numpy as np
from fastapi import APIRouter, UploadFile, File, HTTPException, Query, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from src.api.schemas import PlateDetectionResponse, DetectionResult, DetectionHistoryResponse
from src.core.detector import LicensePlateDetector
from src.core.ocr_engine import PlateOCREngine
from src.core.postprocessor import PlatePostprocessor
from src.core.plate_regions import quadrilateral_plate_regions
from src.utils.visualizer import draw_plate_box
from src.config import settings
from src.db.session import get_db
from src.db.models import PlateHistory, User
from src.api.auth import get_current_user
from src.utils.logger import logger

router = APIRouter(prefix="/license-plates", tags=["License Plates"])

_detector = None
_ocr_engine = None
_inference_lock = Lock()


def _ocr_character_regions(image, ocr_engine):
    """Propose plate crops from grouped character detections when plate YOLO misses."""
    character_model = getattr(ocr_engine, "yolo_ocr", None)
    if character_model is None:
        return []

    try:
        # Preserve small characters in full-scene images, including additional
        # plates that the detector missed. Crop OCR still runs at normal size.
        prediction = character_model.predict(image, conf=0.15, imgsz=1280, agnostic_nms=True, verbose=False)[0]
        boxes = []
        for box in prediction.boxes:
            x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().tolist()
            confidence = float(box.conf[0].cpu().numpy())
            if x2 > x1 and y2 > y1:
                boxes.append({"bbox": [x1, y1, x2, y2], "confidence": confidence})
    except Exception as exc:
        logger.warning(f"OCR character fallback failed: {exc}")
        return []

    # OCR can return multiple classes for the same glyph. Keep the best box.
    boxes.sort(key=lambda item: item["confidence"], reverse=True)
    unique = []
    for candidate in boxes:
        x1, y1, x2, y2 = candidate["bbox"]
        cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
        height = y2 - y1
        if any(
            abs(cx - (b["bbox"][0] + b["bbox"][2]) / 2) < 0.3 * height
            and abs(cy - (b["bbox"][1] + b["bbox"][3]) / 2) < 0.3 * height
            for b in unique
        ):
            continue
        unique.append(candidate)

    # Nearby glyphs on one or two lines form a connected plate candidate.
    parent = list(range(len(unique)))

    def find(index):
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    for i, first in enumerate(unique):
        ax1, ay1, ax2, ay2 = first["bbox"]
        acx, acy = (ax1 + ax2) / 2, (ay1 + ay2) / 2
        ah = ay2 - ay1
        for j in range(i + 1, len(unique)):
            bx1, by1, bx2, by2 = unique[j]["bbox"]
            bcx, bcy = (bx1 + bx2) / 2, (by1 + by2) / 2
            bh = by2 - by1
            threshold = 2.2 * max(ah, bh)
            if abs(acx - bcx) <= threshold and abs(acy - bcy) <= threshold:
                root_i, root_j = find(i), find(j)
                if root_i != root_j:
                    parent[root_j] = root_i

    clusters = {}
    for index, item in enumerate(unique):
        clusters.setdefault(find(index), []).append(item)

    height, width = image.shape[:2]
    proposals = []
    for cluster in clusters.values():
        if len(cluster) < 6:
            continue
        x1 = min(item["bbox"][0] for item in cluster)
        y1 = min(item["bbox"][1] for item in cluster)
        x2 = max(item["bbox"][2] for item in cluster)
        y2 = max(item["bbox"][3] for item in cluster)
        pad_x, pad_y = (x2 - x1) * 0.12, (y2 - y1) * 0.12
        bbox = [
            max(0, int(x1 - pad_x)), max(0, int(y1 - pad_y)),
            min(width, int(x2 + pad_x)), min(height, int(y2 + pad_y)),
        ]
        area = (bbox[2] - bbox[0]) * (bbox[3] - bbox[1])
        if area <= 0 or area > width * height * 0.50:
            continue
        proposals.append({"bbox": bbox, "confidence": sum(item["confidence"] for item in cluster) / len(cluster)})

    return sorted(proposals, key=lambda item: item["confidence"], reverse=True)[:4]

def get_detector() -> LicensePlateDetector:
    global _detector
    if _detector is None:
        _detector = LicensePlateDetector(model_path=settings.YOLO_MODEL_PATH)
    return _detector

def get_ocr_engine() -> PlateOCREngine:
    global _ocr_engine
    if _ocr_engine is None:
        _ocr_engine = PlateOCREngine(engine_type=settings.OCR_ENGINE)
    return _ocr_engine

@router.post("/detect", response_model=PlateDetectionResponse)
def detect_license_plate(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    with _inference_lock:
        return _detect_license_plate(file, db, user)


def _detect_license_plate(file, db, user):
    """Read local candidates, permit at most one cloud recognition call, and save
    accepted results for the authenticated owner. Regex checks structure only.
    """
    start_time = time.perf_counter()
    
    # Đọc file ảnh từ request
    contents = file.file.read(10 * 1024 * 1024 + 1)
    if len(contents) > 10 * 1024 * 1024:
        raise HTTPException(413, "Ảnh quá lớn. Vui lòng chọn ảnh dưới 10 MB.")
    if not contents or len(contents) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tập tin tải lên rỗng (0 bytes). Vui lòng chọn một file ảnh hợp lệ."
        )

    try:
        nparr = np.frombuffer(contents, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Lỗi khi giải mã ảnh: {str(e)}"
        )
    
    if image is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tập tin tải lên không phải là ảnh hợp lệ hoặc định dạng không được hỗ trợ"
        )

    detector = get_detector()
    ocr_engine = get_ocr_engine()

    # 1. Phát hiện biển số bằng Local YOLO Detector chính thức (tối đa 2 box tiềm năng)
    detections = detector.detect(image, include_low_confidence=True)
    
    # 2. Xử lý OCR cục bộ siêu tốc cho từng box phát hiện
    candidates = []
    has_valid_plate = False
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
        ocr_res = ocr_engine.recognize_local_yolo(plate_crop)
        cleaned_text = PlatePostprocessor.clean_text(ocr_res.get("raw_text", ""))
        formatted = PlatePostprocessor.format_vietnamese_plate(cleaned_text, plate_type=ocr_res.get("plate_type"), text_lines=ocr_res.get("text_lines"))
        is_valid = PlatePostprocessor.validate_plate(formatted)
        ocr_conf = float(ocr_res.get("avg_conf", 0.0))
        engine_used = "local_yolo"

        has_valid_plate = has_valid_plate or is_valid

        candidates.append({
            "bbox": bbox,
            "conf": ocr_conf if engine_used == "local_yolo" and ocr_conf > 0 else conf,
            "plate_crop": plate_crop,
            "ocr_res": ocr_res,
            "cleaned_text": cleaned_text,
            "formatted_plate": formatted,
            "is_valid": is_valid,
            "engine_used": engine_used
        })

    # Bổ sung các cụm ký tự OCR để tìm biển mà detector bỏ sót trong ảnh nhiều xe.
    # Bỏ qua cụm trùng với các box đã tìm thấy; chỉ nhận kết quả qua regex biển VN.
    if getattr(ocr_engine, "yolo_ocr", None) is not None:
        for proposal in _ocr_character_regions(image, ocr_engine):
            x1, y1, x2, y2 = proposal["bbox"]
            proposal_area = max(1, (x2 - x1) * (y2 - y1))
            center_x, center_y = (x1 + x2) / 2, (y1 + y2) / 2
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
                "engine_used": "local_yolo_ocr_fallback",
            })
            has_valid_plate = True

    # A bright quadrilateral supplies real geometry when the learned detector
    # misses a rotated plate. Require observed valid OCR before accepting it.
    if not has_valid_plate and getattr(ocr_engine, "yolo_ocr", None) is not None:
        for region in quadrilateral_plate_regions(image):
            ocr_res = ocr_engine.recognize_local_yolo(region["crop"])
            region_engine = "local_yolo_rectified"
            cleaned_text = PlatePostprocessor.clean_text(ocr_res.get("raw_text", ""))
            formatted = PlatePostprocessor.format_vietnamese_plate(cleaned_text, ocr_res.get("plate_type"), ocr_res.get("text_lines"))
            valid = PlatePostprocessor.validate_plate(formatted) and float(ocr_res.get("avg_conf", 0)) >= 0.60
            if not valid:
                line_ocr = getattr(ocr_engine, "line_ocr", None)
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
    if not has_valid_plate and getattr(ocr_engine, "yolo_ocr", None) is not None:
        full_ocr = ocr_engine.recognize_local_yolo(image)
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
                "engine_used": "local_yolo_ocr_full_image",
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
        crop_filename = f"crop_{uuid.uuid4().hex[:8]}.jpg"
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
    annotated_filename = f"result_{uuid.uuid4().hex[:8]}.jpg"
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

@router.get("/history")
async def get_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Lấy danh sách lịch sử nhận diện từ cơ sở dữ liệu SQLite (data/alpr.db) có phân trang.
    """
    start_idx = (page - 1) * page_size
    owned = db.query(PlateHistory).filter(PlateHistory.owner_id == user.id)
    total = owned.count()
    records = owned.order_by(PlateHistory.id.desc()).offset(start_idx).limit(page_size).all()
    
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [r.to_dict() for r in records]
    }

@router.get("/search")
async def search_plates(
    plate: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Tìm kiếm các xe đã nhận diện trong SQLite theo biển số.
    """
    plate_clean = PlatePostprocessor.clean_text(plate)
    records = db.query(PlateHistory).filter(PlateHistory.owner_id == user.id).order_by(PlateHistory.id.desc()).all()
    matched = [
        r.to_dict() for r in records
        if plate_clean in PlatePostprocessor.clean_text(r.plate_number)
    ]
    return {"total": len(matched), "query": plate, "results": matched}

@router.get("/{detection_id}")
async def get_detection_detail(
    detection_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Xem chi tiết một lượt nhận diện theo ID từ SQLite.
    """
    item = db.query(PlateHistory).filter(PlateHistory.id == detection_id, PlateHistory.owner_id == user.id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Không tìm thấy lượt nhận diện")
    return item.to_dict()
