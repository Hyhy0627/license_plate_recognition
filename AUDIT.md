# Kiểm toán dự án ALPR — giai đoạn 0

Ngày kiểm tra: **19/11/2026**, múi giờ Asia/Bangkok.

Phạm vi: working tree hiện tại, gồm cả thay đổi và file chưa commit; HEAD trước kiểm toán là `32d57e7`. Đây không phải báo cáo chỉ về nội dung của commit HEAD. Yêu cầu thực hiện lấy từ [form.md](form.md). Giai đoạn này chỉ bổ sung báo cáo, không sửa thuật toán, cấu hình nghiệp vụ, di chuyển hoặc xóa file. Không in nội dung `.env`, API key, mật khẩu hay dữ liệu tài khoản.

## 1. Thông tin đã xác minh

| Hạng mục | Kết quả thực tế | Bằng chứng |
|---|---|---|
| Frontend | Next.js **16.4.5**, React/React DOM **19.3.0** | `frontend/package.json`, đọc package đã cài trong `frontend/node_modules/` |
| Backend | FastAPI **0.143.0**, Starlette **1.7.0**, SQLAlchemy **2.1.6** | `importlib.metadata.version()` trong Python của `venv` |
| Mật khẩu | **scrypt**, N=32768, r=8, p=3, salt ngẫu nhiên 16 byte, khóa 32 byte | `src/api/auth.py::hash_password`, `verify_password` |
| Phiên đăng nhập | Cookie `platesight_session`, token ngẫu nhiên; DB chỉ lưu SHA256 của token, có hết hạn và thu hồi | `get_current_user`, `start_session`, `logout` |
| API | Tiền tố **`/api/`**, không có `/api/v1/` | Sinh `app.openapi()` từ `main.app` hiện tại |
| Database | **SQLite**, file `data/alpr.db` | Đọc dialect từ settings hiệu lực và schema SQLite bằng kết nối `mode=ro` |
| OCR ảnh | `models/LP_ocr.pt`; cấu hình hiệu lực `OCR_ENGINE=hybrid` | Đọc settings và gọi factory nạp model trong tiến trình kiểm tra riêng |
| OCR video | CCT ONNX qua `VideoPlateOCR(PlateReader)`; `VIDEO_ENGINE=onnx` | Factory `get_video_engines()` nạp thành công |
| NineRouter | Vẫn được sử dụng trong các nhánh ảnh/video có điều kiện; client được khởi tạo ở cấu hình hiện tại | Đọc route, OCR engine, tracker; không gửi ảnh lên dịch vụ khi kiểm toán |
| Kiến trúc | Backend monolith có các module; frontend chạy riêng; worker video nằm trong tiến trình backend | `main.py`, `src/api/video_routes.py`, `_inference_lock` |

Hai lựa chọn bcrypt/PBKDF2 trong mẫu `form.md` không khớp code: thuật toán thực tế là scrypt. Không thay thuật toán chỉ để khớp mẫu.

Phiên bản AI đã cài: PyTorch 2.14.1, Ultralytics 8.4.190, Fast Plate OCR 1.1.0, ONNX Runtime 1.32.0. Các giới hạn `>=` trong `requirements.txt` không khóa toàn bộ môi trường về các phiên bản này.

## 2. Đối chiếu tài liệu với code

| Tài liệu nói gì | Code/thực trạng là gì | Kết luận |
|---|---|---|
| `PROJECT_STRUCTURE.md` ghi Next.js 16 | Package và bản cài là 16.4.5 | Đúng ở cấp phiên bản lớn |
| File này ghi bcrypt và JWT Bearer | Code dùng scrypt và cookie phiên có trạng thái | Sai cơ chế xác thực |
| Sơ đồ ghi `/api/v1/auth`, `/api/v1/recognize`, `/api/v1/video`, `/api/v1/history` | OpenAPI có các đường dẫn tại mục 3 | Các endpoint được mô tả không tồn tại |
| Có Admin/Guest và quyền quản trị toàn bộ lịch sử | `User` không có cột role; dữ liệu được lọc theo `owner_id` | Không có RBAC Admin/Guest như mô tả |
| Có `RecognitionHistory`, `AuditLog`, bảng `recognition_history` | ORM và DB có `PlateHistory`, `User`, `UserSession`, `AuthAttempt` | Sai tên và chức năng bảng |
| `migrations.py` seed sẵn tài khoản | Chỉ tạo bảng, bổ sung `owner_id`, tạo index; không seed | Sai; không cần thêm seed để hợp thức hóa tài liệu |
| `PROJECT_STRUCTURE.md` công bố tài khoản có mật khẩu mặc định | README hướng dẫn đăng ký; runtime code không có seed hai tài khoản đó | Tài liệu mâu thuẫn; không xác minh mật khẩu người dùng trong DB |
| OCR ảnh được mô tả chủ yếu bằng PaddleOCR/EasyOCR | Route ảnh gọi YOLO OCR; EasyOCR dòng là nhánh bổ trợ; engine truyền thống lazy-load | Thiếu engine chính và thứ tự xử lý |
| `plate_regions.py` được mô tả như công cụ deskew | Route sử dụng module để tạo vùng ứng viên biển số; deskew/tiền xử lý còn nằm trong module khác | Mô tả trách nhiệm chưa chính xác/đầy đủ |
| Video/Camera Stream, xử lý stream được mô tả như tính năng hiện tại | API nhận `UploadFile`, trả tiến trình và metadata; không có endpoint RTSP/camera live | Chỉ xác minh video tải lên |
| `data/video_jobs` được mô tả là video kết quả | Route lưu video tải lên và phục vụ lại file bằng `FileResponse`; frontend vẽ overlay metadata | Không phải video đã render annotation |
| `next.config.ts` có API proxy | Không có `rewrites` hoặc proxy; frontend gọi `NEXT_PUBLIC_API_URL` | Sai mô tả cấu hình |
| Frontend giữ JWT/token và user role | Auth provider đọc `/api/auth/me`; fetch gửi cookie; kiểu User chỉ có id/name/email | Sai mô tả frontend |
| `PROJECT_STRUCTURE.md` có `tool/` và script báo cáo đang hoạt động | `tool/` không tồn tại; công cụ ở `scripts/`, `benchmark/`, `notebooks/`; script báo cáo đã lưu cục bộ từ công việc trước | Cây thư mục lỗi thời |
| Cây model ảnh chỉ nêu `best.pt` | Startup còn bắt buộc `LP_ocr.pt` | Thiếu model bắt buộc |
| `PROJECT_STRUCTURE.md` ghi 82 tests như số cố định | Chưa có kết quả hoàn tất của toàn bộ pytest ở lần kiểm toán này | Không dùng số này làm kết quả hiện tại |
| Tuyên bố dưới 15ms/frame, siêu nhẹ, cực kỳ mượt mà | Chưa đo các chỉ số này trong lần kiểm toán | Bỏ hoặc gắn với bằng chứng đo có thể kiểm tra ở giai đoạn 1 |
| PostgreSQL được mô tả cho production | Session có thể nhận URL khác SQLite và có dependency driver; DB hiện tại là SQLite | Chưa xác minh PostgreSQL hoặc vận hành production |
| Backend được mô tả Microservice-ready | AI, route và executor chạy chung tiến trình; không có worker phân tán độc lập | Nên mô tả backend là modular monolith |

Không tìm thấy `project_overview.json` và `project_structure.json` ở thư mục gốc lúc kiểm toán; không tự tạo JSON để thay thế một nguồn thông tin chưa có.

## 3. Endpoint lấy từ OpenAPI thực tế

Sinh bằng `from main import app; app.openapi()`, không gọi lifespan hoặc chạy migration trên DB thật. Có **12 tổ hợp phương thức/đường dẫn** trong schema:

| Method | Đường dẫn |
|---|---|
| GET | `/` |
| POST | `/api/auth/register` |
| POST | `/api/auth/login` |
| GET | `/api/auth/me` |
| POST | `/api/auth/logout` |
| POST | `/api/license-plates/detect` |
| GET | `/api/license-plates/history` |
| GET | `/api/license-plates/search` |
| GET | `/api/license-plates/{detection_id}` |
| POST | `/api/video-tracking/jobs` |
| GET | `/api/video-tracking/jobs/{job_id}` |
| GET | `/api/video-tracking/jobs/{job_id}/media` |

Ngoài OpenAPI: GET `/static/{category}/{filename}` có kiểm tra đăng nhập và chủ sở hữu. Các route tài liệu là `/docs`, `/docs/oauth2-redirect`, `/redoc`, `/openapi.json`. Không có endpoint quản trị tài khoản, export lịch sử hoặc API phiên bản v1 trong schema hiện tại.

## 4. ORM và schema SQLite thật

| Model | Bảng | Các cột |
|---|---|---|
| `User` | `users` | `id`, `name`, `email`, `password_hash`, `created_at` |
| `UserSession` | `user_sessions` | `token_hash`, `user_id`, `expires_at` |
| `AuthAttempt` | `auth_attempts` | `id`, `key`, `created_at` |
| `PlateHistory` | `plate_history` | `id`, `owner_id`, `plate_number`, `confidence`, `plate_type`, `engine_used`, `cropped_plate_url`, `annotated_image_url`, `created_at` |

Các bảng/cột trên hiện diện trong cả `Base.metadata` và `PRAGMA table_info` của DB hiện tại. Thứ tự cột có thể khác do migration cũ. `owner_id` vẫn nullable; lịch sử chưa gán chủ sở hữu không tự động trở thành dữ liệu công khai.

Phân quyền là theo tài khoản/chủ sở hữu, không phải vai trò. Ảnh static kiểm tra bản ghi thuộc người dùng; video job giữ `owner_id` trong bộ nhớ và kiểm tra trước khi đọc tiến trình/media. Video job không có bảng ORM riêng. Cookie có HttpOnly, SameSite=Lax; Secure bật theo cấu hình hoặc môi trường production. Có giới hạn thử đăng nhập/đăng ký và kiểm tra Origin cho request thay đổi dữ liệu.

Không tìm thấy `SECRET_KEY` trong auth/config/migration hiện hành. Cơ chế phiên opaque hiện tại không ký JWT, nên không suy ra thiếu SECRET_KEY là lỗi. Token phiên được sinh bằng `secrets.token_urlsafe(32)`.

## 5. Model thực sự nạp và nhánh gửi dữ liệu ra ngoài

Đã nạp factory trong tiến trình Python riêng, không gọi nhận diện từ xa:

| Thành phần | File/cơ chế | Kết quả |
|---|---|---|
| Detector ảnh | `models/best.pt` | Nạp thành công |
| OCR ảnh | `models/LP_ocr.pt` | Nạp thành công |
| Detector biển video | `models/video/DetectLisence_YOLO11.pt` | Nạp thành công |
| OCR video | `models/video/cct_s_v1_vn.onnx` + YAML tương ứng | Nạp thành công |
| EasyOCR dòng | `models/easyocr/english_g2.pth` | Có file, nhưng reader chưa nạp ở lần khởi tạo này; lazy-load |
| PaddleOCR/EasyOCR truyền thống | `_get_traditional_ocr()` | Chưa nạp ở lần khởi tạo này |
| Detector phương tiện | `yolov8n.pt` tại gốc | Có file; code tạo YOLO riêng cho mỗi video; không chạy video mới trong giai đoạn 0 |
| `models/best_toy.pt` | File bổ sung | Có file; chưa chứng minh thuộc luồng runtime mặc định |

Không kết luận kiến trúc hay nguồn huấn luyện của một trọng số chỉ dựa trên tên file. Nguồn mã/model video được ghi trong `THIRD_PARTY_NOTICES.md`; việc có mã tích hợp không biến model kế thừa thành model nhóm tự huấn luyện.

NineRouter là HTTP client cho dịch vụ Vision qua gateway, gọi `/chat/completions`; không phải OCR model chạy trong backend. Gateway có thể nằm ở localhost nhưng có thể chuyển dữ liệu đến nhà cung cấp khác. Ảnh được chuyển JPEG/base64, gửi cùng prompt và tên model cấu hình; request có Authorization dùng API key. API key không được sao chép vào báo cáo.

- Route ảnh thử các nhánh local trước; nếu không có biển hợp lệ và client sẵn sàng, có tối đa một lời gọi nhận diện từ xa: crop ứng viên, hoặc ảnh toàn cảnh khi không có ứng viên phù hợp. Kiểm tra availability là request riêng.
- `PlateOCREngine.recognize_plate()` còn có nhánh ưu tiên remote ở mode `9router`; không được lấy mô tả riêng method này thay cho thứ tự xử lý của route ảnh.
- Video `fast` qua API không bật remote. `combined`/`detailed` có thể gọi remote theo cấu hình, với danh sách ứng viên giới hạn trong tracker. Dữ liệu gửi có thể là crop biển, crop phương tiện hoặc vùng ảnh tương ứng, không chỉ chuỗi ký tự.
- Client NineRouter được khởi tạo ở cấu hình hiệu lực `hybrid`; client của `VideoPlateOCR` là `None`. Khởi tạo client không chứng minh dịch vụ hiện hoạt động.
- `.env.example` chọn `OCR_ENGINE=9router`, trong khi default code và cấu hình hiệu lực là `hybrid`; danh sách lựa chọn trong example chưa liệt kê `hybrid`. Example thiếu `CROPPED_PLATES_DIR`, `FINAL_RESULTS_DIR`, có `STATIC_URL_PREFIX` không có trường tương ứng trong Settings. Tên model gateway giữa example và default code cũng khác; chưa xác minh các tên đó có tồn tại ở dịch vụ.

## 6. File/thư mục cần xử lý sau khi duyệt

Đây là danh sách đề xuất, **chưa di chuyển/xóa** ở giai đoạn 0:

| Đường dẫn | Quan sát | Đề xuất |
|---|---|---|
| `PROJECT_STRUCTURE.md` | Trùng nội dung hướng dẫn nhưng chứa nhiều sai lệch | Đồng nhất với README; chọn nơi mô tả chi tiết trước khi gộp/xóa |
| `handoff_unpushed/` | Bản bàn giao cục bộ, đã ignore; có cả ZIP và thư mục giải nén | Giữ tới khi kiểm tra khác biệt và lưu patch/branch cần thiết |
| `yolov8n.pt` | Model runtime ở gốc, đã ignore | Chuyển vào `models/` ở giai đoạn 2, cập nhật config, Compose, thông báo lỗi và tài liệu |
| `.env` | Cấu hình máy hiện tại, đã ignore | Giữ cục bộ; chuẩn hóa example, không sao chép secret |
| `data/test_cases/` | 40 JPG tổng hợp và nhãn đang được Git theo dõi | Chuyển thành fixture; cập nhật benchmark, notebook và tài liệu liên quan |
| `data/outputs/` | Kết quả runtime có thể được DB tham chiếu | Không xóa theo tuổi/tên file; mở rộng ignore |
| `.local_archive/` | Kho khôi phục từ lần dọn trước, đã ignore | Không đưa vào bản clone; không xóa khi chưa duyệt |
| `external/LicensePlateDetection/` | Bản clone đối chiếu cục bộ; runtime dùng mã trong `src/` | Không đưa bản clone/nested Git vào repository chính |
| `docs/~$cense_plate_recognition_latest.docx` | File khóa Word, đã ignore | Không coi là DOCX báo cáo, không đụng khi có thể đang mở Word |
| `docs/figures/ablation_study.png` và các biểu đồ khác | Có ảnh; tên file không chứng minh thực nghiệm đã chạy | Tìm dữ liệu nguồn trước khi công bố số liệu hoặc loại bỏ |
| `models/best_toy.pt` | Không phải model mặc định trong settings | Kiểm tra nhu cầu thực nghiệm trước khi loại bỏ |
| `tool/`, `docs/presentation/` | Không tồn tại trong working tree hiện tại | Không tạo lại chỉ để khớp tài liệu cũ |

`scripts/` hiện có script cài model; `benchmark/` chứa công cụ đo; `notebooks/` có runner. Script báo cáo và `test_single_video.py` đã nằm trong `.local_archive/cleanup_20261119/` từ công việc trước. Bản sao `test_single_video.py` còn trong handoff. Không thấy `pytest.ini`/`pyproject.toml`/`setup.cfg` ở gốc để khóa discovery về `tests/`; chạy `pytest` trần cần được kiểm tra riêng vì bản sao cục bộ có tên `test_*.py`. Lệnh kiểm thử ở lần này chỉ định `tests/`.

### Đối chiếu handoff

So sánh byte của **20 file giải nén** với vị trí tương ứng hiện hành, có ánh xạ đường dẫn công cụ đã chuyển: **14 giống, 6 khác, 0 không tìm được bản đối chiếu**. File đã lưu archive được đối chiếu với archive, không coi là code runtime.

Sáu file khác:

- `04_Vy/docs/video_onnx.md`
- `04_Vy/README.md`
- `04_Vy/src/core/video_models.py`
- `04_Vy/src/core/video_tracker.py`
- `04_Vy/tool/setup_video_models.py`
- `05_Y_Huynh/README.md`

Khác biệt tracker có thay đổi cách ghép biển vào phương tiện, ghi timestamp quan sát và xử lý track; adapter/script khác do tích hợp `PlateReader` và đổi đường dẫn. Chưa kết luận một phía hoàn toàn thay thế phía kia. `04_Vy.zip` có 15/15 file giống bản giải nén; `05_Y_Huynh.zip` có 5/5 file giống bản giải nén. Có thể đề xuất loại bản ZIP trùng ở giai đoạn 2, nhưng chưa xóa.

## 7. Kiểm tra Git và dữ liệu runtime

Đã dùng cả `git ls-files` và `git check-ignore`, không chỉ đọc `.gitignore`:

| Đường dẫn | Được track hiện tại? | Quy tắc ignore |
|---|---|---|
| `.env` | Không | Có |
| `data/alpr.db` | Không | Có |
| File trong `data/video_jobs/` | Không | Có |
| Ảnh trong `data/outputs/cropped_plates/`, `final_results/` | Chỉ hai `.gitkeep` được track | Có cho nội dung ảnh; giữ ngoại lệ `.gitkeep` |
| `data/outputs/test_video_result.json` | Không có trong danh sách tracked | **Không được ignore**; đường dẫn thử chứng minh lỗ hổng quy tắc |
| `data/test_cases/` | Có | Chủ đích giữ fixture hiện tại |
| `handoff_unpushed/` | Không | Có |

Kết quả chỉ nói về index hiện tại, chưa kiểm toán toàn bộ lịch sử Git để xác định secret đã từng bị commit hay chưa. Không có nội dung staged từ trước lúc chuẩn bị commit báo cáo.

## 8. Bằng chứng đánh giá và kiểm thử

### Mâu thuẫn/tài liệu chưa đủ bằng chứng

- README, `tests/TESTING.md`, `benchmark/ACCURACY.md`, `notebooks/README.md` phân biệt dữ liệu tổng hợp và ảnh thật. `PROJECT_STRUCTURE.md` mô tả tập có nhãn mà bỏ qua giới hạn tổng hợp; không được diễn giải nó thành bằng chứng giao thông thật.
- DOCX hiện nói scrypt, không có JWT/bcrypt hay `/api/v1` trong phần text kiểm tra; khác với `PROJECT_STRUCTURE.md`. DOCX dùng Guest cho người chưa đăng nhập, khác với vai trò tài khoản Guest có sẵn trong tài liệu cấu trúc.
- DOCX có kết quả lịch sử 82 test Python/14 kịch bản browser và dẫn lượt `system_20261119T042439_305445Z`; thư mục bằng chứng này hiện không tồn tại. Không gọi số liệu lịch sử là kết quả hiện tại hoặc kết luận nó bịa chỉ vì thiếu file.
- `docs/video_onnx.md` dẫn `data/benchmarks/video_legacy_combined.json`, `video_onnx_fast_5fps.json`, `video_api_smoke.json`; cả ba không tồn tại ở workspace lúc kiểm toán. Vì thế chưa xác minh lại được các số giây/hệ số tăng tốc ghi trong tài liệu.
- `benchmark/benchmark_all.py` chạy pytest, TypeScript và ESLint, tùy chọn browser/model thật; không chạy `next build` như mô tả trong cây thư mục cũ.
- Chưa có `training/` hoặc `.github/workflows/ci.yml` ở vị trí được form yêu cầu. Chưa xác minh tập tracking có nhãn, MOTA/IDF1 hoặc ablation từ dữ liệu nguồn. Không tự sinh dữ liệu hoặc số liệu thay thế.

Phạm vi đọc tài liệu: Markdown hướng dẫn hiện hành, cấu hình và text của DOCX bằng XML. Chưa trích xuất/đối chiếu PDF vì môi trường kiểm tra không có pypdf/PyMuPDF; chưa kiểm tra hình, biểu đồ và nội dung ảnh trong DOCX/PDF. Không tuyên bố đã rà hết mâu thuẫn trong các đối tượng nhúng.

### Lệnh kiểm tra và kết quả thật

| Lệnh/thao tác | Kết quả ngày kiểm toán |
|---|---|
| Sinh `main.app.openapi()` trong Python của `venv` | Thành công; 12 tổ hợp method/path |
| Đọc `Base.metadata`, schema SQLite với `mode=ro` | Thành công; 4 bảng tương ứng |
| Gọi `get_detector()`, `get_ocr_engine()`, `get_video_engines()` trong tiến trình riêng | Nạp model ảnh/video thành công; không gửi ảnh lên cloud |
| `git ls-files`, `git check-ignore`, so sánh byte handoff/ZIP | Hoàn tất; kết quả tại mục 6–7 |
| `docker compose config --quiet` | Exit 0; chỉ xác nhận cấu hình Compose, không chứng minh container khởi động |
| `frontend/node_modules/.bin/tsc.cmd --noEmit --incremental false -p frontend/tsconfig.json` | Exit 0 |
| `npm --prefix frontend run lint` | Exit 0 |
| `venv/Scripts/python.exe -B -u -m pytest tests -vv -p no:cacheprovider` | Không hoàn tất trong giới hạn 60 giây; không có tổng pass/fail/skip cuối cùng |
| `venv/Scripts/python.exe -B -u -m pytest tests/test_benchmark.py tests/test_video_models.py tests/test_notebook_evidence.py tests/test_plate_reader.py -q -p no:cacheprovider` | **25 passed, 1 warning, 1.21s** |

Hai lệnh pytest được chạy với `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`, `PYTHONUTF8=1` trong tiến trình con có timeout; không đổi cấu hình dự án. Runner bao ngoài của lượt toàn bộ bị lỗi định dạng output khi xử lý timeout (`AttributeError`), nên không giữ được chi tiết tiến trình test tại thời điểm đó. Không suy ra số test đã chạy hoặc nguyên nhân treo; tổng kết toàn bộ vẫn là **chưa xác minh**.

Warning của lượt 25 test là `PydanticDeprecatedSince20`: `Settings.Config` dạng class đã deprecated. Giai đoạn 0 chưa sửa cấu hình này.

Chưa chạy `docker compose up`, build frontend production, Playwright hoặc benchmark AI mới trong giai đoạn 0. Tốc độ/độ chính xác hiện tại: **chưa đo**. Không lấy kết quả test phần mềm làm độ chính xác AI.

## 9. Điểm dừng và thứ tự tiếp theo

Giai đoạn 0 chỉ bổ sung `AUDIT.md`. Giữ nguyên các thay đổi chưa commit có từ trước, không đưa chúng vào commit kiểm toán.

Theo form: **dừng và báo cáo trước khi sang giai đoạn 1**. Sau khi được duyệt:

1. Đồng nhất README/tài liệu cấu trúc theo các sự thật đã xác minh; loại thông tin tài khoản mặc định, API/role không có và số liệu thiếu bằng chứng. Liệt kê bản trùng trước khi đề xuất xóa.
2. Chốt bố trí tài liệu/công cụ và kiểm tra patch handoff trước khi dọn; không ghi đè các thay đổi tracker đang có. Dùng `git mv` cho file đã tracked; file hiện chưa tracked phải xử lý rõ trạng thái trước khi di chuyển.
3. Chuyển model phương tiện/fixture có kiểm soát, cập nhật mọi tham chiếu; bổ sung ignore và checksum. Không xóa DB hoặc ảnh runtime.
4. Điều tra bộ pytest đầy đủ chưa kết thúc trước khi nhận các tiêu chí toàn bộ test xanh hoặc tái cấu trúc nhẹ. Chưa có căn cứ thêm Alembic/seed/SECRET_KEY chỉ để làm đủ danh sách.

Không có thay đổi code AI, endpoint, schema hoặc phân quyền được áp dụng trong giai đoạn này.
