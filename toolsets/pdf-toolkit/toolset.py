"""
pdf‑toolkit — Extract text, read metadata, list form fields, and merge PDFs.
================================================================================

Handles the messy reality of PDF parsing (multi‑column layouts,
Unicode, encrypted files) so agents don't have to guess.
"""

import io
import json
import sys
from pathlib import Path

try:
    from toolstore.toolset import tool
except ImportError:
    def tool(fn):
        return fn  # no‑op when toolstore package not installed


# ── pdf_extract ────────────────────────────────────────────────────────

@tool
def pdf_extract(*, filepath: str, first_page: int = 1,
                last_page: int = 0) -> dict:
    """Extract readable text from a PDF using layout‑aware extraction.

    Args:
        filepath:   Path to the PDF file.
        first_page: First page to extract (1‑based, default 1).
        last_page:  Last page to extract (0 = all pages).

    Returns:
        dict with keys:
          text      — extracted text (pages separated by form‑feeds)
          pages     — number of pages processed
          total     — total pages in the document
    """
    try:
        import pdfplumber
    except ImportError:
        return {"error": "pdfplumber not installed — run: pip install pdfplumber"}

    p = Path(filepath).expanduser().resolve()
    if not p.exists():
        return {"error": f"File not found: {p}"}

    try:
        pdf = pdfplumber.open(p)
    except Exception as exc:
        return {"error": f"Cannot open PDF: {exc}"}

    total = len(pdf.pages)
    if last_page == 0:
        last_page = total
    first_page = max(1, first_page)
    last_page = min(last_page, total)

    texts = []
    for i in range(first_page - 1, last_page):
        try:
            page_text = pdf.pages[i].extract_text() or ""
            texts.append(page_text)
        except Exception:
            texts.append("")

    pdf.close()
    return {"text": "\n\n".join(texts), "pages": len(texts),
            "total": total, "range": f"{first_page}-{last_page}"}


# ── pdf_meta ───────────────────────────────────────────────────────────

@tool
def pdf_meta(*, filepath: str) -> dict:
    """Read metadata from a PDF file without extracting content.

    Args:
        filepath: Path to the PDF file.

    Returns:
        dict with keys:
          filename, pages, title, author, subject, creator,
          producer, encrypted, file_size_bytes
    """
    p = Path(filepath).expanduser().resolve()
    if not p.exists():
        return {"error": f"File not found: {p}"}

    file_size = p.stat().st_size

    try:
        from PyPDF2 import PdfReader
    except ImportError:
        return {"error": "PyPDF2 not installed — run: pip install PyPDF2"}

    try:
        reader = PdfReader(p)
    except Exception as exc:
        return {"error": f"Cannot read PDF: {exc}"}

    info = reader.metadata or {}
    return {
        "filename": p.name,
        "pages": len(reader.pages),
        "title": (info.get("/Title") or "").strip() or None,
        "author": (info.get("/Author") or "").strip() or None,
        "subject": (info.get("/Subject") or "").strip() or None,
        "creator": (info.get("/Creator") or "").strip() or None,
        "producer": (info.get("/Producer") or "").strip() or None,
        "encrypted": reader.is_encrypted,
        "file_size_bytes": file_size,
    }


# ── pdf_merge ──────────────────────────────────────────────────────────

@tool
def pdf_merge(*, inputs: list, output: str) -> dict:
    """Merge multiple PDF files into a single output file.

    Args:
        inputs: List of file paths to merge (order is preserved).
        output: Path for the merged output PDF.

    Returns:
        dict with "written" (absolute path), "pages", and "sources" count.
    """
    try:
        from PyPDF2 import PdfReader, PdfWriter
    except ImportError:
        return {"error": "PyPDF2 not installed — run: pip install PyPDF2"}

    if not inputs:
        return {"error": "No input files provided"}

    writer = PdfWriter()
    total_pages = 0
    sources = 0

    for path_str in inputs:
        p = Path(path_str).expanduser().resolve()
        if not p.exists():
            return {"error": f"Input not found: {p}"}
        try:
            reader = PdfReader(p)
        except Exception as exc:
            return {"error": f"Cannot read {p.name}: {exc}"}
        for page in reader.pages:
            writer.add_page(page)
        total_pages += len(reader.pages)
        sources += 1

    out = Path(output).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "wb") as f:
        writer.write(f)

    return {"written": str(out), "pages": total_pages, "sources": sources}


# ── pdf_form_fields ────────────────────────────────────────────────────

@tool
def pdf_form_fields(*, filepath: str) -> dict:
    """List all fillable form fields in a PDF with their types and current values.

    Args:
        filepath: Path to the PDF file.

    Returns:
        dict with:
          has_fields — True if the PDF contains any form fields
          count      — total number of fields found
          fields     — list of dicts: {name, type, value, flags}
    """
    try:
        from PyPDF2 import PdfReader
    except ImportError:
        return {"error": "PyPDF2 not installed — run: pip install PyPDF2"}

    p = Path(filepath).expanduser().resolve()
    if not p.exists():
        return {"error": f"File not found: {p}"}

    try:
        reader = PdfReader(p)
    except Exception as exc:
        return {"error": f"Cannot read PDF: {exc}"}

    fields = []
    try:
        raw_fields = reader.get_fields()
    except Exception:
        raw_fields = None

    if raw_fields:
        for name, info in raw_fields.items():
            if info is None:
                continue
            field = {
                "name": name,
                "type": str(info.get("/FT", "unknown")).lstrip("/"),
                "value": str(info.get("/V", "")) if info.get("/V") else None,
                "flags": [],
            }
            ff = info.get("/Ff", 0)
            if isinstance(ff, int):
                if ff & 1: field["flags"].append("readOnly")
                if ff & 2: field["flags"].append("required")
                if ff & 4: field["flags"].append("noExport")
                if ff & 0x10000: field["flags"].append("multiLine")
                if ff & 0x20000: field["flags"].append("password")
            opts = info.get("/Opt")
            if opts:
                field["options"] = [str(o) if not isinstance(o, list) else str(o[0])
                                     for o in opts]
            fields.append(field)

    return {
        "has_fields": len(fields) > 0,
        "count": len(fields),
        "fields": fields,
        "filename": p.name,
    }
