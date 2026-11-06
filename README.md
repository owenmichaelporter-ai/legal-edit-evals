# legal-edit-evals

An evaluation harness for **AI-assisted contract editing**: an attorney gives a plain-English instruction ("make the non-solicit mutual"), an LLM edits a Word document, and this harness measures whether the edit was correct, stayed in scope, kept the document's formatting intact, and only cited sections that exist.

It treats the model as non-deterministic: every case runs N times and is scored as a **pass rate**. Results are compared against a baseline, and a **release gate** in CI blocks changes that cause regressions.

---

## Quick start

```bash
pip install -r requirements.txt
python fixtures/make_fixtures.py          # builds the sample agreement
pytest -q                                 # tests the graders themselves

# offline run, no API key needed (mock model)
python runner.py --model mock:good --trials 5

# real model
export ANTHROPIC_API_KEY=...
python runner.py --model claude-sonnet-5-5 --trials 5 --judge-model claude-haiku-5-5

# compare to baseline and apply the release gate
python compare.py reports/baseline.json reports/run_<...>.json

# visual report: open the .html in a browser
python report.py reports/run_<...>.json --baseline reports/baseline.json
```

### Reading results
- **Terminal table:** pass rate and top failure modes per case.
- **HTML report (`report.py`):** cases sorted worst-first. Click a trial to see which checks failed, the judge's reasoning, and a word-level diff of every section the model touched. Sections changed without being requested are tagged in red.
- **CI:** the nightly run posts the baseline comparison to the Actions job summary and uploads the JSON and HTML reports as a downloadable artifact.

To triage a run: check the gate → sort by severity → group by failure mode → read the actual outputs → decide whether it's a model bug, a bad case, or a grader that needs adjusting → write it up.

> `reports/baseline.json` ships as a **mock** baseline so the pipeline runs end to end. Replace it with a real-model run before relying on the gate:
> `python runner.py --model claude-sonnet-5-5 --trials 5 --out reports/baseline.json`

---

## Test strategy

### What is being tested
The system under test (`editor.py`) receives a contract and an instruction and returns paragraph-level edits, which are applied to the .docx. Quality has four parts:

| Dimension | Question | How it's measured |
|---|---|---|
| **Correctness** | Did it do what the attorney asked? | `must_include` / `must_not_include` + LLM judge |
| **Scope** | Did it change *only* what was asked? | `no_collateral_edits`, `targets_changed`, judge "scope" score |
| **Formatting fidelity** | Is the document still structurally intact? | `formatting_fidelity`: paragraph count, styles, numbering, bold captions, tables |
| **Citation integrity** | Does every cross-reference point to a real section? | `citation_integrity` |
| **Knowing when not to act** | Does it flag vague or impossible instructions instead of guessing? | `flagged_instead_of_editing` |

### Grading layers
1. **Deterministic checks** (`graders/checks.py`): cheap and exact; they run on every trial. A trial that fails any check fails outright.
2. **LLM-as-judge** (`graders/judge.py`): runs only on trials that pass layer 1. It scores correctness, scope, and drafting from 1 to 5 against the case rubric, and a trial passes only if every score is ≥ 4 (configurable).
3. **The graders are tested too** (`tests/`): each check is unit-tested against known-good and known-bad edits. A broken grader silently corrupts every result.

### Handling non-determinism
- Each case runs **N trials** (default 5; use 10+ for cases being investigated).
- Each case gets a **pass rate** plus a count of **failure modes** (which check failed, and how often). A case at 4/5 with "collateral edit to 7.3 (1)" says much more than "flaky."
- Compare runs by pass rate, not single outcomes. A one-trial difference at N=5 is noise, so look for consistent shifts across cases or categories.

### Case design
Cases live in `cases/*.yaml`. The categories are:

| Category | Purpose |
|---|---|
| `happy_path` | Clear, single-paragraph edits. These should be near 100%. |
| `scope_edit` | Substantive edits where over-editing is the main risk |
| `defined_terms` | The right fix is to edit a *definition*, not every place it's used |
| `cross_reference` | Edits that touch or could invent section references |
| `formatting` | Edits where captions, tables, and styles must survive |
| `adversarial` | Vague, self-contradicting, or impossible instructions. The correct behavior is to flag. |

Each case also has a severity:
- **critical:** wrong output could plausibly reach a client unnoticed (for example, a silently broken defined term, or an invented provision)
- **major:** wrong output is likely to be caught, but costs the attorney time and trust
- **minor:** style or polish

### Release gate (`compare.py`)
A candidate (new model, prompt, or code change) **fails** if:
- its overall pass rate drops more than **5 points** below baseline, or
- any **critical** case falls below an **80%** pass rate.

CI (`.github/workflows/ci.yml`):
- **Every push:** grader unit tests plus an offline smoke eval. These are free and take seconds.
- **Nightly or manual:** a full eval against the real model, compared to baseline. The run fails on a gate breach and posts the comparison table to the job summary.

### Bug reporting
Use `.github/ISSUE_TEMPLATE/bug_report.md`. For AI-quality bugs, always include the **failure rate over N runs**, the case id, the exact command to reproduce, and the before/after text.

### Measuring the judge
An LLM judge is itself a model that can be wrong. To calibrate it:
1. Hand-score 20–30 outputs yourself on the same rubric.
2. Report agreement (exact match and within ±1).
3. Where you and the judge disagree, tighten the rubric wording in the case, not the threshold.

---

## Known limitations / next steps
- Numbering is plain text in the fixture. Real agreements use Word auto-numbering (`w:numPr`), which needs its own fidelity check.
- Edits are paragraph-level replacements. A real add-in may insert tracked changes, which should be tested as tracked revisions.
- Only one fixture so far. Add agreements with tables inside clauses, nested sub-sections (7.2(a)(i)), and exhibits.
- Expand to 30–50 cases, weighted toward the categories where failures concentrate.

## Layout
```
cases/          YAML eval cases
fixtures/       sample .docx agreements (+ generator script)
graders/        docx tools, deterministic checks, LLM judge, model wrapper
editor.py       system under test (prompt + parsing)
runner.py       runs cases x N trials, writes reports/
compare.py      baseline diff + release gate
report.py       HTML results viewer
tests/          unit tests for the graders
.github/        CI workflow + bug report template
```
