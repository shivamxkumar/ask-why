import { useEffect, useMemo, useState } from "react";
import { Empty, Tag, Verified } from "../components/ui";
import { evaluateMetrics } from "../lib/formula";
import { cls, fmtMetric } from "../lib/format";
import { useStore } from "../store";
import type { Scenario, ScenarioMetric } from "../types";

export function Scenarios() {
  const { inv } = useStore();
  const [sel, setSel] = useState(inv?.scenarios[0]?.id ?? null);
  if (!inv) return null;
  if (!inv.scenarios.length)
    return (
      <Empty title="No scenarios for this investigation">
        Scenarios are generated from explicit numeric assumptions. None were found with enough cited figures to calculate against.
      </Empty>
    );
  const s = inv.scenarios.find((x) => x.id === sel) ?? inv.scenarios[0];
  return (
    <div className="grid h-full min-h-0 grid-cols-1 md:grid-cols-[260px_1fr]">
      <div className="min-h-0 overflow-y-auto border-b border-line md:border-b-0 md:border-r">
        <div className="px-5 pb-2 pt-5">
          <div className="eyebrow">Decision simulator</div>
          <p className="mt-1 text-[12px] leading-snug text-muted">Challenge one assumption at a time and see what moves.</p>
        </div>
        <ul>
          {inv.scenarios.map((x) => (
            <li key={x.id}>
              <button
                onClick={() => setSel(x.id)}
                aria-current={x.id === s.id}
                className={cls("w-full cursor-pointer border-l-2 px-5 py-3 text-left", x.id === s.id ? "border-amber bg-panel" : "border-transparent hover:bg-panel/60")}
              >
                <span className="mono text-[10.5px] text-amber">{x.id}</span>
                <span className="display mt-0.5 block text-[16px] leading-snug text-fg">{x.question}</span>
              </button>
            </li>
          ))}
        </ul>
      </div>
      <div className="min-h-0 overflow-y-auto">
        <ScenarioDetail key={s.id} s={s} />
      </div>
    </div>
  );
}

function ScenarioDetail({ s }: { s: Scenario }) {
  const { inv, findings, selectFinding } = useStore();
  const [value, setValue] = useState(s.parameter.default);
  useEffect(() => setValue(s.parameter.default), [s.id, s.parameter.default]);

  const constants = useMemo(() => Object.fromEntries(s.constants.map((c) => [c.key, c.value])), [s.constants]);
  const base = useMemo(() => evaluateMetrics(s.metrics, { ...constants, [s.parameter.key]: s.parameter.baseline }), [s, constants]);
  const cur = useMemo(() => evaluateMetrics(s.metrics, { ...constants, [s.parameter.key]: value }), [s, constants, value]);
  const p = s.parameter;
  const pct = ((value - p.min) / (p.max - p.min)) * 100;
  const basePct = ((p.baseline - p.min) / (p.max - p.min)) * 100;
  const assumptionFinding = s.assumption_node_id ? findings.find((f) => `f:${f.id}` === s.assumption_node_id) : undefined;
  const breaches = s.metrics.filter((m) => breached(m, cur[m.key])).length;

  return (
    <div className="mx-auto max-w-[980px] px-5 pb-24 pt-7 sm:px-8">
      <div className="case-in">
        <div className="eyebrow mb-2">Scenario {s.id} · {s.title}</div>
        <h2 className="display text-[30px] font-[400] italic leading-[1.12] text-fg sm:text-[36px]">{s.question}</h2>
      </div>

      <div className="case-in-2 mt-6 grid grid-cols-1 gap-6 lg:grid-cols-[1fr_1fr]">
        <div className="border-l-2 border-amber pl-4">
          <div className="eyebrow mb-1 !text-amber">Assumption being challenged</div>
          <p className="text-[15px] leading-relaxed text-fg">{s.assumption}</p>
          {assumptionFinding && (
            <button className="mono mt-2 cursor-pointer text-left text-[11px] text-cool hover:underline" onClick={() => selectFinding(assumptionFinding.id, { openCase: true })}>
              {assumptionFinding.id} · {assumptionFinding.title.slice(0, 64)}
              {assumptionFinding.title.length > 64 ? "…" : ""} →
            </button>
          )}
        </div>
        <div>
          <div className="flex items-baseline justify-between">
            <label htmlFor="scn" className="eyebrow">
              {p.label}
            </label>
            <span className="mono text-[22px] text-amber">
              {value}
              {p.unit}
            </span>
          </div>
          <div className="relative mt-2">
            <input
              id="scn"
              type="range"
              min={p.min}
              max={p.max}
              step={p.step}
              value={value}
              onChange={(e) => setValue(+e.target.value)}
              className="w-full"
              aria-valuetext={`${value}${p.unit}`}
            />
            <span className="pointer-events-none absolute -bottom-3 h-2 w-px bg-fg-dim" style={{ left: `calc(${basePct}% + ${(0.5 - basePct / 100) * 16}px)` }} aria-hidden />
          </div>
          <div className="mono mt-3 flex justify-between text-[10px] text-faint">
            <span>
              {p.min}
              {p.unit}
            </span>
            <span>
              plan as stated: {p.baseline}
              {p.unit}
            </span>
            <span>
              {p.max}
              {p.unit}
            </span>
          </div>
          <span className="sr-only">{pct.toFixed(0)}% of range</span>
        </div>
      </div>

      {/* calculations */}
      <section className="case-in-2 mt-9">
        <div className="mb-2 flex flex-wrap items-baseline justify-between gap-2">
          <div className="eyebrow">Calculated · arithmetic on cited figures</div>
          <span className={cls("mono text-[11px]", breaches ? "text-alert" : "text-ok")}>
            {breaches ? `${breaches} threshold${breaches > 1 ? "s" : ""} breached` : "no thresholds breached"}
          </span>
        </div>
        <table className="w-full border-collapse text-[13.5px]">
          <thead>
            <tr className="mono text-left text-[9.5px] uppercase tracking-widest text-faint">
              <th className="py-1.5 pr-3 font-normal">Metric</th>
              <th className="py-1.5 pr-3 text-right font-normal">Plan as stated</th>
              <th className="py-1.5 pr-3 text-right font-normal">This scenario</th>
              <th className="py-1.5 font-normal">Check</th>
            </tr>
          </thead>
          <tbody>
            {s.metrics.map((m) => {
              const bad = breached(m, cur[m.key]);
              return (
                <tr key={m.key} className="border-t border-line align-top">
                  <td className="py-2.5 pr-3 text-fg-dim">
                    {m.label}
                    <div className="mono mt-0.5 text-[10px] text-faint">{m.formula}</div>
                  </td>
                  <td className="mono py-2.5 pr-3 text-right text-[12.5px] text-muted">{fmtMetric(base[m.key], m)}</td>
                  <td className={cls("mono py-2.5 pr-3 text-right text-[14px]", bad ? "text-alert" : "text-fg")}>{fmtMetric(cur[m.key], m)}</td>
                  <td className="py-2.5 text-[12px]">
                    {m.threshold != null ? (
                      bad ? (
                        <span className="text-alert">✕ {m.threshold_label}</span>
                      ) : (
                        <span className="text-muted">✓ within {fmtMetric(m.threshold, m)}</span>
                      )
                    ) : (
                      <span className="text-faint">—</span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        <details className="mt-3">
          <summary className="mono cursor-pointer text-[10.5px] uppercase tracking-wider text-muted">Inputs & provenance ({s.constants.length})</summary>
          <ul className="mt-2 space-y-2">
            {s.constants.map((c) => (
              <li key={c.key} className="grid grid-cols-[1fr_auto] gap-3 border-t border-line-soft pt-2 text-[12.5px]">
                <span className="text-fg-dim">
                  <span className="mono mr-2 text-[10.5px] text-faint">{c.key}</span>
                  {c.label}
                  {c.citation && (
                    <span className="mt-1 flex flex-wrap items-center gap-2">
                      <span className="display text-[12.5px] italic text-muted">“{c.citation.excerpt}”</span>
                      <span className="mono text-[10.5px] text-amber">
                        {c.citation.source_id} {c.citation.location_label}
                      </span>
                      <Verified c={c.citation} />
                    </span>
                  )}
                </span>
                <span className="text-right">
                  <span className="mono text-fg">{c.value.toLocaleString("en-US")}</span> <span className="mono text-[10.5px] text-muted">{c.unit}</span>
                  <span className="block">
                    <Tag tone={c.provenance === "source" ? "ok" : c.provenance === "computed" ? "cool" : "alert"}>{c.provenance.replace("_", " ")}</Tag>
                  </span>
                </span>
              </li>
            ))}
          </ul>
        </details>
      </section>

      {/* evidence vs hypothesis */}
      <section className="case-in-3 mt-9 grid grid-cols-1 gap-6 lg:grid-cols-2">
        <div>
          <div className="eyebrow mb-2">Supported by evidence</div>
          <ul className="space-y-3">
            {s.evidence_conclusions.map((e) => (
              <li key={e.text} className="border-l-2 border-ok/60 pl-3">
                <p className="text-[13.5px] leading-relaxed text-fg">{e.text}</p>
                <div className="mt-1 flex flex-wrap gap-2">
                  {e.citations.map((c, i) => (
                    <span key={i} className="mono flex items-center gap-1.5 text-[10.5px] text-muted">
                      {c.source_id} {c.location_label} <Verified c={c} />
                    </span>
                  ))}
                </div>
              </li>
            ))}
          </ul>
        </div>
        <div className="hatch border border-dashed border-line p-4">
          <div className="mb-2 flex flex-wrap items-center gap-2">
            <span className="eyebrow">Illustrative outcomes</span>
            <Tag tone="alert">hypothetical · not a prediction</Tag>
          </div>
          <ul className="space-y-2">
            {s.hypothetical_effects.map((h) => (
              <li key={h} className="text-[13px] italic leading-relaxed text-fg-dim">
                {h}
              </li>
            ))}
          </ul>
        </div>
      </section>

      <section className="case-in-3 mt-9 grid grid-cols-1 gap-6 border-t border-line pt-6 lg:grid-cols-[1fr_1.2fr]">
        <div>
          <div className="eyebrow mb-2">Information still needed</div>
          <ul className="list-inside list-[square] space-y-1 text-[13px] text-fg-dim marker:text-faint">
            {s.info_needed.map((x) => (
              <li key={x}>{x}</li>
            ))}
          </ul>
          <div className="eyebrow mb-1.5 mt-5">Findings that rest on this assumption</div>
          <div className="flex flex-wrap gap-1.5">
            {s.finding_ids.map((id) => {
              const f = findings.find((x) => x.id === id);
              return f ? (
                <button key={id} title={f.title} onClick={() => selectFinding(id, { openCase: true })} className="mono cursor-pointer border border-line px-2 py-0.5 text-[11px] text-fg-dim hover:border-amber hover:text-amber">
                  {id}
                </button>
              ) : null;
            })}
          </div>
        </div>
        <div className="border border-amber/40 bg-amber-soft p-4">
          <div className="eyebrow mb-1 !text-amber">Validation experiment</div>
          <p className="text-[14.5px] leading-relaxed text-fg">{s.experiment}</p>
        </div>
      </section>
      {inv?.mode === "sample" && <p className="mono mt-8 text-[10.5px] text-faint">Sample scenario on synthetic data. Calculations are live; inputs are cited from the sample sources.</p>}
    </div>
  );
}

function breached(m: ScenarioMetric, v: number): boolean {
  if (m.threshold == null || !m.threshold_direction) return false;
  if (Number.isNaN(v)) return false;
  return m.threshold_direction === "above_bad" ? v > m.threshold : v < m.threshold;
}
