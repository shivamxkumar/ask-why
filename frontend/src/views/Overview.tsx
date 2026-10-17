import { useEffect, useMemo, useRef, useState } from "react";
import { Matrix } from "../components/Matrix";
import { Pipeline } from "../components/Pipeline";
import { Button, SeverityMark, Tag } from "../components/ui";
import { CATEGORY_LABEL, CLASS_LABEL, cls, MODULE_LABEL, severity, SEVERITY_LABEL, STATUS_LABEL, type Severity } from "../lib/format";
import { useStore } from "../store";
import type { Category, Finding, Module, Status } from "../types";

const SEVERITIES: Severity[] = ["critical", "high", "medium", "low"];
const STATUSES: (Status | "all")[] = ["all", "open", "validated", "resolved", "dismissed"];

export function Overview() {
  const { inv, findings, selection, selectFinding, wImpact, setWeight, commitWeight } = useStore();
  const [sev, setSev] = useState<Set<Severity>>(new Set());
  const [cat, setCat] = useState<Category | "all">("all");
  const [mod, setMod] = useState<Module | "all">("all");
  const [status, setStatus] = useState<Status | "all">("all");
  const [minConf, setMinConf] = useState(0);
  const [, setCursor] = useState(0);
  const listRef = useRef<HTMLOListElement>(null);

  const visible = useMemo(
    () =>
      findings.filter(
        (f) =>
          (!sev.size || sev.has(severity(f))) &&
          (cat === "all" || f.category === cat) &&
          (mod === "all" || f.module === mod) &&
          (status === "all" || f.status === status) &&
          f.confidence >= minConf,
      ),
    [findings, sev, cat, mod, status, minConf],
  );

  // j/k + enter keyboard navigation
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement;
      if (t.closest("input,textarea,select,[contenteditable]")) return;
      if (e.key === "j" || e.key === "k") {
        e.preventDefault();
        setCursor((c) => {
          const n = Math.max(0, Math.min(visible.length - 1, c + (e.key === "j" ? 1 : -1)));
          const el = listRef.current?.querySelectorAll<HTMLButtonElement>("[data-row]")[n];
          el?.focus();
          return n;
        });
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [visible.length]);

  if (!inv) return null;
  if (inv.status !== "ready") return <Pipeline />;

  const allCites = findings.flatMap((f) => f.citations);
  const verified = allCites.filter((c) => c.verified).length;
  const contradictions = findings.filter((f) => f.contradiction).length;
  const assumptions = findings.filter((f) => f.category === "assumption" || f.assumption_type).length;
  const dataIssues = findings.filter((f) => f.module === "dataset").length;
  const reviewed = findings.filter((f) => f.status !== "open").length;
  const categories = Array.from(new Set(findings.map((f) => f.category)));
  const selectedId = selection?.kind === "finding" ? selection.id : undefined;
  const filtersOn = sev.size > 0 || cat !== "all" || mod !== "all" || status !== "all" || minConf > 0;

  return (
    <div className="mx-auto max-w-[1180px] px-5 pb-24 pt-8 sm:px-8">
      {/* framing */}
      <section className="case-in grid grid-cols-1 gap-8 border-b border-line pb-8 xl:grid-cols-[1fr_400px]">
        <div>
          <div className="eyebrow mb-3">The question framing this investigation</div>
          <p className="display text-[30px] font-[380] italic leading-[1.15] text-fg sm:text-[38px]">{inv.question}</p>
          <p className="mt-5 max-w-2xl text-[14.5px] leading-relaxed text-fg-dim">
            <span className="text-fg">{findings.length} findings</span> across {inv.sources.length} sources:{" "}
            <span className="text-fg">{contradictions}</span> contradiction{contradictions === 1 ? "" : "s"},{" "}
            <span className="text-fg">{assumptions}</span> assumption{assumptions === 1 ? "" : "s"} under question,{" "}
            <span className="text-fg">{dataIssues}</span> dataset issue{dataIssues === 1 ? "" : "s"}.{" "}
            <span className="mono text-[12.5px] text-muted">
              {verified}/{allCites.length} citations verified against extracted text · {reviewed} reviewed
            </span>
          </p>
          {inv.mode === "sample" && (
            <p className="mono mt-4 inline-block border border-amber/30 px-2 py-1 text-[11px] text-amber/90">
              Sample mode · curated findings on synthetic data · not live AI output
            </p>
          )}
          {findings[0] && (
            <button
              onClick={() => selectFinding(findings[0].id, { openCase: true })}
              className="group mt-6 flex w-full max-w-2xl cursor-pointer items-start gap-4 border-l-2 border-alert bg-panel/70 p-4 text-left hover:bg-panel"
            >
              <span className="mono pt-0.5 text-[11px] text-alert">TOP</span>
              <span className="min-w-0">
                <span className="block text-[11px] uppercase tracking-widest text-muted">Investigate first</span>
                <span className="display mt-0.5 block text-[18px] leading-snug text-fg">{findings[0].title}</span>
                <span className="mono mt-2 block text-[11px] text-cool group-hover:underline">open evidence view →</span>
              </span>
            </button>
          )}
        </div>
        <div>
          <div className="flex items-baseline justify-between">
            <div className="eyebrow">Impact × confidence</div>
            <span className="mono text-[10px] text-faint">click a point</span>
          </div>
          <Matrix findings={visible} selectedId={selectedId} onSelect={(id) => selectFinding(id, { openCase: true })} height={290} />
        </div>
      </section>

      {/* controls */}
      <section className="sticky top-0 z-10 -mx-5 flex flex-wrap items-center gap-x-5 gap-y-3 border-b border-line bg-canvas/95 px-5 py-3 backdrop-blur sm:-mx-8 sm:px-8">
        <fieldset className="flex items-center gap-1">
          <legend className="sr-only">Severity</legend>
          {SEVERITIES.map((s) => (
            <button
              key={s}
              aria-pressed={sev.has(s)}
              onClick={() => setSev((cur) => { const n = new Set(cur); if (n.has(s)) n.delete(s); else n.add(s); return n; })}
              className={cls("mono h-7 cursor-pointer border px-2 text-[10.5px] uppercase tracking-wider", sev.has(s) ? "border-amber text-amber" : "border-line text-muted hover:text-fg")}
            >
              {SEVERITY_LABEL[s]}
            </button>
          ))}
        </fieldset>
        <Select label="Category" value={cat} onChange={(v) => setCat(v as Category | "all")} options={[["all", "All categories"], ...categories.map((c) => [c, CATEGORY_LABEL[c]] as [string, string])]} />
        <Select label="Engine" value={mod} onChange={(v) => setMod(v as Module | "all")} options={[["all", "All engines"], ["radar", MODULE_LABEL.radar], ["contradiction", MODULE_LABEL.contradiction], ["dataset", MODULE_LABEL.dataset]]} />
        <Select label="Review" value={status} onChange={(v) => setStatus(v as Status | "all")} options={STATUSES.map((s) => [s, s === "all" ? "Any status" : STATUS_LABEL[s]])} />
        <label className="flex items-center gap-2 text-[12px] text-muted">
          <span className="mono text-[10.5px] uppercase tracking-wider">Conf ≥</span>
          <input type="range" min={0} max={90} step={5} value={minConf} onChange={(e) => setMinConf(+e.target.value)} className="w-20" aria-label="Minimum confidence" />
          <span className="mono w-5 text-[11px] text-fg-dim">{minConf}</span>
        </label>
        {filtersOn && (
          <Button size="sm" onClick={() => { setSev(new Set()); setCat("all"); setMod("all"); setStatus("all"); setMinConf(0); }}>
            Clear
          </Button>
        )}

      </section>

      {/* ranked list */}
      <section className="mt-6">
        <div className="mb-1 flex flex-wrap items-end justify-between gap-3">
          <h2 className="display text-[22px] text-fg">
            {visible.length === findings.length ? `${findings.length} findings` : `${visible.length} of ${findings.length} findings`}
            <span className="mono ml-3 text-[11px] text-muted">ranked by priority</span>
          </h2>
        <label className="flex items-center gap-2 text-[12px] text-muted" title="priority = w × impact + (1 − w) × confidence">
          <span className="mono text-[10.5px] uppercase tracking-wider">Rank by</span>
          <span className="mono text-[10.5px]">conf</span>
          <input
            type="range"
            min={0}
            max={1}
            step={0.05}
            value={wImpact}
            onChange={(e) => setWeight(+e.target.value)}
            onPointerUp={() => commitWeight()}
            onKeyUp={() => commitWeight()}
            className="w-24"
            aria-label="Ranking weight between confidence and impact"
          />
          <span className="mono text-[10.5px]">impact</span>
          <span className="mono w-16 text-[10.5px] text-fg-dim">{Math.round(wImpact * 100)}/{Math.round((1 - wImpact) * 100)}</span>
        </label>
        </div>
        <div className="mono grid grid-cols-[2.25rem_1fr] gap-4 px-2 py-2 text-[10.5px] uppercase tracking-widest text-faint md:grid-cols-[2.25rem_1fr_11rem_4rem]">
          <span>Rank</span>
          <span>Finding</span>
          <span className="hidden md:block">Impact · confidence</span>
          <span className="hidden text-right md:block">Priority</span>
        </div>
        {visible.length === 0 ? (
          <p className="border-t border-line py-10 text-center text-[13px] text-muted">No findings match these filters.</p>
        ) : (
          <ol ref={listRef} className="border-t border-line">
            {visible.map((f, i) => (
              <Row key={f.id} f={f} rank={findings.indexOf(f) + 1} selected={f.id === selectedId} onOpen={() => { setCursor(i); selectFinding(f.id, { openCase: true }); }} />
            ))}
          </ol>
        )}
        <p className="mono mt-4 text-[10.5px] leading-relaxed text-faint">
          Priority = {Math.round(wImpact * 100) / 100} × impact + {Math.round((1 - wImpact) * 100) / 100} × confidence. Impact weighs consequence, decision relevance and breadth; confidence weighs
          evidence strength, specificity and corroboration. Confidence is an evidence rating, not a probability.
        </p>
      </section>
    </div>
  );
}

function Row({ f, rank, selected, onOpen }: { f: Finding; rank: number; selected: boolean; onOpen: () => void }) {
  const sources = Array.from(new Set(f.citations.filter((c) => c.verified).map((c) => c.source_id)));
  const unverified = f.citations.filter((c) => !c.verified).length;
  return (
    <li className="border-b border-line">
      <button
        data-row
        onClick={onOpen}
        className={cls(
          "grid w-full cursor-pointer grid-cols-[2.25rem_1fr] gap-4 px-2 py-4 text-left transition-colors focus:bg-panel md:grid-cols-[2.25rem_1fr_11rem_4rem]",
          selected ? "bg-panel" : "hover:bg-panel/60",
          f.status !== "open" && "opacity-60",
        )}
      >
        <span className="mono pt-1 text-[12px] text-faint">{String(rank).padStart(2, "0")}</span>
        <span className="min-w-0">
          <span className="flex items-start gap-2.5">
            <span className="pt-[9px]">
              <SeverityMark f={f} />
            </span>
            <span className={cls("display text-[18px] leading-snug text-fg", f.status === "dismissed" && "line-through decoration-faint")}>{f.title}</span>
          </span>
          <span className="mt-2 flex flex-wrap items-center gap-1.5 pl-[18px]">
            <span className="mono text-[10.5px] text-amber">{f.id}</span>
            <Tag tone={f.category === "contradiction" ? "alert" : "default"}>{CATEGORY_LABEL[f.category]}</Tag>
            <Tag>{CLASS_LABEL[f.classification]}</Tag>
            {f.assumption_type && <Tag tone="cool">{f.assumption_type} assumption</Tag>}
            {f.contradiction && <Tag tone="alert">{f.contradiction.verdict.replace("_", " ")}</Tag>}
            <span className="mono ml-1 text-[10.5px] text-muted">{sources.join(" ")}</span>
            {unverified > 0 && <Tag tone="alert">{unverified} unverified</Tag>}
            {f.status !== "open" && <Tag tone={f.status === "dismissed" ? "default" : "ok"}>{STATUS_LABEL[f.status]}</Tag>}
          </span>
        </span>
        <span className="hidden flex-col justify-center gap-1.5 md:flex">
          <MiniBar v={f.impact} label="imp" color="var(--color-amber)" />
          <MiniBar v={f.confidence} label="conf" color="var(--color-cool)" />
        </span>
        <span className="mono hidden pt-1 text-right text-[18px] text-fg md:block">{f.priority.toFixed(0)}</span>
      </button>
    </li>
  );
}

function MiniBar({ v, label, color }: { v: number; label: string; color: string }) {
  return (
    <span className="flex items-center gap-2">
      <span className="mono w-7 text-[9.5px] uppercase text-faint">{label}</span>
      <span className="relative h-[3px] flex-1 bg-line">
        <span className="absolute inset-y-0 left-0" style={{ width: `${v}%`, background: color }} />
      </span>
      <span className="mono w-6 text-right text-[10.5px] text-fg-dim">{v}</span>
    </span>
  );
}

function Select({ label, value, onChange, options }: { label: string; value: string; onChange: (v: string) => void; options: [string, string][] }) {
  return (
    <label className="flex items-center gap-1.5">
      <span className="sr-only">{label}</span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="h-7 cursor-pointer border border-line bg-panel px-2 text-[12px] text-fg-dim outline-none hover:border-faint"
      >
        {options.map(([v, l]) => (
          <option key={v} value={v}>
            {l}
          </option>
        ))}
      </select>
    </label>
  );
}
