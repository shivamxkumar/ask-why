"""File → (Source, EvidenceUnits). Unit ids and labels are a hard contract shared with the sample builder and UI.

  md / txt : "{sid}.{n:03d}"                 label "line {line}"
  pdf      : "{sid}.p{page}.{k:02d}"          label "p.{page} ¶{k}"
  docx     : "{sid}.{n:03d}"                 label "¶{n}" or "table {t} · row {r}"
  csv      : "{sid}.r{row:04d}"              label "row {row}"     + "{sid}.stat.dataset", "{sid}.stat.col.{col_slug}"
  xlsx     : "{sid}.{sheet}.r{row:04d}"      label "{Sheet} · row {row}" + "{sid}.{sheet}.stat.dataset" / ".stat.col.{col}"
"""
from __future__ import annotations

from datetime import datetime, timezone

from app.schemas import EvidenceUnit, Source

from .errors import ParseError, UnsupportedFileError
from .tabular import parse_csv, parse_xlsx
from .text import parse_docx, parse_pdf, parse_text

SUPPORTED_EXTENSIONS = [".pdf", ".docx", ".txt", ".md", ".markdown", ".csv", ".xlsx"]
MAX_FILE_MB = 15
MAX_FILE_BYTES = MAX_FILE_MB * 1024 * 1024

_LEGACY = {
    ".xls": "Legacy Excel .xls files are not supported — save the workbook as .xlsx and upload again.",
    ".doc": "Legacy Word .doc files are not supported — save the document as .docx and upload again.",
}

__all__ = ["parse_file", "check_upload", "SUPPORTED_EXTENSIONS", "MAX_FILE_MB", "MAX_FILE_BYTES", "ParseError", "UnsupportedFileError"]


def file_extension(filename: str) -> str:
    name = filename.lower().strip()
    return name[name.rfind("."):] if "." in name else ""


def check_upload(filename: str, size: int) -> str:
    """Validate name/size before parsing; returns the normalised extension or raises."""
    ext = file_extension(filename)
    if ext in _LEGACY:
        raise UnsupportedFileError(f"{filename}: {_LEGACY[ext]}")
    if ext not in SUPPORTED_EXTENSIONS:
        raise UnsupportedFileError(
            f"{filename}: unsupported file type '{ext or 'no extension'}'. Supported: {', '.join(SUPPORTED_EXTENSIONS)}."
        )
    if size == 0:
        raise ParseError(f"{filename}: the file is empty.")
    if size > MAX_FILE_BYTES:
        raise ParseError(f"{filename}: {size / 1024 / 1024:.1f} MB exceeds the {MAX_FILE_MB} MB per-file limit.")
    return ext


def parse_file(data: bytes, filename: str, source_id: str, synthetic: bool = False) -> tuple[Source, list[EvidenceUnit]]:
    ext = check_upload(filename, len(data))
    kind = {".markdown": "md"}.get(ext, ext[1:])
    source = Source(
        id=source_id, name=filename, kind=kind, size_bytes=len(data),  # type: ignore[arg-type]
        uploaded_at=datetime.now(timezone.utc).isoformat(timespec="seconds"), synthetic=synthetic,
    )
    try:
        if kind in ("md", "txt"):
            units = parse_text(data, source, markdown=kind == "md")
        elif kind == "pdf":
            units = parse_pdf(data, source)
        elif kind == "docx":
            units = parse_docx(data, source)
        elif kind == "csv":
            units = parse_csv(data, source)
        else:
            units = parse_xlsx(data, source)
    except (ParseError, UnsupportedFileError):
        raise
    except Exception as exc:  # library-level failure → user-facing message
        raise ParseError(f"{filename}: could not be read as {kind.upper()} ({type(exc).__name__}: {exc}).") from exc
    source.unit_count = len(units)
    if not units and not source.warnings:
        source.warnings.append("No text could be extracted from this file.")
    return source, units
