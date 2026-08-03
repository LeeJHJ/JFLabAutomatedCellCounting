# Engineering handoff — unfinished work

**Written 2026-08-03.** Companion to `NEXT-SESSION.md` (which covers data state and the
open scientific question). This file is only the engineering backlog: self-contained
tasks that need no new imaging and no judgement calls about the biology.

Read `NEXT-SESSION.md` first for context, then this.

---

## Task 1 — fresh-project smoke test  ★ highest value

**The problem it solves.** Ten bugs in four days were all the same shape: code that
works on whatever state the workspace happens to be in, and fails on a genuinely new
one. Each was found by a human hitting it mid-run.

| commit | bug |
| --- | --- |
| `fbcb888` | `find_slices` needed export tables that do not exist yet — the calibrate notebook was circular |
| `624a705` | `02_detect_classify` needed a directory a previous GUI session had left behind |
| `641b5dd` | four writes into `results/` assumed the directory existed |
| `f9f79f9` | `--scenes` broke per-scene tile counting |
| — | single-scene CZI rejected outright |
| — | `sync_project --all` enumerated scratch fixtures as real projects |
| — | session-vs-animal: three imaging sessions counted as three animals |
| — | template config did not carry per-slice-set tuning to a new project |

**What to build.** A test that constructs a synthetic project from nothing — no
`results/`, no `classifiers/object_classifiers/`, no exports, no prior run — and
exercises the whole chain against it.

Suggested shape (adapt freely):

- `scripts/smoke_test.py` with `--self-test` semantics matching the rest of the repo
  (argparse + `RawDescriptionHelpFormatter`, `epilog=__doc__`, `type=Path`, snake_case,
  `_`-prefixed helpers, the 0/2/4-space print indent convention)
- builds a temp project: `project.qpproj` with a couple of image entries, a
  `pipeline.yml`, a `BraiAn.yml`, an ontology JSON, and **nothing else**
- runs every stage that does not need QuPath or real images, and asserts each either
  succeeds or fails with a *clear, actionable* message — never a bare `IndexError`
- specifically asserts the eight cases in the table above stay fixed

**Why it is worth more than it looks.** The same artifact serves three purposes:
regression test for that bug class, install verification on a new lab machine ("run
this, get PASS, you are set up"), and a teaching artifact a student runs before
touching real data.

**Constraint.** QuPath stages cannot run headless in a test without real images. Either
stub them, or scope the smoke test to the Python layer and drive the Groovy stages from
a separate, optional integration test. The Python layer is where most of the bug class
lived, so scoping down is acceptable.

---

## Task 2 — figures from clean data  ⚠ scope carefully

Data is ready in `results/animal/clean/`. Scripts are written and self-tested:
`scripts/figure_region_panels.py`, `scripts/figure_group_comparison.py`.

**BUILD:**

- single-group panels for the M3 cohort and for M5, five metrics each
  (`figure_region_panels.py --separate --ontology <project ontology>`)
- a figure showing the SAME regions under BOTH normalisations (÷ control regions and
  ÷ anchor floor), which makes the ambiguity visible instead of hiding it
- `scripts/chance_methods.py --plot` — the five definitions of chance side by side

**DO NOT BUILD, yet:**

- an M3-vs-M5 comparison bar chart. The direction is undetermined (see
  `NEXT-SESSION.md` §2): normalising by control regions makes M3 look higher,
  normalising by the measured anchor floor makes M5 look higher, and both are
  defensible. A two-group chart asserts a direction no matter what the caption says,
  and it WILL be screenshotted out of context. Wait for the `M5a_s1` re-image.

Use `--ymax` to lock y-scales across groups so panels are visually comparable — without
it, a lower-valued group's bars fill its own panel and read as equal.

---

## Task 3 — notebook portability

`notebooks/01_calibrate.ipynb`, `02_batch.ipynb`, `03_animal.ipynb`:

- `PARAMS["project"]` still defaults to the **wBA** project, not M3 or M5
- absolute `/home/jflab/Analysis/...` paths in `PARAMS` and in the `sys.path` insert
- `scripts/cockpit_checks.py:237` — `QUPATH_BIN` is a hardcoded absolute path with a
  username in it

Fix: repo-root discovery instead of literals; `QUPATH_BIN` from an environment variable
with a sensible default. A new user's first act should not be editing absolute paths in
a notebook — that is how a lab ends up with five divergent copies.

Full context in `DEPLOYMENT-READINESS.md`.

---

## Task 4 — decide the fate of `render_engram_cloud.py`

The only unreferenced script in `scripts/`. Nothing calls it. It needs stage
`export_coords` (`04_export_atlas_coords.groovy`, status `optional`) to produce input.

The 3D atlas-space point cloud is a stated project goal, so this is probably unfinished
rather than abandoned — but it should either be wired up with a worked example or
marked clearly. It is currently `status: unwired` in `docs/pipeline-stages.yml`.

---

## Ground rules (same as the main handoff)

- **Tooling advises, never refuses.** Report and rank; do not block or drop data. Fail
  loud only on a genuine defect — refuse on *cannot be computed*, advise on *may not
  mean what you think*.
- **Every new script gets a `--self-test`** that asserts what the code actually does,
  not what it was hoped to do. Two methods this week failed their own self-tests and
  the failures were the useful part.
- **Match the surrounding conventions** — comment density, naming, the print indent
  convention. `scripts/cockpit_tune.py` and `scripts/local_chance.py` are recent
  examples of the house style.
- **Do not touch** `results/animal/clean/` or any `pipeline.yml` / `BraiAn.yml` without
  saying so — those encode analysis decisions made deliberately.

---

## Suggested order

1, then 3, then 2, then 4. Task 1 protects everything else; task 3 is small and unblocks
other machines; task 2 is quick but scope-sensitive; task 4 is a decision more than a
build.
