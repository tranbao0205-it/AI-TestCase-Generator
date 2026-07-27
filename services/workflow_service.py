"""Evidence-based workflow linker for arbitrary UI screens."""
from __future__ import annotations
import re
import unicodedata
from typing import Any

class WorkflowService:
    """Link a current screen to a prior screen only when evidence is strong."""

    LINK_THRESHOLD = 0.72

    def find_best_parent(self, previous_context: dict[str, Any] | None, current_screen: dict[str, Any]) -> dict[str, Any]:
        previous_screens = self._extract_screens(previous_context)
        if not previous_screens:
            return {"linked": False, "score": 0.0, "reason": "Không có màn hình trước để so sánh."}
        candidates = [self._score_pair(s, current_screen) for s in previous_screens[-8:]]
        best = max(candidates, key=lambda item: item["score"])
        best["linked"] = best["score"] >= self.LINK_THRESHOLD
        if not best["linked"]:
            original_reason = best.get("reason", "")
            threshold_note = "Điểm liên kết chưa đủ cao; giữ ảnh hiện tại độc lập để tránh ghép sai."
            best["reason"] = f"{original_reason} {threshold_note}".strip() if original_reason else threshold_note
        return best
    def build_context(self, previous_context: dict[str, Any] | None, current_screen: dict[str, Any], relation: dict[str, Any]) -> dict[str, Any]:
        screens = self._extract_screens(previous_context)
        current = dict(current_screen)
        current["screen_id"] = self._next_screen_id(screens)
        if relation.get("linked"):
            current["parent_screen_id"] = relation.get("parent_screen_id")
            current["linked_via_action"] = relation.get("via_action")
        screens.append(current)
        return {"version": 1, "screens": screens[-12:], "last_relation": relation}
    def build_generation_hint(self, relation: dict[str, Any] | None) -> str:
        if relation and relation.get("linked"):
            return (
                "\n=== WORKFLOW LINK — GIỚI HẠN BẰNG CHỨNG ===\n"
                f"- Màn hình hiện tại được mở từ \"{relation.get('parent_title')}\" "
                f"qua hành động \"{relation.get('via_action')}\".\n"
                "- Chỉ dùng màn hình trước để tạo testcase điều hướng/mở màn hình hiện tại.\n"
                "- Field, validation, button, rule và expected result chi tiết phải lấy từ màn hình hiện tại.\n"
                "- Tuyệt đối không sao chép field hoặc rule của màn hình trước sang màn hình hiện tại.\n"
                "================================================\n"
            )
        return (
            "\n=== WORKFLOW LINK ===\n"
            "Không đủ bằng chứng liên kết. Không sử dụng dữ liệu ảnh cũ để suy đoán ảnh hiện tại.\n"
            "=====================\n"
        )

    def _score_pair(self, parent: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
        score = 0.0
        reasons = []
        parent_type = parent.get("screen_type", "unknown")
        current_type = current.get("screen_type", "unknown")
        parent_intents = set(parent.get("action_intents", []))
        current_intents = set(current.get("action_intents", []))
        parent_entity = self._normalize(parent.get("business_entity", ""))
        current_entity = self._normalize(current.get("business_entity", ""))
        parent_title = self._normalize(parent.get("screen_title", ""))
        current_title = self._normalize(current.get("screen_title", ""))

        expected = {
            "modal_form": ("create", "update"),
            "form": ("create", "update", "view"),
            "confirm_popup": ("delete",),
            "list": ("back",),
        }.get(current_type, ())
        available = [a for a in expected if a in parent_intents]
        via_action = self._choose_action(available, current_title, current_intents)
        if via_action:
            score += 0.42
            reasons.append(f"Loại màn hình mới phù hợp hành động {via_action} ở màn hình trước.")
        if parent_entity and current_entity:
            similarity = self._entity_similarity(parent_entity, current_entity)
            score += 0.32 * similarity
            if similarity >= 0.55:
                reasons.append("Đối tượng nghiệp vụ tương đồng.")
        elif parent_entity and parent_entity in current_title:
            score += 0.24
            reasons.append("Tiêu đề màn hình mới chứa đối tượng của màn hình trước.")
        score += 0.08 * self._token_similarity(parent_title, current_title)
        if parent_type == "list" and current_type in {"modal_form", "form", "confirm_popup"}:
            score += 0.12
            reasons.append("Chuyển tiếp List → Form/Popup hợp lý.")
        if current_type == "confirm_popup" and "delete" not in parent_intents:
            score -= 0.30
        if current_type in {"form", "modal_form"} and not ({"create", "update", "view"} & parent_intents):
            score -= 0.25
        if parent_entity and current_entity and self._entity_similarity(parent_entity, current_entity) < 0.15:
            score -= 0.18
        score = round(max(0.0, min(score, 0.99)), 2)
        return {
            "linked": False,
            "score": score,
            "parent_screen_id": parent.get("screen_id"),
            "parent_title": parent.get("screen_title"),
            "via_action": via_action,
            "reason": " ".join(reasons) or "Không có tín hiệu liên kết rõ ràng.",
        }

    def _choose_action(self, actions: list[str], current_title: str, current_intents: set[str]) -> str:
        if not actions:
            return ""
        title_signals = {
            "create": ("them moi", "tao moi", "them", "create", "add"),
            "update": ("cap nhat", "chinh sua", "sua", "update", "edit"),
            "delete": ("xoa", "delete"),
            "view": ("chi tiet", "xem", "view"),
            "back": ("danh sach", "quay lai", "back"),
        }
        for action in actions:
            if action in current_intents or any(signal in current_title for signal in title_signals.get(action, ())):
                return action
        for preferred in ("update", "create", "delete", "view", "back"):
            if preferred in actions:
                return preferred
        return actions[0]

    @staticmethod
    def _next_screen_id(screens: list[dict[str, Any]]) -> str:
        max_num = 0
        for s in screens:
            match = re.match(r"^screen_(\d+)$", str(s.get("screen_id", "")))
            if match:
                max_num = max(max_num, int(match.group(1)))
        return f"screen_{max_num + 1:03d}"

    def _extract_screens(self, context: dict[str, Any] | None) -> list[dict[str, Any]]:
        if not isinstance(context, dict):
            return []
        if isinstance(context.get("screens"), list):
            return [s for s in context["screens"] if isinstance(s, dict)]
        nested = context.get("_workflow_context")
        if isinstance(nested, dict) and isinstance(nested.get("screens"), list):
            return [s for s in nested["screens"] if isinstance(s, dict)]
        return []
    @staticmethod
    def _entity_similarity(a: str, b: str) -> float:
        if a == b:
            return 1.0
        if a in b or b in a:
            return 0.85
        return WorkflowService._token_similarity(a, b)
    @staticmethod
    def _token_similarity(a: str, b: str) -> float:
        aa = {t for t in re.split(r"\W+", a) if len(t) > 1}
        bb = {t for t in re.split(r"\W+", b) if len(t) > 1}
        return len(aa & bb) / len(aa | bb) if aa and bb else 0.0
    @staticmethod
    def _normalize(value: str) -> str:
        text = unicodedata.normalize("NFKD", str(value or ""))
        text = "".join(ch for ch in text if not unicodedata.combining(ch))
        return re.sub(r"\s+", " ", text.lower()).strip()