# Changelog

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
