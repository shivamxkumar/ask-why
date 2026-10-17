import time

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas import Investigation, InvestigationSummary
from conftest import FILES, SAMPLE

client = TestClient(app)


def _wait(inv_id, timeout=60):
    end = time.time() + timeout
    while time.time() < end:
        r = client.get(f"/api/investigations/{inv_id}")
        assert r.status_code == 200
        body = r.json()
        if body["status"] != "analyzing":
            return body
        time.sleep(0.2)
    raise AssertionError("pipeline did not finish")


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True and body["ai_available"] is False and body["model"] is None
    assert ".pdf" in body["supported_extensions"] and body["max_file_mb"] == 15


@pytest.fixture(scope="module")
def ready_investigation():
    files = [("files", (name, (FILES / name).read_bytes())) for _, name in SAMPLE]
    r = client.post("/api/investigations", files=files, data={"use_ai": "false"})
    assert r.status_code == 202, r.text
    inv = Investigation.model_validate(r.json())
    assert inv.status == "analyzing" and len(inv.pipeline) == 10
    body = _wait(inv.id)
    assert body["status"] == "ready", body.get("error")
    return Investigation.model_validate(body)


def test_upload_pipeline(ready_investigation):
    inv = ready_investigation
    assert inv.mode == "heuristic" and [s.id for s in inv.sources] == ["S1", "S2", "S3", "S4", "S5"]
    assert all(s.status == "done" for s in inv.pipeline), [(s.step, s.status, s.detail) for s in inv.pipeline]
    assert all(s.ms is not None for s in inv.pipeline)
    assert len(inv.findings) >= 10 and inv.graph.nodes and inv.limitations
    prios = [f.priority for f in inv.findings]
    assert prios == sorted(prios, reverse=True) and prios[0] > 0
    assert inv.name.startswith("Meridian project brief")
    summaries = client.get("/api/investigations").json()
    assert any(InvestigationSummary.model_validate(s).id == inv.id for s in summaries)


def test_patch_and_rescore(ready_investigation):
    inv = ready_investigation
    fid = inv.findings[-1].id
    r = client.patch(f"/api/investigations/{inv.id}/findings/{fid}", json={"status": "validated", "reviewer_note": "checked", "impact_override": 99})
    assert r.status_code == 200
    upd = Investigation.model_validate(r.json())
    f = next(x for x in upd.findings if x.id == fid)
    assert f.status == "validated" and f.reviewer_note == "checked" and f.impact == 99
    r = client.put(f"/api/investigations/{inv.id}/scoring", json={"w_impact": 0.2, "w_confidence": 0.8})
    assert r.status_code == 200 and r.json()["scoring"]["w_impact"] == 0.2
    assert client.patch(f"/api/investigations/{inv.id}/findings/NOPE", json={"status": "open"}).status_code == 404


def test_report(ready_investigation):
    r = client.get(f"/api/investigations/{ready_investigation.id}/report.md")
    assert r.status_code == 200
    md = r.text
    for section in ("## Executive overview", "## Top findings", "## Contradictions", "## Assumptions & constraints",
                    "## Open questions", "## Next actions", "## Limitations", "Human review required"):
        assert section in md


def test_rejections():
    r = client.post("/api/investigations", files=[("files", ("evil.exe", b"MZ..."))])
    assert r.status_code == 415 and "evil.exe" in r.json()["detail"]
    assert client.post("/api/investigations", data={"name": "x"}).status_code in (400, 422)
    big = b"a" * (15 * 1024 * 1024 + 10)
    assert client.post("/api/investigations", files=[("files", ("big.txt", big))]).status_code == 413
    assert client.get("/api/investigations/doesnotexist").status_code == 404


def test_delete():
    r = client.post("/api/investigations", files=[("files", ("n.md", b"# Plan\n\nWe expect 20% growth by March 2027.\n"))], data={"use_ai": "false"})
    inv_id = r.json()["id"]
    _wait(inv_id)
    assert client.delete(f"/api/investigations/{inv_id}").status_code == 200
    assert client.get(f"/api/investigations/{inv_id}").status_code == 404


def test_sample_endpoints():
    r = client.get("/api/sample")
    assert r.status_code == 200
    Investigation.model_validate(r.json())
    files = client.get("/api/sample/files").json()
    assert {f["name"] for f in files} >= {name for _, name in SAMPLE}
    r = client.get("/api/sample/files/pilot_accounts.csv")
    assert r.status_code == 200 and r.content.startswith(b"account_id")
    assert client.get("/api/sample/files/..%2Fbuild.py").status_code == 404
    assert client.post("/api/sample/reset").status_code == 200
