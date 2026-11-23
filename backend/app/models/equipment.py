"""
Equipment document schema + validation helpers.
"""
from datetime import datetime, timezone
from typing import Optional

VALID_CONDITIONS = {"good", "fair", "poor"}
VALID_STATUSES = {"available", "booked", "maintenance", "retired"}


def validate_equipment_payload(data: dict) -> list[str]:
    errors: list[str] = []
    if not (data.get("name") or "").strip():
        errors.append("name is required")
    if not (data.get("category") or "").strip():
        errors.append("category is required")
    qty = data.get("quantity_total")
    if qty is None:
        errors.append("quantity_total is required")
    elif not isinstance(qty, int) or qty < 1:
        errors.append("quantity_total must be a positive integer")
    condition = data.get("condition", "good")
    if condition not in VALID_CONDITIONS:
        errors.append(f"condition must be one of {sorted(VALID_CONDITIONS)}")
    return errors


def build_equipment_doc(data: dict) -> dict:
    now = datetime.now(timezone.utc)
    qty = int(data["quantity_total"])
    return {
        "name": data["name"].strip(),
        "description": (data.get("description") or "").strip(),
        "category": data["category"].strip(),
        "lab_id": data.get("lab_id"),
        "department_id": data.get("department_id"),
        "serial_number": (data.get("serial_number") or "").strip() or None,
        "quantity_total": qty,
        "quantity_available": qty,
        "condition": data.get("condition", "good"),
        "status": "available",
        "image_url": (data.get("image_url") or "").strip() or None,
        "specifications": data.get("specifications") or {},
        "tags": data.get("tags") or [],
        "created_at": now,
        "updated_at": now,
    }
