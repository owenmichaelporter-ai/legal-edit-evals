"""LLM-as-judge grader for qualities string checks can't capture
(legal correctness, scope, drafting quality).

Calibrate it: hand-score ~20 outputs yourself, then report how often the
judge agrees with you (see README, "Measuring the judge").
"""
from __future__ import annotations

import json

from .llm import complete

JUDGE_PROMPT = """You are reviewing an edit an AI made to a legal contract.

INSTRUCTION GIVEN TO THE AI:
{instruction}

ORIGINAL TEXT OF EDITED SECTION(S):
{before}

EDITED TEXT:
{after}

RUBRIC (what a correct edit must do):
{rubric}

Score each dimension 1-5 (5 = a careful employment lawyer would accept as-is):
- correctness: does the edit accomplish the instruction and satisfy the rubric?
- scope: does it change only what was asked, without adding unrequested terms?
- drafting: is it clear, consistent with the agreement's defined terms and style?

Reply with JSON only:
{{"correctness": n, "scope": n, "drafting": n, "reason": "<one sentence>"}}"""


def judge(case: dict, before_sections: dict, after_sections: dict, model: str) -> dict:
    targets = [str(s) for s in case.get("target_sections", [])]
    prompt = JUDGE_PROMPT.format(
        instruction=case["instruction"],
        before="\n".join(before_sections.get(s, "") for s in targets),
        after="\n".join(after_sections.get(s, "") for s in targets),
        rubric=case.get("rubric", "Accomplish the instruction precisely."),
    )
    raw = complete(prompt, model=model, max_tokens=300)
    try:
        scores = json.loads(raw[raw.index("{"): raw.rindex("}") + 1])
    except ValueError:
        return {"error": f"unparseable judge output: {raw[:200]}", "min_score": 0}
    scores["min_score"] = min(scores.get(k, 0) for k in ("correctness", "scope", "drafting"))
    return scores
