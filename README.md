# allure-behavior-snippets

Evidence tooling for repos that keep requirement specs next to their tests, and the ONE portable
home of the spec / evidence / review process those repos run (homelab ADR-156). A repo pins one
release and gets the tools and the process text at the same version.

This page describes the current release; what changed in which version is
[CHANGELOG.md](CHANGELOG.md).

## Install

Every [release](https://github.com/teststuffstash/allure-behavior-snippets/releases) publishes
three artifacts under one version:

| Artifact | For |
|---|---|
| the wheel — a release asset | CI jobs and reviewers that run the tools |
| `ghcr.io/teststuffstash/allure-behavior-snippets:v<version>` | the SVG snippet generator as a container (its entrypoint is `allure-behavior-snippets`) |
| `ghcr.io/teststuffstash/allure-behavior-snippets-process:v<version>` | the process text as files, no tool (§ The process as files) |

```
pip install https://github.com/teststuffstash/allure-behavior-snippets/releases/download/v<version>/allure_behavior_snippets-<version>-py3-none-any.whl
```

| Console script | What it does |
|---|---|
| `allure-evidence` | model-friendly evidence from RAW Allure results: per-rule tables, `evidence.json`, the reviewer `digest.md`, the spec join, the human spec-page render |
| `touched-rules` | which rule IDs a `base...head` diff reaches |
| `evidence-pack` | the specs reviewer's context pack for one PR round |
| `process-path` | prints the installed `process/` dir |
| `allure-behavior-snippets` | one SVG + markdown snippet per Allure behavior (from a generated report's `behaviors.json`) |

## The process

Every repo with a specs root runs the same requirements → tests (Allure) → evidence → review
process, or the process does not work. It ships as package data in
`allure_behavior_snippets/process/`, versioned with the tools that implement it:

- [`RULES.md`](allure_behavior_snippets/process/RULES.md) — the numbered spec rules 1–11 ("rule N"
  means rule N here), the contract page template, how a repo adopts.
- [`CONVENTIONS.md`](allure_behavior_snippets/process/CONVENTIONS.md) — tests and evidence: one
  story per rule, `rule()`, the intent column (the header is the parameter list, expected columns
  end in `?`, rows read without their description), row identity (rule, world, case), the Prime
  rule of reporting (given / when / then, one call under test, a verdict step per claim,
  attachments under their step) and its hygiene codes, the head/artifact stamp, evidence blocks,
  the lint gate and its ratchets.
- [`briefs/rows.md`](allure_behavior_snippets/process/briefs/rows.md) — do the touched rows encode
  intent (checks 1–4 and 7–10; check 10 is the staged read, the rows first with their
  descriptions masked; table shape as an advisory candidate).
- [`briefs/evidence.md`](allure_behavior_snippets/process/briefs/evidence.md) — is there enough
  evidence per touched row (the stamp, the predicate codes, baseline differences, report hygiene
  and its repeat belt).
- [`briefs/finding-contract.md`](allure_behavior_snippets/process/briefs/finding-contract.md) —
  what both briefs share: derived finding IDs, the fields a worker fixes from, reconciliation,
  round tracking, the one combined verdict, what may defer a blocking finding, and the review's
  output shape.
- [`briefs/author.md`](allure_behavior_snippets/process/briefs/author.md) — the worker-facing
  brief: what a row author reads before touching a specs page (row shape, prose, tests, the PR
  body, what the reviewer does with it) — pointers into the rules, conventions and briefs above.

How a repo adopts — the pin, and the repo facts its own process page keeps — is
[`RULES.md` § Adopting this process in a repo](allure_behavior_snippets/process/RULES.md#adopting-this-process-in-a-repo).

### The process as files

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

## The tools

### `allure-evidence`

```
allure-evidence --results DIR [--results DIR2 ...] --out OUTDIR
                [--rules A,B,C] [--baseline evidence.json]
                [--spec PAGE.md [--spec-page-out PAGE.md]]
                [--report-url URL] [--report REPORT]
```

Reads the `*-result.json` files pytest's Allure plugin writes (not the generated report) and
writes into `--out`:

| File | What it is |
|---|---|
| `evidence.json` | every record, grouped by story label (== rule ID) |
| `<RULE>.md` | per rule: the evidence table a spec page transcludes — with `--spec`, the page's own table joined to its evidence when the two join |
| `digest.md` | with `--rules`: the reviewer digest for those rules (tables, Δ vs `--baseline`, mechanical findings, hygiene pre-flags) |

`--spec-page-out` writes the `--spec` page with every joining rule's table rewritten for humans
(the spec's own columns, descriptions linked to their test, exceptions marked). `--report-url` is
the published Allure report (the footer link); with `--report` — that report as a directory or a
single-file `index.html` — each row links to its own test.

### `touched-rules`

```
touched-rules [--base master] [--head HEAD] [--repo DIR] [--specs-root specs]
              [--tests-root DIR ...] [--code-root DIR ...] [--id-regex RE]
              [--json] [--out DIR]
```

A rule is touched by a spec hunk inside its section (`spec-hunk`), a preamble / index hunk on its
page (`page-preamble`, page-wide), a changed test labelled `rule("ID")` (`test-label`, by AST), a
changed module under a `--code-root` quoting the ID (`event-map`, off by default), a changed
`*.schema.json` listing it under `x-requirements` (`schema`), or a glossary term changed under a
rule that links its anchor — `glossary.md#<slug>`; a bare `glossary.md` link counts as every term,
and a hunk no term heading claims (preamble / structure) falls back to every glossary-linking rule
(`glossary`); `orphan` marks an ID with no heading. stdout is one ID per
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
| `digest.md` | `Stamp:` (head / artifact) and `Baseline:` (commit + scope) lines, then per rule: tables, Δ vs baseline, mechanical findings, a `Cases:` block (`added n · changed n · unchanged n` + one `- [added]` / `- [changed]` line per such case; the rest are unchanged; `no baseline — every case counts as added or changed` without one), hygiene pre-flags — each hygiene line ends in the case's status against the baseline, `[added]` / `[changed]` / `[unchanged]` (`[no baseline]` without one); changed = parameters, top-level step names or attachment names differ from the baseline record of the same (rule · world · case) |
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
| `pass1-prior.tsv` | with `--prior-review`: the previous review's "Pass-1 adjudication" as keys only — `key<TAB>ruling<TAB>round<TAB>rule` (ranges expanded, slashes split; ruling read from the verdict position only, ∈ survives / contradicted / withdrawn / noted; the re-listing form `<key> — prior: ruled <ruling> round <N>` carries its original ruling and round; else round = the review's stated round or `prior`). A key is carried only while it provably names the same row: the review's `<!-- specs-review head=… -->` trailer resolves, the record names a rule, that rule's section is unchanged since and the key maps to the same row — otherwise dropped, and with nothing left (or no trailer) there is no file; `manifest.json` `masked.prior` says why |

`tree/`, `evidence/`, `evidence.json` and `attachments/` stay unmasked; `manifest.json` `masked` lists what is
(`masked.files` is the allow-list pass 1 reads; `pass1-prior.tsv` is on it, `row-keys.tsv` is not).

When no rule is touched it exits 0 with the empty forms of these files. Exit 64 on bad input.

### `allure-behavior-snippets`

```
allure-behavior-snippets BEHAVIORS_JSON TARGET_DIR REPORT_URL
```

Reads a generated Allure report's `data/behaviors.json` and writes one SVG per story into
`TARGET_DIR`, each test a line linking to `REPORT_URL<parentUid>/<uid>` (so `REPORT_URL` ends in
`#behaviors/`). `docker compose up` at the repo root runs it over the committed sample report and
serves the result.

## Development

```
python3 -m pytest tests/test_evidence.py tests/test_touched_rules.py tests/test_pack.py tests/test_process_docs.py
cd tests && python3 -m pytest test_unittests.py     # the SVG snippets (relative report paths)
```

A release is a `v<version>` tag on `main`: the tag push publishes the wheel and both images. The
version lives in `pyproject.toml` and `allure_behavior_snippets/__init__.py` (a test holds them
equal; the process image refuses a tag that differs), and the release gets a `CHANGELOG.md` entry.
