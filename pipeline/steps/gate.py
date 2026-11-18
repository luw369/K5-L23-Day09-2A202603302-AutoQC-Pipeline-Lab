"""BƯỚC 4 — Cửa chặn: quyết định Release / Hold / Rework.   ★

Test:  pytest tests/test_gate.py -q

Cây quyết định Day 07 (slide Day 09: "Lỗi bắt buộc chặn pipeline; lỗi cảnh báo chuyển người xem"):

  còn ≥ 1 lỗi bắt buộc (severity ERROR)                          -> "Rework"
  không còn lỗi bắt buộc, nhưng tỉ lệ ẢNH còn cảnh báo
      >= cfg["gate"]["warn_ratio_hold"]                          -> "Hold"
  còn lại                                                        -> "Release"

Tỉ lệ cảnh báo = (số ẢNH khác nhau có ≥ 1 cảnh báo) / (tổng số ảnh).  Chú ý:
- chỉ đếm issue có `image` nằm trong `image_stems` (bỏ "<dataset>", "data.yaml");
- bỏ qua ảnh nằm trong `reviewed` (người đã xem, cảnh báo của ảnh đó coi như đã xử lý) — nhưng LỖI BẮT BUỘC thì không bao giờ được bỏ qua;
- mẫu số là số ảnh, không phải số issue.

Trả về dict: decision, n_errors, n_warn_images, n_images, warn_ratio (làm tròn 4 chữ số), reasons (list[str], giải thích bằng tiếng Việt, có số liệu).
"""
from ..common import ERROR, WARN  # noqa: F401


def decide(issues, image_stems, cfg, reviewed=frozenset()):
    stems = set(image_stems)
    n_errors = sum(i.severity == ERROR for i in issues)
    if n_errors:
        return dict(decision="Rework", n_errors=n_errors, n_warn_images=0,
                    n_images=len(stems), warn_ratio=0.0,
                    reasons=[f"Còn {n_errors} lỗi bắt buộc; phải sửa trước khi xuất"])

    warn_images = {
        i.image for i in issues
        if i.severity == WARN and i.image in stems and i.image not in reviewed
    }
    n_images = len(stems)
    warn_ratio = round(len(warn_images) / n_images, 4) if n_images else 0.0
    threshold = float(cfg["gate"]["warn_ratio_hold"])
    if warn_ratio >= threshold:
        reasons = [f"Tỉ lệ ảnh có cảnh báo {len(warn_images)}/{n_images} = {warn_ratio:.4f}"
                   f" đạt ngưỡng Hold {threshold:.4f}"]
        decision = "Hold"
    else:
        reasons = [f"Tỉ lệ ảnh có cảnh báo {len(warn_images)}/{n_images} = {warn_ratio:.4f}"
                   f" dưới ngưỡng Hold {threshold:.4f}"]
        decision = "Release"
    return dict(decision=decision, n_errors=n_errors,
                n_warn_images=len(warn_images), n_images=n_images,
                warn_ratio=warn_ratio, reasons=reasons)
