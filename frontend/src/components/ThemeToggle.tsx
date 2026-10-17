import { cls } from "../lib/format";
import { useTheme } from "../lib/theme";

export function ThemeToggle({ className }: { className?: string }) {
  const [theme, toggle] = useTheme();
  const next = theme === "light" ? "dark" : "light";
  return (
    <button
      onClick={toggle}
      aria-label={`Switch to ${next} theme`}
      title={`Switch to ${next} theme`}
      className={cls(
        "inline-flex h-8 cursor-pointer items-center gap-2 border border-line px-2.5 text-[12px] text-fg-dim transition-colors hover:border-faint hover:text-fg",
        className,
      )}
    >
      {theme === "light" ? (
        <svg viewBox="0 0 16 16" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="1.4" aria-hidden>
          <path d="M13.5 9.5A5.5 5.5 0 0 1 6.5 2.5a5.5 5.5 0 1 0 7 7Z" strokeLinejoin="round" />
        </svg>
      ) : (
        <svg viewBox="0 0 16 16" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" aria-hidden>
          <circle cx="8" cy="8" r="3" />
          <path d="M8 1.5v1.5M8 13v1.5M1.5 8H3M13 8h1.5M3.4 3.4l1 1M11.6 11.6l1 1M3.4 12.6l1-1M11.6 4.4l1-1" />
        </svg>
      )}
      <span className="mono hidden text-[11px] sm:inline">{next === "dark" ? "Dark" : "Light"}</span>
    </button>
  );
}
