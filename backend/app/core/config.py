"""Settings read from backend/.env (PLAN.md §5.3). Never log secret values."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- core (A) ---
    database_url: str = "postgresql+psycopg://daha:daha@localhost:5432/daha"
    test_database_url: str = "postgresql+psycopg://daha:daha@localhost:5432/daha_test"
    jwt_secret: str = Field(default="change-me", repr=False)
    allowed_email_domains: str = "stanford.edu"
    demo_mode: bool = True
    public_base_url: str = "http://localhost:3000"
    upload_dir: str = "./uploads"
    campus_tz: str = "America/Los_Angeles"
    cors_origins: str = "http://localhost:3000"

    # --- AI & discovery (C) ---
    ai_provider: str = "mock"  # mock | harnessrouter | anthropic
    ai_mock_latency_ms: int = 2500
    ai_max_images_per_scan: int = 6
    ai_daily_scans_per_user: int = 20
    ai_budget_usd: float = 40.0
    harnessrouter_api_key: str = Field(default="", repr=False)
    harnessrouter_base_url: str = "https://api.harnessrouter.ai"
    harnessrouter_vision_harness_id: str = ""
    harnessrouter_base: str = "claude-code"
    harnessrouter_model: str = ""
    harnessrouter_max_concurrency: int = 2
    harnessrouter_timeout_s: int = 180
    harnessrouter_est_cost_per_image: float = 0.10
    anthropic_api_key: str = Field(default="", repr=False)
    anthropic_model: str = "claude-opus-5-5"
    anthropic_effort: str = "medium"
    embeddings_provider: str = "fastembed"  # fastembed | hash (tests/CI)
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    match_min_score: float = 0.55
    ai_enrich_requests: bool = False

    @property
    def allowed_email_domain_list(self) -> list[str]:
        return [d.strip().lower() for d in self.allowed_email_domains.split(",") if d.strip()]

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def upload_path(self) -> Path:
        p = Path(self.upload_dir)
        return p if p.is_absolute() else BACKEND_DIR / p


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
