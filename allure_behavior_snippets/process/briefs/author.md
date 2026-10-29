# Author brief — the row author's checklist

For a PR that touches a spec page, its glossary / schema / worlds, or a `rule("ID")` test (rows.md § Inputs).
"rule N" is [../RULES.md](../RULES.md); a bare `§` is a [../CONVENTIONS.md](../CONVENTIONS.md) section;
"check N" is [rows.md](rows.md). Repo facts (specs root, ID prefix, worlds, gate commands, who gates
rows): your repo's process page — RULES.md § Adopting this process in a repo.

## Read before writing
- The page end to end: schema, use cases, world(s), `glossary.md` — rules 6, 7, 8, § Evidence row identity.
- The neighbouring rows of the table you change — rows.md § Table shape.
- The intent source — `## Acceptance`, a use case, the prose constraint, `External:` — rule 1, check 1.

## A row
- Header = the parameter list, inputs first; expected columns end in `?`, `name?` is the argname
  `expected_name` — § The intent column.
- Description cell = intent, never the inputs restated; `⚖` on a judgment row — rule 4.
- Rows must read with the description hidden — the reviewer reads them masked first; fixture-supplied
  inputs go in a `world` column — § The intent column, rows.md check 10.
- ≲8 curated rows per rule is a review signal; split by distinct behaviour, never by count, and
  preserve the old anchor — rules 2, 3; rows.md § Table shape.

## The prose above the table
- It describes the system, never its tests or its rows — rule 11.
- A fact no row proves is marked where it stands or in the index (`🚧 WIP` / `⚑ gap`) — rules 10, 11.

## Tests
- `pytest.param(..., id=<the description cell, verbatim>)`; argnames == header cells — § The intent column.
- `rule("ID")` on system-level tests only; every labelled test names its `world` — § Allure taxonomy.
- The report is the deliverable: given / when / then, a verdict step per claim — § Prime rule of reporting.
- Run the repo's spec gate and lint gate before opening the PR; the join counts ratchet — § The lint gate.

## The PR body
- Every specs change under a `Spec changes:` heading, each `⚖` row named — rule 1, rows.md check 2.
- What the PR falls short of gets `⚑ gap` in the index row and a `Spec changes:` line — rule 10.
- Never adjust a row to observed behaviour without flagging it as a judgment change — rule 1.

## The review
- One review; fix every blocking finding in this PR per its `Satisfied by:`; a finding the
  description explains is not repaired — finding-contract.md § The verdict, rows.md check 10.
- Contest a ruled `⚖` row by a new `⚖` row, never in review — finding-contract.md § Ground rules.
