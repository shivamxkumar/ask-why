import { useEffect } from "react";
import { Inspector } from "./components/Inspector";
import { LeftRail, NAV, Toasts, TopBar } from "./components/Shell";
import { Spinner } from "./components/ui";
import { cls } from "./lib/format";
import { useStore } from "./store";
import { CaseView } from "./views/CaseView";
import { EvidenceMap } from "./views/EvidenceMap";
import { Investigations } from "./views/Investigations";
import { Landing } from "./views/Landing";
import { Overview } from "./views/Overview";
import { Report } from "./views/Report";
import { Scenarios } from "./views/Scenarios";
import { Sources } from "./views/Sources";

export default function App() {
  const { inv, view, setView, selection, selectFinding, selectNode, caseOpen, closeCase, findings, loading, offline } = useStore();

  // global keys: 1–6 views, esc closes evidence view / inspector, j/k inside the evidence view
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.target as HTMLElement).closest("input,textarea,select,[contenteditable]") || e.metaKey || e.ctrlKey || e.altKey) return;
      if (!inv) return;
      const nav = NAV.find((n) => n.key === e.key);
      if (nav && inv.status === "ready") {
        setView(nav.view);
        return;
      }
      if (e.key === "Escape") {
        if (caseOpen) closeCase();
        else if (selection?.kind === "finding") selectFinding(null);
        else if (selection) selectNode(null);
      }
      if (caseOpen && selection?.kind === "finding" && (e.key === "j" || e.key === "k")) {
        const i = findings.findIndex((f) => f.id === selection.id);
        const n = findings[i + (e.key === "j" ? 1 : -1)];
        if (n) selectFinding(n.id, { openCase: true });
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [inv, setView, caseOpen, closeCase, selection, selectFinding, selectNode, findings]);

  if (!inv) {
    return (
      <>
        <Landing />
        {loading && <LoadingVeil text={loading} />}
        <Toasts />
      </>
    );
  }

  const caseFinding = caseOpen && selection?.kind === "finding" ? findings.find((f) => f.id === selection.id) : undefined;
  const scrollable = view !== "map" && view !== "sources" && view !== "scenarios";

  return (
    <div className="flex h-full flex-col">
      <TopBar />
      {offline && (
        <div className="no-print mono border-b border-amber/30 bg-amber-soft px-4 py-1 text-[11px] text-amber">
          Offline demo — the analysis server is unreachable. Showing bundled sample data; review changes are saved in this browser only.
        </div>
      )}
      <div className="flex min-h-0 flex-1">
        <LeftRail />
        <main id="main" className={cls("print-root min-w-0 flex-1", scrollable ? "overflow-y-auto" : "overflow-hidden")}>
          {caseFinding && view === "overview" ? (
            <CaseView f={caseFinding} />
          ) : view === "overview" ? (
            <Overview />
          ) : view === "sources" ? (
            <Sources />
          ) : view === "map" ? (
            <EvidenceMap />
          ) : view === "scenarios" ? (
            <Scenarios />
          ) : view === "investigations" ? (
            <Investigations />
          ) : (
            <Report />
          )}
        </main>
        {view !== "report" && !(caseFinding && view === "overview") && <Inspector />}
      </div>
      {loading && <LoadingVeil text={loading} />}
      <Toasts />
    </div>
  );
}

function LoadingVeil({ text }: { text: string }) {
  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-ink/70 backdrop-blur-sm" role="status" aria-live="polite">
      <div className="mono flex items-center gap-3 border border-line bg-panel px-4 py-3 text-[12px] text-fg">
        <Spinner /> {text}
      </div>
    </div>
  );
}
