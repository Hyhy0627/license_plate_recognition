# Tái cấu trúc core/services — giai đoạn 4

Ngày thực hiện: **19/11/2026**, Asia/Bangkok. Áp dụng trên working tree đang có các thay đổi tính năng từ trước. **Không tạo commit theo yêu cầu mới nhất của người dùng**, dù mẫu form ban đầu có yêu cầu commit theo giai đoạn.

## 1. Thay đổi

- `src/core/image/`: detector, tiền xử lý, vùng ứng viên hình học và đề xuất vùng biển từ box ký tự.
- `src/core/ocr/`: engine OCR ảnh, OCR dòng và hậu xử lý văn bản.
- `src/core/video/`: adapter model video, tracker, lớp PlateReader và YAML cấu hình.
- `src/core/integrations/`: client NineRouter.
- `src/services/`: điều phối ảnh/lịch sử, job video, xác thực, ảnh kết quả riêng tư, DTO và factory model dùng chung.

Các route ảnh/video/tài khoản chỉ giữ chữ ký HTTP, validation/dependency và gọi service. Endpoint ảnh riêng tư ở `main.py` cũng gọi service để kiểm tra chủ sở hữu/trả file. Middleware HTTP và khởi tạo ứng dụng vẫn nằm tại composition root `main.py`.

| Module mới | Trách nhiệm |
|---|---|
| `services/model_runtime.py` | Singleton detector/OCR ảnh, cache bộ video và một khóa suy luận chung |
| `services/image_recognition.py` | Luồng nhận diện ảnh và lưu kết quả |
| `services/history.py` | Truy vấn lịch sử/tìm kiếm/chi tiết theo chủ sở hữu |
| `services/video_jobs.py` | Upload, một executor, kho job, tiến trình và quyền đọc media |
| `services/authentication.py` | Policy đăng ký, scrypt, token/session, throttle và nghiệp vụ tài khoản |
| `services/result_media.py` | Quyền đọc và trả ảnh kết quả riêng tư |
| `services/schemas.py` | DTO ảnh/lịch sử được chuyển nguyên định nghĩa từ API |

`get_video_engines()` được đưa từ core lên model runtime, tránh core import ngược API/service. Cả ảnh và video tiếp tục dùng cùng đối tượng khóa; các factory trả lại đúng instance đã cache. Seed dùng policy trong service xác thực, không còn import helper từ API. Service vẫn dùng các kiểu lỗi/response FastAPI hiện có ở những chỗ cần giữ hành vi; không đổi sang một cơ chế xử lý lỗi mới trong đợt này.

Đã cập nhật import trong main, core, service, script, test và notebook; cập nhật vị trí YAML trong script cài model, đường dẫn source hash trong benchmark/notebook và tài liệu kiến trúc/video/cloud/model/security. Các file tracked được chuyển bằng `git mv`; source chưa tracked được di chuyển cục bộ. Index đã được trả về trạng thái chưa stage, giữ nguyên working tree để người dùng tự review/commit sau.

## 2. Hành vi được giữ

- Toàn bộ OpenAPI trước/sau bằng nhau: endpoint, operation ID, tham số/default, status và request/response schema. Có 12 đường dẫn trong schema hiện tại; ảnh static riêng tư vẫn là route ngoài OpenAPI.
- AST của 10 file core/schema chuyển nguyên module tương đương sau khi chuẩn hóa tên import và bỏ docstring. Hai class model video, pipeline nhận diện ảnh, helper vùng ký tự và thân 23 hàm nghiệp vụ cũng được đối chiếu với snapshot đầu giai đoạn.
- Factory video chỉ bỏ import ngược API; logic chọn engine, tham số model và cache không đổi. Hằng số upload/queue/worker và hai class validation tài khoản được đối chiếu riêng.
- Không đổi ngưỡng model, số luồng suy luận, profile lấy mẫu video, quy tắc OCR, quyền dữ liệu, format cookie hoặc thuật toán băm.
- DB thật, `.env`, manifest checksum và trọng số được giữ nguyên. YAML chỉ đổi vị trí source; nội dung không đổi. Tất cả 7 trọng số khớp checksum.

OpenAPI baseline và source snapshot nằm cục bộ trong `.local_archive/stage4/`; [refactor_checks.json](refactor_checks.json) giữ kết quả kiểm tra và bằng chứng benchmark đã lọc khỏi thông tin máy không cần thiết. Không dùng commit HEAD làm baseline thuật toán vì working tree trước thay đổi đã có code chưa commit.

## 3. Kiểm tra thực tế

| Kiểm tra | Kết quả |
|---|---|
| `venv/Scripts/python.exe -B -u -m pytest -q -p no:cacheprovider` | **93 passed, 1 warning, 26.40s**, exit 0 |
| Đối chiếu toàn bộ `main.app.openapi()` với snapshot trước sửa | Bằng nhau |
| AST core/schema, class model, hàm dịch vụ, factory và giới hạn job | Giữ nguyên phần tính toán đã kiểm tra |
| Import dependency | Core và services không import `src.api` |
| Nạp model ảnh, video và phương tiện bằng đường dẫn thật | Thành công; cache và khóa dùng chung được xác nhận |
| CLI benchmark, video, hồi quy, seed, setup OCR | `--help` chạy thành công |
| `scripts/run_notebooks.py` | Cả ba notebook hợp lệ về định dạng; chưa thực thi cell |
| TypeScript `--noEmit --incremental false` | Exit 0 |
| `docker compose config --format json` | Hợp lệ; đường dẫn/volume model không đổi |
| Dockerfile | `COPY src/ src/` bao gồm các package/services và YAML mới; không cần sửa lệnh COPY hoặc volume Compose |
| Cú pháp, liên kết tài liệu và trạng thái Git cuối | Đạt: 18 tài liệu và 103 liên kết local; Python hợp lệ, HEAD không đổi, index không có thay đổi staged |

Pytest chạy ngoài sandbox với `PYTHONUTF8=1`, `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`, timeout 60 giây; không sửa cấu hình pytest để bỏ test. Warning còn lại là `PydanticDeprecatedSince20` ở `Settings.Config`. Chỉ cập nhật vị trí mock/import trong các test liên quan; không bỏ assertion hoặc loại test khỏi bộ đang hoạt động.

## 4. Smoke benchmark local trước–sau

Lệnh chạy trước khi sửa và sau khi sửa:

```powershell
.\venv\Scripts\python.exe -B scripts/benchmark.py --dataset-kind synthetic --limit 2 --no-plots --output-root data/benchmarks/stage4_before
.\venv\Scripts\python.exe -B scripts/benchmark.py --dataset-kind synthetic --limit 2 --no-plots --output-root data/benchmarks/stage4_after
.\venv\Scripts\python.exe -B scripts/benchmark.py --dataset-kind synthetic --limit 2 --no-plots --output-root data/benchmarks/stage4_after_isolated
```

Hai ảnh là `blurred/blur_01.jpg`, `blurred/blur_02.jpg` trong fixture tổng hợp. Hash ảnh/nhãn và hai trọng số, thiết bị CPU, 2 luồng Torch, warmup, ngưỡng confidence/AP/IoU và phiên bản thư viện đều được đối chiếu. Không bật cloud. Phép đo này không bao gồm fallback đầy đủ của service ảnh, HTTP/DB hoặc video.

| Lượt | Mean pipeline | Ghi chú |
|---|---:|---|
| Trước refactor | 505,65 ms | Baseline lưu trước khi chuyển module |
| Sau refactor, lượt đầu | 656,78 ms | Chạy trùng thời gian với pytest; không phải so sánh tốc độ công bằng |
| Sau refactor, lượt chạy lại | 529,57 ms | Không có pytest chạy đồng thời |

**Các bản ghi dự đoán, kể cả OCR trên crop GT, và metric chất lượng giống nhau sau khi bỏ thời gian đo.** Tuy nhiên, detector đều bỏ sót cả hai ảnh ở tất cả các lượt: TP=0, FP=0, FN=2; exact recall bằng 0 trên nhóm nhỏ này. Điều đó không chứng minh chất lượng nhận diện tốt hoặc tương đương trên dữ liệu thật. Không che kết quả kém bằng số test phần mềm đạt.

Hai ảnh và một lượt đo độc lập cho mỗi trạng thái chưa đủ kết luận tăng/giảm tốc độ; không tính hệ số tăng tốc hoặc khẳng định hiệu năng hoàn toàn không đổi. Lượt chạy lại được thực hiện vì lượt sau đầu tiên có tải pytest đồng thời, không thay cấu hình/nhãn để làm đẹp kết quả. Chi tiết numeric, hash và output mẫu nằm trong [JSON đối chiếu](refactor_checks.json).

## 5. Giới hạn và việc tiếp theo

- Không tạo commit; không sửa/thay thế các thay đổi ngoài phạm vi đã có trước. Các file còn ở working tree để review.
- Cần khởi động lại backend hoặc rebuild image backend đang chạy để nạp module mới. Python import nội bộ đã đổi; script ngoài repository dùng đường dẫn core cũ cần cập nhật. HTTP API không đổi.
- Chưa chạy `docker compose up`, build frontend production, Playwright hoặc benchmark toàn bộ dữ liệu/đánh giá tracking mới trong giai đoạn này.
- Cần giai đoạn 5 để đánh giá có nhãn đầy đủ, tách local/cloud, kiểm tra triển khai và CI. Bộ 2 ảnh hiện tại chỉ là smoke để đối chiếu refactor; không thay thế đánh giá đó.
- Báo cáo Word/PDF và snapshot các giai đoạn trước không được viết lại như thể đã dùng cấu trúc mới.
