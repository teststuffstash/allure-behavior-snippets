"""Model-friendly evidence from RAW allure results (``*-result.json``).

Reads the files pytest's allure plugin writes (not the generated report) and emits,
per story label (= rule ID), a GFM table whose columns are the tests' parameter
names, plus one ``evidence.json`` a reviewer can grep with jq.

    python3 -m allure_behavior_snippets.evidence --results DIR [--results DIR2 ...] \
        --out OUTDIR [--rules A,B,C] [--baseline evidence.json] [--report-url URL]

stdlib only.
"""
import argparse
import json
import re
from datetime import date
from pathlib import Path

STATUS_ICON = {"passed": "✓", "failed": "❌", "broken": "❌", "skipped": "⚠"}
STATUS_RANK = {"failed": 3, "broken": 3, "unknown": 2, "skipped": 1, "passed": 0}
MAX_ROWS = 12
MAX_CELL = 80

_PARAM_ID = re.compile(r"^[^\[]+\[(.*)\]$", re.S)
_WORLD = re.compile(r"world:\s*([^\]\s(]+)")


# ---------------------------------------------------------------- loading

def load_results(results_dirs):
    """Yield raw result dicts from every ``*-result.json`` under each dir."""
    for d in results_dirs:
        for path in sorted(Path(d).glob("*-result.json")):
            try:
                yield json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue


def load_environment(results_dirs):
    """Merge ``environment.properties`` (key=value lines) from each results dir."""
    env = {}
    for d in results_dirs:
        p = Path(d) / "environment.properties"
        if not p.is_file():
            continue
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env


# ---------------------------------------------------------------- records

def _labels(result):
    out = {}
    for lab in result.get("labels") or []:
        out.setdefault(lab.get("name"), lab.get("value"))
    return out


def _walk_attachments(node, acc):
    for a in node.get("attachments") or []:
        acc.append(a.get("name") or a.get("source") or "")
    for s in node.get("steps") or []:
        _walk_attachments(s, acc)


def _unescape(s):
    # pytest escapes non-ASCII in param ids as literal \uXXXX; undo that
    return re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), s)


def case_of(name):
    m = _PARAM_ID.match(name or "")
    if m:
        return _unescape(m.group(1))
    return re.sub(r"^test_", "", name or "")


def world_of(result, labels, case, attachments):
    if labels.get("world"):
        return labels["world"]
    for text in (case, result.get("name") or "", *attachments):
        m = _WORLD.search(text)
        if m:
            return m.group(1)
    return None


def record_of(result):
    """(rule, record) for a labelled result, or None when it carries no story."""
    labels = _labels(result)
    rule = labels.get("story")
    if not rule:
        return None
    name = result.get("name") or ""
    full = result.get("fullName") or name
    case = case_of(name)
    attachments = []
    _walk_attachments(result, attachments)
    params = {}
    for p in result.get("parameters") or []:
        if p.get("name") is not None:
            params[str(p["name"])] = p.get("value")
    msg = (result.get("statusDetails") or {}).get("message")
    failure = None
    if msg:
        first = msg.strip().splitlines()
        failure = first[0].strip() if first else None
    record = {
        "case": case,
        "world": world_of(result, labels, case, attachments),
        "status": result.get("status") or "unknown",
        "params": params,
        "attachments": attachments,
        "steps": [s.get("name") or "" for s in result.get("steps") or []],
        "failure": failure,
        "test": full,
        "file": full.split("#", 1)[0],
    }
    return rule, record


def build_evidence(results, env=None, generated=None):
    rules = {}
    for r in results:
        got = record_of(r)
        if got is None:
            continue
        rule, rec = got
        rules.setdefault(rule, []).append(rec)
    for recs in rules.values():
        recs.sort(key=lambda r: (r["case"], r["test"]))
    run = dict(env or {})
    run["generated"] = generated or date.today().isoformat()
    return {"run": run, "rules": {k: rules[k] for k in sorted(rules)}}


# ---------------------------------------------------------------- markdown

def cell(value):
    if value is None:
        return ""
    s = str(value).replace("\r", " ").replace("\n", " ").replace("|", "\\|")
    if len(s) > MAX_CELL:
        s = s[:MAX_CELL - 1] + "…"
    return s


def _attachments_cell(names):
    if len(names) <= 3:
        return ", ".join(names)
    return str(len(names))


def _footer(run):
    parts = [f"{k}={v}" for k, v in run.items() if k != "generated"]
    parts.append(str(run.get("generated", "")))
    return f"_run: {' · '.join(parts)}_"


def render_table(records, run, report_url=None):
    """GFM table lines for one rule's records (+ overflow line + run footer)."""
    has_world = any(r.get("world") for r in records)
    has_failure = any(r["status"] not in ("passed", "skipped") for r in records)
    param_names = []
    for r in records:
        for k in r["params"]:
            if k not in param_names:
                param_names.append(k)
    cols = ["status", "case"] + (["world"] if has_world else []) + param_names + ["attachments"]
    if has_failure:
        cols.append("failure")
    lines = ["| " + " | ".join(cols) + " |", "|" + "|".join("---" for _ in cols) + "|"]
    shown = records[:MAX_ROWS]
    for r in shown:
        row = [STATUS_ICON.get(r["status"], r["status"]), cell(r["case"])]
        if has_world:
            row.append(cell(r.get("world")))
        row += [cell(r["params"].get(k)) for k in param_names]
        row.append(cell(_attachments_cell(r["attachments"])))
        if has_failure:
            row.append(cell(r.get("failure")))
        lines.append("| " + " | ".join(row) + " |")
    rest = records[MAX_ROWS:]
    if rest:
        passed = sum(1 for r in rest if r["status"] == "passed")
        failed = sum(1 for r in rest if r["status"] not in ("passed", "skipped"))
        lines.append("")
        lines.append(f"_… {len(rest)} more rows ({passed} passed, {failed} failed)_")
    lines.append("")
    footer = _footer(run)
    if report_url:
        footer = footer[:-1] + f" · report: {report_url}_"
    lines.append(footer)
    return lines


# ---------------------------------------------------------------- digest

def _case_status(records):
    """case -> worst status among records sharing that case."""
    out = {}
    for r in records:
        cur = out.get(r["case"])
        if cur is None or STATUS_RANK.get(r["status"], 2) > STATUS_RANK.get(cur, 2):
            out[r["case"]] = r["status"]
    return out


def delta(rule, evidence, baseline):
    now = _case_status(evidence["rules"].get(rule, []))
    old = _case_status((baseline or {}).get("rules", {}).get(rule, []))
    added = sorted(c for c in now if c not in old)
    removed = sorted(c for c in old if c not in now)
    flips = [(c, old[c], now[c]) for c in sorted(now) if c in old and old[c] != now[c]]
    return added, removed, flips


def findings(rule, evidence, baseline=None):
    out = []
    recs = evidence["rules"].get(rule, [])
    if not recs:
        out.append(f"- NO_EVIDENCE {rule} —: rule listed but no labelled test result carries it")
    for r in recs:
        if not r["params"] and not r["attachments"]:
            out.append(f"- BARE_ROW {rule} {r['case']}: no parameters and no attachments — "
                       f"the row proves only that `{r['test']}` ran")
        if r["status"] not in ("passed", "skipped"):
            why = r.get("failure") or "no failure message"
            out.append(f"- FAILED {rule} {r['case']}: status={r['status']} — {cell(why)}")
    if baseline is not None:
        _, removed, _ = delta(rule, evidence, baseline)
        for c in removed:
            out.append(f"- VANISHED {rule} {c}: present in baseline, absent in this run")
    return out


def render_digest(rules, evidence, baseline=None, report_url=None):
    lines = []
    for rule in rules:
        lines.append(f"## {rule}")
        lines.append("")
        recs = evidence["rules"].get(rule, [])
        if recs:
            lines += render_table(recs, evidence["run"], report_url)
        else:
            lines.append("_no evidence rows for this rule_")
        lines.append("")
        if baseline is not None:
            added, removed, flips = delta(rule, evidence, baseline)
            lines.append("**Δ vs baseline:**")
            lines.append("")
            lines.append(f"- added: {', '.join(added) if added else 'none'}")
            lines.append(f"- removed: {', '.join(removed) if removed else 'none'}")
            if flips:
                lines.append("- flips:")
                lines += [f"  - {c}: {o} → {n}" for c, o, n in flips]
            else:
                lines.append("- flips: none")
            lines.append("")
        lines.append("**Findings:**")
        lines.append("")
        lines += findings(rule, evidence, baseline) or ["- none"]
        lines.append("")
    return lines


# ---------------------------------------------------------------- driver

def write_outputs(evidence, out_dir, rules=None, baseline=None, report_url=None):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "evidence.json").write_text(
        json.dumps(evidence, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    written = ["evidence.json"]
    for rule, recs in evidence["rules"].items():
        (out / f"{rule}.md").write_text(
            "\n".join(render_table(recs, evidence["run"], report_url)) + "\n", encoding="utf-8")
        written.append(f"{rule}.md")
    if rules:
        (out / "digest.md").write_text(
            "\n".join(render_digest(rules, evidence, baseline, report_url)) + "\n", encoding="utf-8")
        written.append("digest.md")
    return written


def cli(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--results", action="append", required=True, metavar="DIR",
                    help="raw allure results dir (repeatable)")
    ap.add_argument("--out", required=True, metavar="OUTDIR")
    ap.add_argument("--rules", default=None, help="comma-separated rule IDs for digest.md")
    ap.add_argument("--baseline", default=None, metavar="evidence.json",
                    help="previous evidence.json for the digest delta")
    ap.add_argument("--report-url", default=None, help="Allure report URL (footer only)")
    args = ap.parse_args(argv)
    env = load_environment(args.results)
    evidence = build_evidence(load_results(args.results), env)
    baseline = None
    if args.baseline:
        baseline = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
    rules = [r.strip() for r in args.rules.split(",") if r.strip()] if args.rules else None
    written = write_outputs(evidence, args.out, rules, baseline, args.report_url)
    n = sum(len(v) for v in evidence["rules"].values())
    print(f"{n} records across {len(evidence['rules'])} rules → {args.out} ({len(written)} files)")


if __name__ == "__main__":
    cli()
