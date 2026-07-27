"""
Coverage Checker — bản 1 + Coverage Report.
Phạm vi CHÍNH của bản này: kiểm tra xem có MODULE nào bị AI bỏ sót
so với những gì thực sự tồn tại (trong ảnh đã OCR, hoặc trong mô tả
text người dùng liệt kê) hay không — và tổng hợp lại thành 1
COVERAGE REPORT (số module áp dụng/đã có/thiếu + % coverage Ở MỨC
MODULE) để hiển thị cho người dùng.
KHÔNG thuộc phạm vi bản 1 (để dành cho bản 2/3 sau này, khi có Rule
Engine/RAG domain cung cấp business rule chuẩn để đối chiếu):
- Số lượng TC trong từng module (vẫn do _validate_testcase_count đảm nhiệm).
- Loại kỹ thuật kiểm thử (Positive/Negative/Boundary/Security...).
- Tính đúng nghiệp vụ của TC theo Business Rule.
- % coverage Ở MỨC LOẠI KỊCH BẢN/TC (coverage_report bản 1 CHỈ tính %
  Ở MỨC MODULE — có/thiếu module, không phải có/thiếu TC).
Được tách ra từ ai_service.py (logic gốc: _detect_missing_modules /
_detect_missing_targeted_modules) để dễ maintain/test độc lập và làm
nền cho Rule Engine domain gắn vào sau.
"""

import re
import difflib
_STANDARD_CHECK_LABELS = [
    'Thêm mới', 'Quay lại', 'Cập nhật', 'Xóa', 'Phân trang', 'Tìm (nút tìm kiếm)',
]

def _evaluate_standard_checks(scanned: str, modules: dict) -> list[dict]:
    """
    Helper DÙNG CHUNG cho detect_missing_modules() và build_coverage_report()
    — tránh viết lặp 2 lần cùng 1 logic nhận diện (bài học đã ghi nhận:
    logic trùng lặp giữa 2 hàm rất dễ bị lệch nhau khi sửa sau này).
    Trả về list các dict {"label": str, "applicable": bool, "covered": bool}
    cho ĐÚNG 6 check chuẩn (Thêm mới/Quay lại/Cập nhật/Xóa/Phân trang/Tìm).
    "applicable" = chức năng này CÓ xuất hiện trong ảnh (scanned) không.
    "covered" = ĐÃ có module tương ứng trong kết quả AI sinh ra chưa.
    """
    if not scanned or not isinstance(modules, dict):
        return [
            {"label": label, "applicable": False, "covered": False}
            for label in _STANDARD_CHECK_LABELS
        ]
    scanned_lower = scanned.lower()
    mod_names_lower = [m.strip().lower() for m in modules.keys()]
    existing_blob = ' '.join(mod_names_lower)
    def _has_any(*keywords: str) -> bool:
        return any(kw in existing_blob for kw in keywords)
    checks = []
    applicable = 'thêm mới' in scanned_lower
    checks.append({
        "label": "Thêm mới",
        "applicable": applicable,
        "covered": _has_any('thêm') if applicable else False,
    })
    applicable = 'quay lại' in scanned_lower
    checks.append({
        "label": "Quay lại",
        "applicable": applicable,
        "covered": _has_any('quay lại') if applicable else False,
    })
    applicable = bool('cập nhật' in scanned_lower or re.search(r'-\s*sửa\b', scanned_lower))
    checks.append({
        "label": "Cập nhật",
        "applicable": applicable,
        "covered": _has_any('cập nhật', 'sửa') if applicable else False,
    })
    applicable = bool('xóa' in scanned_lower or 'xoá' in scanned_lower)
    checks.append({
        "label": "Xóa",
        "applicable": applicable,
        "covered": _has_any('xóa', 'xoá') if applicable else False,
    })
    applicable = 'phân trang' in scanned_lower
    checks.append({
        "label": "Phân trang",
        "applicable": applicable,
        "covered": _has_any('trang') if applicable else False,
    })
    applicable = bool(
        re.search(r'-\s*tìm\s*\|', scanned_lower) or re.search(r'\bnút tìm\b', scanned_lower)
    )
    checks.append({
        "label": "Tìm (nút tìm kiếm)",
        "applicable": applicable,
        "covered": (
            any('tìm' in n and 'kiếm' not in n for n in mod_names_lower)
            if applicable else False
        ),
    })

    return checks
def detect_missing_modules(scanned: str, modules: dict) -> list[str]:
    """
    Dùng khi CÓ ẢNH (có kết quả OCR trong `scanned`).
    Phát hiện chức năng UI xuất hiện trong ảnh (scanned) nhưng KHÔNG có
    module tương ứng nào trong kết quả AI đã sinh.
    LƯU Ý QUAN TRỌNG: "Tìm kiếm theo [X]" (ô lọc) và "Tìm" (nút) là 2
    chức năng KHÁC NHAU. Module "Tìm kiếm theo mã hoặc kho" đã chứa
    chữ "tìm" trong tên, nên nếu chỉ check substring "tìm" thì sẽ luôn
    coi nút "Tìm" là "đã có" dù chưa hề có module riêng cho nó — đây là
    lỗi đã xảy ra thực tế, sửa bằng cách check riêng case "tìm" KHÔNG
    kèm "kiếm" trong tên module.
    Args:
        scanned: Kết quả OCR (mỗi dòng element bắt đầu bằng "-").
        modules: Dict {tên_module: [test_case, ...]} AI đã sinh ra.
    Returns:
        Danh sách tên module (theo cách gọi chuẩn hoá) bị thiếu.
    """
    checks = _evaluate_standard_checks(scanned, modules)
    return [c["label"] for c in checks if c["applicable"] and not c["covered"]]
def detect_missing_targeted_modules(description: str, modules: dict) -> list[str]:
    """
    Dùng khi KHÔNG CÓ ẢNH (mô tả text thuần) — vì khi đó `scanned` luôn
    rỗng nên detect_missing_modules không detect được gì.
    So khớp từng cụm chức năng user liệt kê trong description (tách
    theo dấu phẩy/xuống dòng, bỏ phần role đứng trước dấu ":") với tên
    module đã sinh ra, bằng substring 2 chiều + fuzzy ratio (difflib).
    Cụm nào không khớp module nào → coi là bị AI bỏ sót.
    Args:
        description: Mô tả text người dùng nhập (liệt kê chức năng).
        modules: Dict {tên_module: [test_case, ...]} AI đã sinh ra.
    Returns:
        Danh sách cụm mô tả chức năng bị thiếu (nguyên văn từ description).
    """
    _matched, missing = _match_targeted_phrases(description, modules)
    return missing
def _match_targeted_phrases(description: str, modules: dict) -> tuple[list[str], list[str]]:
    """
    Helper DÙNG CHUNG cho detect_missing_targeted_modules() và
    build_coverage_report() — tách phrase hợp lệ từ description rồi phân
    loại matched/missing, tránh lặp logic parse 2 lần.
    Returns:
        (matched_phrases, missing_phrases) — cả 2 đều là cụm nguyên văn
        từ description (đã strip), KHÔNG gồm các cụm bị lọc bởi stop_phrases
        hoặc quá ngắn (<3 ký tự).
    """
    if not description or not isinstance(modules, dict):
        return [], []
    valid_modules = {
        m: tcs for m, tcs in modules.items()
        if isinstance(tcs, list) and tcs
    }
    module_names_lower = [m.strip().lower() for m in valid_modules.keys()]
    desc = description
    if ':' in desc:
        desc = desc.rsplit(':', 1)[-1]
    phrases = [p.strip() for p in re.split(r'[,\n;]', desc) if p.strip()]
    stop_phrases = {
        'admin', 'employee', 'user', 'customer', 'hr', 'khách hàng',
        'nhân viên', 'quản trị viên', 'người dùng',
    }
    matched: list[str] = []
    missing: list[str] = []
    for phrase in phrases:
        p_lower = phrase.lower().strip()
        if len(p_lower) < 3 or p_lower in stop_phrases:
            continue
        if not module_names_lower:
            missing.append(phrase)
            continue
        is_matched = any(
            p_lower in m_lower or m_lower in p_lower
            or difflib.SequenceMatcher(None, p_lower, m_lower).ratio() >= 0.55
            for m_lower in module_names_lower
        )
        (matched if is_matched else missing).append(phrase)
    return matched, missing


def build_coverage_report(
    modules: dict,
    scanned: str | None = None,
    description: str | None = None,
    has_image: bool = True,
) -> dict:
    """
    Tổng hợp Coverage Report Ở MỨC MODULE (KHÔNG phải % TC/loại kịch bản
    — xem giới hạn phạm vi ở docstring đầu file).
    Dùng ĐÚNG 1 trong 2 nguồn theo has_image (giống cách _enforce_min_coverage
    trong ai_service.py chọn nhánh):
    - has_image=True  → dùng `scanned` (kết quả OCR), check 6 chức năng
    chuẩn (Thêm mới/Quay lại/Cập nhật/Xóa/Phân trang/Tìm).
    - has_image=False → dùng `description` (text thuần), check từng cụm
    chức năng user liệt kê.
    Args:
        modules: Dict {tên_module: [test_case, ...]} AI đã sinh ra.
        scanned: Kết quả OCR — bắt buộc nếu has_image=True.
        description: Mô tả text người dùng — bắt buộc nếu has_image=False.
        has_image: Chọn nguồn đối chiếu (xem trên).
    Returns:
        {
            "total_expected": int,      
            "total_covered": int,       
            "total_missing": int,
            "coverage_percent": float,  
            "covered_items": list[str],
            "missing_items": list[str],
            "source": "image" | "text",
        }
    """
    modules = modules if isinstance(modules, dict) else {}
    if has_image:
        checks = _evaluate_standard_checks(scanned or '', modules)
        applicable_checks = [c for c in checks if c["applicable"]]
        covered_items = [c["label"] for c in applicable_checks if c["covered"]]
        missing_items = [c["label"] for c in applicable_checks if not c["covered"]]
        source = "image"
    else:
        covered_items, missing_items = _match_targeted_phrases(description or '', modules)
        source = "text"
    total_expected = len(covered_items) + len(missing_items)
    total_covered = len(covered_items)
    coverage_percent = (
        round(total_covered / total_expected * 100, 1) if total_expected else 100.0
    )
    return {
        "total_expected": total_expected,
        "total_covered": total_covered,
        "total_missing": len(missing_items),
        "coverage_percent": coverage_percent,
        "covered_items": covered_items,
        "missing_items": missing_items,
        "source": source,
    }