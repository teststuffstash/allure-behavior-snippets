"""Which requirement/rule IDs does a git diff touch? (stdlib only)

Rule IDs are spec headings (``## RT-STATUTE-CITE``, ``### GW-SESSIONS-ADMIT``) in
``<specs-root>/**/*.md``. The diff is ``<base>...<head>`` (three-dot: merge-base to head).
Generalised from oracle-fleet ``scripts/touched-rules.py`` (process v0.5, homelab ADR-156):
the layout (specs root, tests roots, code roots) and the ID regex are options.

Sources a rule can be touched from:

  spec-hunk      a changed ``<specs-root>/**/*.md`` hunk lands inside the rule's section
                 (new-side line range against <head>; deleted-only hunks by the old-side line
                 against <base>); a heading inside a CommonMark code fence (backtick or tilde)
                 never opens or closes a section
  page-preamble  a hunk lands before the page's first rule heading (preamble / index table),
                 which marks the page page-wide: every rule on it is touched; a page whose
                 fence parse is uncertain (a fence left open at EOF) is page-wide too, so a
                 doubtful section boundary never narrows the scope silently
  test-label     a changed ``<tests-root>/**/*.py`` carries ``@rule("ID")`` /
                 ``@evidence.rule("ID")`` / ``@pytest.mark.rule("ID")`` on a function/class, or
                 ``pytestmark = rule("ID")`` (or ``.marks``, or a list of such) at <head> — by
                 ast walk; string literals and comments elsewhere never count
  event-map      a changed ``.py`` module under a ``--code-root`` quotes the ID at <head>
                 (event → requirement tables, ``requirement`` fields). Off unless a code root
                 is given: which runtime modules map events to rules is a repo fact.
  schema         a changed ``<specs-root>/**/*.schema.json`` lists the ID under ``x-requirements``
  glossary       ``<specs-root>/glossary.md`` changed under a term and the rule's section links
                 that term's anchor (``glossary.md#<slug>``). A term is any ``##``+ heading of the
                 glossary; a hunk belongs to every heading whose section spans it, on each diff
                 side it has lines on (a renamed term touches the linkers of both names). Slugs
                 compare normalised (lowercase, ASCII-folded, punctuation dropped, runs of ``-``
                 collapsed), so a mkdocs ``#loige-subsection`` and a GitHub ``--`` slug both
                 resolve; a heading inside a CommonMark code fence (backtick or tilde) is not a
                 term. A bare ``glossary.md`` link (no anchor) or an anchor matching no heading
                 on either side counts as linking every term. Fallback: a hunk no term heading
                 claims (the title, the preamble, a structural change above the first ``##``),
                 or a glossary whose fence parse is uncertain (a fence left open at EOF), keeps
                 the old behaviour — every glossary-linking rule is touched.
  orphan         referenced from tests/code/schema but no heading anywhere under the specs root

Output: one rule ID per line (default) or ``--json`` rows ``{"rule","page","path","sources"}``
on stdout; ``--out DIR`` additionally writes ``touched-rules.json`` + ``touched-rules.txt``. Exit 0 always on a
readable repo (empty = nothing touched); a failing git call prints to stderr and exits 0 with
no rows, like the oracle original.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import sys
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from urllib.parse import unquote

DEFAULT_ID_REGEX = r"[A-Z][A-Z0-9]*(?:-[A-Z0-9¹²³]+)+"
ANY_HEAD_RE = re.compile(r"^(#{1,6})\s+\S")
HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
GLOSSARY_LINK_RE = re.compile(r"glossary\.md(?:#([^)\s\]\"'<>]*))?")
FENCE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})")


@dataclass(frozen=True)
class Layout:
    """Where a repo keeps its specs, tests and event-mapping code, and what an ID looks like."""

    specs_root: str = "specs"
    tests_roots: tuple[str, ...] = ("tests",)
    code_roots: tuple[str, ...] = ()
    id_regex: str = DEFAULT_ID_REGEX

    def __post_init__(self) -> None:
        object.__setattr__(self, "specs_root", _norm_root(self.specs_root))
        object.__setattr__(self, "tests_roots", tuple(_norm_root(r) for r in self.tests_roots))
        object.__setattr__(self, "code_roots", tuple(_norm_root(r) for r in self.code_roots))
        re.compile(self.id_regex)  # fail early on a bad --id-regex

    @property
    def rule_head_re(self) -> re.Pattern[str]:
        return re.compile(rf"^(#{{2,6}})\s+({self.id_regex})(?:\s|$)")

    @property
    def quoted_id_re(self) -> re.Pattern[str]:
        return re.compile(rf"""["']({self.id_regex})["']""")

    @property
    def glossary(self) -> str:
        return f"{self.specs_root}/glossary.md"

    def under(self, path: str, root: str) -> bool:
        return root == "." or path.startswith(root + "/")

    def is_spec_page(self, path: str) -> bool:
        return self.under(path, self.specs_root) and path.endswith(".md")

    def is_schema(self, path: str) -> bool:
        return self.under(path, self.specs_root) and path.endswith(".schema.json")

    def is_test(self, path: str) -> bool:
        return path.endswith(".py") and any(self.under(path, r) for r in self.tests_roots)

    def is_code(self, path: str) -> bool:
        return path.endswith(".py") and any(self.under(path, r) for r in self.code_roots)

    def page_stem(self, path: str) -> str:
        """``<specs-root>/endpoints/sessions.md`` → ``endpoints/sessions``."""
        p = PurePosixPath(path)
        if self.specs_root != ".":
            p = p.relative_to(self.specs_root)
        return p.with_suffix("").as_posix()

    def page_path(self, stem: str) -> str:
        return stem + ".md" if self.specs_root == "." else f"{self.specs_root}/{stem}.md"


def _norm_root(root: str) -> str:
    root = root.strip().strip("/")
    return root or "."


# ---------------------------------------------------------------- pure functions


@dataclass(frozen=True)
class Hunk:
    old_start: int
    old_len: int
    new_start: int
    new_len: int


@dataclass(frozen=True)
class Section:
    rule: str
    start: int  # 1-based heading line
    end: int  # exclusive: first line after the section


def parse_diff(diff_text: str) -> dict[str, list[Hunk]]:
    """``git diff --unified=0`` text → {path: [Hunk, ...]}.

    The path is the new-side one (``+++ b/…``); a deleted file keeps its old-side path.
    """
    hunks: dict[str, list[Hunk]] = {}
    old_path: str | None = None
    path: str | None = None
    for line in diff_text.splitlines():
        if line.startswith("diff --git "):
            old_path = path = None
        elif line.startswith("--- "):
            name = line[4:].split("\t")[0]
            old_path = None if name == "/dev/null" else name.removeprefix("a/")
        elif line.startswith("+++ "):
            name = line[4:].split("\t")[0]
            path = old_path if name == "/dev/null" else name.removeprefix("b/")
            if path is not None:
                hunks.setdefault(path, [])
        elif line.startswith("@@") and path is not None:
            m = HUNK_RE.match(line)
            if m:
                o, ol, n, nl = m.groups()
                hunks[path].append(
                    Hunk(int(o), 1 if ol is None else int(ol), int(n), 1 if nl is None else int(nl))
                )
    return hunks


def _rule_sections(text: str, layout: Layout = Layout()) -> tuple[list[Section], bool]:
    rule_head = layout.rule_head_re
    sections: list[Section] = []
    lines = text.splitlines()
    unfenced, unclosed = unfenced_lines(text)
    if unclosed:  # uncertain parse: every heading counts, so the page-wide fallback reaches them all
        unfenced = list(enumerate(lines, 1))
    open_rule: tuple[str, int, int] | None = None  # (rule, level, start)

    def close(at: int) -> None:
        nonlocal open_rule
        if open_rule is not None:
            sections.append(Section(open_rule[0], open_rule[2], at))
            open_rule = None

    for n, line in unfenced:
        head = ANY_HEAD_RE.match(line)
        if not head:
            continue
        level = len(head.group(1))
        rule_m = rule_head.match(line)
        if open_rule is not None and level <= open_rule[1]:
            close(n)
        if rule_m and open_rule is None:
            open_rule = (rule_m.group(2), level, n)
    close(len(lines) + 1)
    return sections, unclosed


def rule_sections(text: str, layout: Layout = Layout()) -> list[Section]:
    """Rule sections of one spec page: heading line → the next heading at its level or above.

    Lines inside a CommonMark code fence (backtick or tilde, see ``unfenced_lines``) are never
    headings. Non-rule headings at the rule's level or above close the section, so a trailing
    ``## Sources`` block maps to no rule.
    """
    return _rule_sections(text, layout)[0]


def section_text(text: str, rule: str, layout: Layout = Layout()) -> str | None:
    """The rule's section verbatim (heading through the line before the next same/higher
    heading), or None when the page has no such heading."""
    lines = text.splitlines()
    for s in rule_sections(text, layout):
        if s.rule == rule:
            return "\n".join(lines[s.start - 1 : s.end - 1]).rstrip("\n")
    return None


def index_pages(pages: dict[str, str], layout: Layout = Layout()) -> dict[str, str]:
    """{spec path: text} → {rule ID: page stem} (path relative to the specs root, no suffix)."""
    index: dict[str, str] = {}
    for path, text in sorted(pages.items()):
        stem = layout.page_stem(path)
        for section in rule_sections(text, layout):
            index.setdefault(section.rule, stem)
    return index


def _rules_in_range(sections: list[Section], first: int, last: int) -> set[str]:
    return {s.rule for s in sections if s.start <= last and first < s.end}


def hunk_rules(
    hunks: list[Hunk], head_text: str | None, base_text: str | None, layout: Layout = Layout()
) -> tuple[set[str], bool]:
    """Map a page's hunks to its rule sections → (rules, page_wide).

    Added/changed hunks resolve on the new side against <head>; deleted-only hunks
    (new_len == 0) on the old side against <base>. A hunk that starts before the page's first
    rule heading marks the page page-wide (preamble / index table edits touch every rule), as
    does a side whose fence parse is uncertain (a code fence left open at EOF: the section
    boundaries cannot be trusted, so nothing narrows silently).
    """
    rules: set[str] = set()
    page_wide = False
    head_sections, head_unclosed = _rule_sections(head_text, layout) if head_text is not None else ([], False)
    base_sections, base_unclosed = _rule_sections(base_text, layout) if base_text is not None else ([], False)
    for h in hunks:
        if h.new_len == 0 or head_text is None:
            sections, unclosed = base_sections, base_unclosed
            first, last = h.old_start, h.old_start + max(h.old_len, 1) - 1
        else:
            sections, unclosed = head_sections, head_unclosed
            first, last = h.new_start, h.new_start + h.new_len - 1
        if unclosed:
            page_wide = True
        if not sections:
            continue
        if first < sections[0].start:
            page_wide = True
        rules |= _rules_in_range(sections, first, last)
    return rules, page_wide


def _is_rule_call(node: ast.expr) -> bool:
    """``rule(...)`` / ``evidence.rule(...)`` / ``pytest.mark.rule(...)``."""
    if not isinstance(node, ast.Call):
        return False
    target = node.func
    if isinstance(target, ast.Name):
        return target.id == "rule"
    if isinstance(target, ast.Attribute):
        return target.attr == "rule"
    return False


def _rule_id(call: ast.Call, id_regex: str) -> str | None:
    """The ID of a ``rule("ID")`` call: first positional (or ``id=``) string matching the regex."""
    arg = call.args[0] if call.args else next((kw.value for kw in call.keywords if kw.arg == "id"), None)
    if isinstance(arg, ast.Constant) and isinstance(arg.value, str) and re.fullmatch(id_regex, arg.value):
        return arg.value
    return None


def test_labels(text: str, layout: Layout = Layout()) -> set[str]:
    """Every rule ID a test module is labelled with, by ast walk (never a text scan).

    (a) a ``rule("ID")``-shaped call decorating a function or class (at any nesting);
    (b) module-level ``pytestmark = rule("ID")`` / ``rule("ID").marks`` / a list or tuple of
        such calls. A rule ID in any other string literal or a comment does not count. A file
        that does not parse yields no labels.
    """
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError):
        return set()
    found: set[str] = set()

    def add(call: ast.expr) -> None:
        if _is_rule_call(call) and (rid := _rule_id(call, layout.id_regex)) is not None:
            found.add(rid)

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            for dec in node.decorator_list:
                for sub in ast.walk(dec):
                    add(sub)
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "pytestmark" for t in node.targets
        ):
            for sub in ast.walk(node.value):
                add(sub)
    return found


test_labels.__test__ = False  # not a pytest test, despite the name


def code_rules(text: str, layout: Layout = Layout()) -> set[str]:
    """Every quoted rule ID in a runtime module (event → requirement values, requirement fields)."""
    return set(layout.quoted_id_re.findall(text))


def schema_rules(text: str, layout: Layout = Layout()) -> set[str]:
    """Every ID under an ``x-requirements`` key, anywhere in a JSON schema."""
    found: set[str] = set()

    def walk(node: object) -> None:
        if isinstance(node, dict):
            for k, v in node.items():
                if k == "x-requirements":
                    vals = v if isinstance(v, list) else [v]
                    found.update(x for x in vals if isinstance(x, str) and re.fullmatch(layout.id_regex, x))
                else:
                    walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    try:
        walk(json.loads(text))
    except ValueError:
        pass
    return found


def slug(heading: str) -> str:
    """A heading's anchor as links spell it, normalised so renderer dialects compare equal.

    Lowercase, NFKD-folded to ASCII (``lõige`` → ``loige``), everything but letters, digits,
    whitespace and ``-`` dropped, runs of whitespace / ``-`` collapsed to one ``-``: mkdocs'
    ``redaction-redaktsioon-terviktekst`` and GitHub's ``redaction-redaktsioon--terviktekst``
    both come out the same.
    """
    text = unicodedata.normalize("NFKD", unquote(heading)).encode("ascii", "ignore").decode().lower()
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    return re.sub(r"[\s-]+", "-", text).strip("-")


@dataclass(frozen=True)
class Term:
    anchor: str
    start: int  # 1-based heading line
    end: int  # exclusive: the next heading at its level or above


def unfenced_lines(text: str) -> tuple[list[tuple[int, str]], bool]:
    """``[(line number, line)]`` outside CommonMark code fences → (lines, unclosed).

    A fence opens on up to 3 spaces of indent plus three or more backticks or tildes and closes
    on the same character, at least as long, alone on its line (trailing whitespace allowed);
    nothing inside is a heading. ``unclosed`` is True when a fence is still open at EOF — the
    parse is then uncertain: callers treat every line as unfenced and fall back page-wide rather
    than trust the boundaries.
    """
    out: list[tuple[int, str]] = []
    fence: tuple[str, int] | None = None  # (char, length)
    for n, line in enumerate(text.splitlines(), 1):
        m = FENCE_RE.match(line)
        if fence is None:
            if m and not (m.group(1)[0] == "`" and "`" in line[m.end():]):
                fence = (m.group(1)[0], len(m.group(1)))
                continue
            out.append((n, line))
        elif m and m.group(1)[0] == fence[0] and len(m.group(1)) >= fence[1] and not line[m.end():].strip():
            fence = None
    return out, fence is not None


def _glossary_terms(text: str) -> tuple[list[Term], bool]:
    lines, unclosed = unfenced_lines(text)
    if unclosed:  # uncertain parse: every heading counts; the caller falls back page-wide anyway
        lines = list(enumerate(text.splitlines(), 1))
    heads: list[tuple[int, str, int]] = []  # (level, anchor, line)
    for n, line in lines:
        m = ANY_HEAD_RE.match(line)
        if m and len(m.group(1)) >= 2:
            heads.append((len(m.group(1)), slug(line[len(m.group(1)):].strip().rstrip("#").strip()), n))
    total = text.count("\n") + (0 if text.endswith("\n") or not text else 1)
    terms: list[Term] = []
    for i, (level, anchor, start) in enumerate(heads):
        end = next((ln for lv, _, ln in heads[i + 1 :] if lv <= level), total + 1)
        terms.append(Term(anchor, start, end))
    return terms, unclosed


def glossary_terms(text: str) -> list[Term]:
    """Every ``##``+ heading of the glossary with its section (nested headings overlap their
    parent's). Lines inside a code fence (backtick or tilde, CommonMark) are never headings. The
    ``#`` title is not a term."""
    return _glossary_terms(text)[0]


def glossary_changed_terms(
    hunks: list[Hunk], head_text: str | None, base_text: str | None
) -> tuple[set[str], set[str], bool]:
    """Which glossary terms a diff changes → (changed anchors, known anchors, page_wide).

    A hunk is attributed on each side it has lines on: new-side lines against <head>, old-side
    lines against <base>, to every term whose section spans one of its non-blank lines (nested
    terms also mark their parent; a renamed term marks both names; the blank separator a new
    term adds at the tail of the previous one marks nothing). A non-blank line no term claims —
    above the first ``##`` heading, or a side with no headings at all — sets page_wide (the
    caller falls back to touching every glossary-linking rule), as does a side whose fence parse
    is uncertain (a code fence left open at EOF: the term boundaries cannot be trusted).
    ``known`` is every term anchor on either side.
    """
    head_terms, head_unclosed = _glossary_terms(head_text) if head_text is not None else ([], False)
    base_terms, base_unclosed = _glossary_terms(base_text) if base_text is not None else ([], False)
    head_lines = head_text.splitlines() if head_text is not None else []
    base_lines = base_text.splitlines() if base_text is not None else []
    changed: set[str] = set()
    page_wide = head_unclosed or base_unclosed
    for h in hunks:
        sides = [
            (head_terms, head_lines, h.new_start, h.new_start + h.new_len - 1),
            (base_terms, base_lines, h.old_start, h.old_start + h.old_len - 1),
        ]
        for terms, lines, first, last in sides:
            content = [n for n in range(first, last + 1) if n <= len(lines) and lines[n - 1].strip()]
            for n in content:
                hit = {t.anchor for t in terms if t.start <= n < t.end}
                if not hit:
                    page_wide = True
                changed |= hit
    known = {t.anchor for t in head_terms} | {t.anchor for t in base_terms}
    return changed, known, page_wide


def glossary_links(text: str, layout: Layout = Layout()) -> dict[str, set[str | None]]:
    """{rule: anchors} for the rules of one page whose section text links to glossary.md.

    Each anchor is normalised with ``slug``; ``None`` stands for a bare ``glossary.md`` link
    (no anchor, or an empty one), which counts as linking every term.
    """
    lines = text.splitlines()
    links: dict[str, set[str | None]] = {}
    for s in rule_sections(text, layout):
        found: set[str | None] = set()
        for ln in lines[s.start - 1 : s.end - 1]:
            for m in GLOSSARY_LINK_RE.finditer(ln):
                anchor = slug(m.group(1)) if m.group(1) else ""
                found.add(anchor or None)
        if found:
            links[s.rule] = found
    return links


def glossary_linked_rules(text: str, layout: Layout = Layout()) -> set[str]:
    """Rules of one page whose section text links to glossary.md (any anchor or none)."""
    return set(glossary_links(text, layout))


def glossary_touched_rules(
    text: str, changed: set[str], known: set[str], page_wide: bool, layout: Layout = Layout()
) -> set[str]:
    """Rules of one page the glossary source touches: every glossary-linking rule when
    page_wide, else the linkers of a changed term, a bare link, or an anchor no term claims."""
    return {
        rule
        for rule, anchors in glossary_links(text, layout).items()
        if page_wide or any(a is None or a not in known or a in changed for a in anchors)
    }


@dataclass
class Touched:
    sources: dict[str, set[str]] = field(default_factory=dict)

    def add(self, rule: str, source: str) -> None:
        self.sources.setdefault(rule, set()).add(source)


def compute(
    changed: list[str],
    hunks: dict[str, list[Hunk]],
    head_specs: dict[str, str],
    base_spec: dict[str, str | None],
    head_file: dict[str, str | None],
    layout: Layout = Layout(),
) -> list[dict]:
    """The pure core: changed paths + hunks + file texts → the JSON rows.

    head_specs: every spec page under the specs root at <head>; base_spec: changed spec pages
    at <base>; head_file: changed non-spec files (tests/code/schemas) at <head>. Missing = None.
    """
    index = index_pages(head_specs, layout)
    touched = Touched()
    for path in changed:
        if layout.is_spec_page(path):
            head_text = head_specs.get(path)
            rules, page_wide = hunk_rules(hunks.get(path, []), head_text, base_spec.get(path), layout)
            for r in rules:
                touched.add(r, "spec-hunk")
            if page_wide and head_text is not None:
                for s in rule_sections(head_text, layout):
                    touched.add(s.rule, "page-preamble")
        elif layout.is_schema(path):
            for r in schema_rules(head_file.get(path) or "", layout):
                touched.add(r, "schema")
        elif layout.is_test(path):
            for r in test_labels(head_file.get(path) or "", layout):
                touched.add(r, "test-label")
        elif layout.is_code(path):
            for r in code_rules(head_file.get(path) or "", layout):
                touched.add(r, "event-map")
    if layout.glossary in changed:
        terms, known, page_wide = glossary_changed_terms(
            hunks.get(layout.glossary, []), head_specs.get(layout.glossary), base_spec.get(layout.glossary)
        )
        for text in head_specs.values():
            for r in glossary_touched_rules(text, terms, known, page_wide, layout):
                touched.add(r, "glossary")
    rows = []
    for rule in sorted(touched.sources):
        page = index.get(rule)
        sources = set(touched.sources[rule])
        if page is None:
            sources.add("orphan")
        rows.append({
            "rule": rule,
            "page": page,
            "path": layout.page_path(page) if page is not None else None,
            "sources": sorted(sources),
        })
    return rows


# ---------------------------------------------------------------- git plumbing


class Git:
    def __init__(self, repo: str | Path = "."):
        self.repo = str(repo)

    def __call__(self, *args: str) -> str:
        return subprocess.run(
            ["git", "-C", self.repo, *args], check=True, capture_output=True, text=True
        ).stdout

    def show(self, rev: str, path: str) -> str | None:
        proc = subprocess.run(
            ["git", "-C", self.repo, "show", f"{rev}:{path}"], capture_output=True, text=True
        )
        return proc.stdout if proc.returncode == 0 else None

    def rev(self, ref: str) -> str:
        return self("rev-parse", "--verify", f"{ref}^{{commit}}").strip()


def head_spec_pages(git: Git, head: str, layout: Layout) -> dict[str, str]:
    root = layout.specs_root
    listing = git("ls-tree", "-r", "--name-only", head, "--", root) if root != "." else git(
        "ls-tree", "-r", "--name-only", head
    )
    paths = [p for p in listing.splitlines() if p.endswith(".md")]
    return {p: t for p in paths if (t := git.show(head, p)) is not None}


def touched_rules(git: Git, base: str, head: str, layout: Layout = Layout()) -> list[dict]:
    """The rows for ``<base>...<head>`` in ``git``'s repo. Raises CalledProcessError."""
    rng = f"{base}...{head}"
    changed = git("diff", "--name-only", rng).split("\n")
    changed = [p for p in changed if p]
    hunks = parse_diff(git("diff", "--unified=0", rng))
    head_specs = head_spec_pages(git, head, layout)
    base_spec = {p: git.show(base, p) for p in changed if layout.is_spec_page(p)}
    head_file = {p: git.show(head, p) for p in changed if p not in base_spec}
    return compute(changed, hunks, head_specs, base_spec, head_file, layout)


def unique_ids(rows: list[dict]) -> list[str]:
    seen: list[str] = []
    for r in rows:
        if r["rule"] not in seen:
            seen.append(r["rule"])
    return seen


def write_outputs(rows: list[dict], out_dir: str | Path) -> list[str]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "touched-rules.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    ids = unique_ids(rows)
    (out / "touched-rules.txt").write_text("".join(f"{r}\n" for r in ids), encoding="utf-8")
    return ["touched-rules.json", "touched-rules.txt"]


def add_layout_args(ap: argparse.ArgumentParser) -> None:
    ap.add_argument("--repo", default=".", metavar="DIR", help="git checkout to read (default: cwd)")
    ap.add_argument("--specs-root", default="specs", metavar="DIR",
                    help="repo-relative dir holding the spec pages (default: specs)")
    ap.add_argument("--tests-root", action="append", default=None, metavar="DIR",
                    help="repo-relative test dir whose rule labels count (repeatable; default: tests)")
    ap.add_argument("--code-root", action="append", default=None, metavar="DIR",
                    help="repo-relative runtime dir whose quoted IDs count as event-map sources "
                         "(repeatable; default: none)")
    ap.add_argument("--id-regex", default=DEFAULT_ID_REGEX, metavar="RE",
                    help=f"rule ID regex (default: {DEFAULT_ID_REGEX})")


def layout_of(args: argparse.Namespace) -> Layout:
    return Layout(
        specs_root=args.specs_root,
        tests_roots=tuple(args.tests_root or ["tests"]),
        code_roots=tuple(args.code_root or []),
        id_regex=args.id_regex,
    )


def cli(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="touched-rules", description=__doc__.split("\n", 1)[0])
    ap.add_argument("--base", default="master", help="base ref (default: master)")
    ap.add_argument("--head", default="HEAD", help="head ref (default: HEAD)")
    add_layout_args(ap)
    ap.add_argument("--json", action="store_true", dest="as_json", help="print the JSON rows")
    ap.add_argument("--out", default=None, metavar="DIR",
                    help="also write DIR/touched-rules.json + DIR/touched-rules.txt")
    args = ap.parse_args(argv)
    layout = layout_of(args)
    try:
        rows = touched_rules(Git(args.repo), args.base, args.head, layout)
    except subprocess.CalledProcessError as exc:
        print(f"touched-rules: git failed: {(exc.stderr or '').strip()}", file=sys.stderr)
        return 0
    if args.out:
        write_outputs(rows, args.out)
    if args.as_json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
    else:
        for rid in unique_ids(rows):
            print(rid)
    return 0


def main() -> None:  # console-script entry
    raise SystemExit(cli())


if __name__ == "__main__":
    main()
