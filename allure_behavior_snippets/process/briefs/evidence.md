# Evidence brief — is there enough evidence for the rows this PR touches?

One of the two briefs a specs reviewer runs in one session; the other is [rows.md](rows.md), and
both report through [finding-contract.md](finding-contract.md) (IDs, fields, reconciliation,
rounds, the one verdict, the output shape — read it first). You answer ONE question per PR:

> **Is there enough evidence for the requirement rows this PR touches?**

Read intent before evidence; never read implementation code; the inputs dir is the only world
(finding-contract.md § Ground rules). Evidence row identity is (rule, world, case)
([../CONVENTIONS.md](../CONVENTIONS.md) § Evidence row identity); a row that names no world is a
row proven against nothing.

## Inputs — read in this order

1. `spec-sections.md` — what each touched rule MEANS (intent first, always).
2. `digest.md` — the precomputed part: the run's `Stamp:` and `Baseline:` lines, then per rule the
   evidence tables (case · world · status · params · attachments), `Δ vs baseline`, the mechanical
   **Findings** and the **Hygiene** pre-flags. Confirm each precomputed finding against the spec
   section; a false positive is dropped with one line saying why.
3. `evidence.json` — the same rows as data (steps, phases, thread, attachments by file name),
   for what the digest's cells leave open.
4. `attachments/` (and `<RULE>.md`) — open an attachment only where a row's cells leave a value
   unproven. The pack holds the touched rules' attachments; nothing else exists.
5. `baseline-evidence.json` — the base branch's rows for the touched rules (when provided).
6. `prior-review.md` — the previous review: its finding IDs and `Hygiene notes:` are your only
   memory.

## Scope

- Default scope = the rules in `touched-rules.json` — which already includes every rule on a page
  whose preamble / index changed (`page-preamble`) and every rule linking a changed glossary
  (`glossary`).
- Never all specs. Never rules the diff does not reach.

## The stamp comes first

The digest's `Stamp:` line reads `environment.properties` ([../CONVENTIONS.md](../CONVENTIONS.md)
§ The head/artifact stamp). When the run names another commit, or none, the evidence is stale:
ONE pack-level finding `E-STALE/run` and every touched row is unproven at this head — do not judge
rows against it. Where a rule is stated against the shipped artifact and the run carries no
`image.digest`, that is PR-head evidence, not artifact evidence: `UNIT_ONLY`-shaped judgment, ⚖.

## The predicate — "not enough evidence"

Apply per touched rule. Mechanical codes arrive precomputed in `digest.md`; you add the judgment
codes.

| Code | Fires when | Kind |
|---|---|---|
| `NO_EVIDENCE` | zero evidence rows for the rule | mechanical |
| `ROW_UNPROVEN` | a spec-table row added / changed in the diff has no evidence case matching it — exact match on the row's description cell first, then case-insensitive substring; **state which** matched or that neither did | mechanical + confirm |
| `BARE_ROW` | an evidence row with no params and no attachments, on a rule whose spec table has value columns (inputs / expected) | mechanical |
| `FAILED` | any evidence row for the rule is `failed` / `broken` | mechanical |
| `VANISHED` | a case present in the baseline is absent now, the spec diff carries no ~~tombstone~~ / strike for it, AND the case lies inside the baseline's stated scope (the `Baseline:` line; the digest classifies removed cases as relabelled / out-of-scope / unlabelled / gone — only `gone` can be VANISHED) | mechanical + confirm |
| `UNIT_ONLY` | the only evidence observes no system boundary (a static assertion over text, a pure-function call) while the rule states behaviour of an endpoint / tool / step — flag ⚖ (the digest's `UNIT_ONLY_CANDIDATE` pre-flags a case with steps but no `when`) | judgment |
| `WORLD_UNNAMED` | the rule's rows depend on data and no evidence row names a world (a `world` label, a `world:` mention, or the module's single declared world) | judgment |

**An unverified row is legal in exactly two forms** (rule 10), both in the page's requirement
index: `🚧 WIP → #<issue>` or `⚑ gap (<date>, PR #N → work #M): <line>`. `NO_EVIDENCE` /
`ROW_UNPROVEN` on a requirement carrying either mark is a note, not a finding. Verified-ness is
derived — a hand-written "verified" word or ✓ in the spec proves nothing; judge the row by its
evidence and quote the word in that finding's `Observed:`.

Not a code: a row whose evidence exists but you would have designed differently. Not a code: a ⚖
row whose ruling you disagree with. A digest `CELL_MISMATCH` (a spec cell contradicted by the
test's same-named parameter) is `ROW_UNPROVEN` for that row: the case ran, but not the row.

Findings use the contract's fields and IDs: `E-<CODE>/<page>#<RULE>[/<case>]`.

## Report hygiene — non-blocking notes, every review

The evidence is only as readable as its report. Every review, walk each touched rule's cases'
steps (the `steps` / `phases` / `thread` of `evidence.json`; the digest's `Hygiene:` block
pre-flags threshold cases) against [../CONVENTIONS.md](../CONVENTIONS.md) § Prime rule of
reporting, and apply the codes defined there — `STEP_FLAT`, `STEP_NOISE`, `NAME_BLANK`,
`ATTACH_BULK`, `PARAM_BLOB`, `CONTEXT_TAX`, `THREAD_BROKEN` — as it defines them; this brief holds
no second definition.

- Report the **three worst** under `Hygiene notes:`, one line each:
  `H-<CODE>/<case>: <one-line fix>`. Fewer if fewer exist; zero is a legitimate count. Never a
  finding on its own.
- **Anti-degeneration belt:** the same unresolved code on the same case as in `prior-review.md`'s
  `Hygiene notes:` becomes a BLOCKING finding `E-HYGIENE_REPEAT/<page>#<RULE>/<case>` —
  `Observed:` names the code and the prior review it was first noted in. The prior review is your
  only memory; no other state.
- Thresholds are judgment marks, not counters.

## What you must not do

- No code review: no style, no naming, no structure.
- No re-litigating ⚖ rows — the ruling is the spec; you judge whether it is proven.
- No questions — you run unattended; where a fact is unknowable from the pack, say so and decide
  on what the pack shows.
- No proposals to change spec intent, add rows or move requirements — that is the author's
  `Spec changes:` and the rows brief.
