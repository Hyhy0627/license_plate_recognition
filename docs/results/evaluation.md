# Giai đoạn 5 — Đánh giá và kiểm thử

Ngày chạy: **19/11/2026**, múi giờ Asia/Bangkok (UTC+7). Mốc UTC chính xác, câu lệnh, exit code, thời gian, log, hash dữ liệu/model/mã và phản hồi từng ảnh được lưu trong [evidence.json](stage5/evidence.json). Đây là kết quả của working tree chưa commit, không phải kết quả riêng của HEAD `6d60ac6`. Không tạo commit theo yêu cầu tiếp tục từ giai đoạn 4.

## Thay đổi

- Thêm `.github/workflows/ci.yml`: lint/test backend trên Python 3.11 và lint/typecheck/build frontend trên Node 22, runner Ubuntu 24.04, quyền `contents: read`.
- Thêm `requirements-dev.txt`, khai báo HTTPX cho TestClient và Ruff. Lint backend chọn `E9,F63,F7,F82` để bắt lỗi cú pháp/tên không xác định; chưa áp dụng toàn bộ quy tắc style.
- Sửa Dockerfile frontend và Compose để truyền `NEXT_PUBLIC_API_URL` ngay lúc build. URL runtime không thể thay thế giá trị đã được Next.js đưa vào mã trình duyệt.
- Benchmark phát hiện `process_video()` dùng lại biến `duration` trong vòng lọc track, làm thời lượng toàn video thành thời gian track cuối (clip dài trả `0`). Đổi tên biến cục bộ thành `track_duration`, giữ nguyên điều kiện lọc, ngưỡng, model và kết quả nhận diện. Bổ sung assertion vào test video hiện có: clip 25 frame/10 FPS phải trả `2.5`, dù track chỉ kéo dài `2.4` giây. Assertion thất bại trước sửa, toàn bộ test qua sau sửa.
- Đồng bộ liên kết và trạng thái bằng chứng trong README, kiến trúc, hướng dẫn frontend, kiểm thử và benchmark. Bỏ nhận định kích thước PyTorch chưa đo trong comment Dockerfile backend.

## Kiểm thử phần mềm và khởi động

| Kiểm tra | Kết quả thực tế |
|---|---|
| Pytest toàn bộ, sau sửa lỗi video | **93 pass, 0 fail, 0 skip**, 26.10 giây theo pytest |
| Cảnh báo pytest | 1: `Settings.Config` kiểu class bị Pydantic đánh dấu deprecated |
| Ruff backend | Qua với bộ quy tắc nêu trên |
| TypeScript `tsc --noEmit` | Qua |
| ESLint frontend | Qua |
| Playwright trên Edge | **14 pass, 0 fail, 0 skip**, 49.4 giây; không có attachment lỗi runtime |
| Production build Next.js trong Docker | Qua, tạo đủ 8 trang; Next.js 16.4.5 |
| Compose build/up | Backend và frontend khởi động thành công trong project kiểm thử riêng |
| HTTP trên container | Qua OpenAPI, trang login, đăng ký, session, nhận diện ảnh thật, lịch sử, logout và chặn session đã logout |

Playwright dùng API/media được mock để kiểm tra thao tác giao diện. Không dùng kết quả này để suy ra OCR chính xác hay video thật phát được trong trình duyệt. Smoke Docker gọi HTTP thật, model thật; CSDL riêng, không dùng tài khoản hay lịch sử của người dùng. Ảnh `car_30A_11111.jpg` trả `30A-111.11`, không gọi cloud. Đây là một lượt lạnh trong container, không phải benchmark độ trễ đại diện.

Kiểm tra Docker dùng Compose được materialize từ cấu hình repository, đổi project/container sang `alpr-stage5`/`alpr_stage5_*`, cổng backend/frontend sang `18080`/`13080`, mount CSDL đầu ra riêng, model chỉ đọc, bỏ mount `.env` thật và đặt `OCR_ENGINE=yolo`. Frontend được build với URL `http://127.0.0.1:18080`. Container kiểm thử được dừng/gỡ sau chạy; dữ liệu bằng chứng được giữ. Không dừng ứng dụng hay container có sẵn của người dùng.

Workflow CI đã kiểm tra cú pháp/cấu trúc YAML tại máy. **Chưa chạy GitHub Actions**, vì chưa commit/push. CI không tải trọng số hoặc benchmark AI; unit/integration test dùng fixture và mock theo bộ test hiện có. Dependency runtime còn nhiều giới hạn `>=`, nên môi trường mới chưa được khóa hoàn toàn theo phiên bản.

## Benchmark ảnh: chỉ local, 40 ảnh tổng hợp

Chạy toàn bộ `tests/fixtures/test_cases/` và nhãn có sẵn, không thêm ảnh, không sửa nhãn. CPU, 2 thread, warmup 1, operating confidence `0.30`, AP minimum confidence `0.01`, IoU `0.5`. Phiên bản máy/Python/Torch/OpenCV/Ultralytics nằm trong manifest bằng chứng.

| Chỉ số | Kết quả |
|---|---:|
| Ảnh / biển số đối chứng | 40 / 40 |
| Detection TP / FP / FN ở ngưỡng 0.30 | 0 / 0 / 40 |
| Precision / recall / F1 do script trả | 0 / 0 / 0 |
| AP50 trên proposal giữ lại ở ngưỡng thấp | 2.87% |
| Đọc đúng toàn biển / đúng toàn ảnh | 0/40 / 0/40 |
| CER end-to-end, tính cả biển bỏ sót | 100% |
| OCR trên crop ground truth, phép đo riêng | 2/40 đọc đúng (5%) |
| Pipeline local mean / p50 / p95 | 486.16 / 491.73 / 630.84 ms/ảnh |

Không có detection qua ngưỡng vận hành; precision bằng 0 là quy ước của script khi mẫu số bằng 0. AP50 khác 0 vì phép tính AP dùng proposal từ ngưỡng `0.01`. Đây là AP sau bộ lọc hình học/màu và NMS đang có, không phải `YOLO.val()` trên output thô.

Phạm vi pipeline này chỉ gồm detector + YOLO OCR + hậu xử lý. Không gồm fallback vùng ký tự/toàn ảnh của service, OCR dòng, cloud, giải mã ảnh, HTTP, ghi file/DB, load model, warmup hoặc OCR crop GT. Với lượt này không có crop dự đoán nào qua ngưỡng, nên phần lớn độ trễ là detection. Không xem 486 ms là độ trễ HTTP khi OCR thành công, không suy ra FPS phục vụ nhiều người dùng.

Kết quả này cho thấy bộ model/pipeline cơ bản hoạt động kém trên fixture tổng hợp hiện có. Nó không chứng minh ảnh giao thông thật có độ chính xác 0%, cũng không chứng minh thay đổi cơ cấu thư mục làm giảm chất lượng. Chưa xác định nguyên nhân giữa khác biệt dữ liệu, detector, OCR và các bộ lọc; không tự chỉnh ngưỡng để làm đẹp kết quả. Chi tiết từng ảnh: [offline_per_image.csv](stage5/offline_per_image.csv), prediction/bbox/nhãn nằm trong JSON bằng chứng.

## Benchmark service ảnh: local và cấu hình hybrid

Dùng **3 ảnh web có nhãn biển chính đã được lưu từ 05/11/2026** trong `data/test_real_web/sources.json`. Giữ nguyên nhãn, ảnh và hash. Đây là nhóm development đã từng dùng kiểm tra, không phải tập test độc lập; không có bbox hay nhãn đầy đủ cho mọi biển trong ảnh. Không tính precision/recall khoa học từ nhóm này.

Service đầy đủ có fallback local và DB/thư mục đầu ra riêng cho mỗi lượt. CPU 2 thread, không warmup; thời gian từng ảnh bao gồm service, đọc/ghi dữ liệu và lazy loading có thể xảy ra ở ảnh đầu, loại trừ khởi tạo detector/YOLO OCR trước vòng đo.

| Ảnh | Nhãn biển chính có sẵn | Local đúng nhãn | Hybrid đúng nhãn | Local ms | Hybrid ms |
|---|---|---|---|---:|---:|
| `motorbike_69B1_77777.png` | `69-B1 777.77` | Có | Có | 6903.41 | 9121.74 |
| `car_30A_11111.jpg` | `30A-111.11` | Có | Có | 1671.67 | 1887.16 |
| `car_30A_88888.jpg` | `30A-888.88` | Có | Có | 1781.85 | 1552.23 |

Local đọc đúng **3/3** nhãn có sẵn. Hybrid cũng **3/3**, nhưng tổng `cloud_attempts=0`. `NineRouterVisionClient.is_available()` kiểm tra ngoài sandbox trả `False` với gateway đã cấu hình; probe không gửi ảnh. **Độ chính xác và độ trễ khi thực sự có OCR cloud: chưa đo**. Không gọi nhóm hybrid này là kết quả của model cloud, không quy chênh lệch thời gian cho lợi ích/chi phí cloud.

Các ảnh web không nằm trong bản clone mặc định, vì `data/` bị ignore. Manifest tái hiện không chứa khóa API: [web_cases.json](stage5/web_cases.json); nguồn ảnh, nhãn cũ và hash nằm trong bằng chứng. Cần đúng file có hash tương ứng khi tái hiện; không lấy tên file làm ground truth mới.

## Video local

Chạy ONNX/CCT hiện có, mode `fast`, cloud tắt. Số track có chuỗi biển số chỉ là output của model, **không phải số biển đọc đúng**. Không có ground truth frame/ID/transcript để tính MOTA, IDF1, precision/recall hay độ chính xác OCR. Bằng chứng lưu kết quả trước/sau sửa metadata; số đo cuối ở `videos` trong JSON.

| Clip có sẵn | Thời lượng video | Xử lý, chưa gồm load model | Track giữ lại / track có chuỗi biển |
|---|---:|---:|---:|
| `bien_so_ro_59V1_84625.webm` | 3.47 giây | 6.587 giây | 1 / 0 |
| `nhieu_xe_may_37s.mp4` | 36.93 giây | 16.648 giây | 4 / 4 |

Không dùng biển số trong tên clip ngắn làm nhãn. Clip dài có 1108 frame / 30 FPS theo metadata; mode `fast` lấy mẫu khung hình, nên thời gian xử lý trên không tương đương chạy nhận diện đủ 30 FPS. Sau sửa, thời lượng trả về khớp metadata thay vì `3.0` và `0.0`. Track, biển số và annotation trước/sau được đối chiếu riêng, không so sánh thời gian các lượt để kết luận tăng tốc.

Không có đánh giá nhiều luồng đồng thời, tải production hay kết luận khả năng mở rộng từ hai clip này. Lỗi metadata thời lượng được sửa; thuật toán nhận diện và điều kiện lọc track giữ nguyên.

## Lệnh đã chạy và cách tái hiện

Các lệnh thực tế và thời điểm từng tiến trình nằm trong `commands`, `software.steps`, `browser.stats` và log của [evidence.json](stage5/evidence.json). Lệnh chính (PowerShell, từ gốc repo):

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
$env:PYTHONUTF8='1'
.\venv\Scripts\python.exe -B -u scripts/benchmark_all.py --timeout 240
.\venv\Scripts\python.exe -B -m pytest tests -q -p no:cacheprovider --junitxml=.local_archive/stage5/pytest_final.xml
.\venv\Scripts\python.exe -m ruff check main.py src scripts tests --select E9,F63,F7,F82
.\venv\Scripts\python.exe -B -u scripts/benchmark.py --dataset-kind synthetic --no-plots --output-root data/benchmarks/stage5_offline
.\venv\Scripts\python.exe -B -u scripts/check_regression.py --label stage5_web_local --mode local --cases .local_archive/stage5/web_cases.json
.\venv\Scripts\python.exe -B -u scripts/check_regression.py --label stage5_web_hybrid --mode hybrid --cases .local_archive/stage5/web_cases.json
.\venv\Scripts\python.exe -B -u scripts/benchmark_video.py data/benchmarks/video_samples/bien_so_ro_59V1_84625.webm --engine onnx --mode fast --output data/benchmarks/stage5_video.json
.\venv\Scripts\python.exe -B -u scripts/benchmark_video.py data/benchmarks/video_samples/nhieu_xe_may_37s.mp4 --engine onnx --mode fast --output data/benchmarks/stage5_video_multi.json
docker compose -p alpr-stage5 -f .local_archive/stage5/compose.json build
docker compose -p alpr-stage5 -f .local_archive/stage5/compose.json up -d
docker compose -p alpr-stage5 -f .local_archive/stage5/compose.json down
```

`benchmark_all.py` chạy pytest + `npm exec -- tsc --noEmit` + `npm run lint` + Playwright; production build được xác minh riêng bằng Dockerfile chạy `npm run build`. Browser dùng Edge trên máy, không gọi backend thật trong 14 test này. Các benchmark AI chạy tuần tự, sau khi test trình duyệt và container kiểm thử kết thúc; không chạy tải AI song song để tính thời gian.

`.local_archive/` là bằng chứng cục bộ bị ignore. Khi clone mới, cài `requirements-dev.txt`, model và browser theo tài liệu kiểm thử; với 3 ảnh web, dùng manifest đã xuất `docs/results/stage5/web_cases.json` thay đường dẫn archive. Video/ảnh web cần được cung cấp riêng đúng hash. Pytest có thể lưu JUnit vào thư mục đầu ra khác. Compose thông thường chạy `docker compose up --build -d` với model và `.env` đã chuẩn bị; lần đo ở đây dùng cấu hình cô lập như mô tả, không dùng CSDL thật.

## Còn thiếu để đánh giá khoa học

1. Tập ảnh thật đủ lớn, độc lập với quá trình phát triển/huấn luyện, có nguồn/quyền sử dụng, nhãn bbox và transcript đầy đủ, bao gồm ảnh âm tính và nhiều biển; có chia tập, nhóm điều kiện và khoảng tin cậy.
2. Ground truth video theo frame và ID phương tiện/biển để tính IDF1/MOTA, ID switch, phát hiện bỏ sót và độ chính xác đọc biển theo track.
3. Ablation cùng dữ liệu/ngưỡng/phần cứng giữa detector, OCR, các fallback local và cloud đang hoạt động; lưu chi phí, độ trễ, tỷ lệ kích hoạt cloud. OCR trên crop GT trong lần này là chẩn đoán riêng, chưa thay thế ablation.
4. Pipeline `training/`, cấu hình train, script chia dữ liệu, provenance trọng số và log thí nghiệm nếu muốn chứng minh đóng góp huấn luyện/cải tiến của nhóm. Chưa tạo một pipeline giả chỉ để đủ cấu trúc.
5. Đo tải đồng thời, tài nguyên, độ trễ p95/p99 qua HTTP và nhiều video; giới hạn SQLite, lock inference và hàng đợi trong bộ nhớ phải được đánh giá riêng. Không tự thêm Redis/Celery khi chưa có nhu cầu tải được chứng minh.
6. Gateway cloud hoạt động để chạy phép đo thật có fallback. Chưa có kết quả cloud hoặc lợi ích của cloud trên bộ dữ liệu này.

Không thêm nhãn/dataset/ablation giả, không tự huấn luyện model hay thay đổi chính sách fallback. Cảnh báo Pydantic và dependency chưa khóa phiên bản vẫn còn; không gọi chúng là test thất bại.

## Tính toàn vẹn và nguồn cấu hình CI

`integrity` trong bằng chứng đối chiếu HEAD, hash `.env`, database người dùng, `models/checksums.txt`, Git index và đường dẫn riêng tư bị track. File nguồn/model/dữ liệu đầu vào có hash để đối chiếu; các đường dẫn máy được rút về tương đối khi xuất JSON. Không xuất API key, cookie, mật khẩu hay database thật. DOCX/PDF và biểu đồ lịch sử chưa được tái xuất với số đo này.

Đối chiếu cuối: `.env`, CSDL người dùng và checksum inventory không đổi; cả 7 file model khớp SHA256 đã lưu. OpenAPI giữ nguyên so với baseline giai đoạn 4. Git index rỗng, HEAD không đổi, `.env` và `data/` không bị track. Kết quả video trước/sau chỉ khác thời lượng đã sửa và các giá trị thời gian đo.

Tham khảo cấu hình action từ nguồn chính thức: [checkout](https://github.com/actions/checkout), [setup-python](https://github.com/actions/setup-python), [setup-node](https://github.com/actions/setup-node). Các số liệu trong báo cáo lấy từ lệnh thực thi trong workspace, không lấy từ các trang này.
