import json

import pytest

from allure_behavior_snippets import touched_rules as tr
from tests.gitrepo import EVENTS, GLOSSARY, PAGE_A, SCHEMA, TEST_A, base_repo


def rows_of(repo, layout=tr.Layout()):
    return {r["rule"]: r for r in tr.touched_rules(tr.Git(repo.root), "master", "HEAD", layout)}


@pytest.fixture()
def repo(tmp_path):
    return base_repo(tmp_path / "repo")


def test_spec_hunk_maps_to_its_section_only(repo):
    repo.write("specs/endpoints/orders.md", PAGE_A.replace("| zero items | 0 || 400 |", "| zero items | 0 || 422 |"))
    repo.commit()
    rows = rows_of(repo)
    assert list(rows) == ["API-ORDERS-CREATE"]
    assert rows["API-ORDERS-CREATE"] == {"rule": "API-ORDERS-CREATE", "page": "endpoints/orders",
                                         "path": "specs/endpoints/orders.md", "sources": ["spec-hunk"]}


def test_preamble_hunk_touches_every_rule_on_the_page(repo):
    repo.write("specs/endpoints/orders.md", PAGE_A.replace("Preamble prose.", "Preamble prose, changed."))
    repo.commit()
    rows = rows_of(repo)
    assert set(rows) == {"API-ORDERS-CREATE", "API-ORDERS-LIMIT"}
    assert all(r["sources"] == ["page-preamble"] for r in rows.values())


def test_deleted_only_hunk_resolves_against_base(repo):
    repo.write("specs/endpoints/orders.md", PAGE_A.replace("| over the limit | 101 || 429 |\n", ""))
    repo.commit()
    assert list(rows_of(repo)) == ["API-ORDERS-LIMIT"]


def test_fenced_heading_and_trailing_section_map_to_no_rule(repo):
    repo.write("specs/endpoints/orders.md", PAGE_A.replace("nothing here", "still nothing"))
    repo.commit()
    assert rows_of(repo) == {}


def test_test_labels_by_ast_not_text(repo):
    repo.write("tests/test_orders.py", TEST_A)
    repo.commit()
    rows = rows_of(repo)
    assert set(rows) == {"API-ORDERS-CREATE", "API-HEALTH"}  # the string literal does not count
    assert rows["API-HEALTH"]["sources"] == ["test-label"]


def test_test_label_shapes():
    src = '''
import pytest
pytestmark = [rule("A-ONE").marks, pytest.mark.rule("A-TWO")]
class TestX:
    @evidence.rule(id="A-THREE")
    def test_y(self): "A-FOUR"
def test_z(): pass  # A-FIVE
'''
    assert tr.test_labels(src) == {"A-ONE", "A-TWO", "A-THREE"}
    assert tr.test_labels("def broken(:") == set()


def test_event_map_only_with_a_code_root(repo):
    repo.write("src/events.py", EVENTS)
    repo.commit()
    assert rows_of(repo) == {}
    rows = rows_of(repo, tr.Layout(code_roots=("src",)))
    assert rows["API-ORDERS-CREATE"]["sources"] == ["event-map"]


def test_schema_x_requirements(repo):
    repo.write("specs/endpoints/orders.schema.json", SCHEMA)
    repo.commit()
    assert rows_of(repo)["API-ORDERS-CREATE"]["sources"] == ["schema"]


def test_glossary_change_touches_linking_rules(repo):
    repo.write("specs/glossary.md", GLOSSARY + "\n## extra\nmore\n")
    repo.commit()
    rows = rows_of(repo)
    assert list(rows) == ["API-ORDERS-LIMIT"]
    assert rows["API-ORDERS-LIMIT"]["sources"] == ["glossary"]


def test_orphan_label(repo):
    repo.write("tests/test_ghost.py", '@rule("API-GHOST")\ndef test_g(): pass\n')
    repo.commit()
    row = rows_of(repo)["API-GHOST"]
    assert row["page"] is None and row["path"] is None
    assert row["sources"] == ["orphan", "test-label"]


def test_custom_layout_and_id_regex(tmp_path):
    repo = base_repo(tmp_path / "repo", specs_root="svc/specs", tests_root="svc/tests")
    repo.write("svc/specs/endpoints/health.md", "# x\n\n## gw_health\n\nchanged\n")
    repo.write("svc/tests/test_h.py", '@rule("gw_probe")\ndef test_p(): pass\n')
    repo.commit()
    layout = tr.Layout(specs_root="svc/specs/", tests_roots=("svc/tests",), id_regex=r"gw_[a-z]+")
    rows = rows_of(repo, layout)
    assert rows["gw_health"]["page"] == "endpoints/health"
    assert rows["gw_health"]["path"] == "svc/specs/endpoints/health.md"
    assert rows["gw_probe"]["sources"] == ["orphan", "test-label"]
    # the default layout sees none of it (wrong roots, wrong regex)
    assert rows_of(repo) == {}


def test_bad_id_regex_fails_early():
    with pytest.raises(Exception):
        tr.Layout(id_regex="(")


def test_section_text():
    body = tr.section_text(PAGE_A, "API-ORDERS-CREATE")
    assert body.startswith("## API-ORDERS-CREATE") and "| zero items |" in body
    assert "API-ORDERS-LIMIT" not in body
    assert tr.section_text(PAGE_A, "API-NOPE") is None


def test_cli_txt_json_and_out(repo, tmp_path, capsys):
    repo.write("specs/endpoints/orders.md", PAGE_A.replace("Preamble prose.", "Changed."))
    repo.commit()
    out = tmp_path / "out"
    assert tr.cli(["--repo", str(repo.root), "--out", str(out)]) == 0
    assert capsys.readouterr().out.splitlines() == ["API-ORDERS-CREATE", "API-ORDERS-LIMIT"]
    assert (out / "touched-rules.txt").read_text() == "API-ORDERS-CREATE\nAPI-ORDERS-LIMIT\n"
    assert [r["rule"] for r in json.loads((out / "touched-rules.json").read_text())] == [
        "API-ORDERS-CREATE", "API-ORDERS-LIMIT"]
    assert tr.cli(["--repo", str(repo.root), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)[0]["page"] == "endpoints/orders"


def test_cli_git_failure_exits_zero_with_no_rows(repo, capsys):
    assert tr.cli(["--repo", str(repo.root), "--base", "no-such-ref"]) == 0
    captured = capsys.readouterr()
    assert captured.out == "" and "git failed" in captured.err
