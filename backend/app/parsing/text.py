"""Prose parsers: Markdown / plain text, PDF (PyMuPDF blocks) and DOCX."""
from __future__ import annotations

import io
import re

from app.schemas import EvidenceUnit, Location, Source

from .errors import ParseError

_HEADING = re.compile(r"^\s{0,3}(#{1,6})\s+(.*?)\s*#*\s*$")
_BULLET = re.compile(r"^\s*[-*+]\s+(.*)$")
_NUMBERED = re.compile(r"^\s*(?:Step\s+\d+[.:)]|\d+[.)])\s+", re.I)
_QUOTE = re.compile(r"^\s*>\s?(.*)$")
_TABLE_SEP = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$")


def decode_text(data: bytes, source: Source) -> str:
    head = data[:8192]
    if b"\x00" in head:
        raise ParseError(f"{source.name}: looks like a binary file, not text.")
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = data.decode("latin-1")
        source.warnings.append("File is not valid UTF-8; decoded as Latin-1 — some characters may be wrong.")
    sample = text[:8192]
    if sample:
        ctrl = sum(1 for ch in sample if ord(ch) < 32 and ch not in "\n\r\t\f")
        if ctrl / len(sample) > 0.05:
            raise ParseError(f"{source.name}: contains binary data, not readable text.")
    return text.replace("\r\n", "\n").replace("\r", "\n")


def parse_text(data: bytes, source: Source, markdown: bool) -> list[EvidenceUnit]:
    text = decode_text(data, source)
    lines = text.split("\n")
    # Each block: [kind, first_line, [text parts]]
    blocks: list[list] = []
    current: list | None = None
    in_fence = False
    for i, raw in enumerate(lines, start=1):
        line = raw.rstrip()
        if line.strip().startswith("```"):
            in_fence = not in_fence
            current = None
            continue
        if not line.strip():
            current = None
            continue
        if in_fence:
            if current is None:
                current = ["paragraph", i, []]
                blocks.append(current)
            current[2].append(line.strip())
            continue
        h = _HEADING.match(line)
        if h:
            blocks.append(["heading", i, [h.group(2).strip()]])
            current = None
            continue
        if markdown and line.lstrip().startswith("|"):
            if _TABLE_SEP.match(line):
                continue
            blocks.append(["table_row", i, [line.strip()]])
            current = None
            continue
        q = _QUOTE.match(line)
        content = q.group(1) if q else line
        b = _BULLET.match(content)
        if b:
            current = ["list_item", i, [b.group(1).strip()]]
            blocks.append(current)
            continue
        if _NUMBERED.match(content):
            current = ["list_item", i, [content.strip()]]
            blocks.append(current)
            continue
        if current is None or current[0] == "heading":
            current = ["paragraph", i, []]
            blocks.append(current)
        current[2].append(content.strip())

    units: list[EvidenceUnit] = []
    section: str | None = None
    for kind, line_no, parts in blocks:
        body = " ".join(p for p in parts if p).strip()
        if not body:
            continue
        if kind == "heading":
            section = body
        n = len(units) + 1
        units.append(EvidenceUnit(
            id=f"{source.id}.{n:03d}", source_id=source.id, kind=kind,
            location=Location(line=line_no, paragraph=n), label=f"line {line_no}", text=body, section=section,
        ))
    source.summary = f"{len(lines)} lines · {len(units)} passages"
    return units


# ---------------------------------------------------------------- PDF
def _join_lines(text: str) -> str:
    lines = [l.strip() for l in text.split("\n")]
    out = ""
    for l in lines:
        if not l:
            continue
        if not out:
            out = l
        elif out.endswith("-") and l[:1].islower() and len(out) > 1 and out[-2].isalpha():
            out = out[:-1] + l
        else:
            out += " " + l
    return out


def parse_pdf(data: bytes, source: Source) -> list[EvidenceUnit]:
    import pymupdf

    try:
        doc = pymupdf.open(stream=data, filetype="pdf")
    except Exception as exc:
        raise ParseError(f"{source.name}: not a readable PDF ({exc}).") from exc
    if doc.needs_pass:
        raise ParseError(f"{source.name}: the PDF is password-protected.")
    pages: list[list[tuple[str, float, float]]] = []  # (text, y0, rel_y)
    for page in doc:
        h = page.rect.height or 1
        blocks = [b for b in page.get_text("blocks") if b[6] == 0]
        blocks.sort(key=lambda b: (round(b[1], 1), b[0]))
        items = []
        for b in blocks:
            t = _join_lines(b[4])
            if t:
                items.append((t, b[1], b[1] / h, b[3] / h))
        pages.append(items)
    source.page_count = len(pages)

    # running headers / footers: identical except digits on ≥2 pages, located in the top or bottom margin band
    def key(t: str) -> str:
        return re.sub(r"\d+", "#", t.strip().lower())

    counts: dict[str, set[int]] = {}
    for pi, items in enumerate(pages):
        for t, _, top, bottom in items:
            if top < 0.12 or bottom > 0.88:
                counts.setdefault(key(t), set()).add(pi)
    running = {k for k, ps in counts.items() if len(ps) >= 2} if len(pages) >= 2 else set()

    units: list[EvidenceUnit] = []
    section: str | None = None
    for pi, items in enumerate(pages, start=1):
        k = 0
        for t, _, top, bottom in items:
            if (top < 0.12 or bottom > 0.88) and key(t) in running:
                continue
            k += 1
            is_heading = len(t) < 60 and not re.search(r"[.!?:;,]$", t) and len(t.split()) <= 9 and t[:1].isupper()
            if is_heading:
                section = t
            units.append(EvidenceUnit(
                id=f"{source.id}.p{pi}.{k:02d}", source_id=source.id, kind="heading" if is_heading else "paragraph",
                location=Location(page=pi, paragraph=k), label=f"p.{pi} ¶{k}", text=t, section=section,
            ))
    if not units:
        source.warnings.append("No extractable text — scanned PDFs are not OCR'd.")
    elif len(pages) > 1 and sum(1 for items in pages if not items) >= max(1, len(pages) // 2):
        source.warnings.append("Several pages have no extractable text — scanned PDFs are not OCR'd.")
    source.summary = f"{len(pages)} page{'s' if len(pages) != 1 else ''} · {len(units)} passages"
    return units


# ---------------------------------------------------------------- DOCX
def parse_docx(data: bytes, source: Source) -> list[EvidenceUnit]:
    import docx
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    try:
        document = docx.Document(io.BytesIO(data))
    except Exception as exc:
        raise ParseError(f"{source.name}: not a readable .docx file ({type(exc).__name__}).") from exc
    units: list[EvidenceUnit] = []
    section: str | None = None
    t_index = 0
    paragraphs = 0
    for el in document.element.body.iterchildren():
        tag = el.tag.rsplit("}", 1)[-1]
        if tag == "p":
            p = Paragraph(el, document)
            text = " ".join(p.text.split())
            if not text:
                continue
            style = (p.style.name if p.style is not None else "") or ""
            is_heading = style.startswith("Heading") or style == "Title"
            if is_heading:
                section = text
            n = len(units) + 1
            paragraphs += 1
            list_like = "List" in style
            units.append(EvidenceUnit(
                id=f"{source.id}.{n:03d}", source_id=source.id,
                kind="heading" if is_heading else ("list_item" if list_like else "paragraph"),
                location=Location(paragraph=n), label=f"¶{n}", text=text, section=section,
            ))
        elif tag == "tbl":
            t_index += 1
            table = Table(el, document)
            for r_i, row in enumerate(table.rows, start=1):
                cells: list[str] = []
                prev = None
                for c in row.cells:
                    ct = " ".join(c.text.split())
                    if c._tc is prev:  # merged cell repeats
                        continue
                    prev = c._tc
                    cells.append(ct)
                text = " | ".join(cells).strip()
                if not text.replace("|", "").strip():
                    continue
                n = len(units) + 1
                units.append(EvidenceUnit(
                    id=f"{source.id}.{n:03d}", source_id=source.id, kind="table_row",
                    location=Location(paragraph=n, row=r_i), label=f"table {t_index} · row {r_i}", text=text, section=section,
                ))
    source.summary = f"{paragraphs} paragraphs" + (f" · {t_index} table{'s' if t_index != 1 else ''}" if t_index else "") + f" · {len(units)} passages"
    return units
