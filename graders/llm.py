"""Thin LLM wrapper. Provider is picked by the model name:

  mock:*        offline fake model (no API key; for smoke tests and CI)
  claude-*      Anthropic API (needs ANTHROPIC_API_KEY)
  gpt-*         OpenAI API (needs OPENAI_API_KEY)
"""
from __future__ import annotations

import json
import os
import random
import re


def complete(prompt: str, model: str, max_tokens: int = 1500, temperature: float = 1.0) -> str:
    if model.startswith("mock"):
        return _mock(prompt, model)
    if model.startswith("claude"):
        import anthropic
        client = anthropic.Anthropic()
        msg = client.messages.create(
            model=model, max_tokens=max_tokens, temperature=temperature,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text
    if model.startswith("gpt"):
        from openai import OpenAI
        resp = OpenAI().chat.completions.create(
            model=model, temperature=temperature,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.choices[0].message.content
    raise ValueError(f"unknown model provider for {model!r}")


# --- mock model ------------------------------------------------------------
# Behaves like a sloppy-but-plausible model so the whole pipeline (graders,
# pass rates, regression diff, CI gate) can be exercised without an API key.
# mock:good -> usually correct;  mock:bad -> frequently makes classic mistakes.

def _mock(prompt: str, model: str) -> str:
    if "Score each dimension" in prompt:  # acting as judge
        return json.dumps({"correctness": 4, "scope": 4, "drafting": 4, "reason": "mock judge"})

    error_rate = 0.15 if model == "mock:good" else 0.5
    m = re.search(r"TARGET SECTION HINT: (\S+)", prompt)
    sec = m.group(1) if m else None
    if sec is None:  # ambiguous instruction case
        if random.random() > error_rate:
            return json.dumps({"edits": [], "flag": "Instruction is ambiguous; please clarify."})
        return json.dumps({"edits": [{"section": "9.1", "new_text": "9.1 Governing Law. Changed."}]})

    orig = re.search(rf"^{re.escape(sec)} .*$", prompt, re.M).group(0)
    adds = re.search(r"MOCK_PHRASES: (.*)$", prompt, re.M)
    phrase = adds.group(1).strip() if adds else ""
    banned = re.search(r"MOCK_BANNED: (.*)$", prompt, re.M)
    banned = [b for b in (banned.group(1).split("|") if banned else []) if b]
    new = orig
    for b in banned:  # swap the old term for the new one, like a real edit would
        new = re.sub(re.escape(b), phrase, new, flags=re.I)
    if phrase and phrase.lower() not in new.lower():
        new = f"{new.rstrip('.')}, provided that {phrase}."
    roll = random.random()
    if roll < error_rate / 3:
        new = new + " See Section 12.4."            # hallucinated cross-reference
    elif roll < 2 * error_rate / 3:
        return json.dumps({"edits": [{"section": sec, "new_text": new},
                                     {"section": "7.3", "new_text": "7.3 Reasonableness. Edited too."}]})
    elif roll < error_rate:
        new = orig                                    # no-op edit
    return json.dumps({"edits": [{"section": sec, "new_text": new}]})
