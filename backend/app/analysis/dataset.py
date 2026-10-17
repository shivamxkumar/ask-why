"""Deterministic dataset profiler.

`analyze_table(columns, rows)` takes raw string cells (header excluded) and returns a `TableAnalysis` that
carries the schema-level `DatasetProfile` plus the detail the parsers and heuristics need (missing rows,
sentinels, out-of-range rows, label variants, cross-column issues) and the exact sentences used for the
`dataset_stat` evidence units. Every sentence is a pure function of the data, so re-running the analysis on
the same rows always yields the same text.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from app.schemas import ColumnProfile, DatasetProfile

MISSING_TOKENS = {"", "na", "n/a", "null", "none", "nan", "#n/a"}
SENTINELS = {9999.0, 99999.0, 999999.0, -999.0, -9999.0, -99999.0}
COMPASS = ("north", "south", "east", "west")
MONEY_NAME = re.compile(r"(fee|price|amount|revenue|mrr|arr|arpu|cost|usd|eur|gbp|salary|spend|budget|paid_amount)", re.I)
PAID_STATUS = {"paid", "active", "subscribed", "paying", "customer", "converted"}
LIST_LIMIT = 10

_NUM = re.compile(r"^([-+]?)\s*([$€£])?\s*([-+]?)(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d*\.?\d+(?:[eE][-+]?\d+)?)\s*(%)?\s*(usd|eur|gbp)?$", re.I)
_DATE_PATTERNS = [
    re.compile(r"^\d{4}-\d{1,2}(-\d{1,2})?([ T]\d{1,2}:\d{2}(:\d{2}(\.\d+)?)?)?$"),
    re.compile(r"^\d{1,2}[/.]\d{1,2}[/.]\d{2,4}$"),
    re.compile(r"^(\d{1,2}\s+)?(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?,?\s+(\d{1,2},?\s+)?\d{4}$", re.I),
    re.compile(r"^q[1-4]\s+\d{4}$", re.I),
]
_BOOL = {"true", "false", "yes", "no", "y", "n", "t", "f"}


def slugify(name: str) -> str:
    """lowercase, runs of non-alphanumerics → '-', trimmed (shared by sheet and column slugs)."""
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return s or "x"


def fmt_num(x: float) -> str:
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "n/a"
    if abs(x - round(x)) < 1e-9:
        return str(int(round(x)))
    return f"{x:.2f}".rstrip("0").rstrip(".")


def parse_numeric(raw: str) -> tuple[Optional[float], bool, bool]:
    """→ (value, had_currency_or_separators, had_percent). Accepts '$1,200', '35%', '(500)', '1.2e3'."""
    s = raw.strip()
    neg = False
    if s.startswith("(") and s.endswith(")"):
        neg, s = True, s[1:-1].strip()
    m = _NUM.match(s)
    if not m:
        return None, False, False
    sign1, cur, sign2, num, pct, code = m.groups()
    try:
        v = float(num.replace(",", ""))
    except ValueError:
        return None, False, False
    if "-" in (sign1 or "") + (sign2 or "") or neg:
        v = -v
    return v, bool(cur or code or "," in num), bool(pct)


def is_missing(v: str) -> bool:
    return v.strip().lower() in MISSING_TOKENS


def _is_date(v: str) -> bool:
    return any(p.match(v.strip()) for p in _DATE_PATTERNS)


def _rows_list(rows: list[int], values: Optional[dict[int, str]] = None) -> str:
    shown = rows[:LIST_LIMIT]
    parts = [f"{r} ({values[r]})" if values else str(r) for r in shown]
    s = ", ".join(parts)
    if len(rows) > LIST_LIMIT:
        s += f" and {len(rows) - LIST_LIMIT} more"
    return s


def _words(label: str) -> list[str]:
    out: list[str] = []
    for w in re.split(r"[^A-Za-z0-9]+", label):
        if not w:
            continue
        parts = re.findall(r"[A-Z]+(?![a-z])|[A-Z]?[a-z]+|\d+", w) or [w]
        for p in parts:
            lw = p.lower()
            split = next((c for c in COMPASS if lw.startswith(c) and lw[len(c):] in COMPASS), None)
            out.extend([split, lw[len(split):]] if split else [lw])
    return out


def _variant_groups(counts: dict[str, int]) -> list[list[tuple[str, int]]]:
    labels = sorted(counts)
    parent = {l: l for l in labels}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)

    by_key: dict[str, str] = {}
    for l in labels:
        key = re.sub(r"[^a-z0-9]", "", l.lower())
        if not key:
            continue
        if key in by_key:
            union(by_key[key], l)
        else:
            by_key[key] = l
    initials = {l: "".join(w[0] for w in _words(l)).upper() for l in labels if len(_words(l)) >= 2}
    for l in labels:
        abbr = re.sub(r"[\s.]", "", l)
        if 2 <= len(abbr) <= 4 and abbr.isalpha() and abbr.isupper():
            for other, ini in initials.items():
                if other != l and ini == abbr:
                    union(l, other)
    groups: dict[str, list[tuple[str, int]]] = {}
    for l in labels:
        groups.setdefault(find(l), []).append((l, counts[l]))
    out = [sorted(g, key=lambda t: (-t[1], t[0])) for g in groups.values() if len(g) >= 2]
    return sorted(out, key=lambda g: (-sum(c for _, c in g), g[0][0]))


@dataclass
class ColumnAnalysis:
    name: str
    slug: str
    dtype: str
    missing_rows: list[int]
    unique: int
    values: dict[int, str]  # row -> raw (non-missing) value
    numeric: dict[int, float] = field(default_factory=dict)
    stats: Optional[dict[str, float]] = None
    top_values: list[tuple[str, int]] = field(default_factory=list)
    iqr_outliers: list[int] = field(default_factory=list)
    sentinel_rows: list[int] = field(default_factory=list)
    range_rows: list[int] = field(default_factory=list)
    expected_range: Optional[tuple[float, float]] = None
    variant_groups: list[list[tuple[str, int]]] = field(default_factory=list)
    currency: bool = False
    percent: bool = False
    sentences: dict[str, str] = field(default_factory=dict)  # ordered: key -> sentence
    profile: Optional[ColumnProfile] = None

    @property
    def text(self) -> str:
        return " ".join(self.sentences.values())


@dataclass
class CrossIssue:
    kind: str  # "paid_zero"
    status_column: str
    amount_column: str
    rows: list[int]
    sentence: str


@dataclass
class TableAnalysis:
    rows: int
    columns: list[str]
    duplicate_rows: list[int]
    duplicate_of: dict[int, int]
    column_analyses: list[ColumnAnalysis]
    cross_issues: list[CrossIssue]
    sentences: dict[str, str]
    profile: DatasetProfile

    @property
    def text(self) -> str:
        return " ".join(self.sentences.values())

    def column(self, name: str) -> Optional[ColumnAnalysis]:
        return next((c for c in self.column_analyses if c.name == name), None)


def _name_tokens(name: str) -> set[str]:
    return set(_words(name)) | set(re.split(r"[^a-z0-9]+", name.lower()))


def _analyze_column(name: str, col: list[str], n_rows: int, nums: list[int]) -> ColumnAnalysis:
    values = {nums[i]: v.strip() for i, v in enumerate(col) if not is_missing(v)}
    missing_rows = [nums[i] for i, v in enumerate(col) if is_missing(v)]
    nonmissing = list(values.values())
    counts: dict[str, int] = {}
    for v in nonmissing:
        counts[v] = counts.get(v, 0) + 1
    ca = ColumnAnalysis(name=name, slug=slugify(name), dtype="empty", missing_rows=missing_rows, unique=len(counts), values=values)
    ca.top_values = sorted(counts.items(), key=lambda t: (-t[1], t[0]))[:5]

    if nonmissing:
        parsed = {r: parse_numeric(v) for r, v in values.items()}
        ok = {r: p[0] for r, p in parsed.items() if p[0] is not None}
        lower = {v.lower() for v in nonmissing}
        if lower <= _BOOL and len(lower) <= 2:
            ca.dtype = "boolean"
        elif len(ok) >= 0.95 * len(nonmissing):
            ca.dtype = "numeric"
            ca.numeric = ok
            ca.currency = any(p[1] for p in parsed.values())
            ca.percent = any(p[2] for p in parsed.values())
        elif sum(_is_date(v) for v in nonmissing) >= 0.95 * len(nonmissing):
            ca.dtype = "date"
        elif len(counts) <= 50 and len(counts) <= max(2, 0.5 * len(nonmissing)):
            ca.dtype = "categorical"
        else:
            ca.dtype = "text"

    pct_missing = round(100.0 * len(missing_rows) / n_rows, 1) if n_rows else 0.0
    s = ca.sentences
    s["summary"] = f"Column {name}: {ca.dtype}, {ca.unique} unique values, {len(missing_rows)} missing ({pct_missing:.1f}%)."
    if missing_rows:
        s["missing"] = f"Missing in rows {_rows_list(missing_rows)}."

    if ca.dtype == "numeric" and ca.numeric:
        rows_sorted = sorted(ca.numeric)
        arr = np.array([ca.numeric[r] for r in rows_sorted], dtype=float)
        q1, med, q3 = (float(x) for x in np.percentile(arr, [25, 50, 75]))
        ca.stats = {
            "min": float(arr.min()), "max": float(arr.max()), "mean": float(arr.mean()), "median": med,
            "std": float(arr.std(ddof=1)) if len(arr) > 1 else 0.0, "q1": q1, "q3": q3,
        }
        s["stats"] = (
            f"Values: min {fmt_num(ca.stats['min'])}, median {fmt_num(med)}, "
            f"mean {fmt_num(round(ca.stats['mean'], 2))}, max {fmt_num(ca.stats['max'])}."
        )
        zeros = [r for r in rows_sorted if ca.numeric[r] == 0]
        if zeros and len(zeros) >= 0.1 * len(arr) and len(zeros) < len(arr):
            nz = np.array([ca.numeric[r] for r in rows_sorted if ca.numeric[r] != 0])
            s["nonzero"] = f"Excluding zeros: n={len(nz)}, median {fmt_num(float(np.median(nz)))}, mean {fmt_num(round(float(nz.mean()), 2))}."
        nonneg_others = all(v >= 0 for v in arr if v != -1)
        ca.sentinel_rows = [
            r for r in rows_sorted
            if ca.numeric[r] in SENTINELS or (ca.numeric[r] == -1 and nonneg_others and (arr != -1).any())
        ]
        iqr = q3 - q1
        if iqr > 0:
            lo, hi = q1 - 3 * iqr, q3 + 3 * iqr
            ca.iqr_outliers = [r for r in rows_sorted if ca.numeric[r] < lo or ca.numeric[r] > hi]
        raw = {r: values[r] for r in rows_sorted}
        if ca.sentinel_rows:
            sv = sorted({fmt_num(ca.numeric[r]) for r in ca.sentinel_rows})
            s["sentinel"] = f"Possible sentinel values ({', '.join(sv)}) in rows {_rows_list(ca.sentinel_rows, raw)}."
        if ca.iqr_outliers:
            s["outliers"] = f"IQR outliers (k=3): rows {_rows_list(ca.iqr_outliers, raw)}."
        toks = _name_tokens(name)
        if toks & {"nps", "score", "rating", "csat"} and ca.stats["max"] <= 11:
            ca.expected_range = (0.0, 10.0)
        elif toks & {"pct", "percent", "percentage", "rate"} or name.strip().endswith("%"):
            inside = sum(1 for v in arr if 0 <= v <= 100)
            if inside >= 0.9 * len(arr) and ca.stats["max"] > 1:
                ca.expected_range = (0.0, 100.0)
        if ca.expected_range:
            lo_r, hi_r = ca.expected_range
            ca.range_rows = [r for r in rows_sorted if not (lo_r <= ca.numeric[r] <= hi_r) and r not in ca.sentinel_rows]
            if ca.range_rows:
                s["range"] = f"Out of expected range {fmt_num(lo_r)}–{fmt_num(hi_r)}: rows {_rows_list(ca.range_rows, raw)}."
        if ca.currency:
            s["currency"] = "Values contain currency symbols or thousands separators and were parsed as numbers."
    elif ca.dtype in ("categorical", "boolean"):
        listed = sorted(counts.items(), key=lambda t: (-t[1], t[0])) if len(counts) <= 24 else ca.top_values
        s["top"] = "Top values: " + ", ".join(f"{v} ({c})" for v, c in listed) + "."
        if ca.dtype == "categorical":
            ca.variant_groups = _variant_groups(counts)
            if ca.variant_groups:
                txt = "; ".join(" / ".join(f"{l} ({c})" for l, c in g) for g in ca.variant_groups)
                s["variants"] = f"Inconsistent labels that likely mean the same category: {txt}."
    elif ca.dtype == "date":
        iso = sorted(v for v in nonmissing if _DATE_PATTERNS[0].match(v))
        if iso:
            s["range"] = f"Range: {iso[0]} to {iso[-1]}."
        if len(counts) <= 24:
            s["counts"] = "Counts: " + ", ".join(f"{v} ({c})" for v, c in sorted(counts.items())) + "."

    outlier_rows = sorted(set(ca.iqr_outliers) | set(ca.sentinel_rows) | set(ca.range_rows))
    ca.profile = ColumnProfile(
        name=name, dtype=ca.dtype, missing=len(missing_rows), missing_pct=pct_missing, unique=ca.unique,  # type: ignore[arg-type]
        stats={k: round(v, 4) for k, v in ca.stats.items()} if ca.stats else None,
        top_values=ca.top_values, outlier_rows=outlier_rows,
        category_variants=[[l for l, _ in g] for g in ca.variant_groups],
    )
    return ca


def _cross_issues(cols: list[ColumnAnalysis]) -> list[CrossIssue]:
    out: list[CrossIssue] = []
    status_cols = [c for c in cols if c.dtype == "categorical" and any(v.lower() in PAID_STATUS for v, _ in c.top_values)]
    money_cols = [c for c in cols if c.dtype == "numeric" and MONEY_NAME.search(c.name)]
    for sc in status_cols:
        paid_labels = sorted({v for v in sc.values.values() if v.lower() in PAID_STATUS})
        for mc in money_cols:
            rows = sorted(r for r, v in sc.values.items() if v.lower() in PAID_STATUS and mc.numeric.get(r) == 0)
            if rows:
                lbl = "/".join(paid_labels)
                out.append(CrossIssue(
                    kind="paid_zero", status_column=sc.name, amount_column=mc.name, rows=rows,
                    sentence=f"{len(rows)} rows have {sc.name} = {lbl} but {mc.name} = 0 (rows {_rows_list(rows)}).",
                ))
    return out


def analyze_table(columns: list[str], rows: list[list[str]], sheet: Optional[str] = None,
                  row_numbers: Optional[list[int]] = None) -> TableAnalysis:
    """row_numbers: the 1-based data-row number of each row (defaults to 1..n)."""
    n = len(rows)
    nums = row_numbers or list(range(1, n + 1))
    width = len(columns)
    norm_rows = [[(r[i] if i < len(r) else "") for i in range(width)] for r in rows]
    seen: dict[tuple, int] = {}
    dups: list[int] = []
    dup_of: dict[int, int] = {}
    for i, r in zip(nums, norm_rows):
        key = tuple(v.strip() for v in r)
        if key in seen:
            dups.append(i)
            dup_of[i] = seen[key]
        else:
            seen[key] = i
    cas = [_analyze_column(name, [r[j] for r in norm_rows], n, nums) for j, name in enumerate(columns)]
    cross = _cross_issues(cas)
    sent: dict[str, str] = {}
    if dups:
        sent["overview"] = f"{n} rows × {width} columns; {len(dups)} rows exactly duplicate an earlier row (rows {_rows_list(dups)})."
    else:
        sent["overview"] = f"{n} rows × {width} columns; no rows exactly duplicate an earlier row."
    miss = [c for c in cas if c.missing_rows and c.dtype != "empty"]
    if miss:
        sent["missing"] = "Columns with missing values: " + ", ".join(f"{c.name} ({len(c.missing_rows)})" for c in miss) + "."
    empty = [c.name for c in cas if c.dtype == "empty"]
    if empty:
        sent["empty"] = "Entirely empty columns: " + ", ".join(empty) + "."
    for i, ci in enumerate(cross):
        sent[f"cross{i}"] = ci.sentence
    profile = DatasetProfile(
        sheet=sheet, rows=n, columns=width, duplicate_rows=dups, column_profiles=[c.profile for c in cas if c.profile]
    )
    return TableAnalysis(rows=n, columns=list(columns), duplicate_rows=dups, duplicate_of=dup_of, column_analyses=cas,
                         cross_issues=cross, sentences=sent, profile=profile)


def row_text(columns: list[str], row: list[str]) -> str:
    return " | ".join(f"{c}: {row[i] if i < len(row) else ''}" for i, c in enumerate(columns))


def parse_row_text(text: str, columns: list[str]) -> list[str]:
    """Inverse of row_text using the known ordered column names."""
    vals: list[str] = []
    rest = text
    for i, c in enumerate(columns):
        prefix = f"{c}: "
        if rest.startswith(prefix):
            rest = rest[len(prefix):]
        elif rest.startswith(f"{c}:"):
            rest = rest[len(c) + 1:]
        if i + 1 < len(columns):
            sep = f" | {columns[i + 1]}:"
            idx = rest.find(sep)
            if idx < 0:
                vals.append(rest)
                rest = ""
                continue
            vals.append(rest[:idx])
            rest = rest[idx + 3:]
        else:
            vals.append(rest)
    return vals
