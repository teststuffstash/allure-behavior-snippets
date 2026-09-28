import json

import pytest

from allure_behavior_snippets import evidence

RULE = "ING-RT-BUILD-CORPUS"
HYG = "ING-RT-HYGIENE"
THR = "ING-RT-THREAD"


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
        # REPORT-HYGIENE: one record per code + one clean record (own rule, own module)
        _result("test_h[clean]", "tests.test_hyg#test_h", "passed", story=HYG,
                params={"n": 1}, attachments=["sizes"],
                steps=[{"name": "open", "steps": [{"name": "Verdict: ok"}]}]),
        _result("test_h[flat]", "tests.test_hyg#test_h", "passed", story=HYG, params={"n": 1}),
        _result("test_h[noisy]", "tests.test_hyg#test_h", "passed", story=HYG, params={"n": 9},
                steps=[{"name": f"s{i}"} for i in range(9)]),
        _result("test_h[bulk]", "tests.test_hyg#test_h", "passed", story=HYG, params={"n": 9},
                attachments=[f"a{i}" for i in range(9)], steps=[{"name": "open"}]),
        _result("test_h[blob]", "tests.test_hyg#test_h", "passed", story=HYG,
                params={"payload": "b" * 500}, steps=[{"name": "open"}]),
        _result("test_h[blank]", "tests.test_hyg#test_h", "passed", story=HYG, params={"n": 1},
                attachments=["Attachment 3"],
                steps=[{"name": "open", "steps": [{"name": "verdict"}]}]),
        # thread: (a) ``sha`` threads all three phases (name in given, value in when,
        # key in the verdict JSON file); ``rc`` by name only (value "0" too short)
        _result("test_t[threaded]", "tests.test_thr#test_t", "passed", story=THR,
                params={"sha": "'cafef00d'", "rc": 0},
                steps=[{"name": "Given: a world with one sha and rc", "status": "passed"},
                       {"name": "ert-build rc=0 → corpus/cafef00d/corpus.sqlite",
                        "attachments": [{"name": "ert-build events", "source": "ev.txt"}]},
                       {"name": "verdict: corpus_meta carries the row",
                        "attachments": [{"name": "verdict: corpus_meta carries the row",
                                         "source": "verdict-threaded.json"}]}]),
        # (b) ``door`` appears nowhere → THREAD_BROKEN
        _result("test_t[nowhere]", "tests.test_thr#test_t", "passed", story=THR,
                params={"door": "'Dockerfile'"},
                steps=[{"name": "open"}, {"name": "Then: fragments present"}]),
        # (c) no steps and no params → nothing to thread, never THREAD_BROKEN
        _result("test_t[empty]", "tests.test_thr#test_t", "passed", story=THR, params={}),
    ]
    for i, r in enumerate(rows):
        (d / f"{i}-result.json").write_text(json.dumps(r), encoding="utf-8")
    (d / "environment.properties").write_text("corpus=c68134b\nrunner=ci\n", encoding="utf-8")
    (d / "sizes.txt").write_bytes(b"s" * 1234)   # the clean record's attachment file
    (d / "verdict-threaded.json").write_text(
        json.dumps({"rc": {"expected": 0, "actual": 0}, "sha": {"expected": "cafef00d"}}), encoding="utf-8")
    return d


def test_records_extracted(results_dir):
    ev = evidence.build_evidence(evidence.load_results([results_dir]),
                                 evidence.load_environment([results_dir]), generated="2026-09-28")
    assert set(ev["rules"]) == {RULE, HYG, THR}, "unlabelled row must be skipped"
    assert ev["run"] == {"corpus": "c68134b", "runner": "ci", "generated": "2026-09-28",
                         "files": ["tests.test_build", "tests.test_delta", "tests.test_hyg",
                                   "tests.test_misc", "tests.test_thr"],
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
    ], "ING-RT-SPLIT-FROM": [old("bare", "tests.test_build#test_bare")]}}   # bare now under RULE
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
            "  - relabelled (now under another rule): none\n"
            "  - out-of-scope (file not run): elsewhere\n"
            "  - unlabelled (ran, no rule): lost_label\n"
            "  - gone (not in run): gone\n") in text
    assert "  - pipe|case: passed → failed" in text
    assert "**Findings:**\n\n- none" not in text
    # a case that moved rule (spec split): classified, never VANISHED, no finding
    split = evidence.render_digest(["ING-RT-SPLIT-FROM"], ev, baseline)
    assert "  - relabelled (now under ING-RT-BUILD-CORPUS): bare" in split
    assert not any("VANISHED" in l or "UNLABELLED" in l for l in split)
    assert evidence.classify_removed("ING-RT-SPLIT-FROM", ev, baseline, ["bare"]) == {
        "relabelled": [("bare", RULE)], "out-of-scope": [], "unlabelled": [], "gone": []}
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
    assert lines[-8:] == ["- none", "", "**Hygiene:**", "", "cases 1 · attachments 0 · bytes 0 · max depth 0", "", "- none", ""]


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


def test_hygiene_metrics_and_block(results_dir, tmp_path):
    ev = evidence.build_evidence(evidence.load_results([results_dir]), generated="2026-09-28",
                                 results_dirs=[results_dir])
    by_case = {r["case"]: r for r in ev["rules"][HYG]}
    assert by_case["clean"]["hygiene"] == {
        "steps_top": 1, "steps_total": 2, "steps_depth": 2, "attachments_total": 1,
        "attachment_bytes": 1234, "param_max_len": 1, "verdict_step": True, "blank_names": []}
    assert by_case["bulk"]["hygiene"]["attachment_bytes"] == 0, "missing files count 0"
    assert by_case["blank"]["hygiene"] == {
        "steps_top": 1, "steps_total": 2, "steps_depth": 2, "attachments_total": 1,
        "attachment_bytes": 0, "param_max_len": 1, "verdict_step": True,
        "blank_names": ["Attachment 3", "verdict"]}
    assert by_case["flat"]["hygiene"]["steps_total"] == 0
    block = evidence.hygiene_lines(HYG, ev)
    assert block == [
        "cases 6 · attachments 11 · bytes 1234 · max depth 2",
        "",
        f"- STEP_FLAT {HYG} flat: steps_total=0 (threshold > 0)",
        f"- STEP_NOISE {HYG} noisy: steps_top=9 (threshold 8)",
        f"- ATTACH_BULK {HYG} bulk: attachments_total=9 (threshold 8)",
        f"- PARAM_BLOB {HYG} blob: param_max_len=500 (threshold 400)",
        f"- NAME_BLANK {HYG} blank: blank_names=`Attachment 3`, `verdict` (threshold 0)",
    ] + [f"- THREAD_BROKEN {HYG} {c}: {p} in no given/when/then step"
         for c, p in [("blank", "n"), ("blob", "payload"), ("bulk", "n"), ("clean", "n"),
                      ("flat", "n"), ("noisy", "n")]]
    assert not any("clean" in l for l in block[:-6])
    # bytes threshold fires on its own; a bare record (no params/attachments) is never STEP_FLAT
    big = dict(by_case["clean"], case="big", thread_broken=[],
               hygiene=dict(by_case["clean"]["hygiene"], attachment_bytes=262145))
    bare = dict(by_case["flat"], case="bare0", params={}, attachments=[], thread_broken=[])
    ev2 = {"run": {}, "rules": {"X": [big, bare]}}
    assert evidence.hygiene_lines("X", ev2)[2:] == ["- ATTACH_BULK X big: attachment_bytes=262145 (threshold 262144)"]
    # digest: block sits after Findings, hygiene lines never appear among findings
    out = tmp_path / "out"
    evidence.write_outputs(ev, out, rules=[HYG])
    text = (out / "digest.md").read_text(encoding="utf-8")
    findings_part, hyg_part = text.split("**Hygiene:**")
    assert "STEP_FLAT" not in findings_part and "- none" in findings_part
    assert "- STEP_FLAT" in hyg_part and "- NAME_BLANK" in hyg_part


def test_is_blank_name():
    assert all(evidence.is_blank_name(n) for n in ["verdict", "Events", "ATTACHMENT", "step", "attachment 12"])
    assert not any(evidence.is_blank_name(n) for n in ["verdict: ok", "attachment x", "open", "steps"])


def test_thread_phases_bolding_and_summary(results_dir, tmp_path):
    ev = evidence.build_evidence(evidence.load_results([results_dir]), generated="2026-09-28",
                                 results_dirs=[results_dir])
    by_case = {r["case"]: r for r in ev["rules"][THR]}
    good, none, empty = by_case["threaded"], by_case["nowhere"], by_case["empty"]
    assert good["phases"] == {"given": ["Given: a world with one sha and rc"],
                              "when": ["ert-build rc=0 → corpus/cafef00d/corpus.sqlite"],
                              "then": ["verdict: corpus_meta carries the row"], "other": []}
    assert good["thread"] == {"sha": {"given": True, "when": True, "then": True},
                              "rc": {"given": True, "when": True, "then": True}}
    assert good["thread_broken"] == []
    assert none["phases"] == {"given": [], "when": [], "then": ["Then: fragments present"], "other": ["open"]}
    assert none["thread"] == {"door": {"given": False, "when": False, "then": False}}
    assert none["thread_broken"] == ["door"]
    assert empty["phases"] == {"given": [], "when": [], "then": [], "other": []}
    assert empty["thread"] == {} and empty["thread_broken"] == []
    # hygiene: THREAD_BROKEN only for (b), placed after NAME_BLANK
    block = evidence.hygiene_lines(THR, ev)
    assert block[2:] == [f"- THREAD_BROKEN {THR} nowhere: door in no given/when/then step"]
    # colouring: the fully threaded cell is bold in the fragment and the digest, others plain
    out = tmp_path / "out"
    evidence.write_outputs(ev, out, rules=[THR])
    frag = (out / f"{THR}.md").read_text(encoding="utf-8").splitlines()
    assert frag[0] == "| status | case | door | sha | rc | attachments |"
    assert "| **'cafef00d'** | **0** |" in "\n".join(frag)
    assert "| 'Dockerfile' |" in "\n".join(frag)
    digest = (out / "digest.md").read_text(encoding="utf-8")
    assert "| **'cafef00d'** | **0** |" in digest and "**'Dockerfile'**" not in digest
    assert "|\n\nthreads: 3 cases · 1 fully threaded · broken: door(1)\n" in digest
    assert digest.index("threads: 3 cases") < digest.index("_run:")
    # multi-module digest: one summary per table; none broken → "none"
    two = [dict(good, file="a"), dict(good, file="b", case="t2")]
    lines = evidence.render_digest_tables(two, {"generated": "d"})
    assert lines.count("threads: 1 cases · 1 fully threaded · broken: none") == 2
    assert evidence.thread_summary([none] * 7 + [empty]) == "threads: 8 cases · 0 fully threaded · broken: door(7)"


def test_phase_of_and_thread_value():
    assert [evidence.phase_of(n) for n in
            ["Given: x", "ARRANGE", "seed world", "world: rks", "When x", "act", "ert-delta rc=0",
             "call search", "request /mcp", "a → b", "then: a → b", "Verdict: ok", "open", ""]] == [
        "given", "given", "given", "given", "when", "when", "when", "when", "when", "when",
        "then", "then", "other", "other"]
    assert evidence._thread_value("'C'") is None and evidence._thread_value("'null'") == "null"
    assert evidence._thread_value(0) is None and evidence._thread_value("abc") == "abc"
    assert evidence._thread_value(None) is None
    # top-5 cap and count-then-name ordering
    recs = [{"thread_broken": list("abcdef")}] + [{"thread_broken": ["f"]}] * 2
    assert evidence.thread_summary(recs).endswith("broken: f(3), a(1), b(1), c(1), d(1)")
