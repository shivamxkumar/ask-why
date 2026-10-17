import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { api, ApiError, clearOfflinePatches, loadBundledSample, rerank, saveOfflinePatch } from "./lib/api";
import type { Finding, Health, Investigation, Status, View } from "./types";

type Selection = { kind: "finding"; id: string } | { kind: "node"; id: string } | null;

interface Toast {
  id: number;
  text: string;
  tone: "ok" | "warn" | "error";
}

interface Store {
  health: Health | null;
  backendChecked: boolean;
  offline: boolean;
  inv: Investigation | null;
  findings: Finding[]; // ranked with current weight
  view: View;
  selection: Selection;
  caseOpen: boolean;
  sourceFocus: { sourceId: string; unitId?: string } | null;
  wImpact: number;
  loading: string | null;
  error: string | null;
  toasts: Toast[];
  setView: (v: View) => void;
  openSample: (reset?: boolean) => Promise<void>;
  openInvestigation: (id: string) => Promise<void>;
  closeInvestigation: () => void;
  createInvestigation: (files: File[], opts: { name?: string; question?: string; useAi: boolean }) => Promise<void>;
  selectFinding: (id: string | null, opts?: { openCase?: boolean }) => void;
  selectNode: (id: string | null) => void;
  closeCase: () => void;
  goSource: (sourceId: string, unitId?: string) => void;
  updateFinding: (id: string, patch: { status?: Status; reviewer_note?: string; impact_override?: number }) => Promise<void>;
  setWeight: (w: number) => void;
  commitWeight: () => Promise<void>;
  toast: (text: string, tone?: Toast["tone"]) => void;
}

const Ctx = createContext<Store | null>(null);

export function useStore(): Store {
  const s = useContext(Ctx);
  if (!s) throw new Error("useStore outside provider");
  return s;
}

function parseHash(): { invId?: string; view?: View; findingId?: string } {
  const parts = window.location.hash.replace(/^#\/?/, "").split("/").filter(Boolean).map(decodeURIComponent);
  if (parts[0] !== "i" || !parts[1]) return {};
  return { invId: parts[1], view: (parts[2] as View) || "overview", findingId: parts[3] };
}

export function StoreProvider({ children }: { children: ReactNode }) {
  const [health, setHealth] = useState<Health | null>(null);
  const [backendChecked, setBackendChecked] = useState(false);
  const [inv, setInv] = useState<Investigation | null>(null);
  const [view, setViewState] = useState<View>("overview");
  const [selection, setSelection] = useState<Selection>(null);
  const [caseOpen, setCaseOpen] = useState(false);
  const [sourceFocus, setSourceFocus] = useState<Store["sourceFocus"]>(null);
  const [wImpact, setWImpact] = useState(0.65);
  const [loading, setLoading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [offlineInv, setOfflineInv] = useState(false);
  const toastId = useRef(0);
  const initialHash = useRef(parseHash()); // read before the URL-sync effect can rewrite it
  const restored = useRef(false);

  const toast = useCallback((text: string, tone: Toast["tone"] = "ok") => {
    const id = ++toastId.current;
    setToasts((t) => [...t, { id, text, tone }]);
    window.setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 3800);
  }, []);

  const adopt = useCallback((next: Investigation, offline = false) => {
    setInv(next);
    setOfflineInv(offline);
    const total = next.scoring.w_impact + next.scoring.w_confidence || 1;
    setWImpact(next.scoring.w_impact / total);
    setError(null);
  }, []);

  // health check once
  useEffect(() => {
    api
      .health()
      .then(setHealth)
      .catch(() => setHealth(null))
      .finally(() => setBackendChecked(true));
  }, []);

  // keep URL in sync
  useEffect(() => {
    if (!inv) {
      if (restored.current && window.location.hash) history.replaceState(null, "", window.location.pathname);
      return;
    }
    const fid = selection?.kind === "finding" ? `/${encodeURIComponent(selection.id)}` : "";
    const h = `#/i/${encodeURIComponent(inv.id)}/${view}${fid}`;
    if (window.location.hash !== h) history.replaceState(null, "", h);
  }, [inv, view, selection]);

  const openSample = useCallback(
    async (reset = false) => {
      setLoading(reset ? "Resetting sample investigation…" : "Opening sample investigation…");
      try {
        let next: Investigation;
        try {
          next = reset ? await api.resetSample() : await api.sample();
          adopt(next);
        } catch (e) {
          // the sample must always be demonstrable: fall back to the bundled copy on any backend failure
          if (reset) clearOfflinePatches();
          next = await loadBundledSample();
          adopt(next, true);
          const why = e instanceof ApiError && e.status !== 0 ? `Backend error (${e.message})` : "Backend offline";
          toast(`${why} — showing the bundled sample. Review changes are kept in this browser.`, "warn");
        }
        setViewState("overview");
        setSelection(null);
        setCaseOpen(false);
      } catch (e) {
        setError((e as Error).message);
      } finally {
        setLoading(null);
      }
    },
    [adopt, toast],
  );

  const openInvestigation = useCallback(
    async (id: string) => {
      if (id === "sample-meridian") return openSample();
      setLoading("Opening investigation…");
      try {
        adopt(await api.get(id));
        setViewState("overview");
        setSelection(null);
        setCaseOpen(false);
      } catch (e) {
        setError((e as Error).message);
      } finally {
        setLoading(null);
      }
    },
    [adopt, openSample],
  );

  // restore from URL on first load
  useEffect(() => {
    if (!backendChecked || restored.current) return;
    const h = initialHash.current;
    if (!h.invId) {
      restored.current = true;
      return;
    }
    (async () => {
      await openInvestigation(h.invId!);
      if (h.view) setViewState(h.view);
      if (h.findingId) {
        setSelection({ kind: "finding", id: h.findingId });
        if (!h.view || h.view === "overview") setCaseOpen(true);
      }
      restored.current = true;
    })();
  }, [backendChecked, openInvestigation]);

  // poll while analysing
  useEffect(() => {
    if (!inv || inv.status !== "analyzing") return;
    const t = window.setInterval(async () => {
      try {
        const next = await api.get(inv.id);
        setInv(next);
        if (next.status === "ready") toast(`Investigation ready — ${next.findings.length} findings.`);
        if (next.status === "error") toast(next.error || "Analysis failed.", "error");
      } catch {
        /* transient; keep polling */
      }
    }, 900);
    return () => window.clearInterval(t);
  }, [inv, toast]);

  const createInvestigation = useCallback<Store["createInvestigation"]>(
    async (files, opts) => {
      setLoading("Uploading sources…");
      try {
        const next = await api.create(files, opts);
        adopt(next);
        setViewState("overview");
        setSelection(null);
        setCaseOpen(false);
      } catch (e) {
        setError((e as Error).message);
        throw e;
      } finally {
        setLoading(null);
      }
    },
    [adopt],
  );

  const closeInvestigation = useCallback(() => {
    setInv(null);
    setSelection(null);
    setCaseOpen(false);
    setViewState("overview");
  }, []);

  const selectFinding = useCallback<Store["selectFinding"]>((id, opts) => {
    setSelection(id ? { kind: "finding", id } : null);
    if (id && opts?.openCase) setViewState("overview"); // the evidence view lives on the Findings view
    if (opts?.openCase !== undefined) setCaseOpen(!!id && opts.openCase);
    else if (!id) setCaseOpen(false);
  }, []);

  const selectNode = useCallback((id: string | null) => {
    setSelection(id ? { kind: "node", id } : null);
  }, []);

  const setView = useCallback((v: View) => {
    setViewState(v);
    setCaseOpen(false);
  }, []);

  const goSource = useCallback((sourceId: string, unitId?: string) => {
    setSourceFocus({ sourceId, unitId });
    setViewState("sources");
    setCaseOpen(false);
  }, []);

  const updateFinding = useCallback<Store["updateFinding"]>(
    async (fid, patch) => {
      if (!inv) return;
      const local = (f: Finding): Finding => {
        const next: Finding = { ...f };
        if (patch.status) next.status = patch.status;
        if (patch.reviewer_note !== undefined) next.reviewer_note = patch.reviewer_note;
        if (patch.impact_override !== undefined) {
          next.impact = patch.impact_override;
          next.score_notes = [`Impact manually set to ${patch.impact_override} by reviewer.`, ...f.score_notes.filter((n) => !n.startsWith("Impact manually set"))];
        }
        return next;
      };
      if (offlineInv) {
        const f = inv.findings.find((x) => x.id === fid);
        if (!f) return;
        const n = local(f);
        saveOfflinePatch(fid, { status: n.status, reviewer_note: n.reviewer_note, impact: n.impact, score_notes: n.score_notes });
        setInv({ ...inv, findings: inv.findings.map((x) => (x.id === fid ? n : x)) });
      } else {
        try {
          setInv(await api.patchFinding(inv.id, fid, patch));
        } catch (e) {
          toast((e as Error).message, "error");
          return;
        }
      }
      if (patch.status) toast(`${fid} marked ${patch.status}.`);
    },
    [inv, offlineInv, toast],
  );

  const setWeight = useCallback((w: number) => setWImpact(w), []);

  const commitWeight = useCallback(async () => {
    if (!inv || offlineInv) return;
    try {
      const cfg = { ...inv.scoring, w_impact: Math.round(wImpact * 100) / 100, w_confidence: Math.round((1 - wImpact) * 100) / 100 };
      setInv(await api.scoring(inv.id, cfg));
    } catch (e) {
      toast(`Ranking not saved: ${(e as Error).message}`, "warn");
    }
  }, [inv, offlineInv, wImpact, toast]);

  const findings = useMemo(() => (inv ? rerank(inv.findings, wImpact) : []), [inv, wImpact]);

  const value: Store = {
    health,
    backendChecked,
    offline: backendChecked && !health,
    inv,
    findings,
    view,
    selection,
    caseOpen,
    sourceFocus,
    wImpact,
    loading,
    error,
    toasts,
    setView,
    openSample,
    openInvestigation,
    closeInvestigation,
    createInvestigation,
    selectFinding,
    selectNode,
    closeCase: () => setCaseOpen(false),
    goSource,
    updateFinding,
    setWeight,
    commitWeight,
    toast,
  };
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}
