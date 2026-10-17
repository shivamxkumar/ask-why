import { cls } from "../lib/format";
import { useStore } from "../store";
import { Button, Spinner } from "./ui";

/** Live view of the backend pipeline. Every row is a real step reported by the server. */
export function Pipeline() {
  const { inv, closeInvestigation } = useStore();
  if (!inv) return null;
  const failed = inv.status === "error";
  return (
    <div className="mx-auto max-w-2xl px-6 py-16">
      <div className="eyebrow mb-3">{failed ? "Analysis stopped" : "Investigation in progress"}</div>
      <p className="display text-[30px] italic leading-tight text-fg">{inv.question}</p>
      <p className="mono mt-3 text-[11.5px] text-muted">
        {inv.sources.length || "—"} sources · {inv.mode === "ai" ? `deterministic engine + ${inv.ai_model}` : "deterministic engine"}
      </p>
      <ol className="mt-8 border-t border-line">
        {inv.pipeline.map((s, i) => (
          <li key={s.step} className="grid grid-cols-[2rem_1.25rem_1fr_auto] items-start gap-3 border-b border-line py-3">
            <span className="mono pt-0.5 text-[11px] text-faint">{String(i + 1).padStart(2, "0")}</span>
            <span className="pt-0.5">
              {s.status === "running" ? (
                <Spinner />
              ) : (
                <span
                  className={cls(
                    "mono text-[12px]",
                    s.status === "done" && "text-ok",
                    s.status === "error" && "text-alert",
                    s.status === "skipped" && "text-faint",
                    s.status === "pending" && "text-faint",
                  )}
                >
                  {s.status === "done" ? "✓" : s.status === "error" ? "✕" : s.status === "skipped" ? "–" : "○"}
                </span>
              )}
            </span>
            <span>
              <span className={cls("text-[14px]", s.status === "pending" ? "text-muted" : "text-fg")}>{s.step}</span>
              {s.detail && <span className="mt-0.5 block text-[12px] leading-snug text-muted">{s.detail}</span>}
            </span>
            <span className="mono text-right text-[11px] text-muted">
              {s.count != null && <span className="text-fg-dim">{s.count}</span>}
              {s.ms != null && <span className="block text-faint">{s.ms} ms</span>}
            </span>
          </li>
        ))}
      </ol>
      {failed && (
        <div className="mt-6 border-l-2 border-alert pl-4">
          <p className="text-[14px] text-fg">{inv.error || "The analysis failed."}</p>
          <Button tone="line" className="mt-3" onClick={closeInvestigation}>
            Back to start
          </Button>
        </div>
      )}
    </div>
  );
}
