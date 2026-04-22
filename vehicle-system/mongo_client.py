import datetime
import os
from pymongo import MongoClient
from pymongo.errors import PyMongoError

MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
MONGODB_DB = os.getenv("MONGODB_DB", "vehicle_system")

_client: MongoClient | None = None
_connected: bool = False

def _normalize_document(document: dict) -> dict:
    normalized = {}
    for key, value in document.items():
        if isinstance(value, datetime.date) and not isinstance(value, datetime.datetime):
            normalized[key] = datetime.datetime.combine(value, datetime.time.min)
        else:
            normalized[key] = value
    return normalized


def init_mongo_client() -> bool:
    global _client, _connected
    if _client is not None and _connected:
        return True
    try:
        _client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
        _client.server_info()
        _connected = True
    except PyMongoError:
        _client = None
        _connected = False
    return _connected


def get_reminder_collection():
    if _client is None:
        if not init_mongo_client():
            raise RuntimeError(f"MongoDB is not available at {MONGODB_URI}")
    return _client[MONGODB_DB]["renewal_reminders"]


def insert_reminder(document: dict) -> dict:
    try:
        collection = get_reminder_collection()
        normalized = _normalize_document(document)
        result = collection.insert_one(normalized)
        return {**normalized, "_id": str(result.inserted_id)}
    except PyMongoError as error:
        raise RuntimeError(f"Failed to save reminder: {error}")


def find_reminders(filter_query: dict = None) -> list[dict]:
    collection = get_reminder_collection()
    query = filter_query or {}
    reminders = []
    for item in collection.find(query):
        normalized = {k: (v.isoformat() if isinstance(v, datetime.datetime) else v) for k, v in item.items() if k != "_id"}
        reminders.append({"_id": str(item["_id"]), **normalized})
    return reminders
