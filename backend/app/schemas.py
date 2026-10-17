"""Typed contract shared by the pipeline, the API and the frontend (mirrored in frontend/src/types.ts)."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

SourceKind = Literal["pdf", "docx", "txt", "md", "csv", "xlsx"]
UnitKind = Literal["heading", "paragraph", "list_item", "table_row", "dataset_stat"]
Category = Literal[
    "assumption",
    "contradiction",
    "missing_constraint",
    "dependency",
    "contingency",
    "missing_evidence",
    "data_quality",
    "open_question",
]
Classification = Literal["observed_conflict", "missing_evidence", "inferred_assumption", "potential_risk"]
Module = Literal["radar", "contradiction", "dataset"]
Status = Literal["open", "validated", "dismissed", "resolved"]
Origin = Literal["sample", "heuristic", "ai"]
CitationRole = Literal["claim_a", "claim_b", "support", "counter", "context"]
MatchKind = Literal["exact", "normalized", "unverified"]


# ---------------------------------------------------------------- sources & evidence units
class Location(BaseModel):
    page: Optional[int] = None
    sheet: Optional[str] = None
    row: Optional[int] = None  # 1-based data row (header excluded) for CSV / XLSX
    paragraph: Optional[int] = None
    line: Optional[int] = None
    column: Optional[str] = None


class EvidenceUnit(BaseModel):
    id: str  # stable, e.g. "S2.p3.014" — unique within an investigation
    source_id: str
    kind: UnitKind
    location: Location
    label: str  # human-readable locator, e.g. "p.3 ¶2", "Budget · row 7", "line 14"
    text: str
    section: Optional[str] = None  # nearest heading, when known


class ColumnProfile(BaseModel):
    name: str
    dtype: Literal["numeric", "categorical", "date", "text", "boolean", "empty"]
    missing: int
    missing_pct: float
    unique: int
    stats: Optional[dict[str, float]] = None  # min, max, mean, median, std, q1, q3
    top_values: list[tuple[str, int]] = Field(default_factory=list)
    outlier_rows: list[int] = Field(default_factory=list)  # 1-based data rows
    category_variants: list[list[str]] = Field(default_factory=list)  # groups of labels that normalise together


class DatasetProfile(BaseModel):
    sheet: Optional[str] = None
    rows: int
    columns: int
    duplicate_rows: list[int] = Field(default_factory=list)  # 1-based rows that repeat an earlier row
    column_profiles: list[ColumnProfile] = Field(default_factory=list)


class Source(BaseModel):
    id: str  # "S1", "S2", ...
    name: str
    kind: SourceKind
    size_bytes: int
    uploaded_at: str
    synthetic: bool = False
    page_count: Optional[int] = None
    sheet_names: list[str] = Field(default_factory=list)
    row_count: Optional[int] = None
    unit_count: int = 0
    summary: str = ""  # one factual line, e.g. "3 pages · 41 passages"
    profiles: list[DatasetProfile] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------- findings
class Citation(BaseModel):
    source_id: str
    excerpt: str  # must be a verbatim substring of the unit text to be verified
    role: CitationRole = "support"
    unit_id: Optional[str] = None
    location_label: Optional[str] = None
    verified: bool = False
    match: MatchKind = "unverified"
    note: Optional[str] = None


class Claim(BaseModel):
    statement: str
    value: Optional[str] = None
    unit: Optional[str] = None
    as_of: Optional[str] = None
    scope: Optional[str] = None
    citation: Citation


class ComparisonRow(BaseModel):
    dimension: str  # "Value", "Units", "Date / version", "Scope"
    a: str
    b: str
    note: str = ""


class Contradiction(BaseModel):
    claim_a: Claim
    claim_b: Claim
    comparison: list[ComparisonRow] = Field(default_factory=list)
    verdict: Literal["true_conflict", "possible_conflict", "explainable_difference"]
    verdict_reason: str
    resolution: str


class ImpactFactors(BaseModel):
    consequence: int = Field(ge=0, le=100)  # how bad if this is wrong
    decision_relevance: int = Field(ge=0, le=100)  # does it change a go / no-go, budget or date decision
    breadth: int = Field(ge=0, le=100)  # how much of the plan it touches


class ConfidenceFactors(BaseModel):
    evidence_strength: int = Field(ge=0, le=100)  # verified direct evidence vs inference
    specificity: int = Field(ge=0, le=100)  # concrete numbers / dates vs vague language
    corroboration: int = Field(ge=0, le=100)  # independent sources agreeing


class Calculation(BaseModel):
    """Deterministic arithmetic performed on cited figures — shown as 'calculated', never as prediction."""

    label: str
    expression: str  # human readable, e.g. "2,500 accounts × 6 technicians × 4 calls"
    result: str


class Finding(BaseModel):
    id: str
    title: str
    summary: str
    why_it_matters: str
    category: Category
    classification: Classification
    module: Module
    assumption_type: Optional[Literal["explicit", "inferred"]] = None
    impact_factors: ImpactFactors
    confidence_factors: ConfidenceFactors
    impact: int = 0
    confidence: int = 0
    priority: float = 0.0
    score_notes: list[str] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    calculations: list[Calculation] = Field(default_factory=list)
    inference_note: Optional[str] = None
    contradiction: Optional[Contradiction] = None
    recommendation: str
    question: str
    related: list[str] = Field(default_factory=list)  # other finding ids
    depends_on: list[str] = Field(default_factory=list)  # graph node ids of assumptions this rests on
    status: Status = "open"
    reviewer_note: Optional[str] = None
    origin: Origin = "heuristic"


# ---------------------------------------------------------------- graph
NodeType = Literal["source", "claim", "assumption", "constraint", "risk", "question", "action"]
Relation = Literal["supports", "contradicts", "depends_on", "requires_validation", "raises", "addresses", "cites"]


class GraphNode(BaseModel):
    id: str
    type: NodeType
    label: str
    detail: str = ""
    finding_ids: list[str] = Field(default_factory=list)
    source_id: Optional[str] = None
    unit_id: Optional[str] = None


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    relation: Relation


class Graph(BaseModel):
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)


# ---------------------------------------------------------------- scenarios
class ScenarioConstant(BaseModel):
    key: str
    label: str
    value: float
    unit: str = ""
    provenance: Literal["source", "computed", "assumed_default"]
    citation: Optional[Citation] = None


class ScenarioParameter(BaseModel):
    key: str
    label: str
    unit: str = ""
    baseline: float
    min: float
    max: float
    step: float
    default: float


class ScenarioMetric(BaseModel):
    key: str
    label: str
    formula: str  # tiny arithmetic language: + - * / ^ ( ) min max log ln ceil floor abs; identifiers = constants/parameter/earlier metrics
    format: Literal["int", "currency", "pct", "months", "float"] = "float"
    unit: str = ""
    threshold: Optional[float] = None
    threshold_direction: Optional[Literal["above_bad", "below_bad"]] = None
    threshold_label: Optional[str] = None


class EvidenceConclusion(BaseModel):
    text: str
    citations: list[Citation] = Field(default_factory=list)


class Scenario(BaseModel):
    id: str
    title: str
    question: str
    assumption: str
    assumption_node_id: Optional[str] = None
    finding_ids: list[str] = Field(default_factory=list)
    parameter: ScenarioParameter
    constants: list[ScenarioConstant] = Field(default_factory=list)
    metrics: list[ScenarioMetric] = Field(default_factory=list)
    evidence_conclusions: list[EvidenceConclusion] = Field(default_factory=list)
    hypothetical_effects: list[str] = Field(default_factory=list)
    info_needed: list[str] = Field(default_factory=list)
    experiment: str = ""
    origin: Origin = "heuristic"


# ---------------------------------------------------------------- investigation
class ScoringConfig(BaseModel):
    """priority = w_impact * impact + w_confidence * confidence (weights normalised to sum 1)."""

    w_impact: float = 0.65
    w_confidence: float = 0.35
    impact_weights: dict[str, float] = Field(
        default_factory=lambda: {"consequence": 0.5, "decision_relevance": 0.3, "breadth": 0.2}
    )
    confidence_weights: dict[str, float] = Field(
        default_factory=lambda: {"evidence_strength": 0.5, "specificity": 0.3, "corroboration": 0.2}
    )
    unverified_evidence_cap: int = 35  # evidence_strength ceiling when no citation could be verified


class PipelineStep(BaseModel):
    step: str
    detail: str = ""
    count: Optional[int] = None
    ms: Optional[int] = None
    status: Literal["pending", "running", "done", "skipped", "error"] = "done"


class Investigation(BaseModel):
    id: str
    name: str
    question: str
    mode: Literal["sample", "heuristic", "ai"]
    status: Literal["analyzing", "ready", "error"] = "ready"
    error: Optional[str] = None
    created_at: str
    updated_at: str
    sources: list[Source] = Field(default_factory=list)
    units: list[EvidenceUnit] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    graph: Graph = Field(default_factory=Graph)
    scenarios: list[Scenario] = Field(default_factory=list)
    scoring: ScoringConfig = Field(default_factory=ScoringConfig)
    pipeline: list[PipelineStep] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    ai_model: Optional[str] = None


class InvestigationSummary(BaseModel):
    id: str
    name: str
    mode: str
    status: str
    created_at: str
    updated_at: str
    source_count: int
    finding_count: int
    open_count: int


class FindingPatch(BaseModel):
    status: Optional[Status] = None
    reviewer_note: Optional[str] = None
    impact_override: Optional[int] = Field(default=None, ge=0, le=100)
