"""The 10-step investigation pipeline. Each step records real counts and elapsed time."""
from __future__ import annotations

import re
import time
from datetime import datetime, timezone
from typing import Callable, Optional

from app.analysis import ai
from app.analysis.heuristics import Heuristics
from app.parsing import ParseError, UnsupportedFileError, check_upload, parse_file
from app.schemas import EvidenceUnit, Finding, Investigation, PipelineStep, Scenario, ScoringConfig, Source

STEP_NAMES = [
    "Validate uploads",
    "Extract text & tables",
    "Create evidence units",
    "Identify claims & assumptions",
    "Compare claims across sources",
    "Find gaps & failure scenarios",
    "Generate findings",
    "Validate citations",
    "Score & rank",
    "Build evidence map",
]
DEFAULT_QUESTION = "What must be true for this plan to succeed — and what haven't we asked?"
ProgressCb = Callable[[list[PipelineStep]], None]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def pending_steps() -> list[PipelineStep]:
    return [PipelineStep(step=s, status="pending") for s in STEP_NAMES]


def default_name(filenames: list[str]) -> str:
    if not filenames:
        return "Untitled investigation"
    stem = re.sub(r"\.[A-Za-z0-9]+$", "", filenames[0])
    stem = re.sub(r"[_\-]+", " ", stem).strip() or filenames[0]
    stem = stem[:1].upper() + stem[1:]
    return stem + (f" + {len(filenames) - 1} more" if len(filenames) > 1 else "")


class _Steps:
    def __init__(self, cb: Optional[ProgressCb]):
        self.steps = pending_steps()
        self.cb = cb
        self._t = 0.0

    def start(self, i: int) -> None:
        self.steps[i].status = "running"
        self._t = time.perf_counter()
        self._emit()

    def done(self, i: int, count: Optional[int], detail: str, status: str = "done") -> None:
        s = self.steps[i]
        s.status = status  # type: ignore[assignment]
        s.count = count
        s.detail = detail
        s.ms = int((time.perf_counter() - self._t) * 1000)
        self._emit()

    def _emit(self) -> None:
        if self.cb:
            try:
                self.cb([s.model_copy() for s in self.steps])
            except Exception:
                pass


def _title_tokens(t: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9$%]{3,}", t.lower())}


def _cited_units(f: Finding) -> set[str]:
    ids = {c.unit_id for c in f.citations if c.unit_id}
    if f.contradiction:
        ids |= {x for x in (f.contradiction.claim_a.citation.unit_id, f.contradiction.claim_b.citation.unit_id) if x}
    return ids


def merge_findings(heuristic: list[Finding], ai_findings: list[Finding], scenarios: list[Scenario]) -> list[Finding]:
    """AI findings replace heuristic ones that cite overlapping units and have a similar title or same category.
    The AI wording wins; heuristic calculations, extra citations and links are kept."""
    remaining = list(heuristic)
    idmap: dict[str, str] = {}
    for af in ai_findings:
        a_units, a_tok = _cited_units(af), _title_tokens(af.title)
        best, best_score = None, 0.0
        for hf in remaining:
            overlap = a_units & _cited_units(hf)
            if not overlap:
                continue
            h_tok = _title_tokens(hf.title)
            jac = len(a_tok & h_tok) / max(1, len(a_tok | h_tok))
            same_cat = af.category == hf.category
            score = jac + (0.3 if same_cat else 0) + 0.1 * len(overlap)
            if (jac >= 0.25 or same_cat) and score > best_score:
                best, best_score = hf, score
        if best is None:
            continue
        remaining.remove(best)
        idmap[best.id] = af.id
        af.calculations = best.calculations + af.calculations
        seen = {(c.unit_id, c.excerpt) for c in af.citations}
        for c in best.citations:
            if (c.unit_id, c.excerpt) not in seen and len(af.citations) < 6:
                af.citations.append(c)
        if af.contradiction is None and best.contradiction is not None:
            af.contradiction = best.contradiction
        if af.inference_note is None:
            af.inference_note = best.inference_note
        af.related = sorted(set(af.related) | set(best.related))
        af.depends_on = sorted(set(af.depends_on) | set(best.depends_on))
    merged = ai_findings + remaining
    valid = {f.id for f in merged}
    for f in merged:
        f.related = sorted({idmap.get(r, r) for r in f.related if idmap.get(r, r) in valid and idmap.get(r, r) != f.id})
        f.depends_on = sorted({idmap.get(r, r) for r in f.depends_on if idmap.get(r, r) in valid and idmap.get(r, r) != f.id})
    for s in scenarios:
        s.finding_ids = [idmap.get(x, x) for x in s.finding_ids]
    return merged


def run_pipeline(inv_id: str, name: Optional[str], question: Optional[str], files: list[tuple[str, bytes]], use_ai: bool,
                 progress_cb: Optional[ProgressCb] = None, scoring: Optional[ScoringConfig] = None) -> Investigation:
    from app.analysis.graph import build_graph
    from app.analysis.scoring import score_all
    from app.analysis.validation import validate_investigation

    st = _Steps(progress_cb)
    created = now_iso()
    cfg = scoring or ScoringConfig()
    filenames = [f for f, _ in files]
    limitations: list[str] = []

    # 1. validate
    st.start(0)
    for fname, data in files:
        check_upload(fname, len(data))  # raises with a user-facing message
    total_mb = sum(len(d) for _, d in files) / 1024 / 1024
    st.done(0, len(files), f"{len(files)} file{'s' if len(files) != 1 else ''} · {total_mb:.2f} MB · types OK")

    # 2. extract
    st.start(1)
    sources: list[Source] = []
    units: list[EvidenceUnit] = []
    failed: list[str] = []
    for i, (fname, data) in enumerate(files, start=1):
        try:
            src, us = parse_file(data, fname, f"S{i}")
        except (ParseError, UnsupportedFileError) as exc:
            failed.append(str(exc))
            continue
        sources.append(src)
        units.extend(us)
    if not sources:
        raise ParseError("None of the files could be read: " + " ".join(failed))
    pages = sum(s.page_count or 0 for s in sources)
    rows = sum(s.row_count or 0 for s in sources)
    detail = f"{len(sources)} parsed" + (f" · {pages} PDF pages" if pages else "") + (f" · {rows} table rows" if rows else "")
    if failed:
        detail += f" · {len(failed)} failed: " + " ".join(failed)
        limitations.append("Some files could not be read and were excluded: " + " ".join(failed))
    warnings = [f"{s.name}: {w}" for s in sources for w in s.warnings]
    if warnings:
        detail += " · warnings: " + "; ".join(warnings[:3])
    st.done(1, len(sources), detail, status="error" if failed and not sources else "done")

    # 3. units
    st.start(2)
    by_kind: dict[str, int] = {}
    for u in units:
        by_kind[u.kind] = by_kind.get(u.kind, 0) + 1
    st.done(2, len(units), " · ".join(f"{v} {k.replace('_', ' ')}s" for k, v in sorted(by_kind.items())))

    # 4–6. deterministic analysis
    h = Heuristics(sources, units)
    st.start(3)
    n_claims = h.stage_claims()
    n_assump = sum(1 for g, _ in h.drafts if g == "assumption")
    st.done(3, n_claims, f"{n_claims} claim-bearing sentences/rows · {n_assump} unevidenced assumptions flagged")
    st.start(4)
    n_conf = h.stage_compare()
    st.done(4, n_conf, f"{n_conf} contradictions or scope conflicts across {len(sources)} sources")
    st.start(5)
    n_gaps = h.stage_gaps()
    st.done(5, n_gaps, f"{n_gaps} dependency / coverage gaps · {len(h.scenarios)} what-if scenarios")

    # 7. findings (+ optional AI)
    st.start(6)
    findings, scenarios = h.stage_findings()
    detail = f"{len(findings)} heuristic findings"
    status = "done"
    mode = "heuristic"
    model = None
    if use_ai and ai.ai_available():
        log: list[tuple[str, str, str]] = []

        def log_cb(step: str, s: str, d: str) -> None:
            log.append((step, s, d))

        ai_findings = ai.run_ai_analysis(sources, units, findings, log_cb)
        errors = [d for _, s, d in log if s == "error"]
        if ai_findings:
            mode, model = "ai", ai.ai_model()
            before = len(findings)
            findings = merge_findings(findings, ai_findings, scenarios)
            detail = f"{len(ai_findings)} AI findings ({model}) merged with {before} heuristic → {len(findings)}"
        if errors:
            status = "error"
            detail += " · AI: " + " ".join(errors)
            limitations.append("The AI step failed for this run, so findings are heuristic only: " + " ".join(errors))
        skipped = [d for _, s, d in log if s == "skipped"]
        if skipped:
            detail += " · " + " ".join(skipped)
    elif use_ai:
        detail += " · AI not configured (heuristic mode)"
    st.done(6, len(findings), detail, status=status)

    # 8. validate citations
    st.start(7)
    verified, unverified = validate_investigation(findings, scenarios, units)
    st.done(7, verified, f"{verified} verified · {unverified} unverified")
    if unverified:
        limitations.append(f"{unverified} citation(s) could not be matched to the extracted text and are marked unverified.")

    # 9. score
    st.start(8)
    findings = score_all(findings, cfg)
    st.done(8, len(findings), "Weighted impact × confidence; see score notes on each finding")

    # 10. graph
    st.start(9)
    graph = build_graph(sources, findings, units)
    st.done(9, len(graph.nodes), f"{len(graph.nodes)} nodes · {len(graph.edges)} edges")

    if mode == "heuristic":
        limitations.insert(0, "Heuristic mode: findings come from pattern matching (cue phrases, numbers, dates, keyword overlap), "
                              "not from language understanding — subtle or implicit issues will be missed.")
    else:
        limitations.insert(0, f"AI-assisted mode ({model}): the model can miss issues or misjudge severity; deterministic checks run alongside it.")
    limitations += [
        "Citations are verified by exact or whitespace/case-normalised substring match only; a verified quote is real, but its interpretation still needs review.",
        "Scanned PDFs are not OCR'd; images, charts and embedded objects are ignored.",
        "Dataset statistics are deterministic and computed from the uploaded rows; they say nothing about data that was not uploaded.",
        "Coverage-gap findings are inferred from absence — the topic may be covered in documents that were not uploaded.",
        "Scores are transparent weighted ratings, not calibrated probabilities. Human review is required before acting on any finding.",
    ]
    ts = now_iso()
    return Investigation(
        id=inv_id, name=(name or "").strip() or default_name(filenames), question=(question or "").strip() or DEFAULT_QUESTION,
        mode=mode, status="ready", created_at=created, updated_at=ts,  # type: ignore[arg-type]
        sources=sources, units=units, findings=findings, graph=graph, scenarios=scenarios, scoring=cfg,
        pipeline=st.steps, limitations=limitations, ai_model=model,
    )
