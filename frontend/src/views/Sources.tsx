import { useEffect, useMemo, useRef, useState } from "react";
import { Highlighted, rowPairs } from "../components/Passage";
import { Tag } from "../components/ui";
import { cls, fmtBytes } from "../lib/format";
import { useStore } from "../store";
import type { Citation, DatasetProfile, EvidenceUnit, Finding, Source } from "../types";

export function Sources() {
  const { inv, findings, sourceFocus, selectFinding } = useStore();
  const [sid, setSid] = useState<string | null>(sourceFocus?.sourceId ?? inv?.sources[0]?.id ?? null);
  const [onlyCited, setOnlyCited] = useState(false);
  const scroller = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (sourceFocus?.sourceId) setSid(sourceFocus.sourceId);
  }, [sourceFocus]);

  // index: unit id -> citing findings + excerpts
  const cited = useMemo(() => {
    const m = new Map<string, { f: Finding; c: Citation }[]>();
    findings.forEach((f) => f.citations.forEach((c) => c.verified && c.unit_id && m.set(c.unit_id, [...(m.get(c.unit_id) || []), { f, c }])));
    return m;
  }, [findings]);

  useEffect(() => {
    if (!sourceFocus?.unitId) return;
    const t = window.setTimeout(() => {
      const el = document.getElementById(`unit-${sourceFocus.unitId}`);
      el?.scrollIntoView({ block: "center", behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
      el?.focus({ preventScroll: true });
    }, 80);
    return () => window.clearTimeout(t);
  }, [sourceFocus, sid]);

  if (!inv) return null;
  const src = inv.sources.find((s) => s.id === sid) ?? inv.sources[0];
  const units = inv.units.filter((u) => u.source_id === src?.id);
  const isTable = src && (src.kind === "csv" || src.kind === "xlsx");
  const shownUnits = units.filter((u) => u.kind !== "dataset_stat" && (!onlyCited || cited.has(u.id)));

  return (
    <div className="grid h-full min-h-0 grid-cols-1 md:grid-cols-[280px_1fr]">
      {/* registry */}
      <div className="min-h-0 overflow-y-auto border-b border-line md:border-b-0 md:border-r">
        <div className="px-5 pb-2 pt-5">
          <div className="eyebrow">Source registry</div>
          <p className="mono mt-1 text-[10.5px] text-faint">{inv.units.length} evidence units extracted</p>
        </div>
        <ul>
          {inv.sources.map((s) => {
            const n = findings.filter((f) => f.citations.some((c) => c.verified && c.source_id === s.id)).length;
            return (
              <li key={s.id}>
                <button
                  onClick={() => setSid(s.id)}
                  aria-current={s.id === src?.id}
                  className={cls("w-full cursor-pointer border-l-2 px-5 py-3 text-left", s.id === src?.id ? "border-amber bg-panel" : "border-transparent hover:bg-panel/60")}
                >
                  <div className="flex items-center gap-2">
                    <span className="mono text-[11px] text-amber">{s.id}</span>
                    <span className="mono text-[10px] uppercase text-faint">{s.kind}</span>
                    {s.synthetic && <Tag tone="amber">synthetic</Tag>}
                  </div>
                  <div className="mt-1 truncate text-[13.5px] text-fg" title={s.name}>
                    {s.name}
                  </div>
                  <div className="mono mt-0.5 text-[10.5px] text-muted">
                    {s.summary} · {fmtBytes(s.size_bytes)}
                  </div>
                  <div className="mono mt-0.5 text-[10.5px] text-faint">cited by {n} finding{n === 1 ? "" : "s"}</div>
                  {s.warnings.map((w) => (
                    <div key={w} className="mt-1 text-[11px] text-alert">
                      ⚠ {w}
                    </div>
                  ))}
                </button>
              </li>
            );
          })}
        </ul>
      </div>

      {/* reader */}
      <div ref={scroller} className="min-h-0 overflow-y-auto">
        {src && (
          <div className="mx-auto max-w-[920px] px-5 py-6 sm:px-8">
            <div className="flex flex-wrap items-end justify-between gap-3">
              <div>
                <div className="eyebrow mb-1">
                  {src.id} · {src.kind.toUpperCase()}
                  {src.page_count ? ` · ${src.page_count} pages` : ""}
                  {src.sheet_names.length ? ` · sheets: ${src.sheet_names.join(", ")}` : ""}
                </div>
                <h2 className="display text-[24px] leading-tight text-fg">{src.name}</h2>
              </div>
              <label className="mono flex items-center gap-2 text-[11px] text-muted">
                <input type="checkbox" checked={onlyCited} onChange={(e) => setOnlyCited(e.target.checked)} className="accent-[#f5a623]" />
                cited passages only
              </label>
            </div>

            {isTable && src.profiles.map((p) => <ProfileTable key={p.sheet ?? "csv"} p={p} src={src} units={units} cited={cited} focusUnit={sourceFocus?.unitId} onOpen={(id) => selectFinding(id, { openCase: true })} />)}

            <div className="paper mt-5 shadow-[0_24px_60px_-30px_rgba(0,0,0,0.8)]">
              <div className="mono flex justify-between border-b border-paper-line px-5 py-2 text-[10.5px] text-paper-muted">
                <span>{isTable ? "Rows (each row is an addressable evidence unit)" : "Extracted text, as parsed"}</span>
                <span>{shownUnits.length} units</span>
              </div>
              <div className="divide-y divide-paper-line/60">
                {shownUnits.length === 0 && <p className="px-5 py-6 text-[13px] text-paper-muted">No units to show.</p>}
                {shownUnits.slice(0, 600).map((u) => (
                  <UnitRow key={u.id} u={u} hits={cited.get(u.id) || []} focused={sourceFocus?.unitId === u.id} onOpen={(id) => selectFinding(id, { openCase: true })} />
                ))}
                {shownUnits.length > 600 && <p className="mono px-5 py-3 text-[11px] text-paper-muted">Showing first 600 of {shownUnits.length} units.</p>}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function UnitRow({ u, hits, focused, onOpen }: { u: EvidenceUnit; hits: { f: Finding; c: Citation }[]; focused: boolean; onOpen: (id: string) => void }) {
  const ids = Array.from(new Set(hits.map((h) => h.f.id)));
  return (
    <div
      id={`unit-${u.id}`}
      tabIndex={-1}
      className={cls("grid grid-cols-[5.5rem_1fr] gap-3 px-5 py-2.5 outline-none", focused && "bg-[#f5a6231f] ring-1 ring-inset ring-[#d48b0f]", hits.length > 0 && "sweep")}
    >
      <span className="mono pt-0.5 text-right text-[10px] leading-tight text-paper-muted">
        {u.label}
        {u.location.page ? <span className="block text-[9px]">page {u.location.page}</span> : null}
      </span>
      <div className="min-w-0">
        {u.kind === "table_row" ? (
          <div className="mono flex flex-wrap gap-x-3 gap-y-0.5 text-[11.5px] text-paper-ink">
            {rowPairs(u.text).map(([k, v]) => (
              <span key={k}>
                <span className="text-paper-muted">{k}:</span> {v || <span className="text-[#b13a2c]">∅</span>}
              </span>
            ))}
          </div>
        ) : (
          <p className={cls("leading-relaxed text-paper-ink", u.kind === "heading" ? "display text-[18px] font-semibold" : "text-[14.5px]")}>
            {hits.length ? <Highlighted text={u.text} excerpts={hits.map((h) => h.c.excerpt)} /> : u.text}
          </p>
        )}
        {ids.length > 0 && (
          <div className="mt-1.5 flex flex-wrap gap-1">
            {ids.map((id) => (
              <button key={id} onClick={() => onOpen(id)} className="mono cursor-pointer border border-[#d48b0f] px-1.5 text-[10px] text-[#8a5a08] hover:bg-[#f5a62330]">
                {id} ↗
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function ProfileTable({
  p,
  src,
  units,
  cited,
  onOpen,
  focusUnit,
}: {
  focusUnit?: string;
  p: DatasetProfile;
  src: Source;
  units: EvidenceUnit[];
  cited: Map<string, { f: Finding; c: Citation }[]>;
  onOpen: (id: string) => void;
}) {
  const statUnits = units.filter((u) => u.kind === "dataset_stat" && (p.sheet ? u.label.startsWith(p.sheet) || u.location.sheet === p.sheet : true));
  return (
    <div className="mt-5 border border-line">
      <div className="flex flex-wrap items-baseline justify-between gap-2 border-b border-line bg-panel px-4 py-2">
        <span className="eyebrow">Dataset profile{p.sheet ? ` · ${p.sheet}` : ""}</span>
        <span className="mono text-[11px] text-muted">
          {p.rows} rows × {p.columns} columns · <span className={p.duplicate_rows.length ? "text-alert" : ""}>{p.duplicate_rows.length} duplicate rows</span>
        </span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-[12px]">
          <thead>
            <tr className="mono text-left text-[9.5px] uppercase tracking-widest text-faint">
              {["Column", "Type", "Missing", "Unique", "Range / top values", "Flags"].map((h) => (
                <th key={h} className="px-3 py-1.5 font-normal">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {p.column_profiles.map((c) => {
              const flags: string[] = [];
              if (c.missing) flags.push(`${c.missing} missing`);
              if (c.outlier_rows.length) flags.push(`${c.outlier_rows.length} outliers`);
              if (c.category_variants.length) flags.push(`${c.category_variants.length} label conflicts`);
              const range = c.stats
                ? `${fmt(c.stats.min)} – ${fmt(c.stats.max)} · median ${fmt(c.stats.median)}`
                : c.top_values.slice(0, 3).map(([v, n]) => `${v} (${n})`).join(", ");
              return (
                <tr key={c.name} className="border-t border-line-soft align-top">
                  <td className="mono px-3 py-1.5 text-fg">{c.name}</td>
                  <td className="mono px-3 py-1.5 text-muted">{c.dtype}</td>
                  <td className={cls("mono px-3 py-1.5", c.missing ? "text-alert" : "text-muted")}>{c.missing ? `${c.missing} (${c.missing_pct.toFixed(1)}%)` : "0"}</td>
                  <td className="mono px-3 py-1.5 text-muted">{c.unique}</td>
                  <td className="px-3 py-1.5 text-fg-dim">
                    {range}
                    {c.category_variants.map((g) => (
                      <div key={g.join()} className="mono text-[10.5px] text-amber">
                        ≈ {g.join(" / ")}
                      </div>
                    ))}
                  </td>
                  <td className="mono px-3 py-1.5 text-[10.5px] text-amber">{flags.join(" · ")}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {statUnits.length > 0 && (
        <details className="border-t border-line px-4 py-2" open={statUnits.some((u) => u.id === focusUnit) || undefined}>
          <summary className="mono cursor-pointer text-[10.5px] uppercase tracking-wider text-muted">Profile statements ({statUnits.length}) — citable evidence units</summary>
          <ul className="mt-2 space-y-1.5">
            {statUnits.map((u) => (
              <li key={u.id} id={`unit-${u.id}`} tabIndex={-1} className={cls("text-[12px] leading-relaxed text-fg-dim outline-none", u.id === focusUnit && "bg-amber-soft text-fg")}>
                <span className="mono mr-2 text-[10px] text-faint">{u.label}</span>
                {u.text}
                {(cited.get(u.id) || []).map((h) => (
                  <button key={h.f.id} onClick={() => onOpen(h.f.id)} className="mono ml-2 cursor-pointer text-[10px] text-amber hover:underline">
                    {h.f.id} ↗
                  </button>
                ))}
              </li>
            ))}
          </ul>
        </details>
      )}
      <p className="mono border-t border-line px-4 py-1.5 text-[10px] text-faint">Profile computed deterministically from {src.name}; no sampling.</p>
    </div>
  );
}

function fmt(n: number | undefined) {
  if (n === undefined || n === null || Number.isNaN(n)) return "—";
  return Math.abs(n) >= 1000 ? Math.round(n).toLocaleString("en-US") : (Math.round(n * 100) / 100).toString();
}
