"""Deterministic Blind Spot Radar, Contradiction Lab and dataset checks — no LLM involved.

Everything here is pattern-based: cue phrases, number/date/money extraction and keyword overlap. Each finding
quotes a verbatim sentence (or a full table row / profile sentence) from a real evidence unit.

Factor rules (impact / confidence are computed later by app.analysis.scoring from these factors):
  consequence        contradiction on money/date/headcount 80, other contradiction 70, requirement conflict 75,
                     dependency 70 (+10 when "no fallback" is stated), money/% assumption 70, count 65, date 60,
                     rationale (non-numeric) 60, coverage gap 50–60, data quality 40–60 by issue type.
  decision_relevance 80 when the finding touches a budget, date, price or headcount figure; 70 for requirement
                     and dependency findings; 45–60 for data quality; 50–60 for gaps.
  breadth            20 + 20 × distinct sources cited (cap 90); data quality: share of affected rows scaled.
  evidence_strength  direct verbatim quotes on both sides 85; quoted assumption 75; dependency 70 (+10 explicit
                     "no fallback"); computed dataset statistic 90; inference (gaps, open questions) ≤ 45.
  specificity        numbers 80, dates 75, statements without figures 45; dataset 85.
  corroboration      20 + 25 × (distinct sources − 1), cap 90; dataset statistics 60 (single source, computed).
"""
from __future__ import annotations

import calendar
import re
from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from app.analysis.dataset import TableAnalysis, analyze_table, fmt_num, parse_numeric, parse_row_text, MONEY_NAME
from app.schemas import (
    Calculation, Citation, Claim, ComparisonRow, ConfidenceFactors, Contradiction, EvidenceConclusion, EvidenceUnit,
    Finding, ImpactFactors, Scenario, ScenarioConstant, ScenarioMetric, ScenarioParameter, Source,
)

# ---------------------------------------------------------------- cue patterns
I = re.I
ASSUMPTION_RE = re.compile(
    r"\b(assum\w*|expect\w*|should|will likely|likely to|estimat\w*|projected|projections?|forecast\w*|"
    r"targets?|targeted|goals?|plans? to|planned to|anticipat\w*|believe\w*)\b", I)
SOFT_RE = re.compile(r"\b(generally|typically|usually|most|close to|loves?|always|never|everyone|surely|obviously)\b", I)
RATIONALE_RE = re.compile(r"\b(because|since|so|as a result|therefore)\b", I)
CONSTRAINT_RE = re.compile(r"\b(must|required|requires?|P0|deadline|no more than|at least|at most|limits?|limited|SLA|"
                           r"maximum|minimum|cap(ped)?)\b", I)
DEPENDENCY_RE = re.compile(r"\b(provided by|relies on|rely on|depends? on|dependent on|via|through|third[- ]party|vendors?|"
                           r"API|integrations?|partners?(hip)?|powered by|suppliers?|providers?)\b", I)
CONTINGENCY_RE = re.compile(r"\b(fallback|fall back|contingency|backup|plan b|mitigat\w*|workaround|alternatives?)\b|"
                            r"\bif\b[^.]{0,60}\bfails?\b", I)
NEG_CONTINGENCY_RE = re.compile(r"\b(no|without|not|lack of|none)\b[^.]{0,40}\b(fallback|contingency|backup|plan b|"
                                r"alternatives?|mitigation)\b", I)
DEFERRAL_RE = re.compile(r"\b(deferred|defer|out of scope|not included|not in scope|won't|will not|online-only|excluded|"
                         r"postponed|descoped|not supported)\b", I)
REQUIRED_RE = re.compile(r"\b(must|required|P0|mandatory|critical requirement)\b", I)
INCLUSION_RE = re.compile(r"\b(covering|covers|includes|including|in scope|comprises)\b", I)
EVIDENCE_RE = re.compile(r"\b(reported|interviews?|surveys?|surveyed|measured|observed|according to|found that|data shows?|"
                         r"\d+ of \d+|study|benchmark\w*)\b", I)
TARGET_SECTION_RE = re.compile(r"goal|objective|target|kpi|success|okr", I)
LAUNCH_RE = re.compile(r"\b(launch\w*|release[sd]?|go[- ]live|general availability|ship date|rollout|deadline)\b|\bGA\b", I)
LAUNCH_STRONG = re.compile(r"\b(launch\w*|go[- ]live|general availability)\b|\bGA\b", I)
DOCDATE_RE = re.compile(r"\b(last updated|updated|dated|as of|revised|approved|prepared|status)\b", I)
VERSION_RE = re.compile(r"\b(?:version\s+(\d+(?:\.\d+)*)|v(\d+\.\d+(?:\.\d+)?))\b", I)

MONTHS = {m.lower(): i for i, m in enumerate(calendar.month_name) if m}
MONTHS.update({m.lower(): i for i, m in enumerate(calendar.month_abbr) if m})
MONTHS["sept"] = 9
_MON = r"(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|June?|July?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
DATE_DMY = re.compile(rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+{_MON}\.?,?\s+(\d{{4}})\b", I)
DATE_MDY = re.compile(rf"\b{_MON}\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?,\s+(\d{{4}})\b", I)
DATE_MY = re.compile(rf"\b{_MON}\.?\s+(\d{{4}})\b", I)
DATE_ISO = re.compile(r"\b(20\d{2}|19\d{2})-(\d{2})-(\d{2})\b")
DATE_Q = re.compile(r"\b(Q[1-4])\s*(?:FY\s*)?'?(\d{4})\b", I)
MONEY_RE = re.compile(r"(?<![\w$€£])(US\$|[$€£]|USD\s?|EUR\s?|GBP\s?)(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)\s?"
                      r"(k|K|M|bn|BN|B|million|billion|thousand)?(?![\w])")
PCT_RE = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)\s?(%|percent\b|per cent\b)", I)
COUNT_NOUNS = (r"accounts?|customers?|clients?|users?|engineers?|developers?|designers?|technicians?|people|persons?|staff|"
               r"FTEs?|employees?|managers?|stores?|sites?|locations?|seats?|licen[cs]es?|subscribers?|members?|requests?|"
               r"stops?|calls?|tickets?|jobs?|orders?|hires?|contractors?")
COUNT_RE = re.compile(rf"(?<![\w.$€£,])(\d{{1,3}}(?:,\d{{3}})+|\d+)\s+((?:[A-Za-z][\w-]*\s+){{0,2}}?)({COUNT_NOUNS})\b", I)
WORDNUM = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
           "eleven": 11, "twelve": 12}
WORDCOUNT_RE = re.compile(r"\b(one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)[- ](person|people|member|engineer)s?\b", I)
SCOPE_WORDS = [
    ("general availability", "general availability"), (r"\bGA\b", "general availability"), ("public", "public"),
    ("beta", "beta"), ("feature-complete", "feature-complete"), ("pilot", "pilot"), ("soft launch", "soft launch"),
    ("internal", "internal"), ("limited", "limited"), ("total", "total"), ("excluding", "excluding"),
    ("including", "including"), ("net", "net"), ("gross", "gross"), ("month-over-month", "monthly"), ("monthly", "monthly"),
    (r"\bMoM\b", "monthly"), ("year-over-year", "annual"), ("annual", "annual"), (r"\bYoY\b", "annual"), ("weekly", "weekly"),
]
EXCLUSIVE_SCOPES = {"excluding", "net"}
STOP = set("""a an the and or of to in on for by with from at as is are was were be been being this that these those it its
we our you your they their will would should could can may might must not no yes than then so such per each every all any
some more most less least very also only just into over under about after before during within without between up down
out off again further once here there when where why how what which who whom whose because while until if else both few
other same own too has have had having do does did doing plan plans project team account accounts customer customers
new first year month months week weeks day days time support""".split())

MAX_ASSUMPTIONS = 6
MAX_CONTRADICTIONS_PER_KEY = 3
MAX_DEPENDENCIES = 3
MAX_GAPS = 3


# ---------------------------------------------------------------- extracted values
@dataclass
class Val:
    kind: str  # money | pct | date | count
    value: float  # money/pct/count value; for dates the ordinal of the interval start
    raw: str
    start: int
    unit: str = ""
    end_value: float = 0.0  # dates: ordinal of interval end
    precision: str = ""  # dates: day | month | quarter
    noun: str = ""


@dataclass
class Sent:
    unit: EvidenceUnit
    source: Source
    text: str
    is_row: bool = False
    cues: set[str] = field(default_factory=set)
    vals: list[Val] = field(default_factory=list)

    @property
    def context(self) -> str:
        return f"{self.text} {self.unit.section or ''}" if self.is_row else self.text


@dataclass
class MetricClaim:
    key: str
    val: Val
    sent: Sent
    strength: int
    scopes: set[str]


@dataclass
class Draft:
    finding: Finding
    keys: set[str] = field(default_factory=set)  # metric keys / brand names for relatedness


# ---------------------------------------------------------------- helpers
_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(“‘])")
_SHORT_LEAD = re.compile(r"^(Step\s+\d+|R-\d+|\d+|[A-Z])\.$|^(e\.g|i\.e|vs|approx|No|Fig)\.$", I)


def split_sentences(text: str) -> list[str]:
    spans: list[list[int]] = []
    pos = 0
    for m in _SPLIT.finditer(text):
        spans.append([pos, m.start()])
        pos = m.end()
    spans.append([pos, len(text)])
    merged: list[list[int]] = []
    for s in spans:
        if merged:
            prev = text[merged[-1][0]:merged[-1][1]].strip()
            if len(prev) < 12 or _SHORT_LEAD.match(prev):
                merged[-1][1] = s[1]
                continue
        merged.append(s)
    return [text[a:b].strip() for a, b in merged if text[a:b].strip()]


def _short(text: str, n: int = 90) -> str:
    text = " ".join(text.split())
    return text if len(text) <= n else text[: n - 1].rstrip(" ,;:") + "…"


def _month_end(y: int, m: int) -> date:
    return date(y, m, calendar.monthrange(y, m)[1])


def _date_val(y: int, m: int, d: Optional[int], raw: str, start: int, precision: str, m_end: Optional[int] = None) -> Optional[Val]:
    try:
        a = date(y, m, d or 1)
        b = date(y, m, d) if d else _month_end(y, m_end or m)
    except ValueError:
        return None
    return Val("date", a.toordinal(), raw, start, unit="date", end_value=b.toordinal(), precision=precision)


def extract_values(text: str) -> list[Val]:
    vals: list[Val] = []
    taken: list[tuple[int, int]] = []

    def free(a: int, b: int) -> bool:
        return all(b <= x or a >= y for x, y in taken)

    for m in DATE_DMY.finditer(text):
        v = _date_val(int(m.group(3)), MONTHS[m.group(2).lower()[:3]], int(m.group(1)), m.group(0), m.start(), "day")
        if v:
            vals.append(v); taken.append(m.span())
    for m in DATE_MDY.finditer(text):
        if free(*m.span()):
            v = _date_val(int(m.group(3)), MONTHS[m.group(1).lower()[:3]], int(m.group(2)), m.group(0), m.start(), "day")
            if v:
                vals.append(v); taken.append(m.span())
    for m in DATE_ISO.finditer(text):
        if free(*m.span()):
            v = _date_val(int(m.group(1)), int(m.group(2)), int(m.group(3)), m.group(0), m.start(), "day")
            if v:
                vals.append(v); taken.append(m.span())
    for m in DATE_MY.finditer(text):
        if free(*m.span()):
            v = _date_val(int(m.group(2)), MONTHS[m.group(1).lower()[:3]], None, m.group(0), m.start(), "month")
            if v:
                vals.append(v); taken.append(m.span())
    for m in DATE_Q.finditer(text):
        if free(*m.span()):
            q = int(m.group(1)[1])
            v = _date_val(int(m.group(2)), 3 * q - 2, None, m.group(0), m.start(), "quarter", m_end=3 * q)
            if v:
                vals.append(v); taken.append(m.span())
    for m in MONEY_RE.finditer(text):
        num = float(m.group(2).replace(",", ""))
        suf = (m.group(3) or "").lower()
        mult = {"k": 1e3, "thousand": 1e3, "m": 1e6, "million": 1e6, "b": 1e9, "bn": 1e9, "billion": 1e9}.get(suf, 1)
        cur = {"$": "USD", "us$": "USD", "usd": "USD", "€": "EUR", "eur": "EUR", "£": "GBP", "gbp": "GBP"}[m.group(1).strip().lower()]
        vals.append(Val("money", num * mult, m.group(0).strip(), m.start(), unit=cur)); taken.append(m.span())
    for m in PCT_RE.finditer(text):
        if free(*m.span()):
            vals.append(Val("pct", float(m.group(1)), m.group(0), m.start(), unit="%")); taken.append(m.span())
    for m in COUNT_RE.finditer(text):
        if free(*m.span()):
            vals.append(Val("count", float(m.group(1).replace(",", "")), m.group(0), m.start(), unit=m.group(3).lower(),
                            noun=(m.group(2) + m.group(3)).lower())); taken.append(m.span())
    for m in WORDCOUNT_RE.finditer(text):
        if free(*m.span()):
            vals.append(Val("count", float(WORDNUM[m.group(1).lower()]), m.group(0), m.start(), unit=m.group(2).lower(),
                            noun=m.group(2).lower()))
    return sorted(vals, key=lambda v: v.start)


def _row_values(text: str) -> list[Val]:
    """Values from a 'col: value | col: value' row (cells parsed individually, so headers type bare numbers)."""
    vals: list[Val] = []
    pos = 0
    for part in text.split(" | "):
        col, _, cell = part.partition(": ")
        start = pos + len(col) + 2
        pos += len(part) + 3
        cell_s = cell.strip()
        if not cell_s:
            continue
        num, cur, pct = parse_numeric(cell_s)
        if num is not None:
            if pct:
                vals.append(Val("pct", num, cell_s, start, unit="%"))
            elif cur or MONEY_NAME.search(col) or "$" in col:
                unit = "EUR" if ("€" in cell_s or "eur" in col.lower()) else "GBP" if ("£" in cell_s or "gbp" in col.lower()) else "USD"
                vals.append(Val("money", num, cell_s, start, unit=unit))
            else:
                vals.append(Val("count", num, cell_s, start, unit="", noun=col.lower()))
            continue
        for v in extract_values(cell_s):
            v.start += start
            vals.append(v)
    return vals


def _cues(text: str, section: str) -> set[str]:
    c: set[str] = set()
    if ASSUMPTION_RE.search(text):
        c.add("assumption")
    if SOFT_RE.search(text):
        c.add("soft")
    if RATIONALE_RE.search(text):
        c.add("rationale")
    if CONSTRAINT_RE.search(text):
        c.add("constraint")
    if DEPENDENCY_RE.search(text):
        c.add("dependency")
    if NEG_CONTINGENCY_RE.search(text):
        c.add("no_contingency")
    elif CONTINGENCY_RE.search(text):
        c.add("contingency")
    if DEFERRAL_RE.search(text):
        c.add("deferral")
    if REQUIRED_RE.search(text):
        c.add("required")
    if INCLUSION_RE.search(text):
        c.add("inclusion")
    if EVIDENCE_RE.search(text):
        c.add("evidence")
    if TARGET_SECTION_RE.search(section or ""):
        c.add("target")
    return c


def _scopes(text: str) -> set[str]:
    out = set()
    for pat, label in SCOPE_WORDS:
        if pat.startswith("\\b"):
            if re.search(pat, text):
                out.add(label)
        elif re.search(rf"\b{re.escape(pat)}\b", text, I):
            out.add(label)
    return out


def _tokens(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z][a-z0-9-]{3,}", text.lower()) if w not in STOP}


def _fmt_money(v: float, unit: str = "USD") -> str:
    sym = {"USD": "$", "EUR": "€", "GBP": "£"}.get(unit, "")
    if abs(v) >= 1e6:
        return f"{sym}{v / 1e6:.2f}M".replace(".00M", "M")
    return f"{sym}{v:,.0f}" if v == int(v) else f"{sym}{v:,.2f}"


def _fmt_val(v: Val) -> str:
    if v.kind == "money":
        return _fmt_money(v.value, v.unit)
    if v.kind == "pct":
        return f"{fmt_num(v.value)}%"
    if v.kind == "date":
        return v.raw
    return f"{fmt_num(v.value)}{(' ' + v.unit) if v.unit else ''}"


def _cite(s: Sent, role: str = "support", note: Optional[str] = None, excerpt: Optional[str] = None) -> Citation:
    return Citation(source_id=s.source.id, unit_id=s.unit.id, location_label=s.unit.label, excerpt=excerpt or s.text, role=role, note=note)  # type: ignore[arg-type]


def _ucite(u: EvidenceUnit, excerpt: str, role: str = "support", note: Optional[str] = None) -> Citation:
    return Citation(source_id=u.source_id, unit_id=u.id, location_label=u.label, excerpt=excerpt, role=role, note=note)  # type: ignore[arg-type]


def _breadth(source_ids: set[str]) -> int:
    return min(90, 20 + 20 * len(source_ids))


def _corroboration(source_ids: set[str]) -> int:
    return min(90, 20 + 25 * max(0, len(source_ids) - 1))


# ---------------------------------------------------------------- corpus
class Corpus:
    def __init__(self, sources: list[Source], units: list[EvidenceUnit]):
        self.sources = sources
        self.by_source = {s.id: s for s in sources}
        self.units = units
        self.unit_by_id = {u.id: u for u in units}
        self.sents: list[Sent] = []
        self.doc_meta: dict[str, str] = {}
        csv_sources = {s.id for s in sources if s.kind == "csv"}
        big_sheets: set[tuple[str, str]] = set()
        for s in sources:
            for p in s.profiles:
                if s.kind == "xlsx" and p.rows > 200:
                    big_sheets.add((s.id, p.sheet or ""))
        for u in units:
            src = self.by_source.get(u.source_id)
            if src is None or u.kind == "dataset_stat":
                continue
            if u.kind == "table_row":
                if u.source_id in csv_sources or (u.source_id, u.location.sheet or "") in big_sheets:
                    continue
                st = Sent(u, src, u.text, is_row=True)
                st.cues = _cues(u.text + " " + (u.section or ""), u.section or "")
                if re.search(r"assumption", u.section or "", I):
                    st.cues.add("assumption")
                st.vals = _row_values(u.text)
                self.sents.append(st)
                continue
            for t in split_sentences(u.text):
                st = Sent(u, src, t)
                st.cues = _cues(t, u.section or "")
                st.vals = extract_values(t)
                self.sents.append(st)
        # document date / version per source (first match wins)
        for s in sources:
            meta_date, meta_ver = None, None
            for st in self.sents:
                if st.source.id != s.id or st.is_row:
                    continue
                if meta_ver is None and (m := VERSION_RE.search(st.text)):
                    meta_ver = "v" + (m.group(1) or m.group(2))
                if meta_date is None and DOCDATE_RE.search(st.text):
                    d = next((v for v in st.vals if v.kind == "date"), None)
                    if d:
                        meta_date = d.raw
                if meta_date and meta_ver:
                    break
            parts = [p for p in (meta_ver, f"dated {meta_date}" if meta_date else None) if p]
            self.doc_meta[s.id] = " · ".join(parts) if parts else "not stated"
        self.token_df: dict[str, int] = {}
        for u in units:
            if u.kind != "dataset_stat":
                for t in _tokens(u.text):
                    self.token_df[t] = self.token_df.get(t, 0) + 1
        self.all_text = "\n".join(u.text for u in units if u.kind != "table_row" or u.source_id not in csv_sources)

    def rare_shared(self, a: str, b: str, max_df: int = 4) -> list[str]:
        shared = _tokens(a) & _tokens(b)
        return sorted((t for t in shared if self.token_df.get(t, 0) <= max_df), key=lambda t: (self.token_df.get(t, 0), t))


# ---------------------------------------------------------------- metric keys (contradiction lab)
def _nearest(text: str, pattern: re.Pattern, pos: int, window: int = 80) -> Optional[int]:
    best = None
    for m in pattern.finditer(text):
        d = min(abs(m.start() - pos), abs(m.end() - pos))
        if d <= window and (best is None or d < best):
            best = d
    return best


PRICE_RE = re.compile(r"\b(price[sd]?|pricing|ARPU|average revenue per|per (?:account|user|seat|customer|location) per month|per month|/month|monthly fee|subscription fee)\b", I)
REVENUE_RE = re.compile(r"\b(ARR|MRR|annual recurring revenue|monthly recurring revenue|revenue)\b", I)
BUDGET_RE = re.compile(r"\bbudget\b|\btotal cost\b|\bproject cost\b", I)
TOTAL_RE = re.compile(r"\b(total|overall|approved|entire)\b", I)
GROWTH_RE = re.compile(r"\b(grow\w*|growth)\b", I)
CONVERSION_RE = re.compile(r"\bconver\w*", I)
CHURN_RE = re.compile(r"\bchurn\w*", I)
CAC_RE = re.compile(r"\b(acquisition cost|CAC)\b", I)
ENG_RE = re.compile(r"\b(engineers?|developers?)\b", I)
CS_RE = re.compile(r"\b(customer success|support team|cs team|support staff)\b", I)
PEOPLE_NOUN = re.compile(r"(person|people|members?|managers?|staff|headcount|ftes?|employees?|hires?|value)$", I)

METRIC_LABEL = {
    "launch": "launch / release date", "budget": "total budget", "price": "price per account per month",
    "revenue": "revenue target", "growth": "growth rate", "conversion": "conversion rate", "churn": "churn rate",
    "cac": "customer acquisition cost", "headcount:engineering": "engineering headcount",
    "headcount:customer_success": "customer success headcount", "headcount:design": "design headcount",
    "accounts": "customer / account target",
}
ACCOUNTS_RE = re.compile(r"\b(accounts?|customers?|clients?|users?|subscribers?)$", I)


def metric_claims(sents: list[Sent]) -> list[MetricClaim]:
    out: list[MetricClaim] = []
    for s in sents:
        ctx = s.context
        scopes = _scopes(ctx)
        for v in s.vals:
            key, strength = None, 0
            pos = v.start
            if v.kind == "date":
                d = _nearest(s.text, LAUNCH_RE, pos, 120) if not s.is_row else (0 if LAUNCH_RE.search(ctx) else None)
                if d is not None:
                    key = "launch"
                    strength = 3 if LAUNCH_STRONG.search(ctx) else 2
            elif v.kind == "money":
                cands = []
                for k, pat in (("price", PRICE_RE), ("revenue", REVENUE_RE), ("cac", CAC_RE)):
                    d = _nearest(s.text, pat, pos + len(v.raw)) if not s.is_row else (0 if pat.search(ctx) else None)
                    if d is not None:
                        cands.append((d, k))
                if BUDGET_RE.search(ctx) and TOTAL_RE.search(s.text):
                    cands.append((-1 if s.is_row else 0, "budget"))
                if cands:
                    cands.sort()
                    key = cands[0][1]
                    if key == "revenue" and any(k == "price" for _, k in cands) and s.is_row:
                        key = "price"
                    strength = 2
            elif v.kind == "pct":
                for k, pat in (("growth", GROWTH_RE), ("conversion", CONVERSION_RE), ("churn", CHURN_RE)):
                    if (_nearest(s.text, pat, pos, 100) is not None) if not s.is_row else pat.search(ctx):
                        key, strength = k, 2
                        break
            elif v.kind == "count":
                noun = v.noun
                if ENG_RE.search(noun):
                    key = "headcount:engineering"
                elif re.search(r"designers?$", noun):
                    key = "headcount:design"
                elif PEOPLE_NOUN.search(noun) and (CS_RE.search(ctx) or re.search(r"customer success", ctx, I)):
                    key = "headcount:customer_success"
                if s.is_row and key is None and re.search(r"headcount", ctx, I) and CS_RE.search(ctx):
                    key = "headcount:customer_success"
                if key and s.is_row and re.search(r"\d+\s+months?", ctx) and v.noun.endswith("months"):
                    key = None
                strength = 2 if key else 0
            if key:
                out.append(MetricClaim(key, v, s, strength, scopes))
    return out


def _compare(a: Val, b: Val) -> tuple[bool, str, float]:
    """→ (equal_or_consistent, difference text, relative difference)."""
    if a.kind == "date":
        if a.value <= b.end_value and b.value <= a.end_value:
            return True, "overlapping dates", 0.0
        gap = (b.value - a.end_value) if b.value > a.end_value else (a.value - b.end_value)
        later = "later" if b.value > a.value else "earlier"
        approx = "" if a.precision == b.precision == "day" else "at least "
        return False, f"b is {approx}{int(gap)} day{'s' if gap != 1 else ''} {later} than a", gap
    if a.value == b.value:
        return True, "identical", 0.0
    base = abs(a.value) or 1.0
    rel = (b.value - a.value) / base
    return False, f"{rel * 100:+.1f}% (b vs a)", abs(rel)


def _verdict(a: MetricClaim, b: MetricClaim, rel: float) -> tuple[str, str]:
    if (a.val.kind == "date" and rel <= 3 and a.val.precision == b.val.precision == "day") or (a.val.kind != "date" and rel <= 0.03):
        return "explainable_difference", "The figures differ only marginally (within 3% or 3 days); rounding or timing may explain it."
    sa, sb = a.scopes, b.scopes
    if (sa and sb and not (sa & sb)) or ((sa ^ sb) & EXCLUSIVE_SCOPES):
        return "possible_conflict", (
            f"Both describe the {METRIC_LABEL.get(a.key, a.key)}, but the scope wording differs "
            f"({', '.join(sorted(sa)) or 'none'} vs {', '.join(sorted(sb)) or 'none'}), so they may refer to different milestones or bases."
        )
    return "true_conflict", f"Both statements describe the same {METRIC_LABEL.get(a.key, a.key)} with no qualifier that explains the different values."


# ---------------------------------------------------------------- the engine
class Heuristics:
    def __init__(self, sources: list[Source], units: list[EvidenceUnit]):
        self.c = Corpus(sources, units)
        self.drafts: list[tuple[str, Draft]] = []  # (group, draft)
        self.scenarios: list[Scenario] = []
        self._n = 0
        self.assumption_drafts: list[tuple[Draft, Sent, Optional[Val], Optional[str]]] = []

    def _new(self, group: str, keys: set[str], **kw) -> Draft:
        self._n += 1
        kw.setdefault("origin", "heuristic")
        f = Finding(id=f"tmp{self._n}", **kw)
        d = Draft(f, keys)
        self.drafts.append((group, d))
        return d

    # ---- a. contradictions between figures
    def contradictions(self) -> None:
        claims = metric_claims(self.c.sents)
        by_key: dict[str, list[MetricClaim]] = {}
        for mc in claims:
            by_key.setdefault(mc.key, []).append(mc)
        for key, group in by_key.items():
            # representative claim per source: strongest keyword, then first occurrence
            per_source: dict[str, list[MetricClaim]] = {}
            for mc in group:
                per_source.setdefault(mc.sent.source.id, []).append(mc)
            reps = {sid: sorted(lst, key=lambda m: -m.strength)[0] for sid, lst in per_source.items()}
            pairs: list[tuple[int, MetricClaim, MetricClaim, str, str, str]] = []
            sids = sorted(reps)
            for i, sa in enumerate(sids):
                for sb in sids[i + 1:]:
                    a, b = reps[sa], reps[sb]
                    eq, diff, rel = _compare(a.val, b.val)
                    if eq:
                        continue
                    verdict, reason = _verdict(a, b, rel)
                    pairs.append(({"true_conflict": 0, "possible_conflict": 1}.get(verdict, 2), a, b, verdict, reason, diff))
            # within one source: only same-scope claims with different values are real internal conflicts
            for sid, lst in per_source.items():
                for i, a in enumerate(lst):
                    for b in lst[i + 1:]:
                        if a.sent.unit.id == b.sent.unit.id or a.scopes != b.scopes:
                            continue
                        eq, diff, rel = _compare(a.val, b.val)
                        if not eq:
                            verdict, reason = _verdict(a, b, rel)
                            pairs.append(({"true_conflict": 0, "possible_conflict": 1}.get(verdict, 2) + 0.5, a, b, verdict, reason, diff))
            pairs.sort(key=lambda p: (p[0], p[1].sent.source.id, p[2].sent.source.id))
            for _, a, b, verdict, reason, diff in pairs[:MAX_CONTRADICTIONS_PER_KEY]:
                self._contradiction_finding(key, a, b, verdict, reason, diff)
        self._price_vs_data(by_key.get("price", []))

    def _claim(self, mc: MetricClaim, role: str) -> Claim:
        return Claim(statement=mc.sent.text, value=mc.val.raw, unit=mc.val.unit or None,
                     as_of=self.c.doc_meta.get(mc.sent.source.id), scope=", ".join(sorted(mc.scopes)) or None,
                     citation=_cite(mc.sent, role))

    def _contradiction_finding(self, key: str, a: MetricClaim, b: MetricClaim, verdict: str, reason: str, diff: str) -> None:
        label = METRIC_LABEL.get(key, key)
        na, nb = a.sent.source.name, b.sent.source.name
        same = a.sent.source.id == b.sent.source.id
        units_a = f"{a.val.unit} ({a.val.precision})" if a.val.kind == "date" else (a.val.unit or "count")
        units_b = f"{b.val.unit} ({b.val.precision})" if b.val.kind == "date" else (b.val.unit or "count")
        comparison = [
            ComparisonRow(dimension="Value", a=a.val.raw, b=b.val.raw, note=diff),
            ComparisonRow(dimension="Units", a=units_a, b=units_b, note="" if units_a == units_b else "different precision or unit"),
            ComparisonRow(dimension="Date / version", a=self.c.doc_meta.get(a.sent.source.id, "not stated"),
                          b=self.c.doc_meta.get(b.sent.source.id, "not stated")),
            ComparisonRow(dimension="Scope", a=", ".join(sorted(a.scopes)) or "not stated", b=", ".join(sorted(b.scopes)) or "not stated",
                          note="scope wording differs" if a.scopes != b.scopes else "same scope wording"),
        ]
        owners = f"the authors of {na}" if same else f"the owners of {na} and {nb}"
        resolution = (f"Ask {owners} to confirm which {label} is current and whether the two statements describe the same "
                      f"milestone or basis; record the agreed figure in one place. ASK//WHY does not pick a winner.")
        title_verb = {"true_conflict": "Conflicting", "possible_conflict": "Possibly conflicting", "explainable_difference": "Slightly different"}[verdict]
        where = f"within {na}" if same else f"{na} vs {nb}"
        money_like = key in ("launch", "budget", "price", "revenue", "cac") or key.startswith("headcount")
        cons = 80 if money_like else 70
        if verdict == "explainable_difference":
            cons -= 35
        elif verdict == "possible_conflict":
            cons -= 10
        sids = {a.sent.source.id, b.sent.source.id}
        self._new(
            "contradiction", {key},
            title=f"{title_verb} {label}: {_fmt_val(a.val)} vs {_fmt_val(b.val)}",
            summary=f"{na} gives the {label} as {a.val.raw}; {'it also' if same else nb} gives {b.val.raw} ({diff}).",
            why_it_matters=(f"Plans, budgets and commitments built on the {label} diverge depending on which document a team reads; "
                            "the gap stays invisible until a deadline or invoice exposes it."),
            category="contradiction", classification="observed_conflict", module="contradiction",
            impact_factors=ImpactFactors(consequence=cons, decision_relevance=80 if money_like else 60, breadth=_breadth(sids)),
            confidence_factors=ConfidenceFactors(evidence_strength=85, specificity=80 if a.val.kind != "date" else 75,
                                                 corroboration=_corroboration(sids)),
            citations=[], contradiction=Contradiction(
                claim_a=self._claim(a, "claim_a"), claim_b=self._claim(b, "claim_b"), comparison=comparison,
                verdict=verdict, verdict_reason=reason, resolution=resolution),  # type: ignore[arg-type]
            recommendation=f"Reconcile the {label} across {where} and publish a single agreed value with an owner.",
            question=f"Which {label} is the plan actually committed to — {a.val.raw} ({na}) or {b.val.raw} ({nb}) — and who signs off on it?",
        ).finding.citations = [_cite(a.sent, "claim_a"), _cite(b.sent, "claim_b")]

    def _price_vs_data(self, price_claims: list[MetricClaim]) -> None:
        if not price_claims:
            return
        a = sorted(price_claims, key=lambda m: (m.sent.is_row, m.sent.source.id))[0]
        for prefix, src, analysis in self._tables():
            for ca in analysis.column_analyses:
                if ca.dtype != "numeric" or not re.search(r"fee|price|arpu|mrr|plan_amount", ca.name, I):
                    continue
                nz = sorted(v for v in ca.numeric.values() if v > 0)
                if len(nz) < 5:
                    continue
                med = nz[len(nz) // 2] if len(nz) % 2 else (nz[len(nz) // 2 - 1] + nz[len(nz) // 2]) / 2
                rel = abs(med - a.val.value) / (a.val.value or 1)
                if rel <= 0.03:
                    continue
                unit = self._stat_unit(prefix, ca.slug)
                if unit is None:
                    continue
                excerpt = ca.sentences.get("nonzero") or ca.sentences.get("stats") or ca.sentences["summary"]
                if excerpt not in unit.text:
                    excerpt = split_sentences(unit.text)[0]
                claim_b = Claim(statement=f"Observed median non-zero {ca.name} in {src.name}: {fmt_num(med)}", value=fmt_num(med),
                                unit=a.val.unit, as_of=self.c.doc_meta.get(src.id), scope="observed data",
                                citation=_ucite(unit, excerpt, "claim_b"))
                label = "price per account per month"
                self._new(
                    "contradiction", {"price"},
                    title=f"Planned {label} {a.val.raw} vs observed {ca.name} median {fmt_num(med)}",
                    summary=(f"{a.sent.source.name} plans on {a.val.raw}, but the non-zero {ca.name} values in {src.name} "
                             f"have a median of {fmt_num(med)} ({(med - a.val.value) / a.val.value * 100:+.0f}%)."),
                    why_it_matters="Revenue projections multiply this price by every account; a lower realised price scales the whole forecast down.",
                    category="contradiction", classification="observed_conflict", module="contradiction",
                    impact_factors=ImpactFactors(consequence=75, decision_relevance=80, breadth=_breadth({a.sent.source.id, src.id})),
                    confidence_factors=ConfidenceFactors(evidence_strength=80, specificity=85, corroboration=_corroboration({a.sent.source.id, src.id})),
                    contradiction=Contradiction(
                        claim_a=self._claim(a, "claim_a"), claim_b=claim_b,
                        comparison=[
                            ComparisonRow(dimension="Value", a=a.val.raw, b=fmt_num(med), note=f"{(med - a.val.value) / a.val.value * 100:+.1f}% (b vs a)"),
                            ComparisonRow(dimension="Units", a=a.val.unit or "", b=f"{ca.name} (median of {len(nz)} non-zero rows)"),
                            ComparisonRow(dimension="Date / version", a=self.c.doc_meta.get(a.sent.source.id, "not stated"), b="pilot data as uploaded"),
                            ComparisonRow(dimension="Scope", a="planned price", b="observed fees (may include pilot discounts)", note="scope differs"),
                        ],
                        verdict="possible_conflict",
                        verdict_reason="The plan and the observed data describe different things (planned list price vs realised fees), so the gap may be intentional — but nothing in the sources explains it.",
                        resolution="Ask the pricing owner whether the observed fees are discounted pilot pricing and what evidence supports the planned price.",
                    ),
                    citations=[_cite(a.sent, "claim_a"), _ucite(unit, excerpt, "claim_b")],
                    recommendation=f"Validate the planned {label} with real price tests before it drives revenue targets.",
                    question=f"What evidence shows customers will pay {a.val.raw} when observed {ca.name} values centre on {fmt_num(med)}?",
                    calculations=[Calculation(label=f"Median non-zero {ca.name}", expression=f"median of {len(nz)} non-zero values", result=fmt_num(med))],
                )
                return

    # ---- requirement / scope conflicts
    def requirement_conflicts(self) -> None:
        defers = [s for s in self.c.sents if "deferral" in s.cues and not s.is_row]
        opposing = [s for s in self.c.sents if ("required" in s.cues or "inclusion" in s.cues)]
        found = 0
        used: set[tuple[str, str]] = set()
        for d in defers:
            best = None
            for o in opposing:
                if o.unit.id == d.unit.id:
                    continue
                shared = self.c.rare_shared(d.text, o.unit.text if "required" in _cues(o.unit.text, "") else o.text)
                if not shared:
                    continue
                strong = "required" in o.cues or bool(REQUIRED_RE.search(o.unit.text))
                score = (2 if strong else 1, -self.c.token_df.get(shared[0], 9))
                if best is None or score > best[0]:
                    best = (score, o, shared, strong)
            if not best or found >= 3:
                continue
            _, o, shared, strong = best
            if (d.unit.id, o.unit.id) in used:
                continue
            used.add((d.unit.id, o.unit.id))
            found += 1
            kw = shared[0]
            o_excerpt = o.unit.text if (strong and len(o.unit.text) <= 320) else o.text
            verdict = "true_conflict" if strong else "possible_conflict"
            sids = {d.source.id, o.source.id}
            claim_a = Claim(statement=d.text, value=None, as_of=self.c.doc_meta.get(d.source.id), scope="deferred / excluded",
                            citation=_cite(d, "claim_a"))
            claim_b = Claim(statement=o_excerpt, value=None, as_of=self.c.doc_meta.get(o.source.id),
                            scope="required" if strong else "included", citation=_cite(o, "claim_b", excerpt=o_excerpt))
            self._new(
                "contradiction", {kw},
                title=f"“{kw}” is {'deferred' if 'defer' in d.text.lower() else 'excluded'} in one place but {'required' if strong else 'included'} in another",
                summary=f"{d.source.name} ({d.unit.label}) says: “{_short(d.text, 120)}” — while {o.source.name} ({o.unit.label}) says: “{_short(o_excerpt, 120)}”.",
                why_it_matters=("Teams will build, budget and test against different scopes; one of them will discover the gap late."
                                if strong else "Costs or scope counted in one document but excluded in another make totals and plans incomparable."),
                category="contradiction", classification="observed_conflict", module="contradiction",
                impact_factors=ImpactFactors(consequence=75, decision_relevance=70, breadth=_breadth(sids)),
                confidence_factors=ConfidenceFactors(evidence_strength=85, specificity=60, corroboration=_corroboration(sids)),
                citations=[_cite(d, "claim_a"), _cite(o, "claim_b", excerpt=o_excerpt)],
                contradiction=Contradiction(
                    claim_a=claim_a, claim_b=claim_b,
                    comparison=[
                        ComparisonRow(dimension="Value", a="deferred / excluded", b="required" if strong else "included"),
                        ComparisonRow(dimension="Units", a="scope statement", b="requirement" if strong else "scope statement"),
                        ComparisonRow(dimension="Date / version", a=self.c.doc_meta.get(d.source.id, "not stated"), b=self.c.doc_meta.get(o.source.id, "not stated")),
                        ComparisonRow(dimension="Scope", a=_short(d.text, 70), b=_short(o_excerpt, 70), note=f"shared keyword: {kw}"),
                    ],
                    verdict=verdict,  # type: ignore[arg-type]
                    verdict_reason=(f"One statement defers or excludes “{kw}” while the other makes it mandatory." if strong
                                    else f"One statement excludes “{kw}” while the other counts it in; they may use different bases."),
                    resolution=f"Ask the owners of {d.source.name} and {o.source.name} to agree whether “{kw}” is in scope for this release.",
                ),
                recommendation=f"Decide explicitly whether “{kw}” is in or out of scope and update both documents.",
                question=f"Is “{kw}” in scope for this release — and if it is deferred, who accepted the risk described in {o.source.name}?",
            )

    # ---- b. explicit / rationale assumptions
    def assumptions(self) -> None:
        cands: list[tuple[int, Sent]] = []
        for s in self.c.sents:
            nums = [v for v in s.vals if v.kind in ("money", "pct") or (v.kind == "count" and not re.search(r"(hours?|days?|weeks?|months?)$", v.unit))]
            dates = [v for v in s.vals if v.kind == "date"]
            explicit = "assumption" in s.cues
            target = "target" in s.cues and bool(re.match(r"(reach|achieve|grow|hit|deliver|launch|public|sign|win|cut|reduce|increase)", s.text, I) or nums or dates)
            rationale = "soft" in s.cues and "rationale" in s.cues
            if not (explicit or target or rationale):
                continue
            if not (nums or dates or rationale):
                continue
            if s.is_row and not explicit:
                continue
            score = 3 * explicit + 2 * target + 1 * ("soft" in s.cues) + 2 * bool(nums) + 1 * bool(dates) + (2 if rationale else 0)
            score -= 2 * s.is_row  # table restatements rank below prose
            if rationale and self._related_evidence(s):
                score += 3  # a premise that other material speaks to directly is worth checking first
            cands.append((score, s))
        cands.sort(key=lambda t: (-t[0], t[1].source.id, t[1].unit.id))
        seen_vals: dict[str, Draft] = {}
        used_units: set[str] = set()
        for score, s in cands:
            nums = [v for v in s.vals if v.kind in ("money", "pct", "count")]
            main = (sorted(nums, key=lambda v: {"pct": 0, "money": 1, "count": 2}[v.kind])[0] if nums
                    else next((v for v in s.vals if v.kind == "date"), None))
            vkey = f"{main.kind}:{main.value}" if main else None
            if vkey and vkey in seen_vals:  # restatement of a figure we already flagged
                d = seen_vals[vkey]
                if s.source.id not in {c.source_id for c in d.finding.citations} and len(d.finding.citations) < 4:
                    d.finding.citations.append(_cite(s, "support", note="Restates the same figure — not independent evidence."))
                    d.finding.confidence_factors.corroboration = min(90, d.finding.confidence_factors.corroboration + 15)
                continue
            if s.unit.id in used_units or len(self.assumption_drafts) >= MAX_ASSUMPTIONS:
                continue
            used_units.add(s.unit.id)
            d = self._assumption_finding(s, main)
            if vkey:
                seen_vals[vkey] = d

    def _related_evidence(self, s: Sent) -> Optional[tuple[Sent, str]]:
        for o in self.c.sents:
            if o.source.id == s.source.id or "evidence" not in o.cues or o.is_row:
                continue
            shared = self.c.rare_shared(s.text, o.text, 3)
            if shared:
                return o, shared[0]
        return None

    def _metric_key_for(self, s: Sent, v: Optional[Val]) -> Optional[str]:
        for mc in metric_claims([s]):
            if v is None or mc.val is v:
                return mc.key
        t = s.context
        kind = v.kind if v else None
        options = {
            "pct": (("growth", GROWTH_RE), ("conversion", CONVERSION_RE), ("churn", CHURN_RE)),
            "money": (("cac", CAC_RE), ("price", PRICE_RE), ("revenue", REVENUE_RE), ("budget", BUDGET_RE)),
            "date": (("launch", LAUNCH_RE),),
            "count": (("accounts", ACCOUNTS_RE),),
        }.get(kind or "", ())
        for k, pat in options:
            if pat.search(t if kind != "count" else v.noun):
                return k
        return None

    def _assumption_finding(self, s: Sent, v: Optional[Val]) -> Draft:
        explicit = "assumption" in s.cues or "target" in s.cues
        key = self._metric_key_for(s, v)
        label = METRIC_LABEL.get(key or "", "")
        is_target = "target" in s.cues and "assumption" not in s.cues
        if v is not None and label:
            title = f"{label[0].upper() + label[1:]} of {v.raw} is {'a target' if is_target else 'assumed'} without supporting evidence"
        elif v is not None:
            title = f"{'Target' if is_target else 'Assumption'} “{_short(s.text, 70)}” has no supporting evidence"
        else:
            title = f"Stated as fact, used as an assumption: “{_short(s.text, 70)}”"
        cites = [_cite(s, "support")]
        calcs: list[Calculation] = []
        notes: list[str] = []
        # related evidence elsewhere (shares a rare keyword and carries evidence cues)
        rel_ev = self._related_evidence(s)
        if rel_ev:
            o, term = rel_ev
            cites.append(_cite(o, "context", note=f"Related evidence (shared term “{term}”) — check whether it supports or undermines the assumption."))
            notes.append(f"{o.source.name} ({o.unit.label}) reports related evidence on “{term}”.")
        # dataset values mentioned in the assumption → deterministic share calculation
        for prefix, src, analysis in self._tables():
            for ca in analysis.column_analyses:
                if ca.dtype != "categorical":
                    continue
                total = sum(1 for _ in ca.values)
                for label_v, cnt in ca.top_values:
                    if len(label_v) >= 3 and re.search(rf"\b{re.escape(label_v)}\b", s.text, I) and total:
                        unit = self._stat_unit(prefix, ca.slug)
                        ex = ca.sentences.get("top")
                        if unit is None or not ex or ex not in unit.text:
                            continue
                        share = cnt / total * 100
                        calcs.append(Calculation(label=f"Share of rows with {ca.name} = {label_v} in {src.name}",
                                                 expression=f"{cnt} / {total} rows" + (" (exact duplicates included)" if analysis.duplicate_rows else ""),
                                                 result=f"{share:.1f}%"))
                        cites.append(_ucite(unit, ex, "context", note="Observed distribution in the uploaded data."))
                        notes.append(f"In {src.name}, {cnt} of {total} rows ({share:.1f}%) have {ca.name} = {label_v}.")
                        break
                if calcs:
                    break
            if calcs:
                break
        sids = {c.source_id for c in cites}
        kind = v.kind if v else None
        cons = {"money": 70, "pct": 70, "count": 65, "date": 60, None: 60}[kind]
        decision = 80 if key in ("launch", "budget", "price", "revenue", "growth", "cac") else 65
        if explicit:
            classification, a_type, inference = "missing_evidence", "explicit", None
        else:
            classification, a_type = "inferred_assumption", "inferred"
            inference = "The sentence states this as fact and uses it to justify a decision, but cites no data — it functions as an untested assumption."
        summary = f"{s.source.name} ({s.unit.label}) states: “{_short(s.text, 160)}”. No source provides data that backs this figure."
        if v is None:
            summary = f"{s.source.name} ({s.unit.label}) justifies a decision with: “{_short(s.text, 160)}”. No data is given for this premise."
        if notes:
            summary += " " + " ".join(notes)
        d = self._new(
            "assumption", {key} if key else set(),
            title=title, summary=summary,
            why_it_matters=("Downstream targets, budgets and staffing are sized from this figure; if it is wrong, everything derived from it is wrong by the same factor."
                            if v is not None else "A scope or design decision rests on this premise; if it is false, the decision has to be revisited late."),
            category="assumption", classification=classification, module="radar", assumption_type=a_type,  # type: ignore[arg-type]
            impact_factors=ImpactFactors(consequence=cons, decision_relevance=decision, breadth=_breadth(sids)),
            confidence_factors=ConfidenceFactors(evidence_strength=75 if explicit else 55, specificity=80 if kind in ("money", "pct", "count") else (75 if kind == "date" else 45),
                                                 corroboration=_corroboration({s.source.id})),
            citations=cites, calculations=calcs, inference_note=inference,
            recommendation=(f"Find or collect evidence for {v.raw if v else 'this premise'} (historical data, pilot metrics or a benchmark) and name an owner for it."),
            question=(f"What evidence supports {v.raw}{(' for the ' + label) if label else ''} — and what happens to the plan if the real value is half that?"
                      if v is not None and v.kind != "date" else
                      f"What evidence supports “{_short(s.text, 90)}”, and who has verified it?"),
        )
        self.assumption_drafts.append((d, s, v, key))
        return d

    # ---- dependencies without contingency
    def dependencies(self) -> None:
        name_re = re.compile(
            r"\b(?:provided by|relies on|rely on|depends? on|dependent on|via|through|using|powered by|integrat\w* with|partner\w* with|hosted on|built on)\s+"
            r"(?:the\s+|our\s+|a\s+|an\s+)?([A-Z][A-Za-z0-9&\-]*(?:\s+[A-Z][A-Za-z0-9&\-]*){0,3})")
        api_re = re.compile(r"\b([A-Z][A-Za-z0-9]+(?:\s+[A-Z][A-Za-z0-9]+){0,2}\s+(?:API|SDK|Platform|Cloud))\b")
        excluded = set()
        for u in self.c.units:
            if u.kind == "heading":
                excluded |= {w.lower() for w in re.findall(r"[A-Za-z]+", u.text)}
        for s in self.c.sources:
            excluded |= {w.lower() for w in re.findall(r"[A-Za-z]+", s.name)}
        generic = {"api", "sdk", "the", "our", "we", "platform", "cloud", "finance", "engineering", "sales", "product", "crm", "it"}
        names: dict[str, list[Sent]] = {}
        for s in self.c.sents:
            if "dependency" not in s.cues and not api_re.search(s.text):
                continue
            for m in list(name_re.finditer(s.text)) + list(api_re.finditer(s.text)):
                full = m.group(1).strip()
                brand = full.split()[0]
                if brand.lower() in generic or brand.lower() in excluded or len(brand) < 3:
                    continue
                names.setdefault(brand, [])
                if s not in names[brand]:
                    names[brand].append(s)
        neg_units = [s for s in self.c.sents if "no_contingency" in s.cues]
        count = 0
        for brand, dep_sents in sorted(names.items(), key=lambda kv: (-len(kv[1]), kv[0])):
            if count >= MAX_DEPENDENCIES:
                break
            mentions = [s for s in self.c.sents if re.search(rf"\b{re.escape(brand)}\b", s.text)]
            if any("contingency" in s.cues for s in mentions):
                continue  # a fallback is mentioned for this dependency
            full_name = next((m.group(1) for s in dep_sents for m in name_re.finditer(s.text) if m.group(1).startswith(brand)), brand)
            full_name = next((m.group(1) for s in dep_sents for m in api_re.finditer(s.text) if m.group(1).startswith(brand)), full_name)
            neg = None
            for n in neg_units:
                ctx = " ".join(x.text for x in mentions)
                if self.c.rare_shared(n.text, ctx, 6) or n.unit.section == mentions[0].unit.section:
                    neg = n
                    break
            cites = [_cite(dep_sents[0], "support")]
            for s in mentions:
                if len(cites) >= 3:
                    break
                if s.unit.id not in {c.unit_id for c in cites} and ("constraint" in s.cues or s.source.id not in {c.source_id for c in cites}):
                    cites.append(_cite(s, "support"))
            if neg:
                cites.append(_cite(neg, "support", note="States explicitly that no fallback exists."))
            sids = {c.source_id for c in cites}
            constraint = next((s for s in mentions if "constraint" in s.cues), None)
            count += 1
            summary = f"The plan relies on {full_name} ({dep_sents[0].source.name}, {dep_sents[0].unit.label}), and no source describes a fallback if it fails, degrades or changes terms."
            if constraint:
                summary += f" Known limits: “{_short(constraint.text, 140)}”."
            if neg:
                summary += f" {neg.source.name} states: “{neg.text}”"
            self._new(
                "dependency", {brand.lower()},
                title=f"Single dependency on {full_name} with no {'evaluated ' if neg else ''}fallback",
                summary=summary,
                why_it_matters=f"If {full_name} has an outage, hits a quota or changes pricing, the features that rely on it stop working and there is no plan B.",
                category="contingency" if neg else "dependency", classification="potential_risk", module="radar",
                impact_factors=ImpactFactors(consequence=80 if neg else 70, decision_relevance=70, breadth=_breadth(sids)),
                confidence_factors=ConfidenceFactors(evidence_strength=80 if neg else 70, specificity=75 if constraint else 55,
                                                     corroboration=_corroboration(sids)),
                citations=cites,
                recommendation=f"Evaluate a fallback for {full_name} (alternative provider, cached/degraded mode or contractual SLA) and record the trigger for switching.",
                question=f"What happens to the product on the day {full_name} is unavailable or rate-limits us — and who owns that contingency?",
            )

    # ---- coverage gaps
    def gaps(self) -> None:
        text = self.c.all_text
        has_dates = any(v.kind == "date" for s in self.c.sents for v in s.vals)
        projectish = (has_dates or re.search(r"timeline|milestone|sprint", text, I)) and re.search(r"budget|launch|goal|plan|scope|requirement", text, I)
        prose = [s for s in self.c.sents if not s.is_row]
        if not projectish or not prose:
            return
        topics = [
            ("security / privacy / compliance", r"\b(security|secure|privacy|gdpr|ccpa|hipaa|compliance|soc ?2|encrypt\w*|data protection|pii|personal data|consent)\b",
             r"\b(SMS|e-?mail|phone|customer|personal|payment|data)\b", 60, 60,
             "Customer contact data and third-party processors appear in the plan, but nothing addresses security, privacy or compliance."),
            ("risks & contingency", r"\b(risks?|mitigat\w*|contingenc\w*|fallback)\b", r"\b(depend\w*|API|vendor|launch)\b", 60, 60,
             "The documents never discuss what could go wrong or how it would be handled."),
            ("testing / QA", r"\b(test\w*|qa|quality assurance|beta|hardening|acceptance|uat)\b", r"\b(release|launch|feature)\b", 55, 55,
             "There is no mention of how the product will be tested before release."),
            ("ownership / accountability", r"\b(owners?|owned by|responsible|accountable|dri|raci)\b", r"\b(will|must|plan)\b", 50, 55,
             "No owner is named for the commitments in the plan."),
            ("success metrics", r"\b(kpis?|metrics?|success criteria|measure\w*|targets?|goals?)\b", r"\b(launch|reach|achieve)\b", 50, 55,
             "The plan does not say how success will be measured."),
            ("support / operations", r"\b(support|operations|on-call|incident|monitoring|runbook)\b", r"\b(customers?|launch|accounts?)\b", 50, 50,
             "Nothing describes how the product is supported or operated after launch."),
        ]
        emitted = 0
        for name, present, hint, cons, dec, why in topics:
            if emitted >= MAX_GAPS:
                break
            if re.search(present, text, I):
                continue
            ctx = next((s for s in prose if "dependency" in s.cues and re.search(hint, s.text, I)), None) or \
                next((s for s in prose if re.search(hint, s.text, I)), None)
            emitted += 1
            self._new(
                "gap", {name},
                title=f"No mention of {name} anywhere in the uploaded material",
                summary=f"None of the {len(self.c.sources)} sources mentions {name}. {why}",
                why_it_matters=f"Gaps in {name} are usually discovered late, when they are expensive to fix or block a launch.",
                category="missing_constraint", classification="missing_evidence", module="radar",
                impact_factors=ImpactFactors(consequence=cons, decision_relevance=dec, breadth=60),
                confidence_factors=ConfidenceFactors(evidence_strength=40, specificity=40, corroboration=_corroboration({s.id for s in self.c.sources})),
                citations=[_cite(ctx, "context", note=f"Closest related passage — it would normally raise {name} questions.")] if ctx else [],
                inference_note=f"Inferred from absence: no passage in any source matches {name} vocabulary. The topic may be covered in documents that were not uploaded.",
                recommendation=f"Add a short {name} section (requirements, owner, open items) or confirm where it is documented.",
                question=f"Where is {name} for this plan addressed, and who is accountable for it?",
            )
        # risk section that names a single risk while dependencies / conflicts exist
        dep_or_conflict = any(g in ("dependency", "contradiction") for g, _ in self.drafts)
        for u in self.c.units:
            if u.kind != "heading" or not re.search(r"\brisks?\b", u.text, I):
                continue
            body = [x for x in self.c.units if x.source_id == u.source_id and x.section == u.text and x.kind != "heading"]
            risk_sents = [s for s in self.c.sents if s.unit in body]
            if 0 < len(body) <= 2 and dep_or_conflict and risk_sents:
                main = next((s for s in risk_sents if re.search(r"\brisk\b", s.text, I)), risk_sents[0])
                others = [d.finding for g, d in self.drafts if g in ("dependency", "contradiction")][:2]
                self._new(
                    "gap", {"risk"},
                    title=f"The risk section of {u.source_id and self.c.by_source[u.source_id].name} names only one risk",
                    summary=f"“{u.text}” contains only: “{_short(main.text, 140)}”. Dependencies and conflicts found elsewhere in the material are not listed as risks.",
                    why_it_matters="Risks that are not written down have no owner and no mitigation; they surface as surprises.",
                    category="contingency", classification="potential_risk", module="radar",
                    impact_factors=ImpactFactors(consequence=60, decision_relevance=60, breadth=60),
                    confidence_factors=ConfidenceFactors(evidence_strength=60, specificity=50, corroboration=40),
                    citations=[_cite(main, "support")],
                    inference_note="Inferred: compares the length of the risk section with the dependencies and conflicts detected in other sources.",
                    recommendation="Expand the risk register with the dependency and scope findings in this investigation, each with an owner and mitigation.",
                    question="Which risks beyond the one listed has the team considered, and why were they left out?",
                ).keys |= {f.id for f in others}
                break

    # ---- dataset findings
    def _tables(self) -> list[tuple[str, Source, TableAnalysis]]:
        if hasattr(self, "_table_cache"):
            return self._table_cache
        out = []
        for src in self.c.sources:
            for p in src.profiles:
                prefix = src.id if src.kind == "csv" else f"{src.id}.{_slug_from_units(self.c.units, src.id, p.sheet)}"
                cols = [cp.name for cp in p.column_profiles]
                rows_u = sorted((u for u in self.c.units if u.source_id == src.id and u.kind == "table_row" and u.id.startswith(prefix + ".r")
                                 and (u.location.sheet == p.sheet)), key=lambda u: u.location.row or 0)
                if not rows_u:
                    continue
                rows = [parse_row_text(u.text, cols) for u in rows_u]
                out.append((prefix, src, analyze_table(cols, rows, sheet=p.sheet, row_numbers=[u.location.row or 0 for u in rows_u])))
        self._table_cache = out
        return out

    def _stat_unit(self, prefix: str, col_slug: Optional[str] = None) -> Optional[EvidenceUnit]:
        uid = f"{prefix}.stat.dataset" if col_slug is None else f"{prefix}.stat.col.{col_slug}"
        return self.c.unit_by_id.get(uid)

    def _row_unit(self, prefix: str, row: int) -> Optional[EvidenceUnit]:
        return self.c.unit_by_id.get(f"{prefix}.r{row:04d}")

    def _ds_finding(self, src: Source, prefix: str, stat: EvidenceUnit, sentence: str, rows: list[int], *, title: str, summary: str,
                    why: str, classification: str, cons: int, decision: int, affected: int, total: int, rec: str, q: str,
                    calcs: list[Calculation], key: str, extra_rows_note: str = "Example row") -> None:
        if sentence not in stat.text:
            sentence = split_sentences(stat.text)[0]
        cites = [_ucite(stat, sentence, "support", note="Deterministic profile computed from every row.")]
        for r in rows[:3]:
            ru = self._row_unit(prefix, r)
            if ru:
                cites.append(_ucite(ru, ru.text, "support", note=f"{extra_rows_note} {r}."))
        breadth = min(90, 30 + int(60 * affected / max(total, 1)) * 3)
        self._new(
            "dataset", {key},
            title=title, summary=summary, why_it_matters=why, category="data_quality", classification=classification,  # type: ignore[arg-type]
            module="dataset",
            impact_factors=ImpactFactors(consequence=cons, decision_relevance=decision, breadth=min(90, breadth)),
            confidence_factors=ConfidenceFactors(evidence_strength=90, specificity=85, corroboration=60),
            citations=cites, calculations=calcs, recommendation=rec, question=q,
        )

    def dataset_findings(self) -> None:
        for prefix, src, ta in self._tables():
            where = f"{src.name}" + (f" · {ta.profile.sheet}" if src.kind == "xlsx" else "")
            stat = self._stat_unit(prefix)
            if stat is None:
                continue
            n = ta.rows
            if ta.duplicate_rows:
                k = len(ta.duplicate_rows)
                ex_rows = []
                for r in ta.duplicate_rows[:2]:
                    ex_rows += [r, ta.duplicate_of[r]]
                self._ds_finding(
                    src, prefix, stat, ta.sentences["overview"], ex_rows[:3],
                    title=f"{k} exact duplicate row{'s' if k > 1 else ''} in {where}",
                    summary=f"{k} of {n} rows repeat an earlier row exactly (rows {', '.join(map(str, ta.duplicate_rows[:10]))}). Counts and sums computed from this file are inflated.",
                    why="Duplicated records overstate totals (accounts, revenue, usage) that plans are sized from.",
                    classification="observed_conflict", cons=55, decision=55, affected=k, total=n,
                    rec="De-duplicate on the record key before computing any metric, and fix the export that produced the copies.",
                    q=f"Are the {k} duplicated rows double-counted in any figure already reported from {src.name}?",
                    calcs=[Calculation(label="Rows after removing exact duplicates", expression=f"{n} − {k}", result=str(n - k))],
                    key=f"{prefix}:dup",
                )
            for ca in ta.column_analyses:
                cstat = self._stat_unit(prefix, ca.slug)
                if cstat is None or ca.dtype == "empty":
                    continue
                miss = len(ca.missing_rows)
                if miss and miss / n > 0.02:
                    vals = list(ca.numeric.values())
                    calcs = [Calculation(label=f"Rows with a usable {ca.name}", expression=f"{n} − {miss}", result=f"{n - miss} ({(n - miss) / n * 100:.1f}%)")]
                    if vals:
                        calcs.append(Calculation(label=f"Mean {ca.name} over non-missing rows", expression=f"sum / {len(vals)}", result=fmt_num(round(sum(vals) / len(vals), 2))))
                    self._ds_finding(
                        src, prefix, cstat, ca.sentences.get("missing", ca.sentences["summary"]), ca.missing_rows,
                        title=f"{miss} missing values in {ca.name} ({miss / n * 100:.1f}%) — {where}",
                        summary=f"{ca.name} is blank in {miss} of {n} rows (rows {', '.join(map(str, ca.missing_rows[:10]))}{'…' if miss > 10 else ''}).",
                        why=f"Any estimate that uses {ca.name} either drops these rows or silently treats them as zero.",
                        classification="potential_risk", cons=45 if miss / n < 0.1 else 55, decision=50, affected=miss, total=n,
                        rec=f"Backfill {ca.name} from the system of record or state explicitly how missing values are treated.",
                        q=f"Why is {ca.name} missing for these records, and are they systematically different from the rest?",
                        calcs=calcs, key=f"{prefix}:{ca.name}", extra_rows_note="Row with missing value:",
                    )
                if ca.sentinel_rows:
                    vals_all = list(ca.numeric.values())
                    clean = [v for r, v in ca.numeric.items() if r not in ca.sentinel_rows]
                    sv = sorted({fmt_num(ca.numeric[r]) for r in ca.sentinel_rows})
                    calcs = []
                    if clean:
                        calcs.append(Calculation(label=f"Mean {ca.name} with vs without sentinel rows",
                                                 expression=f"mean of {len(vals_all)} rows vs mean of {len(clean)} rows",
                                                 result=f"{fmt_num(round(sum(vals_all) / len(vals_all), 2))} vs {fmt_num(round(sum(clean) / len(clean), 2))}"))
                    self._ds_finding(
                        src, prefix, cstat, ca.sentences["sentinel"], ca.sentinel_rows,
                        title=f"Placeholder value{'s' if len(sv) > 1 else ''} {', '.join(sv)} in {ca.name} — {where}",
                        summary=f"{len(ca.sentinel_rows)} row(s) hold {', '.join(sv)} in {ca.name}, a typical 'unknown' placeholder rather than a real measurement.",
                        why=f"Sentinel values distort averages and totals of {ca.name} by orders of magnitude.",
                        classification="potential_risk", cons=55, decision=55, affected=len(ca.sentinel_rows), total=n,
                        rec=f"Treat {', '.join(sv)} in {ca.name} as missing and recompute any figure derived from this column.",
                        q=f"What do the {', '.join(sv)} values in {ca.name} actually mean, and has any reported average included them?",
                        calcs=calcs, key=f"{prefix}:{ca.name}", extra_rows_note="Row",
                    )
                other_out = [r for r in ca.iqr_outliers if r not in ca.sentinel_rows]
                if other_out and n >= 20:
                    self._ds_finding(
                        src, prefix, cstat, ca.sentences.get("outliers", ca.sentences["summary"]), other_out,
                        title=f"Extreme outliers in {ca.name} — {where}",
                        summary=f"{len(other_out)} value(s) in {ca.name} fall far outside the interquartile range (k=3).",
                        why="Unchecked extreme values can dominate means and totals.",
                        classification="potential_risk", cons=40, decision=45, affected=len(other_out), total=n,
                        rec=f"Check the flagged {ca.name} rows against the source system.",
                        q=f"Are the extreme {ca.name} values real, or entry errors?",
                        calcs=[], key=f"{prefix}:{ca.name}", extra_rows_note="Row",
                    )
                if ca.range_rows and ca.expected_range:
                    lo, hi = ca.expected_range
                    self._ds_finding(
                        src, prefix, cstat, ca.sentences["range"], ca.range_rows,
                        title=f"{ca.name} values outside the valid {fmt_num(lo)}–{fmt_num(hi)} range — {where}",
                        summary=f"{len(ca.range_rows)} row(s) have {ca.name} outside {fmt_num(lo)}–{fmt_num(hi)} (e.g. row {ca.range_rows[0]} = {ca.values[ca.range_rows[0]]}).",
                        why=f"Impossible values signal entry or export errors, which undermines trust in every {ca.name}-based conclusion.",
                        classification="observed_conflict", cons=40, decision=45, affected=len(ca.range_rows), total=n,
                        rec=f"Correct or exclude out-of-range {ca.name} values and add validation at the point of entry.",
                        q=f"How did {ca.name} values outside {fmt_num(lo)}–{fmt_num(hi)} get into the data, and are other columns from the same entries reliable?",
                        calcs=[], key=f"{prefix}:{ca.name}", extra_rows_note="Row",
                    )
                if ca.variant_groups:
                    g = ca.variant_groups[0]
                    total_g = sum(c for _, c in g)
                    rows = []
                    for lbl, _ in g[1:]:
                        r = next((r for r, v in sorted(ca.values.items()) if v == lbl), None)
                        if r:
                            rows.append(r)
                    self._ds_finding(
                        src, prefix, cstat, ca.sentences["variants"], rows,
                        title=f"Inconsistent {ca.name} labels: {' / '.join(l for l, _ in g)} — {where}",
                        summary=f"{len(g)} spellings appear to denote the same {ca.name} ({', '.join(f'{l}: {c}' for l, c in g)}). Grouped counts by {ca.name} are split across them.",
                        why=f"Any breakdown by {ca.name} under-counts the affected category and can change which segment looks largest.",
                        classification="observed_conflict", cons=40, decision=45, affected=total_g - g[0][1], total=n,
                        rec=f"Normalise {ca.name} to a controlled list of values before reporting by segment.",
                        q=f"Should {' / '.join(l for l, _ in g)} be treated as one {ca.name}, and which other labels need mapping?",
                        calcs=[Calculation(label=f"Rows in '{g[0][0]}' if variants are merged", expression=" + ".join(str(c) for _, c in g),
                                           result=f"{total_g} (vs {g[0][1]} under '{g[0][0]}' alone)")],
                        key=f"{prefix}:{ca.name}", extra_rows_note="Row using variant label:",
                    )
            for ci in ta.cross_issues:
                amt = ta.column(ci.amount_column)
                nz = sorted(v for v in amt.numeric.values() if v > 0) if amt else []
                typical = nz[len(nz) // 2] if nz else None
                calcs = [Calculation(label=f"Rows with {ci.status_column} paid-like but {ci.amount_column} = 0", expression=f"count of rows", result=str(len(ci.rows)))]
                if typical:
                    calcs.append(Calculation(label=f"Missing {ci.amount_column} if each charged the median non-zero fee",
                                             expression=f"{len(ci.rows)} × {fmt_num(typical)}", result=fmt_num(len(ci.rows) * typical)))
                self._ds_finding(
                    src, prefix, stat, ci.sentence, ci.rows,
                    title=f"{len(ci.rows)} '{ci.status_column}: paid' rows with {ci.amount_column} = 0 — {where}",
                    summary=f"{ci.sentence} Either the status or the amount is wrong for these records.",
                    why="Revenue and conversion figures computed from status and amount disagree for these rows.",
                    classification="observed_conflict", cons=60, decision=60, affected=len(ci.rows), total=n,
                    rec=f"Reconcile {ci.status_column} with billing records for the flagged rows.",
                    q=f"Are these accounts really paying? If so, why is {ci.amount_column} recorded as 0?",
                    calcs=calcs, key=f"{prefix}:{ci.amount_column}", extra_rows_note="Row",
                )

    # ---- open questions (labelled inference)
    def open_questions(self) -> None:
        launch = [d for g, d in self.drafts if g == "contradiction" and "launch" in d.keys]
        if len(launch) >= 2:
            sides: dict[str, Citation] = {}
            for d in launch:
                c = d.finding.contradiction
                for cl in (c.claim_a, c.claim_b):
                    sides.setdefault(cl.citation.unit_id or cl.statement, cl.citation.model_copy(update={"role": "context"}))
            values = sorted({d.finding.contradiction.claim_a.value for d in launch} | {d.finding.contradiction.claim_b.value for d in launch})
            self._new(
                "question", {"launch"} | {d.finding.id for d in launch},
                title=f"There is no single agreed launch date ({len(values)} different dates across the sources)",
                summary=f"The sources mention {', '.join(values)} as launch, release or availability dates. Each pairwise conflict is listed separately; together they suggest no shared timeline exists.",
                why_it_matters="Marketing, staffing, budget phasing and revenue start dates all key off the launch date.",
                category="open_question", classification="inferred_assumption", module="radar",
                impact_factors=ImpactFactors(consequence=75, decision_relevance=85, breadth=_breadth({c.source_id for c in sides.values()})),
                confidence_factors=ConfidenceFactors(evidence_strength=45, specificity=75, corroboration=_corroboration({c.source_id for c in sides.values()})),
                citations=list(sides.values())[:4],
                inference_note="Synthesised from the individual date contradictions; the dates may legitimately describe different milestones.",
                recommendation="Hold a 30-minute timeline alignment with the document owners and publish one dated milestone list.",
                question="Which date are customers, finance and engineering each planning around — and who decides?",
            )
        assum = [d for g, d in self.drafts if g == "assumption"]
        if len(assum) >= 3:
            top = assum[:3]
            self._new(
                "question", {k for d in top for k in d.keys} | {d.finding.id for d in top},
                title="Which unevidenced assumption is the plan most sensitive to?",
                summary=(f"{len(assum)} figures or premises are stated without evidence. They are listed individually; nobody has said which one, "
                         "if wrong, would change the go / no-go decision."),
                why_it_matters="Validation effort should go first to the assumption with the largest downstream effect.",
                category="open_question", classification="inferred_assumption", module="radar",
                impact_factors=ImpactFactors(consequence=65, decision_relevance=75, breadth=70),
                confidence_factors=ConfidenceFactors(evidence_strength=40, specificity=45, corroboration=40),
                citations=[c.model_copy(update={"role": "context"}) for d in top for c in d.finding.citations[:1]],
                inference_note="Synthesised from the assumption findings; ranking their sensitivity requires a human or a model of the plan.",
                recommendation="Run the scenario sliders for each assumption and pick the one whose change moves the outcome most; validate it first.",
                question="If only one assumption could be tested before committing budget, which one should it be?",
            )

    # ---- scenarios
    def build_scenarios(self) -> None:
        targets = [(s, v) for s in self.c.sents for v in s.vals if v.kind == "count" and "target" in s.cues
                   and re.search(r"within\s+(\d+)\s+months?|by month\s+(\d+)", s.text, I)]
        ranked = sorted(self.assumption_drafts, key=lambda t: (t[3] != "growth", t[3] not in ("price", "revenue", "cac", "conversion")))
        for d, s, v, key in ranked:
            if len(self.scenarios) >= 3:
                break
            if v is None or v.kind not in ("pct", "count", "money"):
                continue
            idx = len(self.scenarios) + 1
            max_change = 100.0
            if v.kind == "pct" and key in ("conversion", "churn") and v.value > 0:
                max_change = max(0.0, float(int((100.0 / v.value - 1) * 100 // 5 * 5)))  # a rate cannot exceed 100%
            label = METRIC_LABEL.get(key or "", "") or f"stated {v.kind}"
            unit = "%" if v.kind == "pct" else (v.unit if v.kind == "money" else v.unit)
            cit = _cite(s, "support")
            constants = [ScenarioConstant(key="stated", label=f"Stated {label}", value=v.value, unit=unit, provenance="source", citation=cit)]
            fmt = "float" if v.kind == "pct" else ("currency" if v.kind == "money" else "int")
            metrics = [
                ScenarioMetric(key="adjusted", label=f"Adjusted {label}", formula="stated * (1 + change / 100)", format=fmt, unit=unit),
                ScenarioMetric(key="delta", label="Difference from stated value", formula="adjusted - stated", format=fmt, unit=unit),
            ]
            effects = [f"If the real {label} is lower than {v.raw}, then every figure derived from it could be overstated by the same proportion."]
            # compound growth toward a target: base count in the same sentence + target with horizon elsewhere
            base = next((x for x in s.vals if x.kind == "count" and x is not v), None)
            if key == "growth" and base is not None and targets:
                ts, tv = targets[0]
                m = re.search(r"within\s+(\d+)\s+months?|by month\s+(\d+)", ts.text, I)
                months = int(m.group(1) or m.group(2))
                constants += [
                    ScenarioConstant(key="base", label=f"Starting {base.unit}", value=base.value, unit=base.unit, provenance="source", citation=_cite(s, "support")),
                    ScenarioConstant(key="target", label=f"Target {tv.unit}", value=tv.value, unit=tv.unit, provenance="source", citation=_cite(ts, "support")),
                    ScenarioConstant(key="months", label="Months to target", value=float(months), unit="months", provenance="source", citation=_cite(ts, "support")),
                ]
                metrics = [
                    ScenarioMetric(key="adjusted", label=f"Adjusted {label}", formula="stated * (1 + change / 100)", format="float", unit="%"),
                    ScenarioMetric(key="projected", label=f"Projected {tv.unit} after {months} months", formula="base * (1 + adjusted / 100) ^ months",
                                   format="int", unit=tv.unit),
                    ScenarioMetric(key="gap", label="Shortfall vs target", formula="max(0, target - projected)", format="int", unit=tv.unit,
                                   threshold=0, threshold_direction="above_bad", threshold_label="Target missed"),
                    ScenarioMetric(key="months_needed", label="Months needed to reach target", formula="ceil(ln(target / base) / ln(1 + adjusted / 100))",
                                   format="months", unit="months", threshold=float(months), threshold_direction="above_bad", threshold_label="Later than planned"),
                ]
                effects.append(f"If monthly growth is lower than {v.raw}, then the {tv.value:,.0f} {tv.unit} target could be reached later than month {months} — or not at all.")
                projected = base.value * (1 + v.value / 100) ** months
                d.finding.calculations.append(Calculation(
                    label=f"{base.unit.capitalize()} after {months} months at the stated rate",
                    expression=f"{fmt_num(base.value)} × (1 + {fmt_num(v.value)}%)^{months}", result=f"{projected:,.0f} (target {tv.value:,.0f})"))
            ev = [EvidenceConclusion(text=f"{s.source.name} ({s.unit.label}) states the figure “{v.raw}” without citing data.", citations=[cit])]
            for c in d.finding.citations[1:]:
                if c.role in ("support", "context"):
                    ev.append(EvidenceConclusion(text=c.note or "Related passage.", citations=[c.model_copy()]))
            self.scenarios.append(Scenario(
                id=f"HS{idx}", title=f"What if the {label} is not {v.raw}?",
                question=f"How sensitive is the plan to the {label} stated as {v.raw}?",
                assumption=s.text, finding_ids=[d.finding.id],
                parameter=ScenarioParameter(key="change", label="Change vs stated value (%)", unit="%", baseline=0, min=-90, max=max_change, step=5, default=-50),
                constants=constants, metrics=metrics, evidence_conclusions=ev, hypothetical_effects=effects,
                info_needed=[f"Historical data or a comparable benchmark for the {label}", f"Who set {v.raw} and on what basis"],
                experiment=f"Measure the actual {label} on current pilot data for 4–6 weeks and compare it against {v.raw} before committing spend.",
                origin="heuristic",
            ))

    # ---- assemble
    # stages are exposed separately so the pipeline can time and count each one
    def stage_claims(self) -> int:
        """Identify claims & assumptions → number of claim-bearing sentences."""
        self.assumptions()
        return sum(1 for s in self.c.sents if s.vals or (s.cues - {"target"}))

    def stage_compare(self) -> int:
        n = len(self.drafts)
        self.contradictions()
        self.requirement_conflicts()
        return len(self.drafts) - n

    def stage_gaps(self) -> int:
        n = len(self.drafts)
        self.dependencies()
        self.gaps()
        self.build_scenarios()
        return len(self.drafts) - n

    def stage_findings(self) -> tuple[list[Finding], list[Scenario]]:
        self.dataset_findings()
        self.open_questions()
        return self.finalize()

    def run(self) -> tuple[list[Finding], list[Scenario]]:
        self.stage_claims()
        self.stage_compare()
        self.stage_gaps()
        return self.stage_findings()

    def finalize(self) -> tuple[list[Finding], list[Scenario]]:
        order = {"contradiction": 0, "assumption": 1, "dependency": 2, "gap": 3, "dataset": 4, "question": 5}
        ordered = sorted(enumerate(self.drafts), key=lambda t: (order[t[1][0]], t[0]))
        idmap: dict[str, str] = {}
        for i, (_, (_, d)) in enumerate(ordered, start=1):
            idmap[d.finding.id] = f"H{i:02d}"
        drafts = [d for _, (_, d) in ordered]
        for d in drafts:
            d.finding.id = idmap[d.finding.id]
            d.keys = {idmap.get(k, k) for k in d.keys}
        for sc in self.scenarios:
            sc.finding_ids = [idmap.get(x, x) for x in sc.finding_ids]
        units_of = {d.finding.id: {c.unit_id for c in d.finding.citations if c.unit_id} for d in drafts}
        assumption_ids = {d.finding.id for d in drafts if d.finding.category == "assumption"}
        for d in drafts:
            f = d.finding
            rel: list[str] = []
            for o in drafts:
                if o is d:
                    continue
                oid = o.finding.id
                if (units_of[f.id] & units_of[oid]) or (d.keys & o.keys) or oid in d.keys or f.id in o.keys:
                    rel.append(oid)
            f.related = sorted(set(rel))
            if f.category != "assumption":
                f.depends_on = sorted(oid for oid in assumption_ids if (units_of[f.id] & units_of[oid]) or oid in d.keys)
        return [d.finding for d in drafts], self.scenarios


def _slug_from_units(units: list[EvidenceUnit], sid: str, sheet: Optional[str]) -> str:
    for u in units:
        if u.source_id == sid and u.location.sheet == sheet and u.kind == "dataset_stat" and u.id.endswith(".stat.dataset"):
            return u.id[len(sid) + 1: -len(".stat.dataset")]
    from app.analysis.dataset import slugify
    return slugify(sheet or "")


def run_heuristics(sources: list[Source], units: list[EvidenceUnit]) -> tuple[list[Finding], list[Scenario]]:
    return Heuristics(sources, units).run()
