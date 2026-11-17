"""Test setup: a separate database (TEST_DATABASE_URL), no paid AI, hash embeddings.

The env vars must be set before anything imports app.core.config.
"""

import os
from pathlib import Path

from dotenv import dotenv_values

_TEST_DB_URL = (
    os.environ.get("TEST_DATABASE_URL")
    or dotenv_values(Path(__file__).resolve().parents[1] / ".env").get("TEST_DATABASE_URL")
    or "postgresql+psycopg://daha:daha@localhost:5432/daha_test"
)
# lock_timeout: a test that forgets to release a transaction fails in 10 s instead of hanging.
_TEST_DB_URL += ("&" if "?" in _TEST_DB_URL else "?") + "options=-c%20lock_timeout%3D10000"
os.environ["DATABASE_URL"] = _TEST_DB_URL
os.environ["AI_PROVIDER"] = "mock"
os.environ["EMBEDDINGS_PROVIDER"] = "hash"
os.environ["AI_MOCK_LATENCY_MS"] = "0"
os.environ["DEMO_MODE"] = "true"
os.environ["ALLOWED_EMAIL_DOMAINS"] = "stanford.edu"
os.environ["JWT_SECRET"] = "test-secret-test-secret-test-secret-test"

import pytest  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from alembic import command  # noqa: E402
from app.core import security  # noqa: E402
from app.core.config import BACKEND_DIR, settings  # noqa: E402
from app.core.db import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base  # noqa: E402

security.BCRYPT_ROUNDS = 4
assert settings.database_url == _TEST_DB_URL, "tests must use the test database"


@pytest.fixture(scope="session", autouse=True)
def _schema(tmp_path_factory):
    """Rebuild the test database from the real migrations once per run."""
    settings.upload_dir = str(tmp_path_factory.mktemp("uploads"))
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.attributes["configure_logging"] = False
    command.upgrade(cfg, "head")
    yield
    engine.dispose()


@pytest.fixture(autouse=True)
def _clean_tables(_schema):
    yield
    tables = ", ".join(f'"{t.name}"' for t in Base.metadata.sorted_tables)
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))


@pytest.fixture
def db():
    with SessionLocal() as session:
        yield session


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c
