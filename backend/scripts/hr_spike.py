"""C0 spike: run the vision prompt on a few photos and print a latency / validity / cost table.

    cd backend && uv run python scripts/hr_spike.py ~/daha-spike/photos/*.jpg

PAID: each photo is one HarnessRouter task (~$0.02–0.20). Uses the harness(es) in
HARNESSROUTER_VISION_HARNESS_ID (scripts/setup_harnessrouter.py --write-env); with several
keys in HARNESSROUTER_API_KEY, photos are spread across them (raw output records which key).
Raw outputs go to ~/daha-spike/out/. Only use photos with no people or personal info.
"""

import asyncio
import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # `python scripts/x.py` finds `app`

from app.ai.providers import ProviderError  # noqa: E402
from app.ai.providers.harnessrouter import HarnessRouterVisionProvider  # noqa: E402
from app.ai.vision import downscale  # noqa: E402
from app.core.config import settings  # noqa: E402

OUT = Path.home() / "daha-spike" / "out"


async def main(paths: list[str]) -> None:
    if not paths:
        sys.exit(__doc__)
    OUT.mkdir(parents=True, exist_ok=True)
    provider = HarnessRouterVisionProvider()
    rows = []
    for p in paths:
        data = downscale(Path(p).read_bytes())
        try:
            res = await provider.detect(data, Path(p).name)
            rows.append((Path(p).name, res.latency_ms / 1000, True, len(res.items), res.cost_usd))
            (OUT / f"{Path(p).stem}.json").write_text(
                json.dumps({"items": [i.model_dump() for i in res.items], "raw": res.raw}, indent=2)
            )
        except ProviderError as exc:
            rows.append((Path(p).name, None, False, 0, None))
            print(f"{p}: FAILED {exc}")
    lat = [r[1] for r in rows if r[1] is not None]
    cost = [r[4] for r in rows if r[4] is not None]
    model = settings.harnessrouter_model or "(default)"
    keys = len(settings.harnessrouter_api_keys)
    print(f"\nconfig: {settings.harnessrouter_base}/{model} · {keys} key(s), load-balanced")
    for r in rows:
        print(f"  {r[0]:30} {r[1] or 0:6.1f}s  valid={r[2]}  items={r[3]}  ${r[4] or 0:.3f}")
    if lat:
        valid = sum(r[2] for r in rows)
        avg = statistics.mean(cost or [0])
        print(f"p50 {statistics.median(lat):.1f}s · max {max(lat):.1f}s · ", end="")
        print(f"valid {valid}/{len(rows)} · ~${avg:.3f}/photo")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:]))
