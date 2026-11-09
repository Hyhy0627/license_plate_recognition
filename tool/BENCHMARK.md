# Benchmark ALPR đo từ kết quả thực tế

## Chạy

Từ thư mục gốc dự án, dùng môi trường đã có thư viện AI:

```powershell
.\venv\Scripts\python.exe tool/benchmark.py --dataset-kind synthetic
```

Lệnh này đọc bộ ảnh hiện có tại `data/test_cases` và nhãn `ground_truth.json`.
Bộ 40 ảnh hiện tại là ảnh tổng hợp; kết quả chỉ mô tả bộ ảnh đó, không đại diện toàn bộ ảnh giao thông thực tế.

Chạy nhanh để kiểm tra cài đặt:

```powershell
.\venv\Scripts\python.exe tool/benchmark.py --dataset-kind synthetic --limit 2 --no-plots
```

Chạy với bộ ảnh thực đã gán nhãn độc lập:

```powershell
.\venv\Scripts\python.exe tool/benchmark.py --dataset data/test_real --dataset-kind real
```

Không cần Internet hoặc 9Router. Benchmark cố định engine YOLO cục bộ và thiết bị CPU; không dùng `OCR_ENGINE=hybrid` từ `.env` để gửi ảnh lên cloud.
Nếu model không tải được, ảnh thiếu/hỏng hoặc nhãn không hợp lệ, chương trình báo lỗi và không tạo báo cáo thành công giả.

## Kết quả

Mỗi lượt tạo một thư mục mới, ví dụ `data/benchmarks/<UTC-run-id>/`:

| File | Nội dung |
|---|---|
| `metrics.json` | Chỉ số tổng hợp, theo nhóm, tham số, phiên bản thư viện, hash model/mã/ảnh/nhãn |
| `predictions.json` | Mọi bbox dự đoán, chuỗi OCR gốc, chuỗi định dạng, nhãn đối chứng và thời gian từng ảnh |
| `per_image.csv` | Số biển GT, số phát hiện/đầu ra, số khớp chính xác và thời gian từng ảnh |
| `REPORT.md` | Báo cáo đọc nhanh từ số đo của lượt chạy |
| `pr_curve.png` | Điểm precision/recall từ dự đoán đã xếp theo confidence |
| `category_metrics.png` | Detection recall và tỷ lệ khớp biển chính xác theo nhóm |
| `latency_breakdown.png` | Thời gian detection và crop/OCR/định dạng đo bằng `perf_counter` |

Không ghi đè ảnh đầu vào, `ground_truth.json`, notebook, database hoặc biểu đồ cũ trong `docs/figures`.
Những biểu đồ/KPI cũ ghi trong `TIEN_DO.md` cần được coi là chưa kiểm chứng; chúng không được nhập làm kết quả cho benchmark này.
Không tạo biểu đồ ablation nếu chưa thực sự chạy các biến thể xử lý tương ứng.

## Ba phép đánh giá riêng biệt

1. **Detection:** dùng tất cả bbox giữ lại từ detector, không chọn bbox nhờ biết trước GT. Ghép một-một theo confidence và IoU ≥ 0,5; box dư/trùng là FP, biển bỏ sót là FN.
2. **OCR trên crop GT:** đo riêng khả năng đọc ký tự khi vị trí biển đã được cung cấp. Báo cả chuỗi thô và chuỗi sau định dạng. Kết quả này không được đưa vào dự đoán của pipeline.
3. **Local end-to-end:** detector → crop dự đoán → YOLO OCR → định dạng → giữ chuỗi qua kiểm tra cấu trúc. Không dùng bbox/chuỗi GT để cứu biển bỏ sót. Tỷ lệ khớp phải đạt cả IoU và nội dung chuỗi sau chuẩn hóa dấu/khoảng trắng.

Đây là benchmark **pipeline cục bộ cơ bản**, không phải benchmark endpoint web hiện tại. Chưa bao gồm nhánh OCR cụm ký tự toàn ảnh, OCR toàn ảnh, Vision toàn ảnh, cloud, ghi ảnh, DB và HTTP của `routes.py`. Không dùng kết quả này để tuyên bố độ chính xác hoặc độ trễ của chế độ hybrid/web.

## Định nghĩa chỉ số

- `ap50`: AP cho một lớp biển số, IoU 0,5; trung bình precision envelope tại 101 điểm recall từ 0 đến 1. Chưa có AP50–95. Nếu không có GT dương, giá trị là `null`/N/A.
- Detector chạy mặc định với confidence thu thập AP `0.01`, vẫn giữ các bộ lọc hình học/màu và NMS của ứng dụng. AP này đánh giá các proposal được giữ lại, không phải kết quả `YOLO.val()` trên đầu ra YOLO thô.
- Precision, recall và F1 vận hành mặc định dùng confidence `0.30`. Thay đổi bằng `--confidence`; `--ap-min-confidence` phải nhỏ hơn hoặc bằng ngưỡng vận hành. Không trộn P/R tại một ngưỡng với AP trên toàn đường cong.
- `mean_iou_matched`: trung bình IoU của các cặp TP; N/A nếu không có TP.
- `mean_iou_including_misses`: tổng IoU TP chia tổng biển GT, tức biển bỏ sót đóng góp 0.
- `exact_plate_recall`: số biển đúng cả vị trí và nội dung / tổng biển GT.
- `exact_plate_precision`: số biển đúng cả vị trí và nội dung / tổng biển đầu ra.
- `exact_image_accuracy`: tỷ lệ ảnh đọc đúng tất cả biển và không thêm biển dư. Ảnh âm tính chỉ đúng khi không tạo đầu ra.
- CER: tổng khoảng cách Levenshtein / tổng ký tự GT. Biển bỏ sót là xóa toàn chuỗi; chữ trên biển dự đoán dư được tính là lỗi chèn. CER có thể lớn hơn 100%, không ép về một giá trị đẹp hơn.
- Chuẩn hóa so khớp chỉ bỏ dấu phân cách/khoảng trắng và viết hoa, không tự sửa ký tự GT hoặc dự đoán khi tính so khớp.

## Độ trễ và tính tái lập

- Dùng `perf_counter`; báo mean, p50, p95 cho detection, crop/OCR/định dạng, tổng pipeline và phép OCR crop GT riêng biệt.
- Thời gian local pipeline bắt đầu sau giải mã ảnh và kết thúc sau chọn đầu ra hợp lệ. Không bao gồm load model, warmup, đọc file, OCR GT, vẽ biểu đồ, HTTP, DB hoặc ghi ảnh.
- Mặc định warmup một lần; `--warmup 0` có thể làm ảnh đầu chịu chi phí khởi tạo. Load/warmup được ghi riêng trong manifest.
- Mặc định CPU và hai luồng Torch, tùy chỉnh `--threads`. Thời gian thay đổi theo phần cứng, tải máy và phiên bản; hash giúp xác định đầu vào của mỗi lượt.
- Không suy ra FPS phục vụ web hoặc khả năng xử lý đồng thời từ nghịch đảo thời gian trung bình.
- Nếu dùng `--limit`, báo cáo ghi rõ số ảnh đã chọn và tổng ảnh dataset. Không coi chạy nhanh là nghiệm thu cả dataset.

## Nhãn một biển, nhiều biển và ảnh âm tính

Định dạng cũ vẫn được hỗ trợ:

```json
{
  "car.jpg": {
    "bbox": [10, 20, 100, 60],
    "clean_text": "29A12345",
    "category": "daylight"
  }
}
```

Định dạng nhiều biển và ảnh không có biển:

```json
{
  "metadata": {"kind": "real", "description": "Independent held-out test set"},
  "images": {
    "cars.jpg": {
      "category": "multiple",
      "plates": [
        {"bbox": [10, 20, 100, 60], "text": "29A12345"},
        {"bbox": [120, 20, 210, 60], "text": "30B67890"}
      ]
    },
    "empty.jpg": {"category": "negative", "plates": []}
  }
}
```

Bbox dùng tọa độ pixel `[x1, y1, x2, y2]`, phải nằm trong ảnh. File ảnh dùng đường dẫn tương đối trong dataset. Nhãn cần được đối chiếu thủ công; không dùng chính model đang đánh giá để tạo GT mà không kiểm tra.

## Kiểm thử logic benchmark

```powershell
.\venv\Scripts\python.exe -m unittest discover -s tests -p test_benchmark.py -v
```

Các ca gồm: TP/FP/FN, box trùng, AP bị giảm khi FP có confidence cao, biển bỏ sót, ảnh âm tính, ngưỡng AP và ngưỡng vận hành, CER, percentile, nhãn nhiều biển và kiểm tra OCR crop GT không cứu kết quả E2E.
