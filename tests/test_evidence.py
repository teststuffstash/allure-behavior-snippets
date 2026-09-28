import json

import pytest

from allure_behavior_snippets import evidence

RULE = "ING-RT-BUILD-CORPUS"


def _result(name, full, status, story=RULE, params=None, attachments=None, steps=None,
            message=None, labels=None):
    d = {
        "name": name,
        "fullName": full,
        "status": status,
        "labels": [{"name": "epic", "value": "e"}, {"name": "feature", "value": "f"}]
                  + ([{"name": "story", "value": story}] if story else [])
                  + (labels or []),
        "uuid": name,
        "historyId": "h" + name,
    }
    if params is not None:
        d["parameters"] = [{"name": k, "value": v} for k, v in params.items()]
    if attachments:
        d["attachments"] = [{"name": a, "source": a + ".txt", "type": "text/plain"} for a in attachments]
    if steps:
        d["steps"] = steps
    if message:
        d["statusDetails"] = {"message": message, "trace": "tb"}
    return d


@pytest.fixture()
def results_dir(tmp_path):
    d = tmp_path / "allure-results"
    d.mkdir()
    rows = [
        _result("test_build[two entries → newest wins]", "tests.test_build#test_build", "passed",
                params={"intent": "two entries → newest wins", "expect": "{'base': '2026-09-01'}"},
                attachments=["corpus.sqlite"],
                steps=[{"name": "open", "status": "passed",
                        "attachments": [{"name": "world: rks-open  (sha256:abc)", "source": "x"}]}]),
        _result("test_bare", "tests.test_build#test_bare", "passed"),
        _result("test_build[pipe|case]", "tests.test_build#test_build", "failed",
                params={"intent": "pipe|case", "act": "amended"},
                message="AssertionError: boom\nsecond line"),
        _result("test_unlabelled", "tests.test_misc#test_unlabelled", "passed", story=None),
        # was labelled in the baseline, ran at HEAD with no story → UNLABELLED, not VANISHED
        _result("test_lost_label", "tests.test_build#test_lost_label", "passed", story=None),
        # same rule from a second module; ``unused`` is empty everywhere → column dropped
        _result("test_delta[zeta]", "tests.test_delta#test_delta", "passed",
                params={"desc": "z" * 100, "unused": ""}),
    ]
    for i, r in enumerate(rows):
        (d / f"{i}-result.json").write_text(json.dumps(r), encoding="utf-8")
    (d / "environment.properties").write_text("corpus=c68134b\nrunner=ci\n", encoding="utf-8")
    return d


def test_records_extracted(results_dir):
    ev = evidence.build_evidence(evidence.load_results([results_dir]),
                                 evidence.load_environment([results_dir]), generated="2026-09-28")
    assert set(ev["rules"]) == {RULE}, "unlabelled row must be skipped"
    assert ev["run"] == {"corpus": "c68134b", "runner": "ci", "generated": "2026-09-28",
                         "files": ["tests.test_build", "tests.test_delta", "tests.test_misc"],
                         "unlabelled": ["tests.test_build#test_lost_label",
                                        "tests.test_misc#test_unlabelled"]}
    recs = ev["rules"][RULE]
    assert [r["case"] for r in recs] == ["bare", "pipe|case", "two entries → newest wins", "zeta"]
    good = recs[2]
    assert good["params"] == {"intent": "two entries → newest wins", "expect": "{'base': '2026-09-01'}"}
    assert good["attachments"] == ["corpus.sqlite", "world: rks-open  (sha256:abc)"]
    assert good["attachment_files"] == {"corpus.sqlite": "corpus.sqlite.txt",
                                        "world: rks-open  (sha256:abc)": "x"}
    assert good["world"] == "rks-open"
    assert good["steps"] == ["open"]
    assert good["file"] == "tests.test_build"
    assert good["failure"] is None
    assert recs[1]["failure"] == "AssertionError: boom"
    assert recs[0]["params"] == {} and recs[0]["attachments"] == []


def test_markdown_columns(results_dir, tmp_path):
    ev = evidence.build_evidence(evidence.load_results([results_dir]), generated="2026-09-28")
    out = tmp_path / "out"
    evidence.write_outputs(ev, out)
    lines = (out / f"{RULE}.md").read_text(encoding="utf-8").splitlines()
    # status, case, world, params first-seen; ``unused`` (empty everywhere) is dropped
    assert lines[0] == "| status | case | world | intent | act | expect | desc | attachments | failure |"
    assert lines[2].startswith("| ✓ | bare |")
    assert "| ❌ | pipe\\|case | " in lines[3] and "AssertionError: boom" in lines[3]
    assert "z" * 79 + "…" in lines[5], "per-rule fragment keeps the 80-char cell cap"
    assert lines[-1] == "_run: 2026-09-28_", "run.files/unlabelled never leak into the footer"
    assert json.loads((out / "evidence.json").read_text())["rules"][RULE][0]["case"] == "bare"


def test_digest_predicates_and_delta(results_dir, tmp_path):
    ev = evidence.build_evidence(evidence.load_results([results_dir]), generated="2026-09-28")
    def old(case, test, **kw):
        d = {"case": case, "status": "passed", "test": test, "file": test.split("#")[0],
             "params": {"p": 1}, "attachments": []}
        d.update(kw)
        return d
    baseline = {"run": {}, "rules": {RULE: [
        old("bare", "tests.test_build#test_bare", params={}),               # bare then too
        old("pipe|case", "tests.test_build#test_build"),
        old("gone", "tests.test_build#test_gone"),                          # not in run
        old("lost_label", "tests.test_build#test_lost_label"),              # ran, no story
        old("elsewhere", "tests.test_other#test_elsewhere"),                # module not run
    ]}}
    out = tmp_path / "out"
    evidence.write_outputs(ev, out, rules=[RULE, "ING-RT-NOPE"], baseline=baseline)
    text = (out / "digest.md").read_text(encoding="utf-8")
    assert text.startswith(f"## {RULE}\n")
    assert "## ING-RT-NOPE\n\n_no evidence rows for this rule_" in text
    assert f"- NO_EVIDENCE ING-RT-NOPE" in text
    assert f"- BARE_ROW (pre-existing) {RULE} bare:" in text
    assert f"- BARE_ROW {RULE} bare:" not in text
    assert f"- FAILED {RULE} pipe|case: status=failed — AssertionError: boom" in text
    assert f"- VANISHED {RULE} gone:" in text
    assert f"- UNLABELLED {RULE} lost_label: ran at HEAD without a rule label" in text
    assert "VANISHED" not in text.split("gone:")[1], "out-of-scope + unlabelled never VANISH"
    assert "- added: two entries → newest wins, zeta" in text
    assert ("- removed: elsewhere, gone, lost_label\n"
            "  - out-of-scope (file not run): elsewhere\n"
            "  - unlabelled (ran, no rule): lost_label\n"
            "  - gone (not in run): gone\n") in text
    assert "  - pipe|case: passed → failed" in text
    assert "- none" not in text
    # digest tables: one per module, full cells, no row elision
    assert "### tests.test_build\n\n| status | case | world | intent | act | expect | attachments | failure |" in text
    assert "### tests.test_delta\n\n| status | case | desc | attachments |\n" in text
    assert "z" * 100 in text and "…" not in text


def test_pre_existing_bare_rows_listed_after_new_ones():
    rec = lambda c: {"case": c, "world": None, "status": "passed", "params": {}, "attachments": [],
                     "steps": [], "failure": None, "test": f"t#test_{c}", "file": "t"}
    ev = {"run": {"generated": "x", "files": ["t"], "unlabelled": []},
          "rules": {"R": [rec("a_old"), rec("b_new")]}}
    baseline = {"run": {}, "rules": {"R": [
        {"case": "a_old", "status": "passed", "params": {}, "attachments": [], "test": "t#test_a_old", "file": "t"},
        {"case": "b_new", "status": "passed", "params": {"p": 1}, "attachments": [], "test": "t#test_b_new", "file": "t"},
    ]}}
    assert [l.split(" R ")[0] for l in evidence.findings("R", ev, baseline)] == [
        "- BARE_ROW", "- BARE_ROW (pre-existing)"]
    assert evidence.findings("R", ev)[0].startswith("- BARE_ROW R a_old"), "no baseline → plain"


def test_digest_shows_every_row_wide_cells():
    recs = [{"case": f"c{i:02d}", "world": None, "status": "passed", "params": {"p": "x" * 300},
             "attachments": [], "steps": [], "failure": None, "test": "t", "file": "t"}
            for i in range(15)]
    lines = evidence.render_digest_tables(recs, {"generated": "d"})
    assert sum(1 for l in lines if l.startswith("| ")) == 16  # header + all 15 rows
    assert not any("more rows" in l for l in lines)
    assert "x" * 300 in lines[2]
    assert evidence.cell("y" * 500, 400).endswith("…") and len(evidence.cell("y" * 500, 400)) == 400


def test_case_unescapes_pytest_ids():
    assert evidence.case_of("test_x[Q1 audit \\u2014 A]") == "Q1 audit — A"
    assert evidence.case_of("test_plain") == "plain"


def test_no_findings_is_none(tmp_path):
    ev = {"run": {"generated": "x"}, "rules": {"R": [
        {"case": "a", "world": None, "status": "passed", "params": {"p": 1}, "attachments": [],
         "steps": [], "failure": None, "test": "t#a", "file": "t"}]}}
    lines = evidence.render_digest(["R"], ev)
    assert lines[-2] == "- none"


def test_param_columns_drop_all_empty():
    recs = [{"params": {"b": "", "a": 1, "c": None}}, {"params": {"c": "", "a": None, "d": 0}}]
    assert evidence.param_columns(recs) == ["a", "d"]


def test_case_of_full():
    assert evidence.case_of_full("tests.test_build#test_bare") == "bare"
    assert evidence.case_of_full("tests.test_x#TestK.test_bare") == "bare"
    assert evidence.case_of_full("tests.test_x#test_p[a b]") == "a b"


def test_overflow_line():
    recs = [{"case": f"c{i:02d}", "world": None, "status": "passed" if i % 2 else "failed",
             "params": {}, "attachments": [], "steps": [], "failure": "f", "test": "t", "file": "t"}
            for i in range(15)]
    lines = evidence.render_table(recs, {"generated": "d"})
    assert lines[-3] == "_… 3 more rows (1 passed, 2 failed)_"
    assert sum(1 for l in lines if l.startswith("| ")) == 13  # header + 12 rows
