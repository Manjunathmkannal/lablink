"""
/api/projects  –  Project request CRUD + faculty review
"""
from flask import Blueprint, request, jsonify, g

from ..utils.jwt_utils import jwt_required, role_required
from ..utils.json_utils import mongo_to_json
from ..extensions import mongo
from ..services.project_service import (
    create_project_request,
    list_project_requests,
    get_project_request,
    update_project_request,
    submit_project_request,
    review_project_request,
    ProjectNotFoundError,
    ProjectError,
)
from ..services.notification_service import create_notification

projects_bp = Blueprint("projects", __name__)


# ── GET /api/projects  ────────────────────────────────────────────────────────
@projects_bp.route("/", methods=["GET"])
@jwt_required
def list_projects():
    """
    Students: own requests only.
    Faculty / Admin: all requests (filterable by status).
    Query params: status, page, per_page.
    """
    args = request.args
    role = g.current_role

    student_id = g.current_user_id if role == "student" else args.get("student_id", "")
    result = list_project_requests(
        student_id=student_id,
        status=args.get("status", ""),
        page=int(args.get("page", 1)),
        per_page=int(args.get("per_page", 20)),
    )
    return jsonify(mongo_to_json(result))


# ── GET /api/projects/<id>  ───────────────────────────────────────────────────
@projects_bp.route("/<request_id>", methods=["GET"])
@jwt_required
def get_project(request_id):
    try:
        doc = get_project_request(request_id)
    except ProjectNotFoundError as e:
        return jsonify({"error": str(e)}), 404

    # Students can only see their own
    if g.current_role == "student" and str(doc["student_id"]) != g.current_user_id:
        return jsonify({"error": "Forbidden"}), 403

    return jsonify(mongo_to_json(doc))


# ── POST /api/projects  ───────────────────────────────────────────────────────
@projects_bp.route("/", methods=["POST"])
@jwt_required
@role_required("student")
def create_project():
    data = request.get_json(silent=True) or {}
    try:
        doc = create_project_request(g.current_user_id, data)
    except ProjectError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"message": "Project request created", "project_request": mongo_to_json(doc)}), 201


# ── PUT /api/projects/<id>  ───────────────────────────────────────────────────
@projects_bp.route("/<request_id>", methods=["PUT"])
@jwt_required
@role_required("student")
def update_project(request_id):
    """Update a draft project request (student, own only)."""
    data = request.get_json(silent=True) or {}
    try:
        doc = update_project_request(request_id, g.current_user_id, data)
    except ProjectNotFoundError as e:
        return jsonify({"error": str(e)}), 404
    except ProjectError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"message": "Project request updated", "project_request": mongo_to_json(doc)})


# ── PUT /api/projects/<id>/submit  ────────────────────────────────────────────
@projects_bp.route("/<request_id>/submit", methods=["PUT"])
@jwt_required
@role_required("student")
def submit_project(request_id):
    """Submit a draft project request for faculty review."""
    try:
        doc = submit_project_request(request_id, g.current_user_id)
    except ProjectNotFoundError as e:
        return jsonify({"error": str(e)}), 404
    except ProjectError as e:
        return jsonify({"error": str(e)}), 400

    # Notify the student
    create_notification(
        user_id=g.current_user_id,
        notif_type="system",
        title="Project request submitted",
        message="Your project request has been submitted for faculty review.",
        reference_id=doc["_id"],
        reference_type="project_request",
    )
    return jsonify({"message": "Project request submitted", "project_request": mongo_to_json(doc)})


# ── PUT /api/projects/<id>/review  ───────────────────────────────────────────
@projects_bp.route("/<request_id>/review", methods=["PUT"])
@jwt_required
@role_required("faculty", "admin")
def review_project(request_id):
    """
    Faculty approves or rejects a submitted project request.
    Body: { "decision": "approved"|"rejected", "notes": "..." }
    """
    data = request.get_json(silent=True) or {}
    decision = (data.get("decision") or "").strip().lower()
    notes = (data.get("notes") or data.get("review_notes") or "").strip()

    if not decision:
        return jsonify({"error": "decision is required ('approved' or 'rejected')"}), 400

    try:
        doc = review_project_request(request_id, g.current_user_id, decision, notes)
    except ProjectNotFoundError as e:
        return jsonify({"error": str(e)}), 404
    except ProjectError as e:
        return jsonify({"error": str(e)}), 400

    # Notify the student
    notif_type = "booking_approved" if decision == "approved" else "booking_rejected"
    msg = (
        f"Your project request '{doc['title']}' has been {decision}."
        + (f" Notes: {notes}" if notes else "")
    )
    create_notification(
        user_id=str(doc["student_id"]),
        notif_type=notif_type,
        title=f"Project request {decision}",
        message=msg,
        reference_id=doc["_id"],
        reference_type="project_request",
    )
    return jsonify({"message": f"Project request {decision}", "project_request": mongo_to_json(doc)})
