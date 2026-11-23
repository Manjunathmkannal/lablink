"""
IBM watsonx.ai service wrapper.

Authentication uses IBM IAM token exchange:
  POST https://iam.cloud.ibm.com/identity/token
  → Bearer token used in watsonx inference calls.

All calls go through Flask; credentials never leave the server.
AI is advisory only – it NEVER approves bookings or modifies data.
"""
import os
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

import requests
from flask import current_app

logger = logging.getLogger(__name__)

# IAM token cache (per-process, not shared across workers – acceptable for advisory AI)
_iam_cache: dict = {"token": None, "expires_at": None}

_IAM_URL = "https://iam.cloud.ibm.com/identity/token"
_REQUEST_TIMEOUT = 20   # seconds


def _get_iam_token(api_key: str) -> Optional[str]:
    """Exchange IBM Cloud API key for a short-lived IAM Bearer token (cached)."""
    now = datetime.now(timezone.utc)
    if _iam_cache["token"] and _iam_cache["expires_at"] and _iam_cache["expires_at"] > now:
        return _iam_cache["token"]

    try:
        resp = requests.post(
            _IAM_URL,
            data={
                "grant_type": "urn:ibm:params:oauth:grant-type:apikey",
                "apikey": api_key,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=_REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        payload = resp.json()
        token = payload.get("access_token")
        # IBM tokens typically expire in 3600 s; refresh 5 minutes early
        expires_in = int(payload.get("expires_in", 3600))
        _iam_cache["token"] = token
        _iam_cache["expires_at"] = now + timedelta(seconds=expires_in - 300)
        return token
    except requests.RequestException as exc:
        logger.warning("IAM token exchange failed: %s", exc)
        return None


def _watsonx_generate(prompt: str, model_id: str = "ibm/granite-13b-instruct-v2") -> Optional[str]:
    """
    Call the watsonx.ai text generation endpoint.
    Returns the generated text string, or None on failure.
    """
    cfg = current_app.config
    api_key = cfg.get("WATSONX_API_KEY", "")
    project_id = cfg.get("WATSONX_PROJECT_ID", "")
    base_url = cfg.get("WATSONX_URL", "https://us-south.ml.cloud.ibm.com")

    if not api_key or not project_id:
        return None

    token = _get_iam_token(api_key)
    if not token:
        return None

    url = f"{base_url}/ml/v1/text/generation?version=2023-05-29"
    payload = {
        "model_id": model_id,
        "project_id": project_id,
        "input": prompt,
        "parameters": {
            "decoding_method": "greedy",
            "max_new_tokens": 400,
            "stop_sequences": ["</answer>"],
        },
    }
    try:
        resp = requests.post(
            url,
            json=payload,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            timeout=_REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        results = resp.json().get("results", [])
        if results:
            return results[0].get("generated_text", "").strip()
        return None
    except requests.Timeout:
        logger.warning("watsonx.ai call timed out")
        return None
    except requests.RequestException as exc:
        logger.warning("watsonx.ai call failed: %s", exc)
        return None


# ── Public API ─────────────────────────────────────────────────────────────────

def is_configured() -> bool:
    cfg = current_app.config
    return bool(cfg.get("WATSONX_API_KEY") and cfg.get("WATSONX_PROJECT_ID"))


def recommend_equipment(project_description: str, available_equipment: list) -> dict:
    """
    Recommend equipment from the available list that suits the project.
    Returns {"recommendations": [...], "explanation": str, "mode": "ai"|"stub"}.
    AI is advisory only – caller must still enforce all booking rules.
    """
    if not is_configured():
        return _stub_recommend(available_equipment)

    equip_summary = "\n".join(
        f"- {e.get('name')} ({e.get('category', '')}): {e.get('description', '')}"
        for e in available_equipment[:20]
    )
    prompt = (
        "You are a university lab resource assistant.\n"
        "A student has described their project:\n"
        f'"{project_description}"\n\n'
        "Available equipment:\n"
        f"{equip_summary}\n\n"
        "List up to 3 equipment items best suited for this project. "
        "For each, give the name and one sentence explaining why it is suitable. "
        "Format as a JSON array: "
        '[{"name": "...", "reason": "..."}]'
        " only. Do not add extra text.\n<answer>"
    )

    raw = _watsonx_generate(prompt)
    if not raw:
        return _stub_recommend(available_equipment)

    import json, re
    # Extract JSON array from response
    match = re.search(r'\[.*\]', raw, re.DOTALL)
    if not match:
        return _stub_recommend(available_equipment)
    try:
        recs = json.loads(match.group())
        # Cross-reference against actual equipment names
        eq_names = {e.get("name", ""): e for e in available_equipment}
        enriched = []
        for rec in recs[:3]:
            eq = eq_names.get(rec.get("name", ""))
            enriched.append({
                "name": rec.get("name", ""),
                "reason": rec.get("reason", ""),
                "equipment_id": str(eq["_id"]) if eq else None,
                "status": eq.get("status") if eq else None,
            })
        return {"recommendations": enriched, "mode": "ai"}
    except (json.JSONDecodeError, KeyError):
        return _stub_recommend(available_equipment)


def suggest_slots(
    equipment_id: str,
    preferred_date: str,
    existing_bookings: list,
) -> dict:
    """
    Suggest up to 3 free 2-hour time slots for the given equipment.
    Uses availability data from the DB (passed in by the route).
    AI is advisory only – booking creation still requires the full service layer.
    """
    # Build a simple gap-finding algorithm first (always works)
    slots = _find_free_slots(preferred_date, existing_bookings)

    if not is_configured() or not slots:
        return {"slots": slots, "mode": "computed"}

    # Ask watsonx to rank/explain the slots
    prompt = (
        "You are a university lab scheduling assistant.\n"
        f"Available 2-hour slots on {preferred_date}:\n"
        + "\n".join(f"- {s['start']} to {s['end']}" for s in slots)
        + "\nRank these slots from best to worst for a student project booking "
        "and add a one-sentence reason for the top pick. "
        'Return JSON: {"ranked": [{"start":"...","end":"...","reason":"..."}]}.\n<answer>'
    )
    raw = _watsonx_generate(prompt)
    if raw:
        import json, re
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if match:
            try:
                ranked = json.loads(match.group()).get("ranked", slots)
                return {"slots": ranked[:3], "mode": "ai"}
            except (json.JSONDecodeError, KeyError):
                pass
    return {"slots": slots, "mode": "computed"}


def draft_request(project_description: str) -> dict:
    """
    Help student fill out a project request form from a free-text description.
    Returns pre-filled fields; student must review and submit.
    """
    if not is_configured():
        return {
            "title": "",
            "description": project_description,
            "mode": "stub",
        }

    prompt = (
        "You are a university lab resource assistant.\n"
        "A student wrote this description of their project:\n"
        f'"{project_description}"\n\n'
        "Generate a structured project request with a concise title and "
        "a clear 2-3 sentence description suitable for faculty review. "
        'Return only JSON: {"title": "...", "description": "..."}.\n<answer>'
    )
    raw = _watsonx_generate(prompt)
    if raw:
        import json, re
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if match:
            try:
                fields = json.loads(match.group())
                fields["mode"] = "ai"
                return fields
            except (json.JSONDecodeError, KeyError):
                pass
    return {"title": "", "description": project_description, "mode": "stub"}


# ── Internal helpers ───────────────────────────────────────────────────────────

def _stub_recommend(equipment: list) -> dict:
    """Fallback when AI is not configured: return first 3 available items."""
    recs = [
        {"name": e.get("name", ""), "reason": "Available in lab", "equipment_id": str(e["_id"]), "status": e.get("status")}
        for e in equipment[:3]
        if e.get("status") == "available"
    ]
    return {"recommendations": recs, "mode": "stub"}


def _find_free_slots(preferred_date: str, bookings: list) -> list:
    """Return up to 3 free 2-hour slots on preferred_date not overlapping bookings."""
    from datetime import datetime, timezone, timedelta
    try:
        from datetime import date
        ref = date.fromisoformat(preferred_date)
    except (ValueError, TypeError):
        from datetime import datetime as dt
        ref = dt.now(timezone.utc).date()

    day_start = datetime(ref.year, ref.month, ref.day, 8, 0, tzinfo=timezone.utc)
    day_end   = datetime(ref.year, ref.month, ref.day, 18, 0, tzinfo=timezone.utc)
    slot_len  = timedelta(hours=2)
    intervals = []
    for b in bookings:
        s, e = b.get("start_time"), b.get("end_time")
        if s and e:
            if isinstance(s, str):
                s = datetime.fromisoformat(s.replace("Z", "+00:00"))
            if isinstance(e, str):
                e = datetime.fromisoformat(e.replace("Z", "+00:00"))
            if s.tzinfo is None:
                s = s.replace(tzinfo=timezone.utc)
            if e.tzinfo is None:
                e = e.replace(tzinfo=timezone.utc)
            intervals.append((s, e))

    candidate = day_start
    slots = []
    while candidate + slot_len <= day_end and len(slots) < 3:
        overlap = any(s < candidate + slot_len and e > candidate for s, e in intervals)
        if not overlap:
            slots.append({"start": candidate.isoformat(), "end": (candidate + slot_len).isoformat()})
            candidate += slot_len
        else:
            blocking_end = max(e for s, e in intervals if s < candidate + slot_len and e > candidate)
            candidate = blocking_end
    return slots
