"""
ProjectRequest document schema + validation helpers.
"""
from datetime import datetime, timezone

VALID_STATUSES = {"draft", "submitted", "under_review", "approved", "rejected"}


def validate_project_request_payload(data: dict) -> list[str]:
    errors: list[str] = []
    if not (data.get("title") or "").strip():
        errors.append("title is required")
    if not (data.get("description") or "").strip():
        errors.append("description is required")
    if not data.get("deadline"):
        errors.append("deadline is required")
    equipment = data.get("equipment_needed") or []
    if not isinstance(equipment, list) or len(equipment) == 0:
        errors.append("equipment_needed must be a non-empty list")
    return errors


def build_project_request_doc(student_id, data: dict) -> dict:
    now = datetime.now(timezone.utc)
    return {
        "student_id": student_id,
        "title": data["title"].strip(),
        "description": data["description"].strip(),
        "deadline": data["deadline"],
        "equipment_needed": data.get("equipment_needed", []),
        "status": "draft",
        "reviewed_by": None,
        "review_notes": None,
        "ai_recommendation": None,
        "created_at": now,
        "updated_at": now,
    }
