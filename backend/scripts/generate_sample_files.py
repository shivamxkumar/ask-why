"""Generate the binary / tabular sample sources (PDF, CSV, XLSX) for the synthetic Meridian investigation.

Run from backend/:  .venv/bin/python scripts/generate_sample_files.py
Outputs are committed so the app never needs to regenerate them at runtime.
"""
from __future__ import annotations

import csv
import random
from pathlib import Path

import openpyxl
import pymupdf

OUT = Path(__file__).resolve().parents[1] / "app" / "sample" / "files"

PDF_PAGES = [
    [
        "# Meridian Engineering Delivery Plan",
        "SYNTHETIC SAMPLE DOCUMENT created for the ASK//WHY demonstration. All details are fictional.",
        "Prepared by: Engineering. Status: approved for planning, 28 September 2026.",
        "## Timeline",
        "Sprint 1 begins 5 October 2026. With two-week sprints, the release is planned as feature-complete at the end of sprint 12 on 21 March 2027.",
        "Feature-complete is followed by a 6-week hardening and beta period with selected pilot accounts.",
        "General availability is targeted for 2 May 2027.",
        "Team: 4 engineers and 1 product designer for the full plan.",
    ],
    [
        "## Requirements",
        "R-07 (P0): Offline job sync. Technicians must be able to view job details and record work while offline; changes sync when connectivity returns.",
        "Source for R-07: field interviews, where 14 of 20 technicians reported daily coverage gaps in basements and rural sites.",
        "R-11 (P0): Route optimization via the PathCore Routing API for up to 40 stops per technician per day.",
        "R-15 (P1): Customer SMS reminders 24 hours and 1 hour before each appointment.",
    ],
    [
        "## Dependencies and capacity",
        "PathCore Starter plan: 10,000 route requests per day, 99.5% monthly availability, no contractual SLA.",
        "Estimated load: each account averages 6 technicians and triggers about 4 route re-optimizations per technician per day.",
        "No fallback routing provider has been evaluated yet.",
        "Infrastructure costs are not included in this plan and are tracked by Finance.",
    ],
]


def make_pdf(path: Path) -> None:
    doc = pymupdf.open()
    for lines in PDF_PAGES:
        page = doc.new_page(width=595, height=842)
        y = 64
        for raw in lines:
            if raw.startswith("# "):
                text, size, font, gap = raw[2:], 18, "hebo", 14
            elif raw.startswith("## "):
                text, size, font, gap = raw[3:], 13, "hebo", 8
            else:
                text, size, font, gap = raw, 10.5, "helv", 10
            width = 595 - 2 * 64
            chars_per_line = int(width / (size * 0.5))
            n_lines = max(1, -(-len(text) // chars_per_line))
            height = n_lines * size * 1.45 + 4
            rect = pymupdf.Rect(64, y, 64 + width, y + height)
            rc = page.insert_textbox(rect, text, fontsize=size, fontname=font)
            if rc < 0:  # not enough room: grow the box
                rect.y1 += -rc + 4
                page.insert_textbox(rect, text, fontsize=size, fontname=font)
                height += -rc + 4
            y += height + gap
        page.insert_text((64, 812), f"Meridian Engineering Delivery Plan — page {doc.page_count}", fontsize=8, fontname="helv")
    doc.save(path)


def make_csv(path: Path) -> None:
    rng = random.Random(20260917)
    months = [("2026-03", 21), ("2026-04", 19), ("2026-05", 20), ("2026-06", 22), ("2026-07", 18), ("2026-08", 20)]
    regions = ["Northeast"] * 38 + ["North East"] * 5 + ["NE"] * 4 + ["northeast"] * 2 + ["Midwest"] * 30 + ["South"] * 25 + ["West"] * 16
    rng.shuffle(regions)
    statuses = ["paid"] * 41 + ["trial"] * 63 + ["churned"] * 16
    rng.shuffle(statuses)
    rows = []
    i = 0
    for month, count in months:
        for _ in range(count):
            i += 1
            status = statuses[i - 1]
            techs = rng.randint(3, 14)
            fee = 49 if status == "paid" else 0
            rows.append(
                {
                    "account_id": f"P-{i:03d}",
                    "signup_month": month,
                    "region": regions[i - 1],
                    "technicians": techs,
                    "jobs_per_week": techs * rng.randint(9, 16),
                    "plan_status": status,
                    "monthly_fee_usd": fee,
                    "nps": rng.choice([6, 7, 8, 8, 9, 9, 10, 4, 5]),
                }
            )
    # Deliberate, documented data-quality defects
    for idx in (8, 23, 37, 52, 66, 81, 99):
        rows[idx]["technicians"] = ""
    rows[44]["jobs_per_week"] = 9999
    rows[90]["jobs_per_week"] = 9999
    paid_rows = [r for r in rows if r["plan_status"] == "paid"]
    for r in paid_rows[5:8]:
        r["monthly_fee_usd"] = 0  # paid accounts billed at $0
    rows[17]["nps"] = 11  # outside the 0-10 scale
    # Exact duplicate rows (export glitch)
    for idx in (12, 40, 71, 103):
        rows.insert(idx + 1, dict(rows[idx]))
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def make_xlsx(path: Path) -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Budget"
    ws.append(["Category", "Amount (USD)", "Notes"])
    budget = [
        ("Engineering salaries", 780000, "4 engineers, 7 months"),
        ("Product design", 120000, "1 designer"),
        ("Launch marketing", 250000, "Distributor co-marketing and paid search"),
        ("Infrastructure (year 1)", 96000, "Cloud hosting and monitoring"),
        ("PathCore Routing API (Starter plan)", 6000, "Annual subscription"),
        ("Customer support tooling", 18000, "Helpdesk and call software"),
        ("Contingency (10%)", 127000, "Rounded"),
        ("Total", 1397000, "Finance working total, SYNTHETIC SAMPLE"),
    ]
    for row in budget:
        ws.append(list(row))
    wa = wb.create_sheet("Assumptions")
    wa.append(["Assumption", "Value", "Owner"])
    for row in [
        ("Launch month", "April 2027", "Finance"),
        ("Monthly growth in paying accounts", "35%", "Product Strategy"),
        ("Average revenue per account per month", "$79", "Product Strategy"),
        ("Customer success headcount", "2", "Operations"),
        ("Data note", "SYNTHETIC SAMPLE created for the ASK//WHY demonstration", "ASK//WHY"),
    ]:
        wa.append(list(row))
    wb.save(path)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    make_pdf(OUT / "engineering_delivery_plan.pdf")
    make_csv(OUT / "pilot_accounts.csv")
    make_xlsx(OUT / "finance_budget.xlsx")
    print("wrote", sorted(p.name for p in OUT.iterdir()))
