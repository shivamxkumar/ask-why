from app.analysis.heuristics import run_heuristics, split_sentences
from app.schemas import Finding, Scenario


def test_findings_on_sample(corpus):
    sources, units = corpus
    findings, scenarios = run_heuristics(sources, units)
    assert len(findings) >= 10
    assert all(isinstance(f, Finding) and f.origin == "heuristic" and f.id.startswith("H") for f in findings)
    cats = {f.category for f in findings}
    assert {"contradiction", "assumption", "data_quality"} <= cats
    titles = " ".join(f.title for f in findings)
    assert "PathCore" in titles and "offline" in titles and "duplicate" in titles
    budget = next(f for f in findings if f.contradiction and "budget" in f.title)
    assert budget.contradiction.verdict == "true_conflict"
    ga = next(f for f in findings if f.contradiction and "2 May 2027" in f.title and "15 March 2027" in f.title)
    assert ga.contradiction.verdict == "possible_conflict"
    assert all(f.impact == 0 and f.priority == 0 for f in findings)
    assert 1 <= len(scenarios) <= 3 and all(isinstance(s, Scenario) for s in scenarios)


def test_all_heuristic_citations_verify(corpus):
    from app.analysis.validation import validate_investigation

    sources, units = corpus
    findings, scenarios = run_heuristics(sources, units)
    verified, unverified = validate_investigation(findings, scenarios, units)
    assert unverified == 0 and verified > 30
    by_id = {u.id: u for u in units}
    for f in findings:
        for c in f.citations:
            assert c.unit_id in by_id and c.excerpt in by_id[c.unit_id].text


def test_scenario_formulas_use_known_identifiers(corpus):
    import re

    sources, units = corpus
    _, scenarios = run_heuristics(sources, units)
    funcs = {"min", "max", "log", "ln", "ceil", "floor", "abs"}
    for s in scenarios:
        known = {c.key for c in s.constants} | {s.parameter.key}
        for m in s.metrics:
            assert re.fullmatch(r"[a-z_][a-z0-9_]*", m.key)
            for ident in re.findall(r"[A-Za-z_][A-Za-z0-9_]*", m.formula):
                assert ident in known or ident in funcs, (m.formula, ident)
            known.add(m.key)


def test_deterministic(corpus):
    sources, units = corpus
    a, _ = run_heuristics(sources, units)
    b, _ = run_heuristics(sources, units)
    assert [f.model_dump() for f in a] == [f.model_dump() for f in b]


def test_generic_document_produces_findings():
    from app.parsing import parse_file

    text = (b"# Rollout plan\n\nWe expect 60% of stores to adopt the kiosk by June 2027.\n\n"
            b"Payments are processed via the Stripe API.\n\nGo-live is 1 June 2027.\n")
    other = b"# Ops\n\nThe go-live date is 15 July 2027 for all stores.\n"
    s1, u1 = parse_file(text, "plan.md", "S1")
    s2, u2 = parse_file(other, "ops.md", "S2")
    findings, _ = run_heuristics([s1, s2], u1 + u2)
    titles = " ".join(f.title for f in findings)
    assert "Stripe" in titles and "60%" in titles
    assert any(f.contradiction and f.contradiction.verdict == "true_conflict" for f in findings)


def test_split_sentences_keeps_step_prefix():
    assert split_sentences("Step 1. Sales marks it. Then more text here.") == ["Step 1. Sales marks it.", "Then more text here."]
