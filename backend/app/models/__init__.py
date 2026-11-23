"""
Shared model helpers – pure Python, no DB calls.
"""
from bson import ObjectId


def to_str_id(doc: dict) -> dict:
    """Convert ObjectId _id (and any *_id fields) to strings for JSON serialisation."""
    if doc is None:
        return doc
    out = dict(doc)
    for key, val in out.items():
        if isinstance(val, ObjectId):
            out[key] = str(val)
    return out
