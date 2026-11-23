"""
/api/auth  –  register, login, refresh, logout, /me
"""
from flask import Blueprint, request, jsonify, make_response, g, current_app
from bson import ObjectId

from ..services.auth_service import (
    register_user,
    login_user,
    issue_tokens,
    refresh_tokens,
    logout_user,
)
from ..utils.jwt_utils import jwt_required
from ..utils.json_utils import mongo_to_json
from ..extensions import mongo

auth_bp = Blueprint("auth", __name__)

_REFRESH_COOKIE = "refresh_token"


def _set_refresh_cookie(response, token: str, max_age: int):
    response.set_cookie(
        _REFRESH_COOKIE,
        token,
        httponly=True,
        secure=current_app.config.get("JWT_COOKIE_SECURE", False),
        samesite="Lax",
        max_age=max_age,
        path="/api/auth",
    )
    return response


# ── POST /api/auth/register ────────────────────────────────────────────────────
@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    user, errors = register_user(data)
    if errors:
        return jsonify({"errors": errors}), 400

    user_id = str(user["_id"])
    role = user["role"]
    access, refresh = issue_tokens(user_id, role)

    resp = make_response(
        jsonify({
            "message": "Registration successful",
            "access_token": access,
            "user": mongo_to_json(user),
        }),
        201,
    )
    _set_refresh_cookie(resp, refresh, max_age=7 * 24 * 3600)
    return resp


# ── POST /api/auth/login ───────────────────────────────────────────────────────
@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip()
    password = data.get("password", "")

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    user, error = login_user(email, password)
    if error:
        return jsonify({"error": error}), 401

    user_id = str(user["_id"])
    role = user["role"]
    access, refresh = issue_tokens(user_id, role)

    resp = make_response(
        jsonify({
            "access_token": access,
            "user": mongo_to_json(user),
        })
    )
    _set_refresh_cookie(resp, refresh, max_age=7 * 24 * 3600)
    return resp


# ── POST /api/auth/refresh ─────────────────────────────────────────────────────
@auth_bp.route("/refresh", methods=["POST"])
def refresh():
    old_token = request.cookies.get(_REFRESH_COOKIE)
    if not old_token:
        return jsonify({"error": "No refresh token cookie"}), 401

    # We need the user_id; extract it from the cookie's linked DB record
    # (we look up the hash without trusting the payload)
    import hashlib
    token_hash = hashlib.sha256(old_token.encode()).hexdigest()
    record = mongo.db.refresh_tokens.find_one(
        {"token_hash": token_hash, "revoked": False}
    )
    if not record:
        return jsonify({"error": "Invalid or expired refresh token"}), 401

    user_id = str(record["user_id"])
    user = mongo.db.users.find_one({"_id": ObjectId(user_id)})
    if not user or not user.get("is_active"):
        return jsonify({"error": "User not found or inactive"}), 401

    new_access, new_refresh, err = refresh_tokens(user_id, old_token, user["role"])
    if err:
        return jsonify({"error": err}), 401

    resp = make_response(jsonify({"access_token": new_access}))
    _set_refresh_cookie(resp, new_refresh, max_age=7 * 24 * 3600)
    return resp


# ── GET /api/auth/me ───────────────────────────────────────────────────────────
@auth_bp.route("/me", methods=["GET"])
@jwt_required
def me():
    user = dict(g.current_user)
    user.pop("password_hash", None)
    return jsonify(mongo_to_json(user))


# ── PUT /api/auth/me ───────────────────────────────────────────────────────────
@auth_bp.route("/me", methods=["PUT"])
@jwt_required
def update_me():
    data = request.get_json(silent=True) or {}
    allowed = {"name", "phone"}
    update = {k: v for k, v in data.items() if k in allowed and isinstance(v, str) and v.strip()}
    if not update:
        return jsonify({"error": "No updatable fields provided"}), 400

    from datetime import datetime, timezone
    update["updated_at"] = datetime.now(timezone.utc)
    mongo.db.users.update_one(
        {"_id": ObjectId(g.current_user_id)},
        {"$set": update},
    )
    user = mongo.db.users.find_one({"_id": ObjectId(g.current_user_id)})
    user.pop("password_hash", None)
    return jsonify(mongo_to_json(user))


# ── POST /api/auth/logout ──────────────────────────────────────────────────────
@auth_bp.route("/logout", methods=["POST"])
@jwt_required
def logout():
    logout_user(g.current_user_id)
    resp = make_response(jsonify({"message": "Logged out"}))
    resp.delete_cookie(_REFRESH_COOKIE, path="/api/auth")
    return resp
