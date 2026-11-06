"""Compare a run against the baseline and enforce the release gate.

  python compare.py reports/baseline.json reports/run_xxx.json
  python compare.py reports/baseline.json reports/run_xxx.json --markdown reports/diff.md

Exit code 1 (blocks the release in CI) if:
  - overall pass rate drops more than --max-drop points below baseline, or
  - any severity=critical case falls below --critical-min pass rate.
"""
from __future__ import annotations

import argparse
import json
import sys


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("baseline")
    ap.add_argument("candidate")
    ap.add_argument("--max-drop", type=float, default=5.0, help="percentage points")
    ap.add_argument("--critical-min", type=float, default=0.8)
    ap.add_argument("--markdown", default=None)
    args = ap.parse_args()

    base = json.load(open(args.baseline))
    cand = json.load(open(args.candidate))

    lines = [
        f"## Eval comparison: `{base['model']}` (baseline) vs `{cand['model']}`",
        "",
        f"Overall: **{base['overall_pass_rate']:.0%} → {cand['overall_pass_rate']:.0%}**",
        "",
        "| case | severity | baseline | candidate | change |",
        "|---|---|---|---|---|",
    ]
    regressions, critical_fails = [], []
    for cid in sorted(set(base["cases"]) | set(cand["cases"])):
        b = base["cases"].get(cid, {}).get("pass_rate")
        c = cand["cases"].get(cid, {}).get("pass_rate")
        sev = (cand["cases"].get(cid) or base["cases"].get(cid))["severity"]
        delta = "" if b is None or c is None else f"{(c - b) * 100:+.0f} pts"
        flag = " ⚠️" if b is not None and c is not None and c < b else ""
        fmt = lambda x: "—" if x is None else f"{x:.0%}"
        lines.append(f"| {cid} | {sev} | {fmt(b)} | {fmt(c)} | {delta}{flag} |")
        if b is not None and c is not None and c < b:
            regressions.append(cid)
        if sev == "critical" and c is not None and c < args.critical_min:
            critical_fails.append(f"{cid} ({c:.0%})")

    drop = (base["overall_pass_rate"] - cand["overall_pass_rate"]) * 100
    gate_fail = drop > args.max_drop or critical_fails
    lines += ["", f"Regressed cases: {regressions or 'none'}"]
    if critical_fails:
        lines.append(f"Critical cases below {args.critical_min:.0%}: {critical_fails}")
    lines.append(f"\n**Release gate: {'FAIL ❌' if gate_fail else 'PASS ✅'}** "
                 f"(overall drop {drop:+.1f} pts, limit {args.max_drop})")

    md = "\n".join(lines)
    print(md)
    if args.markdown:
        open(args.markdown, "w").write(md)
    sys.exit(1 if gate_fail else 0)


if __name__ == "__main__":
    main()
