"""
/api/notifications
"""
from flask import Blueprint, request, jsonify, g
from bson import ObjectId

from ..utils.jwt_utils import jwt_required
from ..utils.json_utils import mongo_to_json
from ..extensions import mongo

notifications_bp = Blueprint("notifications", __name__)


@notifications_bp.route("/", methods=["GET"])
@jwt_required
def get_notifications():
    unread_param = request.args.get("unread", "")
    unread_only = unread_param.lower() in ("1", "true", "yes")
    query = {"user_id": ObjectId(g.current_user_id)}
    if unread_only:
        query["is_read"] = False
    items = list(
        mongo.db.notifications.find(query).sort("created_at", -1).limit(50)
    )
    return jsonify({"notifications": mongo_to_json(items)})


@notifications_bp.route("/<notification_id>/read", methods=["PUT"])
@jwt_required
def mark_read(notification_id):
    try:
        oid = ObjectId(notification_id)
    except Exception:
        return jsonify({"error": "Invalid notification ID"}), 400

    result = mongo.db.notifications.update_one(
        {"_id": oid, "user_id": ObjectId(g.current_user_id)},
        {"$set": {"is_read": True}},
    )
    if result.matched_count == 0:
        return jsonify({"error": "Notification not found"}), 404
    return jsonify({"message": "Marked as read"})


@notifications_bp.route("/read-all", methods=["PUT"])
@jwt_required
def mark_all_read():
    mongo.db.notifications.update_many(
        {"user_id": ObjectId(g.current_user_id), "is_read": False},
        {"$set": {"is_read": True}},
    )
    return jsonify({"message": "All notifications marked as read"})
