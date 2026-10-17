# ASK//WHY — Demo video voiceover script

Video: `ASK-WHY_Demo.mp4` (3:06). Timecodes match the on-screen caption numbers (01–23).
Pace: calm and confident, ~145 words per minute. Say "ASK//WHY" as **"Ask Why"**. Pause briefly at each "—".

| # | Time | On screen | Voiceover |
|---|------|-----------|-----------|
| 01 | 0:01 – 0:05 | Landing page | This is Ask Why — the unasked question engine. |
| 02 | 0:05 – 0:12 | Three starting points | Pick a starting point — a project, a dataset, or a workflow — and it frames the question for your investigation. |
| 03 | 0:12 – 0:18 | Upload form | Drop in PDFs, Word files, Markdown, CSVs or spreadsheets. Every file is checked before analysis begins. |
| 04 | 0:18 – 0:22 | Sample button | Let's open the sample investigation — no API key needed. |
| 05 | 0:22 – 0:26 | Findings overview | Thirteen findings, ranked by priority. Every citation verified. |
| 06 | 0:26 – 0:34 | Impact × confidence chart | This chart plots impact against confidence. Top left is the danger zone: high impact, weak evidence — validate those first. |
| 07 | 0:34 – 0:49 | Filters & ranking slider | Filter by severity or category, by engine or review status. And if evidence matters more to you than impact, drag this slider — the whole ranking re-orders instantly, using a formula you can actually see. |
| 08 | 0:49 – 0:56 | Evidence view opens | Open a finding and the workspace becomes a dossier — the claim, why it matters, and the controls to review it. |
| 09 | 0:56 – 1:05 | Contradiction Lab | Three documents, three launch dates. Both claims sit side by side with their exact sources — and a verdict, never a silent pick. |
| 10 | 1:05 – 1:12 | Evidence tabs | Every quote is matched word for word against the original file — down to the page, paragraph, or spreadsheet row. |
| 11 | 1:12 – 1:18 | Score breakdown | Scores aren't a black box. Open the breakdown and see exactly why. |
| 12 | 1:18 – 1:26 | Validate / Reopen | Reviewers can validate, resolve or dismiss each finding, and leave notes — the report keeps up. |
| 13 | 1:26 – 1:31 | Evidence graph | Below is its evidence chain — from source, to passage, to next action. |
| 14 | 1:31 – 1:36 | Sources reader | One click jumps to the exact paragraph in the original PDF. |
| 15 | 1:36 – 1:44 | Dataset profile | Spreadsheets get a full audit: duplicate rows, missing values, fake "nine-nine-nine-nine" values, impossible scores and messy labels. |
| 16 | 1:44 – 1:54 | PathCore finding | Here's a blind spot: one routing API, no fallback. Using the plan's own numbers, it hits its daily limit at about four hundred accounts. |
| 17 | 1:54 – 2:04 | Evidence map | The evidence map shows every source and finding at a glance. Click one, and it isolates that finding's evidence — and the assumption it depends on. |
| 18 | 2:04 – 2:17 | Scenario slider | Now challenge an assumption. What if customers arrive fifty percent slower? Drag the slider and watch accounts, revenue and API load recalculate live — with a warning the moment a target breaks. |
| 19 | 2:17 – 2:30 | Evidence vs hypothetical | Crucially, what the evidence supports is kept apart from what's only illustrative. Ask Why never dresses up a guess as a prediction. Another scenario: what if routes are re-optimised more often? |
| 20 | 2:30 – 2:37 | Report | Everything rolls into a print-ready report — findings, contradictions, open questions and next actions. |
| 21 | 2:37 – 2:46 | Light / dark toggle | Light by default, dark when you want it — one click, and it remembers your choice. |
| 22 | 2:46 – 2:55 | Live upload & pipeline | And it works on real files. Upload five documents and watch the pipeline parse, compare, verify and rank — live. |
| 23 | 2:55 – 3:02 | Live results | Twenty-four findings, every citation verified. Add a Claude API key for even deeper analysis. |
| — | 3:02 – 3:06 | End card | Your biggest risk might be the question you never asked. |

**Word count:** ~430 words · **Speaking time:** ~3:00

---

## Plain read-through (for a teleprompter)

This is Ask Why — the unasked question engine.

Pick a starting point — a project, a dataset, or a workflow — and it frames the question for your investigation.

Drop in PDFs, Word files, Markdown, CSVs or spreadsheets. Every file is checked before analysis begins.

Let's open the sample investigation — no API key needed.

Thirteen findings, ranked by priority. Every citation verified.

This chart plots impact against confidence. Top left is the danger zone: high impact, weak evidence — validate those first.

Filter by severity or category, by engine or review status. And if evidence matters more to you than impact, drag this slider — the whole ranking re-orders instantly, using a formula you can actually see.

Open a finding and the workspace becomes a dossier — the claim, why it matters, and the controls to review it.

Three documents, three launch dates. Both claims sit side by side with their exact sources — and a verdict, never a silent pick.

Every quote is matched word for word against the original file — down to the page, paragraph, or spreadsheet row.

Scores aren't a black box. Open the breakdown and see exactly why.

Reviewers can validate, resolve or dismiss each finding, and leave notes — the report keeps up.

Below is its evidence chain — from source, to passage, to next action.

One click jumps to the exact paragraph in the original PDF.

Spreadsheets get a full audit: duplicate rows, missing values, fake "nine-nine-nine-nine" values, impossible scores and messy labels.

Here's a blind spot: one routing API, no fallback. Using the plan's own numbers, it hits its daily limit at about four hundred accounts.

The evidence map shows every source and finding at a glance. Click one, and it isolates that finding's evidence — and the assumption it depends on.

Now challenge an assumption. What if customers arrive fifty percent slower? Drag the slider and watch accounts, revenue and API load recalculate live — with a warning the moment a target breaks.

Crucially, what the evidence supports is kept apart from what's only illustrative. Ask Why never dresses up a guess as a prediction. Another scenario: what if routes are re-optimised more often?

Everything rolls into a print-ready report — findings, contradictions, open questions and next actions.

Light by default, dark when you want it — one click, and it remembers your choice.

And it works on real files. Upload five documents and watch the pipeline parse, compare, verify and rank — live.

Twenty-four findings, every citation verified. Add a Claude API key for even deeper analysis.

Your biggest risk might be the question you never asked.

---

## Recording tips

- Record each numbered line as its own take, then place it at its timecode in any editor (CapCut, iMovie, DaVinci Resolve).
- If a line runs long, drop the words after the last "—"; the meaning survives.
- To put a single voice track onto the video without re-encoding it:

  ```bash
  ffmpeg -i ASK-WHY_Demo.mp4 -i voiceover.m4a -map 0:v -map 1:a -c:v copy -c:a aac -b:a 192k -shortest ASK-WHY_Demo_VO.mp4
  ```
