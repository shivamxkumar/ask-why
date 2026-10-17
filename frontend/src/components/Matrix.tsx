import { CartesianGrid, ReferenceArea, ReferenceLine, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis } from "recharts";
import { severity, SEVERITY_COLOR } from "../lib/format";
import { PALETTE, useTheme } from "../lib/theme";
import type { Finding } from "../types";

interface Pt {
  x: number;
  y: number;
  f: Finding;
}

/** Impact (y) vs evidence confidence (x). High impact + low confidence = validate first. */
export function Matrix({ findings, selectedId, onSelect, height = 300 }: { findings: Finding[]; selectedId?: string; onSelect: (id: string) => void; height?: number }) {
  const [theme] = useTheme();
  const P = PALETTE[theme];
  const data: Pt[] = findings.map((f) => ({ x: f.confidence, y: f.impact, f }));
  // label only points that won't collide with an already-labelled, higher-priority point
  const labelled = new Set<string>();
  const placed: Pt[] = [];
  [...data]
    .sort((a, b) => b.f.priority - a.f.priority)
    .forEach((p) => {
      if (p.f.id === selectedId || !placed.some((q) => Math.abs(q.x - p.x) < 9 && Math.abs(q.y - p.y) < 5)) {
        labelled.add(p.f.id);
        placed.push(p);
      }
    });
  return (
    <div className="relative" style={{ height }}>
      <div className="mono pointer-events-none absolute left-12 top-1 z-10 text-[10px] uppercase tracking-widest text-alert/80">Validate first</div>
      <div className="mono pointer-events-none absolute right-3 top-1 z-10 text-[10px] uppercase tracking-widest text-amber/80">Act now</div>
      <div className="mono pointer-events-none absolute bottom-12 left-12 z-10 text-[10px] uppercase tracking-widest text-faint">Monitor</div>
      <div className="mono pointer-events-none absolute bottom-12 right-6 z-10 text-[10px] uppercase tracking-widest text-faint">Schedule</div>
      <ResponsiveContainer width="100%" height="100%">
        <ScatterChart margin={{ top: 18, right: 14, bottom: 22, left: 0 }}>
          <ReferenceArea x1={0} x2={60} y1={60} y2={100} fill={P.alert} fillOpacity={P.areaOpacity} stroke="none" />
          <ReferenceArea x1={60} x2={100} y1={60} y2={100} fill={P.amber} fillOpacity={P.areaOpacity} stroke="none" />
          <CartesianGrid stroke={P.grid} />
          <ReferenceLine x={60} stroke={P.axis} />
          <ReferenceLine y={60} stroke={P.axis} />
          <XAxis
            type="number"
            dataKey="x"
            domain={[0, 100]}
            ticks={[0, 20, 40, 60, 80, 100]}
            tick={{ fill: P.tick, fontSize: 10, fontFamily: "JetBrains Mono" }}
            stroke={P.axis}
            label={{ value: "CONFIDENCE (evidence strength) →", position: "insideBottom", offset: -12, fill: P.label, fontSize: 9.5, fontFamily: "JetBrains Mono" }}
          />
          <YAxis
            type="number"
            dataKey="y"
            domain={[0, 100]}
            ticks={[0, 20, 40, 60, 80, 100]}
            width={40}
            tick={{ fill: P.tick, fontSize: 10, fontFamily: "JetBrains Mono" }}
            stroke={P.axis}
            label={{ value: "IMPACT →", angle: -90, position: "insideLeft", offset: 12, fill: P.label, fontSize: 9.5, fontFamily: "JetBrains Mono" }}
          />
          <Tooltip
            cursor={false}
            content={({ payload }) => {
              const p = payload?.[0]?.payload as Pt | undefined;
              if (!p) return null;
              return (
                <div className="max-w-[260px] border border-line bg-ink px-3 py-2 shadow-xl">
                  <div className="mono text-[10.5px] text-amber">
                    {p.f.id} · impact {p.f.impact} · confidence {p.f.confidence}
                  </div>
                  <div className="mt-1 text-[12.5px] leading-snug text-fg">{p.f.title}</div>
                </div>
              );
            }}
          />
          <Scatter
            data={data}
            isAnimationActive={false}
            onClick={(p) => onSelect((p as unknown as { payload: Pt }).payload.f.id)}
            shape={(props: unknown) => {
              const { cx, cy, payload } = props as { cx: number; cy: number; payload: Pt };
              const sel = payload.f.id === selectedId;
              const done = payload.f.status !== "open";
              const color = SEVERITY_COLOR[severity(payload.f)];
              return (
                <g style={{ cursor: "pointer" }} role="button" aria-label={`${payload.f.id}: ${payload.f.title}`}>
                  {sel && <circle cx={cx} cy={cy} r={11} fill="none" stroke={P.amber} strokeWidth={1.2} />}
                  <rect x={cx - 4.5} y={cy - 4.5} width={9} height={9} transform={`rotate(45 ${cx} ${cy})`} style={{ fill: done ? "transparent" : color, stroke: color }} strokeWidth={1.4} />
                  {labelled.has(payload.f.id) && (
                    <text x={cx + 9} y={cy + 3.5} fill={sel ? P.text : P.label} fontSize={10} fontFamily="JetBrains Mono">
                      {payload.f.id}
                    </text>
                  )}
                </g>
              );
            }}
          />
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  );
}
