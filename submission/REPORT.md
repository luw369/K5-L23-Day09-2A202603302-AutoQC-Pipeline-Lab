# Báo cáo Day 09 — Phạm Thị Lương, 2A202603302

## 1. Kết luận trước
Pipeline kết luận **HOLD**, không phải Release. Tập thô có 224 ảnh; intake giữ lại 203 và loại 21 ảnh (3 `BAD_SIZE`, 2 `CORRUPT_IMAGE`, 8 `DUP_IMAGE_EXACT`, 3 `DUP_IMAGE_NEAR`, 5 `LEAK_TEST`). Sau tự sửa và mô phỏng duyệt 80 ảnh, v3 còn 0 lỗi bắt buộc nhưng có cảnh báo trên 44/203 ảnh = **21.67%**, cao hơn ngưỡng Hold 10%. Vì vậy pipeline xuất `clean_v1` ở trạng thái bản nháp; chưa được phát hành.

## 2. Lỗi và phân việc
Số dưới đây là số issue, không phải số ảnh duy nhất. Intake quét 224 ảnh; các lỗi QC v1 kiểm tra trên 203 ảnh được nhận.

| Giai đoạn / mã lỗi | Số issue | Mẫu số | Xử lý |
|---|---:|---:|---|
| Intake: `BAD_SIZE` | 3 | 224 ảnh | Máy loại ảnh nhỏ |
| Intake: `CORRUPT_IMAGE` | 2 | 224 ảnh | Máy loại ảnh không đọc được |
| Intake: `DUP_IMAGE_EXACT` / `DUP_IMAGE_NEAR` | 8 / 3 | 224 ảnh | Máy loại ảnh trùng |
| Intake: `LEAK_TEST` | 5 | 224 ảnh | Máy loại ảnh trùng kho test/val |
| QC: `BAD_CLASS_ID` / `BAD_CLASS_NAME` | 6 / 2 | 203 ảnh | Máy bỏ dòng ID sai; sửa tên lớp trong YAML |
| QC: `BAD_FORMAT` / `BOX_ZERO` / `DUP_BOX` | 3 / 4 / 7 | 203 ảnh | Máy bỏ dòng hỏng, box rỗng hoặc trùng |
| QC: `BOX_OUT_OF_IMAGE` | 8 | 203 ảnh | Máy clip box |
| QC: `MISSING_LABEL_FILE` | 6 | 203 ảnh | Người gán nhãn; máy không tự tạo nhãn |
| Cảnh báo QC: `POSSIBLE_FALSE_POS` / `POSSIBLE_LOOSE_BOX` / `POSSIBLE_MISSING` / `POSSIBLE_WRONG_CLASS` | 29 / 31 / 68 / 18 | 203 ảnh | Người kiểm ngữ nghĩa; cảnh báo có thể trùng trên cùng ảnh |

QC v1 có 36 lỗi bắt buộc và 171 cảnh báo. `03_fixes.csv` ghi 36 hành động: 20 `drop_line`, 8 `clip_box`, 6 `needs_label`, 2 `rename_classes`. Ở v2 còn 6 `MISSING_LABEL_FILE`; mô phỏng duyệt thay nhãn cho 80 ảnh. Queue có 130 ảnh, sắp theo điểm ưu tiên có trọng số; nhóm `NEEDS_LABEL` được ưu tiên cao (trọng số 10), cùng các ảnh có nhiều lỗi/độ tin cậy cao. Sau duyệt, v3 không còn lỗi bắt buộc, còn 44 ảnh có cảnh báo. Đây là duyệt mô phỏng, không phải xác nhận của chuyên gia thật.

## 3. Calibration (2 ngưỡng)
Sweep trên tập calib 39 ảnh được lưu tại `submission/calibration/calibration_report.md` và `.json`. Bảng ghi precision/recall; các mã trong mỗi ô là nhóm lỗi tương ứng.

| Tham số | Giá trị đối chiếu → dùng | Precision / Recall trước → sau | Lý do và đánh đổi |
|---|---|---|---|
| `duplicates.phash_dist` | 2 → 8 | `DUP_IMAGE_NEAR`: 1.00/0.50 → 1.00/0.67 | Ở 8 tăng recall mà sweep không ghi nhận FP. 16 còn tăng recall lên 0.83 với precision 1.00, nhưng chọn 8 một cách bảo thủ để giảm nguy cơ loại nhầm ảnh thật trên dữ liệu ngoài calib. 20 làm kết quả xấu đi: recall exact còn 0.33, near 0.50. |
| `second_opinion.conf` | 0.25 → 0.50 | `POSSIBLE_MISSING`: 0.50/1.00 → 0.57/1.00; `POSSIBLE_WRONG_CLASS`: 0.56/0.83 → 0.56/0.83 | Tăng ngưỡng cải thiện precision của cảnh báo thiếu nhãn mà không giảm recall trên calib; wrong-class không đổi. Đổi lại, loose-box giảm từ 0.29/0.40 xuống 0.20/0.20. Chấp nhận trade-off này để hạn chế queue nhiễu; `FALSE_POS` không đổi (0.31/1.00) vì dùng ngưỡng `fp_conf` riêng. |

**Điểm có thể đánh lừa:** calib nhỏ và lỗi được chèn có kiểm soát; ví dụ `conf` không ảnh hưởng `POSSIBLE_FALSE_POS` vì mã đó dùng `fp_conf=0.1`. Các precision/recall này không đảm bảo tương tự trên dữ liệu thật, nơi model có thể bỏ sót vật nhỏ/khuất hoặc báo nhầm.

## 4. Cửa chặn và giới hạn
Đã kiểm chứng nhánh Rework bằng lệnh:
```bash
python -m pipeline.run --budget 0 --reports work/report_probe_reports_20261119 --export-dir work/report_probe_export_20261119 --export-name clean --work work/report_probe_20261119
```
Kết quả: exit code **20**, còn 6 lỗi bắt buộc `MISSING_LABEL_FILE`, thông báo không xuất dataset; `work/report_probe_export_20261119/clean` không tồn tại. Ở lần chạy chính với ngân sách 80, lỗi bắt buộc bằng 0 nhưng 44/203 ảnh còn cảnh báo nên quyết định là Hold.

Pipeline không xác nhận được hai việc sau: (1) cảnh báo từ model có thật sự là thiếu/thừa box hay model sai; cần người xem ảnh và nhãn. (2) nhãn rỗng có phải ảnh nền thật hay ảnh bị thiếu annotation; cần đối chiếu ảnh gốc/annotator. Ngoài ra, calib nhỏ không đại diện hết ảnh khuất, biến dạng hoặc lớp hiếm.

## 5. So sánh train raw vs clean
Đã chạy 2 seed (`0, 1`) cho mỗi biến thể với cùng `yolo26n.pt`, 20 epoch, batch 16, imgsz 640, cùng val/test theo notebook. Bảng dưới là mean ± độ lệch chuẩn giữa seed, lấy từ `submission/results/comparison.md`.

| Biến thể | Ảnh train | mAP50 | mAP50-95 | Precision | Recall |
|---|---:|---:|---:|---:|---:|
| raw | 224 | 0.7258 ± 0.0002 | 0.5117 ± 0.0038 | 0.7635 ± 0.0612 | 0.6490 ± 0.0281 |
| clean | 203 | 0.6947 ± 0.0095 | 0.4822 ± 0.0069 | 0.7263 ± 0.0049 | 0.6191 ± 0.0165 |

Chênh mAP50 (clean − raw) là **−0.0311**; mAP50-95 là **−0.0295**. Chênh mAP50 lớn hơn dao động seed quan sát được, nhưng chỉ có 2 seed nên chưa đủ kết luận tổng quát. Raw có thể được lợi không công bằng từ ảnh trùng/rò rỉ; intake ghi nhận 5 ảnh `LEAK_TEST`. Mặt khác clean có ít hơn 21 ảnh; AP50 lớp truck giảm từ trung bình khoảng 0.648 raw xuống 0.524 clean. Cần kiểm tra trùng/lộ dữ liệu bằng hash, so phân bố số box theo lớp và xem overlay nhãn trước/sau, sau đó chạy thêm seed. Kết quả hiện tại **không chứng minh clean tốt hơn**; cũng chưa chứng minh việc làm sạch là nguyên nhân duy nhất khiến điểm thấp hơn.

## 6. Tái lập, Git và sử dụng AI
Các kết quả train có cùng cấu hình ghi trong JSON; clean dùng manifest SHA1 `5d6d7d473931286cb3246b2a90b5c107617a6a0f`, config SHA1 `82187374d421abcee64783b7dad22f0bd99848cf`. Lần kiểm gần nhất: **79 tests passed**; pipeline, calibration và checker `--no-train` đã chạy. Repo có 11 commit; trong 5 commit gần nhất chỉ thấy một commit của `Sue3004` (`Nop bai Lab day09`). Rubric yêu cầu ít nhất 5 commit rõ ràng của học viên, nên số commit cá nhân cần được bổ sung bằng các mốc công việc thật, không tạo commit giả.

Có dùng AI hỗ trợ code/debug và soạn báo cáo; kết quả được kiểm bằng test, artifacts và lệnh chạy pipeline. Một lỗi AI đã mắc: bản báo cáo trước giữ số liệu cũ (205 ảnh, 29.27%, queue 145, thiếu nhãn 36), không khớp artifacts hiện tại. Đã đối chiếu lại với CSV/JSON sinh bởi pipeline và sửa các số liệu trong báo cáo này.