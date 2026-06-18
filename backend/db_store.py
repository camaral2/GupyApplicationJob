import hashlib
import hmac
import json
import secrets
from typing import Any

from psycopg import connect
from psycopg.rows import dict_row


class DatabaseStore:
    def __init__(self, database_url: str) -> None:
        self.database_url = database_url

    def _conn(self):
        return connect(self.database_url, row_factory=dict_row)

    def init_schema(self) -> None:
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS users (
                        email TEXT PRIMARY KEY,
                        password_hash TEXT NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS sessions (
                        token TEXT PRIMARY KEY,
                        email TEXT NOT NULL REFERENCES users(email) ON DELETE CASCADE,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS user_profiles (
                        email TEXT PRIMARY KEY REFERENCES users(email) ON DELETE CASCADE,
                        skills JSONB NOT NULL DEFAULT '[]'::jsonb,
                        exclusions JSONB NOT NULL DEFAULT '[]'::jsonb,
                        resume_text TEXT NOT NULL DEFAULT '',
                        resume_file_name TEXT NOT NULL DEFAULT '',
                        resume_updated_at TIMESTAMPTZ NULL
                    );
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS validated_jobs (
                        email TEXT NOT NULL REFERENCES users(email) ON DELETE CASCADE,
                        job_url TEXT NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        PRIMARY KEY (email, job_url)
                    );
                    """
                )
            conn.commit()

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

    def ensure_profile(self, email: str) -> None:
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO user_profiles(email)
                    VALUES (%s)
                    ON CONFLICT (email) DO NOTHING
                    """,
                    (email,),
                )
            conn.commit()

    def register_user(self, email: str, password: str) -> dict[str, Any]:
        email = email.strip().lower()
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT email FROM users WHERE email = %s", (email,))
                if cur.fetchone():
                    raise ValueError("Este email já está cadastrado.")
                cur.execute(
                    "INSERT INTO users(email, password_hash) VALUES (%s, %s)",
                    (email, self._hash_password(password)),
                )
                cur.execute(
                    """
                    INSERT INTO user_profiles(email)
                    VALUES (%s)
                    ON CONFLICT (email) DO NOTHING
                    """,
                    (email,),
                )
            conn.commit()
        return {"email": email}

    def login_user(self, email: str, password: str) -> dict[str, str]:
        email = email.strip().lower()
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT password_hash FROM users WHERE email = %s", (email,))
                row = cur.fetchone()
                if not row or not self._verify_password(password, str(row.get("password_hash") or "")):
                    raise ValueError("Email ou senha inválidos.")

                token = secrets.token_urlsafe(32)
                cur.execute("INSERT INTO sessions(token, email) VALUES (%s, %s)", (token, email))
            conn.commit()
        return {"token": token, "email": email}

    def get_email_by_token(self, token: str) -> str | None:
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT email FROM sessions WHERE token = %s", (token,))
                row = cur.fetchone()
                if not row:
                    return None
                return str(row.get("email") or "").strip().lower() or None

    def revoke_token(self, token: str) -> None:
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM sessions WHERE token = %s", (token,))
            conn.commit()

    def load_user_data(self, email: str) -> dict[str, Any]:
        email = email.strip().lower()
        self.ensure_profile(email)
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT skills::text AS skills,
                           exclusions::text AS exclusions,
                           resume_text,
                           resume_file_name,
                           COALESCE(TO_CHAR(resume_updated_at, 'YYYY-MM-DD"T"HH24:MI:SSOF'), '') AS resume_updated_at
                    FROM user_profiles
                    WHERE email = %s
                    """,
                    (email,),
                )
                profile = cur.fetchone() or {}

                cur.execute(
                    "SELECT job_url FROM validated_jobs WHERE email = %s ORDER BY created_at DESC",
                    (email,),
                )
                jobs = [str(row.get("job_url") or "").strip() for row in cur.fetchall() if str(row.get("job_url") or "").strip()]

        skills = []
        exclusions = []
        try:
            skills = json.loads(profile.get("skills") or "[]")
        except Exception:
            skills = []
        try:
            exclusions = json.loads(profile.get("exclusions") or "[]")
        except Exception:
            exclusions = []

        return {
            "skills": skills if isinstance(skills, list) else [],
            "exclusions": exclusions if isinstance(exclusions, list) else [],
            "resume_text": str(profile.get("resume_text") or ""),
            "resume_file_name": str(profile.get("resume_file_name") or ""),
            "resume_updated_at": str(profile.get("resume_updated_at") or ""),
            "validated_jobs": jobs,
        }

    def save_user_data(self, email: str, payload: dict[str, Any]) -> dict[str, Any]:
        email = email.strip().lower()
        self.ensure_profile(email)
        current = self.load_user_data(email)

        skills = current["skills"]
        exclusions = current["exclusions"]
        resume_text = current["resume_text"]
        resume_file_name = current["resume_file_name"]
        resume_updated_at = current["resume_updated_at"]

        if "skills" in payload:
            skills = [str(item).strip() for item in payload.get("skills", []) if str(item).strip()]
        if "exclusions" in payload:
            exclusions = [str(item).strip() for item in payload.get("exclusions", []) if str(item).strip()]
        if "resume_text" in payload:
            resume_text = str(payload.get("resume_text") or "")
            resume_updated_at = "NOW"
        if "resume_file_name" in payload:
            resume_file_name = str(payload.get("resume_file_name") or "")
            if payload.get("resume_file_name"):
                resume_updated_at = "NOW"

        with self._conn() as conn:
            with conn.cursor() as cur:
                if resume_updated_at == "NOW":
                    cur.execute(
                        """
                        UPDATE user_profiles
                        SET skills = %s::jsonb,
                            exclusions = %s::jsonb,
                            resume_text = %s,
                            resume_file_name = %s,
                            resume_updated_at = NOW()
                        WHERE email = %s
                        """,
                        (json.dumps(skills, ensure_ascii=False), json.dumps(exclusions, ensure_ascii=False), resume_text, resume_file_name, email),
                    )
                else:
                    cur.execute(
                        """
                        UPDATE user_profiles
                        SET skills = %s::jsonb,
                            exclusions = %s::jsonb,
                            resume_text = %s,
                            resume_file_name = %s
                        WHERE email = %s
                        """,
                        (json.dumps(skills, ensure_ascii=False), json.dumps(exclusions, ensure_ascii=False), resume_text, resume_file_name, email),
                    )
            conn.commit()

        return self.load_user_data(email)

    def add_validated_job(self, email: str, job_url: str) -> dict[str, Any]:
        email = email.strip().lower()
        job_url = job_url.strip()
        if not job_url:
            return self.load_user_data(email)
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO validated_jobs(email, job_url)
                    VALUES (%s, %s)
                    ON CONFLICT (email, job_url) DO NOTHING
                    """,
                    (email, job_url),
                )
            conn.commit()
        return self.load_user_data(email)

    def remove_validated_job(self, email: str, job_url: str) -> dict[str, Any]:
        email = email.strip().lower()
        job_url = job_url.strip()
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM validated_jobs WHERE email = %s AND job_url = %s", (email, job_url))
            conn.commit()
        return self.load_user_data(email)
