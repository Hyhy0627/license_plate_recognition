# OCR qua NineRouter

`src/core/ninerouter_vision.py` là HTTP client gọi dịch vụ Vision qua gateway tương thích `/chat/completions`. Backend không chạy mô hình ngôn ngữ/thị giác đó trong tiến trình Python. Dù gateway đặt ở localhost, gateway vẫn có thể chuyển request đến nhà cung cấp bên ngoài.

## Khi nào gọi

| Điểm gọi | Điều kiện |
|---|---|
| API nhận diện ảnh | Thử các nhánh local trước; chỉ gọi nhận diện từ xa khi chưa có biển hợp lệ, client được khởi tạo và gateway được kiểm tra là sẵn sàng. Tối đa một lời gọi nhận diện crop hoặc toàn ảnh trong handler |
| API video `mode=fast` | Không bật OCR từ xa, kể cả khi `VIDEO_ENGINE=legacy` |
| API video `mode=detailed` hoặc `combined` | Lượt detailed có thể gọi remote cho track chưa đọc được, nếu engine có client. Tracker chọn tối đa `MAX_NINEROUTER_CALLS=6` ứng viên và có thể dừng sớm khi lỗi |
| Gọi trực tiếp `PlateOCREngine.recognize_plate()` | Mode `9router` thử remote trước; `hybrid` có thể dùng remote sau local yếu. Method này có thứ tự riêng, không phải luồng mặc định của handler ảnh |

Chỉ engine ảnh ở mode `hybrid`/`9router` khởi tạo client NineRouter. `VideoPlateOCR` của bộ ONNX không có client remote. `is_available()` thực hiện request kiểm tra riêng, được cache theo code; nó không phải lời gọi nhận diện ảnh.

## Dữ liệu gửi đi

- Ảnh ứng viên biển số, ảnh toàn cảnh khi cần dò biển, hoặc crop biển/phương tiện lấy từ video tùy nhánh xử lý.
- Ảnh được tiền xử lý theo method, resize/nén JPEG và mã hóa base64 trong phần nội dung ảnh của request.
- Prompt yêu cầu đọc biển, tên model được cấu hình và các tham số request.
- API key nằm trong header Authorization của request tới gateway.

Payload nhận diện không chủ đích chứa mật khẩu người dùng, cookie phiên hoặc database. Tuy nhiên, ảnh toàn cảnh/crop phương tiện có thể chứa nội dung ngoài biển số; không mô tả tính năng này như chỉ gửi chuỗi ký tự.

## Cấu hình và chạy cục bộ

Các biến nằm trong `src/config.py` và [.env.example](../.env.example): `OCR_ENGINE`, `NINEROUTER_BASE_URL`, `NINEROUTER_API_KEY`, `NINEROUTER_MODEL`, `NINEROUTER_TIMEOUT`, `VIDEO_NINEROUTER_TIMEOUT`. Tên model là chuỗi cấu hình; cần đối chiếu model gateway thực tế cung cấp, không coi tên ví dụ là model đã xác minh.

Default code chọn `OCR_ENGINE=hybrid`; `.env.example` hiện chọn `9router`. Khi chỉ muốn nhận diện local qua API ảnh, đặt `OCR_ENGINE=yolo` trong `.env` rồi khởi động lại backend. Mode fast của API video đã tắt remote. Không thay cấu hình tài khoản hoặc API key thật chỉ để chạy test.

Benchmark ảnh local và `benchmark/benchmark_video.py` không gửi ảnh qua NineRouter. Khi đánh giá hybrid, dùng manifest riêng, ghi rõ gateway/model/thời gian chờ và tách kết quả khỏi local. Không dùng kết quả hybrid để kết luận hệ thống offline đạt cùng độ chính xác.

Độ trễ, chi phí và mức đóng góp độ chính xác của remote trong đợt đồng bộ tài liệu: **chưa đo**.
