"""
/api/ai  –  AI-assisted equipment recommendation and slot suggestions.

IMPORTANT: AI is advisory only. It NEVER approves bookings, never modifies
the database, and never bypasses booking conflict checks.
All watsonx.ai calls are proxied through this Flask backend.
Credentials are read from env vars; they are never sent to the browser.
"""
from flask import Blueprint, request, jsonify, g
from ..utils.jwt_utils import jwt_required
from ..extensions import mongo
from ..utils.json_utils import mongo_to_json
import app.services.watsonx_service as wx

ai_bp = Blueprint("ai", __name__)


# ── POST /api/ai/recommend  ───────────────────────────────────────────────────
@ai_bp.route("/recommend", methods=["POST"])
@jwt_required
def recommend():
    """
    Recommend equipment for a student project.
    Body: { "project_description": "...", "department_id": "..." (optional) }
    Returns: { "recommendations": [...], "mode": "ai"|"stub" }
    AI result is advisory only. The student still chooses and must book normally.
    """
    data = request.get_json(silent=True) or {}
    description = (data.get("project_description") or "").strip()
    if not description:
        return jsonify({"error": "project_description is required"}), 400

    # Fetch available equipment (optionally filtered by department)
    query: dict = {"status": "available"}
    if data.get("department_id"):
        from bson import ObjectId
        try:
            query["department_id"] = ObjectId(data["department_id"])
        except Exception:
            pass

    available = list(mongo.db.equipment.find(query).limit(30))
    result = wx.recommend_equipment(description, available)
    return jsonify(result)


# ── POST /api/ai/slots  ───────────────────────────────────────────────────────
@ai_bp.route("/slots", methods=["POST"])
@jwt_required
def suggest_slots():
    """
    Suggest available 2-hour time slots for an equipment item on a given date.
    Body: { "equipment_id": "...", "preferred_date": "YYYY-MM-DD" }
    Returns: { "slots": [...], "mode": "ai"|"computed" }
    Slots are suggestions only. Booking still requires the normal POST /api/bookings flow.
    """
    data = request.get_json(silent=True) or {}
    equipment_id = (data.get("equipment_id") or "").strip()
    preferred_date = (data.get("preferred_date") or "").strip()

    if not equipment_id:
        return jsonify({"error": "equipment_id is required"}), 400

    from bson import ObjectId
    from datetime import datetime, timezone, timedelta
    try:
        oid = ObjectId(equipment_id)
    except Exception:
        return jsonify({"error": "Invalid equipment_id"}), 400

    if not mongo.db.equipment.find_one({"_id": oid}):
        return jsonify({"error": "Equipment not found"}), 404

    # Fetch existing bookings on that date to pass to the AI
    if preferred_date:
        try:
            from datetime import date
            ref = date.fromisoformat(preferred_date)
            day_start = datetime(ref.year, ref.month, ref.day, tzinfo=timezone.utc)
            day_end   = day_start + timedelta(days=1)
        except ValueError:
            day_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
            day_end   = day_start + timedelta(days=1)
    else:
        day_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        day_end   = day_start + timedelta(days=1)
        preferred_date = day_start.date().isoformat()

    existing = list(mongo.db.bookings.find({
        "equipment_id": oid,
        "status": {"$in": ["pending", "approved", "active"]},
        "start_time": {"$lt": day_end},
        "end_time":   {"$gt": day_start},
    }))

    result = wx.suggest_slots(equipment_id, preferred_date, existing)
    return jsonify(result)


# ── POST /api/ai/draft  ───────────────────────────────────────────────────────
@ai_bp.route("/draft", methods=["POST"])
@jwt_required
def draft_request():
    """
    Help a student draft a project request from a free-text description.
    Body: { "description": "..." }
    Returns: { "title": "...", "description": "...", "mode": "ai"|"stub" }
    The student must review the draft and submit it themselves.
    """
    data = request.get_json(silent=True) or {}
    description = (data.get("description") or "").strip()
    if not description:
        return jsonify({"error": "description is required"}), 400
    result = wx.draft_request(description)
    return jsonify(result)


# ── GET /api/ai/status  ───────────────────────────────────────────────────────
@ai_bp.route("/status", methods=["GET"])
@jwt_required
def ai_status():
    """Returns whether watsonx.ai is configured (without exposing credentials)."""
    configured = wx.is_configured()
    return jsonify({"configured": configured, "mode": "ai" if configured else "stub"})
