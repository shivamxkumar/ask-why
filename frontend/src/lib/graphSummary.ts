import type { Finding, GraphEdge, GraphNode, Relation } from "../types";

const STRENGTH: Relation[] = ["contradicts", "supports", "requires_validation", "raises"];
const ROLE_REL: Record<string, Relation> = { counter: "contradicts", support: "supports", context: "requires_validation", claim_a: "raises", claim_b: "raises" };

/** Summary level of the evidence map: sources → findings (one edge per pair, strongest role wins) + depends-on links. */
export function summarize(nodes: GraphNode[], edges: GraphEdge[], findings: Finding[]): { nodes: GraphNode[]; edges: GraphEdge[] } {
  const keep = nodes.filter((n) => n.id.startsWith("src:") || n.id.startsWith("f:") || n.id.startsWith("q:") || n.id.startsWith("a:"));
  const pair = new Map<string, Relation>();
  for (const f of findings) {
    for (const c of f.citations) {
      if (!c.verified) continue;
      const key = `src:${c.source_id}|f:${f.id}`;
      const rel = ROLE_REL[c.role] ?? "supports";
      const cur = pair.get(key);
      if (!cur || STRENGTH.indexOf(rel) < STRENGTH.indexOf(cur)) pair.set(key, rel);
    }
  }
  const out: GraphEdge[] = Array.from(pair.entries()).map(([k, relation], i) => {
    const [source, target] = k.split("|");
    return { id: `s${i}`, source, target, relation };
  });
  edges.filter((e) => e.relation === "depends_on" || (e.source.startsWith("f:") && (e.target.startsWith("q:") || e.target.startsWith("a:"))) || (e.source.startsWith("q:") && e.target.startsWith("a:"))).forEach((e) => out.push(e));
  return { nodes: keep, edges: out };
}
