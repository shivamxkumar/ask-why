"""ASK//WHY API."""
from __future__ import annotations

import logging
import threading
import uuid
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse, JSONResponse

from app import db
from app.analysis import ai
from app.parsing import MAX_FILE_BYTES, MAX_FILE_MB, SUPPORTED_EXTENSIONS, ParseError, UnsupportedFileError, check_upload
from app.pipeline import DEFAULT_QUESTION, default_name, now_iso, pending_steps, run_pipeline
from app.report import build_report
from app.schemas import FindingPatch, Investigation, InvestigationSummary, ScoringConfig

log = logging.getLogger("askwhy")
MAX_FILES = 12

app = FastAPI(title="ASK//WHY — The Unasked Question Engine", version="1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:5174", "http://127.0.0.1:5174"],
    allow_methods=["*"], allow_headers=["*"],
)
_locks: dict[str, threading.Lock] = {}
_locks_guard = threading.Lock()


def _lock(inv_id: str) -> threading.Lock:
    with _locks_guard:
        return _locks.setdefault(inv_id, threading.Lock())


def _get_or_404(inv_id: str) -> Investigation:
    inv = db.get(inv_id)
    if inv is None:
        raise HTTPException(404, f"Investigation '{inv_id}' not found.")
    return inv


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "ai_available": ai.ai_available(), "model": ai.ai_model(),
            "supported_extensions": SUPPORTED_EXTENSIONS, "max_file_mb": MAX_FILE_MB}


def _run_background(inv_id: str, name: Optional[str], question: Optional[str], payload: list[tuple[str, bytes]], use_ai: bool) -> None:
    def progress(steps):
        with _lock(inv_id):
            cur = db.get(inv_id)
            if cur is None or cur.status != "analyzing":
                return
            cur.pipeline = steps
            cur.updated_at = now_iso()
            db.save(cur)

    try:
        result = run_pipeline(inv_id, name, question, payload, use_ai, progress)
        with _lock(inv_id):
            cur = db.get(inv_id)
            if cur is None:
                return  # deleted while analysing
            result.created_at = cur.created_at
            result.updated_at = now_iso()
            db.save(result)
    except Exception as exc:  # report, never crash the worker
        log.exception("pipeline failed for %s", inv_id)
        with _lock(inv_id):
            cur = db.get(inv_id)
            if cur is None:
                return
            cur.status = "error"
            cur.error = str(exc) if isinstance(exc, (ParseError, UnsupportedFileError)) else f"Analysis failed: {type(exc).__name__}: {exc}"
            for s in cur.pipeline:
                if s.status == "running":
                    s.status = "error"
                    s.detail = cur.error
                elif s.status == "pending":
                    s.status = "skipped"
            cur.updated_at = now_iso()
            db.save(cur)


@app.post("/api/investigations", status_code=202, response_model=Investigation)
async def create_investigation(
    files: list[UploadFile] = File(default=[]),
    name: Optional[str] = Form(default=None),
    question: Optional[str] = Form(default=None),
    use_ai: Optional[str] = Form(default=None),
) -> Investigation:
    files = [f for f in files if f is not None and (f.filename or "")]
    if not files:
        raise HTTPException(400, "No files uploaded. Attach 1–12 files in the 'files' field.")
    if len(files) > MAX_FILES:
        raise HTTPException(400, f"Too many files ({len(files)}). Upload at most {MAX_FILES} at a time.")
    payload: list[tuple[str, bytes]] = []
    for f in files:
        fname = f.filename or "upload"
        try:
            check_upload(fname, 1)  # extension check first, before reading the body
        except UnsupportedFileError as exc:
            raise HTTPException(415, str(exc))
        data = await f.read(MAX_FILE_BYTES + 1)
        if len(data) > MAX_FILE_BYTES:
            raise HTTPException(413, f"{fname}: exceeds the {MAX_FILE_MB} MB per-file limit.")
        if not data:
            raise HTTPException(400, f"{fname}: the file is empty.")
        payload.append((fname, data))
    flag = (use_ai or "").strip().lower()
    want_ai = ai.ai_available() if flag == "" else flag in ("1", "true", "yes", "on")
    inv_id = uuid.uuid4().hex[:12]
    ts = now_iso()
    inv = Investigation(
        id=inv_id, name=(name or "").strip() or default_name([n for n, _ in payload]),
        question=(question or "").strip() or DEFAULT_QUESTION,
        mode="ai" if want_ai and ai.ai_available() else "heuristic", status="analyzing",
        created_at=ts, updated_at=ts, pipeline=pending_steps(),
    )
    db.save(inv)
    threading.Thread(target=_run_background, args=(inv_id, name, question, payload, want_ai), daemon=True).start()
    return inv


@app.get("/api/investigations", response_model=list[InvestigationSummary])
def list_investigations() -> list[InvestigationSummary]:
    return db.list_summaries()


@app.get("/api/investigations/{inv_id}", response_model=Investigation)
def get_investigation(inv_id: str) -> Investigation:
    return _get_or_404(inv_id)


def _rescore(inv: Investigation) -> None:
    from app.analysis.scoring import score_all

    inv.findings = score_all(inv.findings, inv.scoring)


@app.patch("/api/investigations/{inv_id}/findings/{finding_id}", response_model=Investigation)
def patch_finding(inv_id: str, finding_id: str, patch: FindingPatch) -> Investigation:
    with _lock(inv_id):
        inv = _get_or_404(inv_id)
        f = next((x for x in inv.findings if x.id == finding_id), None)
        if f is None:
            raise HTTPException(404, f"Finding '{finding_id}' not found.")
        if patch.status is not None:
            f.status = patch.status
        if patch.reviewer_note is not None:
            f.reviewer_note = patch.reviewer_note.strip() or None
        if patch.impact_override is not None:
            from app.analysis.scoring import set_impact_override

            set_impact_override(f, patch.impact_override)
            _rescore(inv)
        inv.updated_at = now_iso()
        db.save(inv)
        return inv


@app.put("/api/investigations/{inv_id}/scoring", response_model=Investigation)
def put_scoring(inv_id: str, cfg: ScoringConfig) -> Investigation:
    with _lock(inv_id):
        inv = _get_or_404(inv_id)
        inv.scoring = cfg
        _rescore(inv)
        inv.updated_at = now_iso()
        db.save(inv)
        return inv


@app.delete("/api/investigations/{inv_id}")
def delete_investigation(inv_id: str) -> dict:
    if not db.delete(inv_id):
        raise HTTPException(404, f"Investigation '{inv_id}' not found.")
    return {"ok": True}


@app.get("/api/investigations/{inv_id}/report.md", response_class=PlainTextResponse)
def report_md(inv_id: str) -> PlainTextResponse:
    inv = _get_or_404(inv_id)
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in inv.name)[:60] or "report"
    return PlainTextResponse(build_report(inv), media_type="text/markdown; charset=utf-8",
                             headers={"Content-Disposition": f'inline; filename="askwhy-{safe}.md"'})


# ---------------------------------------------------------------- sample
@app.get("/api/sample", response_model=Investigation)
def get_sample() -> Investigation:
    from app.sample.build import get_or_create_sample

    return get_or_create_sample()


@app.post("/api/sample/reset", response_model=Investigation)
def reset_sample() -> Investigation:
    from app.sample.build import get_or_create_sample

    return get_or_create_sample(reset=True)


@app.get("/api/sample/files")
def list_sample_files() -> list[dict]:
    from app.sample.build import sample_files

    return sample_files()


@app.get("/api/sample/files/{name}")
def download_sample_file(name: str):
    from app.sample.build import FILES_DIR

    allowed = {p.name: p for p in FILES_DIR.iterdir() if p.is_file()}
    if name not in allowed:
        raise HTTPException(404, "Sample file not found.")
    return FileResponse(allowed[name], filename=name)


@app.exception_handler(Exception)
async def _unhandled(_, exc: Exception):  # pragma: no cover - last resort, keeps JSON errors
    log.exception("unhandled error")
    return JSONResponse(status_code=500, content={"detail": f"Internal error: {type(exc).__name__}"})
