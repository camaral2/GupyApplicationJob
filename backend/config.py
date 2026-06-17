import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR / "frontend"

if os.getenv("VERCEL") == "1":
    DATA_DIR = Path("/tmp/gupy-data")
else:
    DATA_DIR = BACKEND_DIR / "data"

DATA_DIR.mkdir(parents=True, exist_ok=True)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    gemini_api_key: str | None = None
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    default_resume_path: str | None = None
    host: str = "0.0.0.0"
    port: int = 8000


settings = Settings()
