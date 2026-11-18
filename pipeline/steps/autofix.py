"""BƯỚC 2/4 — Sửa tự động những lỗi bắt buộc mà máy sửa được AN TOÀN.   ★★

Test:  pytest tests/test_autofix.py -q

`fix(ds, issues, cfg) -> list[dict]`: duyệt `issues` (chỉ lỗi severity ERROR), sửa thẳng vào thư mục `ds`,
và trả về danh sách thay đổi; mỗi phần tử có khoá: image, line, action, before, after
(đây chính là file `03_fixes.csv` — bằng chứng pipeline đã làm gì, người có thể kiểm lại).

| code lỗi                                       | cách sửa                                    | action           |
|------------------------------------------------|---------------------------------------------|------------------|
| BAD_FORMAT, BAD_CLASS_ID, BOX_ZERO, DUP_BOX    | xoá dòng đó khỏi file nhãn                  | "drop_line"      |
| BOX_OUT_OF_IMAGE                               | cắt box về trong [0,1] (giữ nguyên lớp)     | "clip_box"       |
| MISSING_LABEL_FILE                             | KHÔNG sửa file (máy không thể bịa nhãn): ghi 1 dòng fix, before="(không có file)", after="chuyển người gán" | "needs_label" |
| BAD_CLASS_NAME                                 | ghi lại `names` trong data.yaml đúng `cfg["classes"]` | "rename_classes" |
| DUP_IMAGE_*, LEAK_TEST, CORRUPT_IMAGE, BAD_SIZE| xoá ảnh + nhãn khỏi `ds`                    | "remove_image"   |

Bẫy cần nghĩ tới (có test cho từng cái)
- Một file có NHIỀU dòng lỗi: số dòng trong `issues` là số dòng GỐC. Nếu xoá từng dòng một thì số dòng lệch.
  Gom theo file, rồi ghi lại MỘT lần.
- Sau khi cắt, box có thể không còn diện tích (nằm hẳn ngoài ảnh): lúc đó xoá dòng thay vì ghi box rỗng.
- Một dòng có 2 lỗi (vd. BOX_OUT_OF_IMAGE + DUP_BOX): xoá dòng thắng, chỉ ghi 1 fix `drop_line`, không ghi thêm `clip_box`. Dòng trống ở giữa file vẫn đếm vào số dòng gốc.
- Ảnh vừa bị xoá (DUP_IMAGE_*...) mà còn issue dòng của chính nó: bỏ qua êm, không được báo lỗi/chết.
- Không động tới lỗi WARN (cảnh báo là việc của người). Không sửa file ở `data/raw/` — chỉ sửa `ds`.
- Chạy lần 2 trên dữ liệu đã sửa phải không làm gì thêm (idempotent) — NGOẠI LỆ duy nhất: `needs_label` được ghi lại mỗi lần còn lỗi `MISSING_LABEL_FILE` (vì ảnh vẫn chưa có nhãn).

- `needs_label` KHÔNG tạo file nhãn rỗng (rỗng = "ảnh nền", khác với "chưa gán"). `review_queue` sẽ đẩy ảnh này lên đầu hàng đợi cho người.

Gợi ý: `yaml.safe_load / safe_dump`.
"""
from collections import defaultdict  # noqa: F401

import yaml  # noqa: F401

from ..common import ERROR, parse_yolo_line  # noqa: F401


def fix(ds, issues, cfg):
    fixes = []
    removed_stems = set()

    for i in issues:
        if i.severity != ERROR:
            continue
        if i.code in {"DUP_IMAGE_EXACT", "DUP_IMAGE_NEAR", "LEAK_TEST", "CORRUPT_IMAGE", "BAD_SIZE"}:
            removed_stems.add(i.image)

    for stem in sorted(removed_stems):
        ip = ds.image_path(stem)
        lp = ds.label_path(stem)
        if ip is not None:
            ip.unlink(missing_ok=True)
        lp.unlink(missing_ok=True)
        fixes.append(dict(image=stem, line="", action="remove_image",
                          before="ảnh + nhãn", after="đã xoá"))

    drops = defaultdict(set)
    clips = {}
    need_labels = set()

    drop_codes = {"BAD_FORMAT", "BAD_CLASS_ID", "BOX_ZERO", "DUP_BOX"}
    for i in issues:
        if i.severity != ERROR or i.image in removed_stems:
            continue
        if i.code in drop_codes:
            drops[i.image].add(i.line)
        elif i.code == "BOX_OUT_OF_IMAGE":
            clips.setdefault(i.image, set()).add(i.line)
        elif i.code == "MISSING_LABEL_FILE":
            need_labels.add(i.image)

    for stem, lines in list(clips.items()):
        clips[stem] = lines - drops.get(stem, set())
        if not clips[stem]:
            del clips[stem]

    for stem in sorted(drops):
        lp = ds.label_path(stem)
        if not lp.exists():
            continue
        original = lp.read_text(encoding="utf-8", errors="replace").splitlines()
        kept = []
        for line_no, text in enumerate(original, 1):
            if line_no in drops[stem]:
                fixes.append(dict(image=stem, line=line_no, action="drop_line",
                                  before=text, after=""))
            else:
                kept.append(text)
        lp.write_text("\n".join(kept) + ("\n" if kept and original[-1].endswith("\n") else ""),
                      encoding="utf-8")

    for stem in sorted(clips):
        lp = ds.label_path(stem)
        if not lp.exists():
            continue
        original = lp.read_text(encoding="utf-8", errors="replace").splitlines()
        rewritten = list(original)
        for line_no in sorted(clips[stem]):
            if line_no > len(original):
                continue
            text = original[line_no - 1]
            if line_no in drops.get(stem, set()):
                continue
            try:
                cls, cx, cy, w, h = parse_yolo_line(text)
            except ValueError:
                continue
            left = max(0.0, cx - w / 2)
            right = min(1.0, cx + w / 2)
            top = max(0.0, cy - h / 2)
            bottom = min(1.0, cy + h / 2)
            nw, nh = right - left, bottom - top
            if nw <= 0 or nh <= 0:
                fixes.append(dict(image=stem, line=line_no, action="drop_line",
                                  before=text, after=""))
                rewritten[line_no - 1] = None
                continue
            nx, ny = (left + right) / 2, (top + bottom) / 2
            after = f"{cls} {nx:.6f} {ny:.6f} {nw:.6f} {nh:.6f}"
            fixes.append(dict(image=stem, line=line_no, action="clip_box",
                              before=text, after=after))
            rewritten[line_no - 1] = after
        kept = [text for text in rewritten if text is not None]
        lp.write_text("\n".join(kept) + ("\n" if kept else ""), encoding="utf-8")

    for stem in sorted(need_labels):
        fixes.append(dict(image=stem, line="", action="needs_label",
                          before="(không có file)", after="chuyển người gán"))

    for i in issues:
        if i.severity == ERROR and i.code == "BAD_CLASS_NAME":
            if ds.yaml_path.exists():
                data = yaml.safe_load(ds.yaml_path.read_text(encoding="utf-8")) or {}
                data["names"] = list(cfg["classes"])
                ds.yaml_path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True),
                                        encoding="utf-8")
            fixes.append(dict(image="data.yaml", line="", action="rename_classes",
                              before="names cũ", after=str(cfg["classes"])))
    return fixes
