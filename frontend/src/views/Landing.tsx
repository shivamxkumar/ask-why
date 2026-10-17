import { useEffect, useRef, useState, type DragEvent } from "react";
import { Button, Spinner, Tag } from "../components/ui";
import { api } from "../lib/api";
import { cls, fmtBytes, fmtDate } from "../lib/format";
import { useStore } from "../store";
import { ThemeToggle } from "../components/ThemeToggle";
import { CREDIT } from "../lib/brand";
import type { InvestigationSummary } from "../types";

const MODES = [
  {
    key: "project",
    n: "01",
    title: "Investigate a project",
    body: "Briefs, plans, specs and budgets. Surfaces unsupported targets, conflicting dates and requirements, and dependencies with no fallback.",
    formats: "PDF · DOCX · MD · TXT · XLSX",
    question: "What must be true for this plan to succeed — and what haven't we asked?",
  },
  {
    key: "dataset",
    n: "02",
    title: "Audit a dataset",
    body: "Profiles every column: missing values, duplicates, sentinel values, outliers, inconsistent categories and out-of-range values, with row references.",
    formats: "CSV · XLSX",
    question: "Can this data be trusted for the decisions it is meant to support?",
  },
  {
    key: "workflow",
    n: "03",
    title: "Challenge a workflow",
    body: "Process descriptions and runbooks. Finds unowned steps, capacity assumptions and missing escalation paths.",
    formats: "TXT · MD · DOCX · PDF",
    question: "Where can this workflow fail, and who would notice?",
  },
] as const;

const ALLOWED = [".pdf", ".docx", ".txt", ".md", ".markdown", ".csv", ".xlsx"];

function ext(name: string) {
  const i = name.lastIndexOf(".");
  return i < 0 ? "" : name.slice(i).toLowerCase();
}

export function Landing() {
  const { health, backendChecked, offline, openSample, createInvestigation, loading, error, openInvestigation } = useStore();
  const [mode, setMode] = useState<(typeof MODES)[number]["key"]>("project");
  const [files, setFiles] = useState<File[]>([]);
  const [name, setName] = useState("");
  const [question, setQuestion] = useState<string>(MODES[0].question);
  const [questionTouched, setQuestionTouched] = useState(false);
  const [useAi, setUseAi] = useState(true);
  const [drag, setDrag] = useState(false);
  const [recent, setRecent] = useState<InvestigationSummary[]>([]);
  const [sampleFiles, setSampleFiles] = useState<{ name: string; size_bytes: number }[]>([]);
  const inputRef = useRef<HTMLInputElement>(null);
  const formRef = useRef<HTMLDivElement>(null);
  const maxMb = health?.max_file_mb ?? 15;

  useEffect(() => {
    if (!health) return;
    api.list().then(setRecent).catch(() => setRecent([]));
    api.sampleFiles().then(setSampleFiles).catch(() => setSampleFiles([]));
  }, [health]);

  const pickMode = (k: (typeof MODES)[number]["key"]) => {
    setMode(k);
    if (!questionTouched) setQuestion(MODES.find((m) => m.key === k)!.question);
    formRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
    inputRef.current?.focus();
  };

  const checks = files.map((f) => {
    const e = ext(f.name);
    if (!ALLOWED.includes(e)) return { f, ok: false, why: e === ".xls" || e === ".doc" ? `Legacy ${e} is not supported — save as ${e}x` : `${e || "No extension"} is not supported` };
    if (f.size === 0) return { f, ok: false, why: "File is empty" };
    if (f.size > maxMb * 1024 * 1024) return { f, ok: false, why: `Larger than ${maxMb} MB` };
    return { f, ok: true, why: "" };
  });
  const accepted = checks.filter((c) => c.ok).map((c) => c.f);

  const addFiles = (list: FileList | null) => {
    if (!list) return;
    const incoming = Array.from(list);
    setFiles((cur) => {
      const names = new Set(cur.map((f) => f.name + f.size));
      return [...cur, ...incoming.filter((f) => !names.has(f.name + f.size))].slice(0, 12);
    });
  };

  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    setDrag(false);
    addFiles(e.dataTransfer.files);
  };

  const start = async () => {
    if (!accepted.length) return;
    try {
      await createInvestigation(accepted, { name: name || undefined, question: question || undefined, useAi: useAi && !!health?.ai_available });
    } catch {
      /* error surfaced via store */
    }
  };

  return (
    <div className="min-h-full bg-canvas">
      {/* masthead */}
      <header className="border-b border-line">
        <div className="mx-auto flex max-w-[1320px] items-center justify-between gap-4 px-6 py-4 lg:px-10">
          <div className="flex items-baseline gap-3">
            <Wordmark />
            <span className="eyebrow hidden sm:inline">The Unasked Question Engine</span>
          </div>
          <div className="flex items-center gap-4">
            <EngineStatus />
            <ThemeToggle />
          </div>
        </div>
      </header>

      <main className="mx-auto grid max-w-[1320px] grid-cols-1 gap-x-14 gap-y-12 px-6 pb-20 pt-12 lg:grid-cols-12 lg:px-10 lg:pt-20">
        {/* editorial column */}
        <section className="lg:col-span-7">
          <div className="eyebrow mb-6 flex items-center gap-3">
            <span className="inline-block h-px w-10 bg-amber" /> Investigative intelligence for plans, data & workflows
          </div>
          <h1 className="display text-[44px] font-[420] leading-[1.02] text-fg sm:text-[60px] xl:text-[72px]">
            Find the question your project <em className="whitespace-nowrap font-[380] text-amber">forgot to ask.</em>
          </h1>
          <p className="mt-6 max-w-[34rem] text-[17px] leading-relaxed text-fg-dim">
            Investigate your assumptions. Connect conflicting evidence. Discover what could change your next decision.
          </p>
          <div className="mt-8 flex flex-wrap items-center gap-4">
            <Button tone="primary" className="h-11 px-5 text-[14px]" onClick={() => openSample()} disabled={!!loading || !backendChecked}>
              {loading?.startsWith("Opening sample") ? <Spinner className="!border-on-amber/30 !border-t-on-amber" /> : null}
              Try sample investigation →
            </Button>
            <span className="mono text-[11px] leading-snug text-muted">
              Synthetic “Project Meridian” case · 5 sources
              <br />
              No API key needed · runs the real parsers & validator
            </span>
          </div>

          <ol className="mt-14 border-t border-line">
            {MODES.map((m) => (
              <li key={m.key}>
                <button
                  onClick={() => pickMode(m.key)}
                  aria-pressed={mode === m.key}
                  className={cls(
                    "group grid w-full cursor-pointer grid-cols-[3rem_1fr] gap-x-4 border-b border-line py-5 pl-3 pr-4 text-left transition-colors",
                    mode === m.key ? "border-l-2 border-l-amber bg-panel" : "border-l-2 border-l-transparent hover:bg-panel/60",
                  )}
                >
                  <span className={cls("mono pt-1 text-[12px]", mode === m.key ? "text-amber" : "text-faint")}>{m.n}</span>
                  <span>
                    <span className="display block text-[22px] leading-tight text-fg">{m.title}</span>
                    <span className="mt-1 block max-w-xl text-[13.5px] leading-relaxed text-muted">{m.body}</span>
                  </span>
                  <span className="mono col-start-2 mt-2.5 text-[11px] tracking-wider text-faint">{m.formats}</span>
                </button>
              </li>
            ))}
          </ol>

          <figure className="mt-14 max-w-xl">
            <div className="eyebrow mb-3">An unasked question, from the sample case</div>
            <blockquote className="display text-[24px] italic leading-snug text-fg">
              “What happens to dispatching when PathCore rate-limits — and what does the plan cost at 60,000 requests a day?”
            </blockquote>
            <figcaption className="mono mt-3 text-[11px] text-muted">
              Derived from <span className="text-amber">S2 · p.3 ¶2–4</span> — the delivery plan's own load estimate, not a model guess.
            </figcaption>
          </figure>
        </section>

        {/* intake form on paper */}
        <aside className="lg:col-span-5" ref={formRef}>
          <div className="paper relative px-6 pb-6 pt-5 shadow-[0_30px_80px_-30px_rgba(0,0,0,0.7)] sm:px-8">
            <div className="flex items-baseline justify-between border-b border-paper-line pb-3">
              <h2 className="display text-[24px] text-paper-ink">Open a case file</h2>
              <span className="mono text-[10.5px] uppercase tracking-widest text-paper-muted">Intake</span>
            </div>

            {offline ? (
              <p className="mt-4 border border-[#d9574a66] bg-[#d9574a12] p-3 text-[13px] leading-relaxed text-[#8a2a20]">
                The analysis server isn't reachable, so uploads are unavailable. The sample investigation still works from bundled data. Start
                the backend with <code className="mono text-[12px]">./start.sh</code> to analyse your own files.
              </p>
            ) : null}

            <div
              onDragOver={(e) => {
                e.preventDefault();
                setDrag(true);
              }}
              onDragLeave={() => setDrag(false)}
              onDrop={onDrop}
              className={cls(
                "mt-5 border-[1.5px] border-dashed px-4 py-7 text-center transition-colors",
                drag ? "border-amber-deep bg-[#f5a62318]" : "border-[#bdb4a2]",
                offline && "pointer-events-none opacity-50",
              )}
            >
              <p className="display text-[18px] text-paper-ink">Drop project material here</p>
              <p className="mt-1 text-[12.5px] text-paper-muted">
                or{" "}
                <button className="cursor-pointer font-medium text-paper-ink underline underline-offset-2" onClick={() => inputRef.current?.click()}>
                  choose files
                </button>{" "}
                · up to 12 files, {maxMb} MB each
              </p>
              <input
                ref={inputRef}
                type="file"
                multiple
                className="sr-only"
                accept={ALLOWED.join(",")}
                onChange={(e) => {
                  addFiles(e.target.files);
                  e.target.value = "";
                }}
                aria-label="Choose files to investigate"
              />
            </div>

            {checks.length > 0 && (
              <ul className="mt-3 divide-y divide-paper-line border-y border-paper-line">
                {checks.map(({ f, ok, why }) => (
                  <li key={f.name + f.size} className="flex items-center gap-3 py-1.5 text-[12.5px]">
                    <span className={cls("mono w-12 text-[10.5px] uppercase", ok ? "text-paper-muted" : "text-[#b13a2c]")}>{ext(f.name).slice(1) || "?"}</span>
                    <span className="min-w-0 flex-1 truncate text-paper-ink">{f.name}</span>
                    <span className={cls("mono text-[11px]", ok ? "text-paper-muted" : "text-[#b13a2c]")}>{ok ? fmtBytes(f.size) : why}</span>
                    <button
                      aria-label={`Remove ${f.name}`}
                      className="cursor-pointer px-1 text-paper-muted hover:text-paper-ink"
                      onClick={() => setFiles((cur) => cur.filter((x) => x !== f))}
                    >
                      ×
                    </button>
                  </li>
                ))}
              </ul>
            )}

            <label className="mt-5 block">
              <span className="mono text-[10.5px] uppercase tracking-widest text-paper-muted">Case name</span>
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. Q3 launch plan review"
                className="mt-1 w-full border-b border-[#bdb4a2] bg-transparent py-1.5 text-[14px] text-paper-ink outline-none placeholder:text-[#a59d8c] focus:border-paper-ink"
              />
            </label>
            <label className="mt-4 block">
              <span className="mono text-[10.5px] uppercase tracking-widest text-paper-muted">The question framing this investigation</span>
              <textarea
                value={question}
                rows={2}
                onChange={(e) => {
                  setQuestion(e.target.value);
                  setQuestionTouched(true);
                }}
                className="display mt-1 w-full resize-none border-b border-[#bdb4a2] bg-transparent py-1.5 text-[16px] italic leading-snug text-paper-ink outline-none focus:border-paper-ink"
              />
            </label>

            {health?.ai_available ? (
              <label className="mt-4 flex items-start gap-3 text-[12.5px] text-paper-ink">
                <input type="checkbox" className="mt-0.5 accent-[#b97a12]" checked={useAi} onChange={(e) => setUseAi(e.target.checked)} />
                <span>
                  Add AI analysis <span className="mono text-paper-muted">({health.model})</span>
                  <span className="block text-[11.5px] text-paper-muted">Claude proposes extra findings; every excerpt is still checked against the extracted text.</span>
                </span>
              </label>
            ) : (
              <div className="mt-4 flex items-start gap-3 border-t border-paper-line pt-3 text-[12.5px] text-paper-ink">
                <span className="mono mt-0.5 shrink-0 border border-paper-line px-1.5 text-[10px] uppercase tracking-wider text-paper-muted">AI off</span>
                <span className="text-[11.5px] leading-snug text-paper-muted">
                  The deterministic engine will analyse your files. To add Claude, set <code className="mono text-paper-ink">ANTHROPIC_API_KEY</code> on the backend.
                </span>
              </div>
            )}

            {error && <p className="mt-4 border-l-2 border-[#b13a2c] pl-3 text-[12.5px] text-[#8a2a20]">{error}</p>}

            <button
              onClick={start}
              disabled={!accepted.length || !!loading || offline}
              className="mt-5 flex h-11 w-full cursor-pointer items-center justify-center gap-2 bg-paper-ink text-[14px] font-medium text-paper transition-colors hover:bg-black disabled:cursor-not-allowed disabled:opacity-35"
            >
              {loading?.startsWith("Uploading") && <Spinner />}
              {accepted.length ? `Investigate ${accepted.length} source${accepted.length > 1 ? "s" : ""} →` : "Add files to begin"}
            </button>

            <dl className="mt-6 grid grid-cols-[4.5rem_1fr] gap-x-3 gap-y-1 border-t border-paper-line pt-4 text-[11.5px] leading-snug text-paper-muted">
              <dt className="mono text-paper-ink">PDF</dt>
              <dd>Text layer only (no OCR); page numbers preserved</dd>
              <dt className="mono text-paper-ink">DOCX</dt>
              <dd>Paragraphs, headings and tables</dd>
              <dt className="mono text-paper-ink">TXT · MD</dt>
              <dd>Paragraphs and list items with line numbers</dd>
              <dt className="mono text-paper-ink">CSV · XLSX</dt>
              <dd>Every row addressable; sheets, headers and a full column profile</dd>
            </dl>

            {sampleFiles.length > 0 && (
              <p className="mt-4 text-[11.5px] leading-relaxed text-paper-muted">
                Want to test the upload path? Download the synthetic sample files:{" "}
                {sampleFiles.map((s, i) => (
                  <span key={s.name}>
                    <a className="mono text-paper-ink underline underline-offset-2" href={`/api/sample/files/${encodeURIComponent(s.name)}`} download>
                      {s.name}
                    </a>
                    {i < sampleFiles.length - 1 ? ", " : ""}
                  </span>
                ))}
              </p>
            )}
          </div>

          {recent.length > 0 && (
            <div className="mt-10">
              <div className="eyebrow mb-2">Recent case files</div>
              <ul className="divide-y divide-line border-y border-line">
                {recent.slice(0, 6).map((r) => (
                  <li key={r.id}>
                    <button onClick={() => openInvestigation(r.id)} className="flex w-full cursor-pointer items-center gap-3 py-2.5 text-left hover:bg-panel">
                      <span className="min-w-0 flex-1 truncate text-[13.5px] text-fg">{r.name}</span>
                      <Tag tone={r.mode === "ai" ? "cool" : r.mode === "sample" ? "amber" : "default"}>{r.mode}</Tag>
                      <span className="mono w-28 text-right text-[11px] text-muted">
                        {r.status === "ready" ? `${r.open_count}/${r.finding_count} open` : r.status}
                      </span>
                      <span className="mono hidden w-28 text-right text-[11px] text-faint sm:inline">{fmtDate(r.updated_at)}</span>
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </aside>
      </main>

      <footer className="border-t border-line">
        <div className="mx-auto flex max-w-[1320px] flex-wrap items-center justify-between gap-3 px-6 py-5 lg:px-10">
          <p className="display text-[15px] italic text-fg-dim">Your biggest risk might be the question you never asked.</p>
          <p className="mono text-[11px] text-muted">
            <span className="text-fg-dim">{CREDIT}</span> · Findings support human judgement — not guarantees of correctness.
          </p>
        </div>
      </footer>
    </div>
  );
}

export function Wordmark({ size = "lg" }: { size?: "lg" | "sm" }) {
  return (
    <span className={cls("mono font-semibold tracking-tight text-fg", size === "lg" ? "text-[17px]" : "text-[14px]")} aria-label="ASK WHY">
      ASK<span className="text-amber">//</span>WHY
    </span>
  );
}

export function EngineStatus() {
  const { health, backendChecked } = useStore();
  if (!backendChecked) return <span className="mono text-[11px] text-muted">checking engine…</span>;
  if (!health)
    return (
      <span className="mono flex items-center gap-2 text-[11px] text-muted">
        <span className="h-1.5 w-1.5 rounded-full bg-alert" /> engine offline · sample only
      </span>
    );
  return (
    <span className="mono flex items-center gap-2 text-[11px] text-muted">
      <span className="h-1.5 w-1.5 rounded-full bg-ok" /> engine online
      <span className="text-faint">·</span>
      {health.ai_available ? <span className="text-cool">AI: {health.model}</span> : <span>AI off — deterministic engine</span>}
    </span>
  );
}
