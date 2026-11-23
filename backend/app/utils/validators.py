"""
Shared input validators and sanitisers.
"""
from bson import ObjectId


def is_valid_object_id(value: str) -> bool:
    try:
        ObjectId(value)
        return True
    except Exception:
        return False


def sanitise_string(value, max_length: int = 500) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()[:max_length]
