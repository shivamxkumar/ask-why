import { describe, expect, it } from "vitest";
import { locate } from "../components/Passage";
import sample from "../data/sample-investigation.json";
import type { Investigation } from "../types";
import { rerank } from "./api";
import { evaluate, evaluateMetrics } from "./formula";

describe("formula evaluator", () => {
  it("handles precedence, power and functions", () => {
    expect(evaluate("1 + 2 * 3", {})).toBe(7);
    expect(evaluate("2 ^ 3 ^ 2", {})).toBe(512);
    expect(evaluate("-(2 + 3) * x", { x: 2 })).toBe(-10);
    expect(evaluate("ceil(max(1.2, 3.4))", {})).toBe(4);
    expect(evaluate("ln(target / start) / ln(1 + rate)", { target: 100, start: 100, rate: 0.5 })).toBe(0);
  });
  it("rejects unknown identifiers and junk", () => {
    expect(() => evaluate("alert(1)", {})).toThrow();
    expect(() => evaluate("x +", { x: 1 })).toThrow();
    expect(() => evaluate("window", {})).toThrow();
  });
  it("chains metrics and turns errors into NaN", () => {
    const out = evaluateMetrics([{ key: "a", formula: "p * 2" }, { key: "b", formula: "a + 1" }, { key: "c", formula: "nope" }], { p: 3 });
    expect(out).toMatchObject({ a: 6, b: 7 });
    expect(Number.isNaN(out.c)).toBe(true);
  });
});

describe("sample scenarios", () => {
  const inv = sample as unknown as Investigation;
  it("SC1 baseline reproduces the plan's own arithmetic", () => {
    const s = inv.scenarios.find((x) => x.id === "SC1")!;
    const vars = Object.fromEntries(s.constants.map((c) => [c.key, c.value]));
    const base = evaluateMetrics(s.metrics, { ...vars, slowdown: 0 });
    expect(Math.round(base.accounts12)).toBe(4397); // 120 × 1.35^12
    const slow = evaluateMetrics(s.metrics, { ...vars, slowdown: 50 });
    expect(slow.accounts12).toBeLessThan(2500);
  });
  it("every metric formula evaluates at the default", () => {
    for (const s of inv.scenarios) {
      const vars = Object.fromEntries(s.constants.map((c) => [c.key, c.value]));
      const out = evaluateMetrics(s.metrics, { ...vars, [s.parameter.key]: s.parameter.default });
      for (const m of s.metrics) expect(Number.isNaN(out[m.key]), `${s.id}.${m.key}`).toBe(false);
    }
  });
});

describe("evidence highlighting and ranking", () => {
  it("locates excerpts tolerant to whitespace and quotes", () => {
    expect(locate("Hello   brave\nnew world", "brave new")).toEqual([8, 17]);
    expect(locate("the customer’s list", "customer's list")).not.toBeNull();
    expect(locate("nothing here", "absent text")).toBeNull();
  });
  it("re-ranks by weight", () => {
    const fs = [
      { id: "A", impact: 90, confidence: 10 },
      { id: "B", impact: 40, confidence: 95 },
    ] as never[];
    expect(rerank(fs, 1).map((f: { id: string }) => f.id)).toEqual(["A", "B"]);
    expect(rerank(fs, 0).map((f: { id: string }) => f.id)).toEqual(["B", "A"]);
  });
});
