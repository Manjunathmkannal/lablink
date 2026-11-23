"""
Equipment service – CRUD, search, filter, pagination.
All DB calls go through mongo.db so they can be patched in tests.
"""
from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId
from pymongo import ASCENDING, TEXT

from ..extensions import mongo
from ..models.equipment import (
    build_equipment_doc,
    validate_equipment_payload,
    VALID_STATUSES,
    VALID_CONDITIONS,
)


class EquipmentNotFoundError(Exception):
    pass


class EquipmentDeleteError(Exception):
    """Raised when deletion is blocked (e.g. active bookings)."""
    pass


# ── Helpers ────────────────────────────────────────────────────────────────────

def _oid(val) -> Optional[ObjectId]:
    if not val:
        return None
    try:
        return ObjectId(str(val))
    except Exception:
        return None


# ── Read ───────────────────────────────────────────────────────────────────────

def list_equipment(
    search: str = "",
    department_id: str = "",
    lab_id: str = "",
    category: str = "",
    status: str = "",
    condition: str = "",
    page: int = 1,
    per_page: int = 20,
) -> dict:
    """
    Offset-paginated equipment listing with optional search and filters.
    Returns {"items": [...], "total": int, "page": int, "per_page": int, "pages": int}.
    """
    query: dict = {}

    # Full-text search on name / description / tags (text index)
    if search and search.strip():
        query["$text"] = {"$search": search.strip()}

    if department_id and _oid(department_id):
        query["department_id"] = _oid(department_id)
    if lab_id and _oid(lab_id):
        query["lab_id"] = _oid(lab_id)
    if category and category.strip():
        query["category"] = {"$regex": category.strip(), "$options": "i"}
    if status and status in VALID_STATUSES:
        query["status"] = status
    if condition and condition in VALID_CONDITIONS:
        query["condition"] = condition

    page = max(1, page)
    per_page = min(max(1, per_page), 100)

    total = mongo.db.equipment.count_documents(query)
    items = list(
        mongo.db.equipment
        .find(query)
        .sort("name", ASCENDING)
        .skip((page - 1) * per_page)
        .limit(per_page)
    )
    from math import ceil
    return {
        "items": items,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": ceil(total / per_page) if total else 0,
    }


def get_equipment(equipment_id: str) -> dict:
    oid = _oid(equipment_id)
    if not oid:
        raise EquipmentNotFoundError("Invalid equipment ID")
    doc = mongo.db.equipment.find_one({"_id": oid})
    if not doc:
        raise EquipmentNotFoundError("Equipment not found")
    return doc


# ── Write ──────────────────────────────────────────────────────────────────────

def create_equipment(data: dict) -> dict:
    errors = validate_equipment_payload(data)
    if errors:
        raise ValueError("; ".join(errors))

    # Resolve ObjectId references
    if data.get("department_id"):
        data["department_id"] = _oid(data["department_id"])
    if data.get("lab_id"):
        data["lab_id"] = _oid(data["lab_id"])

    doc = build_equipment_doc(data)
    result = mongo.db.equipment.insert_one(doc)
    doc["_id"] = result.inserted_id
    return doc


def update_equipment(equipment_id: str, data: dict) -> dict:
    oid = _oid(equipment_id)
    if not oid:
        raise EquipmentNotFoundError("Invalid equipment ID")
    existing = mongo.db.equipment.find_one({"_id": oid})
    if not existing:
        raise EquipmentNotFoundError("Equipment not found")

    allowed_fields = {
        "name", "description", "category", "condition", "status",
        "image_url", "specifications", "tags", "quantity_total",
    }
    update: dict = {}
    for field in allowed_fields:
        if field in data:
            update[field] = data[field]

    # If quantity_total changes, recalculate quantity_available
    if "quantity_total" in update:
        new_total = int(update["quantity_total"])
        booked_count = existing["quantity_total"] - existing.get("quantity_available", existing["quantity_total"])
        new_available = max(0, new_total - booked_count)
        update["quantity_available"] = new_available
        update["quantity_total"] = new_total

    if not update:
        return existing

    update["updated_at"] = datetime.now(timezone.utc)
    # Resolve ObjectId references if present
    if "department_id" in data:
        update["department_id"] = _oid(data["department_id"])
    if "lab_id" in data:
        update["lab_id"] = _oid(data["lab_id"])

    mongo.db.equipment.update_one({"_id": oid}, {"$set": update})
    return mongo.db.equipment.find_one({"_id": oid})


def delete_equipment(equipment_id: str) -> None:
    oid = _oid(equipment_id)
    if not oid:
        raise EquipmentNotFoundError("Invalid equipment ID")
    if not mongo.db.equipment.find_one({"_id": oid}):
        raise EquipmentNotFoundError("Equipment not found")

    # Block deletion if active/pending/approved bookings exist
    active_booking = mongo.db.bookings.find_one(
        {
            "equipment_id": oid,
            "status": {"$in": ["pending", "approved", "active"]},
        }
    )
    if active_booking:
        raise EquipmentDeleteError(
            "Cannot delete equipment with active, pending, or approved bookings"
        )

    mongo.db.equipment.delete_one({"_id": oid})


def update_condition(equipment_id: str, condition: str, status: str = None) -> dict:
    """Lab-assistant operation: update condition and optionally status."""
    oid = _oid(equipment_id)
    if not oid:
        raise EquipmentNotFoundError("Invalid equipment ID")
    if condition not in VALID_CONDITIONS:
        raise ValueError(f"condition must be one of {sorted(VALID_CONDITIONS)}")
    update: dict = {"condition": condition, "updated_at": datetime.now(timezone.utc)}
    if status:
        if status not in VALID_STATUSES:
            raise ValueError(f"status must be one of {sorted(VALID_STATUSES)}")
        update["status"] = status
    result = mongo.db.equipment.find_one_and_update(
        {"_id": oid}, {"$set": update}, return_document=True
    )
    if not result:
        raise EquipmentNotFoundError("Equipment not found")
    return result
