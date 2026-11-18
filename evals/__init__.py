"""DAHA evals (plans/EVALS.md). Run from the repo root:  uv run --project backend python -m evals.run all"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
