# Xử lý video tải lên

API phân tích video ngắn, trả metadata theo vết và phục vụ lại file tải lên để frontend vẽ annotation. Chưa có luồng RTSP hoặc camera trực tiếp trong API hiện tại.

## Mã xử lý và model

`src/core/video/plate_reader.py` chứa lớp đọc biển được tách khỏi giao diện Streamlit của nguồn kế thừa. Backend dùng phần OCR qua `VideoPlateOCR` trong `src/core/video/models.py`; việc theo vết phương tiện, ghép biển và tổng hợp kết quả của web nằm trong `src/core/video/tracker.py`. Xem [nguồn mã/model](#nguon-ma-va-model).

Bộ model video mặc định gồm `DetectLisence_YOLO11.pt` và `cct_s_v1_vn.onnx`, cùng cấu hình OCR. `models/yolov8n.pt` trong thư mục model là model phương tiện dùng để theo vết. Vị trí và lệnh cài đầy đủ nằm tại [hướng dẫn trọng số](../models/weights_readme.txt).

```powershell
.\venv\Scripts\python.exe scripts/download_models.py --group video
```

Script chỉ tải trọng số thiếu/sai checksum từ phiên bản cố định và cài cấu hình YAML đi kèm. Runtime dùng mã đã nằm trong `src/`; không cần clone ứng dụng khác. Adapter OCR chuyển BGR sang RGB, loại confidence của padding và không bật thêm bộ tiền xử lý CLAHE/khử nhiễu của lớp kế thừa.

Factory `ModelRuntime` và registry nằm trong `src/core/models/`. `src/services/model_runtime.py` giữ cache theo tiến trình và khóa suy luận. `src/services/video_jobs.py` quản lý job video. Route xác thực đầu vào HTTP và gọi service.

## Luồng job trong kiến trúc mục tiêu

Ở giai đoạn 4, FastAPI dự kiến lưu upload qua lớp lưu trữ, tạo bản ghi job, gửi tham chiếu tệp qua Redis và trả `job_id`. Worker riêng sẽ đọc video, chạy tracking/OCR và cập nhật tiến trình, kết quả vào kho lưu trữ chung. Giao diện tiếp tục truy vấn trạng thái theo `job_id` và phát video qua endpoint media có kiểm tra chủ sở hữu và HTTP Range. Các giới hạn runtime bên dưới mô tả executor nội bộ đang chạy. [Kiến trúc triển khai](../README.md#kien-truc-trien-khai)

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
- Executor có một worker trong mỗi tiến trình. Tổng job queued/running tối đa hai trên database đang dùng. Bảng `video_jobs` lưu tiến trình và kết quả. Job bị gián đoạn được đánh dấu failed khi truy vấn hoặc nhận job mới. SQLite dùng file lock cùng máy, còn PostgreSQL dùng advisory lock để nhận biết job đang hoạt động trên máy khác.
- Với S3, executor tải upload vào thư mục tạm để OpenCV đọc và dọn thư mục khi xử lý xong. API truyền dải byte yêu cầu từ bucket riêng sau khi xác minh chủ sở hữu. [Cấu hình lưu trữ](data.md)
- Detector/OCR biển video được cache theo tiến trình; model phương tiện/tracker được tạo mới cho từng video.
- Kết quả tổng hợp có thể vẫn sai dù lặp lại qua nhiều frame. Kiểm tra định dạng biển không chứng minh nội dung đúng.

## Đo hiệu năng

Chạy từ thư mục gốc với video thực sự có trên máy:

```powershell
.\venv\Scripts\python.exe scripts/benchmark_video.py "duong-dan-video.mp4" --engine onnx --mode fast --output data/benchmarks/onnx.json
.\venv\Scripts\python.exe scripts/benchmark_video.py "duong-dan-video.mp4" --engine legacy --mode combined --output data/benchmarks/legacy.json
```

Cả hai lệnh đều tắt OCR từ xa. JSON ghi thời gian nạp detector/OCR biển, thời gian phân tích và tổng thời gian. Việc tạo model phương tiện nằm trong `process_video`, nên thuộc thời gian phân tích của CLI. API bắt đầu tính trước khi lấy engine, không bao gồm upload/thời gian xếp hàng. Hai phép đo khác mode không tách riêng đóng góp của model; cần cùng mode/dữ liệu để so sánh có kiểm soát.

Trong đợt đồng bộ tài liệu, hiệu năng và độ chính xác video **chưa đo**. Các số thời gian/tăng tốc từng ghi tại đây đã được bỏ khỏi hướng dẫn hiện hành vì file bằng chứng không còn ở workspace; xem bản `AUDIT.md` trong lịch sử Git. Chưa có kết quả tracking có nhãn MOTA/IDF1 hoặc ablation tái lập kèm tài liệu này.

<a id="nguon-ma-va-model"></a>

## Nguồn mã và model

## Lõi đọc biển số

- Tác giả/repository: [ddkhoa2605/LicensePlateDetection](https://github.com/ddkhoa2605/LicensePlateDetection), commit `f1c732e2270becc44df1de6529372f63ef251076`.
- File gốc: `appStreamlit.py`, lớp `SimplePlateDetector`.
- File tích hợp: `src/core/video/plate_reader.py`, lớp `PlateReader`.
- Các thuật toán kế thừa: tiền xử lý crop, crop có padding, bỏ phiếu ký tự theo confidence, quản lý vòng đời track và xử lý frame.
- Điều chỉnh của đồ án: bỏ phụ thuộc Streamlit; nạp model tùy chọn; cập nhật API Fast Plate OCR 1.1; chuyển BGR sang RGB; loại padding trước khi tính confidence; cho phép tắt tiền xử lý trong adapter video để giữ luồng đang chạy.
- Backend dùng OCR từ lớp này qua `VideoPlateOCR`; theo vết phương tiện và schema trả về cho web vẫn nằm trong `src/core/video/tracker.py`.

Thông tin nguồn được giữ để phân biệt phần kế thừa với phần nhóm tự triển khai. Repository gốc không có file LICENSE riêng tại phiên bản được tích hợp; tài liệu này không cấp thêm quyền sử dụng. Cần xác nhận giấy phép hoặc được chủ sở hữu đồng ý trước khi phân phối mã chuyển thể và trọng số; nếu không có quyền phù hợp, thay các thành phần đó bằng nguồn có giấy phép rõ ràng. Việc dẫn nguồn trong báo cáo không thay cho quyền sử dụng.

### Trọng số và cấu hình OCR

`DetectLisence_YOLO11.pt`, `cct_s_v1_vn.onnx` và cấu hình `cct_s_v1_vn_plate_config.yaml` thuộc bộ model video kế thừa. Trình cài chọn bản trọng số cố định và xác minh SHA‑256. Cấu hình đi kèm được lấy từ `src/core/video/video_ocr.yaml`. Lệnh `scripts/setup_video_models.py` vẫn cài nhóm detector biển và OCR video như trước.

Tệp `cct_s_v1_vn.onnx` đã có ở repository gốc; đồ án không nhận công huấn luyện hoặc chuyển đổi tệp này. Nguồn huấn luyện và quyền phân phối của `models/best.pt` và `models/LP_ocr.pt` chưa được xác minh trong tài liệu hiện có.

Ultralytics, Fast Plate OCR và ONNX Runtime vẫn là các thư viện cài qua `requirements.txt`, không phải mã do nhóm tự phát triển.
