import type { ButtonHTMLAttributes, ReactNode } from "react";
import { cls, severity, SEVERITY_COLOR, SEVERITY_LABEL, type Severity } from "../lib/format";
import type { Citation, Finding, Investigation } from "../types";

export function Button({
  tone = "ghost",
  size = "md",
  className,
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & { tone?: "primary" | "ghost" | "line" | "danger"; size?: "sm" | "md" }) {
  return (
    <button
      {...rest}
      className={cls(
        "inline-flex items-center justify-center gap-2 font-medium transition-colors disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer select-none",
        size === "sm" ? "h-7 px-2.5 text-[12px]" : "h-9 px-3.5 text-[13px]",
        tone === "primary" && "bg-amber text-on-amber hover:bg-amber-hover",
        tone === "ghost" && "text-fg-dim hover:text-fg hover:bg-raised",
        tone === "line" && "border border-line text-fg-dim hover:text-fg hover:border-faint",
        tone === "danger" && "border border-alert/50 text-alert hover:bg-alert-soft",
        className,
      )}
    />
  );
}

export function SeverityMark({ f, showLabel = false }: { f: Pick<Finding, "priority">; showLabel?: boolean }) {
  const s: Severity = severity(f);
  return (
    <span className="inline-flex items-center gap-1.5" title={`${SEVERITY_LABEL[s]} priority`}>
      <span className="inline-block h-2 w-2 rotate-45" style={{ background: SEVERITY_COLOR[s] }} aria-hidden />
      {showLabel && <span className="mono text-[10.5px] uppercase tracking-wider" style={{ color: SEVERITY_COLOR[s] }}>{SEVERITY_LABEL[s]}</span>}
    </span>
  );
}

export function Tag({ children, tone = "default", title }: { children: ReactNode; tone?: "default" | "amber" | "alert" | "ok" | "cool"; title?: string }) {
  return (
    <span
      title={title}
      className={cls(
        "mono inline-flex items-center gap-1 whitespace-nowrap border px-1.5 py-[1px] text-[10px] uppercase tracking-[0.08em]",
        tone === "default" && "border-line text-muted",
        tone === "amber" && "border-amber/40 text-amber",
        tone === "alert" && "border-alert/50 text-alert",
        tone === "ok" && "border-ok/50 text-ok",
        tone === "cool" && "border-cool/40 text-cool",
      )}
    >
      {children}
    </span>
  );
}

export function Meter({ value, label, tone = "amber", compact = false }: { value: number; label?: string; tone?: "amber" | "cool" | "muted"; compact?: boolean }) {
  const color = tone === "amber" ? "var(--color-amber)" : tone === "cool" ? "var(--color-cool)" : "var(--color-muted)";
  return (
    <div className={cls("flex items-center gap-2", compact ? "w-24" : "w-full")}>
      {label && <span className="eyebrow w-24 shrink-0 !normal-case !tracking-normal !text-[11px]">{label}</span>}
      <div className="relative h-[3px] flex-1 bg-line" role="meter" aria-valuenow={value} aria-valuemin={0} aria-valuemax={100} aria-label={label}>
        <div className="absolute inset-y-0 left-0" style={{ width: `${Math.max(0, Math.min(100, value))}%`, background: color }} />
      </div>
      <span className="mono w-7 text-right text-[11px] text-fg-dim">{Math.round(value)}</span>
    </div>
  );
}

export function Verified({ c }: { c: Pick<Citation, "verified" | "match"> }) {
  return c.verified ? (
    <Tag tone="ok" title={c.match === "exact" ? "Excerpt found verbatim in the extracted text" : "Excerpt found after normalising whitespace, case and quotes"}>
      ✓ verified{c.match === "normalized" ? "·norm" : ""}
    </Tag>
  ) : (
    <Tag tone="alert" title="This excerpt was not found in the extracted source text. Do not treat it as evidence.">
      ⚠ unverified
    </Tag>
  );
}

const ROLE_LABEL: Record<Citation["role"], string> = {
  support: "supports",
  counter: "contradicts",
  context: "context",
  claim_a: "claim A",
  claim_b: "claim B",
};

export function CitationCard({
  c,
  inv,
  onOpen,
  dense = false,
}: {
  c: Citation;
  inv: Investigation;
  onOpen?: (c: Citation) => void;
  dense?: boolean;
}) {
  const src = inv.sources.find((s) => s.id === c.source_id);
  return (
    <figure className={cls("group border-l-2 pl-3", c.verified ? "border-amber/70" : "border-alert/70")}>
      <blockquote className={cls("display italic text-fg", dense ? "text-[13.5px] leading-snug" : "text-[15px] leading-relaxed")}>
        “{c.excerpt.length > 420 ? c.excerpt.slice(0, 420) + "…" : c.excerpt}”
      </blockquote>
      <figcaption className="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-1">
        <span className="mono text-[11px] text-amber">{c.source_id}</span>
        <span className="mono truncate text-[11px] text-fg-dim" title={src?.name}>{src?.name ?? "unknown source"}</span>
        {c.location_label && <span className="mono text-[11px] text-muted">· {c.location_label}</span>}
        <Tag>{ROLE_LABEL[c.role]}</Tag>
        <Verified c={c} />
        {onOpen && c.verified && c.unit_id && (
          <button onClick={() => onOpen(c)} className="mono text-[11px] text-cool underline-offset-2 hover:underline cursor-pointer">
            open in source →
          </button>
        )}
      </figcaption>
      {c.note && <p className="mt-1 text-[11.5px] text-muted">{c.note}</p>}
    </figure>
  );
}

export function Spinner({ className }: { className?: string }) {
  return <span className={cls("spin inline-block h-3.5 w-3.5 rounded-full border-2 border-amber/30 border-t-amber", className)} aria-hidden />;
}

export function Empty({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="mx-auto max-w-md py-16 text-center">
      <p className="display text-xl text-fg">{title}</p>
      {children && <div className="mt-2 text-[13px] text-muted">{children}</div>}
    </div>
  );
}

export function SectionTitle({ eyebrow, children, right }: { eyebrow?: string; children: ReactNode; right?: ReactNode }) {
  return (
    <div className="flex items-end justify-between gap-4 border-b border-line pb-2">
      <div>
        {eyebrow && <div className="eyebrow mb-1">{eyebrow}</div>}
        <h2 className="display text-[22px] leading-tight text-fg">{children}</h2>
      </div>
      {right}
    </div>
  );
}
