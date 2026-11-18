"""CHECK 6 — Ý kiến thứ hai: so nhãn với một model LỚN HƠN (yolo26l).   ★★★ (khó nhất, đáng điểm nhất)

Test:  pytest tests/test_second_opinion.py -q

Máy kiểm quy tắc, người kiểm ý nghĩa (slide). Các lỗi như thiếu nhãn / gán nhầm lớp hợp lệ / box lỏng
KHÔNG bắt được bằng quy tắc cú pháp. Ta nhờ một model mạnh hơn "nhìn lại" và CHỈ CẢNH BÁO (model cũng có thể sai):
những ảnh bị cờ sẽ vào hàng đợi cho NGƯỜI duyệt.

`preds[stem]` = list `[id_lớp, conf, cx, cy, w, h]` của model (lấy qua `get_preds(ds, cfg, "checker")` nếu preds=None).
`L = ds.valid_boxes(stem)` = list `(id_lớp, cx, cy, w, h)` của nhãn (đã bỏ dòng hỏng).
Ngưỡng ở `cfg["second_opinion"]`: conf, min_area_px, fp_conf, iou_missing, iou_match, iou_loose.

Thuật toán gợi ý, với từng ảnh (bỏ qua ảnh không có trong preds hoặc không có file nhãn):
  P = dự đoán có conf >= conf  VÀ diện tích px (w*W * h*H) >= min_area_px
  Với mỗi dự đoán r trong P: lấy các nhãn có IoU(r, nhãn) >= iou_missing  (cands)
   - không có cands                            -> POSSIBLE_MISSING     (model thấy vật mà nhãn không có box)
   - có cands cùng lớp, tốt nhất IoU < iou_loose -> POSSIBLE_LOOSE_BOX  (đúng vật, box lỏng/lệch)
   - không có cands cùng lớp, nhưng cands tốt nhất IoU >= iou_match (khác lớp) -> POSSIBLE_WRONG_CLASS
  Với mỗi dòng nhãn hợp lệ: nếu IoU với MỌI dự đoán (conf >= fp_conf, không lọc diện tích) đều < iou_missing
                                             -> POSSIBLE_FALSE_POS  (box nhãn không khớp vật nào model thấy; Issue.line = số dòng)

Chi tiết các ca biên (test kiểm đúng các ca này)
- `cands` gồm nhãn MỌI lớp có IoU >= iou_missing; "tốt nhất cùng lớp" = cands cùng lớp có IoU lớn nhất; "tốt nhất khác lớp" tương tự với cands khác lớp.
- Thứ tự quyết định cho mỗi dự đoán: (1) cands rỗng -> MISSING. (2) có cands cùng lớp: IoU tốt nhất < iou_loose -> LOOSE_BOX, ngược lại KHÔNG cờ
  (nhãn đúng lớp đã phủ vật này, kể cả khi còn nhãn khác lớp chồng lên). (3) không có cands cùng lớp: nếu IoU tốt nhất khác lớp >= iou_match -> WRONG_CLASS;
  nếu chỉ có khác lớp với IoU trong [iou_missing, iou_match) -> không cờ gì (mơ hồ: để cho FALSE_POS / lần duyệt khác).
- Một dự đoán sinh tối đa MỘT issue (MISSING / LOOSE_BOX / WRONG_CLASS); một ảnh có thể có nhiều issue.
- Thứ tự issue: theo `ds.image_files()` rồi theo thứ tự dự đoán trong `preds[stem]`, cuối cùng là các FALSE_POS theo số dòng; `Issue.image` = stem, `Issue.line` chỉ đặt cho FALSE_POS.

Lưu ý số dòng: dùng `ds.read_label_lines(stem)` (giữ số dòng gốc, kể cả dòng hỏng/trống) để lấy `Issue.line`; `valid_boxes` KHÔNG giữ số dòng.

Tất cả severity WARN; `Issue.extra` nên có {"conf": ...} hoặc {"iou": ...} (hàng đợi duyệt dùng conf để xếp ưu tiên).

Gợi ý
- `iou_xywh` có sẵn. Dòng nhãn hỏng không được làm script chết (dùng `ds.valid_boxes` và `parse_yolo_line` trong try).
- Kết quả phụ thuộc mạnh vào ngưỡng: calibrate chúng ở Bước 3 thay vì đoán.
"""
from ..common import WARN, Issue, iou_xywh, parse_yolo_line  # noqa: F401
from ..model_cache import get_preds  # noqa: F401


def run(ds, cfg, preds=None):
    so_cfg = cfg["second_opinion"]
    conf = float(so_cfg["conf"])
    min_area_px = float(so_cfg["min_area_px"])
    fp_conf = float(so_cfg["fp_conf"])
    iou_missing = float(so_cfg["iou_missing"])
    iou_match = float(so_cfg["iou_match"])
    iou_loose = float(so_cfg["iou_loose"])
    preds = preds if preds is not None else get_preds(ds, cfg, "checker")
    issues = []

    for p in ds.image_files():
        stem = p.stem
        if ds.label_path(stem).exists() is False or stem not in preds:
            continue
        size = ds.image_size(stem)
        if size is None:
            continue
        width, height = size
        labels = ds.valid_boxes(stem)
        P = []
        for pred in preds[stem]:
            cls, pc, cx, cy, w, h = pred
            area = w * width * h * height
            if pc >= conf and area >= min_area_px:
                P.append((cls, pc, (cx, cy, w, h)))

        for cls, pc, box in P:
            cands = [(lab, iou_xywh(box, lab[1:])) for lab in labels
                     if iou_xywh(box, lab[1:]) >= iou_missing]
            if not cands:
                issues.append(Issue("second_opinion", WARN, "POSSIBLE_MISSING", stem,
                                    "Model thấy vật thể không có nhãn", None,
                                    {"conf": pc}))
                continue
            same = [(lab, iou) for lab, iou in cands if lab[0] == cls]
            if same:
                lab, best = max(same, key=lambda x: x[1])
                if best < iou_loose:
                    issues.append(Issue("second_opinion", WARN, "POSSIBLE_LOOSE_BOX", stem,
                                        "Box có thể lỏng hoặc lệch", None,
                                        {"iou": best, "conf": pc}))
                continue
            different = [(lab, iou) for lab, iou in cands if lab[0] != cls]
            if different:
                lab, best = max(different, key=lambda x: x[1])
                if best >= iou_match:
                    issues.append(Issue("second_opinion", WARN, "POSSIBLE_WRONG_CLASS", stem,
                                        "Lớp nhãn có thể sai", None,
                                        {"iou": best, "conf": pc}))

        fp_preds = [(pred[2], pred[3], pred[4], pred[5])
                    for pred in preds[stem] if pred[1] >= fp_conf]
        for line_no, text in ds.read_label_lines(stem) or []:
            try:
                lab = parse_yolo_line(text)
            except ValueError:
                continue
            cls, cx, cy, w, h = lab
            if not 0 <= cls < len(ds.classes):
                continue
            box = (cx, cy, w, h)
            if all(iou_xywh(box, pred) < iou_missing for pred in fp_preds):
                issues.append(Issue("second_opinion", WARN, "POSSIBLE_FALSE_POS", stem,
                                    "Nhãn box không khớp dự đoán model", line_no,
                                    {"iou": max((iou_xywh(box, pred) for pred in fp_preds),
                                                default=0.0)}))
    return issues
