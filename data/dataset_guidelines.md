# HƯỚNG DẪN QUY CHUẨN DỮ LIỆU BIỂN SỐ XE (DATASET GUIDELINES)
> **Phụ trách:** Người 1 (Kỳ Duyên - Data Engineer & Preprocessing)  
> **Dự án:** Automatic License Plate Recognition (ALPR) Cho Biển Số Xe Việt Nam

---

## 📌 1. Mục tiêu thu thập dữ liệu (Data Collection Goals)

Nhằm đảm bảo mô hình phát hiện biển số (YOLO) hoạt động tin cậy trong môi trường thực tế tại Việt Nam, tập dữ liệu thô cần đáp ứng các tiêu chí phân bố:

1. **Đa dạng loại phương tiện:**
   - **Xe máy (Motorbike):** Biển 2 dòng (vuông), chiếm khoảng 50% tổng số lượng.
   - **Ô tô (Car / SUV / Truck):** Biển 1 dòng (dài) và biển 2 dòng (sau xe), chiếm khoảng 50%.
2. **Đa dạng điều kiện ngoại cảnh:**
   - Ban ngày / ánh sáng tự nhiên đầy đủ: ~60%.
   - Ban đêm / ánh sáng đèn đường, đèn pha, trong hầm: ~25%.
   - Điều kiện thời tiết bất lợi (mưa, chói nắng, bóng râm gắt): ~15%.
3. **Đa dạng góc chụp & khoảng cách:**
   - Chụp thẳng trực diện: góc lệch $< 15^\circ$.
   - Chụp góc nghiêng trái/phải: góc lệch $15^\circ - 45^\circ$.
   - Khoảng cách: Biển số chiếm từ $5\%$ đến $35\%$ diện tích khung hình.

---

## 🏷️ 2. Quy ước đặt tên tệp tin (File Naming Conventions)

Tất cả các ảnh đưa vào `data/raw/` bắt buộc phải tuân theo quy tắc sau:
- **Không có dấu tiếng Việt, không chứa khoảng trắng (space)**.
- Định dạng chuẩn: `<loai_xe>_<so_thu_tu>.<duoi_anh>`
- Ví dụ:
  - Ô tô: `car_001.jpg`, `car_002.jpg`, ...
  - Xe máy: `bike_001.jpg`, `bike_002.jpg`, ...
  - Xe tải / xe khách: `truck_001.jpg`, `bus_001.jpg`, ...

---

## 📐 3. Quy chuẩn gán nhãn Bounding Box trên Roboflow

1. **Tên nhãn (Single Class):**
   - Sử dụng một nhãn duy nhất: `license_plate` (class ID: `0`).
2. **Cách vẽ bounding box:**
   - **Ôm sát mép biển số:** Khung chữ nhật bao trọn 4 góc của biển số xe, sai số lề thừa không vượt quá $2\%$.
   - **Tránh cắt lẹm:** Tuyệt đối không cắt mất chữ số hoặc viền của biển số.
   - **Biển bị che khuất nhẹ (Occlusion $< 30\%$):** Vẫn vẽ bounding box ước lượng bao phủ toàn bộ biển.
   - **Biển bị che khuất nặng ($> 50\%$):** Bỏ qua không gán nhãn để tránh gây nhiễu cho mô hình.

---

## 📊 4. Tỷ lệ phân chia tập dữ liệu (Dataset Split Ratio)

Khi xuất dữ liệu từ Roboflow về định dạng YOLO v8/v11 PyTorch TXT format:
- **Tập huấn luyện (Train set):** $70\%$
- **Tập kiểm định (Validation set):** $20\%$
- **Tập kiểm thử độc lập (Test set):** $10\%$

File cấu hình sinh ra phải đảm bảo cấu trúc:
```yaml
path: ../data
train: images/train
val: images/val
test: images/test

nc: 1
names: ['license_plate']
```

---

## 🔄 5. Chiến lược Tăng cường Dữ liệu (Data Augmentation)

Nhằm nâng cao khả năng chống chịu của mô hình trước các điều kiện thực tế bất lợi, Người 1 áp dụng các kỹ thuật augmentation trong `PlatePreprocessor.augment_plate`:
- **Biến đổi góc xoay (Rotation):** Xoay ngẫu nhiên trong khoảng $[-10^\circ, +10^\circ]$ mô phỏng góc chụp nghiêng của camera.
- **Biến đổi độ sáng & tương phản (Photometric Distortion):** Dao động $\pm 20\%$ cường độ sáng ($beta \in [-25, 25]$) và tương phản ($alpha \in [0.8, 1.2]$).
- **Nhiễu hạt Gaussian:** Tạo nhiễu hạt nhẹ ($\sigma = 8$) mô phỏng cảm biến camera trong môi trường thiếu sáng.

---

## 📁 6. Hiện trạng dữ liệu Phase 1

- Đã thu thập và tiền xử lý 30 ảnh mẫu ban đầu đặt tại `data/raw/sample_detection/` (gồm 15 ảnh xe máy và 15 ảnh ô tô kèm nhãn YOLO TXT).
- Đã chuẩn bị 30 ảnh crop mẫu độc lập tại `data/raw/sample_cropped_plates/` phục vụ thử nghiệm OCR (15 biển 1 dòng và 15 biển 2 dòng).
- Đã chuẩn bị bộ 40 ca kiểm thử thực tế tại `data/test_cases/` (blurred, low_light, obscured, skewed) kèm `ground_truth.json`.
- Sẵn sàng mở rộng lên 1.500+ ảnh trong Phase 2.
