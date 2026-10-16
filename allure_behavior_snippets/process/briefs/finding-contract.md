# The finding contract — shared by the rows brief and the evidence brief

One reviewer session runs BOTH briefs ([rows.md](rows.md), [evidence.md](evidence.md)) over one
context pack and posts **ONE** review. A worker fixes from that review without reconstructing
your argument, possibly in a fresh session that never saw the previous round — so every blocking
finding is self-contained, stable across rounds, and compatible with every other finding.

## Ground rules for both briefs

- **Intent before evidence.** Read `spec-sections.md` (and `issue-intent.md`, `pr-body.md`) before
  `digest.md` / `evidence.json`. A row's meaning comes from the spec, never from what the run did.
- **Never read implementation code.** Source, tests' bodies, manifests and workflows are not your
  inputs and the pack does not carry them. A finding that starts from code is invalid — drop it.
  If judging a row needs code, say so under *What would change my verdict* and leave it unjudged.
- **The inputs dir is the only world.** No fetch, no clone, no API call; what the pack does not
  hold is unknown, and an unknown is stated, never guessed. `manifest.json` says what the pack
  holds (and which inputs were not provided); `process/` is the pinned process you judge by.
- No code verdict, no style, no praise, no follow-up issues, no re-litigating a ⚖ row that was
  already ruled — a disagreement with a ruling is a plain comment, never a finding.

## Finding IDs — derived, never numbered

The same problem keeps the same ID across rounds, so the worker and the next round can track it.
`<page>` is the spec page as `touched-rules.json` names it (path under the specs root, no
suffix); `<RULE>` is the requirement ID.

| Brief | ID shape | Example |
|---|---|---|
| rows | `R<check>/<page>#<RULE>` — one finding per check per rule, naming every failing row inside it; `R<check>/<page>` for a page-level finding (a missing `Spec changes:` section is `R2/<page>` for the first page it affects) | `R1/endpoints/orders#API-ORDERS-CREATE` |
| evidence | `E-<CODE>/<page>#<RULE>[/<case>]` — `/<case>` when the code is per case or per row (the case id, or the spec row's description cell, verbatim) | `E-ROW_UNPROVEN/endpoints/orders#API-ORDERS-CREATE/token expired` |
| evidence, pack-level | `E-STALE/run` — the run is not stamped with this head | `E-STALE/run` |
| hygiene (notes) | `H-<CODE>/<case>` — never blocking on its own | `H-NAME_BLANK/token expired` |
| hygiene, repeated | `E-HYGIENE_REPEAT/<page>#<RULE>/<case>` — blocking | |

## Fields of a blocking finding

```
<ID>
  Rule/case:    <RULE> · <the row's description cell, or the case id>
  Violated:     <brief + check/code> — <the sentence of the rule it breaks; cite "rule N" from RULES.md or the CONVENTIONS section by name>
  Observed:     <what the inputs show — quoted, or pointed at: file + row / case / attachment>
  Satisfied by: <the ONE edit (or evidence) that clears it — not a menu>
```

## Reconcile before you post

- No two findings may ask for contradicting edits. A table split that drops a cross-key row
  against "keep this proof" is ONE finding with one compatible edit.
- A rows finding and an evidence finding on the same row are one problem when one edit clears
  both: keep the one whose *Satisfied by* names that edit, and mention the other ID in its
  *Observed*.
- Advisory notes (table shape, ⚖ noise, new terms, hygiene) are never findings and never carry a
  blocking ID — a worker must be able to tell missing proof from a shape suggestion at a glance.

## Later rounds

When `prior-review.md` holds a review, FIRST list each of its finding IDs as `resolved` or
`still open: <what is still missing>`, THEN review what changed. A finding you drop without
marking it is a contradiction the worker cannot see. A prior `H-<CODE>/<case>` note whose same
code still fires on the same case becomes `E-HYGIENE_REPEAT` ([evidence.md](evidence.md)
§ Report hygiene).

## The verdict — one for both briefs

`CHANGES_REQUESTED` when either brief has a blocking finding, or any prior finding is still open.
Otherwise `APPROVE`. A comment is never your terminal state. Your approval approves spec rows and
their evidence — never code.

## Output shape — the review body, in this order

```
## Specs review
Verdict: APPROVE | CHANGES_REQUESTED — <the blocking finding IDs, or "no blocking finding">
Process: allure-behavior-snippets <version from manifest.json>
Prior findings: one line per ID from prior-review.md — <ID> resolved | still open: <what is missing>   (omit on round 1)
Findings: one block per BLOCKING finding, fields as above   ("none" when approving)
Rows: one line per added / changed / removed row —
  <page>#<RULE> "<description>" — intent: <source> | golden · ⚖: present | missing | noise
Evidence: one line per touched rule —
  <RULE>: ENOUGH | NOT_ENOUGH · stamp: head@<sha8> | stale@<sha8> | none · rows proven <n>/<m> · 🚧/⚑: yes | no
Hygiene notes: the three worst, one line each — H-<CODE>/<case>: <one-line fix>   (omit when none)
Shape: ADVISORY (candidate) — one line per touched table: question · axes · cells — the split proposal, if any
Terms: new terms + where defined; existing terms misused
What would change my verdict: the exact edit that flips each blocking finding; the inputs you lacked
```
