"""
Authentication business logic – no Flask request objects here.
"""
from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId
from flask import current_app

from ..extensions import mongo, bcrypt
from ..models.user import build_user_doc, validate_user_payload
from ..utils.jwt_utils import (
    create_access_token,
    create_refresh_token,
    store_refresh_token,
    rotate_refresh_token,
    revoke_all_refresh_tokens,
)


def register_user(data: dict) -> tuple[Optional[dict], list[str]]:
    """
    Validate, hash password, insert user.
    Returns (user_doc_without_hash, errors).
    """
    errors = validate_user_payload(data)
    if errors:
        return None, errors

    email = data["email"].strip().lower()
    if mongo.db.users.find_one({"email": email}):
        return None, ["Email is already registered"]

    password_hash = bcrypt.generate_password_hash(data["password"]).decode("utf-8")
    doc = build_user_doc(
        name=data["name"],
        email=email,
        password_hash=password_hash,
        role=data.get("role", "student"),
        department_id=ObjectId(data["department_id"]) if data.get("department_id") else None,
        student_id=data.get("student_id"),
        phone=data.get("phone"),
    )
    result = mongo.db.users.insert_one(doc)
    doc["_id"] = result.inserted_id
    doc.pop("password_hash", None)
    return doc, []


def login_user(email: str, password: str) -> tuple[Optional[dict], str]:
    """
    Validate credentials.
    Returns (user_doc_without_hash, error_message).
    """
    user = mongo.db.users.find_one({"email": email.strip().lower()})
    if not user:
        return None, "Invalid email or password"
    if not user.get("is_active"):
        return None, "Account is deactivated"
    if not bcrypt.check_password_hash(user["password_hash"], password):
        return None, "Invalid email or password"

    user_out = dict(user)
    user_out.pop("password_hash", None)
    return user_out, ""


def issue_tokens(user_id: str, role: str) -> tuple[str, str]:
    """Create a new access token + refresh token pair."""
    access = create_access_token(user_id, role)
    refresh = create_refresh_token()
    store_refresh_token(user_id, refresh)
    return access, refresh


def refresh_tokens(user_id: str, old_refresh_token: str, role: str) -> tuple[Optional[str], Optional[str], str]:
    """
    Rotate refresh token. Returns (new_access, new_refresh, error).
    """
    new_refresh = rotate_refresh_token(old_refresh_token, user_id)
    if not new_refresh:
        return None, None, "Refresh token is invalid, expired, or already used"
    new_access = create_access_token(user_id, role)
    return new_access, new_refresh, ""


def logout_user(user_id: str) -> None:
    revoke_all_refresh_tokens(user_id)
