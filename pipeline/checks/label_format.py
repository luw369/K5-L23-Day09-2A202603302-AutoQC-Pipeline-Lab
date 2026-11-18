"""CHECK 2 — Dòng nhãn YOLO: sai định dạng, ID lớp lạ, box tràn ảnh, box rỗng, box lặp.   (Script 2 trong slide)   ★★

Test:  pytest tests/test_label_format.py -q

Mỗi dòng nhãn: `id cx cy w h` (5 số, toạ độ 0–1). Trả về list[Issue]; `Issue.line` = số dòng (đếm từ 1).

| code             | severity | khi nào                                                                  |
|------------------|----------|--------------------------------------------------------------------------|
| BAD_FORMAT       | ERROR    | không đúng 5 cột số (dùng `parse_yolo_line`, bắt `ValueError`)           |
| BAD_CLASS_ID     | ERROR    | id lớp ngoài 0..len(ds.classes)-1                                        |
| BOX_ZERO         | ERROR    | w <= 0 hoặc h <= 0                                                       |
| BOX_OUT_OF_IMAGE | ERROR    | mép box vượt [0,1] quá `cfg["label_format"]["overflow_tol"]`; extra={"overflow": mức tràn} |
| DUP_BOX          | ERROR    | cùng lớp với một dòng TRƯỚC ĐÓ và IoU > `dup_box_iou`; báo ở dòng SAU    |
| BOX_TINY         | WARN     | cạnh ngắn của box (px) < `min_box_px`  (cần `ds.image_size(stem)`)       |
| BOX_HUGE         | WARN     | w*h > `max_box_frac`                                                     |

Gợi ý
- Mép trái = x - w/2, mép phải = x + w/2 (xem câu hỏi "dòng YOLO nào lỗi?" trong slide).
- Một dòng hỏng (BAD_FORMAT, BAD_CLASS_ID, BOX_ZERO) thì `continue`, đừng kiểm tiếp hình học của dòng đó.
- Dòng thiếu cột làm script của slide dừng giữa chừng: đây là lý do phải `try/except`.
- `iou_xywh(a, b)` có sẵn trong common.py.
- Ngưỡng nằm trong `cfg["label_format"]` — đừng viết cứng số vào code.
"""
from ..common import ERROR, WARN, Issue, iou_xywh, parse_yolo_line  # noqa: F401


def run(ds, cfg):
    lc = cfg["label_format"]
    overflow_tol = float(lc["overflow_tol"])
    dup_iou = float(lc["dup_box_iou"])
    min_box_px = float(lc["min_box_px"])
    max_box_frac = float(lc["max_box_frac"])
    issues = []

    for stem in sorted(p.stem for p in ds.image_files()):
        lines = ds.read_label_lines(stem)
        if lines is None:
            continue
        size = ds.image_size(stem)
        prior = []
        for line_no, text in lines:
            try:
                cls, cx, cy, w, h = parse_yolo_line(text)
            except ValueError:
                issues.append(Issue("label_format", ERROR, "BAD_FORMAT", stem,
                                    "Dòng không đúng định dạng YOLO", line_no))
                continue

            if cls < 0 or cls >= len(ds.classes):
                issues.append(Issue("label_format", ERROR, "BAD_CLASS_ID", stem,
                                    f"ID lớp {cls} ngoài phạm vi", line_no))
                continue
            if w <= 0 or h <= 0:
                issues.append(Issue("label_format", ERROR, "BOX_ZERO", stem,
                                    "Chiều rộng hoặc chiều cao bằng không", line_no))
                continue

            left, top = cx - w / 2, cy - h / 2
            right, bottom = cx + w / 2, cy + h / 2
            overflow = max(0.0, -left, -top, right - 1.0, bottom - 1.0)
            if overflow > overflow_tol:
                issues.append(Issue("label_format", ERROR, "BOX_OUT_OF_IMAGE", stem,
                                    f"Box tràn ảnh {overflow:.4f}", line_no,
                                    {"overflow": overflow}))

            if size is not None:
                width, height = size
                short_side = min(w * width, h * height)
                if short_side < min_box_px:
                    issues.append(Issue("label_format", WARN, "BOX_TINY", stem,
                                        "Box quá nhỏ", line_no,
                                        {"short_side_px": short_side}))
                if w * h > max_box_frac:
                    issues.append(Issue("label_format", WARN, "BOX_HUGE", stem,
                                        "Box chiếm quá lớn tỉ lệ ảnh", line_no,
                                        {"box_frac": w * h}))

            box = (cls, cx, cy, w, h)
            for prev in prior:
                if cls == prev[0] and iou_xywh(
                    (prev[1], prev[2], prev[3], prev[4]),
                    (cx, cy, w, h),
                ) > dup_iou:
                    issues.append(Issue("label_format", ERROR, "DUP_BOX", stem,
                                        "Box trùng với một dòng trước đó", line_no,
                                        {"iou": iou_xywh((prev[1], prev[2], prev[3], prev[4]),
                                                         (cx, cy, w, h))}))
                    break
            prior.append(box)
    return issues
