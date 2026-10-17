import type { Category, Classification, Finding, NodeType, ScenarioMetric, Status } from "../types";

export const CATEGORY_LABEL: Record<Category, string> = {
  assumption: "Assumption",
  contradiction: "Contradiction",
  missing_constraint: "Missing constraint",
  dependency: "Dependency",
  contingency: "No contingency",
  missing_evidence: "Missing evidence",
  data_quality: "Data quality",
  open_question: "Open question",
};

export const CLASS_LABEL: Record<Classification, string> = {
  observed_conflict: "Observed conflict",
  missing_evidence: "Missing evidence",
  inferred_assumption: "Inferred assumption",
  potential_risk: "Potential risk",
};

export const CLASS_HINT: Record<Classification, string> = {
  observed_conflict: "Sources or data directly disagree",
  missing_evidence: "A claim is made but nothing supports it",
  inferred_assumption: "Implied by the material, not stated — an inference",
  potential_risk: "A plausible failure scenario with no mitigation",
};

export const MODULE_LABEL = { radar: "Blind Spot Radar", contradiction: "Contradiction Lab", dataset: "Dataset audit" } as const;

export const STATUS_LABEL: Record<Status, string> = {
  open: "Open",
  validated: "Validated",
  dismissed: "Dismissed",
  resolved: "Resolved",
};

export const VERDICT_LABEL = {
  true_conflict: "True conflict",
  possible_conflict: "Possible conflict",
  explainable_difference: "Explainable difference",
} as const;

export const NODE_LABEL: Record<NodeType, string> = {
  source: "Source",
  claim: "Claim",
  assumption: "Assumption",
  constraint: "Constraint",
  risk: "Risk",
  question: "Open question",
  action: "Action",
};

export const RELATION_LABEL = {
  supports: "supports",
  contradicts: "contradicts",
  depends_on: "depends on",
  requires_validation: "requires validation",
  raises: "raises",
  addresses: "addressed by",
  cites: "contains",
} as const;

export type Severity = "critical" | "high" | "medium" | "low";

export function severity(f: Pick<Finding, "priority">): Severity {
  if (f.priority >= 80) return "critical";
  if (f.priority >= 68) return "high";
  if (f.priority >= 55) return "medium";
  return "low";
}

export const SEVERITY_LABEL: Record<Severity, string> = { critical: "Critical", high: "High", medium: "Medium", low: "Low" };

export const SEVERITY_COLOR: Record<Severity, string> = {
  critical: "var(--color-alert)",
  high: "var(--color-amber)",
  medium: "var(--color-gold)",
  low: "var(--color-muted)",
};

export function fmtMetric(v: number, m: Pick<ScenarioMetric, "format" | "unit">): string {
  if (!Number.isFinite(v)) return v === Infinity ? "never" : "—";
  switch (m.format) {
    case "int":
      return Math.round(v).toLocaleString("en-US");
    case "currency":
      return (v < 0 ? "−$" : "$") + Math.abs(Math.round(v)).toLocaleString("en-US");
    case "pct":
      return `${(v * 100).toFixed(1)}%`;
    case "months":
      return v > 120 ? "> 10 years" : `${v.toFixed(1)} months`;
    default:
      return `${v.toLocaleString("en-US", { maximumFractionDigits: 2 })}${m.unit ? " " + m.unit : ""}`;
  }
}

export function fmtBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}

export function fmtDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString("en-GB", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
  } catch {
    return iso;
  }
}

export function cls(...xs: (string | false | null | undefined)[]): string {
  return xs.filter(Boolean).join(" ");
}
