# Báo cáo Day 09 — Phạm Thị Lương, 2A202603302

## 1. Kết luận trước
Pipeline kết luận **HOLD**. Tổng số ảnh nhận vào là 205/224 ảnh (loại 19 ảnh do lỗi cấu trúc, kích thước nhỏ, trùng lặp hoặc rò rỉ test ở Bước 1). Sau quá trình tự động sửa lỗi, kiểm định và mô phỏng người duyệt với ngân sách cố định là 80 ảnh, pipeline xuất ra bản nháp `clean_v1` gồm 205 ảnh. 
* **Lý do chính dẫn đến HOLD:** Tỷ lệ ảnh còn tồn đọng cảnh báo chưa được xử lý là `0.2927` (~29.3%), vượt mức giới hạn cho phép của cổng chặn là `0.1` (10%). Nguyên nhân gốc rễ là do hàng đợi người duyệt (`05_review_queue.csv`) có tới 145 ảnh cần xem xét, nhưng ngân sách mô phỏng chỉ giải quyết được 80 ảnh, khiến lượng cảnh báo vượt ngưỡng an toàn bị giữ lại.

## 2. Lỗi và phân việc

Dựa trên báo cáo lỗi thô trước khi sửa (`02_error_list_v1`), phân bố lỗi và trách nhiệm xử lý được chia rõ ràng giữa máy và người như sau:

| Mã lỗi | Số ảnh/dòng | Ai sửa (máy/người) | Giải thích chi tiết nghiệp vụ |
|---|---:|---|---|
| `MISSING_LABEL_FILE` | 36 | Người | Ảnh nền hoặc ảnh thiếu file nhãn hoàn toàn. Hệ thống tuân thủ nguyên tắc an toàn: máy tuyệt đối không tự bịa nhãn mà bắt buộc đẩy vào hàng đợi cho người gán. |
| `BOX_OUT_OF_IMAGE` | 5 | Máy | Các bounding box tràn biên nhẹ. Module `autofix` tự động kẹp (clip) tọa độ về giới hạn chuẩn $[0, 1]$ một cách an toàn. |
| `BAD_CLASS_ID` / `BAD_FORMAT` | 4 | Máy | Các dòng nhãn bị sai định dạng, thiếu cột hoặc chứa ID lớp không tồn tại trong danh mục sẽ bị tự động loại bỏ (`drop_line`) để tránh làm hỏng mô hình train. |
| `POSSIBLE_MISSING` / `POSSIBLE_FALSE_POS` | 273 | Người | Cảnh báo đối soát ngữ nghĩa từ mô hình lớn hơn (`yolo26l`). Các trường hợp này đòi hỏi con người xác thực xem đối tượng có thực sự bị sót hoặc gán nhầm hay không. |

Cơ chế sắp xếp hàng đợi (`05_review_queue.csv`) ưu tiên đưa các ảnh chứa nhiều lỗi nghiêm trọng và độ tự tin thấp lên đầu để tối ưu hóa thời gian cho chuyên gia nhãn. Tuy nhiên, với ngân sách 80 ảnh, người duyệt chỉ giải quyết được một phần trong tổng số 145 ảnh chờ, để lại lượng lớn cảnh báo chưa xử lý làm kích hoạt cổng `HOLD`.

## 3. Calibration (2 ngưỡng)

Quá trình quét hiệu chỉnh trên tập dữ liệu chuẩn `data/calib/` (39 ảnh có chèn lỗi nhân tạo) đem lại sự đánh đổi rõ rệt giữa Precision và Recall:

| Tham số | Khởi đầu | Đã chọn | Precision / Recall (trước → sau) | Lý do chọn lựa và đánh đổi (Precision vs. Recall) |
|---|---|---|---|---|
| `duplicates.phash_dist` | 2 | 8 | Tăng độ phủ ảnh trùng lặp gần | Ngưỡng quá thấp bỏ sót ảnh bị nén/biến đổi ánh sáng; tăng lên 8 giúp bắt trọn các biến thể `DUP_IMAGE_NEAR` mà không làm tăng báo động giả ảnh sạch. |
| `second_opinion.conf` | 0.25 | 0.5 | Precision tăng đáng kể, Recall duy trì ổn định | Nâng ngưỡng tự tin lên 0.5 giúp lọc bỏ bớt các dự đoán nhiễu (FP) của mô hình lớn, tránh làm quá tải hàng đợi của người duyệt bằng những cảnh báo kém chất lượng. |

**Điểm mù từ tập Calibration có thể đánh lừa bạn:** 
Tập dữ liệu calib chỉ có 39 ảnh với các lỗi được chèn nhân tạo rất "sạch" và rạch ròi. Trên thực tế, phân phối lỗi của dữ liệu `raw` phức tạp hơn nhiều (ví dụ các ca biến đổi màu sắc, góc chụp góc khuất). Do đó, chỉ số Precision/Recall trên tập calib chỉ mang tính định hướng, không thể hiện hoàn toàn chính xác hiệu suất khi áp dụng lên dữ liệu thực tế ngoài đời thực.

## 4. Cửa chặn và điều pipeline KHÔNG bắt được
*(a) Kiểm chứng cửa chặn hoạt động:*
Khi chạy lệnh mô phỏng cắt bỏ ngân sách duyệt:
```bash
python -m pipeline.run --budget 0 --reports work/rep_nb --export-dir work/exp_nb