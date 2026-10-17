import json
from pathlib import Path

from app.analysis.scoring import score_all, score_finding, set_impact_override
from app.analysis.validation import UnitIndex, normalize, validate_citation
from app.sample.build import build_sample_investigation
from app.schemas import Citation, ConfidenceFactors, EvidenceUnit, Finding, ImpactFactors, Location, ScoringConfig

FRONTEND_SAMPLE = Path(__file__).resolve().parents[2] / "frontend" / "src" / "data" / "sample-investigation.json"


def _finding(**kw) -> Finding:
    base = dict(
        id="X1", title="t", summary="s", why_it_matters="w", category="assumption", classification="missing_evidence", module="radar",
        impact_factors=ImpactFactors(consequence=80, decision_relevance=60, breadth=40),
        confidence_factors=ConfidenceFactors(evidence_strength=90, specificity=50, corroboration=10),
        recommendation="r", question="q",
    )
    base.update(kw)
    return Finding(**base)


def _unit(text: str, uid: str = "S1.001") -> EvidenceUnit:
    return EvidenceUnit(id=uid, source_id="S1", kind="paragraph", location=Location(line=1), label="line 1", text=text)


# ---------------------------------------------------------------- sample integrity
def test_every_sample_citation_is_verified():
    inv = build_sample_investigation()
    cites = [c for f in inv.findings for c in f.citations]
    cites += [k.citation for s in inv.scenarios for k in s.constants if k.citation]
    cites += [c for s in inv.scenarios for e in s.evidence_conclusions for c in e.citations]
    assert len(cites) > 50
    bad = [(c.source_id, c.excerpt[:60]) for c in cites if not c.verified]
    assert not bad, bad
    unit_text = {u.id: u.text for u in inv.units}
    for c in cites:  # verified really means "present in that unit's text"
        assert normalize(c.excerpt) in normalize(unit_text[c.unit_id])


def test_sample_covers_required_demo_cases():
    inv = build_sample_investigation()
    cats = {f.category for f in inv.findings}
    assert {"assumption", "contradiction", "contingency", "data_quality", "open_question"} <= cats
    assert any(f.contradiction and f.contradiction.verdict == "true_conflict" for f in inv.findings)
    assert len(inv.scenarios) >= 1 and all(s.metrics for s in inv.scenarios)
    node_ids = {n.id for n in inv.graph.nodes}
    assert all(e.source in node_ids and e.target in node_ids for e in inv.graph.edges)
    assert any(e.relation == "depends_on" for e in inv.graph.edges)
    assert any(e.relation == "contradicts" for e in inv.graph.edges)


def test_sample_dataset_figures_match_file():
    inv = build_sample_investigation()
    f06 = next(f for f in inv.findings if f.id == "F06")
    assert "41 paid of 120" in f06.title  # recomputed from pilot_accounts.csv after de-duplication


def test_bundled_frontend_sample_is_in_sync():
    """The offline fallback must equal what the builder produces (ignoring timestamps)."""
    bundled = json.loads(FRONTEND_SAMPLE.read_text())
    fresh = json.loads(build_sample_investigation().model_dump_json())
    for d in (bundled, fresh):
        d.pop("created_at"), d.pop("updated_at")
        for s in d["sources"]:
            s.pop("uploaded_at")
    assert bundled == fresh, "run: .venv/bin/python scripts/export_sample.py"


# ---------------------------------------------------------------- validation
def test_validation_exact_normalized_and_unverified():
    idx = UnitIndex([_unit("The MVP will be online-only.\nOffline support is deferred to v2.")])
    exact = validate_citation(Citation(source_id="S1", excerpt="The MVP will be online-only."), idx)
    assert exact.verified and exact.match == "exact" and exact.unit_id == "S1.001"
    norm = validate_citation(Citation(source_id="S1", excerpt="the mvp will be online-only. offline support"), idx)
    assert norm.verified and norm.match == "normalized"
    fake = validate_citation(Citation(source_id="S1", excerpt="Offline support is the top priority."), idx)
    assert not fake.verified and fake.match == "unverified"
    short = validate_citation(Citation(source_id="S1", excerpt="MVP"), idx)
    assert not short.verified  # too short to count as evidence


def test_validation_relocates_wrong_unit_id():
    idx = UnitIndex([_unit("alpha beta gamma delta", "S1.001"), _unit("the real passage lives here", "S1.002")])
    c = validate_citation(Citation(source_id="S1", unit_id="S1.001", excerpt="the real passage lives here"), idx)
    assert c.verified and c.unit_id == "S1.002" and "relocated" in (c.note or "")


# ---------------------------------------------------------------- scoring
def test_scoring_formula_is_transparent():
    cfg = ScoringConfig()
    f = score_finding(_finding(citations=[Citation(source_id="S1", excerpt="x" * 20, verified=True, match="exact")]), cfg)
    assert f.impact == round(80 * 0.5 + 60 * 0.3 + 40 * 0.2)  # 66
    assert f.confidence == round(90 * 0.5 + 50 * 0.3 + 10 * 0.2)  # 62
    assert f.priority == round(0.65 * 66 + 0.35 * 62, 1)
    assert any(n.startswith("Impact 66") for n in f.score_notes)


def test_unverified_evidence_caps_confidence():
    cfg = ScoringConfig()
    f = score_finding(_finding(citations=[Citation(source_id="S1", excerpt="x" * 20, verified=False)]), cfg)
    assert f.confidence == round(35 * 0.5 + 50 * 0.3 + 10 * 0.2)
    assert any("capped" in n for n in f.score_notes)


def test_weights_and_override_change_ranking():
    a = _finding(id="A", impact_factors=ImpactFactors(consequence=90, decision_relevance=90, breadth=90),
                 confidence_factors=ConfidenceFactors(evidence_strength=20, specificity=20, corroboration=20))
    b = _finding(id="B", impact_factors=ImpactFactors(consequence=50, decision_relevance=50, breadth=50),
                 confidence_factors=ConfidenceFactors(evidence_strength=95, specificity=95, corroboration=95))
    assert [f.id for f in score_all([a, b], ScoringConfig(w_impact=0.9, w_confidence=0.1))] == ["A", "B"]
    assert [f.id for f in score_all([a, b], ScoringConfig(w_impact=0.1, w_confidence=0.9))] == ["B", "A"]
    set_impact_override(a, 10)
    ranked = score_all([a, b], ScoringConfig())
    assert a.impact == 10 and ranked[0].id == "B"
