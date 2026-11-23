"""
/api/admin  –  Admin dashboard, user CRUD, department/lab CRUD, booking management.
Full analytics pipeline is in Phase 4; this phase delivers all management routes.
"""
from datetime import datetime, timezone
from math import ceil
from flask import Blueprint, request, jsonify, g
from bson import ObjectId

from ..utils.jwt_utils import jwt_required, role_required
from ..utils.json_utils import mongo_to_json
from ..extensions import mongo, bcrypt

admin_bp = Blueprint("admin", __name__)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _page_query(args):
    page = max(1, int(args.get("page", 1)))
    per_page = min(max(1, int(args.get("per_page", 20))), 100)
    return page, per_page


# ── GET /api/admin/dashboard  ─────────────────────────────────────────────────
@admin_bp.route("/dashboard", methods=["GET"])
@jwt_required
@role_required("admin")
def dashboard():
    db = mongo.db
    return jsonify({
        "total_users": db.users.count_documents({}),
        "total_equipment": db.equipment.count_documents({}),
        "total_bookings": db.bookings.count_documents({}),
        "pending_bookings": db.bookings.count_documents({"status": "pending"}),
        "approved_bookings": db.bookings.count_documents({"status": "approved"}),
        "pending_projects": db.project_requests.count_documents(
            {"status": {"$in": ["submitted", "under_review"]}}
        ),
        "equipment_in_maintenance": db.equipment.count_documents({"status": "maintenance"}),
    })


# ── Users ──────────────────────────────────────────────────────────────────────

@admin_bp.route("/users", methods=["GET"])
@jwt_required
@role_required("admin")
def list_users():
    args = request.args
    page, per_page = _page_query(args)
    query: dict = {}
    if args.get("role"):
        query["role"] = args["role"]
    if args.get("search"):
        import re
        pattern = re.compile(re.escape(args["search"].strip()), re.IGNORECASE)
        query["$or"] = [{"name": pattern}, {"email": pattern}]

    total = mongo.db.users.count_documents(query)
    items = list(
        mongo.db.users.find(query, {"password_hash": 0})
        .sort("name", 1)
        .skip((page - 1) * per_page)
        .limit(per_page)
    )
    return jsonify(mongo_to_json({
        "items": items, "total": total,
        "page": page, "per_page": per_page,
        "pages": ceil(total / per_page) if total else 0,
    }))


@admin_bp.route("/users/<user_id>", methods=["GET"])
@jwt_required
@role_required("admin")
def get_user(user_id):
    try:
        oid = ObjectId(user_id)
    except Exception:
        return jsonify({"error": "Invalid user ID"}), 400
    user = mongo.db.users.find_one({"_id": oid}, {"password_hash": 0})
    if not user:
        return jsonify({"error": "User not found"}), 404
    return jsonify(mongo_to_json(user))


@admin_bp.route("/users", methods=["POST"])
@jwt_required
@role_required("admin")
def create_user():
    from ..models.user import validate_user_payload, build_user_doc
    data = request.get_json(silent=True) or {}
    errors = validate_user_payload(data)
    if errors:
        return jsonify({"errors": errors}), 400
    if mongo.db.users.find_one({"email": data["email"].strip().lower()}):
        return jsonify({"errors": ["Email already registered"]}), 400

    pw_hash = bcrypt.generate_password_hash(data["password"]).decode("utf-8")
    doc = build_user_doc(
        name=data["name"],
        email=data["email"],
        password_hash=pw_hash,
        role=data.get("role", "student"),
        department_id=ObjectId(data["department_id"]) if data.get("department_id") else None,
        student_id=data.get("student_id"),
        phone=data.get("phone"),
    )
    result = mongo.db.users.insert_one(doc)
    doc["_id"] = result.inserted_id
    doc.pop("password_hash", None)
    return jsonify({"message": "User created", "user": mongo_to_json(doc)}), 201


@admin_bp.route("/users/<user_id>", methods=["PUT"])
@jwt_required
@role_required("admin")
def update_user(user_id):
    try:
        oid = ObjectId(user_id)
    except Exception:
        return jsonify({"error": "Invalid user ID"}), 400
    if not mongo.db.users.find_one({"_id": oid}):
        return jsonify({"error": "User not found"}), 404

    data = request.get_json(silent=True) or {}
    allowed = {"name", "phone", "role", "department_id", "is_active"}
    update = {k: v for k, v in data.items() if k in allowed}
    if "department_id" in update and update["department_id"]:
        try:
            update["department_id"] = ObjectId(update["department_id"])
        except Exception:
            return jsonify({"error": "Invalid department_id"}), 400
    if not update:
        return jsonify({"error": "No updatable fields provided"}), 400
    update["updated_at"] = datetime.now(timezone.utc)
    mongo.db.users.update_one({"_id": oid}, {"$set": update})
    user = mongo.db.users.find_one({"_id": oid}, {"password_hash": 0})
    return jsonify({"message": "User updated", "user": mongo_to_json(user)})


@admin_bp.route("/users/<user_id>", methods=["DELETE"])
@jwt_required
@role_required("admin")
def delete_user(user_id):
    try:
        oid = ObjectId(user_id)
    except Exception:
        return jsonify({"error": "Invalid user ID"}), 400
    # Prevent self-deletion
    if str(oid) == g.current_user_id:
        return jsonify({"error": "Cannot delete your own account"}), 400
    result = mongo.db.users.delete_one({"_id": oid})
    if result.deleted_count == 0:
        return jsonify({"error": "User not found"}), 404
    return jsonify({"message": "User deleted"})


# ── Departments ────────────────────────────────────────────────────────────────

@admin_bp.route("/departments", methods=["GET"])
@jwt_required
@role_required("admin", "faculty", "lab_assistant", "student")
def list_departments():
    items = list(mongo.db.departments.find({}).sort("name", 1))
    return jsonify({"departments": mongo_to_json(items)})


@admin_bp.route("/departments", methods=["POST"])
@jwt_required
@role_required("admin")
def create_department():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    code = (data.get("code") or "").strip().upper()
    if not name:
        return jsonify({"error": "name is required"}), 400
    if mongo.db.departments.find_one({"name": name}):
        return jsonify({"error": "Department name already exists"}), 400
    doc = {
        "name": name,
        "code": code,
        "head_faculty_id": ObjectId(data["head_faculty_id"]) if data.get("head_faculty_id") else None,
        "created_at": datetime.now(timezone.utc),
    }
    result = mongo.db.departments.insert_one(doc)
    doc["_id"] = result.inserted_id
    return jsonify({"message": "Department created", "department": mongo_to_json(doc)}), 201


@admin_bp.route("/departments/<dept_id>", methods=["PUT"])
@jwt_required
@role_required("admin")
def update_department(dept_id):
    try:
        oid = ObjectId(dept_id)
    except Exception:
        return jsonify({"error": "Invalid department ID"}), 400
    data = request.get_json(silent=True) or {}
    allowed = {"name", "code", "head_faculty_id"}
    update = {k: v for k, v in data.items() if k in allowed}
    if "head_faculty_id" in update and update["head_faculty_id"]:
        try:
            update["head_faculty_id"] = ObjectId(update["head_faculty_id"])
        except Exception:
            return jsonify({"error": "Invalid head_faculty_id"}), 400
    if not update:
        return jsonify({"error": "No updatable fields"}), 400
    result = mongo.db.departments.update_one({"_id": oid}, {"$set": update})
    if result.matched_count == 0:
        return jsonify({"error": "Department not found"}), 404
    return jsonify({"message": "Department updated"})


@admin_bp.route("/departments/<dept_id>", methods=["DELETE"])
@jwt_required
@role_required("admin")
def delete_department(dept_id):
    try:
        oid = ObjectId(dept_id)
    except Exception:
        return jsonify({"error": "Invalid department ID"}), 400
    result = mongo.db.departments.delete_one({"_id": oid})
    if result.deleted_count == 0:
        return jsonify({"error": "Department not found"}), 404
    return jsonify({"message": "Department deleted"})


# ── Laboratories ───────────────────────────────────────────────────────────────

@admin_bp.route("/laboratories", methods=["GET"])
@jwt_required
@role_required("admin", "faculty", "lab_assistant", "student")
def list_laboratories():
    args = request.args
    query: dict = {}
    if args.get("department_id"):
        try:
            query["department_id"] = ObjectId(args["department_id"])
        except Exception:
            return jsonify({"error": "Invalid department_id"}), 400
    items = list(mongo.db.laboratories.find(query).sort("name", 1))
    return jsonify({"laboratories": mongo_to_json(items)})


@admin_bp.route("/laboratories", methods=["POST"])
@jwt_required
@role_required("admin")
def create_laboratory():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name is required"}), 400
    if not data.get("department_id"):
        return jsonify({"error": "department_id is required"}), 400
    try:
        dept_oid = ObjectId(data["department_id"])
    except Exception:
        return jsonify({"error": "Invalid department_id"}), 400

    doc = {
        "name": name,
        "department_id": dept_oid,
        "location": (data.get("location") or "").strip(),
        "capacity": int(data.get("capacity", 0)),
        "operating_hours": data.get("operating_hours", {"open": "08:00", "close": "18:00"}),
        "is_active": True,
        "assigned_assistant_id": (
            ObjectId(data["assigned_assistant_id"]) if data.get("assigned_assistant_id") else None
        ),
        "created_at": datetime.now(timezone.utc),
    }
    result = mongo.db.laboratories.insert_one(doc)
    doc["_id"] = result.inserted_id
    return jsonify({"message": "Laboratory created", "laboratory": mongo_to_json(doc)}), 201


@admin_bp.route("/laboratories/<lab_id>", methods=["PUT"])
@jwt_required
@role_required("admin")
def update_laboratory(lab_id):
    try:
        oid = ObjectId(lab_id)
    except Exception:
        return jsonify({"error": "Invalid lab ID"}), 400
    data = request.get_json(silent=True) or {}
    allowed = {"name", "location", "capacity", "operating_hours", "is_active", "assigned_assistant_id"}
    update = {k: v for k, v in data.items() if k in allowed}
    if "assigned_assistant_id" in update and update["assigned_assistant_id"]:
        try:
            update["assigned_assistant_id"] = ObjectId(update["assigned_assistant_id"])
        except Exception:
            return jsonify({"error": "Invalid assigned_assistant_id"}), 400
    if not update:
        return jsonify({"error": "No updatable fields"}), 400
    result = mongo.db.laboratories.update_one({"_id": oid}, {"$set": update})
    if result.matched_count == 0:
        return jsonify({"error": "Laboratory not found"}), 404
    return jsonify({"message": "Laboratory updated"})


@admin_bp.route("/laboratories/<lab_id>", methods=["DELETE"])
@jwt_required
@role_required("admin")
def delete_laboratory(lab_id):
    try:
        oid = ObjectId(lab_id)
    except Exception:
        return jsonify({"error": "Invalid lab ID"}), 400
    result = mongo.db.laboratories.delete_one({"_id": oid})
    if result.deleted_count == 0:
        return jsonify({"error": "Laboratory not found"}), 404
    return jsonify({"message": "Laboratory deleted"})


# ── Bookings (admin view) ──────────────────────────────────────────────────────

@admin_bp.route("/bookings", methods=["GET"])
@jwt_required
@role_required("admin")
def admin_list_bookings():
    args = request.args
    page, per_page = _page_query(args)
    query: dict = {}
    if args.get("status"):
        query["status"] = args["status"]
    if args.get("equipment_id"):
        try:
            query["equipment_id"] = ObjectId(args["equipment_id"])
        except Exception:
            pass
    if args.get("student_id"):
        try:
            query["student_id"] = ObjectId(args["student_id"])
        except Exception:
            pass

    total = mongo.db.bookings.count_documents(query)
    items = list(
        mongo.db.bookings.find(query)
        .sort("created_at", -1)
        .skip((page - 1) * per_page)
        .limit(per_page)
    )
    return jsonify(mongo_to_json({
        "items": items, "total": total,
        "page": page, "per_page": per_page,
        "pages": ceil(total / per_page) if total else 0,
    }))


# ── Analytics (Phase 4) ────────────────────────────────────────────────────────

@admin_bp.route("/analytics", methods=["GET"])
@jwt_required
@role_required("admin")
def analytics():
    """
    Returns six aggregated datasets for the admin analytics dashboard.
    All aggregations run against real MongoDB data.
    Query param: months (default 6) – how many months of booking trend history.
    """
    months = max(1, min(int(request.args.get("months", 6)), 24))
    db = mongo.db

    # 1 ── Equipment utilization: total vs available vs booked count ──────────
    eq_pipeline = [
        {"$group": {
            "_id": None,
            "total": {"$sum": 1},
            "available": {"$sum": {"$cond": [{"$eq": ["$status", "available"]}, 1, 0]}},
            "booked":    {"$sum": {"$cond": [{"$eq": ["$status", "booked"]}, 1, 0]}},
            "maintenance": {"$sum": {"$cond": [{"$eq": ["$status", "maintenance"]}, 1, 0]}},
            "retired":   {"$sum": {"$cond": [{"$eq": ["$status", "retired"]}, 1, 0]}},
        }}
    ]
    eq_util = list(db.equipment.aggregate(eq_pipeline))
    equipment_utilization = eq_util[0] if eq_util else {
        "total": 0, "available": 0, "booked": 0, "maintenance": 0, "retired": 0
    }
    equipment_utilization.pop("_id", None)

    # 2 ── Department-wise booking usage ──────────────────────────────────────
    dept_pipeline = [
        {"$match": {"status": {"$in": ["approved", "active", "completed"]}}},
        {"$group": {"_id": "$department_id", "booking_count": {"$sum": 1}}},
        {"$lookup": {
            "from": "departments",
            "localField": "_id",
            "foreignField": "_id",
            "as": "dept",
        }},
        {"$project": {
            "department_name": {"$ifNull": [{"$arrayElemAt": ["$dept.name", 0]}, "Unknown"]},
            "department_code": {"$ifNull": [{"$arrayElemAt": ["$dept.code", 0]}, "?"]},
            "booking_count": 1,
        }},
        {"$sort": {"booking_count": -1}},
    ]
    dept_usage = mongo_to_json(list(db.bookings.aggregate(dept_pipeline)))
    for d in dept_usage:
        d.pop("_id", None)

    # 3 ── Monthly booking trends (last N months) ─────────────────────────────
    from datetime import datetime as _dt, timezone as _tz
    cutoff = _dt.now(_tz.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    # Go back `months` months
    import calendar
    for _ in range(months - 1):
        first_of_month = cutoff.replace(day=1)
        prev_month = first_of_month - __import__("datetime").timedelta(days=1)
        cutoff = prev_month.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    trend_pipeline = [
        {"$match": {"created_at": {"$gte": cutoff}}},
        {"$group": {
            "_id": {
                "year":  {"$year": "$created_at"},
                "month": {"$month": "$created_at"},
            },
            "total":     {"$sum": 1},
            "approved":  {"$sum": {"$cond": [{"$eq": ["$status", "approved"]}, 1, 0]}},
            "rejected":  {"$sum": {"$cond": [{"$eq": ["$status", "rejected"]}, 1, 0]}},
            "cancelled": {"$sum": {"$cond": [{"$eq": ["$status", "cancelled"]}, 1, 0]}},
        }},
        {"$sort": {"_id.year": 1, "_id.month": 1}},
        {"$project": {
            "_id": 0,
            "year":  "$_id.year",
            "month": "$_id.month",
            "total": 1, "approved": 1, "rejected": 1, "cancelled": 1,
        }},
    ]
    monthly_trends = list(db.bookings.aggregate(trend_pipeline))

    # 4 ── Pending approvals summary ───────────────────────────────────────────
    pending_bookings  = db.bookings.count_documents({"status": "pending"})
    pending_projects  = db.project_requests.count_documents(
        {"status": {"$in": ["submitted", "under_review"]}}
    )

    # 5 ── Top 5 most-booked equipment ─────────────────────────────────────────
    top_eq_pipeline = [
        {"$match": {"status": {"$in": ["approved", "active", "completed"]}}},
        {"$group": {"_id": "$equipment_id", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 5},
        {"$lookup": {
            "from": "equipment",
            "localField": "_id",
            "foreignField": "_id",
            "as": "equip",
        }},
        {"$project": {
            "_id": 0,
            "equipment_name": {"$ifNull": [{"$arrayElemAt": ["$equip.name", 0]}, "Unknown"]},
            "category":       {"$ifNull": [{"$arrayElemAt": ["$equip.category", 0]}, "?"]},
            "count": 1,
        }},
    ]
    top_equipment = list(db.bookings.aggregate(top_eq_pipeline))

    # 6 ── User statistics ─────────────────────────────────────────────────────
    user_pipeline = [
        {"$group": {"_id": "$role", "count": {"$sum": 1}}},
        {"$project": {"_id": 0, "role": "$_id", "count": 1}},
    ]
    user_stats = list(db.users.aggregate(user_pipeline))

    return jsonify({
        "equipment_utilization": equipment_utilization,
        "department_usage":      dept_usage,
        "monthly_trends":        monthly_trends,
        "pending_approvals":     {"bookings": pending_bookings, "projects": pending_projects},
        "top_equipment":         top_equipment,
        "user_statistics":       user_stats,
    })
