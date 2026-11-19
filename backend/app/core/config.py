"""Settings read from backend/.env (PLAN.md §5.3). Never log secret values."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_core import PydanticUseDefault
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


def csv_list(value: str) -> list[str]:
    """'a, b,,c' → ['a', 'b', 'c'] (trimmed, empties dropped, order kept)."""
    return [part.strip() for part in value.split(",") if part.strip()]


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
    harnessrouter_api_key: str = Field(default="", repr=False)  # comma-separated if several
    harnessrouter_base_url: str = "https://api.harnessrouter.ai"
    harnessrouter_vision_harness_id: str = ""  # one shared id, or one per key in the same order
    harnessrouter_base: str = "claude-code"
    harnessrouter_model: str = ""
    # low | medium | high | xhigh, set on every harness the setup script creates; "" = model default
    harnessrouter_reasoning_effort: str = ""
    # Run each photo on two keys at once when a task slot is free; the first answer wins
    # (app/ai/providers/harnessrouter.py, _race). Faster and steadier, about twice the cost.
    harnessrouter_race: bool = False
    harnessrouter_max_concurrency: int = 2
    harnessrouter_timeout_s: int = 180
    harnessrouter_est_cost_per_image: float = 0.10
    # Mutual matching (docs/plans/mutual-matching.md). Off unless backend/.env turns it on.
    mutual_matching: str = "off"  # off | rules (free) | ai (rules + HarnessRouter habit profiles)
    mutual_budget_usd: float = 3.0  # hard stop for paid profile tasks
    mutual_est_cost_per_profile: float = 0.05  # used when the API reports no cost
    harnessrouter_profile_harness_id: str = ""  # one shared id, or one per key in the same order
    # Condition check (handoff vs return photos of a lent item). Off unless backend/.env says so.
    condition_check_enabled: bool = False
    harnessrouter_condition_harness_id: str = ""  # one shared id, or one per key in the same order
    condition_budget_usd: float = 2.0  # hard stop for paid condition checks (all time)
    condition_est_cost_per_check: float = 0.05  # used when the API reports no cost
    # Handoff coordinator (docs/plans/handoff-coordinator.md). Off unless backend/.env turns it on.
    handoff_coordinator_enabled: bool = False
    harnessrouter_handoff_harness_id: str = ""  # one shared id, or one per key in the same order
    harnessrouter_handoff_model: str = ""  # the model the handoff-coordinator harness was made with
    handoff_budget_usd: float = 1.0  # hard stop for paid suggestions (all time)
    handoff_est_cost_per_run: float = 0.02  # used when the API reports no cost
    anthropic_api_key: str = Field(default="", repr=False)
    anthropic_model: str = "claude-opus-5-5"
    anthropic_effort: str = "medium"
    embeddings_provider: str = "fastembed"  # fastembed | hash (tests/CI)
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    match_min_score: float = 0.55
    ai_enrich_requests: bool = False

    # --- buy or rent nearby (C6): store/rental alternatives from Exa web search ---
    commercial_provider: str = "mock"  # mock | exa | off
    exa_api_key: str = Field(default="", repr=False)
    exa_base_url: str = "https://api.exa.ai"
    exa_search_type: str = "auto"  # auto | deep
    exa_timeout_s: int = 30
    commercial_cache_hours: int = 24
    commercial_daily_lookups_per_user: int = 25
    commercial_budget_usd: float = 9.0  # per calendar month (UTC)
    commercial_est_cost_usd: float = 0.017  # per uncached lookup when Exa reports no cost
    commercial_default_place: str = "Stanford, CA"
    commercial_default_label: str = "Stanford campus"  # shown as "Near Stanford campus"
    commercial_default_lat: float = 37.4275
    commercial_default_lng: float = -122.1697

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

    @property
    def harnessrouter_api_keys(self) -> list[str]:
        """Every HarnessRouter key, in order; tasks are load-balanced across them."""
        return csv_list(self.harnessrouter_api_key)

    @field_validator("*", mode="before")
    @classmethod
    def _comment_only_means_unset(cls, value: object) -> object:
        """`KEY=   # note` is empty to python-dotenv (`make api`), but Docker Compose's env_file
        (the server, `make up`) passes the text "# note". A value that is only a comment means
        "not set", so every setting gets its default the same way everywhere."""
        if isinstance(value, str) and value.lstrip().startswith("#"):
            raise PydanticUseDefault()
        return value

    @property
    def harnessrouter_vision_harness_ids(self) -> list[str]:
        return csv_list(self.harnessrouter_vision_harness_id)

    @property
    def harnessrouter_profile_harness_ids(self) -> list[str]:
        return csv_list(self.harnessrouter_profile_harness_id)

    @property
    def harnessrouter_condition_harness_ids(self) -> list[str]:
        return csv_list(self.harnessrouter_condition_harness_id)

    @property
    def harnessrouter_handoff_harness_ids(self) -> list[str]:
        return csv_list(self.harnessrouter_handoff_harness_id)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
