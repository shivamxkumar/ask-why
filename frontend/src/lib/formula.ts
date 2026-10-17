// Tiny, safe arithmetic evaluator for scenario metrics (no eval).
// Grammar: expr := term (("+"|"-") term)* ; term := power (("*"|"/") power)* ;
//          power := unary ("^" power)? ; unary := "-" unary | primary ;
//          primary := number | ident | ident "(" args ")" | "(" expr ")"

const FUNCS: Record<string, (...a: number[]) => number> = {
  min: Math.min,
  max: Math.max,
  log: Math.log10,
  ln: Math.log,
  ceil: Math.ceil,
  floor: Math.floor,
  abs: Math.abs,
  round: Math.round,
};

type Tok = { t: "num"; v: number } | { t: "id"; v: string } | { t: "op"; v: string };

function tokenize(src: string): Tok[] {
  const out: Tok[] = [];
  let i = 0;
  while (i < src.length) {
    const c = src[i];
    if (/\s/.test(c)) {
      i++;
    } else if (/[0-9.]/.test(c)) {
      const m = /^[0-9]*\.?[0-9]+(e[+-]?[0-9]+)?/i.exec(src.slice(i));
      if (!m) throw new Error(`Bad number at ${i}`);
      out.push({ t: "num", v: parseFloat(m[0]) });
      i += m[0].length;
    } else if (/[a-z_]/i.test(c)) {
      const m = /^[a-z_][a-z0-9_]*/i.exec(src.slice(i))!;
      out.push({ t: "id", v: m[0] });
      i += m[0].length;
    } else if ("+-*/^(),".includes(c)) {
      out.push({ t: "op", v: c });
      i++;
    } else {
      throw new Error(`Unexpected '${c}'`);
    }
  }
  return out;
}

export function evaluate(formula: string, vars: Record<string, number>): number {
  const toks = tokenize(formula);
  let p = 0;
  const peek = () => toks[p];
  const isOp = (v: string) => peek()?.t === "op" && peek()!.v === v;
  const expect = (v: string) => {
    if (!isOp(v)) throw new Error(`Expected '${v}'`);
    p++;
  };
  const expr = (): number => {
    let v = term();
    while (isOp("+") || isOp("-")) {
      const op = toks[p++].v;
      const r = term();
      v = op === "+" ? v + r : v - r;
    }
    return v;
  };
  const term = (): number => {
    let v = power();
    while (isOp("*") || isOp("/")) {
      const op = toks[p++].v;
      const r = power();
      v = op === "*" ? v * r : v / r;
    }
    return v;
  };
  const power = (): number => {
    const b = unary();
    if (isOp("^")) {
      p++;
      return Math.pow(b, power());
    }
    return b;
  };
  const unary = (): number => {
    if (isOp("-")) {
      p++;
      return -unary();
    }
    return primary();
  };
  const primary = (): number => {
    const tk = toks[p++];
    if (!tk) throw new Error("Unexpected end");
    if (tk.t === "num") return tk.v;
    if (tk.t === "id") {
      if (isOp("(")) {
        p++;
        const fn = FUNCS[tk.v];
        if (!fn) throw new Error(`Unknown function ${tk.v}`);
        const args: number[] = [];
        if (!isOp(")")) {
          args.push(expr());
          while (isOp(",")) {
            p++;
            args.push(expr());
          }
        }
        expect(")");
        return fn(...args);
      }
      if (!(tk.v in vars)) throw new Error(`Unknown variable ${tk.v}`);
      return vars[tk.v];
    }
    if (tk.v === "(") {
      const v = expr();
      expect(")");
      return v;
    }
    throw new Error(`Unexpected '${tk.v}'`);
  };
  const v = expr();
  if (p !== toks.length) throw new Error("Trailing input");
  return v;
}

/** Evaluate metrics in order; later metrics may reference earlier ones. Errors become NaN. */
export function evaluateMetrics(
  metrics: { key: string; formula: string }[],
  base: Record<string, number>,
): Record<string, number> {
  const vars = { ...base };
  const out: Record<string, number> = {};
  for (const m of metrics) {
    let v: number;
    try {
      v = evaluate(m.formula, vars);
    } catch {
      v = NaN;
    }
    out[m.key] = v;
    vars[m.key] = v;
  }
  return out;
}
