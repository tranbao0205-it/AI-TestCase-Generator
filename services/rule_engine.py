"""
Rule Engine — DOMAIN RULE ENGINE.
Khác với _FIELD_RULE_TABLE trong ai_service.py (match CỨNG theo TÊN FIELD,
vd "Email"/"Số điện thoại", không quan tâm domain), module này match CỨNG
theo TÊN MODULE trong đúng domain do UI chọn (bank/hospital/school/
recruitment...), đọc thẳng BUSINESS_RULES + TEST_CASES mẫu từ file .md
tương ứng — KHÔNG phụ thuộc semantic search như RAGService (RAG vẫn chạy
song song, không bị thay thế).
Cấu trúc thư mục nguồn kỳ vọng: rag/knowledge/<domain>/*.md
Mỗi file theo format:
    ### MODULE: <tên module>
    **BUSINESS_RULES** ...(nội dung, có thể 1 dòng hoặc nhiều dòng bullet)...
    **TEST_CASES** ...(nội dung, có thể 1 dòng hoặc nhiều dòng bullet)...
    --------------------------------------------------------------------------------
(File mẫu sample_knowledge.md ở thư mục gốc rag/knowledge/ CHỈ để tham
khảo format, KHÔNG phải nguồn thật — không được đọc vào đây.)
"""

import re
import difflib
from pathlib import Path

_MODULE_HEADER_RE = re.compile(r'^#{2,6}\s*MODULE\s*:\s*(.+?)\s*$', re.I | re.M)
_SECTION_RE = re.compile(
    r'^#{2,6}\s*(business\s*rules?|quy\s*tắc\s*nghiệp\s*vụ|validation|'
    r'test\s*cases?|test\s*case\s*bắt\s*buộc|dữ\s*liệu\s*mẫu)\s*:?\s*$',
    re.I | re.M,
)
_BOLD_SECTION_RE = re.compile(
    r'^\s*\*\*(BUSINESS_RULES|BUSINESS RULES|VALIDATION|TEST_CASES|TEST CASES)\*\*\s*$',
    re.I | re.M,
)
_DOMAIN_CACHE: dict[str, dict[str, dict]] = {}

def _resolve_knowledge_dir() -> Path | None:
    """
    Tự dò thư mục rag/knowledge/ — không hardcode parents[N] (đã có bài
    học từ rag_service.py: hardcode parents[1] rất dễ vỡ khi cấu trúc
    project đổi). Thử vài vị trí phổ biến, log rõ chỗ nào tìm thấy.
    """
    candidates = [
        Path(__file__).resolve().parent / "rag" / "knowledge",
        Path(__file__).resolve().parent.parent / "rag" / "knowledge",
        Path.cwd() / "rag" / "knowledge",
    ]
    for c in candidates:
        if c.is_dir():
            return c
    print(
        "[RuleEngine] KHÔNG tìm thấy thư mục rag/knowledge/ ở các vị trí:\n"
        + "\n".join(f"  - {c}" for c in candidates)
    )
    return None
def _parse_domain_file(text: str) -> dict[str, dict]:
    """Parse domain.md/workflows.md theo nhiều biến thể Markdown phổ biến."""
    modules: dict[str, dict] = {}
    parts = _MODULE_HEADER_RE.split(text)
    for i in range(1, len(parts), 2):
        module_name = parts[i].strip()
        chunk = parts[i + 1] if i + 1 < len(parts) else ""

        sections: dict[str, list[str]] = {
            "business_rules": [], "validation": [], "test_cases": [], "sample_data": []
        }
        matches = list(_SECTION_RE.finditer(chunk)) + list(_BOLD_SECTION_RE.finditer(chunk))
        matches.sort(key=lambda m: m.start())
        if matches:
            for idx, match in enumerate(matches):
                title = match.group(1).lower().replace('_', ' ').strip()
                body_start = match.end()
                body_end = matches[idx + 1].start() if idx + 1 < len(matches) else len(chunk)
                body = chunk[body_start:body_end].strip()
                if not body:
                    continue
                if 'business' in title or 'quy tắc' in title:
                    sections['business_rules'].append(body)
                elif 'validation' in title:
                    sections['validation'].append(body)
                elif 'test' in title:
                    sections['test_cases'].append(body)
                elif 'dữ liệu' in title:
                    sections['sample_data'].append(body)
        else:
            body = chunk.strip()
            if body:
                sections['business_rules'].append(body)
        business_rules = '\n'.join(sections['business_rules']).strip()
        validation = '\n'.join(sections['validation']).strip()
        test_cases = '\n'.join(sections['test_cases']).strip()
        sample_data = '\n'.join(sections['sample_data']).strip()
        if not any((business_rules, validation, test_cases, sample_data)):
            continue
        modules[module_name] = {
            'business_rules': business_rules,
            'validation': validation,
            'test_cases': test_cases,
            'sample_data': sample_data,
        }
    return modules
def load_domain_modules(domain: str) -> dict[str, dict]:
    """
    Đọc + parse TẤT CẢ file .md trong rag/knowledge/<domain>/*.md.
    Trả về {tên_module_gốc: {"business_rules": str, "test_cases": str}}.
    Trả về {} nếu domain rỗng, thư mục không tồn tại, hoặc không có file.
    Có cache theo domain trong quá trình chạy.
    """
    if not domain:
        return {}
    if domain in _DOMAIN_CACHE:
        return _DOMAIN_CACHE[domain]

    knowledge_dir = _resolve_knowledge_dir()
    if knowledge_dir is None:
        _DOMAIN_CACHE[domain] = {}
        return {}

    domain_dir = knowledge_dir / domain
    if not domain_dir.is_dir():
        print(f"[RuleEngine] Domain '{domain}' không có thư mục tại {domain_dir}")
        _DOMAIN_CACHE[domain] = {}
        return {}

    md_files = sorted(domain_dir.glob("*.md"))
    if not md_files:
        print(f"[RuleEngine] Domain '{domain}' không có file .md nào trong {domain_dir}")
        _DOMAIN_CACHE[domain] = {}
        return {}

    all_modules: dict[str, dict] = {}
    for f in md_files:
        try:
            text = f.read_text(encoding="utf-8")
        except Exception as exc:
            print(f"[RuleEngine] Lỗi đọc file {f}: {exc}")
            continue
        file_modules = _parse_domain_file(text)
        all_modules.update(file_modules)

    print(
        f"[RuleEngine] Domain '{domain}': đã nạp {len(all_modules)} module "
        f"từ {len(md_files)} file trong {domain_dir}"
    )
    _DOMAIN_CACHE[domain] = all_modules
    return all_modules
def _match_module_names(candidate_names: list[str], search_text: str) -> list[str]:
    """
    So khớp tên module trong file domain với nội dung đang xử lý
    (description/proj/relevant_elements đã gộp thành search_text), dùng
    substring 2 chiều + fuzzy ratio — cùng kỹ thuật với
    coverage_checker.detect_missing_targeted_modules để nhất quán trong
    toàn bộ codebase.
    """
    search_lower = search_text.lower()
    matched = []
    for name in candidate_names:
        name_lower = name.lower().strip()
        if not name_lower:
            continue
        if name_lower in search_lower:
            matched.append(name)
            continue
        for segment in re.split(r'[,.\n;]', search_lower):
            segment = segment.strip()
            if len(segment) < 3:
                continue
            if difflib.SequenceMatcher(None, name_lower, segment).ratio() >= 0.6:
                matched.append(name)
                break
    return matched


def select_domain_rules(
    domain: str,
    description: str,
    proj: str,
    relevant_elements: str,
) -> str:
    """
    Trả về block hint (business rules + TC mẫu) cho ĐÚNG các module khớp
    với domain hiện tại, để nhúng song song với rule_hints
    (_build_rule_engine_hints) và RAG context trong prompt.

    Trả về "" nếu domain rỗng, không tìm thấy file, hoặc không match được
    module nào — để không làm phình prompt vô ích.
    """
    if not domain:
        return ""

    modules = load_domain_modules(domain)
    if not modules:
        return ""

    search_text = " ".join([proj or "", description or "", relevant_elements or ""])
    matched_names = _match_module_names(list(modules.keys()), search_text)
    if not matched_names:
        return ""

    hint_blocks = []
    for name in matched_names:
        content = modules[name]
        block = f'- MODULE "{name}":'
        if content.get("business_rules"):
            block += f'\n  BUSINESS_RULES: {content["business_rules"]}'
        if content.get("validation"):
            block += f'\n  VALIDATION: {content["validation"]}'
        if content.get("test_cases"):
            block += f'\n  TEST_CASES mẫu (chỉ tham khảo khung, KHÔNG copy y nguyên): {content["test_cases"]}'
        if content.get("sample_data"):
            block += f'\n  DỮ LIỆU MẪU: {content["sample_data"]}'
        hint_blocks.append(block)

    return (
        f"\n=== DOMAIN RULE ENGINE ({domain}) — BUSINESS RULES BẮT BUỘC THAM KHẢO ===\n"
        "(Ưu tiên rule dưới đây hơn suy đoán chung. TEST_CASES mẫu chỉ để tham khảo "
        "khung/văn phong, KHÔNG copy y nguyên số liệu/tên riêng.)\n"
        + "\n".join(hint_blocks)
    )
CRUD_COMPACT_RULES: dict[str, dict] = {
    "create": {
        "display_name": "Thêm mới",
        "list_min_cases": 2,
        "list_max_cases": 2,
        "form_min_cases": 4,
        "form_max_cases": 5,
        "list_groups": [
            "open_create_form_success",
            "open_create_form_failure_or_permission",
        ],
        "form_groups": [
            "success",
            "required_missing",
            "invalid_data",
            "duplicate",
            "system_error",
        ],
    },
    "update": {
        "display_name": "Cập nhật",
        "list_min_cases": 2,
        "list_max_cases": 2,
        "form_min_cases": 4,
        "form_max_cases": 5,
        "list_groups": [
            "open_correct_record_success",
            "open_update_form_failure_or_permission",
        ],
        "form_groups": [
            "success",
            "required_missing",
            "invalid_data",
            "not_found",
            "system_error",
        ],
    },
    "delete": {
        "display_name": "Xóa",
        "list_min_cases": 2,
        "list_max_cases": 2,
        "form_min_cases": 4,
        "form_max_cases": 4,
        "list_groups": [
            "open_delete_confirmation_success",
            "open_delete_confirmation_failure_or_permission",
        ],
        "form_groups": [
            "success",
            "cancel",
            "not_found",
            "not_allowed",
        ],
    },
}
CRUD_ACTION_ALIASES: dict[str, str] = {
    "thêm": "create",
    "thêm mới": "create",
    "tạo mới": "create",
    "add": "create",
    "add new": "create",
    "create": "create",
    "insert": "create",

    "sửa": "update",
    "cập nhật": "update",
    "chỉnh sửa": "update",
    "edit": "update",
    "update": "update",
    "modify": "update",

    "xóa": "delete",
    "xoá": "delete",
    "delete": "delete",
    "remove": "delete",
}

CRUD_MERGE_RULES = """
=== QUY TẮC CRUD GỌN THEO NGHIỆP VỤ (phong cách tài liệu kiểm định WEB2501) ===
Mục tiêu: SINH ÍT TESTCASE HƠN, mỗi testcase đại diện đúng 1 Ý NGHIỆP VỤ,
không tách theo từng field/từng loại lỗi kỹ thuật. Tiêu đề testcase NGẮN
GỌN (vd "Thêm mới thành công", "Thiếu dữ liệu bắt buộc", "Dữ liệu không
hợp lệ", "Trùng dữ liệu"), KHÔNG viết tiêu đề dài kiểu "Thêm mới khi thiếu
trường Email".
BẮT BUỘC GỘP các biến thể sau vào ĐÚNG 1 testcase duy nhất (liệt kê từng
trường hợp trong test_data, KHÔNG tách thành nhiều testcase riêng):
- Mọi trường bắt buộc bị bỏ trống / chỉ nhập khoảng trắng => 1 TC
  "Thiếu dữ liệu bắt buộc".
- Mọi lỗi sai định dạng + vượt giới hạn/độ dài/biên + vi phạm ràng buộc
  nghiệp vụ (không phải trùng dữ liệu) => 1 TC "Dữ liệu không hợp lệ".
- Không sinh riêng TC cho: click/nhấn nút nhiều lần liên tiếp, refresh,
  F5, back browser, khoảng trắng đầu/cuối, ký tự đặc biệt, XSS, SQL
  Injection — trừ khi ảnh/tài liệu đặc tả mô tả rõ đây là yêu cầu nghiệp
  vụ bắt buộc phải kiểm tra.
KHÔNG ĐƯỢC GỘP (luôn giữ TC riêng):
- Thành công với thất bại.
- Trùng dữ liệu với "Dữ liệu không hợp lệ" (thông báo và cách xử lý khác
  bản chất — trùng dữ liệu là do đã tồn tại, không phải sai định dạng).
- Xác nhận với hủy/đóng popup.
- Lỗi hệ thống/mất kết nối chỉ sinh THÊM (không bắt buộc) khi có bằng
  chứng rõ ràng về xử lý lỗi server trong ảnh/mô tả.
FIELD BẮT BUỘC:
- Dấu * màu đỏ, (*), thuộc tính required hoặc chữ "bắt buộc" => field bắt buộc.
- Field không có bằng chứng bắt buộc thì KHÔNG được tự suy đoán.
PHÂN BIỆT ACTION:
- Icon Cập nhật ngoài danh sách chỉ kiểm tra mở đúng form và đúng dữ liệu bản ghi.
- Nút Cập nhật trong form mới kiểm tra lưu thay đổi, validation và nghiệp vụ.
- Icon Xóa ngoài danh sách chỉ kiểm tra mở popup xác nhận đúng đối tượng.
- Nút xác nhận Xóa trong popup mới kiểm tra thực hiện xóa và ràng buộc.
- Input/Dropdown/Datepicker không tạo module riêng; validation thuộc module Thêm mới/Cập nhật.
""".strip()
CRUD_LIST_ONLY_RULE = """
=== CRUD KHI CHỈ THẤY MÀN HÌNH DANH SÁCH ===
Ảnh hiện tại chỉ cung cấp icon/nút thao tác trên danh sách, chưa cung cấp form/popup chi tiết.
BẮT BUỘC:
- Chỉ sinh ĐÚNG 2 testcase cho module CRUD đang xét:
  1. Thành công: click icon/nút và mở đúng form hoặc popup của đúng bản ghi/đối tượng.
  2. Không thành công: không mở được do không có quyền, bản ghi không tồn tại hoặc lỗi phù hợp.
- KHÔNG suy đoán tên field bên trong form.
- KHÔNG sinh Required, Format, Boundary, Duplicate, XSS/SQL Injection hoặc dependency field.
- KHÔNG sinh testcase lưu/cập nhật/xóa dữ liệu thật khi chưa thấy nút xác nhận hoặc form.
- Khi có ảnh form/popup được gửi tiếp bằng workflow, mới mở rộng module bằng TC chi tiết.
""".strip()
CRUD_FORM_RULE = """
=== CRUD KHI ĐÃ THẤY FORM/POPUP CHI TIẾT ===
Ảnh hiện tại có bằng chứng form/popup chi tiết: field nhập liệu, label, dropdown,
nút lưu/cập nhật/xác nhận hoặc tiêu đề popup.
BẮT BUỘC:
- Mở rộng module CRUD hiện có; không xóa testcase mở form đã sinh ở bước danh sách.
- Chỉ sinh validation cho field THỰC SỰ xuất hiện trong ảnh/mô tả.
- Field có dấu * / (*) / required / "bắt buộc" là trường bắt buộc.
- Không tự coi field không có dấu * là bắt buộc.
- Gộp các trường cùng nhóm validation khi cùng bản chất kết quả.
- Các button phụ như Sinh mã, Hủy bỏ, Đóng popup, Thêm mới và tiếp tục
  vẫn có thể là module độc lập nếu thật sự xuất hiện.
""".strip()


def _normalize_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())  
def normalize_crud_action(action: str | None) -> str:
    value = _normalize_text(action)
    if value in CRUD_ACTION_ALIASES:
        return CRUD_ACTION_ALIASES[value]
    if value.startswith(("thêm mới", "tạo mới")):
        return "create"
    if value.startswith(("cập nhật", "chỉnh sửa", "sửa")):
        return "update"
    if value.startswith(("xóa", "xoá")):
        return "delete"
    return ""


def detect_crud_action(search_text: str) -> str:
    """Nhận diện action CRUD từ mô tả + tên màn hình + UI đã scan."""
    text = _normalize_text(search_text)
    update_markers = (
        r"\b(cập nhật|chỉnh sửa|sửa thông tin|edit|update)\b",
        r"(tiêu đề|title|popup|modal).{0,40}\b(cập nhật|chỉnh sửa)\b",
    )
    create_markers = (
        r"\b(thêm mới|tạo mới|add new|create)\b",
        r"(tiêu đề|title|popup|modal).{0,40}\b(thêm mới|tạo mới)\b",
    )
    delete_markers = (
        r"\b(xác nhận xóa|xác nhận xoá|delete confirmation)\b",
        r"\b(xóa|xoá|delete|remove)\b",
    )

    for pattern in update_markers:
        if re.search(pattern, text, re.I):
            return "update"
    for pattern in create_markers:
        if re.search(pattern, text, re.I):
            return "create"
    for pattern in delete_markers:
        if re.search(pattern, text, re.I):
            return "delete"
    return ""


def detect_required_fields(search_text: str) -> list[str]:
    """
    Trích field bắt buộc từ output scan/OCR.

    Hỗ trợ các dạng:
    - Tên nhà cung cấp * | input
    - Tên nhà cung cấp (*) | input
    - Tên nhà cung cấp | input | required
    - Tên nhà cung cấp | bắt buộc
    """
    required_fields: list[str] = []
    seen: set[str] = set()

    for raw_line in str(search_text or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue

        lower = line.lower()
        is_required = (
            "*" in line
            or "(*)" in line
            or re.search(r"(?<!\w)required(?!\w)", lower) is not None
            or "bắt buộc" in lower
        )
        if not is_required:
            continue
        name = line.split("|", 1)[0]
        name = re.sub(r"^[\-\+\•\s]+", "", name)
        name = name.replace("(*)", "").replace("*", "").strip(" :-")
        if not name:
            continue

        key = _normalize_text(name)
        if key and key not in seen:
            seen.add(key)
            required_fields.append(name)

    return required_fields


def _has_form_fields(text: str) -> bool:
    """True khi scan có bằng chứng field nhập liệu thật."""
    raw = str(text or "")
    lower = raw.lower()
    typed_field_pattern = re.compile(
        r"(?im)^\s*[-+•]?\s*[^|\n]{1,100}\|\s*"
        r"(input|textarea|dropdown|select|combobox|datepicker|date-picker|"
        r"radio|checkbox|file-upload|upload)\b"
    )
    if typed_field_pattern.search(raw):
        return True

    field_metadata = (
        "placeholder=",
        "required=true",
        "readonly=true",
        "field:",
        "trường nhập",
        "ô nhập",
        "ô điền",
        "ô chọn",
        "ô ngày",
        "ô radio",
        "ô checkbox",
        "ô tải file",
        "ô upload",
        "ô combobox",
        "ô select",
        "ô dropdown"
        "ô nhập liệu",
    )
    return any(token in lower for token in field_metadata)


def _has_modal_or_form_title(text: str, action: str) -> bool:
    lower = str(text or "").lower()
    title_tokens = ("popup", "modal", "form", "dialog", "tiêu đề", "title")
    if not any(token in lower for token in title_tokens):
        return False

    action_words = {
        "create": ("thêm mới", "tạo mới"),
        "update": ("cập nhật", "chỉnh sửa"),
        "delete": ("xóa", "xoá", "xác nhận xóa", "xác nhận xoá"),
    }.get(action, ())
    return any(word in lower for word in action_words)


def _has_submit_or_confirm_button(text: str, action: str) -> bool:
    raw = str(text or "")
    patterns = {
        "create": (
            r"(?im)^\s*[-+•]?\s*(thêm mới|lưu|tạo mới)\s*\|\s*(button|submit)",
            r"(?im)^\s*[-+•]?\s*thêm mới và tiếp tục\s*\|\s*button",
        ),
        "update": (
            r"(?im)^\s*[-+•]?\s*(cập nhật|lưu thay đổi|lưu)\s*\|\s*(button|submit)",
        ),
        "delete": (
            r"(?im)^\s*[-+•]?\s*(xác nhận xóa|xác nhận xoá|xóa|xoá|đồng ý)\s*\|\s*(button|submit)",
        ),
    }
    return any(re.search(pattern, raw, re.I | re.M) for pattern in patterns.get(action, ()))


def _looks_like_delete_confirmation(text: str) -> bool:
    lower = _normalize_text(text)
    confirmation_phrases = (
        "bạn có chắc",
        "có chắc chắn",
        "xác nhận xóa",
        "xác nhận xoá",
        "không thể hoàn tác",
        "dữ liệu sẽ bị xóa",
        "dữ liệu sẽ bị xoá",
    )
    return any(phrase in lower for phrase in confirmation_phrases)


def detect_crud_context(
    search_text: str,
    action: str | None = None,
    previous_modules: dict | list | tuple | set | None = None,
) -> dict:
    """
    Nhận diện ngữ cảnh CRUD dùng chung cho Rule + Workflow.

    Kết quả:
    {
        "action": "update",
        "screen_type": "list" | "form" | "confirm_popup" | "unknown",
        "has_form_fields": bool,
        "required_fields": [...],
        "parent_module": "Cập nhật",
        "parent_exists": bool,
        "confidence": float,
    }
    """
    canonical = normalize_crud_action(action) or detect_crud_action(search_text)
    if not canonical:
        return {
            "action": "",
            "screen_type": "unknown",
            "has_form_fields": False,
            "required_fields": [],
            "parent_module": None,
            "parent_exists": False,
            "confidence": 0.0,
        }

    rule = CRUD_COMPACT_RULES[canonical]
    display_name = rule["display_name"]
    has_fields = _has_form_fields(search_text)
    has_form_title = _has_modal_or_form_title(search_text, canonical)
    has_submit = _has_submit_or_confirm_button(search_text, canonical)
    delete_confirm = canonical == "delete" and _looks_like_delete_confirmation(search_text)

    if delete_confirm:
        screen_type = "confirm_popup"
        confidence = 1.0
    elif has_fields or (has_form_title and has_submit):
        screen_type = "form"
        confidence = 0.95
    else:
        screen_type = "list"
        confidence = 0.85

    if isinstance(previous_modules, dict):
        previous_names = list(previous_modules.keys())
    elif isinstance(previous_modules, (list, tuple, set)):
        previous_names = list(previous_modules)
    else:
        previous_names = []

    aliases_by_action = {
        "create": {"thêm", "thêm mới", "tạo mới"},
        "update": {"sửa", "cập nhật", "chỉnh sửa"},
        "delete": {"xóa", "xoá"},
    }
    aliases = aliases_by_action[canonical]
    parent_exists = any(
        _normalize_text(name) in aliases
        or any(alias in _normalize_text(name) for alias in aliases)
        for name in previous_names
    )

    return {
        "action": canonical,
        "screen_type": screen_type,
        "has_form_fields": has_fields,
        "required_fields": detect_required_fields(search_text),
        "parent_module": display_name,
        "parent_exists": parent_exists,
        "confidence": confidence,
    }


def get_crud_compact_rules(
    action: str | None = None,
    screen_type: str | None = None,
) -> dict:
    canonical = normalize_crud_action(action)
    if not canonical:
        return CRUD_COMPACT_RULES if action is None else {}

    base = dict(CRUD_COMPACT_RULES.get(canonical, {}))
    if not base:
        return {}

    normalized_screen = _normalize_text(screen_type)
    is_detail = normalized_screen in {"form", "confirm_popup"}

    base["min_cases"] = (
        base["form_min_cases"] if is_detail else base["list_min_cases"]
    )
    base["max_cases"] = (
        base["form_max_cases"] if is_detail else base["list_max_cases"]
    )
    base["groups"] = list(
        base["form_groups"] if is_detail else base["list_groups"]
    )
    base["screen_type"] = normalized_screen or "list"
    return base


def build_crud_rule_prompt(
    action: str | None = None,
    search_text: str = "",
    previous_modules: dict | list | tuple | set | None = None,
) -> str:
    """
    Tạo block prompt CRUD + Workflow.

    Tương thích code cũ:
        build_crud_rule_prompt(action)
        build_crud_rule_prompt(action, search_text)

    Có thể truyền previous_modules để biết module CRUD đã có ở lượt trước hay chưa.
    """
    context = detect_crud_context(
        search_text=search_text,
        action=action,
        previous_modules=previous_modules,
    )
    canonical = context["action"]
    if not canonical:
        return ""

    rule = get_crud_compact_rules(canonical, context["screen_type"])
    group_lines = "\n".join(f"- {group}" for group in rule["groups"])

    required_fields = context.get("required_fields") or []
    required_block = ""
    if required_fields:
        required_block = (
            "\nField bắt buộc phát hiện được từ ảnh:\n"
            + "\n".join(f"- {field}" for field in required_fields)
            + "\nChỉ các field trên được khẳng định là bắt buộc theo bằng chứng hiện tại."
        )

    if context["screen_type"] == "list":
        context_rule = CRUD_LIST_ONLY_RULE
        workflow_note = (
            "\nĐây là bước DANH SÁCH/ICON. Không được sinh trước dữ liệu của form chưa thấy."
        )
    else:
        context_rule = CRUD_FORM_RULE
        workflow_note = (
            "\nĐây là bước FORM/POPUP chi tiết. "
            + (
                f'Module "{context["parent_module"]}" đã tồn tại ở workflow trước; '
                "hãy mở rộng và giữ testcase cũ."
                if context.get("parent_exists")
                else f'Sinh TC chi tiết cho module "{context["parent_module"]}" '
                     "dựa đúng field/action nhìn thấy."
            )
        )

    return (
        f"\n{CRUD_MERGE_RULES}\n\n"
        f"{context_rule}\n\n"
        f"=== NGỮ CẢNH CRUD ĐÃ NHẬN DIỆN ===\n"
        f"- Action: {canonical}\n"
        f"- Module: {rule['display_name']}\n"
        f"- Loại màn hình: {context['screen_type']}\n"
        f"- Có field form: {context['has_form_fields']}\n"
        f"- Độ tin cậy: {context['confidence']:.2f}\n"
        f"{workflow_note}\n"
        f"Số lượng mục tiêu: {rule['min_cases']}–{rule['max_cases']} testcase.\n"
        f"Các nhóm nghiệp vụ áp dụng:\n{group_lines}"
        f"{required_block}\n"
    )