"""Evidence Constellation: derive a typed relationship graph from sources, cited units and findings.

Columns (left → right): source → claim (cited passage) → assumption / constraint / risk → question → action.
Every edge is backed by something concrete: a citation role, a contradiction pair, or an explicit depends_on.
"""
from __future__ import annotations

from app.schemas import EvidenceUnit, Finding, Graph, GraphEdge, GraphNode, NodeType, Relation, Source

CATEGORY_NODE: dict[str, NodeType] = {
    "assumption": "assumption",
    "missing_constraint": "constraint",
    "contradiction": "risk",
    "dependency": "risk",
    "contingency": "risk",
    "missing_evidence": "risk",
    "data_quality": "risk",
    "open_question": "question",
}
ROLE_RELATION: dict[str, Relation] = {
    "support": "supports",
    "counter": "contradicts",
    "context": "requires_validation",
    "claim_a": "raises",
    "claim_b": "raises",
}


def _short(text: str, n: int = 84) -> str:
    text = " ".join(text.split())
    return text if len(text) <= n else text[: n - 1].rstrip() + "…"


def build_graph(sources: list[Source], findings: list[Finding], units: list[EvidenceUnit]) -> Graph:
    by_unit = {u.id: u for u in units}
    nodes: dict[str, GraphNode] = {}
    edges: dict[str, GraphEdge] = {}

    def node(n: GraphNode) -> GraphNode:
        if n.id in nodes:
            for fid in n.finding_ids:
                if fid not in nodes[n.id].finding_ids:
                    nodes[n.id].finding_ids.append(fid)
            return nodes[n.id]
        nodes[n.id] = n
        return n

    def edge(a: str, b: str, rel: Relation) -> None:
        key = f"{a}|{b}|{rel}"
        if a != b and key not in edges:
            edges[key] = GraphEdge(id=f"e{len(edges) + 1}", source=a, target=b, relation=rel)

    source_names = {s.id: s.name for s in sources}
    finding_ids = {f.id for f in findings}

    for f in findings:
        fid = f"f:{f.id}"
        node(GraphNode(id=fid, type=CATEGORY_NODE.get(f.category, "risk"), label=f.title, detail=f.summary, finding_ids=[f.id]))
        for c in f.citations:
            if not c.unit_id or c.unit_id not in by_unit:
                continue  # unverified excerpts never enter the graph as evidence
            u = by_unit[c.unit_id]
            sid = f"src:{u.source_id}"
            node(GraphNode(id=sid, type="source", label=source_names.get(u.source_id, u.source_id), source_id=u.source_id, finding_ids=[f.id]))
            cid = f"unit:{u.id}"
            node(GraphNode(id=cid, type="claim", label=_short(c.excerpt), detail=u.text, source_id=u.source_id, unit_id=u.id, finding_ids=[f.id]))
            edge(sid, cid, "cites")
            edge(cid, fid, ROLE_RELATION.get(c.role, "supports"))
        if f.contradiction:
            a, b = f.contradiction.claim_a.citation, f.contradiction.claim_b.citation
            if a.unit_id in by_unit and b.unit_id in by_unit:
                edge(f"unit:{a.unit_id}", f"unit:{b.unit_id}", "contradicts")
        if f.category != "open_question":
            qid = f"q:{f.id}"
            node(GraphNode(id=qid, type="question", label=_short(f.question, 96), detail=f.question, finding_ids=[f.id]))
            edge(fid, qid, "raises")
            aid = f"a:{f.id}"
            node(GraphNode(id=aid, type="action", label=_short(f.recommendation, 96), detail=f.recommendation, finding_ids=[f.id]))
            edge(qid, aid, "addresses")
        else:
            aid = f"a:{f.id}"
            node(GraphNode(id=aid, type="action", label=_short(f.recommendation, 96), detail=f.recommendation, finding_ids=[f.id]))
            edge(fid, aid, "addresses")

    for f in findings:
        for dep in f.depends_on:
            target = dep if dep.startswith("f:") else f"f:{dep}"
            if target.removeprefix("f:") in finding_ids:
                edge(f"f:{f.id}", target, "depends_on")

    return Graph(nodes=list(nodes.values()), edges=list(edges.values()))
