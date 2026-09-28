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
MAX_ROWS = 12          # per-rule <RULE>.md fragments
MAX_CELL = 80
DIGEST_MAX_CELL = 400  # digest.md shows every row, wider cells
RUN_META = ("generated", "files", "unlabelled")

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
    """Append (name, source) pairs for every attachment, steps included."""
    for a in node.get("attachments") or []:
        acc.append((a.get("name") or a.get("source") or "", a.get("source") or ""))
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


def case_of_full(full):
    """Case for an allure ``fullName`` (``pkg.mod#Class.test_x`` — no param id)."""
    tail = (full or "").split("#", 1)[-1]
    if "[" not in tail:
        tail = tail.rsplit(".", 1)[-1]
    return case_of(tail)


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
    pairs = []
    _walk_attachments(result, pairs)
    attachments = [n for n, _ in pairs]
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
        "attachment_files": {n: src for n, src in pairs},
        "steps": [s.get("name") or "" for s in result.get("steps") or []],
        "failure": failure,
        "test": full,
        "file": full.split("#", 1)[0],
    }
    return rule, record


def build_evidence(results, env=None, generated=None):
    rules = {}
    files = set()
    unlabelled = set()
    for r in results:
        full = r.get("fullName") or r.get("name") or ""
        files.add(full.split("#", 1)[0])
        got = record_of(r)
        if got is None:
            unlabelled.add(full)
            continue
        rule, rec = got
        rules.setdefault(rule, []).append(rec)
    for recs in rules.values():
        recs.sort(key=lambda r: (r["case"], r["test"]))
    run = dict(env or {})
    run["generated"] = generated or date.today().isoformat()
    run["files"] = sorted(files)            # modules the run covered (labelled or not)
    run["unlabelled"] = sorted(unlabelled)  # fullNames that ran without a story label
    return {"run": run, "rules": {k: rules[k] for k in sorted(rules)}}


# ---------------------------------------------------------------- markdown

def cell(value, max_cell=MAX_CELL):
    if value is None:
        return ""
    s = str(value).replace("\r", " ").replace("\n", " ").replace("|", "\\|")
    if len(s) > max_cell:
        s = s[:max_cell - 1] + "…"
    return s


def _empty(value):
    return value is None or value == ""


def param_columns(records):
    """Param names in first-seen order, minus columns whose every value is empty."""
    names = []
    for r in records:
        for k in r["params"]:
            if k not in names:
                names.append(k)
    return [k for k in names if not all(_empty(r["params"].get(k)) for r in records)]


def _attachments_cell(names):
    if len(names) <= 3:
        return ", ".join(names)
    return str(len(names))


def _footer(run, report_url=None):
    parts = [f"{k}={v}" for k, v in run.items() if k not in RUN_META]
    parts.append(str(run.get("generated", "")))
    footer = f"_run: {' · '.join(parts)}_"
    if report_url:
        footer = footer[:-1] + f" · report: {report_url}_"
    return footer


def table_lines(records, max_rows=MAX_ROWS, max_cell=MAX_CELL):
    """GFM table lines for some records (+ overflow line when ``max_rows`` elides)."""
    has_world = any(r.get("world") for r in records)
    has_failure = any(r["status"] not in ("passed", "skipped") for r in records)
    param_names = param_columns(records)
    cols = ["status", "case"] + (["world"] if has_world else []) + param_names + ["attachments"]
    if has_failure:
        cols.append("failure")
    lines = ["| " + " | ".join(cols) + " |", "|" + "|".join("---" for _ in cols) + "|"]
    shown = records if max_rows is None else records[:max_rows]
    for r in shown:
        row = [STATUS_ICON.get(r["status"], r["status"]), cell(r["case"], max_cell)]
        if has_world:
            row.append(cell(r.get("world"), max_cell))
        row += [cell(r["params"].get(k), max_cell) for k in param_names]
        row.append(cell(_attachments_cell(r["attachments"]), max_cell))
        if has_failure:
            row.append(cell(r.get("failure"), max_cell))
        lines.append("| " + " | ".join(row) + " |")
    rest = records[len(shown):]
    if rest:
        passed = sum(1 for r in rest if r["status"] == "passed")
        failed = sum(1 for r in rest if r["status"] not in ("passed", "skipped"))
        lines.append("")
        lines.append(f"_… {len(rest)} more rows ({passed} passed, {failed} failed)_")
    return lines


def render_table(records, run, report_url=None, max_rows=MAX_ROWS, max_cell=MAX_CELL):
    """GFM table lines for one rule's records (+ overflow line + run footer)."""
    return table_lines(records, max_rows, max_cell) + ["", _footer(run, report_url)]


def render_digest_tables(records, run, report_url=None):
    """Digest view of one rule: every row, wide cells, one table per test module."""
    files = []
    for r in records:
        if r.get("file") not in files:
            files.append(r.get("file"))
    lines = []
    if len(files) <= 1:
        lines += table_lines(records, None, DIGEST_MAX_CELL)
    else:
        for f in files:
            lines += [f"### {f}", ""]
            lines += table_lines([r for r in records if r.get("file") == f], None, DIGEST_MAX_CELL)
            lines.append("")
    return lines + ["", _footer(run, report_url)]


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


REMOVED_CLASSES = (
    ("out-of-scope", "out-of-scope (file not run)"),
    ("unlabelled", "unlabelled (ran, no rule)"),
    ("gone", "gone (not in run)"),
)


def classify_removed(rule, evidence, baseline, removed):
    """Split removed cases: baseline file not in run.files → out-of-scope; a result with
    that test name (or case) ran at HEAD without a story → unlabelled; else gone."""
    run = evidence.get("run", {})
    files = run.get("files")
    unlabelled = run.get("unlabelled") or []
    unlabelled_cases = {case_of_full(u) for u in unlabelled}
    old = {}
    for r in (baseline or {}).get("rules", {}).get(rule, []):
        old.setdefault(r.get("case"), []).append(r)
    out = {key: [] for key, _ in REMOVED_CLASSES}
    for c in removed:
        recs = old.get(c, [])
        if files is not None and recs and all(r.get("file") and r["file"] not in files for r in recs):
            out["out-of-scope"].append(c)
        elif c in unlabelled_cases or any(r.get("test") in unlabelled for r in recs):
            out["unlabelled"].append(c)
        else:
            out["gone"].append(c)
    return out


def _bare(record):
    return not record.get("params") and not record.get("attachments")


def findings(rule, evidence, baseline=None):
    recs = evidence["rules"].get(rule, [])
    out = []
    if not recs:
        out.append(f"- NO_EVIDENCE {rule} —: rule listed but no labelled test result carries it")
    old_bare = set()
    if baseline is not None:
        for r in baseline.get("rules", {}).get(rule, []):
            if "params" in r and "attachments" in r and _bare(r):
                old_bare.add(r.get("case"))
    bare_new, bare_old, failed = [], [], []
    for r in recs:
        if _bare(r):
            tag = "BARE_ROW (pre-existing)" if r["case"] in old_bare else "BARE_ROW"
            line = (f"- {tag} {rule} {r['case']}: no parameters and no attachments — "
                    f"the row proves only that `{r['test']}` ran")
            (bare_old if r["case"] in old_bare else bare_new).append(line)
        if r["status"] not in ("passed", "skipped"):
            why = r.get("failure") or "no failure message"
            failed.append(f"- FAILED {rule} {r['case']}: status={r['status']} — {cell(why)}")
    out += bare_new + bare_old + failed
    if baseline is not None:
        _, removed, _ = delta(rule, evidence, baseline)
        classes = classify_removed(rule, evidence, baseline, removed)
        for c in classes["unlabelled"]:
            out.append(f"- UNLABELLED {rule} {c}: ran at HEAD without a rule label")
        for c in classes["gone"]:
            out.append(f"- VANISHED {rule} {c}: present in baseline, absent in this run")
    return out


def render_digest(rules, evidence, baseline=None, report_url=None):
    lines = []
    for rule in rules:
        lines.append(f"## {rule}")
        lines.append("")
        recs = evidence["rules"].get(rule, [])
        if recs:
            lines += render_digest_tables(recs, evidence["run"], report_url)
        else:
            lines.append("_no evidence rows for this rule_")
        lines.append("")
        if baseline is not None:
            added, removed, flips = delta(rule, evidence, baseline)
            lines.append("**Δ vs baseline:**")
            lines.append("")
            lines.append(f"- added: {', '.join(added) if added else 'none'}")
            lines.append(f"- removed: {', '.join(removed) if removed else 'none'}")
            if removed:
                classes = classify_removed(rule, evidence, baseline, removed)
                for key, label in REMOVED_CLASSES:
                    lines.append(f"  - {label}: {', '.join(classes[key]) if classes[key] else 'none'}")
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
