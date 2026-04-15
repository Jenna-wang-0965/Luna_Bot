from __future__ import annotations

from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Always load `backend/.env` (not cwd-dependent).
_BACKEND_DIR = Path(__file__).resolve().parent.parent
_ENV_FILE = _BACKEND_DIR / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_ENV_FILE, env_file_encoding="utf-8", extra="ignore")

    supabase_url: str = Field(min_length=1, description="Project URL from Supabase → Settings → API")
    supabase_service_role_key: str = Field(
        min_length=1, description="Secret / service_role key (server only)"
    )

    @field_validator("supabase_url", "supabase_service_role_key", mode="before")
    @classmethod
    def strip_whitespace(cls, v: object) -> object:
        if isinstance(v, str):
            return v.strip()
        return v

    @field_validator("supabase_url")
    @classmethod
    def normalize_supabase_url(cls, v: str) -> str:
        # httpx raises UnsupportedProtocol if the URL has no scheme (e.g. "xxx.supabase.co").
        if not v.startswith(("http://", "https://")):
            v = f"https://{v}"
        return v.rstrip("/")

    port: int = 8080
    owner_shared_secret: str = "dev-owner-secret-change-me"

    # Optional: LLM for more meaningful replies (OpenAI-compatible HTTP API)
    # Env vars:
    #   LLM_API_KEY
    #   LLM_BASE_URL (default https://api.openai.com/v1)
    #   LLM_MODEL (default gpt-4o-mini)
    llm_api_key: str = Field(default="", alias="LLM_API_KEY")
    llm_base_url: str = Field(default="https://api.openai.com/v1", alias="LLM_BASE_URL")
    llm_model: str = Field(default="gpt-4o-mini", alias="LLM_MODEL")

    # Optional: Stream Chat (for the starter UI DMs tab)
    # Env vars:
    #   STREAM_API_KEY
    #   STREAM_API_SECRET
    stream_api_key: str = Field(default="", alias="STREAM_API_KEY")
    stream_api_secret: str = Field(default="", alias="STREAM_API_SECRET")

    scheduler_enabled: bool = True
    scheduler_tick_seconds: int = 5
    diary_stale_after_seconds: int = 90
    max_diary_posts_per_agent_per_hour: int = 3


settings = Settings()
