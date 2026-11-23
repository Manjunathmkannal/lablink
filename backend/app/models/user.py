"""
User document schema + validation helpers.
"""
import re
from datetime import datetime, timezone
from typing import Optional

VALID_ROLES = {"student", "faculty", "admin", "lab_assistant"}
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def validate_user_payload(data: dict, require_password: bool = True) -> list[str]:
    """Return a list of validation error strings (empty → valid)."""
    errors: list[str] = []

    name = (data.get("name") or "").strip()
    if not name:
        errors.append("name is required")
    elif len(name) < 2:
        errors.append("name must be at least 2 characters")

    email = (data.get("email") or "").strip().lower()
    if not email:
        errors.append("email is required")
    elif not EMAIL_RE.match(email):
        errors.append("email is invalid")

    if require_password:
        password = data.get("password", "")
        if not password:
            errors.append("password is required")
        elif len(password) < 8:
            errors.append("password must be at least 8 characters")

    role = data.get("role", "student")
    if role not in VALID_ROLES:
        errors.append(f"role must be one of {sorted(VALID_ROLES)}")

    return errors


def build_user_doc(
    name: str,
    email: str,
    password_hash: str,
    role: str = "student",
    department_id=None,
    student_id: Optional[str] = None,
    phone: Optional[str] = None,
) -> dict:
    now = datetime.now(timezone.utc)
    return {
        "name": name.strip(),
        "email": email.strip().lower(),
        "password_hash": password_hash,
        "role": role,
        "department_id": department_id,
        "student_id": student_id,
        "phone": phone,
        "is_active": True,
        "created_at": now,
        "updated_at": now,
    }
