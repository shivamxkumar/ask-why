"""Transparent prioritisation.

impact     = Σ impact_weights[k]     · impact_factors[k]       (consequence, decision relevance, breadth)
confidence = Σ confidence_weights[k] · confidence_factors[k]   (evidence strength, specificity, corroboration)
priority   = w_impact · impact + w_confidence · confidence     (weights normalised to sum to 1)

Confidence is an evidence-strength rating, not a calibrated probability. If none of a finding's citations
could be verified, evidence_strength is capped at `unverified_evidence_cap` before weighting.
"""
from __future__ import annotations

from app.schemas import Finding, ScoringConfig

OVERRIDE_PREFIX = "Impact manually set to"


def _weighted(values: dict[str, int], weights: dict[str, float]) -> float:
    total = sum(weights.values()) or 1.0
    return sum(values.get(k, 0) * w for k, w in weights.items()) / total


def score_finding(f: Finding, cfg: ScoringConfig) -> Finding:
    impact_vals = f.impact_factors.model_dump()
    conf_vals = f.confidence_factors.model_dump()
    notes: list[str] = []

    citations = list(f.citations)
    any_verified = any(c.verified for c in citations)
    if citations and not any_verified and conf_vals["evidence_strength"] > cfg.unverified_evidence_cap:
        conf_vals["evidence_strength"] = cfg.unverified_evidence_cap
        notes.append(f"Evidence strength capped at {cfg.unverified_evidence_cap}: no cited excerpt could be verified.")
    if not citations:
        conf_vals["evidence_strength"] = min(conf_vals["evidence_strength"], cfg.unverified_evidence_cap)
        notes.append("No direct citation — confidence reflects inference only.")

    override = next((n for n in f.score_notes if n.startswith(OVERRIDE_PREFIX)), None)
    if override:
        impact = float(int(override.removeprefix(OVERRIDE_PREFIX).split()[0].rstrip(".")))
        notes.append(override)
    else:
        impact = _weighted(impact_vals, cfg.impact_weights)
        notes.append(
            "Impact {:.0f} = consequence {} · {:.2f} + decision relevance {} · {:.2f} + breadth {} · {:.2f}".format(
                impact,
                impact_vals["consequence"], cfg.impact_weights.get("consequence", 0),
                impact_vals["decision_relevance"], cfg.impact_weights.get("decision_relevance", 0),
                impact_vals["breadth"], cfg.impact_weights.get("breadth", 0),
            )
        )
    confidence = _weighted(conf_vals, cfg.confidence_weights)
    notes.append(
        "Confidence {:.0f} = evidence {} · {:.2f} + specificity {} · {:.2f} + corroboration {} · {:.2f}".format(
            confidence,
            conf_vals["evidence_strength"], cfg.confidence_weights.get("evidence_strength", 0),
            conf_vals["specificity"], cfg.confidence_weights.get("specificity", 0),
            conf_vals["corroboration"], cfg.confidence_weights.get("corroboration", 0),
        )
    )
    w_sum = (cfg.w_impact + cfg.w_confidence) or 1.0
    priority = (cfg.w_impact * impact + cfg.w_confidence * confidence) / w_sum
    notes.append(f"Priority {priority:.1f} = {cfg.w_impact / w_sum:.2f} × impact + {cfg.w_confidence / w_sum:.2f} × confidence")
    verified = sum(c.verified for c in citations)
    if citations:
        notes.append(f"{verified} of {len(citations)} citations verified against extracted text.")

    f.impact = round(impact)
    f.confidence = round(confidence)
    f.priority = round(priority, 1)
    f.score_notes = notes
    return f


def set_impact_override(f: Finding, value: int) -> None:
    f.score_notes = [n for n in f.score_notes if not n.startswith(OVERRIDE_PREFIX)]
    f.score_notes.insert(0, f"{OVERRIDE_PREFIX} {value} by reviewer.")


def score_all(findings: list[Finding], cfg: ScoringConfig) -> list[Finding]:
    for f in findings:
        score_finding(f, cfg)
    return sorted(findings, key=lambda f: (-f.priority, -f.impact, f.id))
