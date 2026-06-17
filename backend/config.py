import os
import tempfile
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR / "frontend"

def _resolve_data_dir() -> Path:
    custom_data_dir = os.getenv("DATA_DIR")
    if custom_data_dir:
        return Path(custom_data_dir)

    # Ambientes serverless normalmente possuem código em filesystem somente leitura.
    if os.getenv("VERCEL") == "1" or os.getenv("VERCEL_ENV"):
        return Path(tempfile.gettempdir()) / "gupy-data"

    local_dir = BACKEND_DIR / "data"
    try:
        local_dir.mkdir(parents=True, exist_ok=True)
        probe = local_dir / ".write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return local_dir
    except Exception:
        return Path(tempfile.gettempdir()) / "gupy-data"


DATA_DIR = _resolve_data_dir()

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
