"""Markdown report for an investigation."""
from __future__ import annotations

from collections import Counter

from app.schemas import Citation, Finding, Investigation

CATEGORY_LABEL = {
    "assumption": "Assumptions", "contradiction": "Contradictions", "missing_constraint": "Missing constraints",
    "dependency": "Dependencies", "contingency": "Contingency gaps", "missing_evidence": "Missing evidence",
    "data_quality": "Data quality", "open_question": "Open questions",
}
VERDICT_LABEL = {"true_conflict": "True conflict", "possible_conflict": "Possible conflict", "explainable_difference": "Explainable difference"}


def _q(text: str) -> str:
    return " ".join(text.split()).replace("|", "\\|")


def _cite_line(c: Citation, names: dict[str, str]) -> str:
    flag = "verified" if c.verified else "UNVERIFIED"
    loc = c.location_label or "location unknown"
    return f"  - “{_q(c.excerpt)}” — *{names.get(c.source_id, c.source_id)}, {loc}* ({c.role}, {flag})"


def _finding_block(f: Finding, names: dict[str, str], level: str = "###") -> list[str]:
    out = [f"{level} {f.id} · {f.title}", "",
           f"**{CATEGORY_LABEL.get(f.category, f.category)}** · {f.classification.replace('_', ' ')} · impact {f.impact} · "
           f"confidence {f.confidence} · priority {f.priority} · status {f.status}", "", f.summary, "",
           f"*Why it matters:* {f.why_it_matters}", ""]
    if f.inference_note:
        out += [f"*Inference:* {f.inference_note}", ""]
    if f.citations:
        out.append("Evidence:")
        out += [_cite_line(c, names) for c in f.citations]
        out.append("")
    if f.calculations:
        out.append("Calculations (deterministic arithmetic on cited figures):")
        out += [f"  - {c.label}: {c.expression} = **{c.result}**" for c in f.calculations]
        out.append("")
    out += [f"**Question to answer:** {f.question}", "", f"**Recommended action:** {f.recommendation}", ""]
    if f.reviewer_note:
        out += [f"*Reviewer note:* {f.reviewer_note}", ""]
    return out


def build_report(inv: Investigation) -> str:
    names = {s.id: s.name for s in inv.sources}
    findings = sorted(inv.findings, key=lambda f: -f.priority)
    cats = Counter(f.category for f in findings)
    verdicts = Counter(f.contradiction.verdict for f in findings if f.contradiction)
    cites = [c for f in findings for c in f.citations]
    verified = sum(c.verified for c in cites)
    L: list[str] = [f"# ASK//WHY report — {inv.name}", "",
                    f"> **Question:** {inv.question}", "",
                    f"Mode: **{inv.mode}**" + (f" ({inv.ai_model})" if inv.ai_model else "") +
                    f" · generated from {len(inv.sources)} source(s) · last updated {inv.updated_at}", ""]

    L += ["## Executive overview", "",
          f"{len(findings)} findings; {sum(1 for f in findings if f.status == 'open')} open. "
          f"{verified} of {len(cites)} citations verified against the extracted source text.", "",
          "| Category | Count |", "|---|---|"]
    L += [f"| {CATEGORY_LABEL.get(k, k)} | {v} |" for k, v in sorted(cats.items(), key=lambda kv: -kv[1])]
    L.append("")
    if verdicts:
        L += ["| Contradiction verdict | Count |", "|---|---|"]
        L += [f"| {VERDICT_LABEL[k]} | {v} |" for k, v in verdicts.items()]
        L.append("")
    L += ["Sources:", ""]
    L += [f"- **{s.id}** {s.name} — {s.summary}" + (" *(synthetic)*" if s.synthetic else "") +
          ("".join(f" ⚠ {w}" for w in s.warnings)) for s in inv.sources]
    L.append("")

    L += ["## Top findings", ""]
    for f in findings[:5]:
        L += _finding_block(f, names)

    contradictions = [f for f in findings if f.contradiction]
    L += ["## Contradictions", ""]
    if not contradictions:
        L += ["No contradictions were detected.", ""]
    for f in contradictions:
        c = f.contradiction
        L += [f"### {f.id} · {f.title}", "", f"**Verdict:** {VERDICT_LABEL[c.verdict]} — {c.verdict_reason}", "",
              "| | Side A | Side B |", "|---|---|---|",
              f"| Statement | {_q(c.claim_a.statement)} | {_q(c.claim_b.statement)} |",
              f"| Source | {names.get(c.claim_a.citation.source_id, c.claim_a.citation.source_id)}, {c.claim_a.citation.location_label or '?'}"
              f"{'' if c.claim_a.citation.verified else ' (unverified)'} | "
              f"{names.get(c.claim_b.citation.source_id, c.claim_b.citation.source_id)}, {c.claim_b.citation.location_label or '?'}"
              f"{'' if c.claim_b.citation.verified else ' (unverified)'} |"]
        L += [f"| {_q(r.dimension)} | {_q(r.a)} | {_q(r.b)} |" for r in c.comparison]
        L += ["", f"**How to resolve:** {c.resolution}", ""]

    L += ["## Assumptions & constraints", ""]
    ac = [f for f in findings if f.category in ("assumption", "missing_constraint", "dependency", "contingency", "missing_evidence")]
    if not ac:
        L += ["None flagged.", ""]
    for f in ac:
        kind = f" ({f.assumption_type})" if f.assumption_type else ""
        L.append(f"- **{f.id}** {f.title}{kind} — {CATEGORY_LABEL.get(f.category, f.category)}, priority {f.priority}")
    L.append("")

    dq = [f for f in findings if f.category == "data_quality"]
    if dq:
        L += ["## Data quality", ""]
        for f in dq:
            L.append(f"- **{f.id}** {f.title}" + "".join(f" — {c.label}: {c.result}" for c in f.calculations[:1]))
        L.append("")

    L += ["## Open questions", ""]
    L += [f"{i}. {f.question} *({f.id})*" for i, f in enumerate(findings, start=1)]
    L.append("")

    L += ["## Next actions", ""]
    for f in [f for f in findings if f.status in ("open", "validated")][:10]:
        L.append(f"- [ ] {f.recommendation} *({f.id}, priority {f.priority})*")
    L.append("")

    if inv.scenarios:
        L += ["## What-if scenarios", ""]
        for s in inv.scenarios:
            L += [f"- **{s.title}** — {s.question}"] + [f"  - *Hypothetical:* {e}" for e in s.hypothetical_effects]
        L.append("")

    L += ["## Limitations", ""] + [f"- {x}" for x in inv.limitations] + [""]
    L += ["---", "", "**Human review required.** ASK//WHY surfaces questions and evidence; it does not decide which source is right. "
          "Every finding should be reviewed by someone who knows the project before it informs a decision.", ""]
    return "\n".join(L)
