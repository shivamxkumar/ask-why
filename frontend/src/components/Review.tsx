import { useEffect, useState } from "react";
import { cls, STATUS_LABEL } from "../lib/format";
import { useStore } from "../store";
import type { Finding, Status } from "../types";
import { Button, Meter } from "./ui";

/** Validate / resolve / dismiss + reviewer note. Shared by the evidence view and the inspector. */
export function ReviewControls({ f }: { f: Finding }) {
  const { updateFinding } = useStore();
  const [note, setNote] = useState(f.reviewer_note ?? "");
  useEffect(() => setNote(f.reviewer_note ?? ""), [f.id, f.reviewer_note]);
  const setStatus = (s: Status) => updateFinding(f.id, { status: s });

  return (
    <div>
      <div className="mb-2 flex items-center justify-between">
        <span className="eyebrow">Review</span>
        <span
          className={cls(
            "mono inline-flex items-center gap-1.5 text-[11px]",
            f.status === "open" ? "text-amber" : f.status === "dismissed" ? "text-muted" : "text-ok",
          )}
        >
          <span className="h-1.5 w-1.5 rounded-full bg-current" />
          {STATUS_LABEL[f.status]}
        </span>
      </div>
      <div className="grid grid-cols-3 gap-1.5">
        {f.status === "open" ? (
          <>
            <Button size="sm" tone="line" onClick={() => setStatus("validated")} title="Confirmed: the issue is real">
              ✓ Validate
            </Button>
            <Button size="sm" tone="line" onClick={() => setStatus("resolved")} title="The issue has been addressed">
              ◆ Resolve
            </Button>
            <Button size="sm" tone="line" onClick={() => setStatus("dismissed")} title="Not a real issue">
              ✕ Dismiss
            </Button>
          </>
        ) : (
          <>
            {f.status === "validated" && (
              <Button size="sm" tone="line" onClick={() => setStatus("resolved")} className="col-span-2">
                ◆ Mark resolved
              </Button>
            )}
            <Button size="sm" tone="ghost" onClick={() => setStatus("open")} className={f.status === "validated" ? "" : "col-span-3"}>
              ↺ Reopen
            </Button>
          </>
        )}
      </div>
      <textarea
        value={note}
        onChange={(e) => setNote(e.target.value)}
        onBlur={() => note !== (f.reviewer_note ?? "") && updateFinding(f.id, { reviewer_note: note })}
        placeholder="Reviewer note — saved when you leave the field"
        rows={2}
        aria-label="Reviewer note"
        className="mt-2 w-full resize-none border border-line bg-canvas px-2 py-1.5 text-[12.5px] text-fg outline-none placeholder:text-faint focus:border-faint"
      />
    </div>
  );
}

/** Impact / confidence / priority with the factor breakdown and an impact override. */
export function ScoreBlock({ f, defaultOpen = false }: { f: Finding; defaultOpen?: boolean }) {
  const { updateFinding } = useStore();
  const [override, setOverride] = useState(f.impact);
  const [open, setOpen] = useState(defaultOpen);
  useEffect(() => setOverride(f.impact), [f.id, f.impact]);

  return (
    <div>
      <div className="grid grid-cols-3 gap-2 border-y border-line py-3">
        <Score label="Impact" v={f.impact} />
        <Score label="Confidence" v={f.confidence} />
        <Score label="Priority" v={f.priority} amber />
      </div>
      <button className="mono mt-2 cursor-pointer text-[11px] text-cool hover:underline" onClick={() => setOpen((v) => !v)} aria-expanded={open}>
        {open ? "− hide score breakdown" : "+ why this score?"}
      </button>
      {open && (
        <div className="mt-3 space-y-1.5">
          <Meter label="Consequence" value={f.impact_factors.consequence} />
          <Meter label="Decision rel." value={f.impact_factors.decision_relevance} />
          <Meter label="Breadth" value={f.impact_factors.breadth} />
          <Meter label="Evidence" value={f.confidence_factors.evidence_strength} tone="cool" />
          <Meter label="Specificity" value={f.confidence_factors.specificity} tone="cool" />
          <Meter label="Corroboration" value={f.confidence_factors.corroboration} tone="cool" />
          <ul className="mono space-y-1 pt-2 text-[10.5px] leading-relaxed text-muted">
            {f.score_notes.map((n) => (
              <li key={n}>· {n}</li>
            ))}
          </ul>
          <div className="flex items-center gap-2 pt-2">
            <label className="mono shrink-0 text-[10.5px] text-muted" htmlFor={`ovr-${f.id}`}>
              Adjust impact
            </label>
            <input id={`ovr-${f.id}`} type="range" min={0} max={100} value={override} onChange={(e) => setOverride(+e.target.value)} className="min-w-0 flex-1" />
            <span className="mono w-6 text-[11px] text-fg-dim">{override}</span>
            <Button size="sm" tone="line" disabled={override === f.impact} onClick={() => updateFinding(f.id, { impact_override: override })}>
              Set
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

function Score({ label, v, amber }: { label: string; v: number; amber?: boolean }) {
  return (
    <div>
      <div className="mono text-[10px] uppercase tracking-widest text-faint">{label}</div>
      <div className={cls("mono text-[26px] leading-tight", amber ? "text-amber" : "text-fg")}>{Math.round(v)}</div>
    </div>
  );
}

export function FindingLinks({ f, onOpen }: { f: Finding; onOpen: (id: string) => void }) {
  const { findings } = useStore();
  const byId = (x: string) => findings.find((y) => y.id === x.replace(/^f:/, ""));
  const deps = f.depends_on.map(byId).filter((x): x is Finding => !!x);
  const dependents = findings.filter((x) => x.depends_on.some((d) => d.replace(/^f:/, "") === f.id));
  const related = f.related.map(byId).filter((x): x is Finding => !!x && !deps.includes(x) && !dependents.includes(x));
  if (!deps.length && !dependents.length && !related.length) return null;
  return (
    <div className="space-y-4">
      {deps.length > 0 && <LinkList title="Rests on assumption" items={deps} onOpen={onOpen} tone="amber" />}
      {dependents.length > 0 && <LinkList title="Findings that depend on this" items={dependents} onOpen={onOpen} />}
      {related.length > 0 && <LinkList title="Related findings" items={related} onOpen={onOpen} />}
    </div>
  );
}

function LinkList({ title, items, onOpen, tone }: { title: string; items: Finding[]; onOpen: (id: string) => void; tone?: "amber" }) {
  return (
    <div>
      <div className={cls("eyebrow mb-1", tone === "amber" && "!text-amber")}>{title}</div>
      <ul>
        {items.map((x) => (
          <li key={x.id}>
            <button onClick={() => onOpen(x.id)} className="group flex w-full cursor-pointer items-start gap-2 py-1 text-left text-[13px] leading-snug text-fg-dim hover:text-fg">
              <span className="mono pt-px text-[11px] text-amber">{x.id}</span>
              <span className="group-hover:underline group-hover:decoration-faint group-hover:underline-offset-2">{x.title}</span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
