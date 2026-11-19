# Phân tích kết quả train raw vs clean

Các số liệu lấy từ `raw_seed0/1.json`, `clean_seed0/1.json`, `comparison.json` và báo cáo QC v1/v3. Mỗi biến thể chỉ có 2 seed; đây là quan sát mô tả, chưa phải kết luận thống kê mạnh.

## 1. Chênh lệch mAP50 và độ nhiễu giữa seed

| Biến thể | Seed 0 | Seed 1 | Trung bình ± SD |
|---|---:|---:|---:|
| raw | 0.7256 | 0.7259 | 0.7258 ± 0.0002 |
| clean | 0.6880 | 0.7015 | 0.6947 ± 0.0095 |

`mAP50(clean) - mAP50(raw) = -0.0311`. Chênh lệch này lớn hơn SD quan sát ở cả hai nhóm, đặc biệt lớn hơn dao động clean giữa hai seed. Tuy nhiên, chỉ hai seed không đủ để ước lượng ổn định độ nhiễu hay chứng minh quan hệ nhân quả. Kết luận thận trọng: trong lần chạy này raw đạt mAP50 cao hơn; chưa thể kết luận rằng dữ liệu raw tốt hơn dữ liệu đã làm sạch.

## 2. Raw thực sự train trên bao nhiêu ảnh?

`raw_seed*.json` ghi `train_images: 224`, nhưng `scripts/train_compare.py` đếm số file đã materialize trước khi Ultralytics quét và xác thực nhãn. Đây là số ảnh đầu vào, không nhất thiết là số ảnh được loader dùng.

Từ `02_error_list_v1`, có 11 ảnh riêng biệt chắc chắn không qua xác thực nhãn/ảnh của Ultralytics 8.4.214: 2 ảnh hỏng, 3 ảnh có dòng nhãn sai định dạng (gồm NaN hoặc thiếu cột), và 6 ảnh có class ID không hợp lệ. Vì vậy, 224 − 11 = **213 ảnh hiệu dụng suy ra từ dữ liệu lỗi**. Ba ảnh nhỏ theo ngưỡng dự án vẫn vượt mức tối thiểu 10 px của Ultralytics; nhãn trống/thiếu được xem như ảnh nền chứ không loại ảnh.

Lưu ý: `BOX_OUT_OF_IMAGE` của pipeline tính theo mép hộp. Các giá trị `cx, cy, w, h` trong 8 dòng bị gắn cờ vẫn nằm trong dung sai tọa độ mà verifier 8.4.214 kiểm tra; do đó không thể trừ cả 8 ảnh này khỏi số ảnh train nếu chưa có log/cache scan xác nhận. Log scan Ultralytics không được lưu cùng JSON kết quả, nên 213 là số suy ra từ các file lỗi, không phải con số `found` được ghi trực tiếp bởi loader. Muốn chốt con số tuyệt đối, lưu lại log/cache dataset scan ở lần chạy tiếp theo.

## 3. Rò rỉ ảnh test và mức ảnh hưởng

Có **5 ảnh train raw trùng với kho test/val**, được intake ghi là `LEAK_TEST`: `img_0049`, `img_0101`, `img_0167`, `img_0174`, `img_0221`. Tức 5/224 ảnh được materialize (khoảng 2.2%); các ảnh này khớp lần lượt với `test/test_033`, `test/test_039`, `test/test_044`, `test/test_085`, `test/test_009`.

Rò rỉ có thể làm điểm test raw lạc quan hơn vì mô hình đã thấy nội dung ảnh lúc train. Nhưng không thể kết luận nó làm tăng mAP bao nhiêu từ các JSON tổng hợp hiện có: không có AP theo từng ảnh và không có lượt train đối chứng đã loại 5 ảnh đó. Không được coi 2.2% ảnh trùng là 2.2 điểm mAP. Để đo, tạo một biến thể raw bỏ đúng 5 ảnh rò rỉ, train lại cùng seed/siêu tham số, rồi so trên cùng test; đồng thời kiểm tra hash giữa train và test trước khi diễn giải điểm raw.

## 4. Lớp nào được lợi?

AP50 trung bình theo hai seed:

| Lớp | raw | clean | clean − raw |
|---|---:|---:|---:|
| car | 0.7375 | 0.7339 | −0.0036 |
| person | 0.8221 | 0.8178 | −0.0043 |
| truck | 0.6485 | 0.5236 | −0.1249 |
| bus | 0.6949 | 0.7037 | **+0.0088** |

Bus có mức tăng danh nghĩa lớn nhất (khoảng 0.009 mAP50), nhưng mức tăng nhỏ và chưa đủ seed để khẳng định là cải thiện ổn định. Truck giảm nhiều nhất.

Trong `02_error_list_v1`, các lỗi hình học tập trung nhiều ở class person: 6/8 `BOX_OUT_OF_IMAGE`, 3/4 `BOX_ZERO`, 5/7 `DUP_BOX`. Ngoài ra có 3 `BAD_FORMAT` và 6 `BAD_CLASS_ID` (các ID sai không thể quy về lớp hợp lệ). Bus không có box nào trong các dòng lỗi định dạng/hình học được liệt kê. Điều này có thể góp phần khiến bus ít bị ảnh hưởng khi dọn dữ liệu, nhưng không chứng minh là nguyên nhân tăng AP; person vẫn có nhiều lỗi mà AP gần như không đổi, còn chênh lệch truck cần kiểm tra số lượng/nhãn truck và các box bị bỏ. Phân bố box clean sau review trong `class_stats.csv` là car 100, person 574, truck 41, bus 30; nên lớp ít mẫu cũng có thể dao động mạnh.

## 5. Clean còn lỗi không? Có phải chặn trên?

V3 không còn lỗi bắt buộc, nhưng còn 88 bản ghi cảnh báo: 3 `BOX_HUGE`, 7 `BOX_TINY`, 4 `EMPTY_LABEL`, 20 `POSSIBLE_FALSE_POS`, 24 `POSSIBLE_LOOSE_BOX`, 26 `POSSIBLE_MISSING`, 4 `POSSIBLE_WRONG_CLASS`. Chúng thuộc **44/203 ảnh**; queue trước review có 130 ảnh, trong khi ngân sách/mô phỏng xử lý 80, tức vượt ngân sách 50 ảnh. Vì vậy verdict là **HOLD** với cảnh báo trên 21.67% ảnh, cao hơn ngưỡng 10%.

Đây chưa phải “chặn trên” hay bộ nhãn vàng/oracle: 44 ảnh vẫn còn cảnh báo, các cảnh báo ngữ nghĩa cần người xác minh, và 80 lượt review là mô phỏng. `clean_v1` là bản nháp để thí nghiệm, không phải dataset đã được xác nhận hoàn toàn sạch. Muốn có chặn trên cần review thủ công toàn bộ queue còn lại, phân xử các nhãn rỗng, rồi chạy QC vòng cuối.
