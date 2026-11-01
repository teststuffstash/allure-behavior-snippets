import json
from pathlib import Path

import pytest

from allure_behavior_snippets import __version__, pack
from tests.gitrepo import PAGE_A, base_repo

RESULT_FILES = {"one item", "zero items"}


def _result(case, status="passed", story="API-ORDERS-CREATE", attach=None, world="uc-1"):
    d = {
        "name": f"test_create[{case}]",
        "fullName": "tests.test_orders#test_create",
        "status": status,
        "labels": [{"name": "story", "value": story}, {"name": "world", "value": world}],
        "parameters": [{"name": "qty", "value": "1"}],
        "steps": [{"name": f"When: POST /orders qty={case}", "steps": [],
                   "attachments": ([{"name": "request", "source": attach, "type": "text/plain"}]
                                   if attach else [])}],
    }
    return d


def write_results(d: Path, results, commit=None, digest=None):
    d.mkdir(parents=True, exist_ok=True)
    for i, r in enumerate(results):
        (d / f"{i}-result.json").write_text(json.dumps(r), encoding="utf-8")
    props = []
    if commit:
        props.append(f"git.commit={commit}")
    if digest:
        props.append(f"image.digest={digest}")
    (d / "environment.properties").write_text("\n".join(props) + "\n", encoding="utf-8")
    return d


@pytest.fixture()
def repo(tmp_path):
    r = base_repo(tmp_path / "repo")
    r.write("specs/endpoints/orders.md", PAGE_A.replace("| zero items | 0 || 400 |", "| zero items | 0 || 422 |"))
    r.head = r.commit("pr")
    return r


def run(repo, results, out, *extra):
    return pack.cli(["master", "HEAD", str(results), "--repo", str(repo.root), "--out", str(out), *extra])


def test_full_pack(repo, tmp_path, capsys):
    res = tmp_path / "results"
    write_results(res, [_result("one item", attach="a1-attachment.txt"), _result("zero items"),
                        _result("other rule", story="API-HEALTH")], commit=repo.head)
    (res / "a1-attachment.txt").write_text("POST /orders {qty: 1}")
    baseline = {"run": {"files": ["tests.test_orders"]},
                "rules": {"API-ORDERS-CREATE": [{"case": "one item", "status": "passed", "test": "t",
                                                  "file": "tests.test_orders", "params": {"qty": "1"},
                                                  "attachments": []}],
                          "API-HEALTH": [{"case": "alive", "status": "passed"}]}}
    (tmp_path / "base.json").write_text(json.dumps(baseline))
    (tmp_path / "prior.md").write_text("## Specs review\nVerdict: CHANGES_REQUESTED\n")
    (tmp_path / "intent.md").write_text("## Acceptance\n- zero items is 422\n")
    (tmp_path / "body.md").write_text("Spec changes:\n- ⚖ zero items 400 → 422\n")
    out = tmp_path / "pack"
    rc = run(repo, res, out, "--baseline", str(tmp_path / "base.json"), "--baseline-commit", "abc1234def",
             "--baseline-scope", "the orders module", "--prior-review", str(tmp_path / "prior.md"),
             "--issue-intent", str(tmp_path / "intent.md"), "--pr-body", str(tmp_path / "body.md"))
    assert rc == 0
    assert "touched rules: 1" in capsys.readouterr().out

    names = {p.name for p in out.iterdir() if p.is_file()}
    assert names == {"touched-rules.json", "touched-rules.txt", "spec-sections.md", "evidence.json",
                     "baseline-evidence.json", "digest.md", "API-ORDERS-CREATE.md", "prior-review.md",
                     "issue-intent.md", "pr-body.md", "manifest.json"}
    assert (out / "touched-rules.txt").read_text() == "API-ORDERS-CREATE\n"

    sections = (out / "spec-sections.md").read_text()
    assert "<!-- specs/endpoints/orders.md § API-ORDERS-CREATE (sources: spec-hunk) -->" in sections
    assert "API-ORDERS-LIMIT" not in sections.split("# Spec diff")[0]
    assert "-| zero items | 0 || 400 |" in sections and "+| zero items | 0 || 422 |" in sections

    ev = json.loads((out / "evidence.json").read_text())
    assert list(ev["rules"]) == ["API-ORDERS-CREATE"]          # scoped to touched rules
    assert {r["case"] for r in ev["rules"]["API-ORDERS-CREATE"]} == RESULT_FILES
    assert list(json.loads((out / "baseline-evidence.json").read_text())["rules"]) == ["API-ORDERS-CREATE"]
    per_rule = json.loads((out / "evidence" / "API-ORDERS-CREATE.json").read_text())
    assert per_rule["rule"] == "API-ORDERS-CREATE"
    assert per_rule["records"] == ev["rules"]["API-ORDERS-CREATE"]   # the same records, one rule per file
    assert sorted(p.name for p in (out / "evidence").iterdir()) == ["API-ORDERS-CREATE.json"]

    digest = (out / "digest.md").read_text()
    assert f"`git.commit={repo.head[:12]}` = this head" in digest
    assert "No `image.digest`: this is PR-head evidence" in digest
    assert "`baseline-evidence.json` at `abc1234def`" in digest and "Scope: the orders module" in digest
    assert "## API-ORDERS-CREATE" in digest and "**Findings:**" in digest

    # the spec join: the rule's md is the spec table annotated
    assert "zero items" in (out / "API-ORDERS-CREATE.md").read_text()
    assert (out / "attachments" / "a1-attachment.txt").read_text() == "POST /orders {qty: 1}"
    assert (out / "tree" / "specs" / "endpoints" / "orders.md").read_text().count("422") == 1
    assert (out / "tree" / "specs" / "glossary.md").is_file()
    assert (out / "prior-review.md").read_text().startswith("## Specs review")
    assert "zero items is 422" in (out / "issue-intent.md").read_text()
    assert "Spec changes:" in (out / "pr-body.md").read_text()
    for f in ("RULES.md", "CONVENTIONS.md", "briefs/rows.md", "briefs/evidence.md", "briefs/finding-contract.md",
              "briefs/author.md"):
        assert (out / "process" / f).is_file(), f
    assert not list((out / "process").rglob("*.py"))

    m = json.loads((out / "manifest.json").read_text())
    assert m["version"] == __version__
    assert m["head"] == repo.head and len(m["base"]) == 40
    assert m["stamp"] == {"git_commit": repo.head, "matches_head": True, "image_digest": None}
    assert m["baseline"] == {"file": "baseline-evidence.json", "commit": "abc1234def", "scope": "the orders module"}
    assert m["counts"]["touched_rules"] == 1 and m["counts"]["records"] == 2
    assert m["counts"]["records_in_run"] == 3 and m["counts"]["attachments"] == 1
    assert m["inputs"] == {"prior_review": True, "issue_intent": True, "pr_body": True}
    assert "manifest.json" not in m["files"] and "digest.md" in m["files"]
    assert m["masked"] is None and not (out / "row-keys.tsv").exists()


def test_mask_descriptions_writes_the_first_pass_surface(repo, tmp_path, capsys):
    # the PR also touches the page's SECOND table (API-ORDERS-LIMIT), so its keys must read r2.*
    page = (repo.root / "specs/endpoints/orders.md").read_text()
    repo.write("specs/endpoints/orders.md", page.replace("| over the limit | 101 || 429 |",
                                                           "| over the limit | 101 || 429 |\n| at the limit | 100 || 201 |"))
    repo.head = repo.commit("pr2")
    res = write_results(tmp_path / "results", [_result("one item"), _result("zero items fall through"),
                                               _result("over the limit", story="API-ORDERS-LIMIT")], commit=repo.head)
    baseline = {"run": {"files": ["tests.test_orders"]},
                "rules": {"API-ORDERS-CREATE": [{"case": "one item", "status": "failed"},
                                                {"case": "zero items", "status": "passed"}]}}
    (tmp_path / "base.json").write_text(json.dumps(baseline))
    out = tmp_path / "pack"
    assert run(repo, res, out, "--mask-descriptions", "--baseline", str(tmp_path / "base.json")) == 0
    assert "masked: 4 + row-keys.tsv" in capsys.readouterr().out

    masked = (out / "spec-sections-masked.md").read_text()
    full = (out / "spec-sections.md").read_text()
    assert "| row | qty || status |" in masked and "| description |" not in masked
    assert "| r1.1 | 1 || 201 |" in masked and "| r1.2 | 0 || 422 |" in masked
    assert "| r2.1 | 101 || 429 |" in masked and "| r2.2 | 100 || 201 |" in masked   # page ordinal, not section ordinal
    for desc in ("one item", "zero items", "over the limit", "at the limit"):
        assert desc not in masked and desc in full
    assert "Creates an order." in masked and "Uses the [quota]" in masked              # prose, headings in view
    assert "# Spec diff" not in masked and "spec diff: not in the masked surface" in masked
    assert "# Spec diff" in full
    assert (out / "row-keys.tsv").read_text() == ("# specs/endpoints/orders.md\n"
                                                  "r1.1\tone item\nr1.2\tzero items\n"
                                                  "r2.1\tover the limit\nr2.2\tat the limit\n")

    # the twins: the same join, every case keyed like its spec row; substring joins read exact
    create = (out / "API-ORDERS-CREATE.masked.md").read_text()
    assert create.startswith("| status | row | qty |")
    assert "| ✓ | r1.1 | 1 |" in create and "| ≠ | r1.2 | 0 ⇢ 1 |" in create
    assert "zero items" not in create and "one item" not in create
    assert "| ≠~ | zero items |" in (out / "API-ORDERS-CREATE.md").read_text()
    limit = (out / "API-ORDERS-LIMIT.masked.md").read_text()
    assert "| ≠ | r2.1 | 101 ⇢ 1 |" in limit and "| ∅ | r2.2 |" in limit and "over the limit" not in limit
    digest = (out / "digest.masked.md").read_text()
    assert "| ✓ | r1.1 |" in digest and "| ✓ | r1.2 |" in digest and "| ✓ | r2.1 |" in digest  # digest = the run's table
    assert "- CELL_MISMATCH API-ORDERS-CREATE r1.2: qty spec 0 ⇢ actual 1" in digest
    assert "- ROW_UNPROVEN API-ORDERS-LIMIT r2.2:" in digest
    assert "- flips:\n  - r1.1: failed → passed" in digest                 # baseline cases keyed too
    assert "zero items" not in digest and "one item" not in digest
    assert "ROW_UNKEYED" not in digest and "ROW_UNKEYED" in (out / "digest.md").read_text()
    assert "**Stamp:**" in digest and "`baseline-evidence.json`" in digest
    # unmasked surfaces keep the descriptions
    assert "one item" in (out / "tree" / "specs" / "endpoints" / "orders.md").read_text()
    assert "one item" in (out / "evidence" / "API-ORDERS-CREATE.json").read_text()

    m = json.loads((out / "manifest.json").read_text())
    assert m["masked"]["files"] == ["API-ORDERS-CREATE.masked.md", "API-ORDERS-LIMIT.masked.md",
                                    "digest.masked.md", "spec-sections-masked.md"]
    assert m["masked"]["keys"] == "row-keys.tsv" and m["masked"]["tree"] == "unmasked"
    assert "tree/" in m["masked"]["unmasked"] and "evidence/" in m["masked"]["unmasked"]
    assert {"spec-sections-masked.md", "row-keys.tsv", "digest.masked.md"} <= set(m["files"])

    # a rerun without the flag clears the masked surface (row-keys.tsv included)
    assert run(repo, res, out, "--no-specs-tree") == 0
    assert not (out / "row-keys.tsv").exists() and not (out / "digest.masked.md").exists()
    assert json.loads((out / "manifest.json").read_text())["masked"] is None


def test_mask_descriptions_on_an_empty_pack(tmp_path):
    repo = base_repo(tmp_path / "repo")
    repo.write("README.md", "changed\n")
    repo.commit()
    out = tmp_path / "pack"
    assert run(repo, write_results(tmp_path / "results", []), out, "--no-specs-tree", "--mask-descriptions") == 0
    assert "no touched rules" in (out / "spec-sections-masked.md").read_text()
    assert (out / "row-keys.tsv").read_text().strip() == ""
    assert "nothing to review" in (out / "digest.masked.md").read_text()
    assert json.loads((out / "manifest.json").read_text())["masked"]["files"] == ["digest.masked.md", "spec-sections-masked.md"]


PRIOR_REVIEW = """## Specs review
Verdict: CHANGES_REQUESTED — R10/tools/statute#RT-STATUTE-PROVISION
Process: allure-behavior-snippets 0.6.7

Prior findings: none (round 1). `pass1.md` is adjudicated below.

### Pass-1 adjudication (revealed descriptions, cells, evidence)
- **P1-1 r18.1/r18.2, RT-STATUTE-PROVISION: survives.** Only the descriptions tell the rows apart ("whole-§ renders (1) once" and "sort: (2) before (10)"). See R10 below.
- **P1-2 r19.3/r19.4: contradicted.** The rows differ in the `paragraph` cell, and the `figures-kas` world prose says § 4 holds an over-cap image.
- **#3 (r71.3–r71.5, `big(...)` notation):** withdrawn. The legend defines `big(...)` as "the over-cap image".
- **P1-4 (CHECKSUM tombstones, check 3):** withdrawn. The quoted carrier rows exist and ran.
1. r20.1/r20.2 (RT-STATUTE-DATE, "Display punctuation") — **survives**.
   - Only the descriptions tell the rows apart: "paren display (1)" against "paren display (2)".
   - r99.9 is quoted here in a continuation line and must not be carried.
- r21.1 A-ONE ("withdrawn application") — survives.
- r22.1 — survives. **withdrawn** (two verdicts: rejected)
- r23.1 (A-TWO) — the cells are "contradicted by the legend" (no verdict position: rejected)

### Findings
**R10/tools/statute#RT-STATUTE-PROVISION**
- Rule/case: RT-STATUTE-PROVISION · "whole-§ renders (1) once"
- Observed: r18.1 and r18.2 carry identical cells ("sort: (2) before (10)" is the hidden condition).

<!-- specs-review head=307418e03dae session=91422913afcf49a2aa1443554304721c -->
"""


def _review(head, items, round1=True):
    """A review body over the fixture page: ``items`` are adjudication lines, ``head`` the trailer."""
    prior = "Prior findings: none (round 1).\n\n" if round1 else "Prior findings:\n- R10/x resolved.\n\n"
    return ("## Specs review\nVerdict: APPROVE — no blocking finding\n\n" + prior +
            "Pass-1 adjudication (revealed descriptions):\n" + "".join(f"- {i}\n" for i in items) +
            "\nFindings: none\n" + (f"\n<!-- specs-review head={head} session=abc -->\n" if head else ""))


def test_prior_rulings_parses_the_adjudication_section_as_keys_only():
    rows = pack.prior_rulings(PRIOR_REVIEW)
    assert [(r["key"], r["ruling"], r["rule"]) for r in rows] == [
        ("r18.1", "survives", "RT-STATUTE-PROVISION"), ("r18.2", "survives", "RT-STATUTE-PROVISION"),
        ("r19.3", "contradicted", ""), ("r19.4", "contradicted", ""),
        ("r71.3", "withdrawn", ""), ("r71.4", "withdrawn", ""), ("r71.5", "withdrawn", ""),   # range expanded
        ("r20.1", "survives", "RT-STATUTE-DATE"), ("r20.2", "survives", "RT-STATUTE-DATE"),
        ("r21.1", "survives", "A-ONE"),           # the quoted "withdrawn" is not a verdict
    ]
    assert {r["round"] for r in rows} == {"1"}                      # "Prior findings: none (round 1)"
    assert not any(r["key"] in ("r99.9", "r22.1", "r23.1", "P1") for r in rows)   # continuation / ambiguous / none
    assert pack.prior_head(PRIOR_REVIEW) == "307418e03dae" and pack.prior_head("no trailer") is None
    later = PRIOR_REVIEW.replace("Prior findings: none (round 1). ", "Prior findings (round 3 review at a7bd9f51):\n- R10 resolved.\n")
    assert {r["round"] for r in pack.prior_rulings(later)} == {"prior"}
    # the inline form (`Pass-1 adjudication (...):`) and the `noted` ruling
    inline = ("Pass-1 adjudication (revealed descriptions):\n- P1-1 r18.1/r18.2, RT-STATUTE-PROVISION — noted, "
              "not a finding (survives as before).\nFindings: none\n- r5.5 — this is a Rows line, not an adjudication\n")
    assert [(r["key"], r["ruling"], r["round"]) for r in pack.prior_rulings(inline)] == [
        ("r18.1", "noted", "prior"), ("r18.2", "noted", "prior")]
    assert pack.prior_rulings(None) == [] and pack.prior_rulings("## Specs review\nFindings: none\n") == []
    assert pack.pass1_prior_tsv(rows[:1]) == "key\truling\tround\trule\nr18.1\tsurvives\t1\tRT-STATUTE-PROVISION\n"


def test_prior_rulings_verdict_position_only():
    one = lambda line: pack.prior_rulings("Pass-1 adjudication:\n" + line + "\n")
    assert [(r["key"], r["ruling"]) for r in one('- r1.1 A-ONE ("withdrawn application") — survives.')] == [("r1.1", "survives")]
    assert one("- r1.1 — survives. **withdrawn**") == []                               # two verdicts: rejected
    assert one("- r1.1 A-ONE — the legend says it is contradicted by the cells") == []  # no verdict position
    assert [r["ruling"] for r in one("- **P1-8 r84.1, ING-RT-BUILD-WINDOWS: contradicted** for check 10.")] == ["contradicted"]
    assert [r["ruling"] for r in one("- PARSE-BODY r50.1/r50.2 — **survives as advisory**.")] == ["survives"] * 2
    assert [r["ruling"] for r in one("- r3.1 'noted thing' — contradicted.")] == ["contradicted"]


def test_prior_rulings_chain_across_three_rounds():
    """Round 2's pass 1 re-lists round 1's keys in the prescribed form; the tsv built from the
    round-2 review still carries both keys with their ORIGINAL ruling and round."""
    r1 = _review("abc1234", ["r1.1, API-ORDERS-CREATE: survives.", "r2.1, API-ORDERS-LIMIT: contradicted."])
    t1 = pack.prior_rulings(r1)
    assert [(r["key"], r["ruling"], r["round"]) for r in t1] == [("r1.1", "survives", "1"), ("r2.1", "contradicted", "1")]
    relisted = [f"{r['key']} ({r['rule']}) — prior: ruled {r['ruling']} round {r['round']}" for r in t1]
    r2 = _review("def5678", relisted + ["r1.3, API-ORDERS-CREATE: withdrawn."], round1=False)
    t2 = pack.prior_rulings(r2)
    assert [(r["key"], r["ruling"], r["round"], r["rule"]) for r in t2] == [
        ("r1.1", "survives", "1", "API-ORDERS-CREATE"), ("r2.1", "contradicted", "1", "API-ORDERS-LIMIT"),
        ("r1.3", "withdrawn", "prior", "API-ORDERS-CREATE")]
    r3 = _review("0123abc", [f"{r['key']} ({r['rule']}) — prior: ruled {r['ruling']} round {r['round']}" for r in t2], round1=False)
    assert [(r["key"], r["ruling"], r["round"]) for r in pack.prior_rulings(r3)] == [
        ("r1.1", "survives", "1"), ("r2.1", "contradicted", "1"), ("r1.3", "withdrawn", "prior")]
    assert [(r["key"], r["ruling"], r["round"]) for r in pack.prior_rulings(
        "Pass-1 adjudication:\n- r1.1 (A-ONE) — (prior: ruled survives round 2)\n")] == [("r1.1", "survives", "2")]
    # a differing verdict on a re-listed line is a re-ruling: the new ruling wins, at this round
    assert [(r["ruling"], r["round"]) for r in pack.prior_rulings(
        "Pass-1 adjudication:\n- r1.1 (A-ONE) — prior: ruled survives round 1 — contradicted.\n")] == [("contradicted", "prior")]


def test_prior_rulings_carry_no_text_from_the_review():
    """The masking guarantee: the file holds keys, rule ids, rulings and a round — never a quote."""
    import re
    tsv = pack.pass1_prior_tsv(pack.prior_rulings(PRIOR_REVIEW))
    quotes = re.findall(r'"([^"]{3,})"|`([^`]{3,})`', PRIOR_REVIEW)
    assert quotes
    for a, b in quotes:
        assert (a or b) not in tsv, (a or b)
    for word in ("descriptions", "legend", "paragraph", "tombstones", "punctuation", "P1-", "#3", "**", "application"):
        assert word not in tsv, word
    for line in tsv.splitlines()[1:]:
        key, ruling, rnd, rule = line.split("\t")
        assert re.fullmatch(r"r\d+(\.\d+)?", key) and ruling in pack.RULINGS
        assert re.fullmatch(r"\d+|prior", rnd) and (rule == "" or re.fullmatch(pack.tr.DEFAULT_ID_REGEX, rule))


FIXTURE_ITEMS = ["r1.1/r1.2, API-ORDERS-CREATE: survives.", "r2.1, API-ORDERS-LIMIT: contradicted.",
                 "r9.9: withdrawn.", "r1.1, API-NOT-A-HEADING: withdrawn."]


def _pack_with_review(repo, tmp_path, review, out="pack"):
    res = write_results(tmp_path / "results", [_result("one item"), _result("zero items")], commit=repo.head)
    (tmp_path / "review.md").write_text(review, encoding="utf-8")
    out = tmp_path / out
    assert run(repo, res, out, "--no-specs-tree", "--mask-descriptions", "--prior-review", str(tmp_path / "review.md")) == 0
    return out, json.loads((out / "manifest.json").read_text())


def test_mask_descriptions_with_a_prior_review_writes_pass1_prior(repo, tmp_path):
    out, m = _pack_with_review(repo, tmp_path, _review(repo.head[:12], FIXTURE_ITEMS))
    assert (out / "pass1-prior.tsv").read_text() == ("key\truling\tround\trule\n"
                                                      "r1.1\tsurvives\t1\tAPI-ORDERS-CREATE\n"
                                                      "r1.2\tsurvives\t1\tAPI-ORDERS-CREATE\n"
                                                      "r2.1\tcontradicted\t1\tAPI-ORDERS-LIMIT\n")
    # r9.9 (no rule: ambiguous across pages) and the fenced non-heading rule are dropped
    assert m["masked"]["prior"] == {"file": "pass1-prior.tsv", "head": repo.head, "carried": 3, "dropped": 2, "reason": None}
    assert "pass1-prior.tsv" in m["masked"]["files"] and "pass1-prior.tsv" in m["files"] and m["inputs"]["prior_review"] is True
    assert (out / "prior-review.md").read_text().startswith("## Specs review")   # pass 2 still gets the review itself
    # no prior review → no file, no entry
    res = tmp_path / "results"
    assert run(repo, res, out, "--no-specs-tree", "--mask-descriptions") == 0
    m = json.loads((out / "manifest.json").read_text())
    assert not (out / "pass1-prior.tsv").exists() and "pass1-prior.tsv" not in m["masked"]["files"]
    assert m["masked"]["prior"] is None and "pass1-prior.tsv" not in m["files"]
    # a prior review without the section → no file, the manifest says so
    out, m = _pack_with_review(repo, tmp_path, "## Specs review\nVerdict: APPROVE\nFindings: none\n")
    assert not (out / "pass1-prior.tsv").exists() and "pass1-prior.tsv" not in m["masked"]["files"]
    assert m["masked"]["prior"]["file"] is None and "no pass-1 adjudication" in m["masked"]["prior"]["reason"]
    # without --mask-descriptions there is no pass 1, so no pass-1 surface
    assert run(repo, res, out, "--no-specs-tree", "--prior-review", str(tmp_path / "review.md")) == 0
    assert not (out / "pass1-prior.tsv").exists() and json.loads((out / "manifest.json").read_text())["masked"] is None


def test_pass1_prior_fails_closed_without_a_resolvable_prior_head(repo, tmp_path):
    out, m = _pack_with_review(repo, tmp_path, _review(None, FIXTURE_ITEMS))
    assert not (out / "pass1-prior.tsv").exists() and "pass1-prior.tsv" not in m["masked"]["files"]
    assert m["masked"]["prior"]["file"] is None and "trailer" in m["masked"]["prior"]["reason"]
    assert m["masked"]["prior"]["dropped"] == 5
    out, m = _pack_with_review(repo, tmp_path, _review("deadbeef0000", FIXTURE_ITEMS))
    assert not (out / "pass1-prior.tsv").exists()
    assert "deadbeef0000 is not in the repo" in m["masked"]["prior"]["reason"]


def test_pass1_prior_drops_keys_whose_row_may_have_moved(repo, tmp_path):
    prior_head = repo.head
    page = (repo.root / "specs/endpoints/orders.md").read_text()
    # a row inserted before r1.1: the key now names the new row — every key of the changed
    # rule's section is dropped; the untouched rule's key is carried
    repo.write("specs/endpoints/orders.md", page.replace("| one item | 1 || 201 |", "| nothing | 0 || 400 |\n| one item | 1 || 201 |"))
    repo.head = repo.commit("insert")
    out, m = _pack_with_review(repo, tmp_path, _review(prior_head[:12], FIXTURE_ITEMS))
    assert (out / "pass1-prior.tsv").read_text() == "key\truling\tround\trule\nr2.1\tcontradicted\t1\tAPI-ORDERS-LIMIT\n"
    assert m["masked"]["prior"]["carried"] == 1 and m["masked"]["prior"]["dropped"] == 4
    # a table added EARLIER on the page renumbers r2.1 (keys count over the whole page): dropped
    # although API-ORDERS-LIMIT's own section is unchanged
    repo.write("specs/endpoints/orders.md", page.replace("## API-ORDERS-LIMIT", "| description | qty || status |\n|---|---|---|\n| extra | 2 || 201 |\n\n## API-ORDERS-LIMIT"))
    repo.head = repo.commit("table")
    out, m = _pack_with_review(repo, tmp_path, _review(prior_head[:12], FIXTURE_ITEMS), out="pack2")
    assert not (out / "pass1-prior.tsv").exists() and "pass1-prior.tsv" not in m["masked"]["files"]
    assert m["masked"]["prior"]["carried"] == 0 and "dropped" in m["masked"]["prior"]["reason"]
    # the same page at the same head: everything named carries
    out, m = _pack_with_review(repo, tmp_path, _review(repo.head, FIXTURE_ITEMS), out="pack3")
    assert m["masked"]["prior"]["carried"] == 3


def test_no_touched_rule_writes_an_empty_pack(tmp_path):
    repo = base_repo(tmp_path / "repo")
    repo.write("README.md", "changed\n")
    repo.commit()
    res = write_results(tmp_path / "results", [])
    out = tmp_path / "pack"
    assert run(repo, res, out, "--no-specs-tree") == 0
    assert (out / "touched-rules.txt").read_text() == ""
    assert json.loads((out / "touched-rules.json").read_text()) == []
    assert json.loads((out / "evidence.json").read_text()) == {"run": {}, "rules": {}}
    assert "nothing to review" in (out / "digest.md").read_text()
    assert "previous review: none" in (out / "prior-review.md").read_text()
    assert "not provided" in (out / "issue-intent.md").read_text()
    assert not (out / "tree").exists() and (out / "process" / "RULES.md").is_file()
    m = json.loads((out / "manifest.json").read_text())
    assert m["counts"]["touched_rules"] == 0 and m["baseline"] is None


def test_stale_and_artifact_stamp(repo, tmp_path):
    res = write_results(tmp_path / "results", [_result("one item")], commit="0" * 40, digest="sha256:abc")
    out = tmp_path / "pack"
    assert run(repo, res, out) == 0
    digest = (out / "digest.md").read_text()
    assert "stale; every row is unproven at this head (E-STALE)" in digest
    assert "Artifact: `image.digest=sha256:abc`" in digest
    assert "**Baseline:** none" in digest
    m = json.loads((out / "manifest.json").read_text())
    assert m["stamp"]["matches_head"] is False and m["stamp"]["image_digest"] == "sha256:abc"


def test_unstamped_run(repo, tmp_path):
    out = tmp_path / "pack"
    assert run(repo, write_results(tmp_path / "results", [_result("one item")]), out) == 0
    assert "names no `git.commit`" in (out / "digest.md").read_text()


def test_rerun_replaces_a_previous_pack(repo, tmp_path):
    res = write_results(tmp_path / "results", [_result("one item")], commit=repo.head)
    out = tmp_path / "pack"
    assert run(repo, res, out) == 0
    (out / "stale-rule.md").write_text("old")
    assert run(repo, res, out, "--no-specs-tree") == 0
    assert not (out / "stale-rule.md").exists() and not (out / "tree").exists()


def test_refuses_a_non_pack_dir_and_bad_inputs(repo, tmp_path, capsys):
    res = write_results(tmp_path / "results", [], commit=repo.head)
    precious = tmp_path / "precious"
    precious.mkdir()
    (precious / "notes.md").write_text("keep me")
    assert run(repo, res, precious) == 64
    assert (precious / "notes.md").read_text() == "keep me"
    assert run(repo, tmp_path / "missing", tmp_path / "p2") == 64
    assert run(repo, res, tmp_path / "p3", "--baseline-scope", "x") == 64
    assert run(repo, res, tmp_path / "p4", "--prior-review", str(tmp_path / "nope.md")) == 64
    assert pack.cli(["no-such-ref", "HEAD", str(res), "--repo", str(repo.root), "--out", str(tmp_path / "p5")]) == 64
    assert "evidence-pack:" in capsys.readouterr().err


def test_process_path(capsys):
    with pytest.raises(SystemExit) as exc:
        pack.process_path_main()
    assert exc.value.code == 0
    p = Path(capsys.readouterr().out.strip())
    assert (p / "RULES.md").is_file() and (p / "briefs" / "rows.md").is_file()
