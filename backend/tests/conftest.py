import os
import sys
import tempfile
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

# isolated database, no network: these must be set before app modules are imported
os.environ["ASKWHY_DB"] = str(Path(tempfile.mkdtemp(prefix="askwhy-test-")) / "test.db")
for var in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ASKWHY_AI"):
    os.environ.pop(var, None)

import pytest  # noqa: E402

FILES = BACKEND / "app" / "sample" / "files"
SAMPLE = [
    ("S1", "meridian_project_brief.md"),
    ("S2", "onboarding_workflow.txt"),
    ("S3", "engineering_delivery_plan.pdf"),
    ("S4", "pilot_accounts.csv"),
    ("S5", "finance_budget.xlsx"),
]


@pytest.fixture(scope="session")
def corpus():
    from app.parsing import parse_file

    sources, units = [], []
    for sid, name in SAMPLE:
        src, us = parse_file((FILES / name).read_bytes(), name, sid, synthetic=True)
        sources.append(src)
        units.extend(us)
    return sources, units
