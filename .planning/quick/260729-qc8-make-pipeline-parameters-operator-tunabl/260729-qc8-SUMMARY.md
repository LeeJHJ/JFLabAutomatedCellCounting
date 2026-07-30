---
quick_id: 260729-qc8
slug: make-pipeline-parameters-operator-tunabl
description: Make pipeline parameters operator-tunable from one control surface
date: 2026-07-30
status: complete
tasks_completed: 3
commits:
  - b20fa68 feat(czi_mip) expose seam/focus/scene knobs on the CLI
  - 78c9ee2 feat(cockpit) cockpit_tune.py -- one control surface for every knob
  - a06c2c6 docs(tuning) knob reference table + notebook tuning surface
---

# Quick Task 260729-qc8 — Summary

## What was built

**1. `czi_mip.py` knobs (b20fa68).** Four previously-unreachable knobs now on the CLI:
`--feather-margin`, `--no-flat-field`, `--dapi-z`, `--scenes`. Omitting all four
reproduces prior behaviour byte for byte — asserted in `--self-test` case (j), which
also proves each knob measurably changes its output.

`--scenes` is what makes seam tuning practical: one scene (~5 min) per iteration
instead of a 6-scene series (~30 min). It also makes crash recovery free, which this
session needed after VSCode died mid-run.

**2. `scripts/cockpit_tune.py` (78c9ee2).** `--list` / `--set` / `--log` over all
three stages. Configs stay split on disk.

**3. Docs + notebook (a06c2c6).** `docs/runbook/03-tuning.md` (every knob, default,
effect, direction) and two new sections in `01_calibrate.ipynb` (1b: list/set;
7: record the round).

## Decisions worth carrying forward

**ruamel.yaml is not installed in the `braian` env**, and a PyYAML round-trip deletes
every comment in `BraiAn.yml` / `pipeline.yml` — comments that carry the tuning
rationale (why `span_frac` is 0.25 and not the old absolute 700, why `sigma` is 2.0,
why `classifiers:` is empty *on purpose*). Rather than add a dependency to one of
three deliberately isolated envs for a config writer, the writer reads with PyYAML and
writes by targeted line-level scalar substitution.

Verified on the real configs: setting three knobs changed exactly three lines, every
comment survived, line count unchanged, and the trailing-comment column is preserved
when the new value is shorter.

**D-14 is asserted, not merely respected.** `--self-test` case (g) fails if any
detection knob is ever routed into `pipeline.yml` or any classification knob into
`BraiAn.yml`. This was the constraint most likely to be broken by a careless registry
edit, so it is now a test rather than a comment.

**MIP knobs are shown but not settable.** They are `czi_mip.py` arguments with nowhere
to persist; `--set` refuses them with the correct command instead. Pretending to store
them would be a lie costing a re-run to discover.

## Verification

- `czi_mip.py --self-test` — green, incl. new case (j)
- `cockpit_tune.py --self-test` — green, incl. comment-preservation and D-14 cases
- `--list` against the real M3 Hipp1 project — reads all 12 stored knobs correctly
- `--set` on a scratch copy — one line changed per knob, comments intact
- `--log` over three rounds — stable column order, `round` first
- New `czi_mip.py` flags parse and their guards fire on bad input

## Deviations from plan

None in scope. The plan's ordering held; `sync_project.py` needed no change because it
deploys `*.groovy` only — Python cockpit scripts run from the repo, matching
`cockpit_threshold.py`.

## Not done (deliberately)

Hand-count / ground-truth validation machinery — the operator validates by eye and said
so explicitly. The open question of whether detection over-splits nuclei is therefore
still open; `docs/runbook/03-tuning.md` records that the reference area/density bands
were imported from a different acquisition and have never been checked against hand
counts on this data.
