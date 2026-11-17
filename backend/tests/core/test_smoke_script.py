"""Keeps scripts/smoke_api.py honest: run it in-process against the test database."""

import importlib.util

from fastapi.testclient import TestClient

from app.core.config import BACKEND_DIR
from app.main import app
from app.seed.seed import run


def test_smoke_script_passes(monkeypatch, capsys):
    run(do_reset=True)
    spec = importlib.util.spec_from_file_location("smoke_api", BACKEND_DIR / "scripts/smoke_api.py")
    smoke = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(smoke)
    monkeypatch.setattr(smoke.httpx, "Client", lambda **kw: TestClient(app))
    exit_code = smoke.main()
    out = capsys.readouterr().out
    assert exit_code == 0, out
    assert out.count("✅") == 7 and "❌" not in out
