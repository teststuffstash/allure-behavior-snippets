# The spec rules — how a repo's `specs/` is worked

The portable process (allure-behavior-snippets v0.5; decided as homelab ADR-156): every repo that keeps
`specs/` runs the SAME requirements → tests → evidence → review process, pinned by the version of
this package it installs. **The reviewer reviews the result, not the diff.** Every interface (an
endpoint, a tool, a pipeline stage) has a contract page under the repo's specs root with a sibling
`<name>.schema.json`; rows are decision tables of key examples; tests prove the rows against the
built artifact and stamp it.

The numbering is stable: "rule N" in a brief, a review or a PR means rule N here. How tests and
evidence are written is [CONVENTIONS.md](CONVENTIONS.md); how a reviewer judges is
[briefs/](briefs/).

## Rules

1. **Spec rows are gated and flagged.** Agents *propose* spec changes freely, in the same PR as
   the implementation, **flagged in the PR body** under a `Spec changes:` heading. Each repo names
   its gate for spec rows — a code owner, or a specs reviewer running
   [briefs/rows.md](briefs/rows.md) and [briefs/evidence.md](briefs/evidence.md) over the
   context pack. Rows encode *intent*; never adjust a row to match observed behaviour without
   flagging it as a judgment change — a row golden-mastered from the diff is the #1 failure mode.
2. **Grown, not pre-written.** An issue carries a handful of key rows (the happy path + the
   failure modes worth a conversation). The implementing agent adds boundary rows as it finds
   them, splits a requirement when it accretes too many tests, and proposes glossary terms. Spec
   refactoring is routine work.
3. **One ID namespace.** Requirement IDs (`<PREFIX>-<AREA>-<NAME>`, the repo picks the prefix) are
   spec-page headings, test labels (`@rule("ID")`), error codes and log fields. IDs are stable
   coordinates; the heading is the anchor, so it is never decorated (phase, WIP and gap flags live
   in the page's index table — rule 10); splitting leaves an alias on the old anchor so evidence
   history and inbound links keep resolving.
4. **Rows that encode judgment** (policy, anything with a plausible alternative) are flagged `⚖`
   in the table's description column; mechanical boundary rows are not.
5. **Evidence** under each rule is generated from test runs and carries its stamp — the commit
   the run tested and, where the run tested a built artifact, that artifact's digest · the date
   ([CONVENTIONS.md § The head/artifact stamp](CONVENTIONS.md#the-headartifact-stamp)). Missing
   or stale evidence = an unverified requirement. Verified-ness is derived, never declared.
6. **Glossary terms** (`<specs-root>/glossary.md`) are used in rows instead of repeating
   definitions; new terms take the same approval path as rows (rule 1).
7. **Requirement ⇄ schema coupling is mechanical.** Every contract page `<name>.md` has a sibling
   `<name>.schema.json` — the machine half (input / output / error shapes) that the implementation
   **imports**, never re-declares. Requirement IDs annotate the schema via `x-requirements`; the
   repo's spec gate (run inside its CI) fails on orphans in either direction and on error codes
   the page never mentions. The page owns *why/when* (rows); the schema owns *shape*. A
   cross-cutting requirement has ONE heading (rule 3) and may be annotated from several schemas.
8. **Use-case first.** `<specs-root>/use-cases/` pins end-to-end key examples with committed
   walk-through data, so every stage has its goalposts before it is built. Contract pages cite
   the use cases that exercise them; an interface or field no use case needs is a candidate for
   deletion, not documentation.
9. **External requirements are linked with maximal precision.** A requirement that implements an
   external clause (a protocol spec, a vendor's wire behaviour) carries one `External:` line per
   clause, in this machine-parseable shape:

   ```
   > **External:** MUST — [<spec + version> · <section path> § <nearest heading>, <numbered step/item + its name>](<url>#<anchor>)
   ```

   Always the deepest anchor that exists, plus the step name/number when the anchor covers a list.
   A vendor fact read off the wire names where and when it was read; a fact nobody read is marked
   "verify during implementation", never asserted. Deviations from a SHOULD/RECOMMENDED are stated
   on the requirement and flagged ⚖, never silent.
10. **The spec is always master; incompleteness is rendered, not hidden in branches.**
    - A requirement MAY land **before** its implementation, marked `🚧 WIP → #<issue>` in the
      page's requirement index table — never on the heading line (heading text == anchor == ID,
      and a decorated heading forks every inbound link).
    - **Known implementation gaps are rendered too** (`⚑ gap`, the dual of `🚧 WIP`): when a PR is
      merged forward despite falling short of a requirement, the shortfall is flagged in the index
      row as `⚑ gap (YYYY-MM-DD, PR #N → work #M): <one line>`; the fixing PR deletes it. `git
      log` on the spec file is the audit trail, never closed issues. Flags carry no sequential id
      — identity is (requirement anchor, date, PR#), so parallel writers never conflict.
    - Removed requirements keep a one-cycle tombstone (~~struck heading~~ + the removing PR; alias
      anchors keep old references resolving), then disappear into git history.
    - Small spec + implementation changes land together in one PR (the flagged flow, rule 1);
      spec-first-as-WIP is for intent that is settled before the code exists.
    - For issue writers: a spec states *verified facts and intent*; anything inferred or
      unverified is marked (⚖ / 🚧 / "verify during implementation") — a spec that looks complete
      but is not strands the worker at the first gap.
11. **The requirement describes the system, never its tests.** The prose above a table states
    what the system does and why, in the system's own nouns (the line written, the answer, the
    row stored); it never narrates how the rows are produced or what "a test" does. "A test row
    feeds each pattern through X; a second set proves Y" is the antipattern: the sentence
    verifies nothing, and it goes stale the moment a row moves. Rows describe themselves — the
    description cell is the case, readable without the test file — and the evidence block
    (rule 5) is the only place that says what ran. A sentence that needs the word "test" to be
    true belongs in the test's docstring, not in the spec. Nor does the prose introduce its rows
    ("the rows below cover …"): rows speak for themselves.
    **A fact the prose states that no row proves is not hidden — it is marked where it stands**,
    in plain words (`unverified — expected to behave like X`, or the index-level `🚧 WIP` /
    `⚑ gap` of rule 10 when the whole requirement is open). The mark is the request for a row.
    "Facts in prose have rows" is the end state, reached rule by rule as rows are written — a
    reading discipline for authors and reviewers, not a gate.

## Contract page template

```markdown
---
id: <KIND>-<NAME>
use-cases: [UC-1]
schema: <name>.schema.json      # the sibling machine half — rule 7
---
# <interface> — one-line purpose

## Interface — the machine half
<coupling table: requirement → schema paths → error codes>

## <PREFIX>-<REQ>
<prose constraint>
<decision table: description | inputs || expected>
<details markdown="1"><summary>Evidence — latest run</summary> --8<-- "<PREFIX>-<REQ>.md" </details>
```

Table shape (one question per table, atomic cells, …) is a **candidate** under the operator's
iteration, carried as advisory in [briefs/rows.md](briefs/rows.md) § Table shape — not a rule.

## Adopting this process in a repo

- Pin `allure-behavior-snippets` (the wheel) at the version whose process you run; bump the pin
  to adopt a new process version. The repo's own process page becomes a pointer here plus its
  repo facts: the specs root, the ID prefix, the worlds, the spec gate and lint commands, who
  gates spec rows (rule 1).
- The tools: `touched-rules` (which rules a diff reaches), `evidence-pack` (the reviewer's
  context pack), `allure-evidence` (evidence tables + digest), `process-path` (where these files
  are installed).
