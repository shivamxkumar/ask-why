# ASK//WHY — The Unasked Question Engine

> Your biggest risk might be the question you never asked.

ASK//WHY investigates project documents, datasets and workflow descriptions. It surfaces hidden assumptions, cross-source contradictions, missing constraints, dependencies with no fallback, dataset-quality problems and high-impact unanswered questions. Every finding is ranked by a transparent impact × confidence score and backed by excerpts that have been **verified against the extracted source text**.

## Quick start

```bash
./start.sh            # creates the venv / installs deps on first run
open http://localhost:5174
```

- UI: `http://localhost:5174` (Vite; `/api` is proxied to the backend)
- API: `http://127.0.0.1:8011/api/health`
- Override ports: `ASKWHY_PORT=9000 UI_PORT=5180 ./start.sh`

Then click **Try sample investigation**. It needs no API key and works even if the backend is down (a bundled copy is used).

### Enabling AI analysis (optional)

```bash
cp backend/.env.example backend/.env
# set ANTHROPIC_API_KEY=...  (optional: ASKWHY_MODEL, default claude-opus-5-5)
./start.sh
```

The key stays on the backend; the browser never sees it. When AI is enabled, Claude runs two small typed steps: claim extraction per source, then cross-source findings, both through `messages.parse` with Pydantic schemas. Its findings are merged with the deterministic engine's, and **every excerpt it cites is re-validated**. If the API fails or refuses, the pipeline records the error and finishes with the deterministic engine. Uploaded text is wrapped as untrusted data, and the model is told never to follow instructions found inside it.

### Manual start

```bash
cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --port 8011
cd frontend && npm install && npx vite --port 5174
```

## Deploy

The `Dockerfile` builds one container: FastAPI serves the API **and** the built frontend on the same URL (port `$PORT`, default 8000).

```bash
docker build -t ask-why . && docker run -p 8000:8000 ask-why        # then open http://localhost:8000
```

- **Railway:** `npx @railway/cli login`, then `npx @railway/cli init --name ask-why`, `npx @railway/cli up`, and `npx @railway/cli domain`.
- **Render:** New → Blueprint → select this repo (`render.yaml`, free plan, Docker).
- Optional: set `ANTHROPIC_API_KEY` as a service variable to enable AI analysis.
- Storage is SQLite inside the container. On free tiers it resets on redeploy, and the sample investigation is rebuilt automatically.

## Demo script (≈3 minutes)

1. **Landing** → *Try sample investigation* (synthetic "Project Meridian": brief `.md`, delivery plan `.pdf`, pilot data `.csv`, finance `.xlsx`, onboarding workflow `.txt`).
2. **Findings**: the framing question, an impact × confidence matrix, and findings ranked by priority. Drag *Rank by* to re-weight impact vs confidence.
3. Open **F02 – three launch dates**: the evidence view opens with the Contradiction Lab (claim A vs claim B on paper sheets, a comparison table and the verdict *true conflict*). ASK//WHY never picks a winner.
4. Click **open full source →**: the Sources reader jumps to the exact PDF paragraph (`p.1 ¶5`) with the excerpt highlighted.
5. **Evidence map** (`4`): click F04 (PathCore). The camera glides to its evidence, and the amber *depends on* edge leads to the F01 growth assumption.
6. **Scenario lab** (`5`): "What if acquisition is 50% slower?" Calculations on cited figures are separated from evidence-backed conclusions and from hatched *illustrative, not a prediction* outcomes.
7. **Validate / Resolve / Dismiss** in the inspector. You can also adjust impact; ranking and the report update.
8. **Report** (`6`): print / save as PDF, or download Markdown.
9. Optional live path: download the sample files from the landing page and upload them. The deterministic engine finds ~24 findings with every citation verified.

Keyboard: `1–6` views · `j/k` move through findings · `Enter` open · `Esc` close. Light theme by default; the Dark/Light toggle (top bar and landing page) is remembered per browser.

## How it works

```
upload → validate → parse (PyMuPDF / python-docx / pandas / openpyxl)
       → evidence units (stable ids: S2.p3.04 = source 2, page 3, block 4; S3.r0017 = row 17; S3.stat.col.region)
       → claims & assumptions → cross-source comparison → gaps & failure scenarios
       → findings (deterministic heuristics [+ Claude]) → citation validation → scoring → graph + scenarios
```

| Capability | Where |
|---|---|
| **Blind Spot Radar**: explicit vs inferred assumptions, dependencies without contingency, coverage gaps, open questions | `backend/app/analysis/heuristics.py`, `ai.py` |
| **Contradiction Lab**: dates, budgets, prices, headcount, growth and requirement polarity across sources, with verdicts *true / possible / explainable* | `heuristics.py`, `frontend/src/views/CaseView.tsx` |
| **Dataset audit**: types, missing values, duplicates, IQR outliers, sentinels (9999), out-of-range, inconsistent category labels, suspicious zeros | `backend/app/analysis/dataset.py` |
| **Evidence Constellation**: sources → cited claims → assumptions / constraints / risks → questions → actions (React Flow) | `backend/app/analysis/graph.py`, `frontend/src/components/Constellation.tsx` |
| **Decision Simulator**: declarative scenario metrics evaluated by a safe expression parser | `frontend/src/lib/formula.ts`, `views/Scenarios.tsx` |

### Evidence validation

An excerpt is **verified** only if it appears verbatim, or after normalising case, whitespace, quotes, dashes and line-break hyphenation, in an extracted unit. Validation checks the cited unit first, then the cited source, then all sources; a mis-attributed unit id is corrected and noted. There is no fuzzy matching: paraphrases stay **unverified**, are flagged in red, never enter the graph as evidence, and cap the finding's confidence. See `backend/app/analysis/validation.py`.

### Scoring (documented & configurable)

```
impact     = 0.5·consequence + 0.3·decision_relevance + 0.2·breadth
confidence = 0.5·evidence_strength + 0.3·specificity + 0.2·corroboration   (evidence ≤ 35 if no citation verified)
priority   = w·impact + (1−w)·confidence        (w = 0.65 by default; adjustable in the UI)
```

Confidence is an evidence-strength rating, **not** a calibrated probability. Each finding shows its score breakdown ("why this score?"), and reviewers can override impact. See `backend/app/analysis/scoring.py`.

### Sample mode

The sample sources in `backend/app/sample/files/` are synthetic and labelled as such. They are parsed by the same parsers as uploads. The curated findings (`backend/app/sample/build.py`) cite by excerpt only, the same validator verifies them, and dataset figures are recomputed from the CSV at load time. The UI labels sample results as *curated, not live AI output*. `frontend/src/data/sample-investigation.json` is the offline fallback; regenerate it with `cd backend && .venv/bin/python scripts/export_sample.py` (a test fails if it drifts).

## API

| Method | Path | |
|---|---|---|
| GET | `/api/health` | AI availability, supported types |
| POST | `/api/investigations` | multipart `files[]` (≤12, ≤15 MB each), `name`, `question`, `use_ai`; returns 202 and analyses in the background |
| GET | `/api/investigations`, `/api/investigations/{id}` | list / fetch (poll while `status=analyzing`) |
| PATCH | `/api/investigations/{id}/findings/{fid}` | `status`, `reviewer_note`, `impact_override` |
| PUT | `/api/investigations/{id}/scoring` | re-rank with new weights |
| GET | `/api/investigations/{id}/report.md` | Markdown report |
| GET/POST | `/api/sample`, `/api/sample/reset`, `/api/sample/files/{name}` | sample investigation & files |

Persistence: SQLite at `backend/data/askwhy.db` (`ASKWHY_DB` to override).

## Tests

```bash
cd backend && .venv/bin/python -m pytest -q     # parsing, profiling, heuristics, validation, scoring, API schemas, AI conversion (no network), sample integrity
cd frontend && npx vitest run                   # formula evaluator, scenario arithmetic, excerpt locator, ranking
```

## Supported formats & limitations

- **PDF** (text layer only, no OCR; page numbers preserved) · **DOCX** (paragraphs, headings, tables) · **TXT / MD** (paragraphs and list items, line numbers) · **CSV** (delimiter sniffing) · **XLSX** (all sheets, first non-empty row as header). Legacy `.doc` / `.xls` are rejected with a clear message.
- The deterministic engine is pattern-based. It finds explicit numbers, dates, cues and polarity conflicts, but it can miss contradictions phrased in different vocabulary (e.g. "finish" vs "go-live") and can flag some redundant pairwise conflicts.
- AI findings depend on the model and can be incomplete. Citations are checked for presence, not for whether the reasoning built on them is correct.
- Scenario outputs are arithmetic on cited figures plus clearly labelled hypotheticals, not forecasts.
- **Human review is required before acting on any finding.**
