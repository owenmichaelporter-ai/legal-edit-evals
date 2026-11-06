"""Turn a run report (JSON) into a single self-contained HTML page.

  python report.py reports/run_xxx.json                 -> reports/run_xxx.html
  python report.py reports/candidate.json --baseline reports/baseline.json

Open the HTML in any browser. Cases are sorted worst-first; click a case to
see every trial, which checks failed, the judge's reasoning, and a word-level
before/after diff of each section the model touched.
"""
from __future__ import annotations

import argparse
import difflib
import html
import json
import re
from pathlib import Path

SEV_ORDER = {"critical": 0, "major": 1, "minor": 2}


def word_diff(before: str, after: str) -> str:
    a, b = re.findall(r"\S+|\s+", before), re.findall(r"\S+|\s+", after)
    out = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if op == "equal":
            out.append(html.escape("".join(a[i1:i2])))
        if op in ("delete", "replace"):
            out.append(f"<del>{html.escape(''.join(a[i1:i2]))}</del>")
        if op in ("insert", "replace"):
            out.append(f"<ins>{html.escape(''.join(b[j1:j2]))}</ins>")
    return "".join(out)


def rate_class(r: float) -> str:
    return "good" if r >= 0.9 else "warn" if r >= 0.6 else "bad"


def render_trial(i: int, t: dict) -> str:
    status = "PASS" if t["passed"] else "FAIL"
    failed = [c for c in t["checks"] if not c["passed"]]
    checks = "".join(
        f'<li class="{"ok" if c["passed"] else "fail"}">{"✓" if c["passed"] else "✗"} '
        f'<b>{c["name"]}</b>{(" — " + html.escape(c["detail"])) if c["detail"] else ""}</li>'
        for c in t["checks"])
    judge = ""
    if t.get("judge"):
        j = t["judge"]
        judge = (f'<div class="judge">Judge: correctness {j.get("correctness","–")}, scope {j.get("scope","–")}, '
                 f'drafting {j.get("drafting","–")} — <i>{html.escape(str(j.get("reason", j.get("error", ""))))}</i></div>')
    flag = t["model_output"].get("flag", "")
    flag_html = f'<div class="flag">Model flag: “{html.escape(flag)}”</div>' if flag else ""
    sections = "".join(
        f'<div class="sec"><div class="sec-h">§ {s}{" <span class=tag>target</span>" if v["target"] else " <span class=\"tag collateral\">not requested</span>"}'
        f'{" <span class=tag>unchanged</span>" if v["before"] == v["after"] else ""}</div>'
        f'<div class="diff">{word_diff(v["before"], v["after"]) if v["before"] != v["after"] else html.escape(v["before"])}</div></div>'
        for s, v in t.get("sections", {}).items())
    summary = ", ".join(c["name"] for c in failed) or "all checks passed"
    return (f'<details class="trial {status.lower()}"><summary><span class="badge {status.lower()}">{status}</span> '
            f'Trial {i} · {html.escape(summary)} · {t.get("latency_s", "?")}s</summary>'
            f'<ul class="checks">{checks}</ul>{judge}{flag_html}{sections}</details>')


def render(report: dict, baseline: dict | None) -> str:
    cases = sorted(report["cases"].items(),
                   key=lambda kv: (kv[1]["pass_rate"], SEV_ORDER.get(kv[1]["severity"], 9)))
    rows, details = [], []
    for cid, c in cases:
        base = baseline["cases"].get(cid, {}).get("pass_rate") if baseline else None
        delta = ""
        if base is not None:
            d = (c["pass_rate"] - base) * 100
            delta = f'<span class="{"bad" if d < 0 else "good" if d > 0 else ""}">{d:+.0f}</span>'
        modes = ", ".join(f"{k} ({v})" for k, v in sorted(c["failure_modes"].items(), key=lambda x: -x[1]))
        rows.append(
            f'<tr><td><a href="#{cid}">{cid}</a></td><td><span class="sev {c["severity"]}">{c["severity"]}</span></td>'
            f'<td>{c["category"]}</td><td class="{rate_class(c["pass_rate"])}">{c["passes"]}/{c["trials"]}</td>'
            f'{"<td>" + delta + "</td>" if baseline else ""}<td class="modes">{html.escape(modes)}</td></tr>')
        trials = "".join(render_trial(i + 1, t) for i, t in enumerate(c["trial_details"]))
        details.append(
            f'<section id="{cid}"><h3>{cid} <span class="sev {c["severity"]}">{c["severity"]}</span> '
            f'<span class="{rate_class(c["pass_rate"])}">{c["passes"]}/{c["trials"]} passed</span></h3>{trials}</section>')

    overall = report["overall_pass_rate"]
    base_line = ""
    if baseline:
        d = (overall - baseline["overall_pass_rate"]) * 100
        base_line = f' <span class="muted">vs baseline {baseline["overall_pass_rate"]:.0%} ({d:+.0f} pts, {html.escape(baseline["model"])})</span>'
    n_crit_fail = sum(1 for _, c in cases if c["severity"] == "critical" and c["pass_rate"] < 1)

    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<title>Eval report · {html.escape(report['model'])}</title>
<style>
body{{font:14px/1.5 -apple-system,Segoe UI,Helvetica,Arial,sans-serif;max-width:1100px;margin:32px auto;padding:0 20px;color:#1d1d1f}}
h1{{font-size:22px;margin:0}} h3{{font-size:15px;margin:28px 0 8px}} .muted{{color:#777;font-weight:normal}}
.kpis{{display:flex;gap:16px;margin:18px 0 24px}} .kpi{{border:1px solid #e3e3e3;border-radius:8px;padding:10px 16px}}
.kpi b{{display:block;font-size:22px}}
table{{border-collapse:collapse;width:100%}} th,td{{text-align:left;padding:6px 10px;border-bottom:1px solid #eee;vertical-align:top}}
th{{font-size:12px;text-transform:uppercase;color:#777}} td.modes{{color:#555;font-size:13px}}
a{{color:#0b57d0;text-decoration:none}}
.good{{color:#137333;font-weight:600}} .warn{{color:#b06000;font-weight:600}} .bad{{color:#c5221f;font-weight:600}}
.sev{{font-size:11px;padding:1px 7px;border-radius:10px;background:#eee}} .sev.critical{{background:#fce8e6;color:#c5221f}}
.sev.major{{background:#fef7e0;color:#b06000}}
details.trial{{border:1px solid #e3e3e3;border-radius:6px;margin:6px 0;padding:6px 10px}}
details.trial.fail{{border-left:4px solid #c5221f}} details.trial.pass{{border-left:4px solid #137333}}
summary{{cursor:pointer}} .badge{{font-size:11px;font-weight:700;padding:1px 6px;border-radius:4px;color:#fff}}
.badge.pass{{background:#137333}} .badge.fail{{background:#c5221f}}
ul.checks{{list-style:none;padding:0;margin:8px 0}} li.fail{{color:#c5221f}} li.ok{{color:#555}}
.sec{{margin:8px 0}} .sec-h{{font-weight:600;font-size:13px}} .tag{{font-size:11px;background:#e8f0fe;color:#0b57d0;padding:0 6px;border-radius:8px;font-weight:normal}}
.tag.collateral{{background:#fce8e6;color:#c5221f}}
.diff{{font-family:Georgia,serif;background:#fafafa;border:1px solid #eee;padding:8px 10px;border-radius:4px;white-space:pre-wrap}}
del{{background:#fce8e6;color:#a50e0e}} ins{{background:#e6f4ea;color:#0d652d;text-decoration:none}}
.judge,.flag{{font-size:13px;color:#444;margin:4px 0}}
</style></head><body>
<h1>Eval report · <code>{html.escape(report['model'])}</code></h1>
<div class="muted">{report['timestamp']} · judge: {html.escape(str(report.get('judge_model') or 'off'))}</div>
<div class="kpis">
 <div class="kpi">Overall pass rate<b class="{rate_class(overall)}">{overall:.0%}</b>{base_line}</div>
 <div class="kpi">Cases<b>{len(cases)}</b></div>
 <div class="kpi">Critical cases not at 100%<b class="{'bad' if n_crit_fail else 'good'}">{n_crit_fail}</b></div>
</div>
<table><tr><th>Case</th><th>Severity</th><th>Category</th><th>Passed</th>{"<th>Δ pts</th>" if baseline else ""}<th>Failure modes</th></tr>
{''.join(rows)}</table>
{''.join(details)}
</body></html>"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("run")
    ap.add_argument("--baseline", default=None)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    report = json.load(open(args.run))
    baseline = json.load(open(args.baseline)) if args.baseline else None
    out = Path(args.out) if args.out else Path(args.run).with_suffix(".html")
    out.write_text(render(report, baseline), encoding="utf-8")
    print("Wrote", out)


if __name__ == "__main__":
    main()
