"""The shipped process documents: numbering, the codes the briefs promise, island neutrality."""
import re
import tomllib
from pathlib import Path

import pytest

import allure_behavior_snippets
from allure_behavior_snippets.pack import process_dir

P = process_dir()
DOCS = ["RULES.md", "CONVENTIONS.md", "briefs/rows.md", "briefs/evidence.md", "briefs/finding-contract.md",
        "briefs/author.md"]


def read(name):
    return (P / name).read_text(encoding="utf-8")


def test_all_docs_ship():
    for d in DOCS:
        assert (P / d).is_file(), d


def test_rules_numbered_1_to_11():
    nums = [int(m) for m in re.findall(r"^(\d+)\. \*\*", read("RULES.md").split("## Rules", 1)[1], re.M)]
    assert nums[:11] == list(range(1, 12))


@pytest.mark.parametrize("doc", DOCS)
def test_island_neutral(doc):
    text = read(doc)
    for word in ("oracle", "gateway", "corpus", "riigi", "minutark"):
        assert word not in text.lower(), f"{doc} mentions {word}"
    for prefix in ("ING-", "RT-", "GW-"):  # the islands' rule-ID prefixes
        assert not re.search(rf"\b{prefix}[A-Z]", text), f"{doc} mentions {prefix}"


def test_conventions_sections_the_briefs_pin_by_name():
    conv = read("CONVENTIONS.md")
    for section in ("## Allure taxonomy — one story per rule", "## The `rule()` decorator",
                    "## The intent column", "## Evidence row identity = (rule ID, world, case)",
                    "## Prime rule of reporting", "## Evidence blocks on spec pages",
                    "## The head/artifact stamp"):
        assert section in conv, section
    headings = re.findall(r"^## (.+)$", conv, re.M)
    refs = [ref.strip() for brief in ("briefs/rows.md", "briefs/evidence.md", "briefs/finding-contract.md",
                                      "briefs/author.md")
            for ref in re.findall(r"CONVENTIONS\.md\]\([^)]*\)\s+§ ([^,.\n();]+)", read(brief))]
    assert len(refs) >= 3
    for ref in refs:
        assert any(h.startswith(ref) for h in headings), ref


def test_hygiene_codes_defined_once_in_conventions():
    codes = ["STEP_FLAT", "STEP_NOISE", "NAME_BLANK", "ATTACH_BULK", "PARAM_BLOB", "CONTEXT_TAX", "THREAD_BROKEN"]
    conv, ev = read("CONVENTIONS.md"), read("briefs/evidence.md")
    for c in codes:
        assert f"| `{c}` |" in conv, c
        assert f"`{c}`" in ev, c
        assert f"| `{c}` |" not in ev, f"{c} defined twice"


def test_evidence_brief_predicate_codes():
    ev = read("briefs/evidence.md")
    for c in ("NO_EVIDENCE", "ROW_UNPROVEN", "ROW_UNKEYED", "HEADER_UNTHREADED", "ROW_UNSPECIFIED", "BARE_ROW",
              "FAILED", "VANISHED", "UNIT_ONLY", "WORLD_UNNAMED"):
        assert f"| `{c}` |" in ev, c
    assert "HYGIENE_REPEAT" in ev and "three worst" in ev


def test_rows_brief_checks_and_candidate_shape():
    rows = read("briefs/rows.md")
    for n in (1, 2, 3, 4, 7, 8, 9, 10):
        assert re.search(rf"^{n}\. \*\*", rows, re.M), n
    assert "## Table shape — CANDIDATE — under operator iteration (2026-09-29 hold); ADVISORY ONLY, never a finding" in rows
    assert "Prose claims without a row" in rows


def test_staged_read_names_the_masked_surface():
    """v0.6.4: check 10 is two passes over the pack's masked surface (evidence-pack --mask-descriptions)."""
    rows, conv, ev = read("briefs/rows.md"), read("CONVENTIONS.md"), read("briefs/evidence.md")
    check = rows.split("10. **", 1)[1].split("\n\n", 1)[0]
    for name in ("spec-sections-masked.md", "row-keys.tsv", "`r<table>.<row>`", "frozen",
                 "`survives`", "`contradicted`", "`withdrawn`", "NOT repaired"):
        assert name in check, name
    assert "spec-sections-masked.md" in conv.split("**Rows read without their description.**", 1)[1].split("\n\n", 1)[0]
    assert "digest.masked.md" in ev and "<RULE>.masked.md" in ev


@pytest.mark.parametrize("brief", ["briefs/rows.md", "briefs/evidence.md", "briefs/finding-contract.md"])
def test_every_brief_states_the_ground_rules(brief):
    text = read(brief).lower()
    assert "intent before evidence" in text
    assert "never read implementation code" in text
    assert "the inputs dir is the only world" in text


def test_author_brief_points_and_does_not_restate():
    """The worker-facing brief cites rules by number and the reviewer's briefs by name; it holds no
    second definition (no code table, no numbered checks) and no repo fact."""
    author = read("briefs/author.md")
    assert author.startswith("# Author brief")
    for name in ("rows.md", "evidence.md", "finding-contract.md", "../RULES.md", "../CONVENTIONS.md"):
        assert f"]({name})" in author, name
    assert len(set(re.findall(r"\(rules? (\d+)", author))) >= 8  # cites most of RULES.md by number
    for phrase in ("Spec changes:", "⚖", "⚑ gap", "🚧 WIP", "Satisfied by:", "check 10",
                   "§ Adopting this process in a repo"):
        assert phrase in author, phrase
    assert not re.search(r"^\| `[A-Z_]+` \|", author, re.M), "a code table belongs in CONVENTIONS / evidence.md"
    assert not re.search(r"^\d+\. \*\*", author, re.M), "numbered checks are the rows brief's"
    assert not re.search(r"\b20\d\d-\d\d-\d\d\b", author), "no dates — the CHANGELOG carries history"


def test_finding_contract():
    fc = read("briefs/finding-contract.md")
    for shape in ("R<check>/<page>#<RULE>", "E-<CODE>/<page>#<RULE>[/<case>]", "H-<CODE>/<case>"):
        assert shape in fc
    for field in ("Rule/case:", "Violated:", "Observed:", "Satisfied by:"):
        assert field in fc
    for line in ("## Specs review", "Verdict:", "Prior findings:", "Findings:", "Rows:", "Evidence:",
                 "Hygiene notes:", "Shape:", "Terms:", "What would change my verdict:"):
        assert line in fc.split("## Output shape", 1)[1], line


def test_version_matches_pyproject():
    root = Path(allure_behavior_snippets.__file__).resolve().parent.parent
    pyproject = root / "pyproject.toml"
    if not pyproject.is_file():  # the test image copies the package + tests only
        pytest.skip("pyproject.toml not in this checkout")
    meta = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    assert meta["tool"]["poetry"]["version"] == allure_behavior_snippets.__version__
    scripts = meta["tool"]["poetry"]["scripts"]
    # v0.4.x entry points stay; v0.5 adds three
    assert scripts["allure-behavior-snippets"] == "allure_behavior_snippets.main:cli"
    assert scripts["allure-evidence"] == "allure_behavior_snippets.evidence:cli"
    assert {"touched-rules", "evidence-pack", "process-path"} <= set(scripts)
