// Mirrors backend/app/schemas.py — keep in sync.

export type SourceKind = "pdf" | "docx" | "txt" | "md" | "csv" | "xlsx";
export type Category =
  | "assumption"
  | "contradiction"
  | "missing_constraint"
  | "dependency"
  | "contingency"
  | "missing_evidence"
  | "data_quality"
  | "open_question";
export type Classification = "observed_conflict" | "missing_evidence" | "inferred_assumption" | "potential_risk";
export type Module = "radar" | "contradiction" | "dataset";
export type Status = "open" | "validated" | "dismissed" | "resolved";
export type Origin = "sample" | "heuristic" | "ai";

export interface Location {
  page?: number | null;
  sheet?: string | null;
  row?: number | null;
  paragraph?: number | null;
  line?: number | null;
  column?: string | null;
}

export interface EvidenceUnit {
  id: string;
  source_id: string;
  kind: "heading" | "paragraph" | "list_item" | "table_row" | "dataset_stat";
  location: Location;
  label: string;
  text: string;
  section?: string | null;
}

export interface ColumnProfile {
  name: string;
  dtype: string;
  missing: number;
  missing_pct: number;
  unique: number;
  stats?: Record<string, number> | null;
  top_values: [string, number][];
  outlier_rows: number[];
  category_variants: string[][];
}

export interface DatasetProfile {
  sheet?: string | null;
  rows: number;
  columns: number;
  duplicate_rows: number[];
  column_profiles: ColumnProfile[];
}

export interface Source {
  id: string;
  name: string;
  kind: SourceKind;
  size_bytes: number;
  uploaded_at: string;
  synthetic: boolean;
  page_count?: number | null;
  sheet_names: string[];
  row_count?: number | null;
  unit_count: number;
  summary: string;
  profiles: DatasetProfile[];
  warnings: string[];
}

export interface Citation {
  source_id: string;
  excerpt: string;
  role: "claim_a" | "claim_b" | "support" | "counter" | "context";
  unit_id?: string | null;
  location_label?: string | null;
  verified: boolean;
  match: "exact" | "normalized" | "unverified";
  note?: string | null;
}

export interface Claim {
  statement: string;
  value?: string | null;
  unit?: string | null;
  as_of?: string | null;
  scope?: string | null;
  citation: Citation;
}

export interface Contradiction {
  claim_a: Claim;
  claim_b: Claim;
  comparison: { dimension: string; a: string; b: string; note: string }[];
  verdict: "true_conflict" | "possible_conflict" | "explainable_difference";
  verdict_reason: string;
  resolution: string;
}

export interface Finding {
  id: string;
  title: string;
  summary: string;
  why_it_matters: string;
  category: Category;
  classification: Classification;
  module: Module;
  assumption_type?: "explicit" | "inferred" | null;
  impact_factors: { consequence: number; decision_relevance: number; breadth: number };
  confidence_factors: { evidence_strength: number; specificity: number; corroboration: number };
  impact: number;
  confidence: number;
  priority: number;
  score_notes: string[];
  citations: Citation[];
  calculations: { label: string; expression: string; result: string }[];
  inference_note?: string | null;
  contradiction?: Contradiction | null;
  recommendation: string;
  question: string;
  related: string[];
  depends_on: string[];
  status: Status;
  reviewer_note?: string | null;
  origin: Origin;
}

export type NodeType = "source" | "claim" | "assumption" | "constraint" | "risk" | "question" | "action";
export type Relation = "supports" | "contradicts" | "depends_on" | "requires_validation" | "raises" | "addresses" | "cites";

export interface GraphNode {
  id: string;
  type: NodeType;
  label: string;
  detail: string;
  finding_ids: string[];
  source_id?: string | null;
  unit_id?: string | null;
}
export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  relation: Relation;
}

export interface ScenarioConstant {
  key: string;
  label: string;
  value: number;
  unit: string;
  provenance: "source" | "computed" | "assumed_default";
  citation?: Citation | null;
}
export interface ScenarioParameter {
  key: string;
  label: string;
  unit: string;
  baseline: number;
  min: number;
  max: number;
  step: number;
  default: number;
}
export interface ScenarioMetric {
  key: string;
  label: string;
  formula: string;
  format: "int" | "currency" | "pct" | "months" | "float";
  unit: string;
  threshold?: number | null;
  threshold_direction?: "above_bad" | "below_bad" | null;
  threshold_label?: string | null;
}
export interface Scenario {
  id: string;
  title: string;
  question: string;
  assumption: string;
  assumption_node_id?: string | null;
  finding_ids: string[];
  parameter: ScenarioParameter;
  constants: ScenarioConstant[];
  metrics: ScenarioMetric[];
  evidence_conclusions: { text: string; citations: Citation[] }[];
  hypothetical_effects: string[];
  info_needed: string[];
  experiment: string;
  origin: Origin;
}

export interface ScoringConfig {
  w_impact: number;
  w_confidence: number;
  impact_weights: Record<string, number>;
  confidence_weights: Record<string, number>;
  unverified_evidence_cap: number;
}

export interface PipelineStep {
  step: string;
  detail: string;
  count?: number | null;
  ms?: number | null;
  status: "pending" | "running" | "done" | "skipped" | "error";
}

export interface Investigation {
  id: string;
  name: string;
  question: string;
  mode: "sample" | "heuristic" | "ai";
  status: "analyzing" | "ready" | "error";
  error?: string | null;
  created_at: string;
  updated_at: string;
  sources: Source[];
  units: EvidenceUnit[];
  findings: Finding[];
  graph: { nodes: GraphNode[]; edges: GraphEdge[] };
  scenarios: Scenario[];
  scoring: ScoringConfig;
  pipeline: PipelineStep[];
  limitations: string[];
  ai_model?: string | null;
}

export interface InvestigationSummary {
  id: string;
  name: string;
  mode: string;
  status: string;
  created_at: string;
  updated_at: string;
  source_count: number;
  finding_count: number;
  open_count: number;
}

export interface Health {
  ok: boolean;
  ai_available: boolean;
  model: string | null;
  supported_extensions: string[];
  max_file_mb: number;
}

export type View = "investigations" | "overview" | "sources" | "map" | "scenarios" | "report";
