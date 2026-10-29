# Rows brief — do the spec rows this PR touches encode intent?

One of the two briefs a specs reviewer runs in one session; the other is
[evidence.md](evidence.md), and both report through [finding-contract.md](finding-contract.md)
(IDs, fields, reconciliation, rounds, the one verdict, the output shape — read it first). This
brief judges **rows**: where each row's expected value comes from, whether judgment is flagged,
whether a proof is lost, whether the page agrees with its schema and glossary. Whether a row is
*proven* is the evidence brief's question, not this one's.

Read intent before evidence; never read implementation code; the inputs dir is the only world
(finding-contract.md § Ground rules). "rule N" means rule N of [../RULES.md](../RULES.md).

## Inputs — from the context pack

- `spec-sections.md` — each touched rule's section at head (with why it was touched), then the
  spec diff. `touched-rules.json` lists the rules; a `page-preamble` source means the page's
  preamble or index changed, so every rule on it is in scope; `glossary` means the glossary
  changed under rules that link it.
- `spec-sections-masked.md` — the same sections with every description cell a row key
  `r<table>.<row>` (header `row`), no diff; `row-keys.tsv` maps the keys back; `digest.masked.md`
  and `<RULE>.masked.md` are the evidence surfaces keyed the same way. Pass 1 of check 10 reads
  these and nothing with a description in it (not `tree/`, not `evidence/`). Absent when the pack
  was built without `--mask-descriptions`: then check 10 is one read with the column covered.
- `tree/<specs-root>/` — the specs at head: neighbouring pages, `glossary.md`, the sibling
  `*.schema.json`, `use-cases/`, `worlds/`. Read a neighbour when a touched row references it
  (an alias anchor, a glossary term, a cited use case).
- `pr-body.md` — the `Spec changes:` section; `issue-intent.md` — the closing issue's
  `## Acceptance` text, fetched by the launcher (the ground for check 1).
- For check 3 only: `baseline-evidence.json` / the digest's `Δ vs baseline` — whether a removed
  row was green on the base branch.

## The checks — numbered, each with its posture

The numbers are stable IDs (`R<check>/…`). 5 (table shape) is the candidate section below; 6
(evidence) is the evidence brief.

1. **Rows derive from intent, not from the diff — BLOCKING.** For every row added or changed,
   name its intent source: the issue's `## Acceptance` bullet, a use case, the prose constraint
   above the table, an `External:` clause (rule 9). A row whose only justification is "that is
   what the implementation returns" is golden-mastered — the #1 failure mode (rule 1) — and
   blocks. The author passes by naming the source; you fail the row by finding none.
2. **Judgment rows are flagged and listed — BLOCKING.** Every added / changed row that encodes a
   choice with a plausible alternative carries `⚖` in its description column (rule 4) AND appears
   under `Spec changes:` in the PR body (rule 1). A spec diff with no `Spec changes:` section, or
   a ⚖-worthy row missing from it, blocks. A `⚖` on a mechanical boundary row is noise —
   ADVISORY, say which.
3. **A removed row with green evidence needs a stated reason — BLOCKING.** Removing (or merging
   away) a row whose evidence was green on the base branch drops a proof. `Spec changes:` must say
   which proof is lost and what carries it now (a sibling row, a tombstone or an alias anchor —
   rules 3 and 10). Rows lost inside a table split are this case — count them.
4. **Schema ⇄ page coupling — ADVISORY on the why, BLOCKING on a contradiction.** The repo's spec
   gate already proves heading ⇄ `x-requirements` and that every error code is mentioned (rule 7);
   you read whether the page says WHEN each code fires and whether the rows' expected values fit
   the sibling schema's shapes. A row whose expected error code, field or type is absent from the
   sibling schema contradicts the machine half and blocks.
7. **Glossary — ADVISORY on new terms, BLOCKING on a redefinition.** A new term is defined in
   `glossary.md` in the same PR and listed under `Spec changes:` (rule 6). Rows use existing terms
   instead of re-explaining them. A row that uses a glossary term in a different meaning blocks.
8. **The requirement describes the system, not its tests — ADVISORY.** A sentence in a touched
   rule's prose that narrates testing ("a test row feeds …", "a second set proves …", "the
   fixture …") or introduces its rows ("the rows below cover …") is rule 11's antipattern: the
   rows and the evidence block carry that, the prose carries behaviour. Quote the sentence; the
   author deletes it or restates it as the behaviour the rows key. Prose rules are read, not
   counted — this never blocks on its own.
9. **Column names are observables — ADVISORY on wording, BLOCKING on a false promise.** Every
   header cell after the description must be placeable from the requirement text alone, and it
   is a parametrize argname (CONVENTIONS § The intent column). A column named `contains` /
   `holds` / `includes` whose cases assert equality (the digest's then-step reads `= <value>`)
   promises less than is proven and blocks; a column that is no parameter of its cases is the
   gate's `header-unthreaded` and the evidence brief's `HEADER_UNTHREADED`, not your finding.

10. **Rows read with their descriptions hidden — BLOCKING when a condition lives only in the
    description.** Two passes, one review. Pass 1 reads the masked surface only
    (`spec-sections-masked.md`, `digest.masked.md`, `<RULE>.masked.md`: every description cell a
    row key `r<table>.<row>`): do the input cells and the expected (`name?`) cells distinguish
    every row, and does each expected cell follow from the requirement prose over those inputs?
    Record what is missing instead of guessing it, one finding per row key; pass 1's findings are
    frozen before the reveal. Pass 2 reads the full surface (`spec-sections.md`, `row-keys.tsv`
    joins the keys back) and marks each pass-1 finding `survives` / `contradicted` (the cells or
    evidence show otherwise) / `withdrawn` (pass 1 misread the cells), then checks that each
    description claims only what its cells and evidence show. A finding pass 2 can explain from
    the description is NOT repaired by it: a description that supplies an input the cells do not
    carry ("empty metadata falls through" over a row whose `meta_title` column is absent) is the
    finding, and it survives. Inputs a `world` column names are explicit; a fixture name alone is
    not when two rows of the same world differ (CONVENTIONS § The intent column, "Rows read
    without their description").

- **Prose claims without a row — ADVISORY, and the ask is a MARK, not a row.** A sentence in a
  rule's prose that constrains behaviour but no row exercises is an unverified constraint: name
  it, and ask for rule 11's in-place mark (`unverified — expected to …`, or the index-level
  `🚧 WIP` / `⚑ gap`) so the reader sees what is claimed and what is proven. An enumerated claim
  (a list of kinds, codes, cases) with rows for only some items is the common shape — say which
  items lack a row. "Facts in prose have rows" is the end state, reached rule by rule; a claim
  that is MARKED is in order. The gate's zero-row check sees whole requirements, not sentences.

## Table shape — CANDIDATE — under operator iteration (2026-09-29 hold); ADVISORY ONLY, never a finding

This checklist is a candidate from the operator's reviewer-shape trial and is still being
iterated. Report it under `Shape:` as suggestions; it never carries an ID, never blocks, never
contributes to the verdict.

- **One question per table.** Rows that answer different questions are different requirements —
  a split goes along MEANING (the output the rows prove), never along row count.
- **Same axes.** A column constant or n/a for most rows signals mixed questions — name the rows
  that differ. The exception: the column carries the rule the rows prove (a precedence or
  default column).
- **Atomic cells.** One value per cell: no `{k: v}` records, no "per XYZ" pointer where a value
  belongs, no several facts joined. A SET is one value when the row proves membership (`{A, B}`).
- **Cross-key rows stay.** A row that varies two inputs together to prove they are independent is
  legitimate; a split that cannot express it loses a proof (check 3).
- **Constants stay in columns.** A parameter moved from a column into the prose makes each row
  unreadable on its own.
- **Notation earns its place.** Every symbol is in a legend; a new symbol must beat spelling the
  value out; `—` means one thing per table.
- **Wide and sparse is a smell, not a finding.** Beyond ~6 columns with mostly `—` cells, say which
  rows differ and propose the axis; size itself is never the finding — no N×M limits.
- **A split proposal declares its new scope.** Rows that exist in the proposal but not the
  original are NEW tests (⚖ + `🚧 WIP` until a test row exists); the old ID keeps an alias anchor
  (rule 3).

## What you do not do

- Never propose an expected value read off the implementation, and never fill a row's expected
  cell yourself — that is golden-mastering by the reviewer.
- No follow-ups for polish (naming, wording, a tidier table): a plain comment or nothing. A spec
  ambiguity is a ⚖ row proposed in the PR, never an issue.
- No "someone should run the tests": evidence is the evidence brief's job, from the pack.
