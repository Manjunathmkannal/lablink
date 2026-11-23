"""
/api/faculty  –  Faculty dashboard, approval queue, lab schedule
"""
from flask import Blueprint, request, jsonify, g
from bson import ObjectId

from ..utils.jwt_utils import jwt_required, role_required
from ..utils.json_utils import mongo_to_json
from ..extensions import mongo

faculty_bp = Blueprint("faculty", __name__)


# ── GET /api/faculty/dashboard  ───────────────────────────────────────────────
@faculty_bp.route("/dashboard", methods=["GET"])
@jwt_required
@role_required("faculty", "admin")
def dashboard():
    """
    Returns:
      - pending_bookings_count
      - pending_projects_count
      - approved_today
      - recent_requests (latest 5 pending bookings)
    """
    db = mongo.db
    fac_id = ObjectId(g.current_user_id)

    pending_bookings = db.bookings.count_documents({"status": "pending"})
    pending_projects = db.project_requests.count_documents(
        {"status": {"$in": ["submitted", "under_review"]}}
    )

    from datetime import datetime, timezone, timedelta
    today_start = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    approved_today = db.bookings.count_documents(
        {
            "status": "approved",
            "updated_at": {"$gte": today_start},
            "approved_by": fac_id,
        }
    )

    recent_requests = list(
        db.bookings.find({"status": "pending"})
        .sort("created_at", -1)
        .limit(5)
    )

    return jsonify({
        "pending_bookings_count": pending_bookings,
        "pending_projects_count": pending_projects,
        "approved_today": approved_today,
        "recent_requests": mongo_to_json(recent_requests),
    })


# ── GET /api/faculty/requests  ────────────────────────────────────────────────
@faculty_bp.route("/requests", methods=["GET"])
@jwt_required
@role_required("faculty", "admin")
def pending_requests():
    """All pending booking requests, paginated. Query: page, per_page."""
    from math import ceil
    args = request.args
    page = max(1, int(args.get("page", 1)))
    per_page = min(max(1, int(args.get("per_page", 20))), 100)

    query = {"status": "pending"}
    total = mongo.db.bookings.count_documents(query)
    items = list(
        mongo.db.bookings.find(query)
        .sort("created_at", -1)
        .skip((page - 1) * per_page)
        .limit(per_page)
    )
    return jsonify(mongo_to_json({
        "items": items,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": ceil(total / per_page) if total else 0,
    }))


# ── GET /api/faculty/schedule  ────────────────────────────────────────────────
@faculty_bp.route("/schedule", methods=["GET"])
@jwt_required
@role_required("faculty", "admin")
def lab_schedule():
    """
    Weekly lab schedule.
    Query params: lab_id (optional), date YYYY-MM-DD (defaults to current week).
    Returns approved + active bookings in the requested week.
    """
    from datetime import datetime, timezone, timedelta, date as date_type
    args = request.args

    date_str = args.get("date", "")
    try:
        ref_date = date_type.fromisoformat(date_str) if date_str else datetime.now(timezone.utc).date()
    except ValueError:
        return jsonify({"error": "Invalid date format, use YYYY-MM-DD"}), 400

    monday = ref_date - timedelta(days=ref_date.weekday())
    week_start = datetime(monday.year, monday.month, monday.day, tzinfo=timezone.utc)
    week_end = week_start + timedelta(days=7)

    query: dict = {
        "status": {"$in": ["approved", "active"]},
        "start_time": {"$lt": week_end},
        "end_time": {"$gt": week_start},
    }
    if args.get("lab_id"):
        try:
            query["lab_id"] = ObjectId(args["lab_id"])
        except Exception:
            return jsonify({"error": "Invalid lab_id"}), 400

    bookings = list(
        mongo.db.bookings.find(query).sort("start_time", 1)
    )
    return jsonify({
        "week_start": week_start.isoformat(),
        "week_end": week_end.isoformat(),
        "bookings": mongo_to_json(bookings),
    })
