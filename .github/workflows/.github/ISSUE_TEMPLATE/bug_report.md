---
name: Bug report
about: Functional or AI-quality defect found by an eval or manual testing
labels: bug
---

**Summary** (one line: what is wrong, where)
<!-- e.g. "Making 7.2 mutual also rewrites 7.3 in ~40% of runs" -->

**Severity:** critical / major / minor
**Type:** functional · formatting fidelity · AI accuracy · citation · scope · UX
**Eval case id:** <!-- e.g. nonsolicit_mutual_01, or "manual" -->
**Model / prompt version:**

**Steps to reproduce**
1. Open `fixtures/...docx`
2. Instruction: "..."
3. `python runner.py --model ... --only <case_id> --trials 10`

**Expected**

**Actual**

**Frequency:** x / N runs  <!-- non-deterministic output: always report a rate -->

**Evidence**
<!-- failing check names + details, before/after text of the section, link to report JSON -->

**Impact on the user**
<!-- what an attorney would experience; would they notice before sending? -->

**Suspected pattern / notes**
