# Backend hardening theo form.md

Thực hiện ngày 19–20/11/2026, Asia/Bangkok. Working tree chưa commit; HEAD giữ nguyên `6d60ac65e94404bdc8e4ea87a1ec5f4388338068`, Git index rỗng. Yêu cầu trực tiếp **không commit** được ưu tiên hơn các mục commit trong form. Không sửa `.env`, trọng số, dữ liệu đầu vào hoặc frontend trong đợt này.

## Phạm vi từng giai đoạn

Khi bắt đầu, working tree đã chứa triển khai giai đoạn 1, 3, 4, 5 và phần lớn giai đoạn 6, cùng test tương ứng. Các phần này được đọc và kiểm chứng lại; không coi chúng là thay đổi mới của phiên này. Không xóa assertion cũ. Kết quả suite cuối áp dụng cho toàn bộ các giai đoạn dưới đây.

| Giai đoạn | File và hành vi hiện tại | Kiểm chứng |
|---|---|---|
| 1 — khóa suy luận | `src/services/image_recognition.py`, `model_runtime.py`: decode, crop, cloud availability/recognition, UUID output, imwrite, db.add/commit ngoài `_inference_lock`; detector và local OCR có khóa. LocalLineOCR có khóa riêng, lazy load không giữ khóa YOLO. | `tests/test_inference_lock.py`: hai biến thể cloud crop/toàn ảnh bị chặn bằng Event; request local thứ hai vẫn xong trước khi cloud được giải phóng. Assertion kiểm tra decode/imwrite/DB không giữ khóa. |
| 2 — OCR | `src/core/ocr/engine.py`, `src/core/image/preprocessor.py`, `src/services/image_recognition.py`, `model_runtime.py`, `main.py`, `src/config.py`, `.env.example`: chọn polarity một lần; biển hợp lệ >=0.70 thoát sớm; chỉ retry low-threshold/Otsu/deskew khi chưa hợp lệ; upscale chỉ khi h<40 bằng linear. Engine `onnx/cct` dùng VideoPlateOCR, startup/health chấp nhận CCT không cần YOLO ký tự. | `tests/test_ocr_optimization.py`, `test_hard_cases.py`, `test_startup.py`; model thật trên ba ảnh có nhãn và bốn ảnh khó hiện còn. |
| 3 — video | `src/db/models.py`, `migrations.py`, `src/services/video_jobs.py`, `src/api/video_routes.py`, `requirements.txt`: VideoJob lưu SQLite, tiến trình/kết quả/error/timestamp; admission tối đa hai job qua giao dịch; lease file phân biệt worker sống/chết; media dùng Range của Starlette FileResponse. | `test_video_media.py`, `test_video_tracking.py`, `test_user_workflows.py`: Range 206 đúng nội dung/header, suffix range, 416 ngoài file, 401/404 cách ly owner, kết quả qua connection mới, job gián đoạn giải phóng slot. |
| 4 — DB/rate limit | `src/db/models.py`, `migrations.py`, `src/services/history.py`, `authentication.py`: cột clean có index, validator ghi cột khi nhận diện; migration backfill từng lô và idempotent. Sliding window deque/Counter có Lock, 30/IP và 10/email mỗi action/900s; không ghi bảng auth_attempts. | `test_auth.py`, `test_seeding.py`: search chuẩn hóa/phân trang/owner, migration hai lần, IP/window/action, đồng thời 30 attempt chỉ chấp nhận 10 cùng email, HTTP 429 Retry-After=900. |
| 5 — domain exception | `src/core/exceptions.py`, các service, `src/api/auth.py`, `src/api/routes.py`, `main.py`: service độc lập FastAPI; adapter xử lý cookie/dependency; domain handler giữ JSON detail và status 400/401/403/404/409/413/429/503. | Các HTTP journey, invalid payload, logout/revocation, missing record và queue capacity trong suite cuối. |
| 6 — quan sát | `main.py`, `src/utils/logger.py`, `src/config.py`, `model_runtime.py`: ID hợp lệ từ client hoặc UUID v4, context log, process time ms; deep health DB SELECT 1/model/output temp file; SettingsConfigDict loại bỏ cảnh báo Pydantic. | `test_startup.py`: startup bắt lỗi model thiếu, CCT được chấp nhận, headers cả lỗi auth, health 200/503 khi từng thành phần hỏng. `-W error` qua. |
| 7 — bằng chứng | `scripts/benchmark.py` thêm số forward pass vào prediction nội bộ; `scripts/check_regression.py` cho chọn local yolo/onnx/cct; `ruff.toml` cố định đúng bộ quy tắc correctness đang dùng ở CI. `README.md`, `PROJECT_STRUCTURE.md`, `docs/README.md`, `docs/video_onnx.md` đồng bộ hành vi mới. | JSON so sánh và script tái hiện ở [backend_hardening](backend_hardening/). XML, snapshot OpenAPI và đầu ra smoke nằm trong kho cục bộ `.local_archive/vibe_cleanup_20261120/docs/results/backend_hardening/`. |

## Kiểm thử và OpenAPI

Chạy lại từ gốc repository bằng PowerShell. Các đầu ra mới được ghi vào `data/`:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
$env:PYTHONUTF8='1'
.\venv\Scripts\python.exe -B -u -m pytest tests -q -W error -p no:cacheprovider --junitxml=data/benchmarks/backend_hardening/final.xml
.\venv\Scripts\python.exe -m ruff check main.py src scripts tests
.\venv\Scripts\python.exe -B scripts/benchmark.py --dataset-kind synthetic --limit 2 --no-plots --output-root data/benchmarks/backend_hardening/smoke_final
```

| Kiểm tra | Exit code | Kết quả/thời gian |
|---|---:|---|
| Nhận diện + hard cases + inference lock sau sửa OCR ban đầu | 0 | 19 passed, 3.82s |
| Suite đầu sau thêm tối ưu | 0 | 111 passed, 22.57s |
| Suite sau sửa polarity | 0 | 113 passed, 18.95s |
| Suite sau thêm startup CCT | 0 | 114 passed, 19.28s |
| Suite cuối sau bảo toàn ảnh nhiều xe | 0 | **115 passed, 0 failures, 0 skipped, 0 warnings; 19.24s** |
| Ruff với cấu hình repository | 0 | All checks passed; khoảng 0.5s |
| So sánh JSON OpenAPI trước/sau | 0 | **Bằng nhau toàn bộ**, gồm paths, query, responses, schema; khoảng 2s gồm import |
| Smoke 2 ảnh synthetic | 0 | Mean pipeline 471.27ms/ảnh; xem phần dưới |

Các lệnh full pytest ban đầu chạy trong sandbox bị treo ở `socket._fallback_socketpair -> accept` khi asyncio khởi tạo TestClient. Đã lấy stack trace, dừng đúng các tiến trình test bị treo và chạy suite ngoài sandbox; không thay code ứng dụng để né lỗi môi trường. Các lần suite qua ở bảng trên đều chạy với `-W error`. Kết quả XML cuối là `final.xml` trong kho cục bộ nêu trên.

Ruff chỉ kiểm tra `E9,F63,F7,F82`, giữ đúng phạm vi CI đã có; không tuyên bố đã dọn toàn bộ lỗi style/import của dự án. Lần chạy trước khi thêm cấu hình repository chịu cấu hình toàn máy và báo 193 lỗi, phần lớn import/style; không áp dụng hàng loạt autofix lên mã ngoài phạm vi.

Kho cục bộ giữ `openapi_before.json` và `openapi_after.json` để đối chiếu schema. `/` vẫn trả payload cũ; `/api/health` nằm ngoài schema. HTTP media không cần tự viết parser Range: phiên bản Starlette đang cài là 1.7.0, đã hỗ trợ và được test end-to-end. `requirements.txt` đã yêu cầu Starlette >=0.49.1.

## OCR: model thật, cùng crop

[measure_crops.py](backend_hardening/measure_crops.py) lấy thuật toán OCR và polarity từ HEAD, dùng chung model YOLO của working tree, cùng crop detector, CPU hai thread, warmup không tính giờ, ba lượt xen kẽ mỗi biến thể. Không ghi DB/gọi cloud. Baseline là thuật toán trong HEAD được tái hiện, không phải checkout toàn bộ ứng dụng cũ. Nguồn baseline, model, ảnh và mã mới có hash trong [crop_comparison.json](backend_hardening/crop_comparison.json).

| Crop | Forward pass trước → sau | Mean OCR trước → sau (ms) |
|---|---:|---:|
| 69-B1 777.77 | 3 → 1 | 654.66 → 216.13 |
| 30A-111.11 | 2 → 1 | 262.50 → 125.92 |
| 30A-888.88 | 2 → 1 | 294.25 → 159.40 |

Cả ba lượt của mỗi biến thể đều đọc đúng ba crop. Đây là **crop OCR**, không gồm detector, HTTP, giải mã ảnh, lưu file hoặc DB. Tái hiện: `.\venv\Scripts\python.exe -B docs/results/backend_hardening/measure_crops.py` (exit 0, khoảng 15s cả load/warmup/18 lượt đo).

## Service ảnh và CCT

Ba ảnh web dùng nhãn có sẵn từ `docs/results/stage5/web_cases.json`; không sửa ảnh/nhãn. Mỗi run có DB/output riêng; local tắt cloud, CPU hai thread, không warmup service. Số đầu tiên gồm lazy detector load nên không đại diện steady-state.

| Ảnh | YOLO trước (ms) | YOLO sau (ms) | CCT sau (ms) |
|---|---:|---:|---:|
| motorbike_69B1_77777 | 4748.86 | 2861.45 | 2577.35 |
| car_30A_11111 | 1587.60 | 468.22 | 284.03 |
| car_30A_88888 | 1721.28 | 416.61 | 309.33 |

Các run cuối đều đọc đúng 3/3 nhãn, cloud_attempts=0. Đây là development regression với ba ảnh, không phải độ chính xác giao thông thật hay p95. Bằng chứng và code/model/input hash: [service_comparison.json](backend_hardening/service_comparison.json). Chạy từng lệnh dưới đây exit 0; khoảng 9–13s/run gồm import/load, kết quả từng ảnh nằm trong JSON.

```powershell
.\venv\Scripts\python.exe -B scripts/check_regression.py --label review_yolo --mode local --cases docs/results/stage5/web_cases.json
.\venv\Scripts\python.exe -B scripts/check_regression.py --label review_cct --mode local --ocr-engine onnx --cases docs/results/stage5/web_cases.json
```

Benchmark đã phát hiện hai regression trong quá trình sửa và được dùng để sửa lại trước kết quả cuối:

1. Viền thân xe tối làm hàm polarity nhận nhầm biển trắng; OCR ra `90A` thay cho `30A`. Dùng median vùng trung tâm để phân loại nền, vẫn giữ kiểm tra màu xanh. Thêm test ảnh biển trắng có padding tối và ảnh grayscale.
2. Một biển mạnh trong ảnh nhiều xe khiến bỏ qua biển lân cận chưa đọc được. Chỉ bỏ fallback khi **tất cả crop đã phát hiện** đều mạnh và đủ năm số. Vẫn cứu hộ biển bốn số có thể bị cắt ký tự cuối, bảo toàn assertion hồi quy cũ.

Bốn ảnh khó còn trên máy (tróc sơn, mòn, biển xanh bốn số, ảnh bốn xe) đều khớp nhãn sau sửa. Ảnh bốn xe trả đủ 48-B1 999.99, 59-G2 777.77, 54-H4 5555 và 54-L4 3939; thời gian 3436.88ms. Hai ảnh trả dấu phân cách khác nhưng giữ đúng ký tự và grouping theo phép so sánh có sẵn. Bốn đường dẫn synthetic trong manifest cũ `data/test_cases/` không còn tồn tại; lệnh chạy nguyên manifest exit 1 vì FileNotFoundError. Lượt cuối dùng đúng bốn file còn tồn tại, không thay ảnh/nhãn hoặc âm thầm chuyển sang fixture khác; không tính bốn ca thiếu là pass.

## Giới hạn và mục chưa đạt

- **Chưa đạt <200–300ms cho toàn pipeline trên CPU ở mọi ảnh.** Crop OCR cải thiện rõ; detector/lazy load/fallback vẫn có chi phí. CCT là tùy chọn, `.env` thật không bị đổi.
- Smoke trước mean 461.79ms, smoke cuối 471.27ms: hai ảnh đều không có detection, TP=0/FN=2, exact=0, CER=100%; không dùng số này để khẳng định OCR tăng tốc. Báo cáo của lượt cuối nằm trong `smoke_final/` tại kho cục bộ nêu trên.
- **`LIKE '%...%'` không thể tìm theo khoảng B-tree.** Cột clean loại bỏ tính lại replace từng dòng, nhưng không triệt tiêu việc quét các dòng của owner. EXPLAIN thực tế: `SEARCH plate_history USING INDEX ix_plate_history_owner_id (owner_id=?)`; không dùng index clean để tìm substring. Muốn cải thiện tiếp cần FTS/trigram hoặc thay đổi hành vi tìm kiếm; chưa thay contract.
- Rate limit trong RAM áp dụng theo process và reset khi restart; không đồng bộ giữa nhiều backend. Video bền vững yêu cầu DB, uploads và file lock ở volume dùng chung trên cùng máy; chưa xác nhận scale đa máy hay tự tiếp tục video bị ngắt.
- Short-circuit tránh quét toàn cảnh khi các crop đều mạnh; chưa chứng minh recall trên những biển khác mà detector bỏ sót hoàn toàn. Không có tập test độc lập đủ lớn để kết luận không giảm chất lượng mọi tình huống.
- Chưa đo tải lớn, cloud thực sự, p95/p99 hoặc benchmark video AI mới. Unit/integration video kiểm chứng persistence/Range/tracking bằng fixture/mock. Không tái xuất DOCX/PDF trong phạm vi nâng cấp backend của form.

Các mục kỹ thuật đã triển khai/kiểm chứng được giữ trong working tree để xem xét. Hai mục chưa thể đánh dấu đạt nguyên văn là mục tiêu độ trễ toàn pipeline và tuyên bố substring LIKE tận dụng B-tree; mục commit được chủ động bỏ theo yêu cầu người dùng.
