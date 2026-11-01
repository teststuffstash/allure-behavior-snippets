"""The context pack for the specs reviewer: one deterministic inputs dir per PR round.

    evidence-pack BASE HEAD RESULTS --out DIR [--repo .] [--specs-root specs]
        [--tests-root DIR ...] [--code-root DIR ...] [--id-regex RE]
        [--baseline evidence.json [--baseline-commit SHA] [--baseline-scope TEXT]]
        [--prior-review FILE] [--issue-intent FILE] [--pr-body FILE]
        [--report-url URL] [--no-specs-tree] [--mask-descriptions]

oracle-fleet ``scripts/evidence-review.sh``'s contract in Python, plus the round inputs of
homelab ADR-156. A confined reviewer reads ONLY this dir: the briefs and rules it judges by are
copied in (``process/``) at the version this tool was pinned at, so the process a review ran
under is the process in its inputs.

``--mask-descriptions`` adds the staged read's first-pass surface (briefs/rows.md check 10):
``spec-sections-masked.md`` (every decision table's description cell → row key ``r<t>.<r>``,
numbered over the whole page), ``row-keys.tsv`` (key → description), and the masked twins
``digest.masked.md`` + ``<RULE>.masked.md`` (the case column keyed the same way). ``tree/``,
``evidence/`` and the attachments stay unmasked; ``manifest.json`` lists the masked files. With
``--prior-review`` it also writes ``pass1-prior.tsv`` — the keys the previous review's "Pass-1
adjudication" ruled on (key, ruling, round, rule) and nothing else, so pass 1 keeps its memory
without a description reaching it; a key is carried only while it provably names the same row
(the review's ``specs-review head=`` trailer, the rule's section and the key's row unchanged
since), else dropped — fail closed, the manifest's ``masked.prior`` says why.

``process-path`` prints the installed ``process/`` dir (the briefs, RULES.md, CONVENTIONS.md).
stdlib only.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

from . import __version__
from . import evidence as ev
from . import touched_rules as tr

PROCESS_DIR = Path(__file__).resolve().parent / "process"
TOP_LEVEL_SUFFIXES = (".md", ".json", ".txt", ".tsv")
PACK_DIRS = ("process", "tree", "attachments")

NONE_TEXT = {
    "prior-review.md": "previous review: none (round 1)\n",
    "issue-intent.md": ("issue intent: not provided (this PR closes no issue, or the launcher did "
                        "not fetch it) — check 1 grounds rows in the page prose, a use case or "
                        "`Spec changes:`\n"),
    "pr-body.md": "pr body: not provided — `Spec changes:` cannot be read from this pack\n",
}


RULINGS = ("survives", "contradicted", "withdrawn", "noted")
PASS1_PRIOR = "pass1-prior.tsv"
_ADJUDICATION_RE = re.compile(r"^\s*(?:#{1,6}\s*)?(?:\*\*)?pass[- ]?1 adjudication", re.IGNORECASE)
_ITEM_RE = re.compile(r"^(?:[-*+]|\d+[.)])\s+")
_KEY_RE = re.compile(r"\br(\d+)(?:\.(\d+))?\b")
_KEY_RANGE_RE = re.compile(r"\br(\d+)\.(\d+)\s*[-–—]\s*r(\d+)\.(\d+)\b")
_RULING = "|".join(RULINGS)
# the verdict positions: an emphasised `**survives**` / `**contradicted as …**`, or the ruling right
# after the key segment's `:` / `—` (optionally through a closing `**`); never a word elsewhere
_VERDICT_RE = re.compile(r"(?:\*\*\s*|[:—–-]\s*(?:\*\*)?\s*)(" + _RULING + r")\b", re.IGNORECASE)
# the prescribed re-listing form: `- <key> — prior: ruled <ruling> round <N>` / `(prior: ruled … round N)`
_PRIOR_FORM_RE = re.compile(r"prior:\s*ruled\s+(" + _RULING + r")\s+round\s+(\d+|prior)\b", re.IGNORECASE)
_QUOTED_RE = re.compile(r'"[^"]*"|`[^`]*`|(?<!\w)\'[^\']*\'(?!\w)')
_LABEL_RE = re.compile(r"\bP\d+-\d+\b")
_ROUND_RE = re.compile(r"^Prior findings:\s*none\s*\(round\s+(\d+)\)", re.IGNORECASE | re.MULTILINE)
_TRAILER_RE = re.compile(r"<!--\s*specs-review\s+head=([0-9a-fA-F]{7,40})\b")


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
                  base: str, head: str, spec_diff: str | None) -> str:
    """Each touched rule's section from ``head_specs`` (the pages at head — or their masked
    copies), then the spec diff; ``spec_diff=None`` states its absence (the masked surface: a
    diff's rows carry descriptions and cannot be keyed)."""
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
    if spec_diff is None:
        out += ["<!-- spec diff: not in the masked surface (its rows carry descriptions) — "
                "spec-sections.md holds it -->", ""]
    else:
        out += ["# Spec diff", "", "```diff", spec_diff.rstrip("\n"), "```", ""]
    return "\n".join(out)


def row_keys_tsv(keymaps: dict[str, list[tuple[str, str]]], used: dict[str, set[str]]) -> str:
    """``row-keys.tsv``: ``key<TAB>description`` for every key the masked sections show, grouped
    under a ``# <page path>`` line per page (keys number per page, so the page disambiguates)."""
    out: list[str] = []
    for path in sorted(keymaps):
        lines = [f"{k}\t{d}" for k, d in keymaps[path] if k in used.get(path, set())]
        if lines:
            out += [f"# {path}", *lines]
    return "\n".join(out) + ("\n" if out else "")


def case_keys(spec: dict[str, list], masked_spec: dict[str, list], evidence: dict) -> dict[tuple[str, str], str]:
    """``(rule, case) → row key`` for every description cell and every record a spec row joins
    (exact or substring), so the masked evidence surfaces key a case the way the page does."""
    keys: dict[tuple[str, str], str] = {}
    for rid, tables in spec.items():
        recs = evidence.get("rules", {}).get(rid, [])
        for (_, rows), (_, mrows) in zip(tables, masked_spec.get(rid, [])):
            for row, mrow in zip(rows, mrows):
                if not row or not mrow or row[0] == mrow[0]:
                    continue  # not a decision table: nothing was keyed
                keys[(rid, row[0])] = mrow[0]
                for r in ev.match_case(row[0], recs)[1]:
                    keys[(rid, r["case"])] = mrow[0]
    return keys


def mask_records(evidence: dict | None, keys: dict[tuple[str, str], str]) -> dict | None:
    """A copy of ``evidence`` with each record's ``case`` keyed by ``keys`` (a case no spec row
    claims keeps its pytest id — there is no key to show)."""
    if evidence is None:
        return None
    rules = {rid: [{**r, "case": keys.get((rid, r["case"]), r["case"])} for r in recs]
             for rid, recs in evidence.get("rules", {}).items()}
    return {**evidence, "rules": rules}


def _rule_lines(tables: list | None, recs: list, run: dict, report_url: str | None, rid: str) -> list[str]:
    """``<RULE>.md``: the spec table joined to its evidence, else the evidence table."""
    if ev.rule_joins(tables, recs) or (tables and not recs):
        return ev.render_joined(tables, recs, run, report_url)
    if recs:
        return ev.render_table(recs, run, report_url)
    return [f"_no evidence rows for {rid}_"]


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


def _adjudication_items(review: str) -> list[str]:
    """The head line of every list item under the review's "Pass-1 adjudication" heading (an
    item's indented continuation lines are not read: that is where a quoted description lives).
    The section ends at the next heading or unindented non-list line (`Findings:` …)."""
    lines = review.split("\n")
    start = next((i for i, l in enumerate(lines) if _ADJUDICATION_RE.match(l)), None)
    if start is None:
        return []
    items: list[str] = []
    for line in lines[start + 1:]:
        if not line.strip():
            continue
        if line.startswith("#") or (not line[0].isspace() and not _ITEM_RE.match(line)):
            break
        if _ITEM_RE.match(line):
            items.append(_ITEM_RE.sub("", line, count=1))
    return items


def _expand_keys(text: str) -> list[str]:
    """Row keys named in one adjudication line, in order: `r18.1/r18.2` splits, `r71.3–r71.5`
    expands (same table only), a table-level `r52` stays as written."""
    keys: list[str] = []
    spans: list[tuple[int, int]] = []
    for m in _KEY_RANGE_RE.finditer(text):
        t1, a, t2, b = m.groups()
        if t1 == t2 and int(a) <= int(b):
            keys += [f"r{t1}.{n}" for n in range(int(a), int(b) + 1)]
            spans.append(m.span())
    for m in _KEY_RE.finditer(text):
        if any(lo <= m.start() < hi for lo, hi in spans):
            continue
        keys.append(m.group(0))
    seen: set[str] = set()
    return [k for k in keys if not (k in seen or seen.add(k))]


def prior_rulings(review: str | None, id_regex: str = tr.DEFAULT_ID_REGEX) -> list[dict]:
    """The previous review's pass-1 rulings as keys only: one record per row key the
    "Pass-1 adjudication" section names, ``{key, ruling, round, rule}``. Quoted (``"…"``,
    ``'…'``) and backticked spans are blanked first; ``ruling`` is read ONLY from a verdict
    position (``**survives**``, ``: contradicted.``, ``— withdrawn.``) — a line with none, or with
    two different rulings there, is rejected. ``round`` is the review's own round when it states
    one (``Prior findings: none (round N)``) else ``prior``. The re-listing form a pass 1 writes,
    ``<key> — prior: ruled <ruling> round <N>``, carries the ORIGINAL ruling and round through
    later rounds (a differing verdict on the same line is a re-ruling and wins). ``rule`` is the
    first requirement id on the line (``""`` when none). No other text of the review is carried
    — pass 1 must never see a description."""
    if not review:
        return []
    m = _ROUND_RE.search(review)
    rnd = m.group(1) if m else "prior"
    rule_re = re.compile(rf"(?<![\w-])({id_regex})(?![\w-])")
    out: list[dict] = []
    for item in _adjudication_items(review):
        item = _QUOTED_RE.sub("", item)
        keys = _expand_keys(item)
        if not keys:
            continue
        prior_form = _PRIOR_FORM_RE.search(item)
        verdicts = {v.lower() for v in _VERDICT_RE.findall(_PRIOR_FORM_RE.sub("", item))}
        if len(verdicts) > 1 or not (verdicts or prior_form):
            continue  # no verdict, or an ambiguous one: not carried
        ruling, this_round = (next(iter(verdicts)), rnd) if verdicts else (None, None)
        if prior_form and (ruling is None or ruling == prior_form.group(1).lower()):
            ruling, this_round = prior_form.group(1).lower(), prior_form.group(2).lower()
        rm = rule_re.search(_LABEL_RE.sub("", item))
        rule = rm.group(1) if rm else ""
        out += [{"key": k, "ruling": ruling, "round": this_round, "rule": rule} for k in keys]
    return out


def prior_head(review: str | None) -> str | None:
    """The head the previous review was posted at: its ``<!-- specs-review head=<sha> … -->``
    trailer, or None."""
    m = _TRAILER_RE.search(review or "")
    return m.group(1).lower() if m else None


def carry_prior_rulings(review: str | None, git: tr.Git, head: str, head_specs: dict[str, str],
                        layout: tr.Layout) -> tuple[list[dict], dict]:
    """The prior rulings that still name the same row at ``head`` — row keys are positional
    per page, so a ruling is carried only when it cannot have drifted: the review states the head
    it was posted at (else NO file: fail closed), the record names a rule (a key without one is
    ambiguous across pages), that rule heads exactly one page at ``head``, its section is
    byte-identical between the prior head and ``head``, and the key maps to the same description
    at both (a table added earlier on the page renumbers every later key). Anything else is
    dropped and the row is reviewed afresh. Returns ``(kept, info)``; ``info`` is the manifest's
    ``masked.prior`` entry."""
    rulings = prior_rulings(review, layout.id_regex)
    info: dict = {"file": None, "head": None, "carried": 0, "dropped": 0, "reason": None}
    if not rulings:
        info["reason"] = "the prior review has no pass-1 adjudication with row keys"
        return [], info
    sha = prior_head(review)
    if sha is None:
        info["reason"] = "the prior review carries no `<!-- specs-review head=… -->` trailer"
        info["dropped"] = len(rulings)
        return [], info
    try:
        prior = git.rev(sha)
    except subprocess.CalledProcessError:
        info["reason"] = f"the prior review's head {sha} is not in the repo"
        info["dropped"] = len(rulings)
        return [], info
    info["head"] = prior
    page_of: dict[str, str | None] = {}
    for path, text in head_specs.items():
        for sec in tr.rule_sections(text, layout):
            page_of[sec.rule] = None if sec.rule in page_of else path  # None = heads two pages
    keymaps: dict[tuple[str, str], dict[str, str]] = {}

    def keymap(rev: str, path: str, text: str | None) -> dict[str, str] | None:
        if (rev, path) not in keymaps:
            keymaps[(rev, path)] = None if text is None else dict(ev.mask_page(text)[1])
        return keymaps[(rev, path)]

    kept: list[dict] = []
    for r in rulings:
        path = page_of.get(r["rule"]) if r["rule"] else None
        if path is None:
            continue
        prior_text = git.show(prior, path)
        if prior_text is None or (tr.section_text(prior_text, r["rule"], layout)
                                  != tr.section_text(head_specs[path], r["rule"], layout)):
            continue
        before, now = keymap(prior, path, prior_text), keymap(head, path, head_specs[path])
        prefix = r["key"] if "." in r["key"] else r["key"] + "."
        same = ({k: d for k, d in before.items() if k == r["key"] or k.startswith(prefix)}
                == {k: d for k, d in now.items() if k == r["key"] or k.startswith(prefix)})
        if same and (r["key"] in now or any(k.startswith(prefix) for k in now)):
            kept.append(r)
    info["carried"], info["dropped"] = len(kept), len(rulings) - len(kept)
    if kept:
        info["file"] = PASS1_PRIOR
    else:
        info["reason"] = "every prior ruling was dropped: its rule's section or its key changed since the prior head"
    return kept, info


def pass1_prior_tsv(rulings: list[dict]) -> str:
    """``pass1-prior.tsv``: ``key<TAB>ruling<TAB>round<TAB>rule`` under a header line."""
    return "".join(f"{r['key']}\t{r['ruling']}\t{r['round']}\t{r['rule']}\n"
                   for r in [{"key": "key", "ruling": "ruling", "round": "round", "rule": "rule"}, *rulings])


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
        (out / name).parent.mkdir(parents=True, exist_ok=True)
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
    # 2b. the masked surface (--mask-descriptions): the same sections with every description
    #     cell a row key numbered over the whole page, the key map, no diff
    masked_specs: dict[str, str] = {}
    masked_files: list[str] = []
    prior_info: dict | None = None
    if args.mask_descriptions:
        keymaps: dict[str, list[tuple[str, str]]] = {}
        used: dict[str, set[str]] = {}
        for path in sorted({r["path"] for r in rows if r["path"]}):
            text = head_specs.get(path)
            if text is None:
                continue
            masked_specs[path], keymaps[path] = ev.mask_page(text)
            keyset = {k for k, _ in keymaps[path]}
            for rid in {r["rule"] for r in rows if r["path"] == path}:
                for _, trows in ev.spec_tables(masked_specs[path], rid):
                    used.setdefault(path, set()).update(t[0] for t in trows if t and t[0] in keyset)
        write("spec-sections-masked.md", spec_sections(rows, masked_specs, layout, base, head, None))
        write("row-keys.tsv", row_keys_tsv(keymaps, used))
        masked_files += ["spec-sections-masked.md"]
        # 2c. pass 1's round memory: the previous review's pass-1 rulings as KEYS only (the
        #     review itself quotes descriptions, so it stays out of the masked allow-list), and
        #     only the keys that still name the same row (fail closed on drift)
        if prior is not None:
            prior_keys, prior_info = carry_prior_rulings(prior, git, head, head_specs, layout)
            if prior_keys:
                write(PASS1_PRIOR, pass1_prior_tsv(prior_keys))
                masked_files.append(PASS1_PRIOR)

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
        if args.mask_descriptions:
            write("digest.masked.md", (out / "digest.md").read_text(encoding="utf-8"))
            masked_files.append("digest.masked.md")
    else:
        dirs = [str(results)]
        evidence = ev.build_evidence(ev.load_results(dirs), ev.load_environment(dirs), results_dirs=dirs)
        stamp = stamp_of(evidence["run"], head)
        spec, masked_spec = {}, {}
        for path in sorted({r["path"] for r in rows if r["path"]}):
            on_page = [r["rule"] for r in rows if r["path"] == path]
            text = head_specs.get(path)
            if text is None:
                continue
            for rid in on_page:
                tables = ev.spec_tables(text, rid)
                if tables:
                    spec[rid] = tables
                    if path in masked_specs:
                        masked_spec[rid] = ev.spec_tables(masked_specs[path], rid)
        records_total = sum(len(v) for v in evidence["rules"].values())
        scoped = _filter_rules(evidence, ids)
        records = sum(len(v) for v in scoped["rules"].values())
        write("evidence.json", json.dumps(scoped, indent=2, sort_keys=True, ensure_ascii=False))
        # one file per touched rule: a reviewer reads ONE rule's records (steps, thread,
        # attachments) without loading every rule's — evidence.json for a wide PR runs to six
        # figures of tokens, and a confined reviewer has no grep to cut it
        for rid in ids:
            write(f"evidence/{rid}.json", json.dumps({"run": scoped.get("run", {}), "rule": rid,
                                                     "records": scoped["rules"].get(rid, [])},
                                                    indent=2, sort_keys=True, ensure_ascii=False))
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
            write(f"{rid}.md", "\n".join(_rule_lines(spec.get(rid), evidence["rules"].get(rid, []),
                                                     evidence["run"], args.report_url, rid)))
        if args.mask_descriptions:
            # the masked twins: the same join, every case keyed like its spec row (a substring
            # join reads exact here — ROW_UNKEYED is a description-level finding, pass 2's)
            keys = case_keys(spec, masked_spec, evidence)
            m_ev, m_base = mask_records(evidence, keys), mask_records(baseline, keys)
            write("digest.masked.md", "\n".join(
                head_lines + ev.render_digest(ids, m_ev, m_base, args.report_url, masked_spec)))
            masked_files.append("digest.masked.md")
            for rid in ids:
                write(f"{rid}.masked.md", "\n".join(_rule_lines(
                    masked_spec.get(rid), m_ev["rules"].get(rid, []), m_ev["run"], args.report_url, rid)))
                masked_files.append(f"{rid}.masked.md")
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
        "masked": ({"files": sorted(masked_files), "keys": "row-keys.tsv", "tree": "unmasked",
                    "prior": prior_info,
                    "unmasked": ["spec-sections.md", "digest.md", "<RULE>.md", "evidence.json",
                                 "evidence/", "baseline-evidence.json", "attachments/", "tree/"]}
                   if args.mask_descriptions else None),
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
    ap.add_argument("--mask-descriptions", action="store_true",
                    help="also write the staged read's first-pass surface: spec-sections-masked.md "
                         "(description cells → row keys r<table>.<row>), row-keys.tsv, "
                         "digest.masked.md and <RULE>.masked.md; with --prior-review also "
                         "pass1-prior.tsv (the prior pass-1 rulings, keys only)")
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
          + (" + tree/" if c["tree_files"] else "")
          + (f" · masked: {len(m['masked']['files'])} + row-keys.tsv" if m["masked"] else ""))
    return 0


def main() -> None:  # console-script entry
    raise SystemExit(cli())


def process_path_main() -> None:  # console-script entry: process-path
    print(PROCESS_DIR)
    raise SystemExit(0 if PROCESS_DIR.is_dir() else 1)


if __name__ == "__main__":
    main()
