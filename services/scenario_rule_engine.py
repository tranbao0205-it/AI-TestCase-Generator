"""
Scenario Rule Engine — TEMPLATE ENGINE TẬP TRUNG cho các chức năng phổ biến
có kịch bản kiểm thử CHUẨN, DÙNG CHUNG cho mọi website/nghiệp vụ (Đăng nhập,
Xem danh sách, Xem chi tiết, Xuất Excel/Word, In, Lưu, Hủy, Đóng popup,
Quay lại...).

MỤC TIÊU (theo yêu cầu cố định hoá template):
- Một nơi DUY NHẤT giữ nội dung fixed template — SYSTEM_PROMPT_FULL và
  SYSTEM_PROMPT_TARGETED trong ai_service.py KHÔNG được chép lại nội dung
  này, chỉ tham chiếu qua get_fixed_template()/replace_generated_cases_with_template().
- TARGETED và FULL PHẢI gọi CHUNG 1 hàm này nên luôn ra cùng 1 kết quả.
- Khi phát hiện chức năng đã có template cố định: LOẠI BỎ hoàn toàn TC do
  AI tự sinh cho chức năng đó và THAY bằng đúng bộ template tương ứng —
  không giữ lại câu chữ AI tự diễn đạt, không bị Coverage Checker chèn
  thêm lệch hướng (vì override này chạy SAU CÙNG, ngay trước bước re-index
  TC ID trong ai_service._normalize_test_cases).

GHI CHÚ PHẠM VI ÁP DỤNG (quan trọng — tránh regression):
- Các chức năng CRUD "Thêm mới", "Cập nhật", "Xóa", "Tìm kiếm", "Tìm",
  "Phân trang" đã có pipeline riêng RẤT chi tiết trong ai_service.py +
  rule_engine.py (đọc field thật từ ảnh/OCR, phân biệt list-only vs
  form/popup, required-field thật, CRUD_COMPACT_RULES theo domain...).
  Để KHÔNG làm vỡ pipeline đó, các canonical này VẪN được định nghĩa đầy
  đủ trong FUNCTION_KNOWLEDGE bên dưới (đúng yêu cầu "một nơi quản lý tập
  trung"), nhưng ai_service.py mặc định KHÔNG đưa chúng vào tập
  `enforced_canonicals` khi gọi replace_generated_cases_with_template().
  Muốn bật override tổng quát cho cả nhóm CRUD, chỉ cần thêm canonical
  tương ứng vào tập đó — không cần sửa gì trong module này.
- "Quay lại" LUÔN được enforce (đây là chức năng gốc của yêu cầu ban đầu):
  không gộp thành công/không thành công, luôn đúng 4 TC cố định.
- "Sinh mã", "Hủy", "Đóng popup" là các hành động popup — theo checklist
  WEB2519 mỗi hành động này PHẢI có đúng 4 TC cố định (không phải 2).
====================================================================
GHI CHÚ REFACTOR (không đổi API, không đổi output, không đổi workflow)
====================================================================
Bản cũ gộp TẤT CẢ chức năng vào 1 dict khổng lồ `FIXED_TEMPLATES`. Bản
này tách mỗi chức năng thành 1 hằng số `<TEN>_SCENARIOS` riêng (dễ tìm,
dễ diff khi sửa 1 chức năng, không phải kéo qua cả nghìn dòng), rồi gộp
lại DUY NHẤT MỘT LẦN vào `FUNCTION_KNOWLEDGE = {canonical: SCENARIOS}`.

`FIXED_TEMPLATES` vẫn được giữ lại như một ALIAS trỏ tới đúng
`FUNCTION_KNOWLEDGE` (cùng 1 object) — phòng trường hợp có code khác
(ngoài ai_service.py) đang import trực tiếp tên cũ này; giá trị và hành
vi hoàn toàn không đổi.

Muốn thêm 1 chức năng mới, làm đúng 2 bước, KHÔNG cần sửa gì khác:
    1. Khai báo XXX_SCENARIOS = [ {module, title, scenario,
       expected_result, test_type}, ... ]
    2. Thêm dòng "canonical_key": XXX_SCENARIOS vào FUNCTION_KNOWLEDGE

Nếu chức năng mới cần nhận diện tên gọi khác nhau (đồng nghĩa), thêm
alias vào normalize_function_name() như cũ.
"""

from __future__ import annotations

import re
def _norm(value: str | None) -> str:
    """Lowercase, gộp khoảng trắng, KHÔNG bỏ dấu (giữ tiếng Việt có dấu để
    match chính xác các cụm như "quay lại" mà không nhầm "trang trước")."""
    text = str(value or "").strip().lower()
    text = re.sub(r"\s+", " ", text)
    return text


def _strip_ui_prefix(text: str) -> str:
    """Bỏ tiền tố UI kỹ thuật (icon còn sót, "nút", "icon", "biểu tượng",
    "button") để so khớp đúng PHẦN TÊN THẬT của chức năng.
    VD: "← Quay lại" -> "quay lại"; "Nút Quay lại" -> "quay lại";
        "icon Xem chi tiết" -> "xem chi tiết".

    BUG ĐÃ SỬA: bản cũ gộp chung 1 regex bóc icon với nhóm ký tự
    "[...xX...]" ở đầu chuỗi để bóc icon nút đóng dạng "x"/"X", nhưng vì
    KHÔNG có ràng buộc "x/X phải đứng ĐỘC LẬP", nó cũng cắt luôn chữ
    "x"/"X" đầu của các từ THẬT như "Xuất Excel", "Xóa", "Xem chi tiết" —
    khiến "Xuất Excel" bị cắt còn "uất Excel" (không match canonical
    xuat_file), "Xóa"->"óa" (không match "xoa"), "Xem"->"em" (không match
    "xem_chi_tiet"). Giờ tách riêng: bước 1 chỉ bóc icon mũi tên/tick/dấu
    nhân (không gồm x/X); bước 2 chỉ bóc "x"/"X" khi nó đứng ĐỘC LẬP (theo
    sau là khoảng trắng hoặc hết chuỗi — tức đúng là icon nút đóng, không
    phải chữ cái đầu của từ khác).

    FIX (refactor lần này): bản trước đó bị thiếu biến trả về ("return"
    trơn, thiếu "t") khiến hàm này LUÔN trả về None, kéo theo
    normalize_function_name() LUÔN trả về None cho MỌI tên module — toàn
    bộ cơ chế override fixed-template bị vô hiệu hóa âm thầm. Đã khôi
    phục "return t" đúng như mô tả docstring ở trên.
    """
    t = text
    for _ in range(3):
        before = t
        t = re.sub(r"^[\-\+←→✓✔✗×]+\s*", "", t).strip()
        t = re.sub(r"^[xX](?=\s|$)", "", t).strip()
        t = re.sub(r"^(nút|button|icon|biểu tượng|btn)\s+", "", t).strip()
        if t == before:
            break
    return t


def normalize_function_name(module_name: str) -> str | None:
    """
    Trả về canonical key nếu `module_name` khớp synonym của 1 trong các
    chức năng đã có fixed template, ngược lại trả về None (chức năng không
    thuộc phạm vi template hoá — AI sinh tự do như bình thường).
    Đồng thời TRÁNH nhầm các hành động rời rạc khác hành động chính (theo
    yêu cầu): "hủy", "đóng popup", "trang trước" (điều hướng phân trang) sẽ
    KHÔNG khớp nhầm vào "quay lại"; "tìm" và "tìm kiếm" là 2 canonical
    tách biệt, không gộp.
    """
    raw = _norm(module_name)
    if not raw:
        return None
    n = _strip_ui_prefix(raw)
    if not n:
        return None
    if "quay lại" in n or "quay lai" in n or n == "back" or n == "trở về" or "trở về" in n:
        return "quay_lai"
    if "đăng nhập" in n or n in {"login", "sign in", "dang nhap"}:
        return "dang_nhap"
    if "đăng ký" in n or n in {"dang ky", "register", "sign up", "signup", "tạo tài khoản"}:
        return "dang_ky"
    if "đăng xuất" in n or n in {"dang xuat", "logout", "sign out", "log out"}:
        return "dang_xuat"
    if "quên mật khẩu" in n or "quen mat khau" in n or n in {"forgot password", "forgotten password"}:
        return "quen_mat_khau"
    if (
        "đổi mật khẩu" in n or "thay đổi mật khẩu" in n or "doi mat khau" in n
        or n in {"change password", "reset password"}
    ):
        return "doi_mat_khau"
    if "tiếp tục" not in n and (
        "thêm mới" in n or "tạo mới" in n or n in {"thêm", "create", "add new", "add", "insert", "tạo"}
    ):
        return "them_moi"
    if n.startswith(("cập nhật", "chỉnh sửa")) or n in {"sửa", "update", "edit", "modify"}:
        return "cap_nhat"
    if n.startswith(("xóa", "xoá")) or n in {"delete", "remove"}:
        return "xoa"
    if n == "tìm" or n == "tim":
        return "tim"
    if n.startswith("tìm kiếm") or n in {"search", "lọc tìm kiếm", "filter", "lọc"}:
        return "tim_kiem"
    if "xem danh sách" in n or n in {"view list", "danh sách"}:
        return "xem_danh_sach"
    if "xem chi tiết" in n or n in {"view", "view detail", "chi tiết", "xem"}:
        return "xem_chi_tiet"
    if "phân trang" in n or "phan trang" in n or "pagination" in n:
        return "phan_trang"
    if (
        "tải lên" in n or "tải ảnh lên" in n or "tải file lên" in n
        or n in {"upload", "upload file", "upload ảnh"}
    ):
        return "upload_file"
    if (
        "import" in n or "nhập dữ liệu" in n or "nhập file" in n
        or "nhập từ excel" in n or "nhập liệu từ file" in n
    ):
        return "import_file"
    if (
        "tải xuống" in n or "download" in n or "tải file" in n
        or "tải tài liệu" in n or "tải biểu mẫu" in n
    ):
        return "download_file"
    if "xuất excel" in n or "xuất word" in n or "xuất file" in n or "export" in n:
        return "xuat_file"
    if n == "in" or n.startswith("in ") or "in ấn" in n or n == "print":
        return "in"
    if "lưu file" not in n and "lưu tệp" not in n and (n in {"lưu", "save"} or n.startswith("lưu ")):
        return "luu"
    if n in {"hủy", "huỷ", "hủy bỏ", "huỷ bỏ", "cancel"}:
        return "huy"
    if "sinh mã" in n or n in {"sinh ma", "generate code", "auto generate", "tự sinh mã"}:
        return "sinh_ma"
    if "chấm công" in n or "cham cong" in n or n in {
        "attendance",
        "check in",
        "check-in",
        "check out",
        "check-out",
    }:
        return "cham_cong"
    if "phân quyền" in n or "phan quyen" in n or n in {
        "permission",
        "permissions",
        "role",
        "roles",
        "role management",
        "grant permission",
    }:
        return "phan_quyen"
    return None

CRUD_FIELD_AWARE_CANONICALS = frozenset({
    "them_moi", "cap_nhat", "xoa", "tim", "tim_kiem", "phan_trang",
})
DEFAULT_ENFORCED_CANONICALS = frozenset({
    "quay_lai", "dang_nhap", "dang_ky", "xem_danh_sach", "xem_chi_tiet",
    "xuat_file", "in", "luu", "huy", "dong_popup", "sinh_ma",
    "dang_xuat", "quen_mat_khau", "doi_mat_khau",
    "upload_file", "import_file", "download_file",
    "cham_cong", "phan_quyen",
})
NO_GROUPING_CANONICALS = frozenset({"quay_lai"})
NO_OUTCOME_SPLIT_CANONICALS = frozenset({"huy", "dong_popup", "sinh_ma"})
CANONICAL_DISPLAY_NAME: dict[str, str] = {
    "quay_lai": "Quay lại",
}
LOGIN_SCENARIOS: list[dict] = [
    {
        "module": 'Đăng nhập thành công',
        "title": 'Đăng nhập thành công',
        "scenario": 'Nhập đúng tên đăng nhập và mật khẩu của tài khoản đang hoạt động rồi nhấn Đăng nhập',
        "expected_result": 'Tạo phiên đăng nhập thành công, chuyển đến màn hình phù hợp với quyền của tài khoản',
        "test_type": 'Kiểm thử chức năng',
    },
    {
        "module": 'Đăng nhập không thành công',
        "title": 'Đăng nhập không thành công',
        "scenario": 'Nhập sai tên đăng nhập, sai mật khẩu, sai cả hai, hoặc đăng nhập sai vượt quá số lần cho phép',
        "expected_result": 'Không tạo phiên đăng nhập, hiển thị thông báo sai thông tin đăng nhập (hoặc thông báo khóa tạm thời nếu vượt số lần), không chuyển vào hệ thống',
        "test_type": 'Kiểm thử chức năng',
    },
    {
        "module": 'Đăng nhập không thành công',
        "title": 'Đăng nhập không thành công',
        "scenario": 'Để trống tên đăng nhập, để trống mật khẩu, hoặc để trống cả hai (kể cả chỉ nhập khoảng trắng) rồi nhấn Đăng nhập',
        "expected_result": 'Hiển thị lỗi bắt buộc nhập tại đúng ô còn thiếu, không tạo phiên đăng nhập',
        "test_type": 'Kiểm thử chức năng',
    },
    {
        "module": 'Đăng nhập không thành công',
        "title": 'Đăng nhập không thành công',
        "scenario": 'Đăng nhập đúng thông tin nhưng tài khoản đang bị khóa, chưa kích hoạt, hoặc không được phân quyền truy cập ứng dụng',
        "expected_result": 'Hiển thị thông báo đúng trạng thái tài khoản (khóa/chưa kích hoạt/không có quyền), không tạo phiên đăng nhập',
        "test_type": 'Kiểm thử chức năng',
    },
    {
        "module": 'Đăng nhập không thành công',
        "title": 'Đăng nhập không thành công',
        "scenario": 'Thực hiện đăng nhập trong lúc dịch vụ xác thực phía server không phản hồi hoặc mất kết nối',
        "expected_result": 'Hiển thị thông báo lỗi hệ thống phù hợp, không tạo phiên đăng nhập, không treo màn hình',
        "test_type": 'Kiểm thử chức năng',
    },
]

CREATE_SCENARIOS: list[dict] = [
    {
        "module": 'Thêm mới thành công',
        "title": 'Thêm mới thành công',
        "scenario": 'Nhập đầy đủ và đúng định dạng toàn bộ dữ liệu bắt buộc rồi thực hiện lưu',
        "expected_result": 'Thêm mới thành công, thông tin được lưu đúng giá trị đã nhập và hiển thị tại danh sách',
        "test_type": 'Kiểm thử chức năng',
    },
    {
        "module": 'Thêm mới không thành công',
        "title": 'Thêm mới không thành công',
        "scenario": 'Để trống hoặc chỉ nhập khoảng trắng vào một trường bắt buộc bất kỳ, các trường còn lại hợp lệ, rồi lưu',
        "expected_result": 'Hiển thị lỗi bắt buộc nhập tại đúng trường bị thiếu, không lưu dữ liệu',
        "test_type": 'Kiểm thử chức năng',
    },
    {
        "module": 'Thêm mới không thành công',
        "title": 'Thêm mới không thành công',
        "scenario": 'Nhập sai định dạng, vượt giới hạn/độ dài cho phép, hoặc vi phạm ràng buộc nghiệp vụ tại một trường, các trường khác hợp lệ, rồi lưu',
        "expected_result": 'Hiển thị lỗi đúng tại trường vi phạm, không lưu dữ liệu',
        "test_type": 'Kiểm thử chức năng',
    },
    {
        "module": 'Thêm mới không thành công',
        "title": 'Thêm mới không thành công',
        "scenario": 'Nhập giá trị của trường yêu cầu duy nhất (mã/tên định danh...) trùng với bản ghi đã tồn tại, rồi lưu',
        "expected_result": 'Hiển thị thông báo dữ liệu đã tồn tại, không tạo thêm bản ghi trùng',
        "test_type": 'Kiểm thử chức năng',
    },
    {
        "module": 'Thêm mới không thành công',
        "title": 'Thêm mới không thành công',
        "scenario": 'Thực hiện lưu dữ liệu hợp lệ trong lúc API hoặc database phía server lỗi/không phản hồi',
        "expected_result": 'Hiển thị thông báo lỗi hệ thống phù hợp, không tạo bản ghi mới, dữ liệu đã nhập không bị mất trên form',
        "test_type": 'Kiểm thử chức năng',
    },
]

UPDATE_SCENARIOS: list[dict] = [
    {
        "module": 'Cập nhật thành công',
        "title": 'Cập nhật thành công',
        "scenario": 'Mở đúng bản ghi cần sửa, thay đổi một hoặc nhiều trường bằng dữ liệu hợp lệ rồi lưu',
        "expected_result": 'Cập nhật thành công, hiển thị đúng dữ liệu mới đã thay đổi',
        "test_type": 'Kiểm thử chức năng',
    },
    {
        "module": 'Cập nhật không thành công',
        "title": 'Cập nhật không thành công',
        "scenario": 'Xóa giá trị hoặc chỉ nhập khoảng trắng vào một trường bắt buộc rồi lưu',
        "expected_result": 'Hiển thị lỗi bắt buộc nhập tại đúng trường, không lưu thay đổi, dữ liệu cũ được giữ nguyên',
        "test_type": 'Kiểm thử chức năng',
    },
    {
        "module": 'Cập nhật không thành công',
        "title": 'Cập nhật không thành công',
        "scenario": 'Sửa một trường thành giá trị sai định dạng, vượt giới hạn/độ dài cho phép, hoặc trùng với bản ghi khác rồi lưu',
        "expected_result": 'Hiển thị lỗi đúng tại trường vi phạm, không lưu thay đổi',
        "test_type": 'Kiểm thử chức năng',
    },
    {
        "module": 'Cập nhật không thành công',
        "title": 'Cập nhật không thành công',
        "scenario": 'Mở form cập nhật một bản ghi, trong lúc đó bản ghi đã bị người khác xóa hoặc thay đổi trước, rồi nhấn Lưu',
        "expected_result": 'Hiển thị thông báo bản ghi không còn tồn tại hoặc đã bị thay đổi, không lưu đè dữ liệu',
        "test_type": 'Kiểm thử chức năng',
    },
    {
        "module": 'Cập nhật không thành công',
        "title": 'Cập nhật không thành công',
        "scenario": 'Thực hiện lưu thay đổi hợp lệ trong lúc API hoặc database phía server lỗi/không phản hồi',
        "expected_result": 'Hiển thị thông báo lỗi hệ thống phù hợp, không lưu thay đổi, dữ liệu cũ được giữ nguyên',
        "test_type": 'Kiểm thử chức năng',
    },
]
DELETE_SCENARIOS: list[dict] = [
    {
        "module": 'Xóa thành công',
        "title": 'Xóa thành công',
        "scenario": 'Chọn một bản ghi hợp lệ, không có ràng buộc, nhấn Xóa rồi xác nhận tại popup',
        "expected_result": 'Xóa thành công, bản ghi không còn hiển thị trong danh sách',
        "test_type": 'Kiểm thử chức năng',
    },
    {
        "module": 'Xóa không thành công',
        "title": 'Xóa không thành công',
        "scenario": 'Tại popup xác nhận xóa, nhấn Hủy hoặc đóng popup bằng nút X',
        "expected_result": 'Không xóa bản ghi, đóng popup và giữ nguyên dữ liệu trong danh sách',
        "test_type": 'Kiểm thử chức năng',
    },
    {
        "module": 'Xóa không thành công',
        "title": 'Xóa không thành công',
        "scenario": 'Mở popup xác nhận xóa một bản ghi, trong lúc đó bản ghi đã bị người khác xóa trước, rồi xác nhận xóa',
        "expected_result": 'Hiển thị thông báo bản ghi không còn tồn tại, không phát sinh lỗi hệ thống',
        "test_type": 'Kiểm thử chức năng',
    },
    {
        "module": 'Xóa không thành công',
        "title": 'Xóa không thành công',
        "scenario": 'Xác nhận xóa một bản ghi đang có ràng buộc/tham chiếu dữ liệu khác, hoặc tài khoản không được phân quyền xóa',
        "expected_result": 'Từ chối thao tác, hiển thị thông báo phù hợp (đang có ràng buộc/không có quyền), dữ liệu không bị xóa',
        "test_type": 'Kiểm thử chức năng',
    },
]

SEARCH_SCENARIOS: list[dict] = [
    {
        "module": 'Tìm kiếm thành công',
        "title": 'Tìm kiếm thành công',
        "scenario": 'Nhập từ khóa khớp chính xác hoặc khớp một phần với dữ liệu đang tồn tại rồi thực hiện tìm kiếm',
        "expected_result": 'Hiển thị đúng và đầy đủ các kết quả phù hợp với từ khóa',
        "test_type": 'Kiểm thử chức năng',
    },
    {
        "module": 'Tìm kiếm không thành công',
        "title": 'Tìm kiếm không thành công',
        "scenario": 'Nhập từ khóa hợp lệ nhưng không có bản ghi nào khớp rồi thực hiện tìm kiếm',
        "expected_result": 'Hiển thị thông báo không tìm thấy dữ liệu phù hợp, danh sách kết quả trống',
        "test_type": 'Kiểm thử chức năng',
    },
    {
        "module": 'Tìm kiếm không thành công',
        "title": 'Tìm kiếm không thành công',
        "scenario": 'Để trống ô tìm kiếm rồi thực hiện tìm kiếm (áp dụng nếu chức năng có ô tìm kiếm bắt buộc nhập)',
        "expected_result": 'Hiển thị toàn bộ dữ liệu theo phân trang mặc định hoặc thông báo yêu cầu nhập từ khóa, đúng theo quy tắc hệ thống',
        "test_type": 'Kiểm thử chức năng',
    },
]

FIND_SCENARIOS: list[dict] = [
    {
        "module": 'Tìm thành công',
        "title": 'Tìm thành công',
        "scenario": 'Nhập giá trị cần tìm khớp với bản ghi đang tồn tại rồi thực hiện tìm',
        "expected_result": 'Hiển thị đúng và chính xác bản ghi/dữ liệu tương ứng với giá trị đã nhập',
        "test_type": 'Kiểm thử chức năng',
    },
    {
        "module": 'Tìm không thành công',
        "title": 'Tìm không thành công',
        "scenario": 'Nhập giá trị hợp lệ nhưng không có bản ghi nào khớp rồi thực hiện tìm',
        "expected_result": 'Hiển thị thông báo không tìm thấy dữ liệu phù hợp',
        "test_type": 'Kiểm thử chức năng',
    },
    {
        "module": 'Tìm không thành công',
        "title": 'Tìm không thành công',
        "scenario": 'Bỏ trống ô nhập, hoặc nhập giá trị sai định dạng yêu cầu (ví dụ ký tự chữ vào ô chỉ nhận số) rồi thực hiện tìm',
        "expected_result": 'Hiển thị lỗi bắt buộc nhập/sai định dạng phù hợp, không thực hiện truy vấn sai lệch',
        "test_type": 'Kiểm thử chức năng',
    },
]

PAGINATION_SCENARIOS: list[dict] = [
    {
        "module": 'Phân trang',
        "title": 'Chuyển trang thành công',
        "scenario": 'Nhấn chuyển đến trang tiếp theo, trang trước, trang đầu, trang cuối, hoặc nhảy trực tiếp đến một số trang cụ thể',
        "expected_result": 'Hiển thị đúng dữ liệu của trang được chọn, số trang hiện tại cập nhật chính xác',
        "test_type": 'Kiểm thử chức năng',
    },
    {
        "module": 'Phân trang',
        "title": 'Nút điều hướng đúng trạng thái ở biên',
        "scenario": 'Quan sát trạng thái nút chuyển trang khi đang ở trang đầu, trang cuối, hoặc khi danh sách chỉ có một trang',
        "expected_result": 'Nút điều hướng tương ứng ở trạng thái vô hiệu (disabled) đúng vị trí biên, không thể nhấn',
        "test_type": 'Kiểm thử chức năng',
    },
    {
        "module": 'Phân trang',
        "title": 'Thay đổi số bản ghi mỗi trang',
        "scenario": 'Chọn một giá trị khác cho số bản ghi hiển thị trên mỗi trang',
        "expected_result": 'Danh sách hiển thị đúng số bản ghi mới đã chọn, tổng số trang được tính lại chính xác',
        "test_type": 'Kiểm thử chức năng',
    },
    {
        "module": 'Phân trang',
        "title": 'Tổng số trang cập nhật đúng sau khi dữ liệu thay đổi',
        "scenario": 'Thực hiện tìm kiếm thu hẹp kết quả hoặc xóa bớt bản ghi, sau đó quan sát khu vực phân trang',
        "expected_result": 'Tổng số trang và trang hiện tại được tính lại chính xác theo số bản ghi mới, không còn hiển thị trang thừa',
        "test_type": 'Kiểm thử chức năng',
    },
]

BACK_SCENARIOS: list[dict] = [
    {
        "module": "Quay lại",
        "title": "Quay lại khi chưa thay đổi dữ liệu",
        "scenario": "Nhấn nút Quay lại khi chưa thay đổi dữ liệu",
        "expected_result": "Về màn hình trước, không cảnh báo và không thay đổi dữ liệu",
        "test_type": "Kiểm thử chức năng",
    },
    {
        "module": "Quay lại",
        "title": "Quay lại khi đã thay đổi dữ liệu chưa lưu",
        "scenario": "Đã thay đổi dữ liệu và nhấn nút Quay lại",
        "expected_result": (
            "Hiển thị cảnh báo dữ liệu chưa lưu; nếu xác nhận bỏ thay đổi thì quay lại "
            "màn hình trước, nếu hủy cảnh báo thì giữ nguyên màn hình và dữ liệu hiện tại"
        ),
        "test_type": "Kiểm thử chức năng",
    },
    {
        "module": "Quay lại",
        "title": "Quay lại từ màn chi tiết hoặc sửa",
        "scenario": "Từ màn chi tiết hoặc sửa, nhấn Quay lại",
        "expected_result":"Chuyển đúng về màn hình danh sách vừa truy cập",
        "test_type": "Kiểm thử chức năng",
    },
    {
        "module": "Quay lại",
        "title": "Quay lại khi không có màn hình trước",
        "scenario": "Truy cập trực tiếp khi không có màn hình trước rồi nhấn Quay lại",
        "expected_result":"Chuyển về trang mặc định hoặc giữ nguyên màn hình an toàn",
        "test_type": "Kiểm thử chức năng",
    },
]

REGISTER_SCENARIOS: list[dict] = [
    {
        "module": 'Đăng ký thành công',
        "title": 'Đăng ký thành công',
        "scenario": 'Nhập đầy đủ và đúng định dạng toàn bộ thông tin bắt buộc rồi thực hiện đăng ký tài khoản',
        "expected_result":'Tạo tài khoản thành công, hiển thị thông báo phù hợp và chuyển đến bước tiếp theo hoặc màn hình đăng nhập',
        "test_type": 'Kiểm thử chức năng',
    },
    {
        "module": 'Đăng ký không thành công',
        "title": 'Đăng ký không thành công',
        "scenario": 'Để trống một trường bắt buộc bất kỳ, hoặc để trống toàn bộ các trường, rồi thực hiện đăng ký',
        "expected_result":'Hiển thị lỗi bắt buộc nhập tại đúng (các) trường bị thiếu, không tạo tài khoản',
        "test_type": 'Kiểm thử chức năng',
    },
    {
        "module": 'Đăng ký không thành công',
        "title": 'Đăng ký không thành công',
        "scenario": 'Nhập Email/số điện thoại sai định dạng, mật khẩu không đạt quy tắc, hoặc xác nhận mật khẩu không khớp, rồi đăng ký',
        "expected_result": 'Hiển thị lỗi đúng tại trường vi phạm, không tạo tài khoản',
        "test_type": 'Kiểm thử chức năng',
    },
    {
        "module": 'Đăng ký không thành công',
        "title": 'Đăng ký không thành công',
        "scenario": 'Nhập Email, số điện thoại, hoặc tên đăng nhập đã được dùng để đăng ký tài khoản khác, rồi đăng ký',
        "expected_result": 'Hiển thị thông báo dữ liệu đã tồn tại, không tạo tài khoản mới',
        "test_type": 'Kiểm thử chức năng',
    },
]
LOGOUT_SCENARIOS: list[dict] = [
    {
        "module": 'Đăng xuất thành công',
        "title": 'Đăng xuất thành công',
        "scenario": 'Người dùng đang đăng nhập, nhấn Đăng xuất và xác nhận',
        "expected_result": 'Kết thúc phiên đăng nhập thành công và chuyển về màn hình đăng nhập',
        "test_type": 'Kiểm thử chức năng',
    },
    {
        "module": 'Đăng xuất không thành công',
        "title": 'Đăng xuất không thành công',
        "scenario": 'Nhấn Đăng xuất, khi popup xác nhận hiện ra thì nhấn Hủy hoặc Không',
        "expected_result": 'Không kết thúc phiên đăng nhập, đóng popup và giữ nguyên màn hình hiện tại',
        "test_type": 'Kiểm thử chức năng',
    },
    {
        "module": 'Đăng xuất không thành công',
        "title": 'Đăng xuất không thành công',
        "scenario": 'Sau khi đăng xuất thành công, dán lại URL trang đã bảo vệ hoặc nhấn Back trình duyệt để quay lại trang đó',
        "expected_result": 'Không hiển thị lại dữ liệu đã bảo vệ, hệ thống yêu cầu đăng nhập lại; xác nhận phiên/cache cũ đã bị vô hiệu hóa',
        "test_type": 'Kiểm thử chức năng',
    },
    {
        "module": 'Đăng xuất không thành công',
        "title": 'Đăng xuất không thành công',
        "scenario": 'Nhấn Đăng xuất trong lúc dịch vụ phía server không phản hồi hoặc trả về lỗi',
        "expected_result": 'Hiển thị thông báo lỗi phù hợp; phiên tại client vẫn được xử lý an toàn để tránh treo ở trạng thái đã đăng nhập',
        "test_type": 'Kiểm thử chức năng',
    },
]

FORGOT_PASSWORD_SCENARIOS: list[dict] = [
    {
        "module": 'Quên mật khẩu',
        "title": 'Gửi yêu cầu thành công',
        "scenario": 'Nhập Email hoặc số điện thoại đã đăng ký và thực hiện gửi yêu cầu quên mật khẩu',
        "expected_result": 'Gửi OTP/liên kết đặt lại mật khẩu đến đúng Email/SĐT, chưa thay đổi mật khẩu hiện tại',
        "test_type": 'Kiểm thử chức năng',
    },
    {
        "module": 'Quên mật khẩu',
        "title": 'Bỏ trống hoặc sai định dạng',
        "scenario": 'Để trống ô Email/SĐT, hoặc nhập Email sai định dạng, rồi nhấn gửi yêu cầu quên mật khẩu',
        "expected_result": 'Hiển thị lỗi bắt buộc nhập/sai định dạng phù hợp, không gửi OTP hoặc liên kết đặt lại mật khẩu',
        "test_type": 'Kiểm thử chức năng',
    },
    {
        "module": 'Quên mật khẩu',
        "title": 'Tài khoản không tồn tại',
        "scenario": 'Nhập Email hoặc số điện thoại chưa từng đăng ký trong hệ thống rồi gửi yêu cầu',
        "expected_result": 'Hiển thị thông báo chung theo đúng quy định bảo mật của hệ thống, không tiết lộ tài khoản có tồn tại hay không, không gửi OTP',
        "test_type": 'Kiểm thử chức năng',
    },
    {
        "module": 'Quên mật khẩu',
        "title": 'Xác thực OTP không hợp lệ',
        "scenario": 'Nhập sai mã OTP, nhập mã OTP đã hết hạn, hoặc gửi/gửi lại OTP vượt quá số lần hệ thống cho phép',
        "expected_result": 'Hiển thị thông báo phù hợp theo từng trường hợp (OTP sai/hết hạn/vượt số lần), không cho phép đặt lại mật khẩu',
        "test_type": 'Kiểm thử chức năng',
    },
    {
        "module": 'Quên mật khẩu',
        "title": 'Đặt lại mật khẩu thành công',
        "scenario": 'Xác thực OTP thành công, nhập mật khẩu mới hợp lệ và xác nhận khớp',
        "expected_result": 'Đặt lại mật khẩu thành công, đăng nhập lần sau phải dùng mật khẩu mới',
        "test_type": 'Kiểm thử chức năng',
    },
    {
        "module": 'Quên mật khẩu',
        "title": 'Lỗi hệ thống',
        "scenario": 'Thực hiện gửi yêu cầu quên mật khẩu trong lúc dịch vụ gửi OTP/Email không phản hồi',
        "expected_result": 'Hiển thị thông báo lỗi hệ thống phù hợp, không đặt lại mật khẩu',
        "test_type": 'Kiểm thử chức năng',
    },
]

CHANGE_PASSWORD_SCENARIOS: list[dict] = [
    {
        "module": 'Đổi mật khẩu thành công',
        "title": 'Đổi mật khẩu thành công',
        "scenario": 'Nhập đúng mật khẩu hiện tại, mật khẩu mới đạt quy tắc và xác nhận khớp, rồi lưu',
        "expected_result": 'Đổi mật khẩu thành công, hiển thị thông báo phù hợp',
        "test_type": 'Kiểm thử chức năng',
    },
    {
        "module": 'Đổi mật khẩu không thành công',
        "title": 'Đổi mật khẩu không thành công',
        "scenario": 'Nhập sai mật khẩu hiện tại, mật khẩu mới và xác nhận hợp lệ, rồi lưu',
        "expected_result": 'Hiển thị thông báo sai mật khẩu hiện tại, không đổi mật khẩu',
        "test_type": 'Kiểm thử chức năng',
    },
    {
        "module": 'Đổi mật khẩu không thành công',
        "title": 'Đổi mật khẩu không thành công',
        "scenario": 'Để trống mật khẩu hiện tại, mật khẩu mới, hoặc xác nhận mật khẩu rồi lưu',
        "expected_result": 'Hiển thị lỗi bắt buộc nhập tại đúng ô còn thiếu, không đổi mật khẩu',
        "test_type": 'Kiểm thử chức năng',
    },
    {
        "module": 'Đổi mật khẩu không thành công',
        "title": 'Đổi mật khẩu không thành công',
        "scenario": 'Nhập mật khẩu mới không đạt quy tắc hệ thống, xác nhận không khớp, hoặc trùng với mật khẩu hiện tại/đã dùng gần đây',
        "expected_result": 'Hiển thị lỗi đúng nguyên nhân, không đổi mật khẩu',
        "test_type": 'Kiểm thử chức năng',
    },
    {
        "module": 'Đổi mật khẩu không thành công',
        "title": 'Đổi mật khẩu không thành công',
        "scenario": 'Thực hiện đổi mật khẩu hợp lệ trong lúc dịch vụ đổi mật khẩu gặp lỗi hoặc phiên đăng nhập đã hết hạn',
        "expected_result": 'Hiển thị thông báo lỗi phù hợp (lỗi hệ thống/phiên hết hạn), không đổi mật khẩu',
        "test_type": 'Kiểm thử chức năng',
    },
]

LIST_VIEW_SCENARIOS: list[dict] = [
    {
        "module": 'Xem danh sách thành công',
        "title": 'Xem danh sách thành công',
        "scenario": 'Truy cập màn hình danh sách khi hệ thống đang có dữ liệu',
        "expected_result": 'Hiển thị đúng và đầy đủ danh sách bản ghi theo đúng số lượng phân trang mặc định',
        "test_type": 'Kiểm thử chức năng',
    },
    {
        "module": 'Xem danh sách không thành công',
        "title": 'Xem danh sách không thành công',
        "scenario": 'Truy cập màn hình danh sách khi hệ thống chưa có dữ liệu',
        "expected_result": 'Hiển thị thông báo/giao diện danh sách rỗng phù hợp, không báo lỗi hệ thống',
        "test_type": 'Kiểm thử chức năng',
    },
    {
        "module": 'Xem danh sách không thành công',
        "title": 'Xem danh sách không thành công',
        "scenario": 'Truy cập màn hình danh sách bằng tài khoản không được phân quyền',
        "expected_result": 'Từ chối truy cập, hiển thị thông báo không có quyền phù hợp',
        "test_type": 'Kiểm thử chức năng',
    },
    {
        "module": 'Xem danh sách không thành công',
        "title": 'Xem danh sách không thành công',
        "scenario": 'Truy cập màn hình danh sách trong lúc dịch vụ tải dữ liệu phía server lỗi hoặc không phản hồi',
        "expected_result": 'Hiển thị thông báo lỗi hệ thống phù hợp, không hiển thị dữ liệu sai lệch',
        "test_type": 'Kiểm thử chức năng',
    },
]

DETAIL_VIEW_SCENARIOS: list[dict] = [
    {
        "module": 'Xem chi tiết thành công',
        "title": 'Xem chi tiết thành công',
        "scenario": 'Chọn một bản ghi đang tồn tại và mở màn hình xem chi tiết',
        "expected_result": 'Hiển thị đúng và đầy đủ dữ liệu chi tiết, khớp chính xác với dữ liệu trong danh sách',
        "test_type": 'Kiểm thử chức năng',
    },
    {
        "module": 'Xem chi tiết không thành công',
        "title": 'Xem chi tiết không thành công',
        "scenario": 'Mở chi tiết một bản ghi đã bị xóa hoặc có định danh không hợp lệ',
        "expected_result": 'Hiển thị thông báo bản ghi không còn tồn tại/không hợp lệ, không phát sinh lỗi hệ thống',
        "test_type": 'Kiểm thử chức năng',
    },
    {
        "module": 'Xem chi tiết không thành công',
        "title": 'Xem chi tiết không thành công',
        "scenario": 'Mở chi tiết một bản ghi ngoài phạm vi quyền được phép của tài khoản',
        "expected_result": 'Từ chối truy cập, hiển thị thông báo không có quyền phù hợp',
        "test_type": 'Kiểm thử chức năng',
    },
    {
        "module": 'Xem chi tiết không thành công',
        "title": 'Xem chi tiết không thành công',
        "scenario": 'Mở màn hình chi tiết trong lúc dịch vụ tải dữ liệu phía server lỗi hoặc không phản hồi',
        "expected_result": 'Hiển thị thông báo lỗi hệ thống phù hợp, không hiển thị dữ liệu sai lệch',
        "test_type": 'Kiểm thử chức năng',
    },
]

EXPORT_FILE_SCENARIOS: list[dict] = [
    {
        "module": '<Tên chức năng> thành công',
        "title": 'Xuất file thành công',
        "scenario": 'Thực hiện xuất file khi danh sách đang có dữ liệu',
        "expected_result": 'Xuất file thành công, đúng định dạng, đúng tên/thứ tự cột và đúng dữ liệu (kể cả tiếng Việt có dấu), file mở được bằng phần mềm tương ứng',
        "test_type": 'Kiểm thử chức năng',
    },
    {
        "module": '<Tên chức năng> không thành công',
        "title": 'Xuất file không thành công',
        "scenario": 'Thực hiện xuất file khi danh sách không có bản ghi nào',
        "expected_result": 'Hiển thị thông báo không có dữ liệu để xuất, hoặc xuất file chỉ chứa tiêu đề cột, đúng theo quy tắc hệ thống',
        "test_type": 'Kiểm thử chức năng',
    },
    {
        "module": '<Tên chức năng> không thành công',
        "title": 'Xuất file không thành công',
        "scenario": 'Áp dụng bộ lọc/điều kiện tìm kiếm rồi thực hiện xuất file',
        "expected_result": 'File xuất ra chỉ chứa đúng dữ liệu thỏa điều kiện lọc đã áp dụng',
        "test_type": 'Kiểm thử chức năng',
    },
    {
        "module": '<Tên chức năng> không thành công',
        "title": 'Xuất file không thành công',
        "scenario": 'Tài khoản không được phân quyền xuất file thực hiện gọi chức năng xuất file',
        "expected_result": 'Từ chối thao tác, hiển thị thông báo không có quyền, không tạo file',
        "test_type": 'Kiểm thử chức năng',
    },
    {
        "module": '<Tên chức năng> không thành công',
        "title": 'Xuất file không thành công',
        "scenario": 'Thực hiện xuất file trong lúc dịch vụ tạo file phía server gặp lỗi',
        "expected_result": 'Hiển thị thông báo lỗi hệ thống phù hợp, không tạo ra file lỗi/rỗng',
        "test_type": 'Kiểm thử chức năng',
    },
]

PRINT_SCENARIOS: list[dict] = [
    {
        "module": 'In',
        "title": 'In thành công',
        "scenario": 'Thực hiện in khi màn hình đang có dữ liệu (áp dụng đúng bộ lọc/điều kiện nếu có)',
        "expected_result": 'Hiển thị đúng bản xem trước và in thành công đúng dữ liệu hiện có',
        "test_type": 'Kiểm thử chức năng',
    },
    {
        "module": 'In',
        "title": 'In không thành công',
        "scenario": 'Thực hiện in khi màn hình không có dữ liệu',
        "expected_result": 'Hiển thị thông báo không có dữ liệu để in, hoặc bản in chỉ chứa tiêu đề, đúng theo quy tắc hệ thống',
        "test_type": 'Kiểm thử chức năng',
    },
    {
        "module": 'In',
        "title": 'In không thành công',
        "scenario": 'Thực hiện in trong lúc dịch vụ tạo bản in phía server gặp lỗi',
        "expected_result": 'Hiển thị thông báo lỗi hệ thống phù hợp, không tạo bản in lỗi',
        "test_type": 'Kiểm thử chức năng',
    },
]

SAVE_SCENARIOS: list[dict] = [
    {
        "module": 'Lưu',
        "title": 'Lưu thành công',
        "scenario": 'Nhập đầy đủ và đúng dữ liệu hợp lệ rồi nhấn Lưu',
        "expected_result": 'Lưu thành công, dữ liệu hiển thị đúng giá trị đã nhập',
        "test_type": 'Kiểm thử chức năng',
    },
    {
        "module": 'Lưu',
        "title": 'Lưu không thành công',
        "scenario": 'Để trống một trường bắt buộc rồi nhấn Lưu',
        "expected_result": 'Hiển thị lỗi bắt buộc nhập tại đúng trường, không lưu dữ liệu',
        "test_type": 'Kiểm thử chức năng',
    },
    {
        "module": 'Lưu',
        "title": 'Lưu không thành công',
        "scenario": 'Nhập sai định dạng, vượt giới hạn độ dài, hoặc trùng dữ liệu tại một trường rồi nhấn Lưu',
        "expected_result": 'Hiển thị lỗi đúng tại trường vi phạm, không lưu dữ liệu',
        "test_type": 'Kiểm thử chức năng',
    },
    {
        "module": 'Lưu',
        "title": 'Lưu không thành công',
        "scenario": 'Tài khoản không được phân quyền lưu thực hiện nhấn Lưu',
        "expected_result": 'Từ chối thao tác, hiển thị thông báo không có quyền, không lưu dữ liệu',
        "test_type": 'Kiểm thử chức năng',
    },
    {
        "module": 'Lưu',
        "title": 'Lưu không thành công',
        "scenario": 'Nhấn Lưu với dữ liệu hợp lệ trong lúc API hoặc database phía server lỗi/không phản hồi, hoặc phiên đăng nhập đã hết hạn',
        "expected_result": 'Hiển thị thông báo lỗi phù hợp, không lưu dữ liệu, dữ liệu đã nhập không bị mất trên form',
        "test_type": 'Kiểm thử chức năng',
    },
]

CANCEL_SCENARIOS: list[dict] = [
    {
        "module": 'Hủy không thành công',
        "title": 'Hủy không thành công',
        "scenario": 'Nhấn Hủy khi chưa nhập hoặc thay đổi dữ liệu nào',
        "expected_result": 'Đóng màn hình hoặc trở về trạng thái trước đó ngay, không hiển thị cảnh báo',
        "test_type": 'Kiểm thử chức năng',
    },
    {
        "module": 'Hủy thành công',
        "title": 'Hủy thành công',
        "scenario": 'Thay đổi dữ liệu, nhấn Hủy, hộp thoại cảnh báo hiện ra, chọn xác nhận bỏ thay đổi',
        "expected_result": 'Bỏ toàn bộ các thay đổi chưa lưu và trở về màn hình phù hợp',
        "test_type": 'Kiểm thử chức năng',
    },
    {
        "module": 'Hủy không thành công',
        "title": 'Hủy không thành công',
        "scenario": 'Thay đổi dữ liệu, nhấn Hủy, hộp thoại cảnh báo hiện ra, chọn không xác nhận (giữ lại)',
        "expected_result": 'Không mất dữ liệu đã thay đổi, đóng hộp thoại cảnh báo và giữ nguyên màn hình hiện tại',
        "test_type": 'Kiểm thử chức năng',
    },
]

GENERATE_CODE_SCENARIOS: list[dict] = [
    {
        "module": 'Sinh mã thành công',
        "title": 'Sinh mã thành công',
        "scenario": 'Nhấn sinh mã khi dữ liệu đầu vào cần thiết để tạo mã đã hợp lệ',
        "expected_result": 'Hệ thống tự động sinh mã đúng quy tắc, duy nhất và hiển thị vào đúng trường tương ứng',
        "test_type": 'Kiểm thử chức năng',
    },
    {
        "module": 'Sinh mã không thành công',
        "title": 'Sinh mã không thành công',
        "scenario": 'Thực hiện sinh mã khi thiếu dữ liệu đầu vào cần thiết để tạo mã',
        "expected_result": 'Hiển thị thông báo phù hợp, không sinh mã',
        "test_type": 'Kiểm thử chức năng',
    },
    {
        "module": 'Sinh mã không thành công',
        "title": 'Sinh mã không thành công',
        "scenario": 'Kiểm tra định dạng/tiền tố/độ dài của mã vừa sinh, và sinh mã nhiều lần liên tiếp cho các bản ghi khác nhau',
        "expected_result": 'Mã sinh ra luôn đúng định dạng, đúng quy tắc và không trùng với mã đã tồn tại hoặc đã sinh trước đó',
        "test_type": 'Kiểm thử chức năng',
    },
    {
        "module": 'Sinh mã không thành công',
        "title": 'Sinh mã không thành công',
        "scenario": 'Thực hiện sinh mã khi đã hết dải mã khả dụng, hoặc trong lúc dịch vụ sinh mã không phản hồi',
        "expected_result": 'Hiển thị thông báo lỗi phù hợp (hết dải mã/lỗi hệ thống), không sinh ra mã trùng hoặc sai quy tắc',
        "test_type": 'Kiểm thử chức năng',
    },
]
ATTENDANCE_SCENARIOS: list[dict] = [
    {
        "module": "Chấm công thành công",
        "title": "Chấm công thành công",
        "scenario": "Nhân viên thực hiện chấm công vào đúng thời gian và đúng vị trí.",
        "expected_result": "Hệ thống ghi nhận thời gian chấm công và hiển thị thông báo chấm công thành công.",
        "test_type": "Kiểm thử chức năng",
    },
    {
        "module": "Chấm công không thành công",
        "title": "Chấm công không thành công",
        "scenario": "Nhân viên thực hiện chấm công ngoài thời gian hoặc ngoài vị trí được phép.",
        "expected_result": "Hệ thống không ghi nhận dữ liệu chấm công và hiển thị thông báo phù hợp.",
        "test_type": "Kiểm thử chức năng",
    },
    {
        "module": "Chấm công không thành công",
        "title": "Chấm công không thành công",
        "scenario": "Nhân viên thực hiện chấm công nhiều lần cho cùng một thời điểm.",
        "expected_result": "Hệ thống không tạo bản ghi chấm công trùng và hiển thị thông báo đã chấm công.",
        "test_type": "Kiểm thử chức năng",
    },
    {
        "module": "Chấm công không thành công",
        "title": "Chấm công không thành công",
        "scenario": "Người dùng không có quyền chấm công hoặc tài khoản đang bị khóa.",
        "expected_result": "Hệ thống từ chối chấm công và hiển thị thông báo không có quyền hoặc tài khoản không hợp lệ.",
        "test_type": "Kiểm thử phân quyền",
    },
]

PERMISSION_SCENARIOS: list[dict] = [
    {
        "module": "Phân quyền thành công",
        "title": "Phân quyền thành công",
        "scenario": "Quản trị viên chọn người dùng, chọn quyền hợp lệ và thực hiện lưu.",
        "expected_result": "Hệ thống lưu quyền thành công và người dùng được truy cập đúng chức năng đã cấp.",
        "test_type": "Kiểm thử phân quyền",
    },
    {
        "module": "Phân quyền không thành công",
        "title": "Phân quyền không thành công",
        "scenario": "Người thực hiện phân quyền không có quyền quản trị hệ thống.",
        "expected_result": "Hệ thống từ chối thao tác và hiển thị thông báo không có quyền phân quyền.",
        "test_type": "Kiểm thử phân quyền",
    },
    {
        "module": "Phân quyền không thành công",
        "title": "Phân quyền không thành công",
        "scenario": "Quản trị viên thực hiện lưu khi chưa chọn người dùng hoặc chưa chọn quyền.",
        "expected_result": "Hệ thống hiển thị lỗi bắt buộc chọn người dùng và quyền, không lưu dữ liệu.",
        "test_type": "Kiểm thử xác thực",
    },
    {
        "module": "Phân quyền không thành công",
        "title": "Phân quyền không thành công",
        "scenario": "Quản trị viên phân quyền cho tài khoản không tồn tại, đã bị xóa hoặc đang bị khóa.",
        "expected_result": "Hệ thống không lưu quyền và hiển thị thông báo trạng thái tài khoản không hợp lệ.",
        "test_type": "Kiểm thử phân quyền",
    },
    {
        "module": "Phân quyền không thành công",
        "title": "Phân quyền không thành công",
        "scenario": "Quản trị viên lưu thay đổi quyền trong lúc API hoặc cơ sở dữ liệu không phản hồi.",
        "expected_result": "Hệ thống hiển thị thông báo lỗi, không lưu thay đổi quyền và giữ nguyên quyền cũ.",
        "test_type": "Kiểm thử tích hợp",
    },
]


FUNCTION_KNOWLEDGE: dict[str, list[dict]] = {
    "dang_nhap": LOGIN_SCENARIOS,
    "them_moi": CREATE_SCENARIOS,
    "cap_nhat": UPDATE_SCENARIOS,
    "xoa": DELETE_SCENARIOS,
    "tim_kiem": SEARCH_SCENARIOS,
    "tim": FIND_SCENARIOS,
    "phan_trang": PAGINATION_SCENARIOS,
    "quay_lai": BACK_SCENARIOS,
    "dang_ky": REGISTER_SCENARIOS,
    "dang_xuat": LOGOUT_SCENARIOS,
    "quen_mat_khau": FORGOT_PASSWORD_SCENARIOS,
    "doi_mat_khau": CHANGE_PASSWORD_SCENARIOS,
    "xem_danh_sach": LIST_VIEW_SCENARIOS,
    "xem_chi_tiet": DETAIL_VIEW_SCENARIOS,
    "xuat_file": EXPORT_FILE_SCENARIOS,
    "in": PRINT_SCENARIOS,
    "luu": SAVE_SCENARIOS,
    "huy": CANCEL_SCENARIOS,
    "sinh_ma": GENERATE_CODE_SCENARIOS,
    "cham_cong": ATTENDANCE_SCENARIOS,
    "phan_quyen": PERMISSION_SCENARIOS,
}
FIXED_TEMPLATES: dict[str, list[dict]] = FUNCTION_KNOWLEDGE
STUDENT_MANAGEMENT_SCENARIOS: list[dict] = [
    {
        "module": "Quản lý sinh viên thành công",
        "title": "Quản lý sinh viên thành công",
        "scenario": "Thực hiện xem, thêm mới hoặc cập nhật thông tin sinh viên bằng dữ liệu hợp lệ",
        "expected_result": "Hệ thống xử lý thành công, lưu đúng thông tin và hiển thị dữ liệu sinh viên chính xác",
        "test_type": "Kiểm thử dương",
    },
    {
        "module": "Quản lý sinh viên không thành công",
        "title": "Quản lý sinh viên không thành công",
        "scenario": (
            "Thực hiện thao tác khi thiếu dữ liệu bắt buộc, dữ liệu không hợp lệ, "
            "mã sinh viên đã tồn tại hoặc người dùng không có quyền"
        ),
        "expected_result": "Không lưu dữ liệu không hợp lệ, hiển thị thông báo phù hợp và giữ thông tin ở trạng thái an toàn",
        "test_type": "Kiểm thử âm",
    },
]

CLASS_MANAGEMENT_SCENARIOS: list[dict] = [
    {
        "module": "Quản lý lớp học thành công",
        "title": "Quản lý lớp học thành công",
        "scenario": "Thực hiện xem, thêm mới hoặc cập nhật lớp học bằng thông tin hợp lệ",
        "expected_result": "Hệ thống xử lý thành công, lưu đúng thông tin lớp học và cập nhật danh sách",
        "test_type": "Kiểm thử dương",
    },
    {
        "module": "Quản lý lớp học thành công",
        "title": "Quản lý lớp học không thành công",
        "scenario": (
            "Thực hiện thao tác khi thiếu dữ liệu, mã lớp bị trùng, "
            "thông tin không hợp lệ hoặc người dùng không có quyền"
        ),
        "expected_result": "Không tạo hoặc cập nhật lớp học, hiển thị thông báo phù hợp và không phát sinh dữ liệu trùng",
        "test_type": "Kiểm thử âm",
    },
]

SUBJECT_MANAGEMENT_SCENARIOS: list[dict] = [
    {
        "module": "Quản lý môn học thành công",
        "title": "Quản lý môn học thành công",
        "scenario": "Thực hiện xem, thêm mới hoặc cập nhật môn học bằng dữ liệu hợp lệ",
        "expected_result": "Hệ thống lưu thành công và hiển thị đúng thông tin môn học",
        "test_type": "Kiểm thử dương",
    },
    {
        "module": "Quản lý môn học không thành công",
        "title": "Quản lý môn học không thành công",
        "scenario": (
            "Thực hiện thao tác khi thiếu dữ liệu bắt buộc, mã môn học đã tồn tại, "
            "số tín chỉ không hợp lệ hoặc người dùng không có quyền"
        ),
        "expected_result": "Không lưu thông tin không hợp lệ, hiển thị thông báo phù hợp và giữ nguyên dữ liệu trước đó",
        "test_type": "Kiểm thử âm",
    },
]

GRADE_MANAGEMENT_SCENARIOS: list[dict] = [
    {
        "module": "Quản lý điểm thành công",
        "title": "Quản lý điểm thành công",
        "scenario": "Nhập hoặc cập nhật điểm của sinh viên bằng giá trị hợp lệ theo thang điểm của hệ thống",
        "expected_result": "Hệ thống lưu điểm thành công, tính toán kết quả đúng và hiển thị chính xác",
        "test_type": "Kiểm thử dương",
    },
    {
        "module": "Quản lý điểm không thành công",
        "title": "Quản lý điểm không thành công",
        "scenario": (
            "Nhập điểm âm, vượt thang điểm, sai định dạng, thiếu thông tin "
            "hoặc thực hiện khi không có quyền"
        ),
        "expected_result": "Không lưu điểm không hợp lệ, hiển thị thông báo phù hợp và giữ nguyên kết quả trước đó",
        "test_type": "Kiểm thử âm",
    },
]

PATIENT_MANAGEMENT_SCENARIOS: list[dict] = [
    {
        "module": "Quản lý bệnh nhân thành công",
        "title": "Quản lý bệnh nhân thành công",
        "scenario": "Thực hiện xem, thêm mới hoặc cập nhật hồ sơ bệnh nhân bằng dữ liệu hợp lệ",
        "expected_result": "Hệ thống lưu thành công và hiển thị đúng thông tin bệnh nhân",
        "test_type": "Kiểm thử dương",
    },
    {
        "module": "Quản lý bệnh nhân không thành công",
        "title": "Quản lý bệnh nhân không thành công",
        "scenario": (
            "Thực hiện thao tác khi thiếu thông tin bắt buộc, dữ liệu sai định dạng, "
            "hồ sơ đã tồn tại hoặc người dùng không có quyền"
        ),
        "expected_result": "Không lưu hồ sơ không hợp lệ, hiển thị thông báo phù hợp và bảo vệ thông tin bệnh nhân",
        "test_type": "Kiểm thử âm",
    },
]

APPOINTMENT_SCENARIOS: list[dict] = [
    {
        "module": "Xem lịch khám thành công",
        "title": "Quản lý lịch khám thành công",
        "scenario": (
            "Tạo hoặc cập nhật lịch khám bằng thời gian hợp lệ, "
            "bệnh nhân và bác sĩ còn khả dụng"
        ),
        "expected_result": (
            "Hệ thống lưu lịch khám thành công, không trùng lịch "
            "và hiển thị đúng thông tin cuộc hẹn"
        ),
        "test_type": "Kiểm thử dương",
    },
    {
        "module": "Xem lịch khám không thành công",
        "title": "Quản lý lịch khám không thành công",
        "scenario": (
            "Tạo lịch khám khi thiếu thông tin, thời gian không hợp lệ, "
            "trùng lịch, bác sĩ không khả dụng hoặc người dùng không có quyền"
        ),
        "expected_result": "Không tạo lịch khám, hiển thị thông báo phù hợp và không làm thay đổi lịch hiện tại",
        "test_type": "Kiểm thử âm",
    },
]

PAYMENT_SCENARIOS: list[dict] = [
    {
        "module": "Thanh toán thành công",
        "title": "Thanh toán thành công",
        "scenario": (
            "Thực hiện thanh toán với hóa đơn hợp lệ, số tiền chính xác "
            "và phương thức thanh toán khả dụng"
        ),
        "expected_result": (
            "Thanh toán thành công, trạng thái hóa đơn được cập nhật "
            "và giao dịch được ghi nhận chính xác"
        ),
        "test_type": "Kiểm thử dương",
    },
    {
        "module": "Thanh toán không thành công",
        "title": "Thanh toán không thành công",
        "scenario": (
            "Thực hiện thanh toán khi số tiền không hợp lệ, hóa đơn không tồn tại, "
            "giao dịch bị từ chối hoặc hệ thống xảy ra lỗi"
        ),
        "expected_result": "Không ghi nhận thanh toán sai, hiển thị thông báo phù hợp và giữ nguyên trạng thái hóa đơn",
        "test_type": "Kiểm thử âm",
    },
]

TRANSFER_SCENARIOS: list[dict] = [
    {
        "module": "Chuyển khoản thành công",
        "title": "Chuyển khoản thành công",
        "scenario": (
            "Thực hiện chuyển khoản đến tài khoản hợp lệ với số tiền phù hợp "
            "và số dư đáp ứng yêu cầu"
        ),
        "expected_result": (
            "Giao dịch thành công, số dư được cập nhật chính xác "
            "và lịch sử giao dịch được ghi nhận"
        ),
        "test_type": "Kiểm thử dương",
    },
    {
        "module": "Chuyển khoản không thành công",
        "title": "Chuyển khoản không thành công",
        "scenario": (
            "Thực hiện chuyển khoản khi tài khoản nhận không hợp lệ, số tiền không hợp lệ, "
            "số dư không đủ, vượt hạn mức hoặc xác thực thất bại"
        ),
        "expected_result": "Không thực hiện giao dịch, không thay đổi số dư và hiển thị thông báo phù hợp với nguyên nhân thất bại",
        "test_type": "Kiểm thử âm",
    },
]

TRANSACTION_HISTORY_SCENARIOS: list[dict] = [
    {
        "module": "Xem lịch sử giao dịch thành công",
        "title": "Xem lịch sử giao dịch thành công",
        "scenario": (
            "Truy cập lịch sử giao dịch của tài khoản hợp lệ "
            "và áp dụng điều kiện lọc phù hợp"
        ),
        "expected_result": (
            "Hiển thị đầy đủ, chính xác và đúng thứ tự các giao dịch "
            "thuộc phạm vi người dùng được phép xem"
        ),
        "test_type": "Kiểm thử dương",
    },
    {
        "module": "Xem lịch sử giao dịch không thành công",
        "title": "Xem lịch sử giao dịch không thành công",
        "scenario": (
            "Truy cập khi tài khoản không tồn tại, điều kiện lọc không hợp lệ, "
            "không có quyền hoặc dịch vụ dữ liệu xảy ra lỗi"
        ),
        "expected_result": "Không hiển thị dữ liệu trái phép, thông báo lỗi phù hợp và giữ màn hình ở trạng thái an toàn",
        "test_type": "Kiểm thử âm",
    },
]

XEM_BAO_CAO: list[dict] = [
    {
        "module": "Xem báo cáo thành công",
        "title": "Xem báo cáo thành công",
        "scenario": (
            "Chọn loại báo cáo, khoảng thời gian và điều kiện thống kê hợp lệ "
            "rồi thực hiện xem báo cáo"
        ),
        "expected_result": "Thông báo xem báo cáo thành công, số liệu chính xác và hiển thị đúng định dạng",
        "test_type": "Kiểm thử dương",
    },
    {
        "module": "Xem báo cáo không thành công",
        "title": "Xem báo cáo không thành công",
        "scenario": (
            "Xem báo cáo khi điều kiện không hợp lệ, không có dữ liệu, "
            "không có quyền hoặc dịch vụ thống kê xảy ra lỗi"
        ),
        "expected_result": "Hiển thị thông báo phù hợp và không làm thay đổi dữ liệu hệ thống",
        "test_type": "Kiểm thử âm",
    },
]

DOMAIN_TEMPLATES: dict[str, list[dict]] = {
    "quan_ly_sinh_vien": STUDENT_MANAGEMENT_SCENARIOS,
    "quan_ly_lop_hoc": CLASS_MANAGEMENT_SCENARIOS,
    "quan_ly_mon_hoc": SUBJECT_MANAGEMENT_SCENARIOS,
    "quan_ly_diem": GRADE_MANAGEMENT_SCENARIOS,
    "quan_ly_benh_nhan": PATIENT_MANAGEMENT_SCENARIOS,
    "lich_kham": APPOINTMENT_SCENARIOS,
    "thanh_toan": PAYMENT_SCENARIOS,
    "chuyen_khoan": TRANSFER_SCENARIOS,
    "lich_su_giao_dich": TRANSACTION_HISTORY_SCENARIOS,
    "xem_bao_cao": XEM_BAO_CAO,
}
    
def get_fixed_template(function_name: str) -> list[dict] | None:
    """
    API công khai: nhận tên chức năng THÔ (bất kỳ biến thể nào AI/OCR sinh
    ra) và trả về BẢN SAO danh sách template cố định tương ứng, hoặc None
    nếu chức năng không thuộc phạm vi đã cố định hoá.
    """
    canonical = normalize_function_name(function_name)
    if canonical is None:
        return None
    template = FUNCTION_KNOWLEDGE.get(canonical)
    if template is None:
        return None
    return [dict(item) for item in template]


def _build_tc(module_display_name: str, item: dict, project_name: str = "", module_base_name: str | None = None) -> dict:
    scenario = item["scenario"]
    expected = item["expected_result"]
    base_name = (module_base_name or module_display_name or "").strip() or module_display_name
    return {
        "id": None,
        "module": base_name,
        "chức năng": base_name,
        "feature": base_name,
        "title": item["title"],
        "scenario": scenario,
        "description": scenario,
        "given": f"Người dùng đang ở màn hình {project_name or 'dự án'}",
        "when": scenario,
        "then": expected,
        "precondition": "Người dùng có quyền truy cập chức năng",
        "steps": f"1. Mở chức năng {module_display_name}\n2. {scenario}\n3. Quan sát kết quả",
        "test_data": "Dữ liệu phù hợp với tình huống kiểm thử",
        "expected_result": expected,
        "priority": "Cao",
        "test_type": item.get("test_type", "Kiểm thử chức năng"),
        "actual_result": "",
        "status": "Chưa chạy",
        "note": "",
    }


def _infer_export_display_base(original_name: str) -> str:
    """Với xuat_file: giữ đúng tên gốc dạng 'Xuất Excel'/'Xuất Word'/'Xuất
    file' thay vì luôn ghi chung 'Xuất file' — để không mất thông tin định
    dạng cụ thể đã phát hiện được từ ảnh/mô tả."""
    n = _norm(original_name)
    if "excel" in n:
        return "Xuất Excel"
    if "word" in n:
        return "Xuất Word"
    if "tải xuống" in n:
        return "Tải xuống file"
    return "Xuất file"


def _tc_key(tc: dict) -> str:
    raw = " | ".join(str(tc.get(k) or "") for k in ("chức năng", "title", "scenario", "expected_result"))
    return re.sub(r"\s+", " ", raw.strip().lower())


_FAILURE_SIGNAL_KEYWORDS = [
    'không thành công', 'thất bại', 'không hợp lệ', 'từ chối', 'không lưu',
    'không thực hiện được', 'không tồn tại', 'không đủ quyền', 'không có quyền',
    'bắt buộc', 'bỏ trống', 'để trống', 'sai định dạng', 'trùng',
    'vượt quá', 'vượt độ dài',
    'xss', 'sql injection', 'sqli', 'injection', 'mã độc',
    'timeout', 'hết thời gian', 'mất mạng', 'mất kết nối',
    'lỗi hệ thống', 'lỗi api', 'lỗi database', 'lỗi kết nối', 'lỗi mạng',
    'hủy', 'huỷ', 'đóng popup', 'không mở được', 'không tìm thấy', 'hết hạn',
    'ngoại lệ', 'không đủ số dư', 'đã tồn tại', 'trạng thái không hợp lệ',
    'lỗi ',
]
_SUCCESS_SIGNAL_KEYWORDS = [
    'thành công', 'hợp lệ', 'hiển thị đúng', 'mở đúng', 'lưu đúng', 'hoạt động đúng',
]
def _classify_item_outcome(item: dict) -> str:
    """Trả về 'success' hoặc 'failure' cho 1 item FUNCTION_KNOWLEDGE, quét
    title + scenario + expected_result — ĐÚNG cùng quy tắc với
    ai_service.py._classify_tc_outcome (xem docstring module ở trên)."""
    text = _norm(' '.join(str(item.get(k) or '') for k in ('title', 'scenario', 'expected_result')))
    if any(kw in text for kw in _FAILURE_SIGNAL_KEYWORDS):
        return 'failure'
    if any(kw in text for kw in _SUCCESS_SIGNAL_KEYWORDS):
        return 'success'
    return 'failure'
def build_testcases_for_module(
    original_module_name: str,
    canonical: str,
    project_name: str = "",
) -> dict[str, list[dict]]:
    """
    Sinh {tên_module_hiển_thị: [testcase...]} từ fixed template ứng với
    canonical đã nhận diện (đọc từ FUNCTION_KNOWLEDGE). 3 nhánh:
      1. canonical trong NO_GROUPING_CANONICALS ("quay_lai"): dùng tên
         hiển thị CHUẨN cố định theo CANONICAL_DISPLAY_NAME để nhiều biến
         thể tên gốc (icon còn sót, "Nút Quay lại", "Back"...) luôn hội tụ
         về ĐÚNG 1 module, không tách thành nhiều module trùng chức năng.
      2. canonical trong NO_OUTCOME_SPLIT_CANONICALS ("sinh_ma", "huy",
         "dong_popup" — theo checklist WEB2519 luôn cố định N kịch bản
         dưới 1 module): lấy thẳng field "module" của item, KHÔNG suy ra
         hậu tố thành công/không thành công.
      3. Các canonical còn lại (Đăng nhập, Đăng ký, Xuất file, Lưu...):
         tên hiển thị = "<tên gốc lấy từ field module, hoặc thay thế
         "<Tên chức năng>" bằng tên gốc phát hiện được cho xuat_file>
         thành công" hoặc "... không thành công", xác định qua
         _classify_item_outcome() quét nội dung title/scenario/
         expected_result của chính item — để mỗi kịch bản thành công/thất
         bại trong template hội tụ về ĐÚNG 2 nhóm hiển thị (dùng để gộp ô
         rowspan ở Preview/Excel), thay vì gộp chung 1 module duy nhất chứa
         lẫn cả 2 loại kịch bản.
    """
    template = FUNCTION_KNOWLEDGE.get(canonical)
    if not template:
        return {}

    result: dict[str, list[dict]] = {}
    for item in template:
        if canonical in NO_GROUPING_CANONICALS:
            display_name = CANONICAL_DISPLAY_NAME.get(canonical, original_module_name)
            base_name = display_name
        elif canonical in NO_OUTCOME_SPLIT_CANONICALS:
            display_name = item.get("module", "") or original_module_name
            base_name = display_name
        else:
            mod_field = item.get("module", "")
            if "<Tên chức năng>" in mod_field:
                base_display = _infer_export_display_base(original_module_name)
            else:
                base_display = mod_field
            # mod_field lấy từ FUNCTION_KNOWLEDGE (vd LOGOUT_SCENARIOS,
            # LOGIN_SCENARIOS...) ĐÃ khai báo cứng sẵn hậu tố "thành công"/
            # "không thành công" ngay trong dữ liệu template tĩnh. Phải tách
            # bỏ hậu tố đó trước khi tự tính lại, nếu không display_name sẽ
            # bị lặp hậu tố 2 lần (vd "Đăng xuất thành công thành công").
            base_display_stripped = base_display.strip()
            for _suffix in (" không thành công", " thành công"):
                if base_display_stripped.lower().endswith(_suffix):
                    base_display_stripped = base_display_stripped[: -len(_suffix)].strip()
                    break
            base_display = base_display_stripped or base_display
            outcome = _classify_item_outcome(item)
            suffix = "thành công" if outcome == "success" else "không thành công"
            display_name = f"{base_display} {suffix}".strip()
            # base_name = tên ĐẦY ĐỦ có hậu tố (display_name), dùng làm
            # tc['module']/tc['chức năng']/tc['feature'] — PHẢI khớp chính
            # xác với key của data['modules'], không phải tên gốc trần trụi.
            base_name = display_name
        tc = _build_tc(display_name, item, project_name, module_base_name=base_name)
        result.setdefault(display_name, []).append(tc)
    return result


def replace_generated_cases_with_template(
    modules: dict,
    enforced_canonicals: frozenset | set | None = None,
    project_name: str = "",
) -> dict:
    """
    Nhận `data["modules"]` hiện tại (dict tên_module -> list TC), trả về
    dict MỚI: với mọi module khớp 1 canonical nằm trong `enforced_canonicals`
    (mặc định = DEFAULT_ENFORCED_CANONICALS), XÓA HẲN nội dung AI sinh ra
    và THAY bằng đúng fixed template — bất kể AI đã sinh bao nhiêu TC,
    đặt tên gì, hay Coverage Checker đã cố bổ sung gì trước đó.
    Các module KHÔNG khớp canonical nào (hoặc canonical thuộc nhóm
    CRUD_FIELD_AWARE_CANONICALS chưa được bật) được giữ NGUYÊN, không đụng
    tới — an toàn cho pipeline hiện có.
    Idempotent: gọi nhiều lần cho cùng input luôn ra cùng kết quả, KHÔNG
    tự nhân đôi TC nếu gọi lặp lại.
    """
    if not isinstance(modules, dict) or not modules:
        return modules
    if enforced_canonicals is None:
        enforced_canonicals = DEFAULT_ENFORCED_CANONICALS
    new_modules: dict[str, list[dict]] = {}
    order: list[str] = []
    for name, tcs in modules.items():
        canonical = normalize_function_name(name)
        if canonical is None or canonical not in enforced_canonicals:
            if name not in new_modules:
                new_modules[name] = tcs if isinstance(tcs, list) else []
                order.append(name)
            continue
        built = build_testcases_for_module(name, canonical, project_name)
        if not built:
            if name not in new_modules:
                new_modules[name] = tcs if isinstance(tcs, list) else []
                order.append(name)
            continue

        for disp_name, disp_tcs in built.items():
            if disp_name not in new_modules:
                new_modules[disp_name] = []
                order.append(disp_name)
            existing_keys = {_tc_key(t) for t in new_modules[disp_name]}
            for tc in disp_tcs:
                k = _tc_key(tc)
                if k in existing_keys:
                    continue
                new_modules[disp_name].append(tc)
                existing_keys.add(k)

    return {name: new_modules[name] for name in order}