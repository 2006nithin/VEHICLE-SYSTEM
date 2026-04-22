import datetime
import os
import logging
from typing import Optional, List, Dict, Any

from pymongo import MongoClient
from pymongo.errors import PyMongoError

# Logging
logger = logging.getLogger("mongo_client")

# Environment variables
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
MONGODB_DB = os.getenv("MONGODB_DB", "vehicle_system")

_client: Optional[MongoClient] = None


# Normalize date → datetime for MongoDB
def _normalize_document(document: Dict[str, Any]) -> Dict[str, Any]:
    normalized = {}
    for key, value in document.items():
        if isinstance(value, datetime.date) and not isinstance(value, datetime.datetime):
            normalized[key] = datetime.datetime.combine(value, datetime.time.min)
        else:
            normalized[key] = value
    return normalized


# Initialize MongoDB connection
def get_client() -> MongoClient:
    global _client

    if _client is not None:
        return _client

    try:
        _client = MongoClient(
            MONGODB_URI,
            serverSelectionTimeoutMS=5000,
        )
        _client.server_info()  # Force connection test
        logger.info("✅ Connected to MongoDB")
        return _client

    except PyMongoError as e:
        logger.error(f"❌ MongoDB connection failed: {e}")
        raise RuntimeError("MongoDB connection failed")


# Get collection
def get_reminder_collection():
    client = get_client()
    return client[MONGODB_DB]["renewal_reminders"]


# Insert reminder
def insert_reminder(document: Dict[str, Any]) -> Dict[str, Any]:
    try:
        collection = get_reminder_collection()
        normalized = _normalize_document(document)

        result = collection.insert_one(normalized)

        return {
            "_id": str(result.inserted_id),
            **normalized
        }

    except PyMongoError as e:
        logger.error(f"Insert failed: {e}")
        raise RuntimeError("Failed to save reminder")


# Fetch reminders
def find_reminders(filter_query: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    try:
        collection = get_reminder_collection()
        query = filter_query or {}

        reminders = []

        for item in collection.find(query):
            formatted = {
                key: (value.isoformat() if isinstance(value, datetime.datetime) else value)
                for key, value in item.items()
                if key != "_id"
            }

            reminders.append({
                "_id": str(item["_id"]),
                **formatted
            })

        return reminders

    except PyMongoError as e:
        logger.error(f"Fetch failed: {e}")
        raise RuntimeError("Failed to fetch reminders")
