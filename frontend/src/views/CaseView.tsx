import { useEffect, useState } from "react";
import { Constellation, GraphLegend } from "../components/Constellation";
import { SourcePassage } from "../components/Passage";
import { FindingLinks, ReviewControls, ScoreBlock } from "../components/Review";
import { Button, SeverityMark, Tag } from "../components/ui";
import { CATEGORY_LABEL, CLASS_HINT, CLASS_LABEL, cls, MODULE_LABEL, VERDICT_LABEL } from "../lib/format";
import { useStore } from "../store";
import type { Citation, Claim, Finding, Investigation } from "../types";

const ROLE_HINT: Record<Citation["role"], string> = {
  support: "supports the finding",
  counter: "contradicts the stated claim",
  context: "context — not direct proof",
  claim_a: "claim A",
  claim_b: "claim B",
};

/** The evidence investigation view: a full-width dossier for one finding. */
export function CaseView({ f }: { f: Finding }) {
  const { inv, findings, closeCase, selectFinding, selectNode, goSource } = useStore();
  const [active, setActive] = useState(0);
  useEffect(() => setActive(0), [f.id]);
  if (!inv) return null;

  const evidence = f.contradiction ? f.citations.filter((c) => c.role !== "claim_a" && c.role !== "claim_b") : f.citations;
  const cur = evidence[Math.min(active, evidence.length - 1)];
  const rank = findings.findIndex((x) => x.id === f.id);
  const prev = findings[rank - 1];
  const next = findings[rank + 1];
  const open = (id: string) => selectFinding(id, { openCase: true });
  const hasSide = !!f.inference_note || f.calculations.length > 0;

  return (
    <div key={f.id} className="mx-auto max-w-[1200px] px-5 pb-24 pt-4 sm:px-8">
      {/* navigation */}
      <nav className="case-in flex flex-wrap items-center gap-3 border-b border-line pb-3" aria-label="Finding navigation">
        <Button size="sm" tone="line" onClick={closeCase} title="Back to findings (Esc)">
          ← All findings
        </Button>
        <span className="mono text-[11px] text-muted">
          Evidence view · rank <span className="text-fg-dim">{rank + 1}</span> of {findings.length}
        </span>
        <span className="ml-auto flex gap-1">
          <Button size="sm" disabled={!prev} onClick={() => prev && open(prev.id)} title="Previous finding (k)">
            ↑ Previous
          </Button>
          <Button size="sm" disabled={!next} onClick={() => next && open(next.id)} title="Next finding (j)">
            Next ↓
          </Button>
        </span>
      </nav>

      {/* dossier header: claim on the left, verdict & review on the right */}
      <div className="mt-7 grid grid-cols-1 gap-x-10 gap-y-8 lg:grid-cols-[minmax(0,1fr)_300px]">
        <header className="case-in min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="mono text-[12px] text-amber">{f.id}</span>
            <SeverityMark f={f} showLabel />
            <Tag tone={f.category === "contradiction" ? "alert" : "default"}>{CATEGORY_LABEL[f.category]}</Tag>
            <Tag title={CLASS_HINT[f.classification]}>{CLASS_LABEL[f.classification]}</Tag>
            {f.assumption_type && <Tag tone="cool">{f.assumption_type} assumption</Tag>}
            <Tag>{MODULE_LABEL[f.module]}</Tag>
            {f.origin === "ai" && <Tag tone="cool">AI-proposed</Tag>}
          </div>
          <h2 className="display mt-4 text-[30px] font-[420] leading-[1.1] text-fg sm:text-[38px]">{f.title}</h2>
          <p className="mt-4 text-[15.5px] leading-relaxed text-fg-dim">{f.summary}</p>
          <p className="mt-4 border-l-2 border-line pl-4 text-[14.5px] leading-relaxed text-fg-dim">
            <span className="eyebrow mr-2">Why it matters</span>
            {f.why_it_matters}
          </p>
        </header>
        <aside className="case-in-2 space-y-5 self-start border border-line bg-panel/60 p-4 lg:sticky lg:top-4" aria-label="Review and score">
          <ReviewControls f={f} />
          <ScoreBlock f={f} />
          <FindingLinks f={f} onOpen={open} />
        </aside>
      </div>

      {f.contradiction && <ContradictionLab f={f} inv={inv} />}

      {/* source evidence */}
      {evidence.length > 0 && (
        <section className="case-in-2 mt-12">
          <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2 border-b border-line pb-2">
            <h3 className="display text-[21px] text-fg">{f.contradiction ? "Supporting evidence" : "Source evidence"}</h3>
            <span className="mono text-[11px] text-muted">
              {evidence.filter((c) => c.verified).length} of {evidence.length} excerpts verified in extracted text
            </span>
          </div>
          <div className={cls("grid grid-cols-1 gap-8", hasSide && "lg:grid-cols-[minmax(0,1.35fr)_minmax(0,1fr)]")}>
            <div className="min-w-0">
              <div role="tablist" aria-label="Citations" className="flex flex-wrap gap-1.5">
                {evidence.map((c, i) => (
                  <button
                    key={i}
                    role="tab"
                    aria-selected={i === active}
                    onClick={() => setActive(i)}
                    title={ROLE_HINT[c.role]}
                    className={cls(
                      "mono flex h-8 cursor-pointer items-center gap-1.5 border px-2.5 text-[11px] transition-colors",
                      i === active ? "border-amber bg-amber-soft text-amber" : "border-line text-muted hover:border-faint hover:text-fg",
                      !c.verified && "!border-alert/60 !text-alert",
                    )}
                  >
                    <span className={cls("h-1.5 w-1.5 rounded-full", c.role === "counter" ? "bg-alert" : c.role === "context" ? "bg-faint" : "bg-ok")} />
                    {c.source_id} · {c.location_label ?? "?"}
                  </button>
                ))}
              </div>
              {cur && (
                <>
                  <SourcePassage key={`${f.id}-${active}`} inv={inv} citation={cur} className="mt-3 shadow-[0_24px_60px_-30px_rgba(0,0,0,0.85)]" />
                  <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
                    <span className="mono text-[11px] text-muted">This excerpt {ROLE_HINT[cur.role]}.</span>
                    {cur.verified && cur.unit_id && (
                      <button className="mono cursor-pointer text-[11.5px] text-cool hover:underline" onClick={() => goSource(cur.source_id, cur.unit_id!)}>
                        Open full source →
                      </button>
                    )}
                  </div>
                  {cur.note && <p className="mt-1 text-[12.5px] text-muted">{cur.note}</p>}
                </>
              )}
            </div>
            {hasSide && (
              <div className="min-w-0 space-y-7">
                {f.inference_note && (
                  <div className="border-l-2 border-cool/70 pl-4">
                    <div className="eyebrow mb-1 !text-cool">Labelled as inference</div>
                    <p className="text-[14px] leading-relaxed text-fg-dim">{f.inference_note}</p>
                  </div>
                )}
                {f.calculations.length > 0 && (
                  <div>
                    <div className="eyebrow mb-2">Calculated from cited figures</div>
                    <dl className="divide-y divide-line border-y border-line">
                      {f.calculations.map((c) => (
                        <div key={c.label} className="py-2.5">
                          <dt className="flex items-baseline justify-between gap-3">
                            <span className="text-[13.5px] text-fg-dim">{c.label}</span>
                            <span className="mono whitespace-nowrap text-[14px] text-amber">{c.result}</span>
                          </dt>
                          <dd className="mono mt-0.5 text-[11px] text-muted">{c.expression}</dd>
                        </div>
                      ))}
                    </dl>
                  </div>
                )}
              </div>
            )}
          </div>
          {!cur && <p className="text-[13px] text-muted">No direct excerpt — this finding is an inference from the material as a whole.</p>}
        </section>
      )}
      {evidence.length === 0 && !f.contradiction && (
        <p className="mt-10 border border-dashed border-line p-4 text-[13.5px] text-muted">No direct excerpt. This finding is an inference from the material as a whole.</p>
      )}

      {/* focused constellation */}
      <section className="case-in-3 mt-12 min-w-0">
        <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2 border-b border-line pb-2">
          <h3 className="display text-[21px] text-fg">How this connects</h3>
          <span className="mono text-[11px] text-muted">sources → cited passages → this finding → question → action · click any node</span>
        </div>
        <div className="h-[420px] border border-line bg-ink/50">
          <Constellation
            nodes={inv.graph.nodes}
            edges={inv.graph.edges}
            findings={findings}
            focusFinding={f.id}
            compact
            onNodeClick={(n) => {
              if (n.id.startsWith("f:")) open(n.id.slice(2));
              else if (n.type === "claim" && n.source_id && n.unit_id) goSource(n.source_id, n.unit_id);
              else selectNode(n.id);
            }}
          />
        </div>
        <div className="mt-2">
          <GraphLegend />
        </div>
      </section>

      {/* next action */}
      <section className="case-in-3 mt-10 grid grid-cols-1 border border-amber/40 md:grid-cols-2">
        <div className="border-b border-amber/30 bg-amber-soft p-6 md:border-b-0 md:border-r">
          <div className="eyebrow !text-amber">Next action</div>
          <p className="mt-2 text-[16px] leading-relaxed text-fg">{f.recommendation}</p>
        </div>
        <div className="p-6">
          <div className="eyebrow">The question to investigate</div>
          <p className="display mt-2 text-[20px] italic leading-snug text-fg">{f.question}</p>
        </div>
      </section>
    </div>
  );
}

function ClaimSheet({ side, claim, inv }: { side: "A" | "B"; claim: Claim; inv: Investigation }) {
  return (
    <div className="min-w-0">
      <div className="mb-3 flex items-start gap-2.5">
        <span className="mono mt-1 flex h-6 w-6 shrink-0 items-center justify-center border border-alert/70 text-[12px] text-alert">{side}</span>
        <span className="display text-[19px] leading-snug text-fg">{claim.statement}</span>
      </div>
      <SourcePassage inv={inv} citation={claim.citation} context={0} />
      <dl className="mono mt-2.5 grid grid-cols-[4.5rem_1fr] gap-y-1 text-[11px] text-muted">
        {claim.value && (
          <>
            <dt>value</dt>
            <dd className="text-fg-dim">{claim.value}</dd>
          </>
        )}
        {claim.scope && (
          <>
            <dt>scope</dt>
            <dd className="text-fg-dim">{claim.scope}</dd>
          </>
        )}
        {claim.as_of && (
          <>
            <dt>as of</dt>
            <dd className="text-fg-dim">{claim.as_of}</dd>
          </>
        )}
      </dl>
    </div>
  );
}

function ContradictionLab({ f, inv }: { f: Finding; inv: Investigation }) {
  const c = f.contradiction!;
  const tone = c.verdict === "true_conflict" ? "text-alert border-alert" : c.verdict === "possible_conflict" ? "text-amber border-amber" : "text-ok border-ok";
  return (
    <section className="case-in-2 mt-12">
      <div className="mb-5 flex flex-wrap items-center gap-x-4 gap-y-2 border-b border-line pb-2">
        <h3 className="display text-[21px] text-fg">Contradiction lab</h3>
        <span className={cls("mono -rotate-1 border-2 px-2.5 py-0.5 text-[12px] font-semibold uppercase tracking-[0.18em]", tone)}>{VERDICT_LABEL[c.verdict]}</span>
        <span className="mono ml-auto text-[11px] text-muted">Both sides shown · ASK//WHY does not decide which source is right</span>
      </div>
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_44px_1fr]">
        <ClaimSheet side="A" claim={c.claim_a} inv={inv} />
        <div className="hidden flex-col items-center justify-center lg:flex" aria-hidden>
          <span className="h-full w-px bg-line" />
          <span className="display my-3 flex h-10 w-10 shrink-0 items-center justify-center rounded-full border border-alert/60 text-[22px] text-alert">≠</span>
          <span className="h-full w-px bg-line" />
        </div>
        <ClaimSheet side="B" claim={c.claim_b} inv={inv} />
      </div>
      {c.comparison.length > 0 && (
        <div className="mt-7 overflow-x-auto">
          <table className="w-full min-w-[560px] border-collapse text-[13.5px]">
            <thead>
              <tr className="mono text-left text-[10.5px] uppercase tracking-widest text-faint">
                <th className="w-[18%] py-2 pr-3 font-normal">Compared on</th>
                <th className="w-[27%] py-2 pr-3 font-normal">Claim A</th>
                <th className="w-[27%] py-2 pr-3 font-normal">Claim B</th>
                <th className="py-2 font-normal">Note</th>
              </tr>
            </thead>
            <tbody>
              {c.comparison.map((r) => (
                <tr key={r.dimension} className="border-t border-line align-top">
                  <td className="mono py-2.5 pr-3 text-[11.5px] text-muted">{r.dimension}</td>
                  <td className="py-2.5 pr-3 text-fg">{r.a}</td>
                  <td className="py-2.5 pr-3 text-fg">{r.b}</td>
                  <td className="py-2.5 text-[13px] text-muted">{r.note}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <div className="mt-6 grid grid-cols-1 gap-6 md:grid-cols-2">
        <div>
          <div className="eyebrow mb-1">Why this verdict</div>
          <p className="text-[14px] leading-relaxed text-fg-dim">{c.verdict_reason}</p>
        </div>
        <div>
          <div className="eyebrow mb-1">What would resolve it</div>
          <p className="text-[14px] leading-relaxed text-fg-dim">{c.resolution}</p>
        </div>
      </div>
    </section>
  );
}
