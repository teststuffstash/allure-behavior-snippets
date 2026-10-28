# Test & evidence conventions — the layer under the evidence

[RULES.md](RULES.md) governs the spec pages; this page governs the tests that produce their
evidence and the pipeline that renders it. The briefs cite these sections **by name**; the
definitions live here only. Each repo enforces them with its lint gate (§ The lint gate) and its
test helpers — never by discipline alone.

## Allure taxonomy — one story per rule

- **story == rule ID, exactly** (`API-ORDERS-CREATE`, not `API-ORDERS-CREATE rows`). The story
  label is the join key: `allure-evidence` emits one `<story>.md` fragment per story, and spec
  pages embed it by that name. One story per rule; one rule per story.
- **epic == spec page** (the page's path under the specs root, no suffix); **feature == the page
  section** the rule sits under. Both are derived by the `rule()` decorator — tests never
  hand-write them.
- A test file MAY cover many rules (per-test or per-class marks); a test function carries exactly
  one story.
- **Only system-level tests are evidence.** A rule label belongs on a test that observes the
  system boundary the rule is stated against (for a server rule: the wire — real requests in and
  out). Unit tests guard internals and stay **unlabelled** — they run in the same suite but emit no
  story, so they never render into a rule's fragment or count as coverage. A rule proven only by
  unit tests is *unverified* and says so.
- **Evidence is earned against the shipped artifact.** Where a rule family has both an
  artifact-level run and a mock-backed twin, the story labels belong to the artifact run and the
  twins go unlabelled — a spec page never silently mixes mock and artifact evidence under one
  story.

## The `rule()` decorator — one string, two duties

The repo's test helpers own a single `rule(rule_id)` decorator that applies **both**
`allure.story(rule_id)` **and** `allure.link` to the spec anchor (the spec-site URL pattern is
configured once, in that helper; tests never hand-write spec URLs). It works on a test, a class,
or module-wide as `pytestmark = rule("ID")`. The decorator locates the rule heading by scanning
the specs root for `^#+ <rule_id>` at collection time and **fails collection loudly** when the ID
matches no heading — a mislabelled test cannot produce evidence that files under a ghost rule.
`touched-rules` recognises exactly these shapes.

## The intent column

Every curated example row is `pytest.param(..., id="<intent>")` — the id is **human-authored
intent** ("invalid typeId", "token expired one second ago"), never a restatement of the input. It
forces a position: intent next to data makes the judgment visible and contestable, where an
unlabelled row silently launders observed behaviour into contract. The id is exactly what renders
in the fragment, and what the spec join matches against the spec table's description cell.

Two tiers: **curated example rows (≲8 per rule) render in fragments; bulk / census
parametrization aggregates to counts only.** When a rule accretes more than ~8 curated rows, split
the rule (rule 2), do not grow the table. An evidence-labelled parametrized test with
auto-generated ids is an input restatement by construction — the lint gate refuses it.

**The header is the parameter list.** A decision table's description cell is the `pytest.param`
id **verbatim** (`⚖` included — the flag is part of the intent); every other header cell is a
parametrize argname verbatim, and each cell is the value that parameter takes in that case (a
legend above the table decodes short literals; the test decodes against the same legend). That
equality is what lets the join compare a cell to the recorded parameter and mark `spec ⇢ actual`,
and what lets a reader match a report row to a spec row without the source open. A header column
no case carries as a parameter is **unthreaded**; a description cell the join reaches only by
substring is **unkeyed** — both are lint (§ The lint gate), never tolerance. Inputs a world
already describes are named by the world (a `world` column holding its name), never restated cell
by cell.

**Expected columns end in `?`** (v0.6.3): inputs first, expected outputs last, and every expected
column's header carries a trailing `?` — `title?`, `rc?`, `events_include?` — which is the
parametrize argname `expected_title` / `expected_rc` / `expected_events_include` in pytest (the
join maps the one to the other and keeps the role in the joined row). Outputs are errors, events
and side effects as much as return values. The `description` column is neither: it is the
row's intent, explanatory metadata. The older `||` divider between inputs and outputs is still
read, but it renders as an empty column in ordinary Markdown; a page that migrates drops it.

**Rows read without their description.** The input and expected cells alone must distinguish the
case; the description says why the case matters; the requirement prose states the general rule.
A table shaped `description | body_text?` fails this — hiding the description leaves outcomes
without the conditions that produce them — so the input that varies between rows is a column
(`meta_title`, `body_heading`), never only words in the description. A world can supply the
inputs (`world` column), but a fixture name alone is not a distinguishing condition when two rows
of the same world differ. The reviewer's first pass reads the table this way (briefs/rows.md
check 10).

**Columns are named by what is observed, and the comparison is equality unless the name says
otherwise.** An expected column names the observable (`the line written`, `status`, `the
answer's keys`). `contains` / `holds` / `includes` in a column name promises a substring check, so
a test that asserts equality under such a name misstates the contract — name the column for what
the then-step compares. The inverse holds too: a column named as the observable (`log_line`) whose
then-step checks containment promises more than is proven — name the fragment (`log_line_contains`,
`fragment`). One vocabulary per rule: the same observable is not "the line" in one
table and "the log" in the next. Prose never gets to explain a column; a column a reader cannot
place from the requirement text alone is misnamed (rule 11).

## Evidence row identity = (rule ID, world, case)

Expected behaviour is a function of (system, **world**) — an example row that does not name its
fixture set is lying by omission. Every test names its world (the committed walk-through data of a
use case, a fault-injectable fake upstream, a seeded policy state); the world name appears in the
rendered row, and the world files are **linked from the spec page as spec text** — worlds are
personas, public and discussable.

A rule whose evidence spans more than one world carries the world on every case; a single-world
module declares it once (module docstring + the spec page's fixture link). The tooling reads the
world from an Allure `world` label, else from a `world: <name>` mention in the case id or an
attachment name — prefer the label; an id prefix like `"uc-1: invalid typeId"` reads well but is
invisible to the tooling (the reviewer's `WORLD_UNNAMED` then rests on judgment).

## Tests speak wire format, never domain models

Test payloads are dicts / strings / lists — the wire format — mutated from a known-good literal
with one mechanism: `good_payload() | {"date": "0000-00-00"}`. No typed models in test code: a
typed model makes exactly the garbage a negative test must send *unrepresentable*. Data literals
live in the test file. **Fixtures are for services and environment** (a DB handle, a fake
upstream, a base URL), never for data.

## The helper razor

- **Action helpers** (arrange only): assert success **internally** — die loudly in arrange — and
  return ids. Never used for the action under test. No flags, no modes.
- **Request-definition helpers** (usable in the act step): one function per interface returning an
  *unexecuted* dict of request kwargs — URL + defaults, **no verb, no assertion**. The test owns
  the send.
- The action under test is **always an inline raw client call** in the test body.

Helpers may grow **observability** (named steps, attachments) — never request-building cleverness.

## Prime rule of reporting: no system interaction goes unlogged

- Every request the system under test receives or sends attaches its request + response bytes
  (an observing client wrapper does this per call — including inside action helpers); every DB
  verification attaches the statement + returned rows; every event stream a claim rests on is
  attached.
- **Step boundary — given, when, then.** A case's top-level steps read:
  - *given* — setup through action / request-definition helpers (§ The helper razor), each step
    named with its data, the world attached once;
  - *when* — exactly **ONE** step: the inline call under test, its bytes (request / response, or
    the step's events) under it;
  - *then* — **one step per claim**, named with the claimed value (`Then: status = 429`, never
    `status`), wrapping the assertion in the repo's `verdict()` helper so the step itself goes
    red / green.

  A step exists where a noun changes state or a verdict is pronounced — nowhere else; names carry
  real data.
- **Names thread the spec column's VALUE**: the same column name runs through the given
  attachment, the when step name and the then comparison keys — the thread is what lets a reader
  follow one value through the case. `allure-evidence` renders it as a per-case thread table and
  bolds the threaded values.
- **Generic writers** (SQL, event streams, request bytes) never attach flat at test level — only
  under the step whose claim they support.
- **Hygiene codes** (reviewer notes; defined here only — [briefs/evidence.md](briefs/evidence.md)
  applies them):

  | Code | Fires when → fix |
  |---|---|
  | `STEP_FLAT` | no `allure.step` at all, or the verdict is not a step (values hide in a step NAME) → verdict = a `verdict()` step carrying the compared values |
  | `STEP_NOISE` | > ~8 top-level steps, or steps that are neither given / when / then → nest, attachments under their step |
  | `NAME_BLANK` | a step / attachment name without data (`verdict`, `events`, `attachment 1`) → names carry the key value |
  | `ATTACH_BULK` | attachment > ~256 KB, or > ~8 attachments on one case → attach the slice the row is about, link the rest |
  | `PARAM_BLOB` | parameter > ~400 chars, or a dict / list where the row needs one value → split into columns, or attach and keep the key |
  | `CONTEXT_TAX` | verifying one row's cells needs > ~2 attachments opened → say which cells and what single attachment would answer them |
  | `THREAD_BROKEN` | a parameter column appears in none of the given / when / then steps → name the step after the value it carries |

  Thresholds are judgment marks, not counters: a 9-step case whose steps are all state changes is
  fine; a 3-step case with a blank verdict is not.
- **Run metadata is a convention, not polish**: every report carries `executor.json` (the CI run
  URL) and `environment.properties` (§ The head/artifact stamp). **The report is the deliverable;
  the green check is merely its summary.**
- **The seeded world attaches at seed time**: session fixtures attach their seed source (world /
  seed files + sha256), so the (rule, world, case) identity is inspectable in the report.
  Test-local world mutations attach the derived data.

## The head/artifact stamp

The fragment on a spec page is a claim; the archived report is the proof; the stamp binds the
proof to what was tested. `environment.properties` carries:

- `git.commit=<sha>` — the commit the suite ran at. Evidence counts for a PR only when this names
  the PR's head; any other commit is **stale** = unverified (rule 5).
- `image.digest=<sha256:…>` — **only** when the suite ran AGAINST that built image and the run
  recorded its digest itself. **PR-head evidence is not built-artifact evidence**: a digest
  written into the properties by a step that did not exercise the image proves nothing about
  the image. Where a repo's rules are stated against its shipped artifact, the artifact run
  carries the labels (§ Allure taxonomy) and the digest; a run without a digest is PR-head
  evidence and says so.

`evidence-pack` reads both keys and states the result in the digest (`Stamp:`) and the manifest.

## Evidence blocks on spec pages

A rule section's evidence block is one line — the transcluded fragment — wrapped in `<details>`
(collapsed by default; the requirement tables are the reading path). Each published site shows
*its own run's* evidence — the master site master's, a PR preview that PR's run; a PR run never
writes master's "latest".

```markdown
<details markdown="1"><summary>Evidence — latest run</summary>

--8<-- "<RULE-ID>.md"

</details>
```

**A table that joins becomes the evidence.** When a rule's spec table is keyed by its tests (the
description cell IS the test id, § The intent column), the site build may rewrite that table in
place (`allure-evidence --spec-page-out`): the spec's own columns, the description linking to its
test in the report, `∅` / `❌` / `⚠` on a row that is not fine, `spec ⇢ actual` in a cell the test
contradicts.

A rule with no evidence yet carries the explicit marker line instead — visibly unverified
(rule 10), never silently blank: `_Evidence: none yet — unverified._`

The `--8<--` transclusion is the single sanctioned snippet include: the fragment is *derived
reality* (regenerated every run), never intent.

## The lint gate (deterministic, merge-blocking)

Each repo's gate holds, at minimum:

1. every story label in test code matches an existing rule heading under the specs root (heading
   text == ID, exactly; ~~tombstones~~ are the one tolerated decoration);
2. every rule heading has an evidence block **or** the explicit unverified marker;
3. every link and `#anchor` in the built site resolves;
4. every evidence-labelled parametrized test carries explicit intent ids;
5. on a page with an index table, every rule section is a row of it;
6. the spec ⇄ test join is exact (§ The intent column): per rule, four counts — `row-unkeyed`
   (a description cell no case id equals), `header-unthreaded` (a column no matched case carries
   as a parameter — a `name?` column under `expected_name`), `cell-mismatch` (a cell ≠ its same-named parameter), `case-unspecified` (a
   labelled case no table row names) — held by the ratchet below; a `⚑ gap` / `🚧 WIP` row is
   rule-10 incompleteness, not an unkeyed row.

Rule 11 (prose describes the system, unproven facts are marked) is deliberately NOT a gate item:
prose rules are read, not counted — a word lint makes requirements read like code.

Report-shape debt (attachments outside steps, steps with no evidence, over-long descriptions) and
the join counts above are held by **ratchets** against a committed baseline — exceeding fails,
equal or lower passes, the fixing PR lowers the line; never a big-bang gate.

## Issue acceptance — rows run at HEAD

Every bullet under an issue's `## Acceptance` names something CI, the artifact run, or a command
in the worker's environment can execute on the PR branch. An observation only production can make
is a **closeout** condition (`## Closeout`), the PR says `Refs #N` for it, never `Fixes #N`. The
rows brief grounds check 1 in this text; `evidence-pack --issue-intent` carries it into the pack.
