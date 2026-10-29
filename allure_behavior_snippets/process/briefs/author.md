# Author brief — writing the spec rows this PR touches

The one page a row author reads before touching a page under the specs root. The reviewer's
briefs ([rows.md](rows.md), [evidence.md](evidence.md), [finding-contract.md](finding-contract.md))
say how your rows are judged; this one says how to write them so that judgment passes. It points,
it does not restate: "rule N" means rule N of [../RULES.md](../RULES.md), a section named by name
is in [../CONVENTIONS.md](../CONVENTIONS.md), and where this page seems to differ, they win. Repo
facts — the specs root, the ID prefix, the worlds, the spec gate and lint commands, who gates
rows — live in your repo's own process page (RULES.md § Adopting this process in a repo).

## When this brief applies

Your PR adds, changes or removes a row, a table, a requirement's prose, an index flag, a glossary
term, a sibling `*.schema.json`, a use case or a world — or a test labelled `rule("ID")`.
`touched-rules` sets the reviewer's scope: a preamble or index hunk puts the whole page in it.

## Read before writing

- The requirement's page end to end: the prose, the index table, the sibling schema (rule 7), the
  use cases it cites (rule 8), the world(s) its rows name, and `glossary.md` (rule 6).
- The neighbouring rows of the table you are changing — a new row answers the same question with
  the same axes, or it belongs in another requirement (rows.md § Table shape, advisory).
- The row's **intent source**, before any run: the issue's `## Acceptance` bullet, a use case, the
  prose constraint above the table, an `External:` clause (rule 9). A row whose only source is
  what the implementation returned is golden-mastered — the #1 failure mode (rule 1).

## A row's shape

- **The header is the parameter list** ([CONVENTIONS.md](../CONVENTIONS.md) § The intent column):
  the description cell first, then inputs, then the expected columns, each ending in `?`
  (`status?` is the argname `expected_status`). Every other header cell is a parametrize argname
  verbatim, named by what is observed — equality unless the name says otherwise
  (`log_line_contains`, not `log_line`); every cell is the value that parameter takes.
- **The description cell is intent**, never a restatement of the inputs. `⚖` in it on a row that
  encodes a choice with a plausible alternative; none on a mechanical boundary row (rule 4).
- **Rows read with the description hidden** (§ The intent column, "Rows read without their
  description"): the input and expected cells alone distinguish every row, and each expected cell
  follows from the prose over those inputs — an input that varies between rows is a column, never
  words in the description. Inputs a fixture set supplies are named once, in a `world` column
  ([CONVENTIONS.md](../CONVENTIONS.md) § Evidence row identity); a fixture name alone does not
  distinguish two rows of the same world. The reviewer reads the table this way first (masked,
  pass 1 of rows.md check 10); a condition only the description supplies is a finding the reveal
  does not repair.
- **Curated rows ≲8 per rule**; past that, split along meaning (rule 2) and alias the old anchor
  (rule 3). Expected codes, fields and types exist in the sibling schema (rule 7); terms come
  from the glossary, a new one defined there in the same PR (rule 6).

## The prose above the table

- It describes the system, in the system's own nouns — never its tests, never its rows (rule 11).
  A sentence that needs the word "test" to be true belongs in a test docstring.
- A fact the prose states that no row proves is **marked where it stands** (`unverified —
  expected to …`) or at the index as `🚧 WIP` / `⚑ gap` when the whole requirement is open
  (rules 10, 11); never asserted bare. A vendor fact nobody read says "verify during
  implementation" (rule 9). The heading is the ID and nothing else (rule 3).

## Tests prove rows

- Each row is `pytest.param(..., id="<the description cell, verbatim — ⚖ included>")`; the
  argnames equal the header cells (§ The intent column). That equality IS the join: a cell no
  test parameter matches is an expected value nobody proved.
- `rule("ID")` labels a system-level test only; unit tests stay unlabelled
  ([CONVENTIONS.md](../CONVENTIONS.md) § Allure taxonomy, § The `rule()` decorator). Every
  labelled test names its world (a `world` label).
- The report is the deliverable ([CONVENTIONS.md](../CONVENTIONS.md) § Prime rule of reporting):
  given / when / then, ONE `when`, a `verdict()` step per claim named with its value, attachments
  under the step they support. A row with no evidence yet carries the explicit unverified marker
  and the index flag (§ Evidence blocks on spec pages, rule 10) — never a silently blank block.
- **Before opening the PR, run the repo's spec gate and lint gate** (§ The lint gate): the join
  counts (`row-unkeyed`, `header-unthreaded`, `cell-mismatch`, `case-unspecified`) are ratcheted
  — your PR holds or lowers the line. Evidence counts only when stamped with the PR's head
  (§ The head/artifact stamp).

## The PR body

- Every specs change goes under a **`Spec changes:`** heading (rule 1): each added, changed or
  removed row, each new glossary term, each split or alias; a `⚖` row names its alternative. A
  removed row whose evidence was green on the base branch says which proof is lost and what
  carries it now — a sibling row, a tombstone, an alias anchor (rows.md check 3).
- **What you did not cover is rendered, not hidden**: a requirement the PR falls short of gets
  `⚑ gap` in its index row (rule 10), listed under `Spec changes:`.
- **Never adjust a row to match observed behaviour without flagging it as a judgment change**
  (rule 1): the run says what the system did; the row says what it must do.
- `Fixes #N` only when every `## Acceptance` bullet runs at the PR head; what only production can
  observe is `## Closeout`, and the PR says `Refs #N` (§ Issue acceptance).

## What the reviewer does with it

- One session runs both briefs over the context pack and posts ONE review, ONE verdict
  (finding-contract.md) — intent before evidence, never your code: your rows are judged from
  `spec-sections.md`, `pr-body.md`, `issue-intent.md` and the digest alone.
- Every blocking finding carries a derived, round-stable ID (`R<check>/…`, `E-<CODE>/…`) and a
  `Satisfied by:` naming the ONE edit that clears it. Make that edit in the same PR. A finding the
  description alone explains is not repaired by it — add the column, the world, the mark, the row.
- Advisory notes (`Shape:`, ⚖ noise, `Hygiene notes:`) are not findings, but the same hygiene code
  left on the same case blocks the next round (`E-HYGIENE_REPEAT`, evidence.md). A disagreement
  with a ruled `⚖` row is a new `⚖` row in a PR, never an argument in review.
