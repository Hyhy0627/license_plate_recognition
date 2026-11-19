# Xử lý video tải lên

API phân tích video ngắn, trả metadata theo vết và phục vụ lại file tải lên để frontend vẽ annotation. Chưa có luồng RTSP hoặc camera trực tiếp trong API hiện tại.

## Mã xử lý và model

`src/core/plate_reader.py` chứa lớp đọc biển được tách khỏi giao diện Streamlit của nguồn kế thừa. Backend dùng phần OCR qua `VideoPlateOCR` trong `src/core/video_models.py`; việc theo vết phương tiện, ghép biển và tổng hợp kết quả của web nằm trong `src/core/video_tracker.py`. Xem [nguồn mã/model](../THIRD_PARTY_NOTICES.md).

Bộ model video mặc định gồm `DetectLisence_YOLO11.pt` và `cct_s_v1_vn.onnx`, cùng cấu hình OCR. `yolov8n.pt` ở thư mục gốc là model phương tiện dùng để theo vết. Vị trí và lệnh cài đầy đủ nằm tại [hướng dẫn trọng số](../models/weights_readme.txt).

```powershell
.\venv\Scripts\python.exe scripts/setup_video_models.py
```

Script chỉ tải trọng số thiếu/sai checksum từ phiên bản cố định và cài cấu hình YAML đi kèm. Runtime dùng mã đã nằm trong `src/`; không cần clone ứng dụng khác. Adapter OCR chuyển BGR sang RGB, loại confidence của padding và không bật thêm bộ tiền xử lý CLAHE/khử nhiễu của lớp kế thừa.

## Engine và chế độ API

| Mode | Detector/OCR biển | OCR từ xa |
|---|---|---|
| `fast` — mặc định của trang `/video` và API | Factory `get_video_engines()` theo `VIDEO_ENGINE`: ONNX mặc định, hoặc bộ ảnh khi chọn `legacy` | Tắt |
| `detailed` | Factory detector/OCR ảnh | Có thể bật theo cấu hình và điều kiện track |
| `combined` | Dùng bộ ảnh cho hai lượt fast/detailed rồi gộp | Tắt ở lượt fast, có thể bật ở lượt detailed |

`VIDEO_ENGINE=onnx` không tự chuyển sang legacy khi thiếu trọng số; job báo lỗi để người chạy cài đúng model. Tham số `--engine` trong CLI benchmark chọn engine cho lần đo; không đồng nhất với cách API chọn engine theo mode.

Cấu hình bộ ONNX:

```dotenv
VIDEO_ENGINE=onnx
VIDEO_PLATE_MODEL_PATH=models/video/DetectLisence_YOLO11.pt
VIDEO_OCR_MODEL_PATH=models/video/cct_s_v1_vn.onnx
VIDEO_OCR_CONFIG_PATH=models/video/cct_s_v1_vn_plate_config.yaml
VIDEO_OCR_MIN_CONFIDENCE=0.7
```

Khởi động lại backend sau khi đổi cấu hình. Điều kiện remote và dữ liệu ảnh có thể gửi đi nằm tại [docs/cloud_ocr.md](cloud_ocr.md).

## Giới hạn xử lý hiện tại

- Upload tối đa 100 MB; chấp nhận đuôi MP4, MOV, AVI, WEBM và còn phải giải mã/đọc metadata được.
- Video tối đa 45 giây, độ phân giải không quá Full HD theo số pixel; tracker kiểm tra metadata và FPS.
- Profile fast/detailed đặt mục tiêu lấy mẫu 5 frame/giây, kích thước suy luận phương tiện 640. Stride được làm tròn từ FPS nguồn nên tần suất mẫu thực tế có thể khác; đây là cấu hình, không phải FPS xử lý đo được.
- Executor có một worker; tổng job queued/running tối đa hai. Job/progress/result được giữ trong bộ nhớ và không khôi phục sau khi backend khởi động lại.
- Detector/OCR biển video được cache theo tiến trình; model phương tiện/tracker được tạo mới cho từng video.
- Kết quả tổng hợp có thể vẫn sai dù lặp lại qua nhiều frame. Kiểm tra định dạng biển không chứng minh nội dung đúng.

## Đo hiệu năng

Chạy từ thư mục gốc với video thực sự có trên máy:

```powershell
.\venv\Scripts\python.exe benchmark/benchmark_video.py "duong-dan-video.mp4" --engine onnx --mode fast --output data/benchmarks/onnx.json
.\venv\Scripts\python.exe benchmark/benchmark_video.py "duong-dan-video.mp4" --engine legacy --mode combined --output data/benchmarks/legacy.json
```

Cả hai lệnh đều tắt OCR từ xa. JSON ghi thời gian nạp detector/OCR biển, thời gian phân tích và tổng thời gian. Việc tạo model phương tiện nằm trong `process_video`, nên thuộc thời gian phân tích của CLI. API bắt đầu tính trước khi lấy engine, không bao gồm upload/thời gian xếp hàng. Hai phép đo khác mode không tách riêng đóng góp của model; cần cùng mode/dữ liệu để so sánh có kiểm soát.

Trong đợt đồng bộ tài liệu, hiệu năng và độ chính xác video **chưa đo**. Các số thời gian/tăng tốc từng ghi tại đây đã được bỏ khỏi hướng dẫn hiện hành vì file bằng chứng không còn ở workspace; xem snapshot [AUDIT.md](../AUDIT.md). Chưa có kết quả tracking có nhãn MOTA/IDF1 hoặc ablation tái lập kèm tài liệu này.
