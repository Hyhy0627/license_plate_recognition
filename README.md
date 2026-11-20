# Hướng dẫn Commit & Push cho Vy (Backend Video Tracking)

Phần này chứa toàn bộ mã nguồn Backend, xử lý AI và kiểm thử của tính năng **Nhận diện biển số xe qua Video (Video LPR & Tracking)**.

---

## 1. Danh sách file phụ trách:
- `src/api/video_routes.py`: API tiếp nhận upload video, polling tiến độ (0% - 100%) và streaming video kết quả.
- `src/core/video_tracker.py`: Bộ điều phối 2-pass (Fast/Detailed), ByteTrack theo vết đa xe, liên kết biển số vào xe và bầu chọn biển số tối ưu.
- `src/core/video_models.py`: Tích hợp các mô hình phát hiện xe YOLOv8n và OCR CCT-VN ONNX.
- `src/config.py`: Các thiết lập cấu hình Video LPR (engine, confidence, model paths).
- `main.py`: Đăng ký router `/api/video-tracking` vào FastAPI app.
- `requirements.txt`: Bổ sung thư viện liên kết dữ liệu `lap` và `fast-plate-ocr[onnx]`.
- `tool/setup_video_models.py`: Script tự động tải và cài đặt trọng số mô hình video.
- `tool/test_single_video.py`: Công cụ kiểm thử trực tiếp trên 1 video cụ thể.
- `tool/benchmark_video.py`: Công cụ đo tốc độ và hiệu năng xử lý video.
- `tests/test_video_tracking.py`: Kiểm thử logic ghép track và bầu chọn biển số.
- `tests/test_video_models.py`: Kiểm thử nạp mô hình và xử lý ảnh xe.
- `tests/test_video_media.py`: Kiểm thử stream và phân quyền video.
- `tests/test_video_validation.py`: Kiểm thử giới hạn file video đầu vào.
- `docs/video_onnx.md`: Tài liệu kỹ thuật mô hình video.

---

## 2. Câu lệnh Git gợi ý để Vy commit:

```powershell
# 1. Chuyển sang nhánh làm việc (ví dụ develop hoặc feature/video-backend)
git checkout develop

# 2. Thêm các file của phần Backend Video vào staging
git add src/api/video_routes.py src/core/video_tracker.py src/core/video_models.py src/config.py main.py requirements.txt tool/setup_video_models.py tool/test_single_video.py tool/benchmark_video.py tests/test_video_tracking.py tests/test_video_models.py tests/test_video_media.py tests/test_video_validation.py docs/video_onnx.md

# 3. Tạo commit chuẩn Conventional Commits
git commit -m "feat(video-backend): hoàn thiện module theo vết xe ByteTrack, API video và bộ kiểm thử tự động"

# 4. Đẩy commit lên remote repository
git push origin develop
```
