import json
import os
import threading
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from django.conf import settings


class JSONDataStore:
    """Small, atomic project-local JSON repository. No database is required."""

    _lock = threading.RLock()

    def __init__(self, path=None):
        self.path = Path(path or settings.JSON_DATA_FILE)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write({"next_search_id": 1, "next_result_id": 1, "searches": []})

    def _read(self):
        with self._lock:
            try:
                with self.path.open("r", encoding="utf-8") as handle:
                    return json.load(handle)
            except (FileNotFoundError, json.JSONDecodeError):
                return {"next_search_id": 1, "next_result_id": 1, "searches": []}

    def _write(self, data):
        with self._lock:
            temporary = self.path.with_suffix(".tmp")
            with temporary.open("w", encoding="utf-8") as handle:
                json.dump(data, handle, ensure_ascii=False, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
            temporary.replace(self.path)

    def save_search(self, metadata, results):
        with self._lock:
            data = self._read()
            search_id = data["next_search_id"]
            data["next_search_id"] += 1
            normalized = []
            for position, item in enumerate(results, 1):
                result = deepcopy(item)
                result["id"] = data["next_result_id"]
                data["next_result_id"] += 1
                result["position"] = position
                for key in ("latitude", "longitude"):
                    if result.get(key) is not None:
                        result[key] = str(result[key])
                normalized.append(result)
            search = {
                "id": search_id,
                **metadata,
                "result_count": len(normalized),
                "created_at": datetime.now(timezone.utc).isoformat(),
                "created_display": datetime.now().strftime("%b %d, %Y %H:%M"),
                "results": normalized,
            }
            data["searches"].insert(0, search)
            self._write(data)
            return deepcopy(search)

    def searches(self, limit=100):
        return deepcopy(self._read().get("searches", [])[:limit])

    def get_search(self, search_id=None):
        searches = self._read().get("searches", [])
        if search_id is None:
            return deepcopy(searches[0]) if searches else None
        try:
            wanted = int(search_id)
        except (TypeError, ValueError):
            return None
        return deepcopy(next((item for item in searches if item.get("id") == wanted), None))

    def stats(self):
        searches = self._read().get("searches", [])
        unique = {}
        for search in searches:
            for business in search.get("results", []):
                unique[business.get("place_id") or f'json:{business.get("id")}'] = business
        businesses = list(unique.values())
        available = lambda value: bool(value and value != "N/A")
        return {
            "searches": len(searches), "businesses": len(businesses),
            "with_phone": sum(available(item.get("phone")) for item in businesses),
            "with_website": sum(available(item.get("website")) for item in businesses),
        }

    def update_result(self, search_id, result_id, updates):
        with self._lock:
            data = self._read()
            for search in data.get("searches", []):
                if search.get("id") == int(search_id):
                    for result in search.get("results", []):
                        if result.get("id") == int(result_id):
                            result.update(updates)
                            self._write(data)
                            return deepcopy(result)
            return None

    def delete_result(self, search_id, result_id):
        with self._lock:
            data = self._read()
            for search in data.get("searches", []):
                if search.get("id") == int(search_id):
                    before = len(search.get("results", []))
                    search["results"] = [item for item in search.get("results", []) if item.get("id") != int(result_id)]
                    if len(search["results"]) == before:
                        return False
                    search["result_count"] = len(search["results"])
                    for position, item in enumerate(search["results"], 1):
                        item["position"] = position
                    self._write(data)
                    return True
            return False
