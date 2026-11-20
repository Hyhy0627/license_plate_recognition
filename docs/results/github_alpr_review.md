# Đối chiếu GitHub và model ALPR — 20/11/2026

## Tích hợp FastPlateOCR cho ảnh sau lần đối chiếu ban đầu

Chế độ cục bộ `OCR_ENGINE=fastplate` dùng CCT-VN cho crop biển. Bộ đọc chấp nhận chuỗi hợp lệ có đủ năm số cuối khi ký tự yếu nhất đạt 0,85 và việc định dạng giữ nguyên ký tự. YOLO ký tự xử lý các trường hợp còn lại, gồm biển vuông tám ký tự cần phân biệt cách chia dòng 3+5 với 4+4. Cấu hình tại máy chọn chế độ này với detector ảnh `best.pt`.

So sánh qua service tải ảnh với model thật trên CPU hai luồng, mỗi cấu hình chạy tuần tự một lượt, cùng 24 ảnh có nhãn (18 ảnh thật, 4 ảnh tổng hợp khó, 2 ảnh âm tính). Thời gian gồm giải mã ảnh, nhận diện, ghi ảnh và lịch sử vào database kiểm thử. Tiêu chí đúng theo ảnh đòi hỏi đủ mọi biển và đúng nhóm ký tự so với nhãn.

| Cấu hình dùng cùng detector ảnh | Ảnh khớp nhãn | Trung vị | P95 |
|---|---:|---:|---:|
| YOLO ký tự | 21/24 | 1,57 s | 3,81 s |
| FastPlateOCR có YOLO đọc lại | 21/24 | 1,39 s | 3,53 s |

Trong 18 ảnh thật, cả hai đúng 17 ảnh. FastPlateOCR cung cấp trực tiếp 20 trong 30 kết quả biển mà service trả về. Hai mẫu tổng hợp mờ, nhiễu và một ảnh chứa hai biển điện dòng MD vẫn bị bỏ sót. Trên ảnh MD, detector tìm thấy cả hai vùng biển, mỗi biển có 10 ký tự còn CCT-VN hỗ trợ tối đa 9. Kết quả chỉ phản ánh tập phát triển hiện có, trong đó ba ảnh là các khung hình của cùng một clip.

Dự đoán và thời gian từng ảnh nằm trong [lượt YOLO](../../data/recognition_regression/20261119T173330_479114Z_fastplate_compare_yolo/results.json) và [lượt FastPlateOCR](../../data/recognition_regression/20261119T173455_542498Z_fastplate_compare_cascade/results.json). Phần bên dưới ghi lại lần khảo sát trước khi triển khai chế độ kết hợp.

## Khảo sát ban đầu

Đã đọc mã hiện tại, kiểm tra nguồn GitHub và chạy ba cấu hình model cục bộ. Không thay đổi model mặc định, `.env`, database hoặc luồng xử lý ứng dụng.

## Repository nên xem

| Repository | Vai trò | Đánh giá cho dự án này |
|---|---|---|
| [ankandrew/fast-plate-ocr](https://github.com/ankandrew/fast-plate-ocr) | OCR chuyên biển số, ONNX Runtime, train/fine-tune, model CCT S/XS | Ưu tiên làm nền OCR để tối ưu; thư viện đã được dự án sử dụng. Cần đánh giá model global S/XS và model VN trên dữ liệu thật trước khi chọn. |
| [ankandrew/fast-alpr](https://github.com/ankandrew/fast-alpr) | Pipeline detection + OCR; thay được model và execution provider | Phù hợp làm baseline ONNX độc lập để đối chiếu. Chưa tải/chạy các model mặc định của repository này trong lượt kiểm tra. |
| [ddkhoa2605/LicensePlateDetection](https://github.com/ddkhoa2605/LicensePlateDetection) | YOLO11n + CCT fine-tune Việt Nam + ByteTrack + voting | Model và một phần lõi đã tích hợp trong dự án; cài lại không tự tạo thêm cải tiến. README mô tả dữ liệu detector chủ yếu ban ngày, biển một dòng; cần kiểm chứng riêng xe máy, ban đêm. |
| [sangtrx/license-plate-recognition](https://github.com/sangtrx/license-plate-recognition) | YOLOv8 + PaddleOCR/PP-OCRv5, ONNX/TensorRT | Hữu ích làm hướng đối chiếu cho biển nghiêng; README yêu cầu Ubuntu và Python 3.9–3.12, trong khi môi trường hiện tại khác. Chưa cài/chạy repository này. |

Nguồn upstream: [FastPlateOCR README](https://github.com/ankandrew/fast-plate-ocr/blob/master/README.md), [FastALPR README](https://github.com/ankandrew/fast-alpr/blob/master/README.md), [README model VN](https://github.com/ddkhoa2605/LicensePlateDetection/blob/main/README.md), [TrafficCam README](https://github.com/sangtrx/license-plate-recognition/blob/main/README.md).

Thông số tốc độ upstream FastPlateOCR được đo trên RTX 3090 với TensorRT/CUDA; không dùng chúng làm số đo CPU của máy này. Không có bằng chứng trong lượt kiểm tra để cam kết độ chính xác 95–99% cho camera của người dùng. Nguồn model VN và tình trạng giấy phép tại phiên bản tích hợp đã được ghi trong `docs/video_onnx.md`.

## Phép đo mới tại máy

Bằng chứng chi tiết: `data/benchmarks/github_review_20261120/results.json`. File chứa timestamp UTC, phiên bản runtime, hash trọng số/nhãn, summary và dự đoán từng ảnh của cả ba cấu hình.

- Toàn bộ 40 ảnh tổng hợp và 40 nhãn đã có trong `tests/fixtures/test_cases`; không tạo hoặc chỉnh nhãn.
- CPU, Torch 2 thread, warmup một lần cho mỗi cấu hình, confidence vận hành 0.30, ghép bbox IoU ≥ 0.5.
- Torch `2.14.1+cpu`, CUDA không khả dụng trong môi trường Python hiện tại. ONNX Runtime `1.32.0`, provider khả dụng Azure/CPU. Điều này không chứng minh máy không có GPU vật lý.
- Dùng `load_annotations`, `collect_records`, `summarize` từ `scripts/benchmark.py` với `LicensePlateDetector`/`VideoPlateDetector`, `PlateOCREngine(engine_type='yolo')`/`VideoPlateOCR`.
- OCR crop GT là phép chẩn đoán độc lập: crop dùng hàm `crop_plate` hiện có với padding, đo OCR + định dạng. Không đưa GT crop vào kết quả end-to-end.
- Các cấu hình là pipeline thực tế khác nhau: detector ảnh có retry và kích thước thích ứng; detector video YOLO11n chạy một lần ở 640. Tỷ lệ tốc độ không phải ablation chỉ riêng kiến trúc/model.
- Không đo HTTP, upload, ghi file/DB, cloud, fallback service, xử lý video/tracking hoặc tải đồng thời. Thời gian load/warmup và OCR GT loại khỏi pipeline.

| Cấu hình | Detection mean | OCR crop GT mean | OCR crop GT đúng toàn biển sau định dạng | End-to-end đúng toàn biển |
|---|---:|---:|---:|---:|
| `best.pt` + `LP_ocr.pt` hiện tại | 425.91 ms | 458.01 ms | 2/40 | 0/40 |
| `best.pt` + CCT VN ONNX | 435.82 ms | 37.69 ms | 0/40 | 0/40 |
| YOLO11n + CCT VN ONNX | 42.90 ms | 38.57 ms | 0/40 | 0/40 |

YOLO11n phát hiện đúng vị trí 1/40 biển ở ngưỡng vận hành; detector hiện tại là 0/40. Cả hai vẫn dùng bộ lọc hình học/màu của ứng dụng. CCT nhanh khoảng 12.2 lần trong phép OCR crop GT đầu tiên; detector video nhanh khoảng 9.9 lần so với cấu hình detector ảnh đầu tiên. Đây là một lượt đo tuần tự, không có khoảng tin cậy.

Pipeline mean lần lượt 425.91 / 435.82 / 43.87 ms nhưng hầu hết ảnh không có crop dự đoán qua ngưỡng: tuyệt đối không coi các số này là tốc độ đọc biển thành công hay FPS của web. Bộ tổng hợp không đại diện camera thật; các số thấp cũng không chứng minh chất lượng giao thông thực tế thấp tương ứng.

## Điểm cần kiểm chứng trong mã

1. `src/core/image/detector.py`: detector chạy 640/960 tùy ảnh và có thể chạy lại ngưỡng thấp. Đây là phần chiếm phần lớn thời gian ở bộ tổng hợp. Nên đối chiếu detector nhẹ/ONNX trên cùng dữ liệu camera, cố định ngưỡng và giới hạn ảnh để đo đúng trade-off.
2. Cũng trong detector: loại box lớn hơn 25% ảnh, rộng dưới 25 px/cao dưới 15 px, tỷ lệ ngoài 0.90–5.2, hoặc vùng có màu đỏ trên 40%. Các luật này có thể loại biển cận cảnh/nhỏ/nghiêng/đỏ; cần ablation từng luật có nhãn, chưa khẳng định chúng là nguyên nhân của kết quả lần này.
3. `src/core/ocr/engine.py`: YOLO OCR có nhiều forward pass khi kết quả yếu; chi phí tăng mạnh ở ảnh khó. CCT đã có đường chọn `OCR_ENGINE=onnx`, nhưng phép đo hiện tại chưa chứng minh giữ được độ chính xác nên chưa đổi cấu hình.
4. `src/services/image_recognition.py`: có các nhánh vùng ký tự, OCR toàn ảnh, EasyOCR và cloud sau khi đọc thất bại. Cần đo số lần gọi/thời gian từng nhánh và p95 của service trước khi giới hạn fallback. Nhánh đọc toàn ảnh của sequence OCR cần kiểm chứng vì FastPlateOCR được thiết kế nhận crop biển.
5. `src/core/video/tracker.py`: đã có lập lịch OCR và chọn/vote đọc theo track. Nên tối ưu tiếp từ cơ chế sẵn có, đo theo ID xe và nhóm điều kiện; không cần thêm một tracker khác chỉ vì repository mới có tracking.

## Hướng triển khai đề xuất

Ưu tiên FastPlateOCR làm nền OCR và một detector nhẹ đã huấn luyện phù hợp biển Việt Nam. Giữ model hiện tại làm đối chứng. Chưa chọn CCT VN hiện có làm mặc định vì chưa đạt độ chính xác trên phép thử sẵn có.

Trước tiên lập tập ảnh camera thật có bbox/transcript được kiểm tra thủ công, gồm xe máy hai dòng, ô tô, nhiều xe, âm tính, đêm, lóa, nhỏ và nghiêng. Tách theo camera/đoạn video để tránh các frame gần nhau lọt cả train và test. Mục tiêu ban đầu vài trăm ảnh để chẩn đoán, mở rộng trước khi nghiệm thu.

Chạy cùng dữ liệu và phần cứng: detector hiện tại so với YOLO11n/ONNX; OCR hiện tại so với CCT VN và global CCT S/XS; raw crop so với nắn phối cảnh khi đủ thông tin hình học. Báo detection recall, exact plate recall/precision, CER và latency p50/p95 riêng theo nhóm, cùng tỷ lệ từ chối đọc. Chỉ đổi mặc định sau khi đạt mục tiêu độ chính xác đã đặt ra và giảm latency trên chính bộ này.

Nếu model sai có hệ thống trên camera thật, fine-tune trên dữ liệu Việt Nam cùng điều kiện camera rồi kiểm thử trên tập giữ riêng. Chọn execution provider phù hợp phần cứng sau khi kiểm tra thiết bị; môi trường CPU hiện tại không dùng được TensorRT/CUDA chỉ bằng việc bật một cờ. Không hạ confidence hoặc ép chuỗi theo regex chỉ để làm đẹp tỷ lệ đọc được.
