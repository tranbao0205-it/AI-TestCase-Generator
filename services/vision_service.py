"""Vision normalization for arbitrary UI screenshots.
AIService performs the multimodal scan. This service converts the scan output
into a stable, evidence-based screen model used by workflow linking and test-case
generation. It never hard-codes a project such as warehouse, school, or bank.
"""
from __future__ import annotations
import re
import unicodedata
from typing import Any


class VisionService:
    """Convert scan text into a generic UI screen structure."""

    _CREATE_WORDS = ("thêm mới", "tạo mới", "thêm", "add", "create")
    _UPDATE_WORDS = ("cập nhật", "chỉnh sửa", "sửa", "edit", "update")
    _DELETE_WORDS = ("xóa", "xoá", "delete", "remove")
    _SEARCH_WORDS = ("tìm kiếm", "tìm", "search", "lọc", "filter")
    _BACK_WORDS = ("quay lại", "trở lại", "back")

    _KNOWN_TYPES = (
        "icon-button", "datepicker", "textarea", "dropdown", "checkbox",
        "pagination", "datatable", "button", "input", "radio", "table",
        "modal", "popup", "dialog", "link", "badge", "tab", "heading",
        "label", "note", "alert",
    )

    def analyze_scan(self, scanned: str | None, description: str | None = None) -> dict[str, Any]:
        raw = str(scanned or "").strip()
        description = str(description or "").strip()
        lines = [line.strip() for line in raw.splitlines() if line.strip()]

        title = self._extract_title(lines, description)
        elements = []
        for line in lines:
            if line.lstrip().startswith("-"):
                parsed = self._parse_element_line(line)
                if parsed:
                    elements.append(parsed)

        fields = [e for e in elements if e["type"] in {"input", "textarea", "dropdown", "datepicker", "checkbox", "radio"}]
        buttons = [e for e in elements if e["type"] in {"button", "icon-button", "link"}]
        tables = [e for e in elements if e["type"] in {"table", "datatable", "pagination"}]
        dialogs = [e for e in elements if e["type"] in {"modal", "popup", "dialog"}]
        notes = [e for e in elements if e["type"] in {"note", "alert", "label"}]

        combined = self._normalize("\n".join([title, description, raw]))
        screen_type = self._detect_screen_type(combined, fields, buttons, tables, dialogs)
        entity = self._extract_business_entity(title, fields, combined)
        intents = self._collect_intents(buttons)
        visible_rules = self._extract_visible_rules(raw, fields, notes)

        return {
            "screen_title": title or "Màn hình chưa xác định",
            "screen_type": screen_type,
            "business_entity": entity,
            "elements": elements,
            "fields": fields,
            "buttons": buttons,
            "tables": tables,
            "dialogs": dialogs,
            "notes": notes,
            "action_intents": intents,
            "visible_rules": visible_rules,
            "evidence": self._build_evidence(screen_type, fields, buttons, tables, dialogs, visible_rules),
            "confidence": self._confidence(screen_type, elements, title),
        }

    def build_generation_hint(self, screen: dict[str, Any], relation: dict[str, Any] | None = None) -> str:
        fields = ", ".join(e.get("label", "") for e in screen.get("fields", []) if e.get("label")) or "(không thấy)"
        buttons = ", ".join(e.get("label", "") for e in screen.get("buttons", []) if e.get("label")) or "(không thấy)"
        rules = "; ".join(screen.get("visible_rules", [])) or "(không thấy rule trực tiếp)"
        intents = ", ".join(screen.get("action_intents", [])) or "(không xác định)"

        if relation and relation.get("linked"):
            relation_text = (
                f'- Liên kết workflow: từ "{relation.get("parent_title", "(không rõ)")}" '
                f'qua hành động "{relation.get("via_action", "(không rõ)")}" '
                f'(điểm {relation.get("score", 0):.2f}).\n'
            )
        else:
            relation_text = "- Không có liên kết workflow đủ chắc chắn; không mượn field/rule từ ảnh cũ.\n"

        return (
            "\n=== SCREEN EVIDENCE — NGUỒN SỰ THẬT CHÍNH ===\n"
            f"- Tiêu đề: {screen.get('screen_title')}\n"
            f"- Loại màn hình: {screen.get('screen_type')}\n"
            f"- Đối tượng: {screen.get('business_entity') or '(chưa xác định)'}\n"
            f"- Field nhìn thấy: {fields}\n"
            f"- Nút/hành động nhìn thấy: {buttons}\n"
            f"- Action intent: {intents}\n"
            f"- Rule nhìn thấy trực tiếp: {rules}\n"
            f"{relation_text}"
            "- Field, validation, button và business rule chi tiết phải lấy từ ẢNH HIỆN TẠI.\n"
            "- Màn hình trước chỉ được dùng để xác định điểm bắt đầu và hành động điều hướng.\n"
            "- Không tự thêm field, popup, ràng buộc hoặc kết quả nghiệp vụ không có bằng chứng.\n"
            "=================================================\n"
        )

    def _extract_title(self, lines: list[str], description: str) -> str:
        for line in lines:
            match = re.match(r"(?:PROJECT_NAME|SCREEN_TITLE|TITLE)\s*:\s*(.+)", line, re.I)
            if match:
                return match.group(1).strip()
        if description and len(description) <= 80 and not re.search(r"\b(tạo|sinh|viết)\s+(test|tc)", description, re.I):
            return description.strip()
        return ""

    def _parse_element_line(self, line: str) -> dict[str, Any] | None:
        text = line.lstrip("- ").strip()
        if not text:
            return None
        parts = [p.strip() for p in text.split("|") if p.strip()]
        if not parts:
            return None
        type_index = None
        type_name = "unknown"
        for idx, part in enumerate(parts):
            normalized = self._normalize(part)
            for candidate in self._KNOWN_TYPES:
                if normalized == candidate:
                    type_index = idx
                    type_name = candidate
                    break
            if type_index is not None:
                break

        label_candidates = [p for i, p in enumerate(parts) if i != type_index and not self._looks_like_metadata(p)]
        label = label_candidates[0] if label_candidates else parts[0]
        metadata = " | ".join(parts)
        normalized_label = self._normalize(label)
        normalized_meta = self._normalize(metadata)
        intent = self._intent_from_metadata(normalized_meta) or self._detect_intent(normalized_label)
        required = bool(re.search(r"\*|required|bắt buộc", metadata, re.I))

        return {
            "label": label,
            "type": type_name,
            "intent": intent,
            "required": required,
            "raw": text,
        }

    def _looks_like_metadata(self, part: str) -> bool:
        p = self._normalize(part)
        return bool(re.match(r"^(action|intent|type|required|placeholder|color|role)\s*=", p))

    def _intent_from_metadata(self, normalized_meta: str) -> str:
        match = re.search(r"(?:action|intent)\s*=\s*([a-z_ -]+)", normalized_meta)
        if not match:
            return ""
        value = match.group(1).strip().replace("-", "_").replace(" ", "_")
        aliases = {
            "edit": "update", "remove": "delete", "add": "create",
            "close_popup": "close", "cancel": "close", "generate_code": "generate_code",
            "export_excel": "export_excel", "export_word": "export_word",
            "export_pdf": "export_pdf", "export_csv": "export_csv",
        }
        return aliases.get(value, value)

    def _detect_screen_type(self, combined: str, fields: list[dict], buttons: list[dict], tables: list[dict], dialogs: list[dict]) -> str:
        has_table = bool(tables) or any(word in combined for word in ("stt", "danh sách", "phan trang", "tổng số", "dong du lieu"))
        business_fields = [f for f in fields if f.get("intent") != "search"]
        has_submit = any(b.get("intent") in {"save", "create", "update", "save_and_continue"} for b in buttons)
        has_delete_confirm = any(word in combined for word in ("ban co chac", "xac nhan xoa", "dong y xoa"))
        has_modal = bool(dialogs) or any(word in combined for word in ("modal", "popup", "dialog", "dong popup", "huy bo"))

        if has_delete_confirm:
            return "confirm_popup"
        if has_table and len(business_fields) < 2:
            return "list"
        if has_modal and business_fields and has_submit:
            return "modal_form"
        if business_fields and has_submit:
            return "form"
        if has_table:
            return "list"
        if fields:
            return "form"
        return "unknown"

    def _extract_business_entity(self, title: str, fields: list[dict], combined: str) -> str:
        title_norm = self._normalize(title)
        title_norm = re.sub(r"\b(danh muc|danh sach|quan ly|them moi|tao moi|cap nhat|chinh sua|chi tiet|xac nhan)\b", " ", title_norm)
        title_norm = re.sub(r"\s+", " ", title_norm).strip()
        if title_norm and title_norm not in {"them", "moi", "them moi"}:
            return title_norm

        candidates = []
        for field in fields:
            label = self._normalize(field.get("label", ""))
            label = re.sub(r"\b(ma|ten|ghi chu|ngay|trang thai)\b", " ", label)
            label = re.sub(r"[^a-z0-9 _-]", " ", label)
            label = re.sub(r"\s+", " ", label).strip()
            if label:
                candidates.append(label)
        if candidates:
            return max(candidates, key=len)
        match = re.search(r"\b(?:ma|ten)\s+([a-z0-9 _-]{2,40})", combined)
        return match.group(1).strip() if match else ""

    def _collect_intents(self, buttons: list[dict]) -> list[str]:
        return sorted({b.get("intent") for b in buttons if b.get("intent")})

    def _detect_intent(self, label: str) -> str:
        if "them moi va tiep tuc" in label or "save and continue" in label:
            return "save_and_continue"
        if "sinh ma" in label or "tao ma" in label:
            return "generate_code"
        if any(self._normalize(w) in label for w in self._BACK_WORDS):
            return "back"
        if any(word in label for word in ("xuat excel", "export excel")):
            return "export_excel"
        if any(word in label for word in ("xuat word", "export word")):
            return "export_word"
        if any(word in label for word in ("xuat pdf", "export pdf")):
            return "export_pdf"
        if any(word in label for word in ("xuat csv", "export csv")):
            return "export_csv"
        if any(self._normalize(w) in label for w in self._SEARCH_WORDS):
            return "search"
        if any(self._normalize(w) in label for w in self._DELETE_WORDS):
            return "delete"
        if any(self._normalize(w) in label for w in self._UPDATE_WORDS):
            return "update"
        if any(self._normalize(w) in label for w in self._CREATE_WORDS):
            return "create"
        if label in {"luu", "save", "dong y", "xac nhan"}:
            return "save"
        if label in {"x", "dong", "close", "huy", "huy bo"}:
            return "close"
        return ""

    def _extract_visible_rules(self, raw: str, fields: list[dict], notes: list[dict]) -> list[str]:
        rules = []
        for field in fields:
            if field.get("required"):
                rules.append(f"{field.get('label')} là trường bắt buộc")
        normalized = self._normalize(raw)
        if "de trong" in normalized and ("tu dong tao ma" in normalized or "tu dong sinh ma" in normalized):
            rules.append("Để trống trường mã thì hệ thống tự động sinh mã")
        for note in notes:
            label = str(note.get("label") or "").strip()
            if label:
                rules.append(label)
        return list(dict.fromkeys(rules))

    def _build_evidence(self, screen_type, fields, buttons, tables, dialogs, rules):
        values = [f"screen_type={screen_type}"]
        for name, items in (("fields", fields), ("buttons", buttons), ("tables", tables), ("dialogs", dialogs), ("rules", rules)):
            if items:
                values.append(f"{name}={len(items)}")
        return values

    def _confidence(self, screen_type: str, elements: list[dict], title: str) -> float:
        score = 0.30 + (0.15 if title else 0) + min(0.35, len(elements) * 0.035) + (0.20 if screen_type != "unknown" else 0)
        return round(min(score, 0.99), 2)

    @staticmethod
    def _normalize(value: str) -> str:
        text = unicodedata.normalize("NFKD", str(value or ""))
        text = "".join(ch for ch in text if not unicodedata.combining(ch))
        return re.sub(r"\s+", " ", text.lower()).strip()
