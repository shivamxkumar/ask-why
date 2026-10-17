import { CATEGORY_LABEL, CLASS_LABEL, cls, NODE_LABEL } from "../lib/format";
import { useStore } from "../store";
import type { Finding } from "../types";
import { FindingLinks, ReviewControls, ScoreBlock } from "./Review";
import { Button, CitationCard, SeverityMark, Tag } from "./ui";

export function Inspector() {
  const { inv, selection, selectFinding, selectNode } = useStore();
  if (!inv || !selection) return null;
  const close = () => (selection.kind === "finding" ? selectFinding(null) : selectNode(null));

  return (
    <aside
      aria-label="Inspector"
      className="no-print case-in fixed inset-y-0 right-0 z-30 flex w-full max-w-[400px] shrink-0 flex-col border-l border-line bg-panel shadow-2xl lg:static lg:z-auto lg:w-[380px] lg:shadow-none"
    >
      <div className="flex h-10 shrink-0 items-center justify-between border-b border-line px-4">
        <span className="eyebrow">Inspector</span>
        <button onClick={close} className="cursor-pointer px-1 text-[18px] leading-none text-muted hover:text-fg" aria-label="Close inspector (Esc)">
          ×
        </button>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto">
        {selection.kind === "finding" ? <FindingPanel id={selection.id} /> : <NodePanel id={selection.id} />}
      </div>
    </aside>
  );
}

function FindingPanel({ id }: { id: string }) {
  const { inv, findings, selectFinding, goSource } = useStore();
  const f = findings.find((x) => x.id === id);
  if (!inv || !f) return <p className="p-4 text-[13px] text-muted">This finding no longer exists.</p>;
  return (
    <div className="space-y-6 p-4">
      <div>
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="mono text-[11px] text-amber">{f.id}</span>
          <SeverityMark f={f} showLabel />
          <Tag>{CATEGORY_LABEL[f.category]}</Tag>
        </div>
        <h3 className="display mt-2 text-[19px] leading-snug text-fg">{f.title}</h3>
        <p className="mono mt-1 text-[11px] text-muted">
          {CLASS_LABEL[f.classification]}
          {f.assumption_type ? ` · ${f.assumption_type} assumption` : ""}
        </p>
        <Button tone="primary" size="sm" className="mt-3" onClick={() => selectFinding(f.id, { openCase: true })}>
          Open evidence view →
        </Button>
      </div>
      <ReviewControls f={f} />
      <ScoreBlock f={f} />
      <div>
        <div className="eyebrow mb-1.5">Why it matters</div>
        <p className="text-[13.5px] leading-relaxed text-fg-dim">{f.why_it_matters}</p>
      </div>
      <div>
        <div className="eyebrow mb-2">Evidence & exact excerpts</div>
        <div className="space-y-4">
          {f.citations.map((c, i) => (
            <CitationCard key={i} c={c} inv={inv} dense onOpen={(c) => goSource(c.source_id, c.unit_id!)} />
          ))}
          {f.citations.length === 0 && <p className="text-[12.5px] text-muted">No direct excerpt — inference only.</p>}
        </div>
        {f.inference_note && <p className="mt-3 border-l-2 border-cool/60 pl-2 text-[12px] text-fg-dim">Inference: {f.inference_note}</p>}
      </div>
      <FindingLinks f={f} onOpen={(x) => selectFinding(x)} />
      <div className="border-l-2 border-amber pl-3">
        <div className="eyebrow mb-1 !text-amber">Next action</div>
        <p className="text-[13.5px] leading-relaxed text-fg">{f.recommendation}</p>
        <div className="eyebrow mb-1 mt-3">Validation question</div>
        <p className="display text-[15px] italic leading-snug text-fg">{f.question}</p>
      </div>
    </div>
  );
}

function NodePanel({ id }: { id: string }) {
  const { inv, findings, selectFinding, goSource } = useStore();
  const n = inv?.graph.nodes.find((x) => x.id === id);
  if (!inv || !n) return <p className="p-4 text-[13px] text-muted">Node not found.</p>;
  const linked = n.finding_ids.map((fid) => findings.find((f) => f.id === fid)).filter((x): x is Finding => !!x);
  const edges = inv.graph.edges.filter((e) => e.source === id || e.target === id);
  const src = n.source_id ? inv.sources.find((s) => s.id === n.source_id) : undefined;
  const lead = linked[0];
  return (
    <div className="space-y-5 p-4">
      <div>
        <Tag tone={n.type === "risk" ? "alert" : n.type === "assumption" ? "amber" : "default"}>{NODE_LABEL[n.type]}</Tag>
        <h3 className={cls("mt-2 leading-snug text-fg", n.type === "claim" ? "display text-[17px] italic" : "display text-[18px]")}>{n.type === "claim" ? `“${n.label}”` : n.label}</h3>
        {src && (
          <p className="mono mt-1 text-[11px] text-muted">
            {src.id} · {src.name}
          </p>
        )}
      </div>
      {n.detail && n.detail !== n.label && (
        <div>
          <div className="eyebrow mb-1">{n.type === "claim" ? "Full passage" : "Detail"}</div>
          <p className="text-[13px] leading-relaxed text-fg-dim">{n.detail}</p>
        </div>
      )}
      {n.unit_id && n.source_id && (
        <Button tone="line" size="sm" onClick={() => goSource(n.source_id!, n.unit_id!)}>
          Open in source →
        </Button>
      )}
      {n.type === "source" && n.source_id && (
        <Button tone="line" size="sm" onClick={() => goSource(n.source_id!)}>
          Read source →
        </Button>
      )}
      <div>
        <div className="eyebrow mb-1">Relationships ({edges.length})</div>
        <ul className="mono space-y-0.5 text-[11px] text-muted">
          {edges.slice(0, 14).map((e) => {
            const other = inv.graph.nodes.find((x) => x.id === (e.source === id ? e.target : e.source));
            return (
              <li key={e.id} className="truncate">
                {e.source === id ? "→" : "←"} <span className="text-fg-dim">{e.relation.replace("_", " ")}</span> · {other ? `${NODE_LABEL[other.type]}: ${other.label}` : "?"}
              </li>
            );
          })}
        </ul>
      </div>
      {linked.length > 0 && (
        <div>
          <div className="eyebrow mb-1">Linked findings</div>
          <ul>
            {linked.map((x) => (
              <li key={x.id}>
                <button onClick={() => selectFinding(x.id, { openCase: true })} className="flex w-full cursor-pointer items-start gap-2 py-1 text-left text-[13px] leading-snug text-fg-dim hover:text-fg">
                  <span className="mono pt-px text-[11px] text-amber">{x.id}</span>
                  <span>{x.title}</span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
      {lead && (
        <div className="border-l-2 border-amber pl-3">
          <div className="eyebrow mb-1 !text-amber">Recommended action ({lead.id})</div>
          <p className="text-[13px] leading-relaxed text-fg">{lead.recommendation}</p>
        </div>
      )}
    </div>
  );
}
