"""A tiny git fixture repo for the touched-rules / evidence-pack tests."""
import subprocess
from pathlib import Path

PAGE_A = """\
---
id: EP-ORDERS
---
# POST /orders — create an order

Preamble prose.

## API-ORDERS-CREATE

Creates an order.

| description | qty || status |
|---|---|---|
| one item | 1 || 201 |
| zero items | 0 || 400 |

## API-ORDERS-LIMIT

Uses the [quota](../glossary.md#quota).

| description | qty || status |
|---|---|---|
| over the limit | 101 || 429 |

```
## API-NOT-A-HEADING
```

## Sources

nothing here
"""

PAGE_B = """\
# GET /health

## API-HEALTH

| description || status |
|---|---|
| alive || 200 |
"""

GLOSSARY = "# Glossary\n\n## quota\nthe per-stack limit\n"
SCHEMA = '{"properties": {"qty": {"x-requirements": ["API-ORDERS-CREATE"]}}}\n'
TEST_A = '''\
from tests.evidence import rule

pytestmark = rule("API-HEALTH")


@rule("API-ORDERS-CREATE")
def test_create():
    assert "API-ORDERS-LIMIT"  # a string literal is not a label
'''
EVENTS = 'EVENT_REQUIREMENT = {"order.created": "API-ORDERS-CREATE"}\n'


class Repo:
    def __init__(self, root: Path):
        self.root = root
        root.mkdir(parents=True, exist_ok=True)
        self.git("init", "-q", "-b", "master")

    def git(self, *args):
        return subprocess.run(
            ["git", "-c", "user.name=t", "-c", "user.email=t@example.com", "-c", "commit.gpgsign=false",
             *args], cwd=self.root, check=True, capture_output=True, text=True).stdout

    def write(self, path, text):
        p = self.root / path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")

    def rm(self, path):
        (self.root / path).unlink()

    def commit(self, msg="c"):
        self.git("add", "-A")
        self.git("commit", "-q", "-m", msg)
        return self.git("rev-parse", "HEAD").strip()

    def branch(self, name):
        self.git("checkout", "-q", "-b", name)


def base_repo(root: Path, specs_root="specs", tests_root="tests"):
    r = Repo(root)
    r.write(f"{specs_root}/endpoints/orders.md", PAGE_A)
    r.write(f"{specs_root}/endpoints/orders.schema.json", '{"properties": {}}\n')
    r.write(f"{specs_root}/endpoints/health.md", PAGE_B)
    r.write(f"{specs_root}/glossary.md", GLOSSARY)
    r.write(f"{tests_root}/test_other.py", "def test_x():\n    pass\n")
    r.write("src/events.py", "EVENT_REQUIREMENT = {}\n")
    r.write("README.md", "repo\n")
    r.commit("base")
    r.branch("pr")
    return r
