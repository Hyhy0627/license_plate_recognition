# Bảo mật cơ bản — giai đoạn 3

Ngày thực hiện: **19/11/2026**, Asia/Bangkok. Phạm vi dựa trên working tree hiện tại. Không chạy seed trên DB người dùng, không xóa tài khoản cũ, không đổi public API, thuật toán AI hoặc file `.env` thật.

## 1. Kết quả rà soát

- Code hiện hành không tự tạo tài khoản mặc định khi startup/migrate. Các tài liệu hướng dẫn đã bỏ bảng tài khoản/mật khẩu mẫu ở giai đoạn trước; không bổ sung lại tài khoản mẫu cho bản clone.
- `initialize_database()` vốn chỉ thao tác schema/index, không có seed để tách ra. Giai đoạn này làm rõ hợp đồng đó bằng docstring và test không tạo tài khoản, đồng thời bổ sung module/lệnh seed độc lập.
- Xác thực vẫn là scrypt và cookie phiên có trạng thái. Token dùng `secrets.token_urlsafe(32)`, DB lưu SHA256 của token. Không có khóa ký JWT `SECRET_KEY` trong implementation; không thêm một default khóa yếu cho tính năng không dùng.
- Default API key NineRouter trong source/example hiện rỗng. Đây là loại secret riêng với token phiên đăng nhập.
- Rà bốn snapshot Git có thay đổi `src/config.py` thấy mẫu key từng ghi cứng trong hai snapshot cũ (`427e88d`, `2aefb96`). Không in giá trị hoặc kiểm tra hiệu lực bằng request tới nhà cung cấp. Không viết lại lịch sử Git trong giai đoạn này.

## 2. Đã thay đổi

| File | Thay đổi |
|---|---|
| `src/db/migrations.py` | Ghi rõ schema-only, không seed/đổi mật khẩu; giữ nguyên logic migration |
| `src/db/seed.py` | Đọc cấu hình seed từ mapping môi trường, dùng chung Registration/hash_password với API; thêm tài khoản trong transaction của caller, bỏ qua email đã có |
| `scripts/seed_user.py` | CLI chủ động; không có account/password mặc định; chỉ nhận credential qua biến môi trường; không in validation input, tham số DB hoặc đối số CLI có thể chứa mật khẩu |
| `tests/test_seeding.py` | Tám ca bao gồm schema không seed, validation, chuẩn hóa/hash, chạy lại không ghi đè, CLI thiếu env, CLI tạo trên DB tạm, lỗi DB và hai dạng đối số không hợp lệ |
| `docs/security.md` | Hướng dẫn đăng nhập/seed, nhập mật khẩu tương tác, dọn biến môi trường, giới hạn kiểm toán secret và đề xuất Alembic |
| README, PROJECT_STRUCTURE, scripts/README, docs/README | Liên kết lệnh seed và mô tả đúng trách nhiệm |
| Tài liệu này | Ghi kết quả, phạm vi và tồn đọng của giai đoạn 3 |

Lệnh seed đọc đủ `ALPR_SEED_NAME`, `ALPR_SEED_EMAIL`, `ALPR_SEED_PASSWORD` từ môi trường tiến trình; không tự lấy ba giá trị đó từ `.env`. Nó dùng cùng policy của API đăng ký, không tạo session/cookie, không thêm role quản trị, không có tùy chọn ghi đè mật khẩu. Khi email đã tồn tại, dữ liệu tài khoản được giữ nguyên. Startup, Docker, migration và import package không gọi seed.

## 3. Kiểm tra thực tế

| Kiểm tra/lệnh | Kết quả |
|---|---|
| `venv/Scripts/python.exe -B -u -m pytest -q -p no:cacheprovider` | **93 passed, 1 warning, 23.23s**; exit 0 |
| Tám test seed, kể cả CLI subprocess | Dùng SQLite trong bộ nhớ hoặc DB tại thư mục test tạm; không seed DB thật |
| `scripts/seed_user.py --help` | Thành công; không có đối số nhận mật khẩu |
| So SHA256 trước/sau | DB thật, `.env`, implementation auth và source OCR/tracker không đổi |
| Quét 92 file text source/tài liệu trước kiểm tra cuối | Không thấy các mẫu tài khoản/mật khẩu demo cũ hoặc mẫu key literal đã kiểm tra; không in matched values |
| Text phần thân DOCX | Không thấy các mẫu credential đã kiểm tra; không chỉnh file báo cáo |
| Text PDF trích bằng Poppler | Quét mẫu credential ASCII trên nội dung trích từ 48 trang; không thấy mẫu đã kiểm tra, không sửa PDF |
| Rà lịch sử có giới hạn của `src/config.py` | Có key literal trong hai snapshot cũ; không sửa lịch sử/không thử key |
| Link tài liệu, cú pháp và ignore | Đạt: 10 file giai đoạn 3, 53 liên kết local hợp lệ; cú pháp Python đúng, runtime và .env không được track |

Pytest chạy ngoài sandbox với `PYTHONUTF8=1`, `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` và timeout 60 giây. Thời gian trên là thời gian runner pytest báo, không phải độ trễ nhận diện. Warning còn lại là `PydanticDeprecatedSince20` tại `Settings.Config`.

Poppler trong sandbox gặp lỗi DLL nên việc trích PDF được chạy ngoài sandbox. Output có phần font ngoài ASCII không giải mã UTF-8 hoàn chỉnh; mẫu credential ASCII được đối chiếu trực tiếp trên byte trích xuất sau khi loại whitespace. Đây không phải kiểm toán toàn bộ nội dung ảnh, annotation, metadata hoặc nội dung ẩn trong tài liệu. Quét pattern có giới hạn không chứng minh không còn mọi loại secret.

## 4. Chưa thực hiện / cần quyết định

- Nếu key cũ còn hiệu lực, chủ sở hữu cần thay/thu hồi tại nhà cung cấp. Xóa giá trị khỏi default hiện tại không thu hồi key đã xuất hiện trong lịch sử. Chưa quét toàn bộ lịch sử mọi file, archive, log hoặc máy triển khai; chưa kiểm thử xâm nhập.
- Không tự xóa/reset tài khoản trong DB thật. Nếu có tài khoản dùng mật khẩu công khai từ trước, cần đổi thông tin sau khi xác định đúng tài khoản; không suy ra mật khẩu từ email hoặc xóa dữ liệu hàng loạt.
- Alembic chưa được cài. Có thể chuyển sang revision schema có version khi cần thay đổi schema tiếp, nhưng chỉ triển khai khi người dùng đồng ý và có kiểm thử DB cũ. Hiện module migration đã tách khỏi seed.
- Chưa chạy Docker production, Playwright hoặc benchmark AI mới trong giai đoạn này. Tốc độ/độ chính xác AI mới: **chưa đo**; các thay đổi không nhằm sửa thuật toán.
- Các thay đổi tính năng có từ trước ngoài những file trên được giữ riêng, không gom vào commit bảo mật này.
