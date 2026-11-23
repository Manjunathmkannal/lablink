"""
/api/lab  –  Lab assistant: view assigned equipment, update condition/status,
              manage handovers and returns.
"""
from datetime import datetime, timezone
from flask import Blueprint, request, jsonify, g
from bson import ObjectId

from ..utils.jwt_utils import jwt_required, role_required
from ..utils.json_utils import mongo_to_json
from ..extensions import mongo
from ..services.equipment_service import (
    update_condition,
    EquipmentNotFoundError,
)

lab_bp = Blueprint("lab", __name__)


# ── GET /api/lab/equipment  ───────────────────────────────────────────────────
@lab_bp.route("/equipment", methods=["GET"])
@jwt_required
@role_required("lab_assistant", "admin")
def list_equipment():
    """
    Lab assistant sees equipment assigned to their lab.
    Admin can see all.
    Query params: lab_id (admin only override), status, condition.
    """
    args = request.args
    role = g.current_role
    query: dict = {}

    if role == "lab_assistant":
        # Determine which lab(s) the assistant is assigned to
        user = mongo.db.users.find_one({"_id": ObjectId(g.current_user_id)})
        # Find labs whose assigned_assistant_id matches this user
        labs = list(
            mongo.db.laboratories.find(
                {"assigned_assistant_id": ObjectId(g.current_user_id)}
            )
        )
        if labs:
            lab_ids = [lab["_id"] for lab in labs]
            query["lab_id"] = {"$in": lab_ids}
        # If no specific labs assigned, show by department
        elif user and user.get("department_id"):
            query["department_id"] = user["department_id"]
    elif args.get("lab_id"):
        try:
            query["lab_id"] = ObjectId(args["lab_id"])
        except Exception:
            return jsonify({"error": "Invalid lab_id"}), 400

    if args.get("status"):
        query["status"] = args["status"]
    if args.get("condition"):
        query["condition"] = args["condition"]

    items = list(mongo.db.equipment.find(query).sort("name", 1))
    return jsonify({"items": mongo_to_json(items), "total": len(items)})


# ── PUT /api/lab/equipment/<id>/condition  ────────────────────────────────────
@lab_bp.route("/equipment/<equipment_id>/condition", methods=["PUT"])
@jwt_required
@role_required("lab_assistant", "admin")
def update_eq_condition(equipment_id):
    """Update equipment condition and optionally status."""
    data = request.get_json(silent=True) or {}
    condition = data.get("condition")
    status = data.get("status")
    if not condition:
        return jsonify({"error": "condition is required"}), 400
    try:
        doc = update_condition(equipment_id, condition, status)
    except EquipmentNotFoundError as e:
        return jsonify({"error": str(e)}), 404
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"message": "Equipment updated", "equipment": mongo_to_json(doc)})


# ── PUT /api/lab/equipment/<id>/status  ───────────────────────────────────────
@lab_bp.route("/equipment/<equipment_id>/status", methods=["PUT"])
@jwt_required
@role_required("lab_assistant", "admin")
def update_eq_status(equipment_id):
    """Set equipment status to available | maintenance | retired."""
    data = request.get_json(silent=True) or {}
    new_status = (data.get("status") or "").strip()
    from ..models.equipment import VALID_STATUSES
    if not new_status or new_status not in VALID_STATUSES:
        return jsonify({"error": f"status must be one of {sorted(VALID_STATUSES)}"}), 400

    try:
        oid = ObjectId(equipment_id)
    except Exception:
        return jsonify({"error": "Invalid equipment ID"}), 400

    result = mongo.db.equipment.find_one_and_update(
        {"_id": oid},
        {"$set": {"status": new_status, "updated_at": datetime.now(timezone.utc)}},
        return_document=True,
    )
    if not result:
        return jsonify({"error": "Equipment not found"}), 404
    return jsonify({"message": "Status updated", "equipment": mongo_to_json(result)})


# ── GET /api/lab/handovers  ───────────────────────────────────────────────────
@lab_bp.route("/handovers", methods=["GET"])
@jwt_required
@role_required("lab_assistant", "admin")
def list_handovers():
    """
    Active bookings in the lab assistant's assigned labs.
    These represent equipment currently handed out or due for return.
    """
    query: dict = {"status": {"$in": ["approved", "active"]}}

    if g.current_role == "lab_assistant":
        labs = list(
            mongo.db.laboratories.find(
                {"assigned_assistant_id": ObjectId(g.current_user_id)}
            )
        )
        if labs:
            lab_ids = [lab["_id"] for lab in labs]
            query["lab_id"] = {"$in": lab_ids}

    bookings = list(
        mongo.db.bookings.find(query).sort("start_time", 1).limit(100)
    )
    return jsonify({"handovers": mongo_to_json(bookings), "count": len(bookings)})


# ── POST /api/lab/handovers/<booking_id>/return  ─────────────────────────────
@lab_bp.route("/handovers/<booking_id>/return", methods=["POST"])
@jwt_required
@role_required("lab_assistant", "admin")
def mark_return(booking_id):
    """Mark an active/approved booking as completed (equipment returned)."""
    try:
        oid = ObjectId(booking_id)
    except Exception:
        return jsonify({"error": "Invalid booking ID"}), 400

    booking = mongo.db.bookings.find_one({"_id": oid})
    if not booking:
        return jsonify({"error": "Booking not found"}), 404
    if booking["status"] not in {"approved", "active"}:
        return jsonify({"error": f"Cannot mark return for status '{booking['status']}'"}), 400

    now = datetime.now(timezone.utc)
    mongo.db.bookings.update_one(
        {"_id": oid},
        {"$set": {"status": "completed", "updated_at": now}},
    )

    # Create a maintenance record note
    data = request.get_json(silent=True) or {}
    if data.get("condition_note"):
        mongo.db.maintenance_records.insert_one({
            "equipment_id": booking["equipment_id"],
            "reported_by": ObjectId(g.current_user_id),
            "issue_description": data["condition_note"],
            "status": "reported",
            "resolved_by": None,
            "resolved_at": None,
            "created_at": now,
        })

    return jsonify({"message": "Equipment return recorded", "booking_id": booking_id})


# ── GET /api/lab/maintenance  ─────────────────────────────────────────────────
@lab_bp.route("/maintenance", methods=["GET"])
@jwt_required
@role_required("lab_assistant", "admin")
def list_maintenance():
    """List all open maintenance records."""
    records = list(
        mongo.db.maintenance_records.find(
            {"status": {"$in": ["reported", "in_progress"]}}
        ).sort("created_at", -1)
    )
    return jsonify({"maintenance_records": mongo_to_json(records), "count": len(records)})


# ── PUT /api/lab/maintenance/<record_id>/resolve  ─────────────────────────────
@lab_bp.route("/maintenance/<record_id>/resolve", methods=["PUT"])
@jwt_required
@role_required("lab_assistant", "admin")
def resolve_maintenance(record_id):
    """Mark a maintenance record as resolved."""
    try:
        oid = ObjectId(record_id)
    except Exception:
        return jsonify({"error": "Invalid record ID"}), 400

    now = datetime.now(timezone.utc)
    result = mongo.db.maintenance_records.find_one_and_update(
        {"_id": oid},
        {
            "$set": {
                "status": "resolved",
                "resolved_by": ObjectId(g.current_user_id),
                "resolved_at": now,
            }
        },
        return_document=True,
    )
    if not result:
        return jsonify({"error": "Maintenance record not found"}), 404
    return jsonify({"message": "Maintenance resolved", "record": mongo_to_json(result)})
