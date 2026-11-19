# Dữ liệu runtime và fixture kiểm thử

Các đường dẫn tính từ thư mục gốc repository. Toàn bộ `data/` bị ignore trong Git; không chứa tài liệu hoặc fixture được version hóa. Dữ liệu cục bộ đang có được giữ nguyên khi sắp xếp thư mục, kể cả DB, ảnh đầu ra và các manifest/bằng chứng lịch sử.

## Dữ liệu runtime

| Đường dẫn | Nội dung |
|---|---|
| `data/alpr.db` | Tài khoản, phiên và lịch sử nhận diện ảnh |
| `data/outputs/` | Ảnh crop, ảnh đánh dấu và file đầu ra; có thể được DB tham chiếu |
| `data/video_jobs/` | Video tải lên; thông tin trạng thái job nằm trong bộ nhớ backend |
| `data/benchmarks/` | Kết quả benchmark theo lượt chạy |
| `data/recognition_regression/` | Manifest/hash và bằng chứng hồi quy |
| `data/notebook_runs/` | Bản notebook đã thực thi và thông tin thực thi |
| `data/test_real_web/`, `data/auth_verification/` | Ảnh/bằng chứng thử nghiệm cục bộ từ các lượt trước, không có trong bản clone |
| `data/raw/` | Đầu vào thô cục bộ nếu có; không phải tập huấn luyện đã công bố |

Không xóa DB hoặc ảnh đầu ra như cache khi chưa kiểm tra các URL trong lịch sử. Job video không được khôi phục chỉ bằng cách giữ file upload. Các tên thư mục lịch sử có chữ test không biến nội dung cục bộ thành fixture đi kèm repository.

## Fixture được giữ trong Git

`tests/fixtures/test_cases/` chứa 40 JPG tổng hợp và `ground_truth.json`. Ảnh/nhãn đã được chuyển nguyên byte từ vị trí cũ; không tạo lại ảnh hoặc chỉnh nhãn để khớp model. Benchmark, notebook và script thao tác người dùng mặc định đọc vị trí mới.

Bộ này phục vụ kiểm thử và đánh giá có phạm vi giới hạn; không đại diện độ chính xác trên giao thông thực tế. Fixture mới cần có nguồn dữ liệu và nhãn được kiểm tra thủ công, tách dữ liệu hiệu chỉnh khỏi dữ liệu đánh giá. Cách chạy xem [tests/TESTING.md](../tests/TESTING.md) và [benchmark/ACCURACY.md](../benchmark/ACCURACY.md).

## Bằng chứng cũ và đường dẫn

Các manifest/báo cáo trước giai đoạn 2 có thể ghi đường dẫn cũ hoặc đường dẫn máy cá nhân. Không sửa hash, nhãn hay kết quả lịch sử để tạo cảm giác đã tái lập. Khi dùng lại, cung cấp ánh xạ đường dẫn và đối chiếu SHA256 với file hiện tại. Một số notebook dùng manifest hồi quy cục bộ; bản clone mới cần cung cấp dữ liệu đó hoặc chỉnh ô cấu hình sang lượt có thật.

Chỉ trích xuất bằng chứng đã kiểm tra, không chứa secret/dữ liệu riêng tư, vào `docs/results/` khi cần công bố. Xem [hướng dẫn notebook](../notebooks/README.md), [kiến trúc](../PROJECT_STRUCTURE.md) và [kết quả giai đoạn 2](results/repository_cleanup.md).
