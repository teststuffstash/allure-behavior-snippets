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
    for f in ("RULES.md", "CONVENTIONS.md", "briefs/rows.md", "briefs/evidence.md", "briefs/finding-contract.md"):
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
