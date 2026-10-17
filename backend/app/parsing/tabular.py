"""CSV / XLSX parsers: one table_row unit per data row plus deterministic dataset_stat units."""
from __future__ import annotations

import csv
import io
from datetime import date, datetime, time
from typing import Optional

from app.analysis.dataset import TableAnalysis, analyze_table, row_text, slugify
from app.schemas import EvidenceUnit, Location, Source

from .errors import ParseError
from .text import decode_text

MAX_ROW_UNITS = 5000


def _stat_units(sid: str, prefix: str, analysis: TableAnalysis, sheet: Optional[str]) -> list[EvidenceUnit]:
    units = [EvidenceUnit(
        id=f"{prefix}.stat.dataset", source_id=sid, kind="dataset_stat", location=Location(sheet=sheet),
        label=f"{sheet} · profile" if sheet else "dataset profile", text=analysis.text, section=sheet,
    )]
    used: set[str] = set()
    for ca in analysis.column_analyses:
        slug = ca.slug
        i = 2
        while slug in used:
            slug = f"{ca.slug}-{i}"
            i += 1
        used.add(slug)
        units.append(EvidenceUnit(
            id=f"{prefix}.stat.col.{slug}", source_id=sid, kind="dataset_stat", location=Location(sheet=sheet, column=ca.name),
            label=f"{sheet} · column {ca.name}" if sheet else f"column {ca.name}", text=ca.text, section=sheet,
        ))
    return units


def _row_units(sid: str, prefix: str, columns: list[str], rows: list[list[str]], row_numbers: list[int],
               sheet: Optional[str], source: Source) -> list[EvidenceUnit]:
    units = []
    for r, row in zip(row_numbers, rows):
        if len(units) >= MAX_ROW_UNITS:
            source.warnings.append(
                f"{sheet + ': ' if sheet else ''}only the first {MAX_ROW_UNITS:,} of {len(rows):,} rows became evidence units; "
                "the profile uses all rows."
            )
            break
        units.append(EvidenceUnit(
            id=f"{prefix}.r{r:04d}", source_id=sid, kind="table_row", location=Location(sheet=sheet, row=r),
            label=f"{sheet} · row {r}" if sheet else f"row {r}", text=row_text(columns, row), section=sheet,
        ))
    return units


def _unique_headers(raw: list[str]) -> list[str]:
    out: list[str] = []
    for i, h in enumerate(raw):
        h = (h or "").strip() or f"column_{i + 1}"
        base, k = h, 2
        while h in out:
            h = f"{base}_{k}"
            k += 1
        out.append(h)
    return out


def parse_csv(data: bytes, source: Source) -> list[EvidenceUnit]:
    import pandas as pd

    text = decode_text(data, source)
    sample = text[:16384]
    try:
        delim = csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
    except csv.Error:
        delim = ","
    try:
        df = pd.read_csv(io.StringIO(text), sep=delim, dtype=str, keep_default_na=False, skip_blank_lines=True)
    except Exception as exc:
        raise ParseError(f"{source.name}: could not be parsed as CSV ({exc}).") from exc
    if df.shape[1] == 0:
        raise ParseError(f"{source.name}: no columns found.")
    columns = _unique_headers([str(c) if not str(c).startswith("Unnamed:") else "" for c in df.columns])
    rows = [[("" if v is None else str(v)) for v in rec] for rec in df.itertuples(index=False, name=None)]
    if not rows:
        source.warnings.append("The CSV has a header but no data rows.")
    source.row_count = len(rows)
    units = _row_units(source.id, source.id, columns, rows, list(range(1, len(rows) + 1)), None, source)
    if rows:
        analysis = analyze_table(columns, rows)
        source.profiles = [analysis.profile]
        units = _stat_units(source.id, source.id, analysis, None) + units
    source.summary = f"{len(rows)} rows × {len(columns)} columns"
    return units


def _cell(v) -> str:
    if v is None:
        return ""
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    if isinstance(v, datetime):
        return v.date().isoformat() if v.time() == time(0) else v.isoformat(sep=" ")
    if isinstance(v, date):
        return v.isoformat()
    if isinstance(v, float):
        return str(int(v)) if v.is_integer() else repr(v)
    return str(v).strip()


def parse_xlsx(data: bytes, source: Source) -> list[EvidenceUnit]:
    import openpyxl

    try:
        wb = openpyxl.load_workbook(io.BytesIO(data), data_only=True, read_only=True)
    except Exception as exc:
        raise ParseError(f"{source.name}: not a readable .xlsx workbook ({type(exc).__name__}).") from exc
    stat_units: list[EvidenceUnit] = []
    row_units: list[EvidenceUnit] = []
    total_rows = 0
    used_slugs: set[str] = set()
    for ws in wb.worksheets:
        source.sheet_names.append(ws.title)
        slug = slugify(ws.title)
        base, k = slug, 2
        while slug in used_slugs:
            slug = f"{base}-{k}"
            k += 1
        used_slugs.add(slug)
        prefix = f"{source.id}.{slug}"
        header: Optional[list[str]] = None
        header_idx = 0
        rows: list[list[str]] = []
        numbers: list[int] = []
        for idx, values in enumerate(ws.iter_rows(values_only=True), start=1):
            cells = [_cell(v) for v in values]
            if not any(cells):
                continue
            if header is None:
                header, header_idx = cells, idx
                continue
            rows.append(cells)
            numbers.append(idx - header_idx)
        if header is None:
            continue
        while header and not header[-1] and all(len(r) < len(header) or not r[len(header) - 1] for r in rows):
            header = header[:-1]
        columns = _unique_headers(header)
        rows = [r[: len(columns)] + [""] * (len(columns) - len(r)) for r in rows]
        total_rows += len(rows)
        row_units += _row_units(source.id, prefix, columns, rows, numbers, ws.title, source)
        if rows:
            analysis = analyze_table(columns, rows, sheet=ws.title, row_numbers=numbers)
            source.profiles.append(analysis.profile)
            stat_units += _stat_units(source.id, prefix, analysis, ws.title)
    wb.close()
    source.row_count = total_rows
    n = len(source.sheet_names)
    source.summary = f"{n} sheet{'s' if n != 1 else ''} · {total_rows} rows"
    return stat_units + row_units
