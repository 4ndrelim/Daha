"""Create DAHA's vision harness on HarnessRouter and print HARNESSROUTER_VISION_HARNESS_ID.

    cd backend && uv run python scripts/setup_harnessrouter.py            # create
    cd backend && uv run python scripts/setup_harnessrouter.py --list     # bases + models only

Reads HARNESSROUTER_API_KEY / _BASE / _MODEL from backend/.env. Costs nothing by itself
(creating a harness is free; only tasks are billed). Never prints the key.
"""

import argparse
import json
import sys

import httpx

from app.ai.prompts import PROMPT_VERSION, VISION_SYSTEM
from app.core.config import settings


def client() -> httpx.Client:
    if not settings.harnessrouter_api_key:
        sys.exit("HARNESSROUTER_API_KEY is empty in backend/.env")
    return httpx.Client(
        base_url=settings.harnessrouter_base_url.rstrip("/"),
        headers={"Authorization": f"Bearer {settings.harnessrouter_api_key}"},
        timeout=30,
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true", help="only print bases and models")
    args = ap.parse_args()
    with client() as c:
        bases = c.get("/v1/bases").raise_for_status().json()
        models = c.get("/v1/models").raise_for_status().json()
        print("bases:", json.dumps(bases, indent=2)[:4000])
        print("models:", json.dumps(models, indent=2)[:4000])
        if args.list:
            return
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
        harness = r.json()
        print("\nAdd this to backend/.env:\n")
        print(f"HARNESSROUTER_VISION_HARNESS_ID={harness.get('id')}")


if __name__ == "__main__":
    main()
