"""Deterministic citation checks: an excerpt is 'verified' only if it is literally present in extracted source text.

Matching order for each citation:
  1. exact substring of the cited unit                      -> match="exact"
  2. substring after normalisation (case, quotes, dashes,
     whitespace, line-break hyphenation) of the cited unit  -> match="normalized"
  3. the same checks against every unit of the cited source,
     then every unit in the investigation (the unit_id /
     source_id are corrected to where the text really is)
  4. otherwise                                              -> verified=False, match="unverified"
No fuzzy matching: a paraphrase is not evidence.
"""
from __future__ import annotations

import re
from typing import Iterable, Optional

from app.schemas import Citation, EvidenceUnit, Finding, Scenario

_QUOTES = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-", "−": "-", " ": " "})
MIN_EXCERPT_CHARS = 12  # shorter excerpts are too ambiguous to count as evidence


def normalize(text: str) -> str:
    text = text.translate(_QUOTES)
    text = re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip().lower()


class UnitIndex:
    def __init__(self, units: Iterable[EvidenceUnit]):
        self.units = list(units)
        self.by_id = {u.id: u for u in self.units}
        self.norm = {u.id: normalize(u.text) for u in self.units}
        self.by_source: dict[str, list[EvidenceUnit]] = {}
        for u in self.units:
            self.by_source.setdefault(u.source_id, []).append(u)

    def find(self, excerpt: str, unit_id: Optional[str], source_id: Optional[str]) -> tuple[Optional[EvidenceUnit], str]:
        target = normalize(excerpt)
        if len(target) < MIN_EXCERPT_CHARS:
            return None, "unverified"
        candidates: list[EvidenceUnit] = []
        if unit_id and unit_id in self.by_id:
            candidates.append(self.by_id[unit_id])
        if source_id:
            candidates.extend(self.by_source.get(source_id, []))
        candidates.extend(self.units)
        seen: set[str] = set()
        for u in candidates:
            if u.id in seen:
                continue
            seen.add(u.id)
            if excerpt in u.text:
                return u, "exact"
            if target in self.norm[u.id]:
                return u, "normalized"
        return None, "unverified"


def validate_citation(c: Citation, index: UnitIndex) -> Citation:
    unit, match = index.find(c.excerpt, c.unit_id, c.source_id)
    if unit is None:
        c.verified = False
        c.match = "unverified"
        if not c.note:
            c.note = "Excerpt not found in the extracted source text — treat as unverified."
        return c
    if c.unit_id and c.unit_id != unit.id:
        c.note = f"Citation relocated from {c.unit_id} to {unit.id}, where the excerpt actually appears."
    c.unit_id = unit.id
    c.source_id = unit.source_id
    c.location_label = unit.label
    c.verified = True
    c.match = match  # type: ignore[assignment]
    return c


def _finding_citations(f: Finding) -> list[Citation]:
    out = list(f.citations)
    if f.contradiction:
        out += [f.contradiction.claim_a.citation, f.contradiction.claim_b.citation]
    return out


def validate_investigation(findings: list[Finding], scenarios: list[Scenario], units: list[EvidenceUnit]) -> tuple[int, int]:
    index = UnitIndex(units)
    verified = unverified = 0
    for f in findings:
        for c in _finding_citations(f):
            validate_citation(c, index)
            verified += c.verified
            unverified += not c.verified
        if f.contradiction:
            # contradiction sides are shown in the citation list too; keep them in sync
            sides = {f.contradiction.claim_a.citation.excerpt, f.contradiction.claim_b.citation.excerpt}
            f.citations = [c for c in f.citations if c.excerpt not in sides] + [
                f.contradiction.claim_a.citation,
                f.contradiction.claim_b.citation,
            ]
    for s in scenarios:
        cites = [k.citation for k in s.constants if k.citation] + [c for e in s.evidence_conclusions for c in e.citations]
        for c in cites:
            validate_citation(c, index)
            verified += c.verified
            unverified += not c.verified
    return verified, unverified
