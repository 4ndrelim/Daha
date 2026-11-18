import pytest

from app.core.config import settings


def pytest_configure(config):
    config.addinivalue_line("markers", "slow: real fastembed on seed data (RUN_SLOW=1 to run)")


@pytest.fixture(autouse=True)
def _hash_match_threshold(monkeypatch):
    """Hash embeddings score ~0.25 lower than fastembed for true matches; scale the floor."""
    if settings.embeddings_provider == "hash":
        monkeypatch.setattr(settings, "match_min_score", 0.40)
