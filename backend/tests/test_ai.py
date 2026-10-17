from app.analysis import ai
from app.analysis.ai import AICitation, AIClaimSide, AIConfidence, AIContradiction, AIFinding, AIImpact, convert_finding
from app.schemas import Finding


def test_ai_disabled_in_tests():
    assert not ai.ai_available() and ai.ai_model() is None
    logs = []
    assert ai.run_ai_analysis([], [], [], lambda *a: logs.append(a)) == []
    assert logs and logs[0][1] == "skipped"


def test_convert_fake_ai_finding(corpus):
    from app.analysis.validation import validate_investigation

    _, units = corpus
    by_id = {u.id: u for u in units}
    af = AIFinding(
        title="Launch date differs between brief and finance", summary="s", why_it_matters="w",
        category="contradiction", classification="observed_conflict",
        citations=[AICitation(unit_id="S1.007", excerpt="Public launch on 15 March 2027", role="claim_a")],
        impact_factors=AIImpact(consequence=80, decision_relevance=80, breadth=50),
        confidence_factors=AIConfidence(evidence_strength=80, specificity=80, corroboration=50),
        recommendation="r", question="q?",
        contradiction=AIContradiction(
            claim_a=AIClaimSide(unit_id="S1.007", excerpt="Public launch on 15 March 2027", statement="Launch 15 March", value="15 March 2027"),
            claim_b=AIClaimSide(unit_id="S5.assumptions.r0001", excerpt="Value: April 2027", statement="Launch April", value="April 2027"),
            verdict="true_conflict", verdict_reason="different months", resolution="Ask finance and product."),
    )
    f = convert_finding(af, 1, by_id)
    assert isinstance(f, Finding) and f.id == "A01" and f.origin == "ai" and f.module == "contradiction"
    Finding.model_validate(f.model_dump())
    verified, unverified = validate_investigation([f], [], units)
    assert unverified == 0 and verified >= 2


def test_ai_connection_error_falls_back(monkeypatch, corpus):
    import anthropic
    import httpx

    sources, units = corpus

    class FakeMessages:
        def parse(self, **kw):
            raise anthropic.APIConnectionError(request=httpx.Request("POST", "https://api.anthropic.com/v1/messages"))

    class FakeClient:
        messages = FakeMessages()

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(anthropic, "Anthropic", lambda *a, **k: FakeClient())
    logs = []
    out = ai.run_ai_analysis(sources, units, [], lambda *a: logs.append(a))
    assert out == [] and any(s == "error" for _, s, _ in logs)


def test_ai_refusal_skips(monkeypatch, corpus):
    import anthropic

    sources, units = corpus

    class Resp:
        stop_reason = "refusal"
        parsed_output = None

    class FakeMessages:
        def parse(self, **kw):
            return Resp()

    class FakeClient:
        messages = FakeMessages()

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(anthropic, "Anthropic", lambda *a, **k: FakeClient())
    logs = []
    assert ai.run_ai_analysis(sources, units, [], lambda *a: logs.append(a)) == []
    assert any(s == "skipped" for _, s, _ in logs)


def test_pipeline_merges_ai_findings(monkeypatch):
    from app import pipeline
    from conftest import FILES, SAMPLE

    def fake_ai(sources, units, heur, log_cb):
        f = convert_finding(AIFinding(
            title="Total budget differs between brief and finance", summary="AI summary", why_it_matters="w",
            category="contradiction", classification="observed_conflict",
            citations=[AICitation(unit_id="S1.019", excerpt="Total approved project budget: $1.2M", role="claim_a")],
            impact_factors=AIImpact(consequence=80, decision_relevance=80, breadth=50),
            confidence_factors=AIConfidence(evidence_strength=80, specificity=80, corroboration=50),
            recommendation="r", question="q?"), 1, {u.id: u for u in units})
        log_cb("AI findings", "done", "1 finding")
        return [f]

    monkeypatch.setattr(pipeline.ai, "ai_available", lambda: True)
    monkeypatch.setattr(pipeline.ai, "ai_model", lambda: "claude-opus-5-5")
    monkeypatch.setattr(pipeline.ai, "run_ai_analysis", fake_ai)
    files = [(name, (FILES / name).read_bytes()) for _, name in SAMPLE]
    inv = pipeline.run_pipeline("t1", None, None, files, True)
    assert inv.mode == "ai" and inv.ai_model == "claude-opus-5-5"
    a01 = next(f for f in inv.findings if f.id == "A01")
    assert a01.contradiction is not None  # inherited from the merged heuristic finding
    assert not any(f.origin == "heuristic" and "budget" in f.title.lower() and f.contradiction and "1.20M" in f.title for f in inv.findings)
