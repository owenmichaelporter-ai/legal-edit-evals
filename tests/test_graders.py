"""Unit tests for the deterministic graders. These run on every push (no API
key, no cost). If a grader is wrong, every eval result is wrong, so the
graders themselves get tested against known-good and known-bad edits."""
from pathlib import Path

import pytest

from graders.checks import run_checks
from graders.docx_tools import apply_edits, snapshot

ROOT = Path(__file__).parent.parent
SRC = str(ROOT / "fixtures" / "employment_agreement_A.docx")

CASE = {
    "id": "t", "target_sections": ["9.1"],
    "must_include": ["Delaware"], "must_not_include": ["Illinois"],
}
GOOD = "9.1 Governing Law. This Agreement shall be governed by the laws of the State of Delaware."


@pytest.fixture(scope="module", autouse=True)
def fixtures_exist():
    if not Path(SRC).exists():
        from fixtures.make_fixtures import build_agreement_a
        build_agreement_a(Path(SRC))


def grade(case, edits, tmp_path, flag=""):
    out = tmp_path / "out.docx"
    errors = apply_edits(SRC, edits, str(out))
    results = run_checks(case, snapshot(SRC), snapshot(str(out)), {"edits": edits, "flag": flag}, errors)
    return {r.name: r for r in results}


def test_good_edit_passes_everything(tmp_path):
    r = grade(CASE, [{"section": "9.1", "new_text": GOOD}], tmp_path)
    assert all(x.passed for x in r.values()), {k: v.detail for k, v in r.items() if not v.passed}


def test_bold_caption_survives_edit(tmp_path):
    r = grade(CASE, [{"section": "9.1", "new_text": GOOD}], tmp_path)
    assert r["formatting_fidelity"].passed


def test_collateral_edit_is_caught(tmp_path):
    edits = [{"section": "9.1", "new_text": GOOD},
             {"section": "9.2", "new_text": "9.2 Entire Agreement. Changed."}]
    r = grade(CASE, edits, tmp_path)
    assert not r["no_collateral_edits"].passed
    assert "9.2" in r["no_collateral_edits"].detail


def test_no_op_edit_is_caught(tmp_path):
    original = snapshot(SRC).sections()["9.1"]
    r = grade(CASE, [{"section": "9.1", "new_text": original}], tmp_path)
    assert not r["targets_changed"].passed


def test_missing_and_banned_phrases(tmp_path):
    bad = "9.1 Governing Law. This Agreement shall be governed by the laws of the State of Illinois."
    r = grade(CASE, [{"section": "9.1", "new_text": bad}], tmp_path)
    assert not r["must_include"].passed
    assert not r["must_not_include"].passed


def test_hallucinated_citation_is_caught(tmp_path):
    r = grade(CASE, [{"section": "9.1", "new_text": GOOD + " See Section 12.4."}], tmp_path)
    assert not r["citation_integrity"].passed
    assert "12.4" in r["citation_integrity"].detail


def test_valid_citation_passes(tmp_path):
    r = grade(CASE, [{"section": "9.1", "new_text": GOOD + " Subject to Section 8.1."}], tmp_path)
    assert r["citation_integrity"].passed


def test_edit_to_missing_section_is_reported(tmp_path):
    r = grade(CASE, [{"section": "10.1", "new_text": "10.1 Severance. ..."}], tmp_path)
    assert not r["edit_applied"].passed


def test_renumbering_is_caught(tmp_path):
    r = grade(CASE, [{"section": "9.1", "new_text": "9.3 Governing Law. Delaware law governs."}], tmp_path)
    assert not r["formatting_fidelity"].passed


def test_flag_case_passes_only_when_no_edits(tmp_path):
    case = {"id": "f", "expect_flag": True}
    ok = grade(case, [], tmp_path, flag="Instruction is ambiguous.")
    assert ok["flagged_instead_of_editing"].passed
    bad = grade(case, [{"section": "6.1", "new_text": "6.1 Notice. Changed."}], tmp_path, flag="")
    assert not bad["flagged_instead_of_editing"].passed
