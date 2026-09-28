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
    ]
    for i, r in enumerate(rows):
        (d / f"{i}-result.json").write_text(json.dumps(r), encoding="utf-8")
    (d / "environment.properties").write_text("corpus=c68134b\nrunner=ci\n", encoding="utf-8")
    return d


def test_records_extracted(results_dir):
    ev = evidence.build_evidence(evidence.load_results([results_dir]),
                                 evidence.load_environment([results_dir]), generated="2026-09-28")
    assert set(ev["rules"]) == {RULE}, "unlabelled row must be skipped"
    assert ev["run"] == {"corpus": "c68134b", "runner": "ci", "generated": "2026-09-28"}
    recs = ev["rules"][RULE]
    assert [r["case"] for r in recs] == ["bare", "pipe|case", "two entries → newest wins"]
    good = recs[2]
    assert good["params"] == {"intent": "two entries → newest wins", "expect": "{'base': '2026-09-01'}"}
    assert good["attachments"] == ["corpus.sqlite", "world: rks-open  (sha256:abc)"]
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
    assert lines[0] == "| status | case | world | intent | act | expect | attachments | failure |"
    assert lines[2].startswith("| ✓ | bare |")
    assert "| ❌ | pipe\\|case | " in lines[3] and "AssertionError: boom" in lines[3]
    assert lines[-1] == "_run: 2026-09-28_"
    assert json.loads((out / "evidence.json").read_text())["rules"][RULE][0]["case"] == "bare"


def test_digest_predicates_and_delta(results_dir, tmp_path):
    ev = evidence.build_evidence(evidence.load_results([results_dir]), generated="2026-09-28")
    baseline = {"run": {}, "rules": {RULE: [
        {"case": "bare", "status": "passed"},
        {"case": "pipe|case", "status": "passed"},
        {"case": "gone", "status": "passed"},
    ]}}
    out = tmp_path / "out"
    evidence.write_outputs(ev, out, rules=[RULE, "ING-RT-NOPE"], baseline=baseline)
    text = (out / "digest.md").read_text(encoding="utf-8")
    assert text.startswith(f"## {RULE}\n")
    assert "## ING-RT-NOPE\n\n_no evidence rows for this rule_" in text
    assert f"- NO_EVIDENCE ING-RT-NOPE" in text
    assert f"- BARE_ROW {RULE} bare:" in text
    assert f"- FAILED {RULE} pipe|case: status=failed — AssertionError: boom" in text
    assert f"- VANISHED {RULE} gone:" in text
    assert "- added: two entries → newest wins" in text
    assert "- removed: gone" in text
    assert "  - pipe|case: passed → failed" in text
    assert "- none" not in text


def test_case_unescapes_pytest_ids():
    assert evidence.case_of("test_x[Q1 audit \\u2014 A]") == "Q1 audit — A"
    assert evidence.case_of("test_plain") == "plain"


def test_no_findings_is_none(tmp_path):
    ev = {"run": {"generated": "x"}, "rules": {"R": [
        {"case": "a", "world": None, "status": "passed", "params": {"p": 1}, "attachments": [],
         "steps": [], "failure": None, "test": "t#a", "file": "t"}]}}
    lines = evidence.render_digest(["R"], ev)
    assert lines[-2] == "- none"


def test_overflow_line():
    recs = [{"case": f"c{i:02d}", "world": None, "status": "passed" if i % 2 else "failed",
             "params": {}, "attachments": [], "steps": [], "failure": "f", "test": "t", "file": "t"}
            for i in range(15)]
    lines = evidence.render_table(recs, {"generated": "d"})
    assert lines[-3] == "_… 3 more rows (1 passed, 2 failed)_"
    assert sum(1 for l in lines if l.startswith("| ")) == 13  # header + 12 rows
