import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from threading import Lock
import json

from src.config import settings
from src.core.detector import LicensePlateDetector
from src.core.ocr_engine import PlateOCREngine
from src.core.video_tracker import process_video

def progress_callback(val):
    print(f"[TIẾN ĐỘ] {val}%")

video_path = Path(r"D:\ảnh\15135701_1080_1920_30fps.mp4")
if not video_path.is_file():
    alt = Path("data/video_jobs/ee5555c99a704787a704d93e68573551.mp4")
    if alt.is_file():
        video_path = alt

print(f"Bắt đầu test video: {video_path}")
vehicle_model_path = Path(settings.VEHICLE_MODEL_PATH)
plate_detector = LicensePlateDetector(model_path=settings.YOLO_MODEL_PATH)
ocr_engine = PlateOCREngine(engine_type=settings.OCR_ENGINE)
inference_lock = Lock()

start_time = time.time()
result = process_video(
    video_path,
    vehicle_model_path,
    plate_detector,
    ocr_engine,
    inference_lock,
    progress_callback,
    mode="combined"
)
elapsed = time.time() - start_time

print(f"\n===== KẾT QUẢ PHÂN TÍCH VIDEO (Thời gian chạy: {elapsed:.2f}s) =====")
print(f"- Thời lượng video: {result.get('duration')}s")
print(f"- FPS gốc: {result.get('fps')}")
print(f"- Kích thước xử lý: {result.get('frame_width')}x{result.get('frame_height')}")
print(f"- Tổng số khung hình đã duyệt: {len(result.get('frames', []))}")
print(f"- Tổng số phương tiện được theo vết (tracks): {len(result.get('tracks', []))}")

print("\n--- DANH SÁCH PHƯƠNG TIỆN VÀ BIỂN SỐ NHẬN DIỆN ---")
tracks = result.get("tracks", [])
recognized = [t for t in tracks if t.get("plate_number")]
unreadable = [t for t in tracks if not t.get("plate_number")]

print(f"\n>> ĐÃ NHẬN DIỆN ĐƯỢC BIỂN SỐ ({len(recognized)}/{len(tracks)} xe):")
for idx, t in enumerate(recognized, 1):
    print(f"  {idx}. [ID {t['track_id']}] Loại xe: {t['vehicle_type']} | Biển số: {t['plate_number']} | Conf: {t['plate_confidence']} | Lượt đọc: {t['plate_observations']} | Trạng thái: {t['plate_status']} | Thời gian: {t['first_seen']}s - {t['last_seen']}s")
    if t.get("plate_candidates") and len(t["plate_candidates"]) > 1:
        print(f"     Các ứng viên đọc được: {t['plate_candidates']}")

if unreadable:
    print(f"\n>> CHƯA NHẬN DIỆN ĐƯỢC BIỂN SỐ ({len(unreadable)}/{len(tracks)} xe):")
    for idx, t in enumerate(unreadable, 1):
        print(f"  {idx}. [ID {t['track_id']}] Loại xe: {t['vehicle_type']} | Thời gian xuất hiện: {t['first_seen']}s - {t['last_seen']}s")

if result.get("ninerouter"):
    print(f"\nThông tin 9Router Rescue: {result.get('ninerouter')}")

# Save json output
output_json = Path("data/outputs/test_video_result.json")
output_json.parent.mkdir(parents=True, exist_ok=True)
with open(output_json, "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
print(f"\nĐã lưu kết quả chi tiết vào: {output_json}")
