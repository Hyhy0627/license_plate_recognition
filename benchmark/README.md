# Bộ benchmark chức năng và thao tác người dùng

Chạy từ thư mục gốc dự án, Windows PowerShell. Bộ này kết hợp kiểm thử Python,
trình duyệt Edge headless, kiểm tra frontend và phép đo model thật tùy chọn.

## Chạy

```powershell
.\venv\Scripts\python.exe -m pip install -r requirements.txt
npm --prefix frontend ci
npm --prefix benchmark ci
.\venv\Scripts\python.exe benchmark/benchmark_all.py
```

Runner mặc định chọn Edge; trình duyệt và dependency benchmark cần được chuẩn bị riêng trên máy chạy. Để dùng Chromium của Playwright:

```powershell
cd benchmark
npx playwright install chromium
$env:BENCHMARK_BROWSER="chromium"
cd ..
```

Chỉ chạy test Python, TypeScript và ESLint (bỏ trình duyệt):

```powershell
.\venv\Scripts\python.exe benchmark/benchmark_all.py --skip-ui
```

Thêm phép đo model thật (cần trọng số hiện tại và `scripts/setup_video_models.py`):

```powershell
.\venv\Scripts\python.exe benchmark/benchmark_all.py --real --image "data/test_cases/blurred/blur_01.jpg" --video "duong-dan-video.mp4" --iterations 3
```

`--video` tùy chọn. Không truyền `--image` sẽ dùng ảnh tổng hợp `blur_01.jpg`;
đổi sang ảnh giao thông thật khi đánh giá môi trường triển khai. Các tệp mẫu
trong `data/video_jobs` của máy hiện tại không được Git theo dõi.

Model được đo qua API TestClient: đăng ký → kiểm tra phiên → nhận diện ảnh →
lịch sử → tìm kiếm → chi tiết/ảnh crop nếu có → đăng xuất/đăng nhập. Video được
đo từ upload đến hoàn tất và thử HTTP Range. OCR từ xa được tắt. Model thật không
được mock ở bước này. HTTP TestClient không bao gồm độ trễ mạng, TLS hay render UI.

## Đọc báo cáo

Mỗi lần tạo thư mục `data/benchmarks/system_<UTC-run-id>/`:

| Tệp | Nội dung |
|---|---|
| `report.html` | Kết quả từng nhóm, danh sách test Python và bảng thời gian API/model |
| `summary.json` | Kết quả máy đọc được, số pass/fail/skip, thông số môi trường |
| `python.xml`, `python_cases.csv` | Chi tiết và thời gian mỗi ca Python |
| `browser/index.html`, `browser.json` | Từng kịch bản UI, thời gian và bằng chứng |
| `browser-artifacts/` | Screenshot/trace khi lỗi; ảnh trạng thái video được chọn |
| `real/real_models.json` | N, mean, P50, P95, max theo thao tác; cold/warm ảnh; thời gian video |
| `*.log` | Log riêng cho từng bước |

Mã thoát `0`: các nhóm được yêu cầu đều đạt. Mã khác `0`: có bước lỗi, thiếu
thư viện/browser, không khởi động được server hoặc quá thời gian. Nhóm không bật
được ghi rõ là chưa chạy. P95 dùng nearest rank, P50 dùng median; mẫu warm ít thì
chỉ dùng kiểm tra nhanh, không kết luận SLA. Thời gian test gồm cả thiết lập/chờ,
không đồng nghĩa thời gian suy luận. Không tự đặt ngưỡng FPS cho mọi cấu hình máy.

`--iterations` lặp cả đăng nhập; trên 10 vòng có thể chủ động chạm rate limit
đăng nhập 15 phút. Đây là hành vi bảo vệ thật, không tắt trong benchmark. Để đo
suy luận nhiều vòng, dùng benchmark offline hiện có thay vì vô hiệu hóa giới hạn.

## Ma trận bao phủ

| Nhóm | Thao tác/điều kiện được kiểm tra | Nguồn |
|---|---|---|
| Tài khoản | Đăng ký, email trùng/sai, tên trống, mật khẩu yếu, xác nhận sai, ẩn/hiện mật khẩu | `tests/test_auth.py`, UI `register validation...` |
| Phiên | Đăng nhập đúng/sai, refresh, logout, cookie thu hồi/giả/hết hạn, khôi phục kết nối | Auth tests, UI `expired session...` |
| Bảo vệ | Chặn khách ở ảnh/video/lịch sử, CORS/CSRF, hash mật khẩu, throttle | Auth tests, UI `guest redirects...` |
| Ảnh | Chọn tệp tự nhận diện, kéo thả, paste, nhiều biển/chọn tab, bật/tắt annotation, thay/xóa ảnh | UI `image...` |
| Lỗi ảnh | Định dạng sai, >10 MB, rỗng, hỏng, API lỗi, thử lại, không tạo lịch sử khi lỗi | Workflow API + UI |
| Chuẩn hóa/OCR | Biển 1/2 dòng, seri chữ/số, xe điện, crop thiếu ký tự, nghiêng, âm tính, cloud budget | Recognition/hard case tests |
| Lịch sử | Lưu kết quả thật qua handler, phân trang, tìm có/không khớp, chuẩn hóa query, xóa tìm, refresh | Workflow API, Auth tests, UI history |
| Phân quyền | Tài khoản khác không đọc được lịch sử, chi tiết, crop hoặc video của chủ sở hữu | Auth + workflow + video media tests |
| Video | Chọn tệp tự chạy đúng một job, polling, chạy lại, ID, chọn xe/keyboard, hover chỉ một nhãn, controls | UI `video auto analysis...`, video tracking tests |
| Lỗi video | Sai đuôi, >100 MB, rỗng, metadata sai, >45 giây, quá Full HD, thiếu model, mode sai, job thất bại, ID không tồn tại, hàng đợi đầy, thu hồi tệp upload lỗi | Workflow API, `test_video_validation.py` + UI |
| Model video | RGB đúng, bỏ confidence padding, OCR yếu/thiếu model, bỏ phiếu, gán biển đúng xe | `test_video_models.py`, `test_video_tracking.py` |
| Media | HTTP Range và quyền chủ sở hữu video | `test_video_media.py`, workflow API, real-model benchmark |
| Khởi động | Thiếu detector/OCR phải báo lỗi, model đủ mới khởi động thành công | `test_startup.py` |
| Mobile | Ba trang chính ở 390×844 không tràn ngang toàn trang | UI mobile |
| Chất lượng mã | TypeScript, ESLint; metric/annotation và notebook evidence | Runner + test hiện có |

Không có chức năng xóa lịch sử, reset mật khẩu hay camera live hoàn chỉnh để
khẳng định đã kiểm tra các chức năng đó. Nút quên mật khẩu hiện chỉ thông báo
chưa hỗ trợ. Bộ test không biến một tính năng chưa có thành kết quả đạt.

## Ranh giới và kiểm tra bổ sung

- Python có auth, database, HTTP và xử lý tệp thật; các ca luồng mới dùng đầu ra
  detector/OCR có kiểm soát để xác minh hành vi lưu/trả dữ liệu, không đo độ đúng AI.
- UI dùng trình duyệt thật nhưng giả lập toàn bộ API và ảnh trả về. Clipboard/drop
  được phát bằng sự kiện DOM; không kiểm tra quyền clipboard của hệ điều hành.
- Video UI dùng tệp hỏng có kiểm soát để kiểm tra trạng thái lỗi phát và job độc lập.
  Giải mã video thật, nút phát/tạm dừng, toàn màn hình, âm lượng và codec cần kiểm
  tra thủ công bằng MP4 H.264 trên từng browser/thiết bị; API Range có test riêng.
- Lỗi JavaScript chưa xử lý được đính kèm `runtime-warnings`; các assertion chức
  năng có thể vẫn đạt. Xem attachment để xử lý lỗi hydration hoặc lỗi runtime.
- Đây không phải kiểm thử tải đồng thời lớn, pentest hay kiểm tra mọi browser.
  Edge desktop và viewport mobile là phạm vi chạy mặc định.
- Độ chính xác AI cần nhãn đối chứng. Dùng `benchmark/benchmark.py` với bộ có nhãn;
  không suy ra accuracy từ số test đạt hoặc số biển model trả về.

## Cách ly dữ liệu

API test dùng SQLite bộ nhớ và thư mục pytest tạm. UI dựng Next riêng trên
`127.0.0.1:13000`, cache `.next-benchmark`, chặn API bằng fixture; không cần backend
8000 và không dùng tài khoản thật. Cổng 13000 phải trống, không tự dùng lại server
có sẵn. Bước model thật tạo SQLite và ảnh/video trong chính thư mục báo cáo.
Các báo cáo/caches trong thư mục đầu ra được ignore; khi công bố kết quả, trích xuất lệnh, cấu hình và bằng chứng được kiểm tra vào `docs/results/`, không đưa tài khoản hoặc dữ liệu nhạy cảm vào báo cáo. Giữ báo cáo để đối chiếu trước/sau cùng
fixture SHA256, số vòng, chế độ và máy chạy.

Chạy riêng một ca để tái hiện lỗi:

```powershell
.\venv\Scripts\python.exe -m pytest tests/test_user_workflows.py -v
npm --prefix benchmark test -- --grep "video auto analysis"
npm --prefix benchmark exec -- playwright show-report "../data/benchmarks/browser_latest/browser"
```

## Công cụ đánh giá

| Script | Mục đích |
|---|---|
| `benchmark_all.py` | Chạy pytest, TypeScript, ESLint, tùy chọn Playwright và phép đo model thật; không chạy production build |
| `benchmark.py` | Đo độ chính xác trên ảnh có nhãn; xem [hướng dẫn](ACCURACY.md) |
| `benchmark_video.py` | Đo xử lý một video |
| `benchmark_user_workflows.py` | Đo thao tác API với model thật |
| `check_regression.py` | So sánh kết quả nhận diện trước và sau thay đổi |

Các công cụ này không cần thiết để khởi động ứng dụng.

## Trạng thái kết quả

Tài liệu này mô tả cách chạy và phạm vi assertion, không chứng nhận tất cả kịch bản hiện đã đạt. Kết quả theo lần chạy được ghi tại [docs/results/documentation_sync.md](../docs/results/documentation_sync.md). Số test phụ thuộc phiên bản code; không cố định một số lượng trong hướng dẫn. Production build cần chạy riêng bằng `npm --prefix frontend run build`.
