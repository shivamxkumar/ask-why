import { Background, Controls, Handle, Position, ReactFlow, ReactFlowProvider, useReactFlow, useStore as useFlowStore, type Edge, type Node, type NodeProps } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { memo, useEffect, useMemo } from "react";
import { cls, NODE_LABEL, RELATION_LABEL } from "../lib/format";
import { PALETTE, useTheme } from "../lib/theme";
import type { Finding, GraphEdge, GraphNode, NodeType } from "../types";

const COL_W = 262;
const NODE_W = 220;

const tint = (c: string, pct: number) => `color-mix(in srgb, ${c} ${pct}%, var(--color-panel))`;

// colours are CSS variables so nodes and edges follow the light / dark theme
const TYPE_STYLE: Record<NodeType, { border: string; label: string; bg: string; text: string }> = {
  source: { border: "var(--color-paper-line)", label: "var(--color-paper-muted)", bg: "var(--color-paper)", text: "var(--color-paper-ink)" },
  claim: { border: "var(--color-line)", label: "var(--color-muted)", bg: "var(--color-panel)", text: "var(--color-fg)" },
  assumption: { border: "var(--color-amber)", label: "var(--color-amber)", bg: tint("var(--color-amber)", 9), text: "var(--color-fg)" },
  constraint: { border: "var(--color-cool)", label: "var(--color-cool)", bg: tint("var(--color-cool)", 8), text: "var(--color-fg)" },
  risk: { border: "var(--color-alert)", label: "var(--color-alert)", bg: tint("var(--color-alert)", 8), text: "var(--color-fg)" },
  question: { border: "var(--color-gold)", label: "var(--color-gold)", bg: "var(--color-panel)", text: "var(--color-fg)" },
  action: { border: "var(--color-ok)", label: "var(--color-ok)", bg: tint("var(--color-ok)", 8), text: "var(--color-fg)" },
};

const QUIET = new Set<GraphEdge["relation"]>(["raises", "addresses", "cites"]);
const EDGE_COLOR: Record<GraphEdge["relation"], string> = {
  supports: "var(--color-faint)",
  contradicts: "var(--color-alert)",
  depends_on: "var(--color-amber)",
  requires_validation: "var(--color-cool)",
  raises: "var(--color-line)",
  addresses: "var(--color-line)",
  cites: "var(--color-line-soft)",
};

type NData = { node: GraphNode; dim: boolean; hot: boolean; findingId?: string };

const EvidenceNode = memo(function EvidenceNode({ data }: NodeProps<Node<NData>>) {
  const { node, dim, hot } = data;
  const st = TYPE_STYLE[node.type];
  const isClaim = node.type === "claim";
  return (
    <div
      className={cls("relative px-2.5 py-2 transition-[opacity,box-shadow] duration-300", hot && "pulse")}
      style={{
        width: NODE_W,
        background: st.bg,
        border: `1px ${node.type === "question" ? "dashed" : "solid"} ${st.border}`,
        borderLeftWidth: node.type === "source" || isClaim ? 1 : 3,
        opacity: dim ? 0.13 : 1,
        boxShadow: hot ? `0 0 0 1px ${st.border}, 0 0 28px -6px ${st.border}` : undefined,
      }}
    >
      <Handle type="target" position={Position.Left} className="!h-1.5 !w-1.5 !min-w-0 !border-0" style={{ background: st.border }} />
      <div className="mono flex items-center justify-between text-[9px] uppercase tracking-[0.14em]" style={{ color: st.label }}>
        <span>{NODE_LABEL[node.type]}</span>
        <span>{node.type === "source" ? node.source_id : node.finding_ids.length > 1 ? `${node.finding_ids.length} findings` : node.finding_ids[0]}</span>
      </div>
      <div
        className={cls("mt-1 line-clamp-3 text-[11.5px] leading-snug", isClaim && "display italic text-[12px]", node.type === "source" && "mono text-[11px]")}
        style={{ color: st.text }}
      >
        {node.label}
      </div>
      <Handle type="source" position={Position.Right} className="!h-1.5 !w-1.5 !min-w-0 !border-0" style={{ background: st.border }} />
    </div>
  );
});

const nodeTypes = { evidence: EvidenceNode };

function column(id: string): number {
  if (id.startsWith("src:")) return 0;
  if (id.startsWith("unit:")) return 1;
  if (id.startsWith("f:")) return 2;
  if (id.startsWith("q:")) return 3;
  return 4;
}

/** Deterministic column layout: sources → cited claims → findings → questions → actions, ordered by finding rank. */
function layout(nodes: GraphNode[], edges: GraphEdge[], rank: Map<string, number>, maxRows = 14) {
  const cols: GraphNode[][] = [[], [], [], [], []];
  nodes.forEach((n) => cols[column(n.id)].push(n));
  const fr = (n: GraphNode) => Math.min(...n.finding_ids.map((f) => rank.get(f) ?? 999));
  cols[2].sort((a, b) => fr(a) - fr(b));
  cols[3].sort((a, b) => fr(a) - fr(b));
  cols[4].sort((a, b) => fr(a) - fr(b));
  const pos2 = new Map(cols[2].map((n, i) => [n.id, i]));
  const adj = new Map<string, string[]>();
  edges.forEach((e) => {
    adj.set(e.source, [...(adj.get(e.source) || []), e.target]);
    adj.set(e.target, [...(adj.get(e.target) || []), e.source]);
  });
  const bary = (n: GraphNode, ref: Map<string, number>) => {
    const ps = (adj.get(n.id) || []).map((x) => ref.get(x)).filter((x): x is number => x !== undefined);
    return ps.length ? ps.reduce((a, b) => a + b, 0) / ps.length : 999;
  };
  cols[1].sort((a, b) => bary(a, pos2) - bary(b, pos2));
  const pos1 = new Map(cols[1].map((n, i) => [n.id, i]));
  cols[0].sort((a, b) => bary(a, pos1) - bary(b, pos1));
  // wrap very tall columns into sub-columns so the map keeps a readable aspect ratio
  const MAX_ROWS = maxRows;
  const split = cols.map((c) => Math.max(1, Math.ceil(c.length / MAX_ROWS)));
  const rows = cols.map((c, i) => Math.ceil(c.length / split[i]));
  const tallest = Math.max(...rows, 1);
  const H = tallest * 86;
  const out = new Map<string, { x: number; y: number }>();
  let x = 0;
  cols.forEach((c, ci) => {
    if (!c.length) return; // empty columns take no width
    const per = rows[ci] || 1;
    for (let k = 0; k < split[ci]; k++) {
      const chunk = c.slice(k * per, (k + 1) * per);
      const gap = H / Math.max(chunk.length, 1);
      chunk.forEach((n, i) => out.set(n.id, { x: x + k * (COL_W - 20), y: (i + 0.5) * gap + (k % 2) * 18 }));
    }
    x += split[ci] * (COL_W - 20) + 110;
  });
  return out;
}

export function neighbourhood(findingId: string, nodes: GraphNode[], edges: GraphEdge[]): Set<string> {
  const set = new Set(nodes.filter((n) => n.finding_ids.includes(findingId)).map((n) => n.id));
  edges.forEach((e) => {
    if (e.relation === "depends_on" && (e.source === `f:${findingId}` || e.target === `f:${findingId}`)) {
      set.add(e.source);
      set.add(e.target);
    }
  });
  return set;
}

interface Props {
  nodes: GraphNode[];
  edges: GraphEdge[];
  findings: Finding[];
  focusFinding?: string | null;
  selectedNode?: string | null;
  hidden?: Set<NodeType>;
  hideQA?: boolean;
  onNodeClick?: (n: GraphNode) => void;
  compact?: boolean;
  /** show only the focused finding's neighbourhood */
  isolate?: boolean;
  /** rows per column before wrapping into sub-columns */
  maxRows?: number;
}

function Inner({ nodes, edges, findings, focusFinding, selectedNode, hidden, hideQA, onNodeClick, compact, isolate, maxRows }: Props) {
  const rf = useReactFlow();
  const [theme] = useTheme();
  const reduced = typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const rank = useMemo(() => new Map(findings.map((f, i) => [f.id, i])), [findings]);

  const subgraph = useMemo(() => ((compact || isolate) && focusFinding ? neighbourhood(focusFinding, nodes, edges) : null), [compact, isolate, focusFinding, nodes, edges]);
  const shown = useMemo(
    () =>
      nodes.filter((n) => {
        if (subgraph) return subgraph.has(n.id) && !(isolate && hideQA && (n.id.startsWith("q:") || n.id.startsWith("a:")));
        if (hidden?.has(n.type) && !n.id.startsWith("f:")) return false;
        if (hideQA && (n.id.startsWith("q:") || n.id.startsWith("a:")) && !(focusFinding && n.finding_ids.includes(focusFinding))) return false;
        return true;
      }),
    [nodes, hidden, hideQA, focusFinding, subgraph, isolate],
  );
  const shownIds = useMemo(() => new Set(shown.map((n) => n.id)), [shown]);
  const shownEdges = useMemo(() => edges.filter((e) => shownIds.has(e.source) && shownIds.has(e.target)), [edges, shownIds]);
  const positions = useMemo(() => layout(shown, shownEdges, rank, subgraph ? 14 : maxRows), [shown, shownEdges, rank, maxRows, subgraph]);

  const focus = useMemo(() => {
    if (focusFinding && (compact || isolate)) return null; // subgraph already isolated
    if (focusFinding) return neighbourhood(focusFinding, nodes, edges);
    if (selectedNode) {
      const s = new Set([selectedNode]);
      edges.forEach((e) => {
        if (e.source === selectedNode) s.add(e.target);
        if (e.target === selectedNode) s.add(e.source);
      });
      return s;
    }
    return null;
  }, [focusFinding, selectedNode, nodes, edges, compact, isolate]);

  const rfNodes: Node<NData>[] = useMemo(
    () =>
      shown.map((n) => ({
        id: n.id,
        type: "evidence",
        position: positions.get(n.id) || { x: 0, y: 0 },
        data: { node: n, dim: !!focus && !focus.has(n.id), hot: n.id === `f:${focusFinding}` || n.id === selectedNode },
        draggable: false,
        connectable: false,
        ariaLabel: `${NODE_LABEL[n.type]}: ${n.label}`,
      })),
    [shown, positions, focus, focusFinding, selectedNode],
  );

  const rfEdges: Edge[] = useMemo(
    () =>
      shownEdges.map((e) => {
        const on = !focus || (focus.has(e.source) && focus.has(e.target));
        const lit = !!focus || !!subgraph;
        const color = EDGE_COLOR[e.relation];
        return {
          id: e.id,
          source: e.source,
          target: e.target,
          type: e.relation === "contradicts" || e.relation === "depends_on" ? "default" : "smoothstep",
          animated: lit && on && (e.relation === "contradicts" || e.relation === "depends_on") && !reduced,
          label: lit && on && e.relation !== "cites" ? RELATION_LABEL[e.relation] : undefined,
          labelStyle: { fill: QUIET.has(e.relation) ? "var(--color-muted)" : color, fontSize: 9.5, fontFamily: "JetBrains Mono" },
          labelBgStyle: { fill: "var(--color-canvas)" },
          labelBgPadding: [3, 1] as [number, number],
          style: {
            stroke: on && lit ? (QUIET.has(e.relation) ? "var(--color-faint)" : color) : color,
            strokeWidth: on && lit ? 1.6 : 1,
            strokeDasharray: e.relation === "contradicts" || e.relation === "requires_validation" ? "5 4" : undefined,
            opacity: on ? 1 : 0.06,
          },
        };
      }),
    [shownEdges, focus, subgraph, reduced],
  );

  // the signature move: glide the camera onto the selected finding's evidence
  const flowW = useFlowStore((st) => st.width);
  const flowH = useFlowStore((st) => st.height);
  useEffect(() => {
    const ids = focus ? Array.from(focus).filter((id) => shownIds.has(id)) : null;
    const t = window.setTimeout(() => {
      rf.fitView({ nodes: ids && ids.length ? ids.map((id) => ({ id })) : undefined, padding: compact ? 0.12 : 0.14, duration: reduced ? 0 : 650, maxZoom: 1.1 });
    }, 280);
    return () => window.clearTimeout(t);
  }, [focus, shownIds, rf, reduced, compact, flowW, flowH, subgraph]);

  return (
    <ReactFlow
      nodes={rfNodes}
      edges={rfEdges}
      nodeTypes={nodeTypes}
      onNodeClick={(_, n) => onNodeClick?.((n.data as NData).node)}
      nodesDraggable={false}
      nodesConnectable={false}
      elementsSelectable
      minZoom={0.15}
      maxZoom={1.8}
      proOptions={{ hideAttribution: false }}
      fitView={!focus}
    >
      <Background color={PALETTE[theme].dots} gap={28} size={1} />
      {!compact && <Controls showInteractive={false} position="bottom-right" />}
    </ReactFlow>
  );
}

export function Constellation(props: Props) {
  return (
    <ReactFlowProvider>
      <Inner {...props} />
    </ReactFlowProvider>
  );
}

export function GraphLegend() {
  return (
    <div className="mono flex flex-wrap items-center gap-x-4 gap-y-1.5 text-[10px] uppercase tracking-wider text-muted">
      {(Object.keys(TYPE_STYLE) as NodeType[]).map((t) => (
        <span key={t} className="flex items-center gap-1.5">
          <span className="inline-block h-2.5 w-2.5" style={{ background: TYPE_STYLE[t].bg, border: `1px solid ${TYPE_STYLE[t].border}` }} />
          {NODE_LABEL[t]}
        </span>
      ))}
      <span className="flex items-center gap-1.5">
        <span className="inline-block w-5 border-t border-dashed border-alert" /> contradicts
      </span>
      <span className="flex items-center gap-1.5">
        <span className="inline-block w-5 border-t border-amber" /> depends on
      </span>
      <span className="flex items-center gap-1.5">
        <span className="inline-block w-5 border-t border-dashed border-cool" /> needs validation
      </span>
    </div>
  );
}
