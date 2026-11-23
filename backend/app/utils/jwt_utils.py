"""
JWT helpers: create access tokens, create/store/rotate refresh tokens.
Refresh tokens are stored hashed in MongoDB and transmitted via HttpOnly cookies.
"""
import secrets
import hashlib
from datetime import datetime, timezone
from functools import wraps
from typing import Optional

import jwt
from bson import ObjectId
from flask import current_app, request, jsonify, g

from ..extensions import mongo


# ── Token creation ─────────────────────────────────────────────────────────────

def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def create_access_token(user_id: str, role: str) -> str:
    """Return a signed JWT access token."""
    cfg = current_app.config
    now = _utcnow()
    payload = {
        "sub": user_id,
        "role": role,
        "iat": now,
        "exp": now + cfg["JWT_ACCESS_TOKEN_EXPIRES"],
        "type": "access",
    }
    return jwt.encode(payload, cfg["SECRET_KEY"], algorithm="HS256")


def create_refresh_token() -> str:
    """Return a secure random refresh token (plain text – stored hashed)."""
    return secrets.token_urlsafe(64)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def store_refresh_token(user_id: str, plain_token: str) -> None:
    """Persist a hashed refresh token; previous tokens for this user remain
    valid until they expire (rotation happens on use)."""
    cfg = current_app.config
    expires_at = _utcnow() + cfg["JWT_REFRESH_TOKEN_EXPIRES"]
    mongo.db.refresh_tokens.insert_one(
        {
            "user_id": ObjectId(user_id),
            "token_hash": _hash_token(plain_token),
            "expires_at": expires_at,
            "created_at": _utcnow(),
            "revoked": False,
        }
    )


def rotate_refresh_token(old_plain_token: str, user_id: str) -> Optional[str]:
    """
    Validate the incoming refresh token, revoke it, issue a new one.
    Returns the new plain token, or None if the old token is invalid/revoked/expired.
    """
    old_hash = _hash_token(old_plain_token)
    now = _utcnow()

    record = mongo.db.refresh_tokens.find_one(
        {
            "user_id": ObjectId(user_id),
            "token_hash": old_hash,
            "revoked": False,
            "expires_at": {"$gt": now},
        }
    )
    if not record:
        return None

    # Revoke the old token (rotation)
    mongo.db.refresh_tokens.update_one(
        {"_id": record["_id"]}, {"$set": {"revoked": True}}
    )

    # Issue a new token
    new_token = create_refresh_token()
    store_refresh_token(user_id, new_token)
    return new_token


def revoke_all_refresh_tokens(user_id: str) -> None:
    """Revoke all active refresh tokens for a user (used on logout)."""
    mongo.db.refresh_tokens.update_many(
        {"user_id": ObjectId(user_id), "revoked": False},
        {"$set": {"revoked": True}},
    )


# ── Token verification ─────────────────────────────────────────────────────────

def decode_access_token(token: str) -> Optional[dict]:
    """Decode and validate an access token. Returns payload dict or None."""
    try:
        payload = jwt.decode(
            token,
            current_app.config["SECRET_KEY"],
            algorithms=["HS256"],
        )
        if payload.get("type") != "access":
            return None
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


# ── Request decorators ─────────────────────────────────────────────────────────

def jwt_required(f):
    """Decorator: validates Bearer token, populates flask.g.current_user."""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "Missing or invalid Authorization header"}), 401
        token = auth_header.split(" ", 1)[1]
        payload = decode_access_token(token)
        if payload is None:
            return jsonify({"error": "Token is invalid or expired"}), 401

        user = mongo.db.users.find_one({"_id": ObjectId(payload["sub"])})
        if not user or not user.get("is_active"):
            return jsonify({"error": "User not found or inactive"}), 401

        g.current_user = user
        g.current_user_id = str(user["_id"])
        g.current_role = user["role"]
        return f(*args, **kwargs)

    return decorated


def role_required(*roles):
    """
    Decorator factory: requires jwt_required to have already run,
    then checks the user role.

    Usage:
        @jwt_required
        @role_required("admin", "faculty")
        def my_view(): ...
    """
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if g.get("current_role") not in roles:
                return jsonify({"error": "Forbidden: insufficient role"}), 403
            return f(*args, **kwargs)
        return decorated
    return decorator
