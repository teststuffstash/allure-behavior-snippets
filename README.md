# allure-behavior-snippets

Evidence tooling for repos that keep requirement specs next to their tests — and, since v0.5, the
ONE portable home of the spec / evidence / review process those repos run. Installed as a wheel
pinned per repo:

```
pip install https://github.com/teststuffstash/allure-behavior-snippets/releases/download/v0.5.0/allure_behavior_snippets-0.5.0-py3-none-any.whl
```

| Console script | What it does |
|---|---|
| `allure-behavior-snippets` | one SVG + markdown snippet per Allure behavior (from a generated report's `behaviors.json`) |
| `allure-evidence` | model-friendly evidence from RAW Allure results: per-rule tables, `evidence.json`, the reviewer `digest.md`, the spec join, the human spec-page render |
| `touched-rules` | which rule IDs a `base...head` diff reaches (v0.5) |
| `evidence-pack` | the specs reviewer's context pack for one PR round (v0.5) |
| `process-path` | prints the installed `process/` dir (v0.5) |

The v0.4.x scripts and flags are unchanged.

## The process (v0.5)

Every repo with a specs root runs the same requirements → tests (Allure) → evidence → review
process, or the process does not work (homelab ADR-156). It ships as package data in
`allure_behavior_snippets/process/`, versioned with the tools that implement it:

- [`RULES.md`](allure_behavior_snippets/process/RULES.md) — the numbered spec rules 1–10 ("rule N"
  means rule N here), the contract page template, how a repo adopts.
- [`CONVENTIONS.md`](allure_behavior_snippets/process/CONVENTIONS.md) — tests and evidence: one
  story per rule, `rule()`, the intent column, row identity (rule, world, case), the Prime rule of
  reporting (given / when / then, one call under test, a verdict step per claim, attachments under
  their step) and its hygiene codes, the head/artifact stamp, evidence blocks, the lint gate.
- [`briefs/rows.md`](allure_behavior_snippets/process/briefs/rows.md) — do the touched rows encode
  intent (checks 1–4, 7; table shape as an advisory candidate).
- [`briefs/evidence.md`](allure_behavior_snippets/process/briefs/evidence.md) — is there enough
  evidence per touched row (the predicate codes, baseline differences, report hygiene).
- [`briefs/finding-contract.md`](allure_behavior_snippets/process/briefs/finding-contract.md) —
  what both briefs share: derived finding IDs, the fields a worker fixes from, reconciliation,
  round tracking, the one combined verdict and the review's output shape.
- [`briefs/author.md`](allure_behavior_snippets/process/briefs/author.md) — the worker-facing
  brief: what a row author reads before touching a specs page (row shape, prose, tests, the PR
  body, what the reviewer does with it) — pointers into the rules, conventions and briefs above.

A repo adopts by pinning the wheel and turning its own process page into a pointer here plus its
repo facts (specs root, ID prefix, worlds, gate commands, who gates spec rows).

### The process as files — the artifact image (v0.6.5)

`ghcr.io/teststuffstash/allure-behavior-snippets-process:v<version>` is a `FROM scratch` image whose
root filesystem is exactly the pinned process text — for a pod that reads the process as files
without installing the tool (a Kubernetes [image volume](https://kubernetes.io/docs/concepts/storage/volumes/#image),
mounted read-only):

```
/process/RULES.md
/process/CONVENTIONS.md
/process/briefs/{rows,evidence,finding-contract,author}.md
/process/VERSION          # the package version, == the image tag without its `v`
```

It is published by the same tag push as the tool image (Dockerfile target `process`, workflow job
`process`), signed the same way, and CI diffs its listing against `allure_behavior_snippets/process/`.

### `touched-rules`

```
touched-rules [--base master] [--head HEAD] [--repo DIR] [--specs-root specs]
              [--tests-root DIR ...] [--code-root DIR ...] [--id-regex RE]
              [--json] [--out DIR]
```

A rule is touched by a spec hunk inside its section (`spec-hunk`), a preamble / index hunk on its
page (`page-preamble`, page-wide), a changed test labelled `rule("ID")` (`test-label`, by AST), a
changed module under a `--code-root` quoting the ID (`event-map`, off by default), a changed
`*.schema.json` listing it under `x-requirements` (`schema`), or a glossary change under a rule
that links the glossary (`glossary`); `orphan` marks an ID with no heading. stdout is one ID per
line (or `--json` rows `{rule, page, path, sources}`); `--out` also writes `touched-rules.json`
+ `touched-rules.txt`. Exit 0 always.

### `evidence-pack`

```
evidence-pack BASE HEAD RESULTS [--out evidence-review] [--repo DIR] [--specs-root specs]
              [--tests-root DIR ...] [--code-root DIR ...] [--id-regex RE]
              [--baseline evidence.json [--baseline-commit SHA] [--baseline-scope TEXT]]
              [--prior-review FILE] [--issue-intent FILE] [--pr-body FILE]
              [--report-url URL] [--no-specs-tree] [--mask-descriptions]
```

Writes into `--out` (a previous pack there is replaced; any other non-empty dir is refused):

| File | What it is |
|---|---|
| `touched-rules.json` / `.txt` | the touched rules and why |
| `spec-sections.md` | each touched rule's section at head, then the spec diff |
| `evidence.json` | the run's records for the touched rules |
| `evidence/<RULE>.json` | the same records, one file per touched rule (what a reviewer opens) |
| `digest.md` | `Stamp:` (head / artifact) and `Baseline:` (commit + scope) lines, then per rule: tables, Δ vs baseline, mechanical findings, hygiene pre-flags |
| `<RULE>.md` | per touched rule: the spec table joined to its evidence, or the evidence table |
| `baseline-evidence.json` | the baseline's records for the touched rules (with `--baseline`) |
| `attachments/` | the touched rules' attachment files |
| `prior-review.md`, `issue-intent.md`, `pr-body.md` | the round inputs, or a stated "none / not provided" line |
| `tree/<specs-root>/` | the specs at head (neighbouring pages, glossary, schemas, worlds) |
| `process/` | `RULES.md`, `CONVENTIONS.md`, `briefs/` — the process the review runs under |
| `manifest.json` | tool version, base / head, layout, stamp, baseline, counts, inputs, files, `masked` |

With `--mask-descriptions` (the staged read's first pass, briefs/rows.md check 10) it also writes:

| File | What it is |
|---|---|
| `spec-sections-masked.md` | the same sections, every decision table's `description` cell → row key `r<table>.<row>` (numbered over the whole page), the header cell → `row`; no spec diff |
| `row-keys.tsv` | `key<TAB>description`, grouped under a `# <page>` line |
| `digest.masked.md`, `<RULE>.masked.md` | the digest and per-rule tables with the case column keyed the same way |

`tree/`, `evidence/`, `evidence.json` and `attachments/` stay unmasked; `manifest.json` `masked` lists what is.

When no rule is touched it exits 0 with the empty forms of these files. Exit 64 on bad input.

## Development

```
python3 -m pytest tests/test_evidence.py tests/test_touched_rules.py tests/test_pack.py tests/test_process_docs.py
cd tests && python3 -m pytest test_unittests.py     # the SVG snippets (relative report paths)
```
