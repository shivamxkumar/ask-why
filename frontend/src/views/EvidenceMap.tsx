import { useMemo, useState } from "react";
import { summarize } from "../lib/graphSummary";
import { Constellation, GraphLegend } from "../components/Constellation";
import { cls, NODE_LABEL } from "../lib/format";
import { useStore } from "../store";
import type { NodeType } from "../types";

const TOGGLABLE: NodeType[] = ["source", "claim", "question", "action"];

export function EvidenceMap() {
  const { inv, findings, selection, selectFinding, selectNode } = useStore();
  const [hidden, setHidden] = useState<Set<NodeType>>(new Set());
  const [qa, setQa] = useState(false);
  const [detail, setDetail] = useState<"summary" | "evidence">("summary");
  const summary = useMemo(() => (inv ? summarize(inv.graph.nodes, inv.graph.edges, findings) : null), [inv, findings]);
  if (!inv || !summary) return null;
  const focusFinding = selection?.kind === "finding" ? selection.id : null;
  const selectedNode = selection?.kind === "node" ? selection.id : null;
  // a focused finding always expands to its cited passages; otherwise the chosen level applies
  const g = detail === "evidence" || focusFinding ? inv.graph : summary;
  const counts = inv.graph.nodes.reduce<Record<string, number>>((a, n) => ({ ...a, [n.type]: (a[n.type] || 0) + 1 }), {});
  const relCounts = inv.graph.edges.reduce<Record<string, number>>((a, e) => ({ ...a, [e.relation]: (a[e.relation] || 0) + 1 }), {});

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex flex-wrap items-end justify-between gap-4 border-b border-line px-5 py-4 sm:px-8">
        <div>
          <div className="eyebrow mb-1">Evidence constellation</div>
          <h2 className="display text-[24px] leading-tight text-fg">How the evidence connects</h2>
          <p className="mono mt-1 text-[11px] text-muted">
            {inv.graph.nodes.length} nodes · {inv.graph.edges.length} edges · {relCounts.contradicts || 0} contradicts · {relCounts.depends_on || 0} depends on ·{" "}
            {relCounts.requires_validation || 0} needs validation
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          <div className="mr-2 flex border border-line" role="group" aria-label="Detail level">
            {(["summary", "evidence"] as const).map((d) => (
              <button
                key={d}
                aria-pressed={detail === d}
                onClick={() => setDetail(d)}
                className={cls("mono h-7 cursor-pointer px-2.5 text-[11px] uppercase tracking-wider", detail === d ? "bg-raised text-amber" : "text-muted hover:text-fg")}
              >
                {d === "summary" ? "Sources → findings" : "All cited passages"}
              </button>
            ))}
          </div>
          {TOGGLABLE.filter((t) => t !== "claim" || detail === "evidence" || focusFinding).map((t) => {
            const on = t === "question" || t === "action" ? qa && !hidden.has(t) : !hidden.has(t);
            return (
              <button
                key={t}
                aria-pressed={on}
                onClick={() => {
                  if (t === "question" || t === "action") {
                    if (!qa) {
                      setQa(true);
                      setHidden((h) => { const n = new Set(h); n.delete("question"); n.delete("action"); return n; });
                    } else setHidden((h) => { const n = new Set(h); if (n.has(t)) n.delete(t); else n.add(t); return n; });
                  } else setHidden((h) => { const n = new Set(h); if (n.has(t)) n.delete(t); else n.add(t); return n; });
                }}
                className={cls("mono h-7 cursor-pointer border px-2 text-[10.5px] uppercase tracking-wider", on ? "border-faint text-fg" : "border-line text-faint line-through")}
              >
                {NODE_LABEL[t]} {counts[t] ?? 0}
              </button>
            );
          })}
          {(focusFinding || selectedNode) && (
            <button className="mono h-7 cursor-pointer border border-amber/50 px-2 text-[10.5px] uppercase tracking-wider text-amber" onClick={() => selectNode(null)}>
              clear focus
            </button>
          )}
        </div>
      </div>
      <div className="relative min-h-0 flex-1">
        <Constellation
          nodes={g.nodes}
          edges={g.edges}
          findings={findings}
          focusFinding={focusFinding}
          selectedNode={selectedNode}
          hidden={hidden}
          hideQA={!qa}
          isolate
          maxRows={detail === "summary" ? 5 : 14}
          onNodeClick={(n) => (n.id.startsWith("f:") ? selectFinding(n.id.slice(2)) : selectNode(n.id))}
        />
        <div className="pointer-events-none absolute left-4 top-3 flex gap-10 mono text-[10px] uppercase tracking-[0.16em] text-faint">
          <span>
            {g === summary ? "Sources → findings" : "Sources → cited passages → findings"}
            {qa ? " → questions → actions" : ""} · click a finding to trace its evidence
          </span>
        </div>
      </div>
      <div className="border-t border-line px-5 py-2.5 sm:px-8">
        <GraphLegend />
      </div>
    </div>
  );
}
