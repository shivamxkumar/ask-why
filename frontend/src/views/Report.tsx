import { Button } from "../components/ui";
import { toMarkdown } from "../lib/report";
import { CATEGORY_LABEL, CLASS_LABEL, severity, SEVERITY_LABEL, STATUS_LABEL, VERDICT_LABEL } from "../lib/format";
import { useStore } from "../store";
import { CREDIT } from "../lib/brand";
import type { Citation, Finding, Investigation } from "../types";

export function Report() {
  const { inv, findings } = useStore();
  if (!inv) return null;
  const top = findings.filter((f) => f.status !== "dismissed").slice(0, 5);
  const contradictions = findings.filter((f) => f.contradiction);
  const assumptions = findings.filter((f) => f.category === "assumption" || f.category === "missing_constraint" || f.category === "missing_evidence" || f.category === "contingency");
  const dataset = findings.filter((f) => f.module === "dataset");
  const dismissed = findings.filter((f) => f.status === "dismissed");
  const cites = findings.flatMap((f) => f.citations);
  const verified = cites.filter((c) => c.verified).length;

  const download = () => {
    const blob = new Blob([toMarkdown(inv, findings)], { type: "text/markdown" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `${inv.name.replace(/[^a-z0-9]+/gi, "-").toLowerCase()}-askwhy-report.md`;
    a.click();
    URL.revokeObjectURL(a.href);
  };

  return (
    <div className="print-root min-h-full bg-ink py-8">
      <div className="no-print mx-auto mb-4 flex max-w-[860px] flex-wrap items-center justify-between gap-3 px-5">
        <p className="mono text-[11px] text-muted">Print-ready report · reflects current review status and ranking</p>
        <div className="flex gap-2">
          <Button tone="line" size="sm" onClick={download}>
            Download Markdown
          </Button>
          <Button tone="primary" size="sm" onClick={() => window.print()}>
            Print / Save as PDF
          </Button>
        </div>
      </div>
      <article className="paper print-sheet mx-auto max-w-[860px] px-8 py-10 text-paper-ink shadow-[0_30px_80px_-30px_rgba(0,0,0,0.8)] sm:px-14">
        <header className="border-b-2 border-paper-ink pb-5">
          <div className="mono flex justify-between text-[10.5px] uppercase tracking-widest text-paper-muted">
            <span>ASK//WHY investigation report</span>
            <span>{new Date().toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" })}</span>
          </div>
          <h1 className="display mt-4 text-[34px] font-[450] leading-tight">{inv.name}</h1>
          <p className="display mt-2 text-[19px] italic leading-snug text-paper-ink/80">{inv.question}</p>
          {inv.mode === "sample" && (
            <p className="mono mt-3 inline-block border border-paper-ink/40 px-2 py-0.5 text-[10.5px] uppercase tracking-wider">Sample investigation · synthetic data · curated findings</p>
          )}
        </header>

        <Section n="1" title="Executive overview">
          <p className="text-[14px] leading-relaxed">
            {findings.length} findings were raised from {inv.sources.length} sources ({inv.sources.map((s) => s.name).join(", ")}). {contradictions.length} involve conflicting
            claims between sources, {assumptions.length} concern assumptions, constraints or missing evidence, and {dataset.length} concern dataset quality. {verified} of {cites.length} cited
            excerpts were verified verbatim against the extracted source text. {findings.filter((f) => f.status !== "open").length} of {findings.length} findings have been reviewed.
          </p>
          {top[0] && (
            <p className="mt-3 border-l-2 border-paper-ink pl-3 text-[14px] leading-relaxed">
              <strong>Highest priority:</strong> {top[0].title}. {top[0].why_it_matters}
            </p>
          )}
        </Section>

        <Section n="2" title="Highest-priority findings">
          {top.map((f, i) => (
            <FindingBlock key={f.id} f={f} inv={inv} rank={i + 1} />
          ))}
        </Section>

        <Section n="3" title="Contradictions">
          {contradictions.length === 0 && <p className="text-[13.5px]">No cross-source contradictions were detected.</p>}
          {contradictions.map((f) => {
            const c = f.contradiction!;
            return (
              <div key={f.id} className="print-avoid mb-5">
                <h4 className="text-[14.5px] font-semibold">
                  <span className="mono mr-2 text-[11px] text-paper-muted">{f.id}</span>
                  {f.title} — <em className="font-normal">{VERDICT_LABEL[c.verdict]}</em>
                </h4>
                <div className="mt-2 grid grid-cols-2 gap-4 text-[13px]">
                  <Quote label="A" c={c.claim_a.citation} inv={inv} />
                  <Quote label="B" c={c.claim_b.citation} inv={inv} />
                </div>
                <p className="mt-2 text-[13px] leading-relaxed">{c.verdict_reason}</p>
                <p className="mt-1 text-[13px] leading-relaxed">
                  <strong>To resolve:</strong> {c.resolution}
                </p>
              </div>
            );
          })}
        </Section>

        <Section n="4" title="Missing assumptions, constraints & evidence">
          <ul className="space-y-2 text-[13.5px]">
            {assumptions.map((f) => (
              <li key={f.id}>
                <span className="mono mr-2 text-[11px] text-paper-muted">{f.id}</span>
                <strong>{f.title}</strong> — {CLASS_LABEL[f.classification]}
                {f.assumption_type ? `, ${f.assumption_type}` : ""}. {f.inference_note ? <em>Inference: {f.inference_note}</em> : null}
              </li>
            ))}
          </ul>
          {dataset.length > 0 && (
            <>
              <h4 className="mt-4 text-[13.5px] font-semibold">Dataset quality</h4>
              <ul className="mt-1 space-y-1 text-[13.5px]">
                {dataset.map((f) => (
                  <li key={f.id}>
                    <span className="mono mr-2 text-[11px] text-paper-muted">{f.id}</span>
                    {f.title}
                  </li>
                ))}
              </ul>
            </>
          )}
        </Section>

        <Section n="5" title="Open questions">
          <ol className="list-decimal space-y-1.5 pl-5 text-[14px]">
            {findings
              .filter((f) => f.status === "open" || f.status === "validated")
              .map((f) => (
                <li key={f.id} className="display italic">
                  {f.question} <span className="mono not-italic text-[10.5px] text-paper-muted">({f.id})</span>
                </li>
              ))}
          </ol>
        </Section>

        <Section n="6" title="Recommended next actions">
          <table className="w-full border-collapse text-[13px]">
            <tbody>
              {findings
                .filter((f) => f.status !== "dismissed" && f.status !== "resolved")
                .map((f) => (
                  <tr key={f.id} className="border-t border-paper-line align-top">
                    <td className="mono w-12 py-1.5 text-[11px] text-paper-muted">{f.id}</td>
                    <td className="py-1.5 pr-2">{f.recommendation}</td>
                    <td className="mono w-20 py-1.5 text-right text-[10.5px] uppercase">{SEVERITY_LABEL[severity(f)]}</td>
                  </tr>
                ))}
            </tbody>
          </table>
        </Section>

        <Section n="7" title="Sources & limitations">
          <ul className="mono space-y-0.5 text-[11.5px]">
            {inv.sources.map((s) => (
              <li key={s.id}>
                {s.id} · {s.name} · {s.summary}
                {s.synthetic ? " · synthetic" : ""}
              </li>
            ))}
          </ul>
          <ul className="mt-3 list-disc space-y-1 pl-5 text-[13px]">
            {inv.limitations.map((l) => (
              <li key={l}>{l}</li>
            ))}
            {dismissed.length > 0 && <li>{dismissed.length} finding(s) were dismissed by a reviewer and are excluded from the action list.</li>}
          </ul>
          <p className="mt-4 border-t border-paper-line pt-3 text-[12.5px] italic">
            Scoring: priority = {inv.scoring.w_impact.toFixed(2)} × impact + {inv.scoring.w_confidence.toFixed(2)} × confidence. Confidence is an evidence-strength rating, not a calibrated
            probability. Human review is required before acting on any finding.
          </p>
          <p className="mono mt-6 border-t border-paper-line pt-3 text-center text-[10.5px] uppercase tracking-widest text-paper-muted">ASK//WHY · {CREDIT}</p>
        </Section>
      </article>
    </div>
  );
}

function Section({ n, title, children }: { n: string; title: string; children: React.ReactNode }) {
  return (
    <section className="mt-8">
      <h2 className="display mb-3 flex items-baseline gap-3 border-b border-paper-line pb-1 text-[21px]">
        <span className="mono text-[12px] text-paper-muted">{n}</span>
        {title}
      </h2>
      {children}
    </section>
  );
}

function Quote({ label, c, inv }: { label: string; c: Citation; inv: Investigation }) {
  const src = inv.sources.find((s) => s.id === c.source_id);
  return (
    <div className="border-l-2 border-paper-ink/40 pl-2">
      <div className="mono text-[10px] uppercase text-paper-muted">
        Claim {label} · {c.source_id} {src?.name} · {c.location_label ?? "—"} · {c.verified ? "verified" : "UNVERIFIED"}
      </div>
      <p className="display mt-0.5 italic">“{c.excerpt}”</p>
    </div>
  );
}

function FindingBlock({ f, inv, rank }: { f: Finding; inv: Investigation; rank: number }) {
  return (
    <div className="print-avoid mb-6">
      <h3 className="text-[16px] font-semibold leading-snug">
        <span className="mono mr-2 text-[11px] text-paper-muted">
          {rank}. {f.id}
        </span>
        {f.title}
      </h3>
      <p className="mono mt-1 text-[10.5px] uppercase tracking-wider text-paper-muted">
        {CATEGORY_LABEL[f.category]} · {CLASS_LABEL[f.classification]} · impact {f.impact} · confidence {f.confidence} · priority {f.priority.toFixed(0)} · {STATUS_LABEL[f.status]}
      </p>
      <p className="mt-2 text-[13.5px] leading-relaxed">{f.summary}</p>
      <p className="mt-1 text-[13.5px] leading-relaxed">
        <strong>Why it matters:</strong> {f.why_it_matters}
      </p>
      <ul className="mt-2 space-y-1">
        {f.citations.slice(0, 4).map((c, i) => (
          <li key={i} className="text-[12.5px]">
            <span className="mono text-[10.5px] text-paper-muted">
              [{c.source_id} · {c.location_label ?? "—"} · {c.verified ? "verified" : "UNVERIFIED"}]
            </span>{" "}
            <span className="display italic">“{c.excerpt.length > 220 ? c.excerpt.slice(0, 220) + "…" : c.excerpt}”</span>
          </li>
        ))}
      </ul>
      {f.reviewer_note && <p className="mt-1 text-[12.5px]">Reviewer note: {f.reviewer_note}</p>}
      <p className="mt-2 text-[13.5px]">
        <strong>Next action:</strong> {f.recommendation}
      </p>
      <p className="display mt-1 text-[14px] italic">Question: {f.question}</p>
      {inv.mode === "sample" ? null : f.origin === "ai" ? <p className="mono mt-1 text-[10px] text-paper-muted">Proposed by AI; citations re-validated.</p> : null}
    </div>
  );
}
