"""
/api/equipment  –  GET list, GET detail, GET availability, POST, PUT, DELETE
"""
from datetime import datetime
from flask import Blueprint, request, jsonify, g
from bson import ObjectId

from ..extensions import mongo
from ..utils.jwt_utils import jwt_required, role_required
from ..utils.json_utils import mongo_to_json
from ..utils.validators import is_valid_object_id
from ..services.equipment_service import (
    list_equipment,
    get_equipment,
    create_equipment,
    update_equipment,
    delete_equipment,
    update_condition,
    EquipmentNotFoundError,
    EquipmentDeleteError,
)

equipment_bp = Blueprint("equipment", __name__)


# ── GET /api/equipment  ────────────────────────────────────────────────────────
@equipment_bp.route("/", methods=["GET"])
@jwt_required
def list_eq():
    """
    Query params:
      search, department_id, lab_id, category, status, condition
      page (default 1), per_page (default 20, max 100)
    """
    args = request.args
    result = list_equipment(
        search=args.get("search", ""),
        department_id=args.get("department_id", ""),
        lab_id=args.get("lab_id", ""),
        category=args.get("category", ""),
        status=args.get("status", ""),
        condition=args.get("condition", ""),
        page=int(args.get("page", 1)),
        per_page=int(args.get("per_page", 20)),
    )
    return jsonify(mongo_to_json(result))


# ── GET /api/equipment/<id>  ───────────────────────────────────────────────────
@equipment_bp.route("/<equipment_id>", methods=["GET"])
@jwt_required
def get_eq(equipment_id):
    try:
        doc = get_equipment(equipment_id)
    except EquipmentNotFoundError as e:
        return jsonify({"error": str(e)}), 404
    return jsonify(mongo_to_json(doc))


# ── GET /api/equipment/<id>/availability  ─────────────────────────────────────
@equipment_bp.route("/<equipment_id>/availability", methods=["GET"])
@jwt_required
def get_availability(equipment_id):
    """
    Query params:
      view: day | week | month  (default: week)
      date: YYYY-MM-DD reference date  (default: today UTC)
    """
    from datetime import timedelta, date
    from ..services.booking_service import get_availability as _get_avail

    # Validate equipment exists
    try:
        equip = get_equipment(equipment_id)
    except EquipmentNotFoundError as e:
        return jsonify({"error": str(e)}), 404

    view = request.args.get("view", "week").lower()
    date_str = request.args.get("date", "")

    from datetime import timezone as tz
    try:
        if date_str:
            ref_date = date.fromisoformat(date_str)
        else:
            ref_date = datetime.now(tz.utc).date()
    except ValueError:
        return jsonify({"error": "Invalid date format, use YYYY-MM-DD"}), 400

    from datetime import datetime as dt
    if view == "day":
        range_start = dt(ref_date.year, ref_date.month, ref_date.day, tzinfo=tz.utc)
        range_end = range_start + timedelta(days=1)
    elif view == "month":
        import calendar
        last_day = calendar.monthrange(ref_date.year, ref_date.month)[1]
        range_start = dt(ref_date.year, ref_date.month, 1, tzinfo=tz.utc)
        range_end = dt(ref_date.year, ref_date.month, last_day, 23, 59, 59, tzinfo=tz.utc)
    else:  # week (default)
        # Week starts on Monday of ref_date's week
        monday = ref_date - timedelta(days=ref_date.weekday())
        range_start = dt(monday.year, monday.month, monday.day, tzinfo=tz.utc)
        range_end = range_start + timedelta(days=7)

    bookings = _get_avail(equipment_id, range_start, range_end)

    # Suggest up to 3 free 2-hour slots in the range
    suggestions = _suggest_free_slots(bookings, range_start, range_end)

    # Maintenance records in range
    maint = list(
        mongo.db.maintenance_records.find(
            {
                "equipment_id": ObjectId(equipment_id),
                "status": {"$in": ["reported", "in_progress"]},
            }
        )
    )

    return jsonify({
        "equipment": mongo_to_json(equip),
        "view": view,
        "range_start": range_start.isoformat(),
        "range_end": range_end.isoformat(),
        "bookings": mongo_to_json(bookings),
        "maintenance": mongo_to_json(maint),
        "suggested_slots": suggestions,
    })


def _suggest_free_slots(bookings: list, range_start, range_end) -> list:
    """Return up to 3 free 2-hour slots not overlapping any existing booking."""
    from datetime import timedelta
    slot_duration = timedelta(hours=2)
    candidate = range_start
    suggestions = []
    booked_intervals = [(b["start_time"], b["end_time"]) for b in bookings]

    while candidate + slot_duration <= range_end and len(suggestions) < 3:
        overlaps = any(
            s < candidate + slot_duration and e > candidate
            for s, e in booked_intervals
        )
        if not overlaps:
            suggestions.append({
                "start": candidate.isoformat(),
                "end": (candidate + slot_duration).isoformat(),
            })
            candidate += slot_duration
        else:
            # Jump to end of the overlapping booking
            blocking_end = max(
                e for s, e in booked_intervals
                if s < candidate + slot_duration and e > candidate
            )
            candidate = blocking_end
    return suggestions


# ── POST /api/equipment  ───────────────────────────────────────────────────────
@equipment_bp.route("/", methods=["POST"])
@jwt_required
@role_required("admin")
def create_eq():
    data = request.get_json(silent=True) or {}
    try:
        doc = create_equipment(data)
    except ValueError as e:
        return jsonify({"errors": str(e).split("; ")}), 400
    return jsonify({"message": "Equipment created", "equipment": mongo_to_json(doc)}), 201


# ── PUT /api/equipment/<id>  ───────────────────────────────────────────────────
@equipment_bp.route("/<equipment_id>", methods=["PUT"])
@jwt_required
def update_eq(equipment_id):
    role = g.current_role
    data = request.get_json(silent=True) or {}

    # Lab assistant may only update condition / status
    if role == "lab_assistant":
        condition = data.get("condition")
        status = data.get("status")
        if not condition:
            return jsonify({"error": "condition is required"}), 400
        try:
            doc = update_condition(equipment_id, condition, status)
        except (EquipmentNotFoundError, ValueError) as e:
            status_code = 404 if isinstance(e, EquipmentNotFoundError) else 400
            return jsonify({"error": str(e)}), status_code
        return jsonify({"message": "Equipment updated", "equipment": mongo_to_json(doc)})

    # Admin may do full update
    if role != "admin":
        return jsonify({"error": "Forbidden: insufficient role"}), 403

    try:
        doc = update_equipment(equipment_id, data)
    except EquipmentNotFoundError as e:
        return jsonify({"error": str(e)}), 404
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"message": "Equipment updated", "equipment": mongo_to_json(doc)})


# ── DELETE /api/equipment/<id>  ────────────────────────────────────────────────
@equipment_bp.route("/<equipment_id>", methods=["DELETE"])
@jwt_required
@role_required("admin")
def delete_eq(equipment_id):
    try:
        delete_equipment(equipment_id)
    except EquipmentNotFoundError as e:
        return jsonify({"error": str(e)}), 404
    except EquipmentDeleteError as e:
        return jsonify({"error": str(e)}), 409
    return jsonify({"message": "Equipment deleted"})
