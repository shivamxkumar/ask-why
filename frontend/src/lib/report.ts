import { CREDIT } from "./brand";
import { CATEGORY_LABEL, CLASS_LABEL, severity, SEVERITY_LABEL, STATUS_LABEL, VERDICT_LABEL } from "./format";
import type { Citation, Finding, Investigation } from "../types";

const cite = (c: Citation) => `> “${c.excerpt}”  \n> — ${c.source_id}, ${c.location_label ?? "location unknown"} · ${c.verified ? "verified" : "**UNVERIFIED**"} (${c.role})`;

/** Client-side Markdown export (works offline; mirrors the printable report). */
export function toMarkdown(inv: Investigation, findings: Finding[]): string {
  const L: string[] = [];
  const cites = findings.flatMap((f) => f.citations);
  L.push(`# ASK//WHY investigation report — ${inv.name}`, "", `*${inv.question}*`, "");
  if (inv.mode === "sample") L.push("> Sample investigation on synthetic data. Findings are curated, not live AI output.", "");
  L.push("## Executive overview", "");
  L.push(
    `${findings.length} findings from ${inv.sources.length} sources. ${findings.filter((f) => f.contradiction).length} contradictions, ` +
      `${findings.filter((f) => f.module === "dataset").length} dataset issues. ${cites.filter((c) => c.verified).length}/${cites.length} citations verified against extracted text. ` +
      `${findings.filter((f) => f.status !== "open").length} reviewed.`,
    "",
  );
  L.push("## Findings by priority", "");
  findings.forEach((f, i) => {
    L.push(`### ${i + 1}. ${f.id} — ${f.title}`, "");
    L.push(
      `**${SEVERITY_LABEL[severity(f)]}** · ${CATEGORY_LABEL[f.category]} · ${CLASS_LABEL[f.classification]} · impact ${f.impact} · confidence ${f.confidence} · priority ${f.priority.toFixed(0)} · status: ${STATUS_LABEL[f.status]}`,
      "",
    );
    L.push(f.summary, "", `**Why it matters.** ${f.why_it_matters}`, "");
    if (f.contradiction) {
      const c = f.contradiction;
      L.push(`**Contradiction — ${VERDICT_LABEL[c.verdict]}.** ${c.verdict_reason}`, "", "Claim A:", "", cite(c.claim_a.citation), "", "Claim B:", "", cite(c.claim_b.citation), "");
      L.push(`To resolve: ${c.resolution}`, "");
    }
    const ev = f.citations.filter((c) => c.role !== "claim_a" && c.role !== "claim_b");
    if (ev.length) {
      L.push("**Evidence**", "");
      ev.forEach((c) => L.push(cite(c), ""));
    }
    if (f.calculations.length) {
      L.push("**Calculated from cited figures**", "");
      f.calculations.forEach((c) => L.push(`- ${c.label}: ${c.expression} = **${c.result}**`));
      L.push("");
    }
    if (f.inference_note) L.push(`*Inference:* ${f.inference_note}`, "");
    L.push(`**Next action.** ${f.recommendation}`, "", `**Question to investigate.** ${f.question}`, "");
    if (f.reviewer_note) L.push(`Reviewer note: ${f.reviewer_note}`, "");
  });
  L.push("## Open questions", "");
  findings.filter((f) => f.status === "open" || f.status === "validated").forEach((f) => L.push(`- ${f.question} (${f.id})`));
  L.push("", "## Sources", "");
  inv.sources.forEach((s) => L.push(`- ${s.id} · ${s.name} · ${s.summary}${s.synthetic ? " · synthetic" : ""}`));
  L.push("", "## Limitations", "");
  inv.limitations.forEach((l) => L.push(`- ${l}`));
  L.push("", "Human review is required before acting on any finding.", "", "---", "", `ASK//WHY · ${CREDIT}`, "");
  return L.join("\n");
}
