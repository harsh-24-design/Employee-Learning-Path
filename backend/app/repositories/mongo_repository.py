import os
import json
import copy
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from app.core.config import settings
from app.core.database import MongoDBClient

class Repository:
    """
    Unified Data Repository.
    Attempts MongoDB operations first; if unreachable, gracefully persists
    in-memory and flushes changes to data/storage_cache.json.
    """
    def __init__(self):
        self.cache_file = os.path.join(settings.DATA_DIR, "storage_cache.json")
        self.local_storage: Dict[str, List[Dict[str, Any]]] = {
            "employees": [],
            "employee_skills": [],
            "skills": [],
            "courses": [],
            "roles": [],
            "learning_plans": [],
            "learning_progress": [],
            "assessments": [],
            "chat_conversations": [],
            "chat_messages": []
        }
        self.use_mongo = False
        self._init_connection()

    def _init_connection(self):
        try:
            db = MongoDBClient.get_database()
            if db is not None:
                self.db = db
                self.use_mongo = True
            else:
                self.use_mongo = False
                self._load_cache()
        except Exception:
            self.use_mongo = False
            self._load_cache()

    def _load_cache(self):
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for k, v in data.items():
                        self.local_storage[k] = v
            except Exception as e:
                print(f"Error reading local cache: {e}")

    def _persist_cache(self):
        if not self.use_mongo:
            try:
                os.makedirs(os.path.dirname(self.cache_file), exist_ok=True)
                with open(self.cache_file, "w", encoding="utf-8") as f:
                    json.dump(self.local_storage, f, indent=2)
            except Exception as e:
                print(f"Error persisting local cache: {e}")

    def insert(self, collection_name: str, document: Dict[str, Any]) -> Dict[str, Any]:
        doc = copy.deepcopy(document)
        now_str = datetime.now(timezone.utc).isoformat()
        if "created_at" not in doc:
            doc["created_at"] = now_str
        doc["updated_at"] = now_str

        if self.use_mongo:
            try:
                col = self.db[collection_name]
                res = col.insert_one(doc)
                doc["_id"] = str(res.inserted_id)
                return doc
            except Exception:
                self.use_mongo = False

        if collection_name not in self.local_storage:
            self.local_storage[collection_name] = []
        self.local_storage[collection_name].append(doc)
        self._persist_cache()
        return doc

    def find(self, collection_name: str, query: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        query = query or {}
        if self.use_mongo:
            try:
                col = self.db[collection_name]
                cursor = col.find(query)
                docs = []
                for d in cursor:
                    if "_id" in d:
                        d["_id"] = str(d["_id"])
                    docs.append(d)
                return docs
            except Exception:
                self.use_mongo = False

        items = self.local_storage.get(collection_name, [])
        if not query:
            return copy.deepcopy(items)

        results = []
        for item in items:
            match = True
            for k, v in query.items():
                if item.get(k) != v:
                    match = False
                    break
            if match:
                results.append(copy.deepcopy(item))
        return results

    def find_one(self, collection_name: str, query: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        docs = self.find(collection_name, query)
        return docs[0] if docs else None

    def update(self, collection_name: str, query: Dict[str, Any], update_data: Dict[str, Any], upsert: bool = False) -> bool:
        update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
        if self.use_mongo:
            try:
                col = self.db[collection_name]
                col.update_many(query, {"$set": update_data}, upsert=upsert)
                return True
            except Exception:
                self.use_mongo = False

        items = self.local_storage.get(collection_name, [])
        updated = False
        for item in items:
            match = all(item.get(k) == v for k, v in query.items())
            if match:
                item.update(update_data)
                updated = True

        if not updated and upsert:
            new_item = copy.deepcopy(query)
            new_item.update(update_data)
            items.append(new_item)
            updated = True

        if updated:
            self._persist_cache()
        return updated

    # Specific convenience queries
    def get_employee(self, employee_id: str) -> Optional[Dict[str, Any]]:
        return self.find_one("employees", {"employee_id": employee_id})

    def get_employee_skills(self, employee_id: str) -> List[Dict[str, Any]]:
        return self.find("employee_skills", {"employee_id": employee_id})

    def update_employee_skill(
        self,
        employee_id: str,
        skill: str,
        self_level: Optional[int] = None,
        verified_level: Optional[int] = None,
        source: Optional[str] = "assessment"
    ):
        query = {"employee_id": employee_id, "skill": skill}
        update_data: Dict[str, Any] = {"skill_id": skill}
        if self_level is not None:
            update_data["self_assessed_level"] = self_level
        if verified_level is not None:
            update_data["verified_level"] = verified_level
        if source:
            update_data["assessment_source"] = source
        self.update("employee_skills", query, update_data, upsert=True)

    def get_all_courses(self) -> List[Dict[str, Any]]:
        return self.find("courses")

    def get_course(self, course_id: str) -> Optional[Dict[str, Any]]:
        return self.find_one("courses", {"course_id": course_id})

    def get_all_roles(self) -> List[Dict[str, Any]]:
        return self.find("roles")

    def get_role(self, role_name: str) -> Optional[Dict[str, Any]]:
        return self.find_one("roles", {"role_name": role_name})

    def get_active_plan(self, employee_id: str) -> Optional[Dict[str, Any]]:
        plans = self.find("learning_plans", {"employee_id": employee_id})
        if plans:
            plans.sort(key=lambda x: x.get("version", 1), reverse=True)
            return plans[0]
        return None

    def save_plan(self, plan_dict: Dict[str, Any]) -> Dict[str, Any]:
        return self.insert("learning_plans", plan_dict)

    def get_learning_progress(self, employee_id: str, course_id: Optional[str] = None) -> List[Dict[str, Any]]:
        query = {"employee_id": employee_id}
        if course_id:
            query["course_id"] = course_id
        return self.find("learning_progress", query)

    def get_assessments(self, employee_id: str) -> List[Dict[str, Any]]:
        return self.find("assessments", {"employee_id": employee_id})

    def get_chat_conversations(self, employee_id: str) -> List[Dict[str, Any]]:
        return self.find("chat_conversations", {"employee_id": employee_id})

    def get_chat_messages(self, conversation_id: str) -> List[Dict[str, Any]]:
        return self.find("chat_messages", {"conversation_id": conversation_id})

repository = Repository()
