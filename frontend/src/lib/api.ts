import type { Finding, Health, Investigation, InvestigationSummary, ScoringConfig, Status } from "../types";

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, init);
  } catch {
    throw new ApiError("The analysis server is not reachable. Start the backend (see README) and try again.", 0);
  }
  if (!res.ok) {
    let msg = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      msg = typeof body.detail === "string" ? body.detail : Array.isArray(body.detail) ? body.detail.map((d: { msg: string }) => d.msg).join("; ") : msg;
    } catch {
      /* not JSON */
    }
    throw new ApiError(msg, res.status);
  }
  return res.json() as Promise<T>;
}

const json = (body: unknown, method = "POST"): RequestInit => ({
  method,
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export const api = {
  health: () => req<Health>("/api/health", { signal: AbortSignal.timeout(2500) }),
  list: () => req<InvestigationSummary[]>("/api/investigations"),
  get: (id: string) => req<Investigation>(`/api/investigations/${encodeURIComponent(id)}`),
  remove: (id: string) => req<unknown>(`/api/investigations/${encodeURIComponent(id)}`, { method: "DELETE" }),
  sample: () => req<Investigation>("/api/sample"),
  resetSample: () => req<Investigation>("/api/sample/reset", { method: "POST" }),
  sampleFiles: () => req<{ name: string; size_bytes: number; kind: string }[]>("/api/sample/files"),
  create: (files: File[], opts: { name?: string; question?: string; useAi: boolean }) => {
    const fd = new FormData();
    files.forEach((f) => fd.append("files", f, f.name));
    if (opts.name) fd.append("name", opts.name);
    if (opts.question) fd.append("question", opts.question);
    fd.append("use_ai", String(opts.useAi));
    return req<Investigation>("/api/investigations", { method: "POST", body: fd });
  },
  patchFinding: (id: string, fid: string, patch: { status?: Status; reviewer_note?: string; impact_override?: number }) =>
    req<Investigation>(`/api/investigations/${encodeURIComponent(id)}/findings/${encodeURIComponent(fid)}`, json(patch, "PATCH")),
  scoring: (id: string, cfg: ScoringConfig) => req<Investigation>(`/api/investigations/${encodeURIComponent(id)}/scoring`, json(cfg, "PUT")),
};

/** Client-side mirror of backend scoring.priority for instant re-ranking (impact/confidence come from the server). */
export function rerank(findings: Finding[], wImpact: number): Finding[] {
  const w = Math.min(1, Math.max(0, wImpact));
  return findings
    .map((f) => ({ ...f, priority: Math.round((w * f.impact + (1 - w) * f.confidence) * 10) / 10 }))
    .sort((a, b) => b.priority - a.priority || b.impact - a.impact || a.id.localeCompare(b.id));
}

// ---- offline sample persistence (used only when the backend is unreachable)
const LS_KEY = "askwhy:offline-sample";

export function loadOfflinePatches(): Record<string, Partial<Finding>> {
  try {
    return JSON.parse(localStorage.getItem(LS_KEY) || "{}");
  } catch {
    return {};
  }
}

export function saveOfflinePatch(fid: string, patch: Partial<Finding>): void {
  try {
    const all = loadOfflinePatches();
    all[fid] = { ...all[fid], ...patch };
    localStorage.setItem(LS_KEY, JSON.stringify(all));
  } catch {
    /* storage unavailable — state lives in memory only */
  }
}

export function clearOfflinePatches(): void {
  try {
    localStorage.removeItem(LS_KEY);
  } catch {
    /* ignore */
  }
}

export async function loadBundledSample(): Promise<Investigation> {
  const mod = await import("../data/sample-investigation.json");
  const inv = structuredClone(mod.default as unknown as Investigation);
  const patches = loadOfflinePatches();
  inv.findings = inv.findings.map((f) => ({ ...f, ...patches[f.id] }));
  return inv;
}
