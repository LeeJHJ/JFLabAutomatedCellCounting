# Deployment readiness — what stands between this and other machines

**Written 2026-07-30.** Banked so it does not have to be re-derived. This is a
findings list, not a plan: it records what was actually checked and what was found,
so the work can be sequenced whenever it becomes the priority.

**Status: NOT for public use yet.** The pipeline is in development and the science
is not settled (the M3/M5 acquisition question is open). Nothing here should be read
as "ready to release" — it is the map of what release would require.

---

## Sequencing — do the science first

Packaging freezes interfaces. On 2026-07-30 alone, four fresh-project bugs were found
and fixed in one afternoon; freezing the interfaces a day earlier would have frozen
them around those bugs. Finish the stress testing before packaging.

The one exception is **the tooling/data split** (below). It gets strictly harder once
other people have clones and local modifications, and it is cheap right now.

---

## 1. The structural decision: split tooling from data

Today the repo tracks both. 526 tracked files include the pipeline *and* the
experiments — `M3 Hipp1 072326 7scene/`, `wBA 1-3 2-1 072026/`, their `project.qpproj`
files, per-entry `data/<N>/` artifacts, and deployed copies of the scripts. Anyone who
clones this gets the morphine study along with the tool.

What packaging wants:

```
pipeline repo   czi_mip.py, scripts/, notebooks/, docs/, env locks, smoke test
user data       lives anywhere on disk; the tool is POINTED at it
```

Everything else in this document is mechanical and can be done in any order. This one
is architectural, so do it first when packaging starts.

## 2. Hard blocker: absolute paths with a username in them

```
scripts/cockpit_checks.py:237
    QUPATH_BIN = Path("/home/jflab/section-pipeline/tools/QuPath/bin/QuPath")
```

Fails immediately on any other machine. Also present in:

- `notebooks/01_calibrate.ipynb`, `02_batch.ipynb`, `03_animal.ipynb` — `PARAMS["project"]`
  and the `sys.path` insert both carry `/home/jflab/Analysis/...`
- `scripts/crop_to_tissue.py`, `scripts/recover_abba_export.groovy` — in docstring/usage
  examples (harmless to run, but they teach the wrong habit to a reader)

Fix: `QUPATH_BIN` from an environment variable with a sensible default; repo-root
discovery in the notebooks instead of literals. A new user's first act should not be
editing absolute paths in a notebook — that is how a lab ends up with five divergent
copies.

## 3. Reproducibility blocker: there are no environment lockfiles

The only pinned spec in the repo is `requirements-docs.txt`, which covers mkdocs. The
three analysis environments (`braian`, `brainrender`, `deepslice`) have **no pinned
specification anywhere**.

This matters specifically because of the plan to **run several lab machines in
parallel**. If one machine drifts to different versions of numpy / scikit-image /
BraiAn, the same input can produce different numbers. Split a cohort across machines
and software version becomes aliased with animal group — structurally the same
confound as the acquisition-regime problem (`CLAUDE.md`, "Comparability boundary"),
one layer down, and just as invisible.

**The rule that follows is the same one: ONE software environment per comparison.**

Actions:
- `conda env export --no-builds` for each of the three envs, committed, while they are
  known-good
- new machines install from those, not from `pip install` at whatever version is current
- verify by running one section on two machines and diffing the outputs

## 4. The highest-leverage item: a fresh-project smoke test

Create a synthetic project with no `results/`, no `classifiers/object_classifiers/`,
no exports, and run the whole chain against it.

Every bug found on 2026-07-30 was the same shape — code that works on a project a
previous run had already populated, and fails on a genuinely new one:

| Commit | Bug |
| --- | --- |
| `fbcb888` | `find_slices` needed export tables that do not exist yet — notebook section 2 was circular |
| `624a705` | `02_detect_classify` needed a directory a previous GUI session had left behind |
| `641b5dd` | four writes into `results/` that assumed the directory existed |

One test would have caught all of them at once, instead of hitting them one at a time
across an afternoon. The generalization pass was validated against *existing* projects,
so anything a prior run had left lying around was invisible to it.

The same artifact serves three purposes:
- **regression test** for that bug class
- **install verification** on each new lab machine — "run this, get PASS, you are set up"
- **teaching artifact** — a student runs it before touching real data and sees the whole
  chain work on something disposable

## 5. Smaller, but only matters once it leaves this machine

- **LICENSE.** Academic software without one is legally unusable by other institutions.
- **Citation line.** People will ask how to cite it.
- **A version concept.** `.planning/` has milestones but nothing is tagged. Once two labs
  run it, "which version produced these numbers" is a question that needs an answer —
  the same provenance problem as the environment locks.

## 6. Documentation: good, with an audience assumption

The documentation is genuinely strong — every script has a `--self-test`, commit
messages carry rationale rather than just description, `.planning/` preserves decision
history, and config comments hold the reasoning behind values (which is why the
comment-preserving writer in `cockpit_tune.py` exists).

The gap is not quality, it is **audience**. The docs assume the reader is the author,
on this machine, with the tissue in front of them:

- "the operator confirmed 2026-07-25" — meaningful internally, opaque externally
- "judge it by eye" — correct, but a student needs to know *what good looks like* before
  that instruction means anything

That is a rewrite of framing, not of content. The expensive part (capturing the
reasoning) is already done.

## 7. Error messages are documentation for a new user

For students, error text is the manual — it arrives exactly when needed. Today's
`IndexError: list index out of range` from notebook section 2 taught nothing; someone
without the codebase in their head is simply stuck. Errors that name the missing file
and the command that fixes it are worth more than a tutorial page.

The Python cockpit scripts already do this well (`is_dir()` guards, `FileNotFoundError`
naming the path). The Groovy stages are weaker.

---

## Cross-references

- `CLAUDE.md` — "Comparability boundary" (one acquisition regime per comparison; the
  software-version analogue is section 3 above)
- `CLAUDE.md` — "Evidence hierarchy" (SEEN > STRUCTURAL > ASSUMED)
- `docs/runbook/03-tuning.md` — the operator-facing knob reference
- `SECTION_PIPELINE_SETUP.md` — current install procedure, single-machine
