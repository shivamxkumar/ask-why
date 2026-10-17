import { Fragment } from "react";
import { cls } from "../lib/format";
import type { Citation, EvidenceUnit, Investigation } from "../types";

function escapeRe(s: string) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

/** Locate an excerpt in text tolerant to whitespace / case / quote differences (mirrors backend normalisation). */
export function locate(text: string, excerpt: string): [number, number] | null {
  const i = text.indexOf(excerpt);
  if (i >= 0) return [i, i + excerpt.length];
  const words = excerpt
    .replace(/[‘’]/g, "'")
    .replace(/[“”]/g, '"')
    .split(/\s+/)
    .filter(Boolean)
    .map((w) => escapeRe(w).replace(/'/g, "['‘’]").replace(/"/g, '["“”]').replace(/-/g, "[-–—]"));
  if (!words.length) return null;
  const m = new RegExp(words.join("\\s+"), "i").exec(text);
  return m ? [m.index, m.index + m[0].length] : null;
}

export function Highlighted({ text, excerpts }: { text: string; excerpts: string[] }) {
  const ranges = excerpts
    .map((e) => locate(text, e))
    .filter((r): r is [number, number] => !!r)
    .sort((a, b) => a[0] - b[0]);
  const merged: [number, number][] = [];
  for (const r of ranges) {
    const last = merged[merged.length - 1];
    if (last && r[0] <= last[1]) last[1] = Math.max(last[1], r[1]);
    else merged.push([...r]);
  }
  const parts: { t: string; hit: boolean }[] = [];
  let p = 0;
  for (const [a, b] of merged) {
    if (a > p) parts.push({ t: text.slice(p, a), hit: false });
    parts.push({ t: text.slice(a, b), hit: true });
    p = b;
  }
  if (p < text.length) parts.push({ t: text.slice(p), hit: false });
  return (
    <>
      {parts.map((x, i) =>
        x.hit ? (
          <mark key={i} className="evidence">
            {x.t}
          </mark>
        ) : (
          <Fragment key={i}>{x.t}</Fragment>
        ),
      )}
    </>
  );
}

/** Row text "col: value | col: value" → pairs, for table-like rendering. */
export function rowPairs(text: string): [string, string][] {
  return text.split(" | ").map((p) => {
    const i = p.indexOf(": ");
    return i < 0 ? [p, ""] : [p.slice(0, i), p.slice(i + 2)];
  });
}

/** A cited passage on a paper surface, with one unit of context either side. */
export function SourcePassage({ inv, citation, context = 1, className }: { inv: Investigation; citation: Citation; context?: number; className?: string }) {
  const src = inv.sources.find((s) => s.id === citation.source_id);
  const units = inv.units.filter((u) => u.source_id === citation.source_id);
  const idx = units.findIndex((u) => u.id === citation.unit_id);
  const unit = idx >= 0 ? units[idx] : undefined;
  const around: EvidenceUnit[] = unit && unit.kind !== "dataset_stat" ? units.slice(Math.max(0, idx - context), idx + context + 1).filter((u) => u.kind !== "dataset_stat") : unit ? [unit] : [];

  return (
    <div className={cls("paper sweep relative", className)}>
      <div className="flex items-center justify-between border-b border-paper-line px-5 py-2">
        <span className="mono truncate text-[11px] text-paper-muted">
          <span className="font-semibold text-paper-ink">{citation.source_id}</span> · {src?.name}
        </span>
        <span className="mono shrink-0 text-[11px] text-paper-muted">{citation.location_label || "—"}</span>
      </div>
      <div className="px-5 py-4">
        {!citation.verified || !unit ? (
          <div>
            <p className="display text-[15px] italic leading-relaxed text-paper-ink/70">“{citation.excerpt}”</p>
            <p className="mono mt-3 border-l-2 border-[#b13a2c] pl-2 text-[11px] text-[#8a2a20]">
              Not found in the extracted text of this source. Shown for transparency only — not evidence.
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {around.map((u) => {
              const isHit = u.id === unit.id;
              return (
                <div key={u.id} className={cls("grid grid-cols-[4.5rem_1fr] gap-3", !isHit && "opacity-45")}>
                  <span className="mono pt-1 text-right text-[10px] leading-tight text-paper-muted">{u.label}</span>
                  {u.kind === "table_row" ? (
                    <table className="w-full border-collapse text-[12.5px]">
                      <tbody>
                        {rowPairs(u.text).map(([k, v]) => {
                          const hit = isHit && citation.excerpt !== u.text && locate(`${k}: ${v}`, citation.excerpt) !== null;
                          const fullHit = isHit && citation.excerpt === u.text;
                          return (
                            <tr key={k} className="border-b border-paper-line/70">
                              <td className="mono w-[42%] py-0.5 pr-2 text-[11px] text-paper-muted">{k}</td>
                              <td className={cls("mono py-0.5 text-[11.5px] text-paper-ink", (hit || fullHit) && "bg-[#f5a62340]")}>{v || <span className="text-[#b13a2c]">∅ missing</span>}</td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  ) : (
                    <p className={cls("leading-relaxed text-paper-ink", u.kind === "heading" ? "display text-[17px] font-semibold" : u.kind === "dataset_stat" ? "mono text-[12px]" : "text-[14.5px]")}>
                      {isHit ? <Highlighted text={u.text} excerpts={[citation.excerpt]} /> : u.text}
                    </p>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
      {citation.verified && (
        <div className="mono border-t border-paper-line px-5 py-1.5 text-[10px] uppercase tracking-wider text-paper-muted">
          ✓ excerpt {citation.match === "exact" ? "found verbatim" : "found after normalisation"} in extracted text · unit {citation.unit_id}
        </div>
      )}
    </div>
  );
}
