"""Create DAHA's vision harness on HarnessRouter and set HARNESSROUTER_VISION_HARNESS_ID.

    cd backend && uv run python scripts/setup_harnessrouter.py --check       # every key valid?
    cd backend && uv run python scripts/setup_harnessrouter.py --list        # bases + models only
    cd backend && uv run python scripts/setup_harnessrouter.py --write-env   # create + save ids

Reads HARNESSROUTER_API_KEY (one key, or several comma-separated) / _BASE / _MODEL from
backend/.env. Each key gets its own harness, so keys from different workspaces work too; the ids
come out in key order. Costs nothing by itself (creating a harness is free; only tasks are
billed). Never prints a key: keys are referred to as "key 2/3".
"""

import argparse
import json
import re
import sys

import httpx

from app.ai.prompts import PROMPT_VERSION, VISION_SYSTEM
from app.core.config import BACKEND_DIR, settings

ENV_FILE = BACKEND_DIR / ".env"
HARNESS_VAR = "HARNESSROUTER_VISION_HARNESS_ID"


def api_keys() -> list[str]:
    keys = settings.harnessrouter_api_keys
    if not keys:
        sys.exit("HARNESSROUTER_API_KEY is empty in backend/.env (one key, or several: a,b,c)")
    return keys


def client(key: str) -> httpx.Client:
    return httpx.Client(
        base_url=settings.harnessrouter_base_url.rstrip("/"),
        headers={"Authorization": f"Bearer {key}"},
        timeout=30,
    )


def check(keys: list[str]) -> None:
    """GET /v1/models with every key (free). Exits non-zero if any key fails."""
    failed = 0
    for n, key in enumerate(keys, 1):
        try:
            with client(key) as c:
                code = c.get("/v1/models").status_code
            status = "OK" if code < 400 else f"HTTP {code}"
        except httpx.HTTPError as exc:
            status = type(exc).__name__
        failed += status != "OK"
        print(f"key {n}/{len(keys)}: {status}")
    sys.exit(1 if failed else 0)


def create_harness(c: httpx.Client) -> str:
    body = {
        "name": f"daha-vision-{PROMPT_VERSION}",
        "base": settings.harnessrouter_base,
        "default_model": settings.harnessrouter_model or None,
        "system_prompt": VISION_SYSTEM,
        "mcp_servers": [],
        "skills": [],
        "max_step": 6,
        "timeout_seconds": settings.harnessrouter_timeout_s,
        "max_cost_usd": 0.5,  # per-turn cap; the default is $10
        "disabled_tools": ["Write", "Edit", "Bash", "WebFetch", "WebSearch"],
    }
    r = c.post("/v1/harnesses", json={k: v for k, v in body.items() if v is not None})
    if r.status_code >= 400 and "disabled_tools" in r.text:
        body.pop("disabled_tools")  # base doesn't support it
        r = c.post("/v1/harnesses", json={k: v for k, v in body.items() if v is not None})
    r.raise_for_status()
    harness_id = (r.json() or {}).get("id")
    if not harness_id:
        sys.exit("HarnessRouter created the harness but returned no id")
    return harness_id


def write_env(value: str) -> None:
    """Set HARNESSROUTER_VISION_HARNESS_ID in backend/.env; every other line stays as it is."""
    lines = ENV_FILE.read_text().splitlines() if ENV_FILE.exists() else []
    line = f"{HARNESS_VAR}={value}"
    pattern = re.compile(rf"^\s*{HARNESS_VAR}\s*=")
    for i, existing in enumerate(lines):
        if pattern.match(existing):
            lines[i] = line
            break
    else:
        lines.append(line)
    ENV_FILE.write_text("\n".join(lines) + "\n")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true", help="only check that every key works")
    ap.add_argument("--list", action="store_true", help="only print bases and models")
    ap.add_argument("--write-env", action="store_true", help=f"save {HARNESS_VAR} to backend/.env")
    args = ap.parse_args()
    keys = api_keys()
    if args.check:
        check(keys)
    with client(keys[0]) as c:
        bases = c.get("/v1/bases").raise_for_status().json()
        models = c.get("/v1/models").raise_for_status().json()
    print("bases:", json.dumps(bases, indent=2)[:4000])
    print("models:", json.dumps(models, indent=2)[:4000])
    if args.list:
        return
    ids: list[str] = []
    for n, key in enumerate(keys, 1):
        with client(key) as c:
            ids.append(create_harness(c))
        print(f"key {n}/{len(keys)}: harness {ids[-1]}")
    value = ",".join(ids)
    if args.write_env:
        write_env(value)
        print(f"\nSaved {HARNESS_VAR} ({len(ids)} id(s)) to backend/.env. Restart `make api`.")
    else:
        print("\nAdd this to backend/.env (or run again with --write-env):\n")
        print(f"{HARNESS_VAR}={value}")


if __name__ == "__main__":
    main()
