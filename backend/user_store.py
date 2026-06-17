import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _safe_user_id(email: str) -> str:
    return hashlib.sha256(email.strip().lower().encode("utf-8")).hexdigest()


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


class UserStore:
    def __init__(self, data_dir: Path) -> None:
        self.base_dir = data_dir / "users"
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _user_path(self, email: str) -> Path:
        return self.base_dir / f"{_safe_user_id(email)}.json"

    def load_user_data(self, email: str) -> dict[str, Any]:
        path = self._user_path(email)
        if not path.exists():
            return {
                "skills": [],
                "exclusions": [],
                "resume_text": "",
                "resume_file_name": "",
                "resume_updated_at": "",
                "validated_jobs": [],
            }
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            payload = {}
        if not isinstance(payload, dict):
            payload = {}
        return {
            "skills": payload.get("skills") if isinstance(payload.get("skills"), list) else [],
            "exclusions": payload.get("exclusions") if isinstance(payload.get("exclusions"), list) else [],
            "resume_text": str(payload.get("resume_text") or ""),
            "resume_file_name": str(payload.get("resume_file_name") or ""),
            "resume_updated_at": str(payload.get("resume_updated_at") or ""),
            "validated_jobs": payload.get("validated_jobs") if isinstance(payload.get("validated_jobs"), list) else [],
        }

    def save_user_data(self, email: str, payload: dict[str, Any]) -> dict[str, Any]:
        data = self.load_user_data(email)
        if "skills" in payload:
            data["skills"] = [str(item).strip() for item in payload.get("skills", []) if str(item).strip()]
        if "exclusions" in payload:
            data["exclusions"] = [str(item).strip() for item in payload.get("exclusions", []) if str(item).strip()]
        if "resume_text" in payload:
            data["resume_text"] = str(payload.get("resume_text") or "")
            data["resume_updated_at"] = _now_iso()
        if "resume_file_name" in payload:
            data["resume_file_name"] = str(payload.get("resume_file_name") or "")
            if payload.get("resume_file_name"):
                data["resume_updated_at"] = _now_iso()
        if "validated_jobs" in payload and isinstance(payload["validated_jobs"], list):
            data["validated_jobs"] = [str(item).strip() for item in payload["validated_jobs"] if str(item).strip()]

        self._user_path(email).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return data

    def add_validated_job(self, email: str, job_url: str) -> dict[str, Any]:
        data = self.load_user_data(email)
        if job_url not in data["validated_jobs"]:
            data["validated_jobs"].append(job_url)
        self.save_user_data(email, data)
        return data

    def remove_validated_job(self, email: str, job_url: str) -> dict[str, Any]:
        data = self.load_user_data(email)
        data["validated_jobs"] = [item for item in data.get("validated_jobs", []) if item != job_url]
        self.save_user_data(email, data)
        return data
