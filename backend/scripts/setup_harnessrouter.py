"""Create DAHA's vision harness on HarnessRouter and set HARNESSROUTER_VISION_HARNESS_ID.

    cd backend && uv run python scripts/setup_harnessrouter.py --check       # keys OK? which org?
    cd backend && uv run python scripts/setup_harnessrouter.py --list        # bases + models only
    cd backend && uv run python scripts/setup_harnessrouter.py --write-env   # create + save ids
    cd backend && uv run python scripts/setup_harnessrouter.py --profile --write-env
        # the same for the mutual-matching profile harness (HARNESSROUTER_PROFILE_HARNESS_ID)
    cd backend && uv run python scripts/setup_harnessrouter.py --condition --write-env
        # the same for the condition-check harness (HARNESSROUTER_CONDITION_HARNESS_ID)

Reads HARNESSROUTER_API_KEY (one key, or several comma-separated) / _BASE / _MODEL from
backend/.env. Each key gets its own harness, so keys from different workspaces work too; the ids
come out in key order. Costs nothing by itself (creating a harness is free; only tasks are
billed). Never prints a key: keys are referred to as "key 2/3".
"""

import argparse
import json
import re
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # `python scripts/x.py` finds `app`

from app.ai.condition import CONDITION_PROMPT_VERSION, CONDITION_SYSTEM  # noqa: E402
from app.ai.profile import PROFILE_PROMPT_VERSION, PROFILE_SYSTEM  # noqa: E402
from app.ai.prompts import PROMPT_VERSION, VISION_SYSTEM  # noqa: E402
from app.core.config import BACKEND_DIR, settings  # noqa: E402

ENV_FILE = BACKEND_DIR / ".env"
HARNESS_VAR = "HARNESSROUTER_VISION_HARNESS_ID"
PROFILE_VAR = "HARNESSROUTER_PROFILE_HARNESS_ID"
CONDITION_VAR = "HARNESSROUTER_CONDITION_HARNESS_ID"


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
    """GET /v1/me with every key (free): which organization and workspace each key acts in.

    Exits non-zero if any key fails. Keys in one organization share its balance and its
    concurrency limit, so the script points that out.
    """
    failed = 0
    orgs: dict[str, list[int]] = {}
    for n, key in enumerate(keys, 1):
        try:
            with client(key) as c:
                r = c.get("/v1/me")
            if r.status_code < 400:
                me = r.json() or {}
                org = str(me.get("org") or "?")
                orgs.setdefault(org, []).append(n)
                where = me.get("workspace_name") or me.get("workspace") or "?"
                status = f"OK · organization {me.get('org_name') or org} · workspace {where}"
            else:
                status = f"HTTP {r.status_code}"
        except httpx.HTTPError as exc:
            status = type(exc).__name__
        failed += not status.startswith("OK")
        print(f"key {n}/{len(keys)}: {status}")
    for numbers in (nums for nums in orgs.values() if len(nums) > 1):
        listed = ", ".join(map(str, numbers))
        print(
            f"note: keys {listed} are in the same organization, so they share one balance and one "
            "concurrency limit (HARNESSROUTER_MAX_CONCURRENCY counts all keys together)."
        )
    sys.exit(1 if failed else 0)


def create_harness(c: httpx.Client, profile: bool = False, condition: bool = False) -> str:
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
    if profile:  # mutual matching (docs/plans/mutual-matching.md): text in, JSON out, no tools
        body.update(
            name=f"daha-{PROFILE_PROMPT_VERSION}",
            system_prompt=PROFILE_SYSTEM,
            max_step=3,
            timeout_seconds=90,
            max_cost_usd=0.15,
            disabled_tools=["Write", "Edit", "Bash", "WebFetch", "WebSearch", "Read"],
        )
    if condition:  # condition check: 6 photos in, one JSON verdict out; a few cents per task
        body.update(
            name=f"daha-{CONDITION_PROMPT_VERSION}",
            system_prompt=CONDITION_SYSTEM,
            max_step=3,
            timeout_seconds=120,
            max_cost_usd=0.05,
            disabled_tools=["Write", "Edit", "Bash", "WebFetch", "WebSearch"],
        )
    r = c.post("/v1/harnesses", json={k: v for k, v in body.items() if v is not None})
    if r.status_code >= 400 and "disabled_tools" in r.text:
        body.pop("disabled_tools")  # base doesn't support it
        r = c.post("/v1/harnesses", json={k: v for k, v in body.items() if v is not None})
    r.raise_for_status()
    harness_id = (r.json() or {}).get("id")
    if not harness_id:
        sys.exit("HarnessRouter created the harness but returned no id")
    return harness_id


def write_env(value: str, var: str = HARNESS_VAR) -> None:
    """Set the harness id variable in backend/.env; every other line stays as it is."""
    lines = ENV_FILE.read_text().splitlines() if ENV_FILE.exists() else []
    line = f"{var}={value}"
    pattern = re.compile(rf"^\s*{var}\s*=")
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
    ap.add_argument("--write-env", action="store_true", help="save the harness ids to backend/.env")
    ap.add_argument(
        "--profile",
        action="store_true",
        help=f"create the mutual-matching profile harness ({PROFILE_VAR}), not the vision one",
    )
    ap.add_argument(
        "--condition",
        action="store_true",
        help=f"create the condition-check harness ({CONDITION_VAR}), not the vision one",
    )
    args = ap.parse_args()
    if args.profile and args.condition:
        sys.exit("Pick one: --profile or --condition")
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
            ids.append(create_harness(c, profile=args.profile, condition=args.condition))
        print(f"key {n}/{len(keys)}: harness {ids[-1]}")
    value = ",".join(ids)
    var = PROFILE_VAR if args.profile else CONDITION_VAR if args.condition else HARNESS_VAR
    if args.write_env:
        write_env(value, var)
        print(f"\nSaved {var} ({len(ids)} id(s)) to backend/.env. Restart `make api`.")
    else:
        print("\nAdd this to backend/.env (or run again with --write-env):\n")
        print(f"{var}={value}")


if __name__ == "__main__":
    main()
