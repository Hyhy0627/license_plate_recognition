import time
import os
import uuid
import cv2
import numpy as np
from fastapi import APIRouter, UploadFile, File, HTTPException, Query, status
from fastapi.responses import JSONResponse

from src.api.schemas import PlateDetectionResponse, DetectionResult, DetectionHistoryResponse
from src.core.detector import LicensePlateDetector
from src.core.ocr_engine import PlateOCREngine
from src.core.postprocessor import PlatePostprocessor
from src.utils.visualizer import draw_plate_box
from src.config import settings

router = APIRouter(prefix="/license-plates", tags=["License Plates"])

# In-memory history mockup khi chưa nối DB PostgreSQL
MOCK_HISTORY = []

@router.post("/detect", response_model=PlateDetectionResponse)
async def detect_license_plate(file: UploadFile = File(...)):
    """
    Endpoint nhận file ảnh, thực hiện phát hiện và nhận diện biển số xe.
    """
    start_time = time.time()
    
    # Đọc file ảnh từ request
    contents = await file.read()
    nparr = np.frombuffer(contents, np.uint8)
    image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    
    if image is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tập tin tải lên không phải là ảnh hợp lệ"
        )

    # Khởi tạo modules (Trong thực tế nên lấy từ app.state/lifespan)
    detector = LicensePlateDetector(model_path=settings.YOLO_MODEL_PATH)
    ocr_engine = PlateOCREngine(engine_type=settings.OCR_ENGINE)

    # 1. Phát hiện biển số (YOLO)
    detections = detector.detect(image)
    
    results = []
    annotated_img = image.copy()

    for idx, det in enumerate(detections):
        bbox = det["bbox"]
        conf = det["confidence"]
        
        # 2. Crop ảnh biển số
        plate_crop = detector.crop_plate(image, bbox)
        if plate_crop is None or plate_crop.size == 0:
            continue
        
        # 3. OCR nhận diện ký tự
        ocr_res = ocr_engine.recognize_plate(plate_crop)
        cleaned_text = PlatePostprocessor.clean_text(ocr_res["raw_text"])
        formatted_plate = PlatePostprocessor.format_vietnamese_plate(cleaned_text)
        is_valid = PlatePostprocessor.validate_plate(formatted_plate)
        
        # Lưu ảnh crop
        crop_filename = f"crop_{uuid.uuid4().hex[:8]}.jpg"
        crop_path = os.path.join(settings.CROPPED_PLATES_DIR, crop_filename)
        cv2.imwrite(crop_path, plate_crop)
        
        # Vẽ lên ảnh kết quả
        annotated_img = draw_plate_box(annotated_img, bbox, formatted_plate, conf)

        res_item = DetectionResult(
            plate_number=formatted_plate or "UNKNOWN",
            confidence=round(conf, 4),
            plate_type=ocr_res["plate_type"],
            bbox=bbox,
            cropped_image_url=f"/static/cropped_plates/{crop_filename}",
            annotated_image_url=None,
            is_valid_format=is_valid
        )
        results.append(res_item)

        # Lưu vào history mock
        MOCK_HISTORY.append({
            "id": len(MOCK_HISTORY) + 1,
            "plate_number": formatted_plate,
            "confidence": conf,
            "plate_type": ocr_res["plate_type"],
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "image_url": None,
            "cropped_plate_url": f"/static/cropped_plates/{crop_filename}"
        })

    # Lưu ảnh annotated
    annotated_filename = f"result_{uuid.uuid4().hex[:8]}.jpg"
    annotated_path = os.path.join(settings.FINAL_RESULTS_DIR, annotated_filename)
    cv2.imwrite(annotated_path, annotated_img)

    for r in results:
        r.annotated_image_url = f"/static/final_results/{annotated_filename}"

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
    page_size: int = Query(10, ge=1, le=100)
):
    """
    Lấy danh sách lịch sử nhận diện có phân trang.
    """
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    items = MOCK_HISTORY[::-1][start_idx:end_idx]
    
    return {
        "total": len(MOCK_HISTORY),
        "page": page,
        "page_size": page_size,
        "items": items
    }

@router.get("/search")
async def search_plates(plate: str = Query(..., min_length=1)):
    """
    Tìm kiếm theo biển số xe.
    """
    plate_clean = PlatePostprocessor.clean_text(plate)
    matched = [
        item for item in MOCK_HISTORY
        if plate_clean in PlatePostprocessor.clean_text(item["plate_number"])
    ]
    return {"total": len(matched), "query": plate, "results": matched}

@router.get("/{detection_id}")
async def get_detection_detail(detection_id: int):
    """
    Xem chi tiết một lượt nhận diện theo ID.
    """
    item = next((x for x in MOCK_HISTORY if x["id"] == detection_id), None)
    if not item:
        raise HTTPException(status_code=404, detail="Không tìm thấy lượt nhận diện")
    return item
