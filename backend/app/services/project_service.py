"""
Project request service – CRUD + faculty review workflow.
"""
from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId
from pymongo import DESCENDING

from ..extensions import mongo
from ..models.project_request import (
    build_project_request_doc,
    validate_project_request_payload,
    VALID_STATUSES,
)


class ProjectNotFoundError(Exception):
    pass


class ProjectError(Exception):
    pass


# ── Helpers ────────────────────────────────────────────────────────────────────

def _oid(val) -> Optional[ObjectId]:
    if not val:
        return None
    try:
        return ObjectId(str(val))
    except Exception:
        return None


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ── Create ─────────────────────────────────────────────────────────────────────

def create_project_request(student_id: str, data: dict) -> dict:
    errors = validate_project_request_payload(data)
    if errors:
        raise ProjectError("; ".join(errors))

    # Parse deadline
    deadline = data.get("deadline")
    if isinstance(deadline, str):
        try:
            deadline = deadline.replace("Z", "+00:00")
            deadline = datetime.fromisoformat(deadline)
            if deadline.tzinfo is None:
                deadline = deadline.replace(tzinfo=timezone.utc)
        except ValueError:
            raise ProjectError("Invalid deadline format; use ISO 8601")

    doc = build_project_request_doc(ObjectId(student_id), {
        **data,
        "deadline": deadline,
    })
    result = mongo.db.project_requests.insert_one(doc)
    doc["_id"] = result.inserted_id
    return doc


# ── Read ───────────────────────────────────────────────────────────────────────

def list_project_requests(
    student_id: str = None,
    status: str = None,
    page: int = 1,
    per_page: int = 20,
) -> dict:
    from math import ceil
    query: dict = {}
    if student_id:
        query["student_id"] = ObjectId(student_id)
    if status and status in VALID_STATUSES:
        query["status"] = status

    page = max(1, page)
    per_page = min(max(1, per_page), 100)
    total = mongo.db.project_requests.count_documents(query)
    items = list(
        mongo.db.project_requests.find(query)
        .sort("created_at", DESCENDING)
        .skip((page - 1) * per_page)
        .limit(per_page)
    )
    return {
        "items": items,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": ceil(total / per_page) if total else 0,
    }


def get_project_request(request_id: str) -> dict:
    oid = _oid(request_id)
    if not oid:
        raise ProjectNotFoundError("Invalid project request ID")
    doc = mongo.db.project_requests.find_one({"_id": oid})
    if not doc:
        raise ProjectNotFoundError("Project request not found")
    return doc


# ── Update (student – draft only) ─────────────────────────────────────────────

def update_project_request(request_id: str, student_id: str, data: dict) -> dict:
    doc = get_project_request(request_id)
    if str(doc["student_id"]) != student_id:
        raise ProjectError("You can only update your own project requests")
    if doc["status"] != "draft":
        raise ProjectError("Only draft requests can be edited")

    allowed = {"title", "description", "deadline", "equipment_needed"}
    update: dict = {k: v for k, v in data.items() if k in allowed and v is not None}
    if "deadline" in update and isinstance(update["deadline"], str):
        try:
            dl = update["deadline"].replace("Z", "+00:00")
            dl = datetime.fromisoformat(dl)
            if dl.tzinfo is None:
                dl = dl.replace(tzinfo=timezone.utc)
            update["deadline"] = dl
        except ValueError:
            raise ProjectError("Invalid deadline format")

    if not update:
        return doc

    update["updated_at"] = _now()
    mongo.db.project_requests.update_one({"_id": doc["_id"]}, {"$set": update})
    return mongo.db.project_requests.find_one({"_id": doc["_id"]})


# ── Submit (student) ───────────────────────────────────────────────────────────

def submit_project_request(request_id: str, student_id: str) -> dict:
    doc = get_project_request(request_id)
    if str(doc["student_id"]) != student_id:
        raise ProjectError("You can only submit your own project requests")
    if doc["status"] != "draft":
        raise ProjectError("Only draft requests can be submitted")
    mongo.db.project_requests.update_one(
        {"_id": doc["_id"]},
        {"$set": {"status": "submitted", "updated_at": _now()}},
    )
    doc["status"] = "submitted"
    return doc


# ── Faculty review ─────────────────────────────────────────────────────────────

def review_project_request(
    request_id: str,
    reviewer_id: str,
    decision: str,
    notes: str = "",
) -> dict:
    if decision not in {"approved", "rejected"}:
        raise ProjectError("decision must be 'approved' or 'rejected'")
    if decision == "rejected" and not (notes or "").strip():
        raise ProjectError("review_notes are required when rejecting a request")

    doc = get_project_request(request_id)
    if doc["status"] not in {"submitted", "under_review"}:
        raise ProjectError(
            f"Cannot review a request with status '{doc['status']}'"
        )

    mongo.db.project_requests.update_one(
        {"_id": doc["_id"]},
        {
            "$set": {
                "status": decision,
                "reviewed_by": ObjectId(reviewer_id),
                "review_notes": (notes or "").strip(),
                "updated_at": _now(),
            }
        },
    )
    doc["status"] = decision
    doc["review_notes"] = (notes or "").strip()
    return doc
