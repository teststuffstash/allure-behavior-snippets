# Changelog

## v0.6.6 — 2026-10-29

Row authors had no page of their own: workers were pointed at the reviewer's checks (briefs/rows.md
check 10) and recipes restated rule content, which drifts. Every worker ride that touches specs pays
the page in tokens, so it is a checklist, not a second document.
- **`briefs/author.md` — the author's checklist**: one page, ≤40 lines, pointers only. Each bullet
  is an imperative plus where the rule lives ("rule N", a CONVENTIONS `§`, a rows.md check) and
  restates no mechanism: when it applies, read before writing, a row (header = parameter list,
  description = intent, rows read with the description hidden, ≲8 curated rows), the prose (rule 11
  + the mark), tests (id == description cell, argnames == header, `rule()` + `world`, the gates
  before the PR), the PR body (`Spec changes:`, ⚖, `⚑ gap`, no unflagged adjustment to observed
  behaviour), the review (fix per `Satisfied by:` in the same PR; a ⚖ disagreement is a new ⚖
  row). Repo facts stay on the repo's process page (RULES.md § Adopting this process in a repo).
- `tests/test_process_docs.py` holds the shape: the line cap, every bullet ≤2 lines and citing a
  rule / `§` / check, every `§` resolving to a heading of the file it names, no tables, no numbered
  checks, no dates. Ships with the wheel, the pack's `process/` and the artifact image like the
  other briefs. Rules, conventions, the reviewer briefs, tools and flags are unchanged.

## v0.6.5 — 2026-10-29

Agent worker pods read the pinned process as files. Until now the only published form of
`process/` was the python wheel / the tool image, where the text sits under the venv's
site-packages — nothing a pod could mount without running the tool.
- **The process artifact image** `ghcr.io/teststuffstash/allure-behavior-snippets-process:<tag>`:
  a `FROM scratch` image (Dockerfile target `process`) whose root filesystem is exactly
  `/process/RULES.md`, `/process/CONVENTIONS.md`, `/process/briefs/*.md` and `/process/VERSION`
  (the package version, derived from `pyproject.toml` at build — one source). Meant for a
  Kubernetes image volume (`pod.spec.volumes[].image`) mounted read-only; same tag set and
  cosign signature as the tool image, published by the same `v*.*.*` tag push (workflow job
  `process`). The tool image is unchanged.
- The `process` job diffs the built rootfs listing against `allure_behavior_snippets/process/`
  (a brief added later cannot be left out silently) and, on a tag push, refuses to publish when
  `VERSION` ≠ the tag.
- Process text, tools and flags are unchanged — v0.6.4's briefs ship as-is.

## v0.6.4 — 2026-10-29

The first staged specs review (oracle-fleet #925 spot-check item 5 → #946) read a masked copy of
the page first: 105 tables · 65 fine without descriptions · 43 structural findings (41 survive the
reveal) · 25 new intent findings — a class nine ordinary rounds had passed. The masking was a
seat-local script; the pack had no masked surface (#39).
- `evidence-pack --mask-descriptions`: `spec-sections-masked.md` beside `spec-sections.md` — the
  same sections, every decision table's `description` cell → row key `r<table>.<row>`, the header
  cell → `row`, every other byte as authored; `row-keys.tsv` (`key<TAB>description`, grouped
  under a `# <page>` line). Tables number over the WHOLE page, not the touched sections, so a key
  is stable between the two passes and across rounds at one head. The spec diff is not in the
  masked file (its rows carry descriptions) — a comment says so.
- The description-derived evidence surfaces get masked twins **beside the originals**:
  `digest.masked.md` and `<RULE>.masked.md`, the case column keyed like the spec row it joins
  (exact or substring). Beside, not a `masked/` dir: pass 1 still reads `process/`, the round
  inputs and `manifest.json` from the top level, so a subdir would scope nothing, and pass 2
  opens the twin by name. A case no spec row claims keeps its pytest id (nothing keys it); a
  substring join reads exact in the twin (`ROW_UNKEYED` and the `~` mark are description-level —
  the full surface's). `tree/`, `evidence/`, `evidence.json`, `attachments/` stay unmasked;
  `manifest.json` `masked` lists the masked files, the key map and what stays unmasked.
- `allure-evidence`: `mask_page()` (the masking, `evidence.py`).
- CONVENTIONS "Rows read without their description" names the masked surface; briefs/rows.md
  check 10 is the two-pass shape — pass 1 on the masked surface, its findings frozen; pass 2 on
  the full one, each pass-1 finding `survives` / `contradicted` / `withdrawn`; a finding pass 2
  explains is NOT repaired. briefs/evidence.md lists the twins among its inputs.

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
