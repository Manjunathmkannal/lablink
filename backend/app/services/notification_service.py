"""
Notification service – creates and queries notifications.
"""
from bson import ObjectId

from ..extensions import mongo
from ..models.notification import build_notification_doc


def create_notification(
    user_id,
    notif_type: str,
    title: str,
    message: str,
    reference_id=None,
    reference_type: str = "",
) -> None:
    doc = build_notification_doc(
        user_id=ObjectId(str(user_id)),
        notif_type=notif_type,
        title=title,
        message=message,
        reference_id=reference_id,
        reference_type=reference_type,
    )
    mongo.db.notifications.insert_one(doc)


def get_user_notifications(user_id: str, unread_only: bool = False) -> list[dict]:
    query: dict = {"user_id": ObjectId(user_id)}
    if unread_only:
        query["is_read"] = False
    return list(
        mongo.db.notifications.find(query).sort("created_at", -1).limit(50)
    )
