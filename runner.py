"""Run every eval case N times against a model and save a results report.

Examples:
  python runner.py --model mock:good --trials 5
  python runner.py --model claude-sonnet-5-5 --trials 5 --judge-model claude-haiku-5-5
  python runner.py --model claude-sonnet-5-5 --only noncompete_mutual_01 --trials 10

Output: reports/run_<model>_<timestamp>.json  (+ a printed summary table)
"""
from __future__ import annotations

import argparse
import json
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml

from editor import edit
from graders.checks import run_checks
from graders.docx_tools import apply_edits, snapshot
from graders.judge import judge

ROOT = Path(__file__).parent


def load_cases(only: str | None) -> list[dict]:
    cases = []
    for f in sorted((ROOT / "cases").glob("*.yaml")):
        cases += yaml.safe_load(f.read_text())
    return [c for c in cases if not only or c["id"] == only]


def run_trial(case: dict, model: str, judge_model: str | None, judge_threshold: int) -> dict:
    src = str(ROOT / case["doc"])
    before = snapshot(src)
    lines = [p.text for p in before.paragraphs]

    t0 = time.time()
    out, raw = edit(lines, case, model)
    latency = round(time.time() - t0, 2)

    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
        apply_errors = apply_edits(src, out["edits"], tmp.name)
        after = snapshot(tmp.name)

    checks = run_checks(case, before, after, out, apply_errors)
    det_pass = all(c.passed for c in checks)

    judge_result = None
    if judge_model and det_pass and not case.get("expect_flag"):
        judge_result = judge(case, before.sections(), after.sections(), judge_model)

    passed = det_pass and (judge_result is None or judge_result["min_score"] >= judge_threshold)
    b, a = before.sections(), after.sections()
    shown = set(case.get("target_sections", [])) | {s for s in b if b[s] != a.get(s)}
    return {
        "passed": passed,
        "sections": {s: {"before": b.get(s, ""), "after": a.get(s, ""),
                         "target": s in case.get("target_sections", [])}
                     for s in sorted(shown, key=lambda x: [int(n) for n in x.split(".")])},
        "checks": [c.__dict__ for c in checks],
        "judge": judge_result,
        "model_output": out,
        "latency_s": latency,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="mock:good")
    ap.add_argument("--trials", type=int, default=5)
    ap.add_argument("--judge-model", default=None, help="omit to skip LLM-as-judge")
    ap.add_argument("--judge-threshold", type=int, default=4)
    ap.add_argument("--only", default=None, help="run a single case id")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    cases = load_cases(args.only)
    results = {}
    for case in cases:
        trials = [run_trial(case, args.model, args.judge_model, args.judge_threshold)
                  for _ in range(args.trials)]
        n_pass = sum(t["passed"] for t in trials)
        failures: dict[str, int] = {}
        for t in trials:
            for c in t["checks"]:
                if not c["passed"]:
                    failures[c["name"]] = failures.get(c["name"], 0) + 1
            if t["judge"] and t["judge"].get("min_score", 5) < args.judge_threshold:
                failures["judge_below_threshold"] = failures.get("judge_below_threshold", 0) + 1
        results[case["id"]] = {
            "category": case.get("category", ""),
            "severity": case.get("severity", "major"),
            "pass_rate": n_pass / args.trials,
            "passes": n_pass,
            "trials": args.trials,
            "failure_modes": failures,
            "trial_details": trials,
        }

    overall = sum(r["passes"] for r in results.values()) / max(1, sum(r["trials"] for r in results.values()))
    report = {
        "model": args.model,
        "judge_model": args.judge_model,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "overall_pass_rate": round(overall, 4),
        "cases": results,
    }

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = Path(args.out) if args.out else ROOT / "reports" / f"run_{args.model.replace(':', '-')}_{stamp}.json"
    out.write_text(json.dumps(report, indent=2))

    print(f"\nModel: {args.model}   Trials/case: {args.trials}   Overall pass rate: {overall:.0%}\n")
    print(f"{'case':<34}{'sev':<10}{'pass':>8}   top failure modes")
    for cid, r in results.items():
        modes = ", ".join(f"{k}({v})" for k, v in sorted(r["failure_modes"].items(), key=lambda x: -x[1]))
        print(f"{cid:<34}{r['severity']:<10}{r['passes']:>3}/{r['trials']:<4}   {modes}")
    print(f"\nSaved {out.relative_to(ROOT) if out.is_relative_to(ROOT) else out}")


if __name__ == "__main__":
    main()
