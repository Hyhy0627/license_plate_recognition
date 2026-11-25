# Dữ liệu runtime và fixture kiểm thử

Các đường dẫn tính từ thư mục gốc repository. Toàn bộ `data/` bị ignore trong Git; không chứa tài liệu hoặc fixture được version hóa. Dữ liệu cục bộ đang có được giữ nguyên khi sắp xếp thư mục, kể cả DB, ảnh đầu ra và các manifest/bằng chứng lịch sử.

## Dữ liệu runtime

| Đường dẫn | Nội dung |
|---|---|
| `data/alpr.db` | Tài khoản, phiên, lịch sử nhận diện ảnh và trạng thái/kết quả job video |
| `data/outputs/` | Ảnh crop, ảnh đánh dấu và file đầu ra; có thể được DB tham chiếu |
| `data/video_jobs/` | Video tải lên và file lock của job đang xử lý |
| `data/benchmarks/` | Kết quả benchmark theo lượt chạy |
| `data/recognition_regression/` | Manifest/hash và bằng chứng hồi quy |
| `data/notebook_runs/` | Bản notebook đã thực thi và thông tin thực thi |
| `data/test_real_web/`, `data/auth_verification/` | Ảnh/bằng chứng thử nghiệm cục bộ từ các lượt trước, không có trong bản clone |
| `data/raw/` | Đầu vào thô cục bộ nếu có; không phải tập huấn luyện đã công bố |

Không xóa DB hoặc ảnh đầu ra như cache khi chưa kiểm tra các URL trong lịch sử. Job video không được khôi phục chỉ bằng cách giữ file upload. Các tên thư mục lịch sử có chữ test không biến nội dung cục bộ thành fixture đi kèm repository.

## Chọn cơ sở dữ liệu và nơi lưu media

`DATABASE_URL` và `STORAGE_BACKEND` được chọn độc lập. Mặc định chạy với SQLite và đĩa cục bộ. Cấu hình mẫu cho backend kết nối PostgreSQL và một bucket riêng đã tạo trước có dạng sau.

```dotenv
DATABASE_URL=postgresql://alpr_user:example_password@localhost:5432/alpr
DB_POOL_SIZE=5
DB_MAX_OVERFLOW=10
STORAGE_BACKEND=s3
S3_BUCKET=alpr-media
S3_REGION=us-east-1
S3_ENDPOINT_URL=
```

- PostgreSQL dùng driver psycopg2 cho URL `postgresql://`, có `pool_pre_ping`. Giới hạn pool áp dụng cho từng tiến trình API và chưa tính kết nối giữ khóa của job video. Migration tự tạo schema/index thiếu và backfill biển số đã chuẩn hóa trong cả hai dialect. [SQLAlchemy Connection Pooling](https://docs.sqlalchemy.org/en/20/core/pooling.html)
- Để dùng MinIO, điền `S3_ENDPOINT_URL` bằng URL mà backend truy cập được. Để dùng AWS S3, để trống endpoint. Cấp quyền đọc, ghi và xóa object, cùng quyền liệt kê bucket nếu cần phân biệt object thiếu với lỗi quyền. `/api/health` kiểm tra ghi/xóa bằng một object tạm dưới prefix `.health/`.
- Cấu hình credential bằng `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY` và `S3_SESSION_TOKEN` nếu có. Khi bỏ trống, SDK dùng chuỗi nguồn credential mặc định, bao gồm IAM role. [Boto3 credentials](https://docs.aws.amazon.com/boto3/latest/guide/credentials.html)
- API giữ URL ảnh `/static/{category}/{filename}` và URL video `/api/video-tracking/jobs/{job_id}/media`. API xác minh chủ sở hữu trước khi đọc object, rồi chuyển tiếp dải byte cho trình duyệt. Adapter hỗ trợ tạo presigned URL có hạn cho mã phía máy chủ. [Boto3 get_object](https://docs.aws.amazon.com/boto3/latest/reference/services/s3/client/get_object.html)

Khi đổi backend lưu media của dữ liệu đang dùng, sao chép ảnh vào các key `cropped_plates/<tên-tệp>`, `final_results/<tên-tệp>` và video vào `video_jobs/<job_id><phần-mở-rộng>` trước khi chuyển cấu hình. Di chuyển dữ liệu từ SQLite sang PostgreSQL là thao tác riêng với migration schema. Compose mặc định vẫn chạy SQLite. Hàng đợi và worker phân tán thuộc giai đoạn tiếp theo. [Kiến trúc triển khai](../README.md#kien-truc-trien-khai)

## Fixture được giữ trong Git

`tests/fixtures/test_cases/` chứa 40 JPG tổng hợp và `ground_truth.json`. Ảnh/nhãn đã được chuyển nguyên byte từ vị trí cũ; không tạo lại ảnh hoặc chỉnh nhãn để khớp model. Benchmark, notebook và script thao tác người dùng mặc định đọc vị trí mới.

Bộ này phục vụ kiểm thử và đánh giá có phạm vi giới hạn; không đại diện độ chính xác trên giao thông thực tế. Fixture mới cần có nguồn dữ liệu và nhãn được kiểm tra thủ công, tách dữ liệu hiệu chỉnh khỏi dữ liệu đánh giá. Cách chạy xem [tests/TESTING.md](../tests/TESTING.md) và [benchmark/ACCURACY.md](../benchmark/ACCURACY.md).

## Bằng chứng cũ và đường dẫn

Các manifest/báo cáo trước giai đoạn 2 có thể ghi đường dẫn cũ hoặc đường dẫn máy cá nhân. Không sửa hash, nhãn hay kết quả lịch sử để tạo cảm giác đã tái lập. Khi dùng lại, cung cấp ánh xạ đường dẫn và đối chiếu SHA256 với file hiện tại. Một số notebook dùng manifest hồi quy cục bộ; bản clone mới cần cung cấp dữ liệu đó hoặc chỉnh ô cấu hình sang lượt có thật.

Chỉ trích xuất bằng chứng đã kiểm tra, không chứa secret/dữ liệu riêng tư, vào `docs/results/` khi cần công bố. Xem [hướng dẫn notebook](../notebooks/README.md) và [kết quả tổ chức lại thư mục](results/repository_cleanup.md).
