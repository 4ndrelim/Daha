"""Settings: a value that is only a comment means "not set".

`KEY=   # note` in backend/.env is empty to python-dotenv (`make api`), but Docker Compose's
env_file (the server, `make up`) passes the text "# note". Both must give the default.
"""

from app.core.config import Settings


def test_docker_style_comment_values_fall_back_to_defaults(monkeypatch):
    # Exactly what the live api container received before the fix.
    monkeypatch.setenv("HARNESSROUTER_MODEL", "# model id chosen in the C0 spike")
    monkeypatch.setenv(
        "HARNESSROUTER_PROFILE_HARNESS_ID",
        "# set by setup_harnessrouter.py --profile --write-env: one id per key, same order",
    )
    monkeypatch.setenv("HARNESSROUTER_CONDITION_HARNESS_ID", "# one id per key, same order")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "# optional fallback provider")
    monkeypatch.setenv("HARNESSROUTER_BASE_URL", "  # where the API lives")
    monkeypatch.setenv("HARNESSROUTER_MAX_CONCURRENCY", "# tasks at once")
    s = Settings(_env_file=None)
    assert s.harnessrouter_model == ""
    assert s.harnessrouter_profile_harness_ids == []
    assert s.harnessrouter_condition_harness_ids == []
    assert s.anthropic_api_key == ""
    assert s.harnessrouter_base_url == "https://api.harnessrouter.ai"
    assert s.harnessrouter_max_concurrency == 2


def test_env_file_read_locally_agrees(tmp_path, monkeypatch):
    for name in ("HARNESSROUTER_MODEL", "HARNESSROUTER_PROFILE_HARNESS_ID", "ANTHROPIC_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    env = tmp_path / ".env"
    env.write_text(
        "HARNESSROUTER_MODEL=                 # model id\n"
        "HARNESSROUTER_PROFILE_HARNESS_ID=    # one id per key, same order\n"
        "ANTHROPIC_API_KEY=                   # optional fallback provider\n"
    )
    s = Settings(_env_file=env)
    assert s.harnessrouter_model == ""
    assert s.harnessrouter_profile_harness_ids == []
    assert s.anthropic_api_key == ""


def test_real_values_are_kept(monkeypatch):
    monkeypatch.setenv("HARNESSROUTER_PROFILE_HARNESS_ID", "h1, h2")
    monkeypatch.setenv("HARNESSROUTER_MAX_CONCURRENCY", "4")
    monkeypatch.setenv("COMMERCIAL_DEFAULT_LABEL", "Stanford campus")
    monkeypatch.setenv("JWT_SECRET", "abc#def")  # a '#' inside a value is fine
    s = Settings(_env_file=None)
    assert s.harnessrouter_profile_harness_ids == ["h1", "h2"]
    assert s.harnessrouter_max_concurrency == 4
    assert s.commercial_default_label == "Stanford campus"
    assert s.jwt_secret == "abc#def"
