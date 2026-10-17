"""Write the deterministic sample investigation to the frontend bundle (offline fallback).

Run from backend/:  .venv/bin/python scripts/export_sample.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.sample.build import build_sample_investigation  # noqa: E402

OUT = Path(__file__).resolve().parents[2] / "frontend" / "src" / "data" / "sample-investigation.json"

if __name__ == "__main__":
    inv = build_sample_investigation()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(inv.model_dump_json(indent=None))
    print(f"wrote {OUT} ({OUT.stat().st_size // 1024} KB)")
