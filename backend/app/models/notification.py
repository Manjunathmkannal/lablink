"""
Notification document schema + builder.
"""
from datetime import datetime, timezone

VALID_TYPES = {
    "booking_approved",
    "booking_rejected",
    "booking_reminder",
    "maintenance_alert",
    "system",
}


def build_notification_doc(
    user_id,
    notif_type: str,
    title: str,
    message: str,
    reference_id=None,
    reference_type: str = "",
) -> dict:
    return {
        "user_id": user_id,
        "type": notif_type,
        "title": title,
        "message": message,
        "is_read": False,
        "reference_id": reference_id,
        "reference_type": reference_type,
        "created_at": datetime.now(timezone.utc),
    }
