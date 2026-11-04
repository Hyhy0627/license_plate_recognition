import time
import os
import uuid
import cv2
import numpy as np
from fastapi import APIRouter, UploadFile, File, HTTPException, Query, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from src.api.schemas import PlateDetectionResponse, DetectionResult, DetectionHistoryResponse
from src.core.detector import LicensePlateDetector
from src.core.ocr_engine import PlateOCREngine
from src.core.postprocessor import PlatePostprocessor
from src.utils.visualizer import draw_plate_box
from src.config import settings
from src.db.session import get_db
from src.db.models import PlateHistory
from src.utils.logger import logger

router = APIRouter(prefix="/license-plates", tags=["License Plates"])

_detector = None
_ocr_engine = None

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
async def detect_license_plate(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Endpoint nhận file ảnh, thực hiện phát hiện và nhận diện biển số xe theo kiến trúc Hybrid:
    - Bước 1: Chạy Local AI trước (YOLO Detection + YOLO OCR có Auto-Invert màu) (~50ms).
    - Bước 2: Tự động cứu cánh bằng Cloud Vision AI (9Router) ĐÚNG 1 LẦN nếu Local AI không tìm thấy.
    - Lọc bỏ 100% box rác (yên xe, bô xe, đèn xe).
    Lưu vĩnh viễn kết quả vào cơ sở dữ liệu SQLite (data/alpr.db).
    """
    start_time = time.time()
    
    # Đọc file ảnh từ request
    contents = await file.read()
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
    detections = detector.detect(image)
    
    # 2. Xử lý OCR cục bộ siêu tốc cho từng box phát hiện
    candidates = []
    has_valid_plate = False

    for det in detections:
        bbox = det["bbox"]
        conf = det["confidence"]
        plate_crop = detector.crop_plate(image, bbox)
        if plate_crop is None or plate_crop.size == 0:
            continue
        
        # Chạy Local YOLO OCR siêu tốc (~20ms)
        ocr_res = ocr_engine.recognize_local_yolo(plate_crop)
        cleaned_text = PlatePostprocessor.clean_text(ocr_res.get("raw_text", ""))
        formatted = PlatePostprocessor.format_vietnamese_plate(cleaned_text, plate_type=ocr_res.get("plate_type"))
        is_valid = PlatePostprocessor.validate_plate(formatted)
        
        if len(cleaned_text) >= 6 or is_valid:
            has_valid_plate = True

        candidates.append({
            "bbox": bbox,
            "conf": conf,
            "plate_crop": plate_crop,
            "ocr_res": ocr_res,
            "cleaned_text": cleaned_text,
            "formatted_plate": formatted,
            "is_valid": is_valid,
            "engine_used": "local_yolo"
        })

    # 3. Cơ chế Cứu trợ Thông minh (Self-Healing Fallback) - CHỈ GỌI DUY NHẤT 1 LẦN:
    # Nếu Local AI hoàn toàn không bắt được biển HOẶC tất cả các box local đều ra kết quả không hợp lệ:
    if (not detections or not has_valid_plate) and hasattr(ocr_engine, "ninerouter_client") and ocr_engine.ninerouter_client is not None:
        try:
            if ocr_engine.ninerouter_client.is_available():
                logger.info("Local AI không tìm thấy biển số hợp lệ. Kích hoạt Cloud Vision AI quét ảnh toàn cảnh (1 lần duy nhất)...")
                ai_fullimg = ocr_engine.ninerouter_client.detect_and_recognize_plate(image)
                ai_clean = PlatePostprocessor.clean_text(ai_fullimg.get("raw_text", ""))
                
                # Nếu Cloud AI tìm thấy biển số chuẩn:
                if len(ai_clean) >= 6:
                    ai_bbox = ai_fullimg.get("bbox")
                    if not ai_bbox:
                        h, w = image.shape[:2]
                        ai_bbox = [int(w * 0.2), int(h * 0.3), int(w * 0.8), int(h * 0.7)]
                    
                    plate_crop_ai = detector.crop_plate(image, ai_bbox)
                    ai_formatted = PlatePostprocessor.format_vietnamese_plate(ai_clean, plate_type=ai_fullimg.get("plate_type"))
                    ai_valid = PlatePostprocessor.validate_plate(ai_formatted)
                    
                    # Thay thế hoàn toàn bằng 1 kết quả duy nhất, chính xác từ Cloud AI
                    candidates = [{
                        "bbox": ai_bbox,
                        "conf": float(ai_fullimg.get("confidence", 0.95)),
                        "plate_crop": plate_crop_ai if plate_crop_ai is not None and plate_crop_ai.size > 0 else image,
                        "ocr_res": ai_fullimg,
                        "cleaned_text": ai_clean,
                        "formatted_plate": ai_formatted,
                        "is_valid": ai_valid,
                        "engine_used": "9router_vision"
                    }]
                    logger.info(f"Cloud Vision AI cứu trợ thành công: {ai_formatted}")
        except Exception as e:
            logger.warning(f"Lỗi khi gọi Cloud Vision AI: {e}")

    # 4. Lọc bỏ các box rác: nếu có ít nhất 1 box hợp lệ thì loại bỏ ngay các box trống/UNKNOWN
    valid_candidates = [c for c in candidates if len(c["cleaned_text"]) >= 5 or c["is_valid"]]
    final_candidates = valid_candidates if valid_candidates else candidates[:1]

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

    total_time_ms = round((time.time() - start_time) * 1000, 2)

    return PlateDetectionResponse(
        success=True,
        message="Nhận diện biển số thành công" if results else "Không tìm thấy biển số trong ảnh",
        total_detected=len(results),
        processing_time_ms=total_time_ms,
        results=results
    )

@router.get("/history")
async def get_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """
    Lấy danh sách lịch sử nhận diện từ cơ sở dữ liệu SQLite (data/alpr.db) có phân trang.
    """
    start_idx = (page - 1) * page_size
    total = db.query(PlateHistory).count()
    records = db.query(PlateHistory).order_by(PlateHistory.id.desc()).offset(start_idx).limit(page_size).all()
    
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [r.to_dict() for r in records]
    }

@router.get("/search")
async def search_plates(
    plate: str = Query(..., min_length=1),
    db: Session = Depends(get_db)
):
    """
    Tìm kiếm các xe đã nhận diện trong SQLite theo biển số.
    """
    plate_clean = PlatePostprocessor.clean_text(plate)
    records = db.query(PlateHistory).order_by(PlateHistory.id.desc()).all()
    matched = [
        r.to_dict() for r in records
        if plate_clean in PlatePostprocessor.clean_text(r.plate_number)
    ]
    return {"total": len(matched), "query": plate, "results": matched}

@router.get("/{detection_id}")
async def get_detection_detail(
    detection_id: int,
    db: Session = Depends(get_db)
):
    """
    Xem chi tiết một lượt nhận diện theo ID từ SQLite.
    """
    item = db.query(PlateHistory).filter(PlateHistory.id == detection_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Không tìm thấy lượt nhận diện")
    return item.to_dict()
