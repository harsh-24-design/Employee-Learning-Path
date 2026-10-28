import os
from typing import Optional
from pymongo import MongoClient
from pymongo.database import Database
from app.core.config import settings

class MongoDBClient:
    _client: Optional[MongoClient] = None
    _db: Optional[Database] = None
    _is_connected: bool = False
    _attempted: bool = False

    @classmethod
    def get_database(cls) -> Optional[Database]:
        if cls._attempted:
            return cls._db
        cls._attempted = True
        try:
            cls._client = MongoClient(
                settings.MONGODB_URI,
                serverSelectionTimeoutMS=500,
                connectTimeoutMS=500,
                socketTimeoutMS=500
            )
            # Test connection
            cls._client.admin.command('ping')
            cls._db = cls._client[settings.MONGODB_DB_NAME]
            cls._is_connected = True
            print("Successfully connected to MongoDB server.")
        except Exception as e:
            cls._is_connected = False
            cls._db = None
            print(f"MongoDB not reachable ({e}). Activating persistent local JSON/memory repository.")
        return cls._db

    @classmethod
    def is_connected(cls) -> bool:
        if not cls._attempted:
            cls.get_database()
        return cls._is_connected

def get_db() -> Optional[Database]:
    return MongoDBClient.get_database()
