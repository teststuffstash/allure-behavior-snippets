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

- **Prose claims without a row — ADVISORY.** A sentence in a rule's prose that constrains
  behaviour but no row exercises is an unverified constraint: name it (the gate's zero-row check
  sees whole requirements, not sentences).

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
