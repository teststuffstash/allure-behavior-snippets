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
    ] + [f"- STEP_NOISE {HYG} {c}: steps outside given/when/then: `open` (threshold 0)"
         for c in ("blank", "blob", "bulk", "clean")] + [
        f"- STEP_NOISE {HYG} noisy: steps_top=9 (threshold 8), steps outside given/when/then: "
        + ", ".join(f"`s{i}`" for i in range(9)) + " (threshold 0)",
    ] + [f"- UNIT_ONLY_CANDIDATE {HYG} {c}: steps but no `when` step (threshold ≥ 1)"
         for c in ("blank", "blob", "bulk", "clean", "noisy")] + [
        f"- ATTACH_BULK {HYG} bulk: attachments_total=9 (threshold 8)",
        f"- PARAM_BLOB {HYG} blob: param_max_len=500 (threshold 400)",
        f"- NAME_BLANK {HYG} blank: blank_names=`Attachment 3`, `verdict` (threshold 0)",
    ] + [f"- THREAD_BROKEN {HYG} {c}: {p} in no given/when/then step"
         for c, p in [("blank", "n"), ("blob", "payload"), ("bulk", "n"), ("clean", "n"),
                      ("flat", "n"), ("noisy", "n")]]
    # "clean" is clean on every threshold code: only the phase codes name it (its one
    # top-level step `open` is neither given/when/then, so it is STEP_NOISE + UNIT_ONLY_CANDIDATE)
    assert [l for l in block if "clean" in l and not l.startswith(("- STEP_NOISE", "- UNIT_ONLY", "- THREAD"))] == []
    # a step-less case is STEP_FLAT, never also UNIT_ONLY_CANDIDATE
    assert not any("UNIT_ONLY_CANDIDATE" in l and " flat:" in l for l in block)
    # bytes threshold fires on its own; a bare record (no params/attachments) is never STEP_FLAT
    big = dict(by_case["clean"], case="big", thread_broken=[],
               phases={"given": [], "when": ["when: x"], "then": [], "other": []},
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
    assert block[2:] == [
        f"- STEP_NOISE {THR} nowhere: steps outside given/when/then: `open` (threshold 0)",
        f"- UNIT_ONLY_CANDIDATE {THR} nowhere: steps but no `when` step (threshold ≥ 1)",
        f"- THREAD_BROKEN {THR} nowhere: door in no given/when/then step"]
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


# ---------------------------------------------------------------- spec join (--spec)

SPEC_PAGE = """# page

### OTHER-RULE

| description | x |
|---|---|
| other row | `1` |

### ING-RT-JOIN ⚖ heading may carry a tail

Prose, then a legend.

| description | built_from_env | rc | parsed_from |
|---|---|---|---|
| exact row ⚖ | `C` | `0` | `[A]` |
| substring row ⚖ (a long parenthetical the case does not carry) | `—` | `—` | `null` |
| unproven row | `C` | `0` | per [X](x.md) |
| mismatch row | `C` | `0` | `[A, B]` |

⚖ door rows are prose here.

| door | fragment |
|---|---|
| Dockerfile carries the stamp | `ARG X` |

<details><summary>Evidence</summary>

--8<-- "ING-RT-JOIN.md"

</details>

### NEXT-RULE

| description | y |
|---|---|
| nope | `2` |
"""

JOIN = "ING-RT-JOIN"


def _join_results():
    return [
        _result("test_j[mismatch row]", "tests.test_j#test_j", "passed", story=JOIN,
                params={"built_from_env": "'C'", "rc": "0", "parsed_from": "'[A]'"}),
        _result("test_j[exact row ⚖]", "tests.test_j#test_j", "passed", story=JOIN,
                params={"built_from_env": "'C'", "rc": "0", "parsed_from": "'[A]'"}),
        _result("test_j[substring row ⚖]", "tests.test_j#test_j", "failed", story=JOIN,
                params={"parsed_from": "'null'"}, message="boom"),
        _result("test_j[Dockerfile carries the stamp]", "tests.test_j#test_j", "passed", story=JOIN,
                params={"door": "'Dockerfile'", "fragment": "'ARG X'"}),
        _result("test_j[an unspecified door]", "tests.test_j#test_j", "passed", story=JOIN,
                params={"door": "'e2e.sh'", "fragment": "'--build-arg'"}),
    ]


def test_spec_tables_scoped_to_the_rule_heading():
    tables = evidence.spec_tables(SPEC_PAGE, JOIN)
    assert [h for h, _ in tables] == [["description", "built_from_env", "rc", "parsed_from"],
                                      ["door", "fragment"]]
    assert len(tables[0][1]) == 4 and len(tables[1][1]) == 1
    assert evidence.spec_tables(SPEC_PAGE, "NEXT-RULE")[0][1] == [["nope", "`2`"]]
    assert evidence.spec_tables(SPEC_PAGE, "ABSENT") == []


def test_norm_cell_and_match_case():
    assert evidence.norm_cell("`C`") == evidence.norm_cell("'C'") == "C"
    assert evidence.norm_cell("`a`, `b`") == evidence.norm_cell("'a, b'")
    assert evidence.norm_cell(None) == ""
    recs = [{"case": "Exact Row ⚖"}, {"case": "exact row ⚖"}]
    assert evidence.match_case("`exact row ⚖`", recs) == ("exact", [recs[1]])
    assert evidence.match_case("exact row ⚖ (tail)", recs)[0] == "substring"
    assert evidence.match_case("nothing", recs) == ("none", [])


def test_joined_fragment_is_the_spec_table_in_spec_order(tmp_path):
    ev = evidence.build_evidence(_join_results())
    spec = {JOIN: evidence.spec_tables(SPEC_PAGE, JOIN)}
    evidence.write_outputs(ev, tmp_path, rules=[JOIN], spec=spec)
    md = (tmp_path / f"{JOIN}.md").read_text(encoding="utf-8")
    lines = md.splitlines()
    # header = status + the spec's own columns; rows in SPEC order, not alphabetical
    assert lines[0] == "| status | description | built_from_env | rc | parsed_from | attachments | test | threads |"
    rows = [l for l in lines[2:6]]
    assert [r.split(" | ")[1] for r in rows] == [
        "exact row ⚖", "substring row ⚖ (a long parenthetical the case does not carry)",
        "unproven row", "mismatch row"]
    assert rows[0].startswith("| ✓ |") and "`C`" in rows[0]          # equal → spec cell as authored
    assert rows[1].startswith("| ❌~ |") and "| `—` | `—` | `null` |" in rows[1]   # `—` cells untouched; ~ = substring match
    assert rows[2].startswith("| ∅ |") and "per [X](x.md)" in rows[2]  # unproven, prose cell kept
    assert rows[3].startswith("| ≠ |") and "`[A, B]` ⇢ '[A]'" in rows[3]  # spec ⇢ actual
    # second spec table joined too; the door row is claimed, so only the other door is unspecified
    assert "| ✓ | Dockerfile carries the stamp | `ARG X` |" in md
    assert "_Not in the spec:_" in md
    assert "an unspecified door" in md and "Dockerfile carries the stamp" in md.split("_Not in the spec:_")[0]
    assert "| status | case | door | fragment |" in md.split("_Not in the spec:_")[1]
    # trailing annotation columns: attachments count, test module (tests. prefix off), unthreaded params
    assert rows[0].endswith("| 0 | test_j | unthreaded: built_from_env, rc, parsed_from |")
    assert rows[1].endswith("| 0 | test_j | unthreaded: parsed_from |")
    assert rows[2].endswith("| per [X](x.md) |  |  |  |")          # ∅ row: blank annotations
    # the divider says what "not in the spec" means
    assert "_Only table rows join; a row ruled in the section's prose joins once that prose becomes a table._" in md.split("_Not in the spec:_")[1]
    assert "_spec: 5 rows · 4 proven (3 exact, 1 substring~) · 1 unproven ∅ · 1 cells ≠ · 1 not in the spec_" in md
    assert "_scope: modules in this run — test_j (5 records for this rule)_" in md
    # digest carries the three mechanical codes
    digest = (tmp_path / "digest.md").read_text(encoding="utf-8")
    assert f"- ROW_UNPROVEN {JOIN} unproven row:" in digest
    assert f"- CELL_MISMATCH {JOIN} mismatch row: parsed_from spec `[A, B]` ⇢ actual '[A]'" in digest
    assert f"- ROW_UNSPECIFIED {JOIN} an unspecified door: evidence row matches no TABLE row (a ruling in section prose does not join)" in digest
    assert f"- FAILED {JOIN} substring row ⚖" in digest


def test_spec_rule_with_no_records_is_all_unproven(tmp_path):
    ev = evidence.build_evidence(_join_results())
    spec = {"NEXT-RULE": evidence.spec_tables(SPEC_PAGE, "NEXT-RULE")}
    evidence.write_outputs(ev, tmp_path, rules=["NEXT-RULE"], spec=spec)
    md = (tmp_path / "NEXT-RULE.md").read_text(encoding="utf-8")
    assert "| ∅ | nope | `2` |" in md
    assert "1 unproven ∅" in md


def test_rule_without_spec_tables_keeps_the_evidence_table(tmp_path):
    ev = evidence.build_evidence(_join_results())
    evidence.write_outputs(ev, tmp_path, rules=[JOIN], spec={})
    md = (tmp_path / f"{JOIN}.md").read_text(encoding="utf-8")
    assert md.startswith("| status | case |") and "attachments" in md


def test_norm_cell_reduces_links_and_module_short():
    # a markdown link in a spec cell compares as its text; the rendered cell keeps the link
    assert evidence.norm_cell("per [ING-RT-DELTA-MERGE](riigiteataja-delta.md#x)") == "per ING-RT-DELTA-MERGE"
    assert evidence.norm_cell("`per [X](y)`") == evidence.norm_cell("'per X'")
    assert evidence.module_short("tests.test_build_provenance#test_x") == "test_build_provenance"
    assert evidence.module_short("pkg.mod") == "pkg.mod" and evidence.module_short(None) == ""


def test_link_cell_joins_and_scope_names_modules_without_records(tmp_path):
    recs = _join_results() + [
        # the ∅ "unproven row" gets its record from another module; its link cell now matches
        _result("test_d[unproven row]", "tests.test_d#test_d", "passed", story=JOIN,
                params={"built_from_env": "'C'", "rc": "0", "parsed_from": "'per X'"}),
        # a module in the run with no record for this rule (unlabelled) → listed with 0
        _result("test_other", "tests.test_other#test_other", "passed", story=None),
    ]
    ev = evidence.build_evidence(recs)
    spec = {JOIN: evidence.spec_tables(SPEC_PAGE, JOIN)}
    evidence.write_outputs(ev, tmp_path, rules=[JOIN], spec=spec)
    md = (tmp_path / f"{JOIN}.md").read_text(encoding="utf-8")
    assert "| ✓ | unproven row | `C` | `0` | per [X](x.md) | 0 | test_d |" in md
    assert "0 unproven ∅" in md
    assert ("_scope: modules in this run — test_d (1 records for this rule) · "
            "test_j (5 records for this rule) · test_other (0 records for this rule)_") in md


def test_substring_mark_and_threads_column_on_the_row(tmp_path):
    recs = [
        _result("test_j[exact row ⚖]", "tests.test_j#test_j", "passed", story=JOIN,
                params={"built_from_env": "'cafef00d'", "rc": "0", "parsed_from": "'[A]'"},
                steps=[{"name": "Given: sha cafef00d", "status": "passed"},
                       {"name": "ert-build cafef00d → corpus", "status": "passed"},
                       {"name": "verdict: cafef00d in corpus_meta", "status": "passed"}]),
        _result("test_j[substring row ⚖]", "tests.test_j#test_j", "passed", story=JOIN,
                params={"parsed_from": "'null'"}),
    ]
    ev = evidence.build_evidence(recs)
    spec = {JOIN: [(["description", "built_from_env", "rc", "parsed_from"],
                    [["exact row ⚖", "`cafef00d`", "`0`", "`[A]`"],
                     ["substring row ⚖ (tail)", "`—`", "`—`", "`null`"]])]}
    evidence.write_outputs(ev, tmp_path, rules=[JOIN], spec=spec)
    rows = (tmp_path / f"{JOIN}.md").read_text(encoding="utf-8").splitlines()[2:4]
    # built_from_env threads all three phases → bold, not listed; rc and parsed_from are listed
    assert rows[0].startswith("| ✓ | exact row ⚖ | **`cafef00d`** | `0` | `[A]` |")
    assert rows[0].endswith("| 0 | test_j | unthreaded: rc, parsed_from |")
    assert rows[1].startswith("| ✓~ | substring row ⚖ (tail) |")


# ---------------------------------------------------------------- human spec page (--spec-page-out)

def _single_file_report(tmp_path, cases):
    """A minimal Allure 2 single-file index.html embedding ``cases`` as base64 test cases."""
    import base64
    body = "".join(
        f"d('data/test-cases/{c['uid']}.json','"
        f"{base64.b64encode(json.dumps(c).encode()).decode()}');" for c in cases)
    path = tmp_path / "index.html"
    path.write_text(f"<html><script>{body}</script></html>", encoding="utf-8")
    return path


def test_load_report_reads_single_file_and_multi_file(tmp_path):
    cases = [{"uid": "aa11", "fullName": "tests.test_j#test_j", "name": "test_j[exact row ⚖]"}]
    single = _single_file_report(tmp_path, cases)
    assert evidence.load_report(single) == {("tests.test_j#test_j", "test_j[exact row ⚖]"): "aa11"}
    assert evidence.load_report(tmp_path) == evidence.load_report(single)   # dir holding index.html
    multi = tmp_path / "multi" / "data" / "test-cases"
    multi.mkdir(parents=True)
    (multi / "aa11.json").write_text(json.dumps(cases[0]), encoding="utf-8")
    assert evidence.load_report(tmp_path / "multi") == evidence.load_report(single)


def test_spec_page_rewrites_tables_in_place_for_humans():
    ev = evidence.build_evidence(_join_results(), generated="2026-09-29")
    links = {("tests.test_j#test_j", "test_j[exact row ⚖]"): "aa11",
             ("tests.test_j#test_j", "test_j[Dockerfile carries the stamp]"): "bb22"}
    page = evidence.render_spec_page(SPEC_PAGE, ev, [JOIN], links,
                                     "../../evidence/latest/report/index.html#behaviors/")
    lines = page.splitlines()
    # the spec's own columns only: no status / attachments / test / threads
    assert "| description | built_from_env | rc | parsed_from |" in lines
    assert not any("attachments" in l or "| status |" in l for l in lines)
    # a passing row: no mark, description linked to the published report, styled by class
    assert ("| [exact row ⚖](../../evidence/latest/report/index.html#testresult/aa11)"
            "{: .evidence-row } | `C` | `0` | `[A]` |") in lines
    # exceptions carry the mark; a row with no uid stays plain text
    assert any(l.startswith("| ❌ substring row ⚖ (a long parenthetical") for l in lines)
    assert "| ∅ unproven row | `C` | `0` | per [X](x.md) |" in lines
    assert any(l.startswith("| mismatch row |") and "`[A, B]` ⇢" in l for l in lines)
    # the second table is rewritten where it stands, under its own prose
    i = lines.index("⚖ door rows are prose here.")
    assert lines[i + 2] == "| door | fragment |"
    assert "[Dockerfile carries the stamp](" in lines[i + 4]
    # one note under the first table (what is off + scope); the clean door table has none
    notes = [l for l in lines if l.startswith("_") and "without evidence" in l]
    assert len(notes) == 1 and "1 not passing" in notes[0] and "_scope" not in notes[0]
    assert "modules in this run — test_j" in notes[0]
    # other rules' tables are untouched
    assert "| other row | `1` |" in lines and "| nope | `2` |" in lines


def test_spec_page_link_text_flattens_links_and_escapes_brackets():
    assert evidence._link_text("per [X](x.md) [sic]") == "per X \\[sic\\]"


def test_cli_writes_the_human_page(tmp_path):
    res = tmp_path / "res"
    res.mkdir()
    for i, r in enumerate(_join_results()):
        (res / f"{i}-result.json").write_text(json.dumps(r), encoding="utf-8")
    spec = tmp_path / "page.md"
    spec.write_text(SPEC_PAGE, encoding="utf-8")
    report = _single_file_report(tmp_path, [
        {"uid": "aa11", "fullName": "tests.test_j#test_j", "name": "test_j[exact row ⚖]"}])
    out = tmp_path / "site" / "page.md"
    evidence.cli(["--results", str(res), "--out", str(tmp_path / "o"), "--rules", JOIN,
                  "--spec", str(spec), "--spec-page-out", str(out), "--report", str(report),
                  "--report-url", "r/index.html"])
    assert "[exact row ⚖](r/index.html#testresult/aa11){: .evidence-row }" in out.read_text()


def test_spec_page_cells_are_as_authored_without_threading_bold():
    ev = evidence.build_evidence(_join_results(), generated="2026-09-29")
    for r in ev["rules"][JOIN]:           # every param fully threaded → the fragment would bold
        r["thread"] = {k: {"given": True, "when": True, "then": True} for k in r["params"]}
    page = evidence.render_spec_page(SPEC_PAGE, ev, [JOIN])
    assert "**" not in page.split("### ING-RT-JOIN", 1)[1].split("### NEXT-RULE", 1)[0]


def test_spec_page_drops_the_rules_own_evidence_block_and_skips_rules_that_join_nothing():
    ev = evidence.build_evidence(_join_results() + [
        _result("test_n[unrelated case]", "tests.test_n#test_n", "passed", story="NEXT-RULE",
                params={"y": "'2'"})], generated="2026-09-29")
    page = evidence.render_spec_page(SPEC_PAGE, ev)          # default: every rule with evidence
    join = page.split("### ING-RT-JOIN", 1)[1].split("### NEXT-RULE", 1)[0]
    assert '--8<-- "ING-RT-JOIN.md"' not in join and "<details>" not in join
    # NEXT-RULE has evidence but no row joins: its table stays exactly as authored
    assert page.split("### NEXT-RULE", 1)[1] == SPEC_PAGE.split("### NEXT-RULE", 1)[1]
    assert "| other row | `1` |" in page                        # no evidence at all: untouched


def test_load_report_reads_the_gzipped_single_file(tmp_path):
    import gzip
    single = _single_file_report(tmp_path, [
        {"uid": "cc33", "fullName": "tests.t#t", "name": "t[x]"}])
    gz = tmp_path / "gz" / "index.html"
    gz.parent.mkdir()
    gz.write_bytes(gzip.compress(single.read_bytes()))
    assert evidence.load_report(gz) == {("tests.t#t", "t[x]"): "cc33"}


def test_plain_fragment_links_cases_and_joined_fragment_needs_a_join(tmp_path):
    ev = evidence.build_evidence(_join_results(), generated="2026-09-29")
    links = {("tests.test_j#test_j", "test_j[an unspecified door]"): "dd44"}
    # a spec whose tables join nothing → the plain fragment, not an all-∅ joined one
    spec = {JOIN: [(["description", "x"], [["no such row", "`1`"]])]}
    evidence.write_outputs(ev, tmp_path, spec=spec, links=links, report_url="https://s/r/index.html")
    md = (tmp_path / f"{JOIN}.md").read_text(encoding="utf-8")
    assert "| status | case |" in md.splitlines()[0]
    assert "[an unspecified door](https://s/r/index.html#testresult/dd44)" in md


def test_cli_page_without_rules_rewrites_every_rule_that_joins(tmp_path):
    res = tmp_path / "res"
    res.mkdir()
    for i, r in enumerate(_join_results()):
        (res / f"{i}-result.json").write_text(json.dumps(r), encoding="utf-8")
    spec = tmp_path / "page.md"
    spec.write_text(SPEC_PAGE, encoding="utf-8")
    out = tmp_path / "page.out.md"
    evidence.cli(["--results", str(res), "--out", str(tmp_path / "o"),
                  "--spec", str(spec), "--spec-page-out", str(out)])
    text = out.read_text(encoding="utf-8")
    assert "| ∅ unproven row |" in text and not (tmp_path / "o" / "digest.md").exists()


def test_substring_join_needs_a_real_phrase_not_one_word():
    recs = [{"case": "known date, 9 days old → stale alert"}, {"case": "alerts severity set"}]
    assert evidence.match_case("`alert`", recs) == ("none", [])          # one word: coincidence
    assert evidence.match_case("hit", [{"case": "hit — law text"}]) == ("none", [])
    assert evidence.match_case("severity set", recs) == ("substring", [recs[1]])
