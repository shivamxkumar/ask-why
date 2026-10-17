import type { ReactNode } from "react";
import { cls } from "../lib/format";
import { useStore } from "../store";
import type { View } from "../types";
import { Wordmark } from "../views/Landing";
import { Button, Spinner, Tag } from "./ui";
import { ThemeToggle } from "./ThemeToggle";
import { CREDIT } from "../lib/brand";

const ICONS: Record<View, ReactNode> = {
  investigations: <path d="M3 4h10M3 8h10M3 12h6" />,
  sources: <path d="M4 2.5h5.5L12 5v8.5H4zM9.5 2.5V5H12" />,
  overview: <path d="M8 2.5 13.5 8 8 13.5 2.5 8z M8 6v2.6M8 10.4v.1" />,
  map: <path d="M4 4.5a1.5 1.5 0 1 0 0 .01M12 3.5a1.5 1.5 0 1 0 0 .01M11 12a1.5 1.5 0 1 0 0 .01M5.3 5.2l4.5 5.6M5.4 4.3l5.2-.6" />,
  scenarios: <path d="M2.5 12.5h11M4 10l3-3.5 2.5 2L13 4" />,
  report: <path d="M4 2.5h8v11H4zM6 5.5h4M6 8h4M6 10.5h2.5" />,
};

export const NAV: { view: View; label: string; key: string }[] = [
  { view: "investigations", label: "Investigations", key: "1" },
  { view: "sources", label: "Sources", key: "2" },
  { view: "overview", label: "Findings", key: "3" },
  { view: "map", label: "Evidence map", key: "4" },
  { view: "scenarios", label: "Scenario lab", key: "5" },
  { view: "report", label: "Report", key: "6" },
];

export function Icon({ view, className }: { view: View; className?: string }) {
  return (
    <svg viewBox="0 0 16 16" className={cls("h-4 w-4 shrink-0", className)} fill="none" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      {ICONS[view]}
    </svg>
  );
}

export function TopBar() {
  const { inv, closeInvestigation, setView, findings } = useStore();
  if (!inv) return null;
  const open = findings.filter((f) => f.status === "open").length;
  return (
    <header className="no-print flex h-12 shrink-0 items-center gap-3 border-b border-line bg-ink/60 px-3 sm:px-4">
      <button onClick={closeInvestigation} className="cursor-pointer" title="Back to start">
        <Wordmark size="sm" />
      </button>
      <span className="h-5 w-px bg-line" />
      <div className="flex min-w-0 flex-1 items-center gap-3">
        <h1 className="display min-w-0 truncate text-[16px] text-fg" title={inv.name}>
          {inv.name}
        </h1>
        {inv.mode === "sample" && (
          <Tag tone="amber" title="Curated demonstration on synthetic data — not live AI output">
            sample · synthetic
          </Tag>
        )}
        {inv.mode === "heuristic" && <Tag title="Deterministic pattern-based engine; no AI call was made">deterministic engine</Tag>}
        {inv.mode === "ai" && <Tag tone="cool" title="Deterministic engine plus Claude; all citations re-validated">AI · {inv.ai_model}</Tag>}
      </div>
      <div className="mono hidden items-center gap-4 text-[11px] text-muted md:flex">
        <span>
          <span className="text-fg-dim">{inv.sources.length}</span> sources
        </span>
        {inv.status === "analyzing" ? (
          <span className="flex items-center gap-2 text-amber">
            <Spinner /> analysing
          </span>
        ) : inv.status === "error" ? (
          <span className="text-alert">analysis failed</span>
        ) : (
          <span>
            <span className="text-fg-dim">{findings.length}</span> findings · <span className="text-amber">{open}</span> open
          </span>
        )}
      </div>
      <ThemeToggle className="h-7" />
      <Button tone="line" size="sm" onClick={() => setView("report")} disabled={inv.status !== "ready"}>
        Export report
      </Button>
    </header>
  );
}

export function LeftRail() {
  const { view, setView, inv } = useStore();
  const ready = inv?.status === "ready";
  return (
    <nav aria-label="Workspace" className="no-print flex w-14 shrink-0 flex-col border-r border-line bg-ink/40 py-3 lg:w-[176px]">
      {NAV.map((n) => {
        const active = view === n.view;
        const disabled = !ready && n.view !== "investigations" && n.view !== "overview";
        return (
          <button
            key={n.view}
            onClick={() => setView(n.view)}
            disabled={disabled}
            aria-current={active ? "page" : undefined}
            title={`${n.label} (${n.key})`}
            className={cls(
              "group relative flex h-9 cursor-pointer items-center gap-3 px-[19px] text-left text-[13px] transition-colors disabled:cursor-not-allowed disabled:opacity-30 lg:px-4",
              active ? "text-fg" : "text-muted hover:text-fg",
            )}
          >
            {active && <span className="absolute inset-y-1.5 left-0 w-[2px] bg-amber" />}
            <Icon view={n.view} className={active ? "text-amber" : ""} />
            <span className="hidden flex-1 lg:inline">{n.label}</span>
            <span className="mono hidden text-[10px] text-faint lg:inline">{n.key}</span>
          </button>
        );
      })}
      <div className="mt-auto hidden px-4 pt-4 lg:block">
        <p className="mono text-[10px] leading-relaxed text-faint">
          j / k move · ↵ open
          <br />
          esc close · 1–6 views
        </p>
        <p className="mt-3 border-t border-line pt-3 text-[11px] leading-snug text-muted">{CREDIT}</p>
      </div>
      <p className="mono mt-auto px-1 text-center text-[8px] leading-tight text-faint lg:hidden" title={CREDIT}>
        XYZ
        <br />
        IIITIANS
      </p>
    </nav>
  );
}

export function Toasts() {
  const { toasts } = useStore();
  return (
    <div className="no-print pointer-events-none fixed bottom-4 left-1/2 z-50 flex -translate-x-1/2 flex-col items-center gap-2" role="status" aria-live="polite">
      {toasts.map((t) => (
        <div
          key={t.id}
          className={cls(
            "case-in mono pointer-events-auto border bg-panel px-3 py-2 text-[12px] shadow-xl",
            t.tone === "ok" && "border-ok/40 text-fg",
            t.tone === "warn" && "border-amber/50 text-fg",
            t.tone === "error" && "border-alert/60 text-fg",
          )}
        >
          <span className={cls("mr-2", t.tone === "ok" ? "text-ok" : t.tone === "warn" ? "text-amber" : "text-alert")}>
            {t.tone === "ok" ? "✓" : "!"}
          </span>
          {t.text}
        </div>
      ))}
    </div>
  );
}
