# Công cụ tài liệu

Thư mục này dành cho công cụ sinh báo cáo hoặc sơ đồ; không được import từ backend và không thuộc luồng nhận diện.

Các script kỹ thuật đang dùng đã tập trung tại [scripts/](../../scripts/): cài model, benchmark ảnh/video, kiểm thử hồi quy và runner notebook. Hướng dẫn đánh giá: [benchmark/README.md](../../benchmark/README.md).

Các script báo cáo dùng một lần trước đây (`build_full_report.py`, `draw_detailed_usecases.py`, `insert_detailed_usecase_diagrams.py`) hiện chỉ có trong kho khôi phục cục bộ `.local_archive/cleanup_20261119/tool/`, không nằm trong bản clone. Hai script thao tác Word còn tham chiếu template/đầu vào đã thiếu; không khôi phục chúng thành công cụ đang hoạt động hoặc dùng số liệu ghi sẵn trong chúng làm kết quả đo.

`test_single_video.py` cũ có đường dẫn video của một máy cá nhân; bản trong archive đã đổi tên thành `run_single_video_legacy.py` và không nằm trong source hoạt động. Bản handoff là snapshot được giữ nguyên ngoài Git. Công cụ thay thế nhận đường dẫn từ người dùng là `scripts/benchmark_video.py`. `pytest.ini` giới hạn discovery vào `tests/` để không thu thập bản sao trong handoff hoặc archive.

Khi bổ sung công cụ tài liệu mới, đặt tại đây, dùng tên chức năng (không đặt `test_*.py`), nhận đầu vào/đầu ra rõ ràng và chỉ đọc số liệu từ bằng chứng thực tế. Không tự sửa báo cáo Word/PDF hiện có khi khởi động ứng dụng hoặc chạy test.
