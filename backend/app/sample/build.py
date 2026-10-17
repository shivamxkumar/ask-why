"""Curated, deterministic sample investigation ("Project Meridian", synthetic data).

The sample sources in ./files are parsed by the real parsers. Curated findings reference sources by verbatim
excerpt only; the same citation validator used for live analysis locates and verifies each excerpt. Dataset
figures are recomputed from pilot_accounts.csv at build time, so numbers in the text always match the file.
"""
from __future__ import annotations


import math
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from app.analysis.graph import build_graph
from app.analysis.scoring import score_all
from app.analysis.validation import validate_investigation
from app.parsing import parse_file
from app.schemas import (
    Calculation,
    Citation,
    Claim,
    ComparisonRow,
    ConfidenceFactors,
    Contradiction,
    EvidenceConclusion,
    EvidenceUnit,
    Finding,
    ImpactFactors,
    Investigation,
    PipelineStep,
    Scenario,
    ScenarioConstant,
    ScenarioMetric,
    ScenarioParameter,
    ScoringConfig,
    Source,
)

SAMPLE_ID = "sample-meridian"
FILES_DIR = Path(__file__).parent / "files"
SAMPLE_FILES = [
    ("S1", "meridian_project_brief.md"),
    ("S2", "engineering_delivery_plan.pdf"),
    ("S3", "pilot_accounts.csv"),
    ("S4", "finance_budget.xlsx"),
    ("S5", "onboarding_workflow.txt"),
]


def C(source_id: str, excerpt: str, role: str = "support", note: str | None = None) -> Citation:
    return Citation(source_id=source_id, excerpt=excerpt, role=role, note=note)  # type: ignore[arg-type]


def IF(c: int, d: int, b: int) -> ImpactFactors:
    return ImpactFactors(consequence=c, decision_relevance=d, breadth=b)


def CF(e: int, s: int, c: int) -> ConfidenceFactors:
    return ConfidenceFactors(evidence_strength=e, specificity=s, corroboration=c)


class _Units:
    def __init__(self, units: list[EvidenceUnit]):
        self.units = units
        self.by_id = {u.id: u for u in units}

    def stat(self, source_id: str, unit_id: str, role: str = "support") -> list[Citation]:
        """Cite a deterministic dataset-profile unit in full (its text is computed from the file)."""
        u = self.by_id.get(unit_id)
        return [Citation(source_id=source_id, excerpt=u.text, role=role, unit_id=u.id)] if u else []  # type: ignore[arg-type]

    def rows(self, source_id: str, *needles: str, role: str = "support", limit: int = 2) -> list[Citation]:
        """Cite full row units whose text contains every needle."""
        hits = [u for u in self.units if u.source_id == source_id and u.kind == "table_row" and all(n in u.text for n in needles)]
        return [Citation(source_id=source_id, excerpt=u.text, role=role, unit_id=u.id) for u in hits[:limit]]  # type: ignore[arg-type]


def _dataset_facts() -> dict:
    raw = pd.read_csv(FILES_DIR / "pilot_accounts.csv", dtype=str, keep_default_na=False)
    dup_mask = raw.duplicated()
    df = raw[~dup_mask].copy()
    jobs = pd.to_numeric(df["jobs_per_week"], errors="coerce")
    status = df["plan_status"].value_counts()
    paid = df[df["plan_status"] == "paid"]
    fees = pd.to_numeric(paid["monthly_fee_usd"], errors="coerce")
    per_month = df["signup_month"].value_counts().sort_index()
    norm_region = df["region"].str.lower().str.replace(r"[^a-z]", "", regex=True).replace({"ne": "northeast"})
    return {
        "rows": len(raw),
        "dupes": int(dup_mask.sum()),
        "unique": len(df),
        "paid": int(status.get("paid", 0)),
        "trial": int(status.get("trial", 0)),
        "churned": int(status.get("churned", 0)),
        "fee_median": float(fees.median()),
        "fee_zero": int((fees == 0).sum()),
        "per_month": {k: int(v) for k, v in per_month.items()},
        "missing_techs": int((df["technicians"] == "").sum()),
        "sentinels": int((jobs == 9999).sum()),
        "jobs_mean_raw": float(jobs.mean()),
        "jobs_mean_clean": float(jobs[jobs != 9999].mean()),
        "nps_out": int((pd.to_numeric(df["nps"], errors="coerce") > 10).sum()),
        "ne_labels": sorted(df.loc[norm_region == "northeast", "region"].unique().tolist()),
        "ne_total": int((norm_region == "northeast").sum()),
        "ne_canonical": int((df["region"] == "Northeast").sum()),
    }


def _findings(u: _Units, d: dict) -> list[Finding]:
    months = d["per_month"]
    avg_new = sum(months.values()) / len(months)
    month_list = ", ".join(f"{m}: {n}" for m, n in months.items())
    required_rate = (2500 / 120) ** (1 / 12) - 1
    best_case_conv = (d["paid"] + d["trial"]) / d["unique"]
    pathcore_load = 2500 * 6 * 4
    pathcore_cap_accounts = 10000 / (6 * 4)
    month_cap_hit = math.log(pathcore_cap_accounts / 120) / math.log(1.35)
    linear_new_per_month = (2500 - 120) / 12
    onboarding_hours = linear_new_per_month * 1.5

    return [
        Finding(
            id="F01",
            title="The 35% monthly growth assumption has no supporting evidence — pilot signups are flat",
            summary=(
                "The business case rests on paying accounts compounding 35% month-over-month from 120 pilots. "
                f"The pilot dataset shows roughly {avg_new:.0f} new pilot accounts each month (after removing duplicate rows: {month_list}) — "
                "steady, not compounding. Reaching 2,500 accounts in 12 months from 120 requires "
                f"{required_rate:.1%} monthly compounding; no source shows that rate has ever been achieved."
            ),
            why_it_matters=(
                "Revenue, PathCore API load, support staffing and the budget envelope are all sized from this growth curve. "
                "If it is wrong, most downstream plans are mis-sized at the same time."
            ),
            category="assumption",
            classification="missing_evidence",
            module="radar",
            assumption_type="explicit",
            impact_factors=IF(95, 95, 92),
            confidence_factors=CF(82, 88, 70),
            citations=[
                C("S1", "We assume paying accounts will grow 35% month-over-month from the 120 pilot accounts we already have"),
                C("S4", "Assumption: Monthly growth in paying accounts | Value: 35%", note="Same assumption repeated by Finance — not independent evidence."),
                *u.stat("S3", "S3.stat.col.signup-month", role="counter"),
            ],
            calculations=[
                Calculation(label="Required monthly growth", expression="(2,500 ÷ 120)^(1/12) − 1", result=f"{required_rate:.1%}"),
                Calculation(label="Observed pilot signups per month", expression=f"mean of {list(months.values())}", result=f"{avg_new:.1f} accounts / month"),
                Calculation(label="Accounts at month 12 if the pilot pace continues linearly", expression=f"120 + 12 × {avg_new:.0f}", result=f"{120 + 12 * avg_new:,.0f}"),
            ],
            inference_note="The dataset records pilot signups, not paid conversions over time; it cannot prove what growth will be, only that nothing in it shows compounding.",
            recommendation="Replace the single 35% figure with a growth range built from the pilot cohort, and stress-test the plan at the low end before approving budget.",
            question="What evidence — referral rates, distributor pipeline, or a comparable launch — supports compounding growth rather than the flat ~20 accounts per month seen in the pilot?",
            related=["F06", "F04", "F10", "F12"],
        ),
        Finding(
            id="F02",
            title="Three different launch dates: 15 March (brief), April (finance), 2 May 2027 (engineering)",
            summary=(
                "The product brief commits to a public launch on 15 March 2027. The engineering plan reaches feature-complete on 21 March 2027 "
                "and targets general availability on 2 May 2027. Finance models an April 2027 launch month."
            ),
            why_it_matters="Marketing spend, the spring-season revenue window and the month-12 targets are all anchored to a launch date the delivery plan does not support.",
            category="contradiction",
            classification="observed_conflict",
            module="contradiction",
            impact_factors=IF(90, 92, 80),
            confidence_factors=CF(92, 95, 85),
            citations=[
                C("S2", "the release is planned as feature-complete at the end of sprint 12 on 21 March 2027"),
                C("S4", "Assumption: Launch month | Value: April 2027"),
            ],
            contradiction=Contradiction(
                claim_a=Claim(statement="Public launch on 15 March 2027", value="15 March 2027", scope="Public launch", as_of="Brief v1.4, 2 Sep 2026",
                              citation=C("S1", "Public launch on 15 March 2027, ahead of the spring maintenance season.", role="claim_a")),
                claim_b=Claim(statement="General availability targeted for 2 May 2027", value="2 May 2027", scope="General availability", as_of="Engineering plan, 28 Sep 2026",
                              citation=C("S2", "General availability is targeted for 2 May 2027.", role="claim_b")),
                comparison=[
                    ComparisonRow(dimension="Value", a="15 March 2027", b="2 May 2027", note="48 days apart"),
                    ComparisonRow(dimension="Milestone wording", a="Public launch", b="General availability", note="Could describe different milestones"),
                    ComparisonRow(dimension="Document date", a="2 September 2026", b="28 September 2026", note="Engineering plan is newer"),
                    ComparisonRow(dimension="Feature-complete", a="—", b="21 March 2027", note="After the brief's launch date"),
                ],
                verdict="true_conflict",
                verdict_reason=(
                    "'Public launch' and 'general availability' could name different milestones, but the engineering plan is not feature-complete until "
                    "21 March 2027 — after the brief's 15 March launch — so no reading of the delivery plan supports the brief's date. A third date (April 2027) appears in Finance's model."
                ),
                resolution="Product, Engineering and Finance agree one launch definition and date; Finance re-baselines month-12 targets against it.",
            ),
            recommendation="Hold a 30-minute date-alignment review with Product, Engineering and Finance and publish one launch milestone definition.",
            question="Which milestone does '15 March 2027' refer to, and what scope would have to be cut for it to be achievable before feature-complete?",
            related=["F11", "F05"],
        ),
        Finding(
            id="F03",
            title="Offline support is 'deferred to v2' in the brief but is a P0 requirement in engineering",
            summary=(
                "The brief scopes the MVP as online-only because technicians 'generally have reliable mobile coverage'. The engineering plan lists offline job sync "
                "as P0 (R-07), based on field interviews where 14 of 20 technicians reported daily coverage gaps."
            ),
            why_it_matters="Offline sync is one of the most expensive features in a mobile field app. Whether it is in or out of the MVP changes the timeline, the budget and the product's fit for its users.",
            category="contradiction",
            classification="observed_conflict",
            module="contradiction",
            impact_factors=IF(85, 88, 70),
            confidence_factors=CF(90, 85, 80),
            citations=[C("S2", "14 of 20 technicians reported daily coverage gaps in basements and rural sites", role="counter")],
            contradiction=Contradiction(
                claim_a=Claim(statement="MVP is online-only; offline deferred to v2", scope="MVP scope", as_of="Brief v1.4",
                              citation=C("S1", "Offline support is deferred to v2 because technicians generally have reliable mobile coverage.", role="claim_a")),
                claim_b=Claim(statement="Offline job sync is a P0 requirement", scope="Release requirements", as_of="Engineering plan",
                              citation=C("S2", "R-07 (P0): Offline job sync. Technicians must be able to view job details and record work while offline", role="claim_b")),
                comparison=[
                    ComparisonRow(dimension="Requirement status", a="Deferred to v2", b="P0 (must have)"),
                    ComparisonRow(dimension="Stated rationale", a="'Reliable mobile coverage' (no source given)", b="Field interviews: 14 of 20 technicians report daily gaps"),
                    ComparisonRow(dimension="Scope", a="MVP", b="Release covered by the delivery plan", note="Both describe the first release"),
                ],
                verdict="true_conflict",
                verdict_reason="Both documents describe the same first release and assign opposite priorities to the same capability. The brief's rationale is an unsupported assumption; the engineering plan cites interview evidence.",
                resolution="Product and Engineering decide offline scope explicitly; the decision should cite the field-interview data rather than the coverage assumption.",
            ),
            recommendation="Run a one-week coverage check with five pilot technicians (log signal loss per job) before locking MVP scope.",
            question="Is the 'reliable mobile coverage' assumption based on any measurement, and how many pilot jobs happen in basements or rural sites?",
            related=["F02", "F05"],
        ),
        Finding(
            id="F04",
            title="PathCore's 10,000-request daily limit is exceeded at roughly 417 accounts — and there is no fallback",
            summary=(
                "At the planned 2,500 accounts, the engineering plan's own load estimate (6 technicians × 4 re-optimizations per account per day) implies "
                f"{pathcore_load:,} route requests per day — {pathcore_load / 10000:.0f}× the Starter plan limit. No fallback routing provider has been evaluated, the plan has no contractual SLA, "
                "and Finance budgets only the Starter plan."
            ),
            why_it_matters="Route optimization is the core product promise. Hitting the daily cap would break dispatching for every customer at once, and nothing in the material says what would happen then.",
            category="contingency",
            classification="potential_risk",
            module="radar",
            impact_factors=IF(93, 85, 88),
            confidence_factors=CF(88, 92, 70),
            citations=[
                C("S2", "PathCore Starter plan: 10,000 route requests per day, 99.5% monthly availability, no contractual SLA."),
                C("S2", "each account averages 6 technicians and triggers about 4 route re-optimizations per technician per day"),
                C("S2", "No fallback routing provider has been evaluated yet."),
                C("S4", "Category: PathCore Routing API (Starter plan) | Amount (USD): 6000"),
                C("S1", "Route optimization will be provided by the PathCore Routing API.", role="context"),
            ],
            calculations=[
                Calculation(label="Daily requests at target", expression="2,500 accounts × 6 technicians × 4 re-optimizations", result=f"{pathcore_load:,} / day"),
                Calculation(label="Accounts at which the cap is reached", expression="10,000 ÷ (6 × 4)", result=f"≈ {pathcore_cap_accounts:.0f} accounts"),
                Calculation(label="Month the cap is reached on the plan's own 35% curve", expression="ln(417 ÷ 120) ÷ ln(1.35)", result=f"≈ month {month_cap_hit:.1f}"),
            ],
            recommendation="Get PathCore's pricing and limits for 60,000 requests per day in writing, and design a degraded mode (cached routes, manual ordering) for when the API is unavailable.",
            question="What happens to dispatching when PathCore rate-limits or is down, and what does the plan cost at 60,000 requests per day?",
            depends_on=["F01"],
            related=["F01", "F05", "F13"],
        ),
        Finding(
            id="F05",
            title="Approved budget is $1.2M; Finance's working total is $1,397,000",
            summary=(
                "The brief states a total approved budget of $1.2M. The finance workbook totals $1,397,000. Part of the gap is scope: Finance includes support tooling and a 10% contingency, "
                "which the brief's budget does not mention. Even with those removed, the remaining lines total $1,252,000 — still above the approved figure."
            ),
            why_it_matters="The project may be operating against a budget that has not been approved, with no agreed contingency.",
            category="contradiction",
            classification="observed_conflict",
            module="contradiction",
            impact_factors=IF(78, 85, 60),
            confidence_factors=CF(90, 90, 75),
            citations=[
                C("S4", "Category: Contingency (10%) | Amount (USD): 127000", role="context"),
                C("S4", "Category: Customer support tooling | Amount (USD): 18000", role="context"),
                C("S2", "Infrastructure costs are not included in this plan and are tracked by Finance.", role="context"),
            ],
            calculations=[
                Calculation(label="Gap vs approved budget", expression="$1,397,000 − $1,200,000", result="$197,000 (16.4%)"),
                Calculation(label="Finance total on the brief's stated scope", expression="$1,397,000 − $127,000 contingency − $18,000 support tooling", result="$1,252,000 (+$52,000)"),
            ],
            contradiction=Contradiction(
                claim_a=Claim(statement="Total approved project budget is $1.2M", value="$1,200,000", scope="Engineering, design, launch marketing, year-1 infrastructure", as_of="Brief v1.4",
                              citation=C("S1", "Total approved project budget: $1.2M, covering engineering, design, launch marketing and the first year of infrastructure.", role="claim_a")),
                claim_b=Claim(statement="Finance working total is $1,397,000", value="$1,397,000", scope="Includes support tooling and 10% contingency", as_of="Undated workbook",
                              citation=C("S4", "Category: Total | Amount (USD): 1397000", role="claim_b")),
                comparison=[
                    ComparisonRow(dimension="Value", a="$1,200,000", b="$1,397,000", note="+$197,000"),
                    ComparisonRow(dimension="Units", a="USD, rounded ($1.2M)", b="USD, exact"),
                    ComparisonRow(dimension="Scope", a="Eng, design, marketing, year-1 infra", b="Same plus support tooling and contingency", note="Scope differs"),
                    ComparisonRow(dimension="Scope-aligned value", a="$1,200,000", b="$1,252,000", note="Still +$52,000"),
                ],
                verdict="true_conflict",
                verdict_reason="Part of the gap is explained by scope (contingency and support tooling), but after aligning scope the finance figure still exceeds the approved budget.",
                resolution="Finance and the budget owner confirm whether $1.2M includes contingency; if not, approve a revised envelope or cut $52,000+ of scope.",
            ),
            recommendation="Ask the budget owner to confirm what the $1.2M covers, and record contingency as an explicit approved line.",
            question="Was the $1.2M approval meant to include contingency, and who approves the $52,000 overrun that remains on the brief's own scope?",
            related=["F04", "F03"],
        ),
        Finding(
            id="F06",
            title=f"'Close to 100%' pilot-to-paid conversion vs {d['paid']} paid of {d['unique']} pilot accounts",
            summary=(
                f"The brief expects nearly all pilots to convert. In the pilot dataset (after removing {d['dupes']} duplicate rows), {d['paid']} of {d['unique']} accounts "
                f"({d['paid'] / d['unique']:.0%}) are paid, {d['churned']} ({d['churned'] / d['unique']:.0%}) have churned and {d['trial']} are still in trial. "
                f"Even if every remaining trial converts, conversion tops out at {best_case_conv:.0%}."
            ),
            why_it_matters="The starting base for the growth curve and the claim that 'pilot customers love the product' both depend on this conversion assumption.",
            category="assumption",
            classification="observed_conflict",
            module="radar",
            assumption_type="explicit",
            impact_factors=IF(80, 82, 70),
            confidence_factors=CF(85, 85, 60),
            citations=[
                C("S1", "Pilot customers love the product, so conversion from pilot to paid should be close to 100%."),
                *u.stat("S3", "S3.stat.col.plan-status", role="counter"),
                *u.rows("S3", "plan_status: churned", role="counter", limit=1),
            ],
            calculations=[
                Calculation(label="Paid share today", expression=f"{d['paid']} ÷ {d['unique']}", result=f"{d['paid'] / d['unique']:.0%}"),
                Calculation(label="Best-case conversion (all trials convert)", expression=f"({d['paid']} + {d['trial']}) ÷ {d['unique']}", result=f"{best_case_conv:.0%}"),
            ],
            inference_note="Trials are still open, so final conversion is unknown; the dataset bounds it rather than determining it.",
            recommendation="Report conversion by signup cohort (month) and treat open trials separately; replace 'close to 100%' with the observed range.",
            question="Why have 16 pilot accounts churned, and does their feedback contradict 'pilot customers love the product'?",
            depends_on=["F01"],
            related=["F01", "F07", "F08"],
        ),
        Finding(
            id="F07",
            title=f"Revenue plan uses $79 per account; paying pilots are billed ${d['fee_median']:.0f}",
            summary=(
                f"The $2.37M ARR target assumes $79 per account per month. In the pilot data, the median paying account is billed ${d['fee_median']:.0f}, "
                f"and {d['fee_zero']} accounts marked 'paid' are billed $0. Nothing in the material says whether ${d['fee_median']:.0f} is a pilot discount."
            ),
            why_it_matters=f"At ${d['fee_median']:.0f}, 2,500 accounts produce about ${2500 * d['fee_median'] * 12 / 1e6:.2f}M ARR — about 38% below the stated target.",
            category="contradiction",
            classification="observed_conflict",
            module="contradiction",
            impact_factors=IF(80, 85, 65),
            confidence_factors=CF(78, 85, 55),
            citations=[
                C("S4", "Assumption: Average revenue per account per month | Value: $79", note="Same figure as the brief — Finance inherits it."),
                *u.rows("S3", "plan_status: paid", "monthly_fee_usd: 0", role="counter", limit=1),
            ],
            calculations=[
                Calculation(label="ARR at the pilot price", expression=f"2,500 × ${d['fee_median']:.0f} × 12", result=f"${2500 * d['fee_median'] * 12:,.0f}"),
                Calculation(label="Stated ARR check", expression="2,500 × $79 × 12", result="$2,370,000 (matches brief)"),
            ],
            contradiction=Contradiction(
                claim_a=Claim(statement="Average of $79 per account per month", value="$79", scope="Post-launch pricing", as_of="Brief v1.4",
                              citation=C("S1", "Achieve $2.37M in annual recurring revenue by month 12 at an average of $79 per account per month.", role="claim_a")),
                claim_b=Claim(statement=f"Paying pilot accounts billed ${d['fee_median']:.0f} (median)", value=f"${d['fee_median']:.0f}", scope="Pilot billing", as_of="Pilot export",
                              citation=(u.rows("S3", "plan_status: paid", "monthly_fee_usd: 49", role="claim_b", limit=1) or [C("S3", "monthly_fee_usd: 49", role="claim_b")])[0]),
                comparison=[
                    ComparisonRow(dimension="Value", a="$79 / month", b=f"${d['fee_median']:.0f} / month (median)"),
                    ComparisonRow(dimension="Scope", a="Planned price after launch", b="Pilot price", note="May be a discount — undocumented"),
                    ComparisonRow(dimension="Anomalies", a="—", b=f"{d['fee_zero']} paid accounts at $0"),
                ],
                verdict="possible_conflict",
                verdict_reason="The difference may be explained by pilot discounting, but no source documents a pilot discount or shows any account paying $79.",
                resolution="Pricing owner documents pilot pricing terms and evidence of willingness to pay $79 (e.g., quotes accepted at list price).",
            ),
            recommendation=f"Test list-price acceptance: offer $79 to the next 20 converting pilots and record the acceptance rate; investigate the {d['fee_zero']} paid-at-$0 accounts.",
            question="Has any customer agreed to pay $79 per month, and why are some 'paid' accounts billed $0?",
            related=["F06", "F01", "F08"],
        ),
        Finding(
            id="F08",
            title=f"Pilot dataset integrity: {d['dupes']} duplicate rows, {d['sentinels']} sentinel values, out-of-range NPS",
            summary=(
                f"pilot_accounts.csv has {d['rows']} rows but {d['unique']} unique accounts — {d['dupes']} rows are exact duplicates. jobs_per_week contains {d['sentinels']} rows with 9999, "
                f"which inflates the mean from {d['jobs_mean_clean']:.1f} to {d['jobs_mean_raw']:.1f}. {d['missing_techs']} accounts are missing technician counts and {d['nps_out']} NPS value is outside the 0–10 scale."
            ),
            why_it_matters="Usage averages and account counts from this file feed capacity and growth estimates. Uncleaned, they overstate demand and double-count accounts.",
            category="data_quality",
            classification="observed_conflict",
            module="dataset",
            impact_factors=IF(62, 60, 60),
            confidence_factors=CF(95, 95, 50),
            citations=[
                *u.stat("S3", "S3.stat.dataset"),
                *u.stat("S3", "S3.stat.col.jobs-per-week"),
                *u.rows("S3", "jobs_per_week: 9999", limit=1),
                *u.rows("S3", "nps: 11", limit=1),
            ],
            calculations=[
                Calculation(label="Mean jobs per week, raw", expression="all unique rows", result=f"{d['jobs_mean_raw']:.1f}"),
                Calculation(label="Mean jobs per week, sentinels removed", expression="excluding 9999", result=f"{d['jobs_mean_clean']:.1f}"),
            ],
            recommendation="De-duplicate on account_id, treat 9999 as missing, and re-run any metric derived from this export before it is used for planning.",
            question="Which system produced the duplicates and the 9999 values, and have any reported pilot metrics already used the uncleaned file?",
            related=["F06", "F09", "F07"],
        ),
        Finding(
            id="F09",
            title=f"Region labels are inconsistent — the Northeast is split across {len(d['ne_labels'])} spellings",
            summary=(
                f"{d['ne_total']} accounts belong to the Northeast but are recorded as {', '.join(repr(x) for x in d['ne_labels'])}. "
                f"A naive group-by reports only {d['ne_canonical']} Northeast accounts, understating the largest region."
            ),
            why_it_matters="The regional distributor partnership in the growth plan would be prioritized from exactly this kind of breakdown.",
            category="data_quality",
            classification="observed_conflict",
            module="dataset",
            impact_factors=IF(45, 45, 40),
            confidence_factors=CF(95, 90, 50),
            citations=[*u.stat("S3", "S3.stat.col.region"), *u.rows("S3", "region: NE |", limit=1)],
            calculations=[Calculation(label="Northeast accounts", expression="sum over all label variants", result=f"{d['ne_total']} (vs {d['ne_canonical']} under the canonical label)")],
            recommendation="Replace free-text region with a controlled list in the CRM export and re-map existing values.",
            question="Which regional figures have been presented to distributor partners, and were they computed before the labels were normalized?",
            related=["F08"],
        ),
        Finding(
            id="F10",
            title="A two-person customer success team cannot absorb onboarding at plan volume",
            summary=(
                "The brief keeps support with the existing two-person team. The onboarding workflow needs 90 minutes of customer success time per new account (30 minutes of setup plus a 60-minute call) "
                f"within 48 hours. Even on a straight-line path to 2,500 accounts (~{linear_new_per_month:.0f} new accounts a month), onboarding alone needs about {onboarding_hours:.0f} hours a month, "
                "more than the 280 productive hours available — before any support tickets."
            ),
            why_it_matters="Missed onboarding calls break the 48-hour service level, delay go-live, and are likely to depress conversion just as growth is meant to accelerate.",
            category="assumption",
            classification="inferred_assumption",
            module="radar",
            assumption_type="inferred",
            impact_factors=IF(75, 70, 65),
            confidence_factors=CF(78, 85, 65),
            citations=[
                C("S1", "Support will be handled by the existing two-person customer success team."),
                C("S5", "Customer success schedules a 60-minute onboarding call within 48 hours of signup."),
                C("S5", "a customer success manager spends 30 minutes importing the customer's technician list and service areas"),
                C("S5", "Each customer success manager works 140 productive hours per month, shared between onboarding and support tickets."),
                C("S4", "Assumption: Customer success headcount | Value: 2"),
            ],
            calculations=[
                Calculation(label="New accounts per month (linear path)", expression="(2,500 − 120) ÷ 12", result=f"≈ {linear_new_per_month:.0f}"),
                Calculation(label="Onboarding hours needed", expression=f"{linear_new_per_month:.0f} × 1.5 h", result=f"≈ {onboarding_hours:.0f} h / month"),
                Calculation(label="Capacity", expression="2 people × 140 h", result="280 h / month (shared with support)"),
            ],
            inference_note="The assumption that the existing team is sufficient is implied rather than stated; the capacity arithmetic uses only figures quoted in the sources.",
            recommendation="Model customer success headcount as a function of new accounts, or redesign onboarding as self-serve for small accounts.",
            question="At what monthly signup volume does the 48-hour onboarding service level break, and who owns hiring before that point?",
            depends_on=["F01"],
            related=["F01", "F06"],
        ),
        Finding(
            id="F11",
            title="Unasked: what happens to the business case if the spring season is missed?",
            summary=(
                "The launch date is justified by the spring maintenance season, and the date is already contested across three sources. No source describes a plan, "
                "revised targets or a go/no-go criterion if launch slips past spring."
            ),
            why_it_matters="If spring is when contractors adopt new tools, a slip of a few weeks could cost a full selling season. The month-12 targets have no stated sensitivity to launch timing.",
            category="open_question",
            classification="missing_evidence",
            module="radar",
            impact_factors=IF(85, 90, 75),
            confidence_factors=CF(55, 60, 70),
            citations=[
                C("S1", "ahead of the spring maintenance season", role="context"),
                C("S2", "General availability is targeted for 2 May 2027.", role="context"),
                C("S1", "The main risk is competitor pricing.", role="context", note="The only risk named; timing is absent."),
            ],
            inference_note="That spring is the decisive adoption window is inferred from the brief's wording; no seasonal sales data is included in the material.",
            recommendation="Define a launch go/no-go date and a 'post-spring' variant of the month-12 targets before committing launch marketing spend.",
            question="If general availability lands on 2 May 2027, what are the revised month-12 targets — and is there seasonal evidence that spring adoption matters?",
            depends_on=["F02"],
            related=["F02", "F13"],
        ),
        Finding(
            id="F12",
            title="'CAC below $180 because of referrals' — no referral data exists in the material",
            summary=(
                "The acquisition-cost ceiling depends on most growth coming from referrals. The pilot dataset has no acquisition-channel field, so referral performance cannot be checked. "
                "Budgeted launch marketing alone works out to about $105 per new account, so the ceiling is arithmetically plausible only if referral-driven growth materializes."
            ),
            why_it_matters="If referrals underperform, paid acquisition must fill the gap, and the CAC and marketing budget assumptions fail together.",
            category="missing_evidence",
            classification="missing_evidence",
            module="radar",
            assumption_type="explicit",
            impact_factors=IF(65, 70, 55),
            confidence_factors=CF(60, 70, 40),
            citations=[
                C("S1", "Customer acquisition cost is expected to stay below $180 per account because most growth will come from referrals."),
                C("S4", "Category: Launch marketing | Amount (USD): 250000", role="context"),
                *u.stat("S3", "S3.stat.dataset", role="context"),
            ],
            calculations=[Calculation(label="Marketing spend per new account", expression="$250,000 ÷ (2,500 − 120)", result="≈ $105")],
            inference_note="The absence of channel data is observed from the dataset columns; whether referrals will work is unknown, not disproven.",
            recommendation="Add an acquisition-channel field to signups now, and track the referral share of the next 50 accounts.",
            question="How many of the 120 pilot accounts came from referrals or distributors, and who would know?",
            depends_on=["F01"],
            related=["F01"],
        ),
        Finding(
            id="F13",
            title="The risk register names one risk; the sources reveal at least four",
            summary=(
                "The brief's risk section lists only competitor pricing. Across the other sources, the material exposes dependency, scope, budget and staffing risks "
                "that have no owner or mitigation."
            ),
            why_it_matters="Decision-makers reading the brief alone would not see the risks most likely to stop the launch.",
            category="missing_constraint",
            classification="potential_risk",
            module="radar",
            impact_factors=IF(60, 65, 70),
            confidence_factors=CF(75, 60, 75),
            citations=[
                C("S1", "The main risk is competitor pricing. We will respond with a lower introductory price if needed.", role="context"),
                C("S2", "No fallback routing provider has been evaluated yet.", role="context"),
            ],
            inference_note="That the other risks are 'missing' is a comparison across sources; the brief may simply be out of date.",
            recommendation="Turn findings F02–F10 into a risk register with an owner, a trigger and a mitigation for each.",
            question="Who owns the project risk register, and when was it last reconciled with the engineering and finance documents?",
            related=["F04", "F11", "F05"],
        ),
    ]


def _scenarios(u: _Units, d: dict) -> list[Scenario]:
    growth_cite = C("S1", "We assume paying accounts will grow 35% month-over-month from the 120 pilot accounts we already have")
    return [
        Scenario(
            id="SC1",
            title="Acquisition slower than planned",
            question="What if customer acquisition is 50% slower than expected?",
            assumption="Paying accounts grow 35% month-over-month from 120 pilot accounts.",
            assumption_node_id="f:F01",
            finding_ids=["F01", "F04", "F06", "F10", "F12"],
            parameter=ScenarioParameter(key="slowdown", label="Growth slowdown vs plan", unit="%", baseline=0, min=0, max=90, step=5, default=50),
            constants=[
                ScenarioConstant(key="start", label="Pilot accounts at launch", value=120, unit="accounts", provenance="source", citation=growth_cite.model_copy()),
                ScenarioConstant(key="plan_rate", label="Planned monthly growth", value=0.35, unit="ratio", provenance="source", citation=growth_cite.model_copy()),
                ScenarioConstant(key="target", label="Month-12 target", value=2500, unit="accounts", provenance="source", citation=C("S1", "Reach 2,500 paying accounts within 12 months of launch.")),
                ScenarioConstant(key="arpu", label="Price per account per month", value=79, unit="$", provenance="source", citation=C("S1", "at an average of $79 per account per month")),
                ScenarioConstant(key="calls", label="Route requests per account per day", value=24, unit="requests", provenance="computed",
                                 citation=C("S2", "each account averages 6 technicians and triggers about 4 route re-optimizations per technician per day")),
                ScenarioConstant(key="cap", label="PathCore daily request limit", value=10000, unit="requests", provenance="source", citation=C("S2", "PathCore Starter plan: 10,000 route requests per day")),
            ],
            metrics=[
                ScenarioMetric(key="rate", label="Effective monthly growth", formula="plan_rate * (1 - slowdown / 100)", format="pct"),
                ScenarioMetric(key="accounts12", label="Paying accounts at month 12", formula="start * (1 + rate) ^ 12", format="int", unit="accounts",
                               threshold=2500, threshold_direction="below_bad", threshold_label="below the 2,500 target"),
                ScenarioMetric(key="arr12", label="Annual recurring revenue at month 12", formula="accounts12 * arpu * 12", format="currency",
                               threshold=2370000, threshold_direction="below_bad", threshold_label="below the $2.37M target"),
                ScenarioMetric(key="months_to_target", label="Months to reach 2,500 accounts", formula="ln(target / start) / ln(1 + rate)", format="months",
                               threshold=12, threshold_direction="above_bad", threshold_label="misses the 12-month goal"),
                ScenarioMetric(key="load12", label="PathCore requests per day at month 12", formula="accounts12 * calls", format="int", unit="requests",
                               threshold=10000, threshold_direction="above_bad", threshold_label="over the Starter plan limit"),
            ],
            evidence_conclusions=[
                EvidenceConclusion(text=f"Pilot signups have been roughly flat at about {sum(d['per_month'].values()) / len(d['per_month']):.0f} accounts a month, with no sign of compounding.",
                                   citations=u.stat("S3", "S3.stat.col.signup-month")),
                EvidenceConclusion(text="The PathCore limit is exceeded well before the target even at reduced growth; the delivery plan has no fallback.",
                                   citations=[C("S2", "No fallback routing provider has been evaluated yet.")]),
            ],
            hypothetical_effects=[
                "Illustrative: slower growth would reduce PathCore and support load, possibly delaying — not removing — the capacity problems in F04 and F10.",
                "Illustrative: if growth comes in below plan, the $1.2M–$1.4M budget would be spent against a smaller revenue base, raising the effective acquisition cost.",
                "Illustrative: investors or approvers anchored on $2.37M ARR may need a revised milestone narrative.",
            ],
            info_needed=[
                "Month-by-month pilot-to-paid conversions (the dataset has status, not conversion dates).",
                "Referral and distributor pipeline counts.",
                "Seasonality of contractor software adoption.",
            ],
            experiment="Run a four-week referral sprint with the 41 paid pilots: offer a referral incentive, count referred signups per week, and compare against the 35% curve's implied weekly adds.",
            origin="sample",
        ),
        Scenario(
            id="SC2",
            title="Pilot pricing persists after launch",
            question=f"What if customers will only pay the pilot price of ${d['fee_median']:.0f} per month?",
            assumption="Accounts pay an average of $79 per month.",
            assumption_node_id="f:F07",
            finding_ids=["F07", "F06"],
            parameter=ScenarioParameter(key="price", label="Average price per account", unit="$", baseline=79, min=29, max=129, step=5, default=d["fee_median"]),
            constants=[
                ScenarioConstant(key="accounts", label="Accounts at month 12 (plan)", value=2500, unit="accounts", provenance="source", citation=C("S1", "Reach 2,500 paying accounts within 12 months of launch.")),
                ScenarioConstant(key="target_arr", label="ARR target", value=2370000, unit="$", provenance="source", citation=C("S1", "Achieve $2.37M in annual recurring revenue by month 12")),
            ],
            metrics=[
                ScenarioMetric(key="arr", label="ARR at month 12", formula="accounts * price * 12", format="currency", threshold=2370000, threshold_direction="below_bad", threshold_label="below target"),
                ScenarioMetric(key="gap", label="Gap vs ARR target", formula="arr - target_arr", format="currency"),
                ScenarioMetric(key="accounts_needed", label="Accounts needed to hit the ARR target", formula="ceil(target_arr / (price * 12))", format="int", unit="accounts",
                               threshold=2500, threshold_direction="above_bad", threshold_label="more than the plan"),
            ],
            evidence_conclusions=[
                EvidenceConclusion(text=f"The median paying pilot is billed ${d['fee_median']:.0f}; {d['fee_zero']} 'paid' pilots are billed $0.",
                                   citations=u.rows("S3", "plan_status: paid", "monthly_fee_usd: 49", limit=1)),
            ],
            hypothetical_effects=[
                "Illustrative: a lower price could raise conversion, partly offsetting the revenue gap — no source quantifies this elasticity.",
            ],
            info_needed=["Whether the pilot price was a documented discount.", "Any accepted quote at $79 or above."],
            experiment="Quote $79 to the next 20 converting pilots (with $49 as a fallback) and record acceptance at each price.",
            origin="sample",
        ),
        Scenario(
            id="SC3",
            title="Routing usage heavier than estimated",
            question="What if technicians re-optimize routes more often than 4 times a day?",
            assumption="Each technician triggers about 4 route re-optimizations per day.",
            assumption_node_id="f:F04",
            finding_ids=["F04"],
            parameter=ScenarioParameter(key="reopt", label="Re-optimizations per technician per day", unit="×", baseline=4, min=1, max=12, step=1, default=6),
            constants=[
                ScenarioConstant(key="techs", label="Technicians per account", value=6, unit="technicians", provenance="source",
                                 citation=C("S2", "each account averages 6 technicians")),
                ScenarioConstant(key="accounts", label="Accounts at month 12 (plan)", value=2500, unit="accounts", provenance="source", citation=C("S1", "Reach 2,500 paying accounts within 12 months of launch.")),
                ScenarioConstant(key="cap", label="PathCore daily limit", value=10000, unit="requests", provenance="source", citation=C("S2", "PathCore Starter plan: 10,000 route requests per day")),
            ],
            metrics=[
                ScenarioMetric(key="load", label="Requests per day at 2,500 accounts", formula="accounts * techs * reopt", format="int", unit="requests",
                               threshold=10000, threshold_direction="above_bad", threshold_label="over the daily limit"),
                ScenarioMetric(key="multiple", label="Multiple of the Starter plan limit", formula="load / cap", format="float", unit="×"),
                ScenarioMetric(key="cap_accounts", label="Accounts at which the limit is hit", formula="floor(cap / (techs * reopt))", format="int", unit="accounts"),
            ],
            evidence_conclusions=[
                EvidenceConclusion(text="The Starter plan carries no contractual SLA and no fallback provider has been evaluated.",
                                   citations=[C("S2", "99.5% monthly availability, no contractual SLA"), C("S2", "No fallback routing provider has been evaluated yet.")]),
            ],
            hypothetical_effects=["Illustrative: same-day job changes (emergency calls) could drive re-optimization well above the estimate; no usage logs are provided to check."],
            info_needed=["Re-optimization counts from pilot usage logs.", "PathCore pricing above the Starter tier."],
            experiment="Instrument the pilot app to log route requests per technician per day for two weeks.",
            origin="sample",
        ),
    ]


def build_sample_investigation() -> Investigation:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    sources: list[Source] = []
    units: list[EvidenceUnit] = []
    for sid, name in SAMPLE_FILES:
        src, us = parse_file((FILES_DIR / name).read_bytes(), name, sid, synthetic=True)
        sources.append(src)
        units.extend(us)
    u = _Units(units)
    facts = _dataset_facts()
    findings = _findings(u, facts)
    scenarios = _scenarios(u, facts)
    for f in findings:
        f.origin = "sample"
    verified, unverified = validate_investigation(findings, scenarios, units)
    finding_cites = sum(c.verified for f in findings for c in f.citations)
    cfg = ScoringConfig()
    findings = score_all(findings, cfg)
    graph = build_graph(sources, findings, units)
    return Investigation(
        id=SAMPLE_ID,
        name="Project Meridian — launch readiness",
        question="Can Meridian really reach 2,500 paying accounts in its first year — and what haven't we asked?",
        mode="sample",
        status="ready",
        created_at=now,
        updated_at=now,
        sources=sources,
        units=units,
        findings=findings,
        graph=graph,
        scenarios=scenarios,
        scoring=cfg,
        pipeline=[
            PipelineStep(step="Validate uploads", detail="5 synthetic sample files registered", count=len(sources)),
            PipelineStep(step="Extract text & tables", detail="Parsed with the same parsers used for uploads", count=len(sources)),
            PipelineStep(step="Create evidence units", detail="Source-addressable passages, rows and dataset profiles", count=len(units)),
            PipelineStep(step="Generate findings", detail="Curated sample findings (deterministic, no AI call)", count=len(findings)),
            PipelineStep(step="Validate citations", detail=f"{finding_cites} finding excerpts + {verified - finding_cites} scenario inputs verified · {unverified} unverified", count=verified),
            PipelineStep(step="Score & rank", detail="Weighted impact and confidence", count=len(findings)),
            PipelineStep(step="Build evidence map", detail=f"{len(graph.nodes)} nodes · {len(graph.edges)} edges", count=len(graph.nodes)),
        ],
        limitations=[
            "This is a curated demonstration on synthetic data. Findings were written in advance; they are not live AI output.",
            "Every quoted excerpt was checked against the text extracted from the sample files; dataset figures are recomputed from the CSV when the sample loads.",
            "Scores are transparent weighted ratings, not calibrated probabilities.",
            "Scenario outputs separate arithmetic on cited figures from illustrative, unverified effects.",
            "Human review is required before acting on any finding.",
        ],
    )


_rebuilt_this_process = False


def get_or_create_sample(reset: bool = False) -> Investigation:
    """Rebuild once per server process (so code changes never serve a stale sample), keeping reviewer state."""
    global _rebuilt_this_process
    from app import db

    existing = None if reset else db.get(SAMPLE_ID)
    if existing is not None and _rebuilt_this_process:
        return existing
    inv = build_sample_investigation()
    if existing is not None:
        prior = {f.id: f for f in existing.findings}
        for f in inv.findings:
            if f.id in prior:
                f.status, f.reviewer_note = prior[f.id].status, prior[f.id].reviewer_note
        inv.scoring = existing.scoring
        inv.findings = score_all(inv.findings, inv.scoring)
        inv.created_at = existing.created_at
    db.save(inv)
    _rebuilt_this_process = True
    return inv


def sample_files() -> list[dict]:
    return [{"name": p.name, "size_bytes": p.stat().st_size, "kind": p.suffix.lstrip(".")} for p in sorted(FILES_DIR.iterdir()) if p.is_file()]


__all__ = ["build_sample_investigation", "get_or_create_sample", "sample_files", "SAMPLE_ID", "FILES_DIR"]
