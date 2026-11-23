"""
Booking document schema + validation helpers.
Phase 2: Extended with project fields.
"""
from datetime import datetime, timezone
from typing import Optional

VALID_STATUSES = {"pending", "approved", "rejected", "active", "completed", "cancelled"}


def validate_booking_payload(data: dict) -> list[str]:
    errors: list[str] = []
    if not data.get("equipment_id"):
        errors.append("equipment_id is required")
    if not data.get("start_time"):
        errors.append("start_time is required")
    if not data.get("end_time"):
        errors.append("end_time is required")
    if not (data.get("purpose") or "").strip():
        errors.append("purpose is required")

    start = data.get("start_time")
    end = data.get("end_time")
    if start and end:
        if not isinstance(start, datetime) or not isinstance(end, datetime):
            errors.append("start_time and end_time must be datetime objects")
        elif end <= start:
            errors.append("end_time must be after start_time")
        elif (end - start).total_seconds() > 24 * 3600:
            errors.append("booking duration cannot exceed 24 hours")
    return errors


def build_booking_doc(
    student_id,
    equipment_id,
    lab_id,
    start_time: datetime,
    end_time: datetime,
    purpose: str,
    # Phase 2 extended fields
    department_id=None,
    project_title: Optional[str] = None,
    project_description: Optional[str] = None,
    project_deadline: Optional[datetime] = None,
    faculty_id=None,
    project_request_id=None,
) -> dict:
    now = datetime.now(timezone.utc)
    return {
        "student_id": student_id,
        "equipment_id": equipment_id,
        "lab_id": lab_id,
        "department_id": department_id,
        "start_time": start_time,
        "end_time": end_time,
        "purpose": purpose.strip(),
        "project_title": (project_title or "").strip() or None,
        "project_description": (project_description or "").strip() or None,
        "project_deadline": project_deadline,
        "status": "pending",
        "faculty_id": faculty_id,
        "approval_notes": None,
        "approved_by": None,
        "rejection_reason": None,
        "project_request_id": project_request_id,
        "created_at": now,
        "updated_at": now,
    }
