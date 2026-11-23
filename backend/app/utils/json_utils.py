"""
Shared response helpers.
"""
from bson import ObjectId
from datetime import datetime
import json


class MongoJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, ObjectId):
            return str(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


def mongo_to_json(doc):
    """Recursively convert ObjectId and datetime in a dict/list."""
    if isinstance(doc, list):
        return [mongo_to_json(d) for d in doc]
    if isinstance(doc, dict):
        return {k: mongo_to_json(v) for k, v in doc.items()}
    if isinstance(doc, ObjectId):
        return str(doc)
    if isinstance(doc, datetime):
        return doc.isoformat()
    return doc
