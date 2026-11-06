"""The system under test: an LLM that edits a contract from a plain-English
instruction, the way a Word drafting add-in would.

Swap in your own prompt (or call a real product's API) here. The eval
harness only cares that edit() returns {"edits": [...], "flag": "..."}.
"""
from __future__ import annotations

import json

from graders.llm import complete

EDIT_PROMPT = """You are a legal drafting assistant editing an employment agreement.

DOCUMENT (one numbered paragraph per line):
{document}

INSTRUCTION FROM THE ATTORNEY:
{instruction}

Rules:
- Edit only the paragraph(s) needed to carry out the instruction.
- Return each edited paragraph in full, keeping its number and caption (e.g. "7.2 Non-Solicitation. ...").
- Use the agreement's existing defined terms. Only cite sections that exist.
- If the instruction is ambiguous, conflicts with the document, or asks for something you cannot do reliably, make NO edits and explain in "flag".

Reply with JSON only:
{{"edits": [{{"section": "<number>", "new_text": "<full paragraph>"}}], "flag": "<empty, or why you did not edit>"}}"""


def build_prompt(document_lines: list[str], case: dict, model: str) -> str:
    prompt = EDIT_PROMPT.format(document="\n".join(document_lines), instruction=case["instruction"])
    if model.startswith("mock"):  # hints only the offline mock can see
        if not case.get("expect_flag"):
            prompt += f"\nTARGET SECTION HINT: {case['target_sections'][0]}"
            prompt += f"\nMOCK_PHRASES: {' '.join(case.get('must_include', []))}"
            prompt += f"\nMOCK_BANNED: {'|'.join(case.get('must_not_include', []))}"
    return prompt


def edit(document_lines: list[str], case: dict, model: str) -> tuple[dict, str]:
    raw = complete(build_prompt(document_lines, case, model), model=model)
    try:
        out = json.loads(raw[raw.index("{"): raw.rindex("}") + 1])
    except ValueError:
        out = {"edits": [], "flag": "", "parse_error": raw[:300]}
    out.setdefault("edits", [])
    out.setdefault("flag", "")
    return out, raw
