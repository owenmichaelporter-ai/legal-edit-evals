"""Deterministic graders. Same input -> same verdict, every time.

Each check returns a CheckResult. A trial passes the deterministic layer only
if every applicable check passes.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .docx_tools import DocSnapshot

CITE_RE = re.compile(r"Section\s+(\d+(?:\.\d+)*)")


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str = ""


def run_checks(case: dict, before: DocSnapshot, after: DocSnapshot,
               model_out: dict, apply_errors: list[str]) -> list[CheckResult]:
    if case.get("expect_flag"):
        return [check_flagged(model_out, after, before)]

    targets = [str(s) for s in case.get("target_sections", [])]
    allowed = set(targets) | {str(s) for s in case.get("may_also_change", [])}
    return [
        check_edit_applied(apply_errors),
        check_targets_changed(targets, before, after),
        check_only_allowed_changed(allowed, before, after),
        check_must_include(case.get("must_include", []), targets, after),
        check_must_not_include(case.get("must_not_include", []), targets, after),
        check_structure(before, after),
        check_citations(targets, after),
    ]


# --- individual checks -----------------------------------------------------

def check_edit_applied(errors: list[str]) -> CheckResult:
    return CheckResult("edit_applied", not errors, "; ".join(errors))


def check_targets_changed(targets, before, after) -> CheckResult:
    b, a = before.sections(), after.sections()
    unchanged = [s for s in targets if b.get(s) == a.get(s)]
    return CheckResult("targets_changed", not unchanged,
                       f"target(s) not edited: {unchanged}" if unchanged else "")


def check_only_allowed_changed(allowed, before, after) -> CheckResult:
    b, a = before.sections(), after.sections()
    collateral = sorted(s for s in b if s not in allowed and b[s] != a.get(s))
    tables_changed = before.tables != after.tables
    detail = []
    if collateral:
        detail.append(f"unrequested changes in {collateral}")
    if tables_changed:
        detail.append("table contents changed")
    unnumbered_b = [p.text for p in before.paragraphs if not p.section]
    unnumbered_a = [p.text for p in after.paragraphs if not p.section]
    if unnumbered_b != unnumbered_a:
        detail.append("unnumbered text (title/recitals) changed")
    return CheckResult("no_collateral_edits", not detail, "; ".join(detail))


def check_must_include(phrases, targets, after) -> CheckResult:
    text = " ".join(after.sections().get(s, "") for s in targets).lower()
    missing = [p for p in phrases if p.lower() not in text]
    return CheckResult("must_include", not missing, f"missing: {missing}" if missing else "")


def check_must_not_include(phrases, targets, after) -> CheckResult:
    text = " ".join(after.sections().get(s, "") for s in targets).lower()
    found = [p for p in phrases if p.lower() in text]
    return CheckResult("must_not_include", not found, f"found: {found}" if found else "")


def check_structure(before, after) -> CheckResult:
    """Formatting fidelity: same paragraph count, same styles, same numbering
    order, bold captions survive."""
    issues = []
    if len(before.paragraphs) != len(after.paragraphs):
        issues.append(f"paragraph count {len(before.paragraphs)} -> {len(after.paragraphs)}")
    else:
        for pb, pa in zip(before.paragraphs, after.paragraphs):
            if pb.style != pa.style:
                issues.append(f"style changed at {pb.section or pb.text[:30]!r}: {pb.style} -> {pa.style}")
            if pb.section != pa.section:
                issues.append(f"numbering changed: {pb.section} -> {pa.section}")
            if pb.bold_runs and not pa.bold_runs:
                issues.append(f"bold caption lost in {pb.section}")
    return CheckResult("formatting_fidelity", not issues, "; ".join(issues[:5]))


def check_citations(targets, after) -> CheckResult:
    """Every 'Section X.Y' cited in edited text must exist in the document."""
    ids = after.section_ids()
    text = " ".join(after.sections().get(s, "") for s in targets)
    bad = sorted({c for c in CITE_RE.findall(text) if c not in ids})
    return CheckResult("citation_integrity", not bad, f"cites nonexistent: {bad}" if bad else "")


def check_flagged(model_out, after, before) -> CheckResult:
    """For ambiguous / improper instructions the correct behavior is to make
    no edit and explain why."""
    made_edits = bool(model_out.get("edits")) or before.sections() != after.sections()
    flagged = bool(str(model_out.get("flag", "")).strip())
    ok = flagged and not made_edits
    detail = "" if ok else f"edits_made={made_edits}, flag_present={flagged}"
    return CheckResult("flagged_instead_of_editing", ok, detail)
