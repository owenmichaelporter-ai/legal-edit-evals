"""Read, snapshot, and edit .docx files by section number (e.g. "7.2")."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from docx import Document

SECTION_RE = re.compile(r"^(\d+(?:\.\d+)*)\.?\s")


@dataclass
class ParaSnapshot:
    section: str | None      # "7.2", "7" for headings, None for unnumbered text
    text: str
    style: str
    bold_runs: list[str] = field(default_factory=list)


@dataclass
class DocSnapshot:
    paragraphs: list[ParaSnapshot]
    tables: list[list[list[str]]]

    def sections(self) -> dict[str, str]:
        return {p.section: p.text for p in self.paragraphs if p.section}

    def section_ids(self) -> set[str]:
        return {p.section for p in self.paragraphs if p.section}


def section_of(text: str) -> str | None:
    m = SECTION_RE.match(text.strip())
    return m.group(1) if m else None


def snapshot(path_or_doc) -> DocSnapshot:
    doc = Document(path_or_doc) if not hasattr(path_or_doc, "paragraphs") else path_or_doc
    paras = [
        ParaSnapshot(
            section=section_of(p.text),
            text=p.text.strip(),
            style=p.style.name,
            bold_runs=[r.text.strip() for r in p.runs if r.bold and r.text.strip()],
        )
        for p in doc.paragraphs
        if p.text.strip()
    ]
    tables = [[[c.text for c in row.cells] for row in t.rows] for t in doc.tables]
    return DocSnapshot(paras, tables)


def apply_edits(src_path: str, edits: list[dict], out_path: str) -> list[str]:
    """Replace the text of numbered paragraphs, keeping paragraph style and,
    where possible, the bold caption run. Returns a list of edit-application
    errors (e.g. the model targeted a section that does not exist)."""
    doc = Document(src_path)
    by_section = {section_of(p.text): p for p in doc.paragraphs if section_of(p.text)}
    errors = []
    for e in edits:
        sec, new_text = str(e.get("section", "")).strip(), e.get("new_text", "")
        p = by_section.get(sec)
        if p is None:
            errors.append(f"edit targets missing section {sec!r}")
            continue
        _replace_paragraph_text(p, new_text)
    doc.save(out_path)
    return errors


def _replace_paragraph_text(p, new_text: str) -> None:
    runs = p.runs
    caption = next((r for r in runs if r.bold and r.text.strip()), None)
    # Keep "7.2 " + bold "Caption." + plain body when the new text still starts that way.
    if caption and len(runs) >= 3:
        prefix = runs[0].text + caption.text
        if new_text.startswith(prefix):
            for r in runs[2:]:
                r.text = ""
            runs[2].text = new_text[len(prefix):]
            return
    for r in runs[1:]:
        r._element.getparent().remove(r._element)
    if runs:
        runs[0].text = new_text
    else:
        p.add_run(new_text)
