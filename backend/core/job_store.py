"""Thread-safe in-memory job store.

Each job looks like:
{
    "status": "processing" | "completed" | "failed",
    "result": MTOResult | None,
    "error": str | None,
    "created_at": float (unix timestamp),
    "filename": str,
}
"""
import threading
import time
import uuid
from typing import Any


class JobStore:
    def __init__(self):
        self._store: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()

    def create_job(self, filename: str) -> str:
        job_id = str(uuid.uuid4())
        with self._lock:
            self._store[job_id] = {
                "status": "processing",
                "result": None,
                "error": None,
                "created_at": time.time(),
                "filename": filename,
            }
        return job_id

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        with self._lock:
            return self._store.get(job_id)

    def complete_job(self, job_id: str, result: Any) -> None:
        with self._lock:
            if job_id in self._store:
                self._store[job_id]["status"] = "completed"
                self._store[job_id]["result"] = result

    def fail_job(self, job_id: str, error: str) -> None:
        with self._lock:
            if job_id in self._store:
                self._store[job_id]["status"] = "failed"
                self._store[job_id]["error"] = error

    def job_exists(self, job_id: str) -> bool:
        with self._lock:
            return job_id in self._store


# Singleton
job_store = JobStore()
