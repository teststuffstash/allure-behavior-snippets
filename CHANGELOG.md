# Changelog

## v0.6.3 — 2026-10-28

Operator's structural spot check of the first migrated oracle page (oracle-fleet #925, comment
6476449506): expected-output columns were indistinguishable from inputs once a table grew past a
few columns, and `||` leaves an empty column in ordinary Markdown.
- CONVENTIONS § The intent column, "Expected columns": **inputs first, expected outputs last, an
  expected column's header ends in `?`** (`title?`) and is the argname `expected_title` in pytest;
  the role is kept in the joined row. `||` stays accepted for pages that already use it.
- `allure-evidence`: the join looks a `name?` column up as `expected_name` (`param_name()`,
  `column_role()`); `HEADER_UNTHREADED` names the pytest argname when it differs; every joined row
  carries `roles`.
- RULES.md page skeleton and briefs/rows.md: a row must read with its description hidden — the
  input cells distinguish the case, the description says why it matters, the prose states the
  rule (CONVENTIONS § The intent column, "Rows read without their description").

## v0.6.2 — 2026-10-23

Operator ruling after the first rule rewritten under v0.6 (homelab GW-REDACT): prose rules start
SOFT — read, not counted — or requirements read like code.
- RULES.md rule 11: the prose does not introduce its rows; **a fact the prose states that no row
  proves is marked where it stands** (`unverified — expected to …`, or rule 10's index flags) —
  the mark is the request for a row; "facts in prose have rows" is the end state, not a gate.
- CONVENTIONS § The lint gate: item 7 (word lint on rule prose) withdrawn; § The intent column:
  the inverse column-naming case (an observable-named column checked by containment).
- briefs/rows.md: check 8 BLOCKING → ADVISORY; "Prose claims without a row" asks for the mark,
  names the enumerated-claim shape.

## v0.6.1 — 2026-10-23

- `HEADER_UNTHREADED` skips the `||` divider's empty header cell (v0.6.0 reported it as a column on
  every decision table that uses the divider).

## v0.6.0 — 2026-10-23

The first rule walked end to end on the gateway island (a redaction rule, 13 rows) joined 0 cells:
its header named no parameter, its prose narrated its tests, and nothing in the process said either
was wrong.
- RULES.md **rule 11**: the requirement describes the system, never its tests.
- CONVENTIONS § The intent column: **the header is the parameter list** (description cell == id
  verbatim, other columns == argnames, cells == values); **columns are named by what is observed**,
  equality unless the name says otherwise. § The lint gate: items 6 (the exact-join counts, a
  ratchet) and 7 (no test words in rule prose).
- briefs/rows.md: checks 8 (prose narrates no tests — blocking) and 9 (column names are observables).
- briefs/evidence.md + `allure-evidence`: `ROW_UNKEYED` (substring join) and `HEADER_UNTHREADED`
  (a column no case carries) computed into the digest; `ROW_UNSPECIFIED` named in the code table.

## v0.5.2 — 2026-10-16

The spec join found NO tables on the first island that used the decision-table shape (homelab
gateway: 0 of 14 rules joined).
- `_TABLE_SEP` accepts an EMPTY separator cell: the `||` that divides a decision table's inputs
  from its expected columns (`|---|---||---|`). Before, such a table read as prose.
- A rule's section runs to the next heading of its own level or higher, or the next heading that
  names another requirement ID; a deeper plain sub-heading (`### Edge cases`) stays inside. Before,
  any sub-heading ended it. `spec_tables` and the spec-page rewrite (`_table_spans`) share the rule.
On the gateway's 219 records: 14/14 rules now find their tables; mechanical findings 26 → 103
(ROW_UNPROVEN, ROW_UNSPECIFIED, CELL_MISMATCH now computed).

## v0.5.1 — 2026-10-16

- `evidence-pack` also writes `evidence/<RULE>.json`, one touched rule's records per file. On the
  first real pack (homelab gateway, 14 touched rules) `evidence.json` was ~165k tokens; one rule's
  file is ~3–16k. The evidence brief now points the reviewer at the per-rule file.

## v0.5.0 — 2026-10-16

The portable spec / evidence / review process (homelab ADR-156). Additions only: the v0.4.x
console scripts (`allure-behavior-snippets`, `allure-evidence`) and their flags are unchanged.

- `process/` package data: `RULES.md` (spec rules 1–10), `CONVENTIONS.md` (tests & evidence, the
  Prime rule of reporting, the head/artifact stamp), `briefs/rows.md`, `briefs/evidence.md`,
  `briefs/finding-contract.md`.
- `touched-rules`: oracle-fleet's `scripts/touched-rules.py` generalised — `--specs-root`,
  `--tests-root`, `--code-root` (event maps, opt-in), `--id-regex`, `--repo`, `--out`.
- `evidence-pack`: oracle-fleet's `scripts/evidence-review.sh` contract in Python plus the round
  inputs (prior review, issue intent, PR body), the baseline's commit + scope, the stamp check,
  the specs tree at head, the touched rules' attachments, the pinned `process/` and a
  `manifest.json`.
- `process-path`: prints the installed `process/` dir.
