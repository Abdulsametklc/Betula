"""Export compiled notes / gaps to DOCX and PDF."""

from __future__ import annotations

import io
import json
import re
from typing import Any

import fitz
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt, RGBColor


def _parse_gaps(note: dict) -> list[dict]:
    try:
        gaps = json.loads(note.get("gap_list_json") or "[]")
    except Exception:
        gaps = []
    return gaps if isinstance(gaps, list) else []


def _md_lines(markdown: str) -> list[str]:
    return (markdown or "").replace("\r\n", "\n").split("\n")


def _add_runs_with_bold(paragraph, text: str) -> None:
    # Simple **bold** support
    parts = re.split(r"(\*\*[^*]+\*\*)", text)
    for part in parts:
        if part.startswith("**") and part.endswith("**") and len(part) > 4:
            run = paragraph.add_run(part[2:-2])
            run.bold = True
        else:
            paragraph.add_run(part)


def markdown_to_docx(markdown: str, *, title: str = "Betula Notu") -> bytes:
    doc = Document()
    style = doc.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(11)

    heading = doc.add_heading(title, level=0)
    heading.alignment = WD_ALIGN_PARAGRAPH.LEFT
    for run in heading.runs:
        run.font.color.rgb = RGBColor(0xC2, 0x65, 0x2A)

    in_code = False
    code_buf: list[str] = []

    for raw in _md_lines(markdown):
        line = raw.rstrip()
        if line.startswith("```"):
            if in_code:
                p = doc.add_paragraph("\n".join(code_buf))
                for run in p.runs:
                    run.font.name = "Consolas"
                    run.font.size = Pt(9)
                code_buf = []
                in_code = False
            else:
                in_code = True
            continue
        if in_code:
            code_buf.append(line)
            continue

        if not line.strip():
            continue
        if line.startswith("# "):
            doc.add_heading(line[2:].strip(), level=1)
        elif line.startswith("## "):
            doc.add_heading(line[3:].strip(), level=2)
        elif line.startswith("### "):
            doc.add_heading(line[4:].strip(), level=3)
        elif re.match(r"^[-*]\s+", line):
            p = doc.add_paragraph(style="List Bullet")
            _add_runs_with_bold(p, re.sub(r"^[-*]\s+", "", line))
        elif re.match(r"^\d+\.\s+", line):
            p = doc.add_paragraph(style="List Number")
            _add_runs_with_bold(p, re.sub(r"^\d+\.\s+", "", line))
        else:
            p = doc.add_paragraph()
            _add_runs_with_bold(p, line)

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def gaps_to_docx(gaps: list[dict], *, title: str = "Eksik Bilgiler") -> bytes:
    doc = Document()
    heading = doc.add_heading(title, level=0)
    for run in heading.runs:
        run.font.color.rgb = RGBColor(0xC2, 0x65, 0x2A)

    if not gaps:
        doc.add_paragraph("Henüz eksik bilgi kaydı yok.")
    else:
        for i, g in enumerate(gaps, 1):
            topic = (g.get("topic") or f"Konu {i}").strip()
            doc.add_heading(f"{i}. {topic}", level=1)
            reason = (g.get("reason") or "").strip()
            if reason:
                p = doc.add_paragraph()
                run = p.add_run("Neden: ")
                run.bold = True
                p.add_run(reason)
            summary = (g.get("summary") or "").strip()
            if summary:
                p = doc.add_paragraph()
                run = p.add_run("Özet: ")
                run.bold = True
                p.add_run(summary)
            sources = [s for s in (g.get("sources") or []) if isinstance(s, dict) and s.get("href")]
            if sources:
                doc.add_paragraph("Kaynaklar:").runs[0].bold = True
                for s in sources:
                    doc.add_paragraph(
                        f"{s.get('title') or s['href']} — {s['href']}",
                        style="List Bullet",
                    )

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _pdf_write_wrapped(page, text: str, *, x: float, y: float, width: float, fontsize: float = 11) -> float:
    """Write wrapped text; returns next y."""
    if not text:
        return y
    # PyMuPDF insert_textbox
    rect = fitz.Rect(x, y, x + width, y + 700)
    rc = page.insert_textbox(
        rect,
        text,
        fontsize=fontsize,
        fontname="helv",
        align=0,
    )
    # rc is unused height leftover (negative if overflow). Approximate advance:
    lines = max(1, text.count("\n") + 1)
    return y + lines * (fontsize + 4) + 6


def markdown_to_pdf(markdown: str, *, title: str = "Betula Notu") -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)  # A4
    margin = 50
    width = 595 - 2 * margin
    y = margin

    y = _pdf_write_wrapped(page, title, x=margin, y=y, width=width, fontsize=18) + 8

    for raw in _md_lines(markdown):
        line = raw.rstrip()
        if not line.strip() or line.startswith("```"):
            continue
        # Strip simple markdown markers for PDF
        clean = re.sub(r"\*\*([^*]+)\*\*", r"\1", line)
        clean = re.sub(r"^#+\s*", "", clean)
        clean = re.sub(r"^[-*]\s+", "• ", clean)
        if y > 780:
            page = doc.new_page(width=595, height=842)
            y = margin
        size = 14 if line.startswith("# ") else 12 if line.startswith("## ") else 11
        y = _pdf_write_wrapped(page, clean, x=margin, y=y, width=width, fontsize=size)

    out = io.BytesIO()
    doc.save(out)
    doc.close()
    return out.getvalue()


def gaps_to_pdf(gaps: list[dict], *, title: str = "Eksik Bilgiler") -> bytes:
    blocks: list[str] = [title, ""]
    if not gaps:
        blocks.append("Henuz eksik bilgi kaydi yok.")
    else:
        for i, g in enumerate(gaps, 1):
            blocks.append(f"{i}. {(g.get('topic') or 'Konu').strip()}")
            if g.get("reason"):
                blocks.append(f"Neden: {g['reason']}")
            if g.get("summary"):
                blocks.append(f"Ozet: {g['summary']}")
            for s in g.get("sources") or []:
                if isinstance(s, dict) and s.get("href"):
                    blocks.append(f"- {s.get('title') or s['href']}: {s['href']}")
            blocks.append("")
    return markdown_to_pdf("\n\n".join(blocks), title=title)


def build_export(
    note: dict,
    *,
    kind: str,
    fmt: str,
    doc_title: str | None = None,
) -> tuple[bytes, str, str]:
    """
    kind: note | gaps | full
    fmt: md | docx | pdf
    returns: (bytes, media_type, filename)
    """
    kind = (kind or "note").lower()
    fmt = (fmt or "docx").lower()
    gaps = _parse_gaps(note)
    md = note.get("markdown") or ""
    base = re.sub(r"[^\w\-]+", "_", (doc_title or f"betula_{note.get('document_id') or 'note'}") )[:60]

    if kind == "gaps":
        title = "Eksik Bilgiler — Betula"
        if fmt == "docx":
            return gaps_to_docx(gaps, title=title), (
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            ), f"{base}_eksik_bilgiler.docx"
        if fmt == "pdf":
            return gaps_to_pdf(gaps, title=title), "application/pdf", f"{base}_eksik_bilgiler.pdf"
        # md
        lines = ["# Eksik Bilgiler\n"]
        for i, g in enumerate(gaps, 1):
            lines.append(f"## {i}. {g.get('topic') or 'Konu'}\n")
            if g.get("reason"):
                lines.append(f"**Neden:** {g['reason']}\n")
            if g.get("summary"):
                lines.append(f"{g['summary']}\n")
        body = "\n".join(lines).encode("utf-8")
        return body, "text/markdown; charset=utf-8", f"{base}_eksik_bilgiler.md"

    if kind == "full":
        gap_md_parts = ["\n\n---\n\n# Eksik Bilgiler\n"]
        for i, g in enumerate(gaps, 1):
            gap_md_parts.append(f"\n## {i}. {g.get('topic') or 'Konu'}\n")
            if g.get("reason"):
                gap_md_parts.append(f"**Neden:** {g['reason']}\n")
            if g.get("summary"):
                gap_md_parts.append(f"{g['summary']}\n")
        md = md + "".join(gap_md_parts)

    title = "Master Sentez — Betula"
    if fmt == "docx":
        return markdown_to_docx(md, title=title), (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ), f"{base}_master_sentez.docx"
    if fmt == "pdf":
        return markdown_to_pdf(md, title=title), "application/pdf", f"{base}_master_sentez.pdf"
    return md.encode("utf-8"), "text/markdown; charset=utf-8", f"{base}_master_sentez.md"
