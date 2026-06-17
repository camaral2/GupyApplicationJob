import hashlib
import hmac
import json
import secrets
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


class AuthStore:
    def __init__(self, data_dir: Path) -> None:
        self.auth_dir = data_dir / "auth"
        self.auth_dir.mkdir(parents=True, exist_ok=True)
        self.users_path = self.auth_dir / "users.json"
        self.sessions_path = self.auth_dir / "sessions.json"

    def _read_json(self, path: Path, fallback: dict[str, Any]) -> dict[str, Any]:
        if not path.exists():
            return fallback
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                return payload
        except Exception:
            return fallback
        return fallback

    def _write_json(self, path: Path, payload: dict[str, Any]) -> None:
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def _read_users(self) -> dict[str, Any]:
        return self._read_json(self.users_path, {"users": {}})

    def _write_users(self, payload: dict[str, Any]) -> None:
        self._write_json(self.users_path, payload)

    def _read_sessions(self) -> dict[str, Any]:
        return self._read_json(self.sessions_path, {"sessions": {}})

    def _write_sessions(self, payload: dict[str, Any]) -> None:
        self._write_json(self.sessions_path, payload)

    def _hash_password(self, password: str, salt: str | None = None) -> str:
        token_salt = salt or secrets.token_hex(16)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), token_salt.encode("utf-8"), 100_000).hex()
        return f"{token_salt}${digest}"

    def _verify_password(self, password: str, saved_hash: str) -> bool:
        if "$" not in saved_hash:
            return False
        salt, _ = saved_hash.split("$", 1)
        candidate = self._hash_password(password, salt=salt)
        return hmac.compare_digest(candidate, saved_hash)

    def register_user(self, email: str, password: str) -> dict[str, Any]:
        email = email.strip().lower()
        users = self._read_users()
        records = users.get("users") or {}
        if email in records:
            raise ValueError("Este email já está cadastrado.")
        records[email] = {
            "password_hash": self._hash_password(password),
            "created_at": _now_iso(),
        }
        users["users"] = records
        self._write_users(users)
        return {"email": email}

    def login_user(self, email: str, password: str) -> dict[str, str]:
        email = email.strip().lower()
        users = self._read_users()
        record = (users.get("users") or {}).get(email)
        if not record or not self._verify_password(password, str(record.get("password_hash") or "")):
            raise ValueError("Email ou senha inválidos.")

        token = secrets.token_urlsafe(32)
        sessions = self._read_sessions()
        active_sessions = sessions.get("sessions") or {}
        active_sessions[token] = {
            "email": email,
            "created_at": _now_iso(),
        }
        sessions["sessions"] = active_sessions
        self._write_sessions(sessions)
        return {"token": token, "email": email}

    def get_email_by_token(self, token: str) -> str | None:
        sessions = self._read_sessions()
        active_sessions = sessions.get("sessions") or {}
        session = active_sessions.get(token) or {}
        email = str(session.get("email") or "").strip().lower()
        return email or None

    def revoke_token(self, token: str) -> None:
        sessions = self._read_sessions()
        active_sessions = sessions.get("sessions") or {}
        if token in active_sessions:
            del active_sessions[token]
            sessions["sessions"] = active_sessions
            self._write_sessions(sessions)
