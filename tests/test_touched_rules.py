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
    repo.write("specs/glossary.md", GLOSSARY.replace("the per-stack limit", "the per-stack limit, revised"))
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


# ---------------------------------------------------------------- glossary scoped by term

PAGE_C = """\
# GET /extras

## API-EXTRA-ANCHORED

Uses [extra](../glossary.md#extra) only.

| description || status |
|---|---|
| anchored || 200 |

## API-EXTRA-BARE

See the [glossary](../glossary.md).

| description || status |
|---|---|
| bare || 200 |

## API-EXTRA-NONE

Links nothing.

| description || status |
|---|---|
| none || 200 |
"""
GLOSSARY_2 = "# Glossary\n\nIntro prose.\n\n## quota\nthe per-stack limit\n\n## extra\nthe extra thing\n"


@pytest.fixture()
def repo2(repo):
    """The base repo with a second term (`extra`) and a page linking it anchored / bare / not."""
    repo.write("specs/glossary.md", GLOSSARY_2)
    repo.write("specs/endpoints/extras.md", PAGE_C)
    repo.commit("base-2")
    repo.git("branch", "-f", "master", "HEAD")
    return repo


def glossary_rows(repo):
    return {r["rule"]: r["sources"] for r in rows_of(repo).values()}


def test_changed_term_touches_only_its_linkers_and_bare_links(repo2):
    repo2.write("specs/glossary.md", GLOSSARY_2.replace("the per-stack limit", "the per-stack limit, revised"))
    repo2.commit()
    assert glossary_rows(repo2) == {"API-ORDERS-LIMIT": ["glossary"], "API-EXTRA-BARE": ["glossary"]}


def test_new_term_leaves_other_terms_linkers_alone(repo2):
    repo2.write("specs/glossary.md", GLOSSARY_2 + "\n## brand new\nnobody links this yet\n")
    repo2.commit()
    assert glossary_rows(repo2) == {"API-EXTRA-BARE": ["glossary"]}  # the #977 shape: quota / extra linkers untouched


def test_preamble_only_glossary_change_falls_back_to_every_linker(repo2):
    repo2.write("specs/glossary.md", GLOSSARY_2.replace("Intro prose.", "Intro prose, reworded."))
    repo2.commit()
    assert glossary_rows(repo2) == {"API-ORDERS-LIMIT": ["glossary"], "API-EXTRA-ANCHORED": ["glossary"],
                                    "API-EXTRA-BARE": ["glossary"]}


def test_renamed_term_touches_the_old_anchors_linkers(repo2):
    repo2.write("specs/glossary.md", GLOSSARY_2.replace("## extra\n", "## extra thing\n"))
    repo2.commit()
    # the base side of the hunk sits under `extra`; its linker is touched although head no longer has the anchor
    assert glossary_rows(repo2) == {"API-EXTRA-ANCHORED": ["glossary"], "API-EXTRA-BARE": ["glossary"]}


def test_glossary_links_shapes():
    page = """\
## A-ONE
[x](../glossary.md#quota) and <a href="glossary.md#L%C3%B5ige%20(subsection)">y</a>
## A-TWO
plain [glossary](glossary.md) and an empty anchor glossary.md#
## A-THREE
no link
"""
    assert tr.glossary_links(page) == {"A-ONE": {"quota", "loige-subsection"}, "A-TWO": {None}}
    assert tr.glossary_linked_rules(page) == {"A-ONE", "A-TWO"}


def test_slug_normalises_renderer_dialects():
    assert tr.slug("lõige (subsection)") == "loige-subsection"
    assert tr.slug("redaction (redaktsioon / terviktekst)") == tr.slug("redaction-redaktsioon--terviktekst")
    assert tr.slug("Dump Family") == "dump-family"


def test_glossary_changed_terms_attribution():
    base = "# G\n\nintro\n\n## quota\nold\n\n## extra\nx\n### sub\ny\n"
    head = "# G\n\nintro\n\n## quota\nnew\n\n## extra\nx\n### sub\nz\n"
    # a changed line under `### sub` marks the nested term and its parent; `quota` too
    hunks = [tr.Hunk(6, 1, 6, 1), tr.Hunk(11, 1, 11, 1)]
    assert tr.glossary_changed_terms(hunks, head, base) == ({"quota", "extra", "sub"}, {"quota", "extra", "sub"}, False)
    # a blank line appended to a term's tail marks nothing; the preamble marks page-wide
    assert tr.glossary_changed_terms([tr.Hunk(6, 0, 7, 1)], head.replace("new\n", "new\n\n"), head) == (set(), {"quota", "extra", "sub"}, False)
    assert tr.glossary_changed_terms([tr.Hunk(3, 1, 3, 1)], head, base)[2] is True
    # a glossary with no term headings at all cannot attribute: page-wide
    assert tr.glossary_changed_terms([tr.Hunk(1, 1, 1, 1)], "# G\nonly a title\n", None)[2] is True


def test_unresolvable_anchor_counts_as_bare(repo2):
    repo2.write("specs/endpoints/extras.md", PAGE_C.replace("glossary.md#extra", "glossary.md#no-such-term"))
    repo2.commit("base-3")
    repo2.git("branch", "-f", "master", "HEAD")
    repo2.write("specs/glossary.md", GLOSSARY_2.replace("the per-stack limit", "the per-stack limit, revised"))
    repo2.commit()
    assert glossary_rows(repo2) == {"API-ORDERS-LIMIT": ["glossary"], "API-EXTRA-ANCHORED": ["glossary"],
                                    "API-EXTRA-BARE": ["glossary"]}


GLOSSARY_FENCED = """\
# Glossary

## quota
the per-stack limit

## extra

~~~markdown
## example
a heading inside a tilde fence is not a term
~~~

the extra thing, defined after the fenced example
"""


def test_heading_inside_a_tilde_fence_is_not_a_term_boundary(repo2):
    repo2.write("specs/glossary.md", GLOSSARY_FENCED)
    repo2.commit("base-fenced")
    repo2.git("branch", "-f", "master", "HEAD")
    repo2.write("specs/glossary.md", GLOSSARY_FENCED.replace("the extra thing, defined", "the extra thing, redefined"))
    repo2.commit()
    # the edit sits under `extra`, not under the fenced `## example` (which would unselect extra's linker)
    assert glossary_rows(repo2) == {"API-EXTRA-ANCHORED": ["glossary"], "API-EXTRA-BARE": ["glossary"]}


def test_unclosed_fence_falls_back_to_every_linker(repo2):
    unclosed = GLOSSARY_2 + "\n```\nleft open\n"
    repo2.write("specs/glossary.md", unclosed)
    repo2.commit("base-unclosed")
    repo2.git("branch", "-f", "master", "HEAD")
    repo2.write("specs/glossary.md", unclosed.replace("the extra thing", "the extra thing, revised"))
    repo2.commit()
    assert glossary_rows(repo2) == {"API-ORDERS-LIMIT": ["glossary"], "API-EXTRA-ANCHORED": ["glossary"],
                                    "API-EXTRA-BARE": ["glossary"]}


def test_unfenced_lines_commonmark_shapes():
    text = "a\n```py\n## not\n``\n```\nb\n   ~~~~\n~~~\n## still fenced\n~~~~  \nc\n``` x ` y\n## heading\n"
    lines, unclosed = tr.unfenced_lines(text)
    # the backtick fence closes only on >= 3 backticks alone; the 4-tilde fence ignores the shorter ~~~;
    # a backtick opener whose info string holds a backtick is not a fence
    assert [ln for _, ln in lines] == ["a", "b", "c", "``` x ` y", "## heading"]
    assert unclosed is False
    assert tr.unfenced_lines("x\n```\nopen\n")[1] is True
    assert [a.anchor for a in tr.glossary_terms(GLOSSARY_FENCED)] == ["quota", "extra"]


PAGE_A_FENCED = PAGE_A.replace(
    "Creates an order.\n",
    "Creates an order.\n\n~~~markdown\n## example\nnot a heading: a fenced sample of the page shape\n~~~\n",
)


def test_heading_inside_a_tilde_fence_does_not_split_a_rule_section(repo):
    repo.write("specs/endpoints/orders.md", PAGE_A_FENCED)
    repo.commit("base-fenced")
    repo.git("branch", "-f", "master", "HEAD")
    repo.write("specs/endpoints/orders.md", PAGE_A_FENCED.replace("| zero items | 0 || 400 |", "| zero items | 0 || 422 |"))
    repo.commit()
    rows = rows_of(repo)
    # the row sits after the fenced `## example`; it still belongs to API-ORDERS-CREATE (the old parser mapped it to no rule)
    assert {r: v["sources"] for r, v in rows.items()} == {"API-ORDERS-CREATE": ["spec-hunk"]}


def test_unclosed_fence_on_a_spec_page_is_page_wide(repo):
    unclosed = PAGE_A.replace("Creates an order.\n", "Creates an order.\n\n~~~\nleft open\n")
    repo.write("specs/endpoints/orders.md", unclosed)
    repo.commit("base-unclosed")
    repo.git("branch", "-f", "master", "HEAD")
    repo.write("specs/endpoints/orders.md", unclosed.replace("| over the limit | 101 || 429 |", "| over the limit | 101 || 430 |"))
    repo.commit()
    rows = rows_of(repo)
    # uncertain parse: every heading counts (even PAGE_A's own fenced `## API-NOT-A-HEADING`) and the
    # page is page-wide — a superset of the real rules, never a narrower set
    assert {"API-ORDERS-CREATE", "API-ORDERS-LIMIT"} <= set(rows)
    assert all("page-preamble" in r["sources"] for r in rows.values())
