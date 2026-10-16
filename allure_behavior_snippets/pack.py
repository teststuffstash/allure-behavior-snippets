"""The context pack for the specs reviewer: one deterministic inputs dir per PR round.

    evidence-pack BASE HEAD RESULTS --out DIR [--repo .] [--specs-root specs]
        [--tests-root DIR ...] [--code-root DIR ...] [--id-regex RE]
        [--baseline evidence.json [--baseline-commit SHA] [--baseline-scope TEXT]]
        [--prior-review FILE] [--issue-intent FILE] [--pr-body FILE]
        [--report-url URL] [--no-specs-tree]

oracle-fleet ``scripts/evidence-review.sh``'s contract in Python, plus the round inputs of
homelab ADR-156. A confined reviewer reads ONLY this dir: the briefs and rules it judges by are
copied in (``process/``) at the version this tool was pinned at, so the process a review ran
under is the process in its inputs.

``process-path`` prints the installed ``process/`` dir (the briefs, RULES.md, CONVENTIONS.md).
stdlib only.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

from . import __version__
from . import evidence as ev
from . import touched_rules as tr

PROCESS_DIR = Path(__file__).resolve().parent / "process"
TOP_LEVEL_SUFFIXES = (".md", ".json", ".txt")
PACK_DIRS = ("process", "tree", "attachments")

NONE_TEXT = {
    "prior-review.md": "previous review: none (round 1)\n",
    "issue-intent.md": ("issue intent: not provided (this PR closes no issue, or the launcher did "
                        "not fetch it) — check 1 grounds rows in the page prose, a use case or "
                        "`Spec changes:`\n"),
    "pr-body.md": "pr body: not provided — `Spec changes:` cannot be read from this pack\n",
}


class PackError(Exception):
    pass


def process_dir() -> Path:
    return PROCESS_DIR


def _read_optional(path: str | None, what: str) -> str | None:
    if not path:
        return None
    p = Path(path)
    if not p.is_file():
        raise PackError(f"{what} not found: {path}")
    return p.read_text(encoding="utf-8")


def _prepare_out(out: Path) -> None:
    """Clear a previous pack; refuse a non-empty dir that is not one (never wipe a checkout)."""
    if out.exists():
        if not out.is_dir():
            raise PackError(f"--out is not a directory: {out}")
        if any(out.iterdir()) and not (out / "manifest.json").is_file():
            raise PackError(f"--out {out} is non-empty and holds no manifest.json — not a previous "
                            "pack; refusing to clear it")
        for child in out.iterdir():
            if child.is_dir() and child.name in PACK_DIRS:
                shutil.rmtree(child)
            elif child.is_file() and child.suffix in TOP_LEVEL_SUFFIXES:
                child.unlink()
    out.mkdir(parents=True, exist_ok=True)


def _show_bytes(git: tr.Git, rev: str, path: str) -> bytes | None:
    proc = subprocess.run(["git", "-C", git.repo, "show", f"{rev}:{path}"], capture_output=True)
    return proc.stdout if proc.returncode == 0 else None


def spec_sections(rows: list[dict], head_specs: dict[str, str], layout: tr.Layout,
                  base: str, head: str, spec_diff: str) -> str:
    out: list[str] = []
    ids = tr.unique_ids(rows)
    if not ids:
        out += [f"<!-- no touched rules between {base} and {head} -->", ""]
    by_rule = {}
    for r in rows:
        by_rule.setdefault(r["rule"], r)
    for rid in ids:
        row = by_rule[rid]
        srcs = ", ".join(row["sources"])
        if row["path"] is None:
            out += [f"<!-- {rid} (sources: {srcs}) -->",
                    f"_orphan: no `{rid}` heading under `{layout.specs_root}/` at {head[:12]}_", ""]
            continue
        out.append(f"<!-- {row['path']} § {rid} (sources: {srcs}) -->")
        body = tr.section_text(head_specs.get(row["path"], ""), rid, layout)
        out.append(body if body is not None else
                   f"_section not found at {head[:12]} (heading removed? see the spec diff)_")
        out.append("")
    out += ["# Spec diff", "", "```diff", spec_diff.rstrip("\n"), "```", ""]
    return "\n".join(out)


def stamp_of(run: dict, head: str) -> dict:
    """What the run says it proved: the commit it ran at (``git.commit``) and the artifact
    (``image.digest``). ``matches_head`` is None when the run names no commit."""
    commit = run.get("git.commit") or None
    matches = None
    if commit:
        c = commit.strip().lower()
        matches = len(c) >= 7 and (head.lower().startswith(c) or c.startswith(head.lower()))
    return {"git_commit": commit, "matches_head": matches, "image_digest": run.get("image.digest") or None}


def _stamp_line(stamp: dict, head: str) -> str:
    if stamp["git_commit"] is None:
        s = (f"**Stamp:** the run names no `git.commit` — it cannot be tied to head "
             f"{head[:12]}; every row is unproven at this head (E-STALE).")
    elif stamp["matches_head"]:
        s = f"**Stamp:** run at `git.commit={stamp['git_commit'][:12]}` = this head."
    else:
        s = (f"**Stamp:** run at `git.commit={stamp['git_commit'][:12]}` ≠ head {head[:12]} — "
             f"stale; every row is unproven at this head (E-STALE).")
    if stamp["image_digest"]:
        s += f" Artifact: `image.digest={stamp['image_digest']}`."
    else:
        s += " No `image.digest`: this is PR-head evidence, not built-artifact evidence."
    return s


def _baseline_line(baseline_file: str | None, commit: str | None, scope: str) -> str:
    if baseline_file is None:
        return ("**Baseline:** none — no Δ, and VANISHED cannot fire (a missing baseline is not a "
                "lost proof).")
    at = f" at `{commit[:12]}`" if commit else " (commit not stated)"
    return (f"**Baseline:** `baseline-evidence.json`{at}. Scope: {scope}. A removed case is "
            f"VANISHED only inside this scope.")


def _filter_rules(evidence: dict, ids: list[str]) -> dict:
    return {**evidence, "rules": {k: v for k, v in evidence.get("rules", {}).items() if k in ids}}


def build(args: argparse.Namespace) -> dict:
    layout = tr.layout_of(args)
    git = tr.Git(args.repo)
    out = Path(args.out)
    results = Path(args.results)
    if not results.is_dir():
        raise PackError(f"allure results dir not found: {args.results}")
    if (args.baseline_commit or args.baseline_scope) and not args.baseline:
        raise PackError("--baseline-commit / --baseline-scope need --baseline")
    prior = _read_optional(args.prior_review, "prior review")
    intent = _read_optional(args.issue_intent, "issue intent")
    body = _read_optional(args.pr_body, "pr body")
    baseline_text = _read_optional(args.baseline, "baseline")
    try:
        base = git.rev(args.base)
        head = git.rev(args.head)
    except subprocess.CalledProcessError as exc:
        raise PackError(f"cannot resolve base/head: {(exc.stderr or '').strip()}") from exc
    _prepare_out(out)
    files: list[str] = []

    def write(name: str, text: str) -> None:
        (out / name).write_text(text if text.endswith("\n") else text + "\n", encoding="utf-8")
        files.append(name)

    # 1. touched rules
    rows = tr.touched_rules(git, base, head, layout)
    files += tr.write_outputs(rows, out)
    ids = tr.unique_ids(rows)

    # 2. spec sections at <head> + the spec diff
    head_specs = tr.head_spec_pages(git, head, layout)
    diff_args = ["diff", f"{base}...{head}"] + (["--", layout.specs_root] if layout.specs_root != "." else [])
    write("spec-sections.md", spec_sections(rows, head_specs, layout, base, head, git(*diff_args)))

    # 3. evidence for the touched rules (the digest reads the WHOLE run, so a case that moved
    #    to another rule is classified relabelled, not vanished; the files carry touched rules)
    baseline = json.loads(baseline_text) if baseline_text is not None else None
    scope = args.baseline_scope or ("the test modules the baseline run covered (its "
                                    "`run.files`); a case whose module did not run is out-of-scope")
    records = records_total = n_findings = 0
    stamp = {"git_commit": None, "matches_head": None, "image_digest": None}
    n_attach = 0
    if not ids:
        write("evidence.json", json.dumps({"run": {}, "rules": {}}, indent=2))
        write("digest.md", f"# Evidence digest\n\n_No touched rules between {base[:12]} and "
                           f"{head[:12]} — nothing to review._")
    else:
        dirs = [str(results)]
        evidence = ev.build_evidence(ev.load_results(dirs), ev.load_environment(dirs), results_dirs=dirs)
        stamp = stamp_of(evidence["run"], head)
        spec = {}
        for path in sorted({r["path"] for r in rows if r["path"]}):
            on_page = [r["rule"] for r in rows if r["path"] == path]
            text = head_specs.get(path)
            if text is None:
                continue
            for rid in on_page:
                tables = ev.spec_tables(text, rid)
                if tables:
                    spec[rid] = tables
        records_total = sum(len(v) for v in evidence["rules"].values())
        scoped = _filter_rules(evidence, ids)
        records = sum(len(v) for v in scoped["rules"].values())
        write("evidence.json", json.dumps(scoped, indent=2, sort_keys=True, ensure_ascii=False))
        if baseline is not None:
            write("baseline-evidence.json",
                  json.dumps(_filter_rules(baseline, ids), indent=2, sort_keys=True, ensure_ascii=False))
        for rid in ids:
            n_findings += len(ev.findings(rid, evidence, baseline))
            if spec.get(rid):
                n_findings += len(ev.spec_findings(rid, spec[rid], evidence["rules"].get(rid, [])))
        head_lines = ["# Evidence digest", "",
                      f"Rules: {', '.join(ids)}", "",
                      _stamp_line(stamp, head), "",
                      _baseline_line(args.baseline, args.baseline_commit, scope), ""]
        digest = ev.render_digest(ids, evidence, baseline, args.report_url, spec)
        write("digest.md", "\n".join(head_lines + digest))
        for rid in ids:
            recs = evidence["rules"].get(rid, [])
            if ev.rule_joins(spec.get(rid), recs) or (spec.get(rid) and not recs):
                lines = ev.render_joined(spec[rid], recs, evidence["run"], args.report_url)
            elif recs:
                lines = ev.render_table(recs, evidence["run"], args.report_url)
            else:
                lines = [f"_no evidence rows for {rid}_"]
            write(f"{rid}.md", "\n".join(lines))
        # attachments of the touched rules' records, so the pack is the reviewer's whole world
        for recs in scoped["rules"].values():
            for src in {s for r in recs for s in (r.get("attachment_files") or {}).values() if s}:
                p = results / src
                if p.is_file() and not (out / "attachments" / src).exists():
                    (out / "attachments").mkdir(exist_ok=True)
                    shutil.copyfile(p, out / "attachments" / src)
                    n_attach += 1

    # 4. round inputs: the previous review, the closing issue's acceptance text, the PR body
    write("prior-review.md", prior if prior is not None else NONE_TEXT["prior-review.md"])
    write("issue-intent.md", intent if intent is not None else NONE_TEXT["issue-intent.md"])
    write("pr-body.md", body if body is not None else NONE_TEXT["pr-body.md"])

    # 5. the specs tree at <head> — neighbouring pages, glossary, schemas, worlds
    n_tree = 0
    if not args.no_specs_tree:
        listing = git("ls-tree", "-r", "--name-only", head, *(["--", layout.specs_root]
                                                               if layout.specs_root != "." else []))
        for path in filter(None, listing.split("\n")):
            data = _show_bytes(git, head, path)
            if data is None:
                continue
            dest = out / "tree" / path
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
            n_tree += 1

    # 6. the pinned process: the briefs and the rules they cite
    shutil.copytree(PROCESS_DIR, out / "process",
                    ignore=shutil.ignore_patterns("__pycache__", "*.py", "*.pyc"))

    manifest = {
        "tool": "allure-behavior-snippets",
        "version": __version__,
        "base": base, "head": head, "base_ref": args.base, "head_ref": args.head,
        "layout": {"specs_root": layout.specs_root, "tests_roots": list(layout.tests_roots),
                   "code_roots": list(layout.code_roots), "id_regex": layout.id_regex},
        "stamp": stamp,
        "baseline": ({"file": "baseline-evidence.json", "commit": args.baseline_commit, "scope": scope}
                     if baseline is not None else None),
        "counts": {
            "touched_rules": len(ids),
            "orphans": sum(1 for r in rows if r["path"] is None),
            "records": records,
            "records_in_run": records_total,
            "mechanical_findings": n_findings,
            "attachments": n_attach,
            "tree_files": n_tree,
        },
        "inputs": {"prior_review": prior is not None, "issue_intent": intent is not None,
                   "pr_body": body is not None},
        "files": sorted(files),
        "process": "process/",
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def cli(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="evidence-pack", description=__doc__.split("\n\n")[0])
    ap.add_argument("base", help="base ref (the PR's target, e.g. origin/master)")
    ap.add_argument("head", help="head ref (the PR head under review)")
    ap.add_argument("results", help="raw allure results dir (*-result.json + attachments)")
    ap.add_argument("--out", default="evidence-review", metavar="DIR",
                    help="pack dir (default: evidence-review); a previous pack there is replaced")
    tr.add_layout_args(ap)
    ap.add_argument("--baseline", default=None, metavar="evidence.json",
                    help="the base branch's evidence.json (Δ + VANISHED)")
    ap.add_argument("--baseline-commit", default=None, metavar="SHA",
                    help="the commit the baseline evidence ran at")
    ap.add_argument("--baseline-scope", default=None, metavar="TEXT",
                    help="what the baseline run covered (default: its run.files)")
    ap.add_argument("--prior-review", default=None, metavar="FILE",
                    help="the previous review of this PR (round memory)")
    ap.add_argument("--issue-intent", default=None, metavar="FILE",
                    help="the closing issue's acceptance text, fetched by the launcher")
    ap.add_argument("--pr-body", default=None, metavar="FILE",
                    help="the PR body (`Spec changes:` lives there)")
    ap.add_argument("--report-url", default=None, help="published Allure report URL (table footers)")
    ap.add_argument("--no-specs-tree", action="store_true",
                    help="skip tree/<specs-root>/ (the specs at head, for neighbouring pages)")
    args = ap.parse_args(argv)
    try:
        m = build(args)
    except PackError as exc:
        print(f"evidence-pack: {exc}", file=sys.stderr)
        return 64
    c = m["counts"]
    print(f"evidence-pack {m['version']}: {m['base'][:12]}...{m['head'][:12]} → {args.out}")
    print(f"touched rules: {c['touched_rules']} · records: {c['records']} · "
          f"mechanical findings: {c['mechanical_findings']} · files: {len(m['files'])} + process/"
          + (" + tree/" if c["tree_files"] else ""))
    return 0


def main() -> None:  # console-script entry
    raise SystemExit(cli())


def process_path_main() -> None:  # console-script entry: process-path
    print(PROCESS_DIR)
    raise SystemExit(0 if PROCESS_DIR.is_dir() else 1)


if __name__ == "__main__":
    main()
