import { useSyncExternalStore } from "react";

export type Theme = "light" | "dark";
const KEY = "askwhy:theme";
const listeners = new Set<() => void>();

function read(): Theme {
  const t = document.documentElement.dataset.theme;
  return t === "dark" ? "dark" : "light";
}

export function setTheme(t: Theme): void {
  document.documentElement.dataset.theme = t;
  try {
    localStorage.setItem(KEY, t);
  } catch {
    /* storage unavailable: theme lasts for this page view only */
  }
  listeners.forEach((l) => l());
}

export function useTheme(): [Theme, () => void] {
  const theme = useSyncExternalStore(
    (cb) => {
      listeners.add(cb);
      return () => listeners.delete(cb);
    },
    read,
    () => "light" as Theme,
  );
  return [theme, () => setTheme(theme === "light" ? "dark" : "light")];
}

/** Colours for SVG chart/graph attributes, which can't read CSS variables reliably. */
export const PALETTE = {
  dark: {
    grid: "#1c2430",
    axis: "#29344a",
    tick: "#6e7989",
    label: "#98a1af",
    text: "#e8e4da",
    amber: "#f5a623",
    alert: "#d9574a",
    dots: "#1c2430",
    areaOpacity: 0.05,
  },
  light: {
    grid: "#e4dfd4",
    axis: "#cfc8bb",
    tick: "#848b96",
    label: "#5c6470",
    text: "#1b1f27",
    amber: "#c07a0a",
    alert: "#bf3b2d",
    dots: "#dcd6ca",
    areaOpacity: 0.07,
  },
} as const;
