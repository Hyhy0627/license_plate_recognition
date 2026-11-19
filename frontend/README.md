# PlateSight frontend

Giao diện Next.js 16.4.5 và React 19.3.0 theo `package.json`. [README gốc](../README.md) hướng dẫn cài backend/model và chạy hai dịch vụ; [kiến trúc dự án](../PROJECT_STRUCTURE.md) mô tả API, phiên đăng nhập và dữ liệu.

## Chạy frontend

Từ thư mục gốc, sau khi cài môi trường backend theo README:

```powershell
npm --prefix frontend ci
npm --prefix frontend run dev -- --port 3000
```

Backend cần được khởi động ở terminal khác bằng `.\venv\Scripts\python.exe main.py`. Mở [localhost:3000](http://localhost:3000), đăng ký tài khoản mới khi chưa có tài khoản cục bộ.

## Địa chỉ API và cookie

`src/lib/api.ts` mặc định gọi `http://localhost:8000`. Nếu backend ở địa chỉ khác, tạo `frontend/.env.local`:

```dotenv
NEXT_PUBLIC_API_URL=http://localhost:8000
```

Đồng thời thêm origin frontend vào `CORS_ORIGINS` trong `.env` backend. Frontend gọi API trực tiếp; `next.config.ts` hiện không khai báo API proxy. Với bản production, cần đặt biến `NEXT_PUBLIC_API_URL` khi build và build lại nếu đổi địa chỉ; biến môi trường chỉ đặt lúc chạy container không tự cập nhật mã trình duyệt đã build.

Auth provider đọc `/api/auth/me`; fetch gửi cookie với `credentials: "include"`. Backend lưu phiên và kiểm tra chủ sở hữu lịch sử/ảnh/video. Frontend không quản lý JWT hoặc vai trò Admin/Guest.

Trang `/video` gửi video tải lên, polling trạng thái job và vẽ annotation theo metadata trên file media. Đây không phải luồng camera trực tiếp. `/history` hiển thị lịch sử nhận diện ảnh của tài khoản; chưa có chức năng xuất/xóa lịch sử.

## Kiểm tra

```powershell
npm --prefix frontend run lint
npm --prefix frontend run build
```

Kết quả kiểm tra có thời điểm/phạm vi cụ thể nằm tại [báo cáo đồng bộ tài liệu](../docs/results/documentation_sync.md). Lint/build không thay cho kiểm thử thao tác trình duyệt hoặc độ chính xác AI; xem [hướng dẫn kiểm thử](../tests/TESTING.md).
