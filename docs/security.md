# Tài khoản, seed và secret

## Đăng nhập hiện tại

Mật khẩu được băm bằng scrypt; phiên đăng nhập dùng token ngẫu nhiên do `secrets.token_urlsafe(32)` tạo ra. Database chỉ lưu SHA256 của token, chủ sở hữu và hạn dùng. Cookie có HttpOnly, SameSite=Lax; Secure được bật theo cấu hình hoặc môi trường production. API kiểm tra quyền sở hữu dữ liệu theo tài khoản.

Ứng dụng không có role Admin/Guest hoặc tài khoản/mật khẩu mặc định. Cách thông thường để tạo tài khoản là `/register`. Người dùng cục bộ đã tồn tại không bị xóa, đổi tên hoặc đổi mật khẩu trong đợt chuẩn hóa này.

Không có `SECRET_KEY` để ký JWT trong kiến trúc hiện tại. Không thêm một khóa mặc định cho cơ chế không sử dụng nó. Token phiên và salt mật khẩu do thư viện `secrets` sinh; API key gateway là secret riêng đọc từ cấu hình, default trong source/example để trống.

## Tạo tài khoản bằng lệnh seed riêng

Chỉ chạy khi người vận hành chủ động gọi:

```powershell
.\venv\Scripts\python.exe scripts/seed_user.py
```

Lệnh bắt buộc nhận đủ ba biến **môi trường tiến trình**:

| Biến | Yêu cầu |
|---|---|
| `ALPR_SEED_NAME` | Tên 2–60 ký tự, theo validation của đăng ký |
| `ALPR_SEED_EMAIL` | Email hợp lệ; được trim và viết thường |
| `ALPR_SEED_PASSWORD` | Mật khẩu 8–128 ký tự, theo validation của đăng ký |

Không có giá trị mặc định; script không lấy ba giá trị seed từ `.env` hoặc nhận mật khẩu qua đối số dòng lệnh. Database đích vẫn lấy `DATABASE_URL` theo Settings, nên cần kiểm tra đúng môi trường trước khi chủ động chạy. Script không được gọi khi import package, khởi động API, build Docker hoặc migrate schema.

Ví dụ nhập tương tác trong PowerShell, không ghi mật khẩu vào tài liệu/lịch sử câu lệnh:

```powershell
$env:ALPR_SEED_NAME = Read-Host "Tên tài khoản"
$env:ALPR_SEED_EMAIL = Read-Host "Email"
$seedSecret = Read-Host "Mật khẩu" -AsSecureString
try {
    $env:ALPR_SEED_PASSWORD = [System.Net.NetworkCredential]::new("", $seedSecret).Password
    .\venv\Scripts\python.exe scripts/seed_user.py
}
finally {
    Remove-Item Env:ALPR_SEED_NAME, Env:ALPR_SEED_EMAIL, Env:ALPR_SEED_PASSWORD -ErrorAction SilentlyContinue
    Remove-Variable seedSecret -ErrorAction SilentlyContinue
}
```

Script dùng cùng schema validation và hàm băm với API đăng ký. Nó tạo một người dùng trong transaction, không tạo phiên/cookie và không cấp quyền quản trị. Nếu email đã tồn tại, script giữ nguyên tên, mật khẩu và dữ liệu của tài khoản; chạy lại không phải là thao tác reset mật khẩu. Không có tùy chọn ghi đè hoặc sửa hàng loạt.

Mã thoát: `0` khi tạo thành công hoặc tài khoản đã có, `2` khi thiếu/sai cấu hình seed, `1` khi cấu hình ứng dụng/database không hợp lệ hoặc thao tác DB thất bại. Output không in mật khẩu, hash hoặc chi tiết exception DB. Thiếu cấu hình seed được phát hiện trước khi tạo schema/tài khoản.

## Tách schema và dữ liệu

- `src/db/migrations.py::initialize_database`: chỉ tạo schema/index còn thiếu và bổ sung trường theo code. Không seed tài khoản hoặc đổi mật khẩu.
- `src/db/seed.py`: xác minh cấu hình seed và thêm người dùng trong transaction do caller quản lý.
- `scripts/seed_user.py`: điểm vào CLI chủ động; có thể khởi tạo schema rồi gọi seed sau khi cấu hình đã hợp lệ.

Alembic chưa được cài/thay thế migration hiện tại. Có thể cân nhắc khi cần revision schema có lịch sử rõ ràng; việc chuyển công cụ cần một thay đổi riêng được đồng ý và kiểm thử với DB cũ.

## Giới hạn rà soát secret

Quét source/tài liệu hiện hành không thay cho kiểm toán toàn bộ lịch sử Git, archive, log hoặc môi trường triển khai. Secret từng xuất hiện trong lịch sử không mất đi khi default hiện tại được để trống. Không in lại giá trị đó vào báo cáo và không tự viết lại lịch sử Git; chủ sở hữu cần thay/thu hồi key còn hiệu lực tại nhà cung cấp.

Kiểm tra giai đoạn 3 dùng DB tạm, không chạy seed trên `data/alpr.db`. Kết quả và phạm vi rà soát nằm tại [security_hardening.md](results/security_hardening.md).
