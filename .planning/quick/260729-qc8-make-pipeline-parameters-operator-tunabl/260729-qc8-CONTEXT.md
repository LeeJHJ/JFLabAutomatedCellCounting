# Quick Task 260729-qc8: Make pipeline parameters operator-tunable from one control surface - Context

**Gathered:** 2026-07-29
**Status:** Ready for planning

<domain>
## Task Boundary

Make every tuning knob in the section pipeline reachable and adjustable from one
control surface, so the operator can iterate ("go back and forth") on parameters
without editing source or hunting across files.

Trigger: the operator is mid-run on **M3 Hipp2 072526** (6-scene hippocampus set).
Stitch seams are a real, confirmed property of this slice-set and will be dealt with
by eye — but the seam knobs are currently the *least* reachable in the pipeline
(`DEFAULT_FEATHER_MARGIN = 130` is a module constant at `czi_mip.py:62`, only
reachable via `_stitch_scene_tiles(feather_margin=)`; flat-field correction is applied
unconditionally with no off switch).

IN SCOPE: exposing knobs, one place to see/set them, and a per-project record of what
each tuning round produced.

OUT OF SCOPE: hand-count / ground-truth machinery. The operator validates by eye and
has explicitly said so. Do not build counting-validation tooling.

</domain>

<decisions>
## Implementation Decisions

### Config layout — LOCKED
**One control surface, files stay split.** `BraiAn.yml` and `pipeline.yml` remain
separate files on disk. **D-14 stays intact** (`CLAUDE.md` + the `pipeline.yml` header:
pipeline.yml MUST NOT contain BraiAnDetect detection params such as
sigma/minArea/maxArea/threshold/cellExpansionMicrons).

Explicitly rejected by the operator: a unified `tuning.yml` that generates the other
two. Do NOT unify the configs, and do NOT generate one file from the other.

The control surface is a *reader/writer over the existing files*, not a replacement for
them.

### Run history — LOCKED
**Log each tuning round** to a per-project `results/tuning_log.csv`: the parameter set
plus the key readout numbers, so the operator can compare rounds and revert to a set
that looked right by eye. Source the numbers from the cockpit outputs that already
exist (`results/cockpit_qc_summary.csv`, `results/cockpit_readout.csv`) — do not
recompute them.

### Comment preservation — LOCKED
`BraiAn.yml` and `pipeline.yml` are heavily commented, and those comments carry the
tuning rationale (why span_frac is 0.25, why sigma 2.0 vs 2.5, why classifiers is
empty). A writer that reformats them destroys project knowledge.

Check whether `ruamel.yaml` is available in the `braian` env **before** assuming it.
If it is not available, do not silently reformat — either add the dependency
deliberately or use a targeted line-level edit that provably preserves surrounding
comments. Round-trip fidelity must be demonstrated, not assumed.

### MIP knobs are CLI-only
The MIP-stage knobs live on `czi_mip.py`'s command line, not in any YAML. `--list`
must present them honestly as "pass to czi_mip.py" rather than implying it can set
them.

### Backward compatibility
When the new `czi_mip.py` flags are omitted, behaviour must be **byte-identical** to
today. The M3 Hipp2 MIPs already produced (s1, s2, and whatever the currently-running
job finishes) must remain valid and comparable to any produced later with default
flags.

### Claude's Discretion
- Exact table formatting of `--list`
- Column set of `tuning_log.csv` beyond the required parameter set + key numbers
- Which notebook (`01_calibrate.ipynb` vs a new one) hosts the tuning section
- Where in `docs/` the knob reference table lands

</decisions>

<specifics>
## Specific Ideas

**A. `czi_mip.py` — expose the unreachable knobs**
- `--feather-margin` (default 130, currently `DEFAULT_FEATHER_MARGIN`, `czi_mip.py:62`)
- `--no-flat-field` (flat-field is currently unconditional)
- `--dapi-z N` — force the anchor focus plane instead of the auto var-of-Laplacian
  pick. Motivation: auto selected `Z=0` on scene s1 of this set, and the operator
  needs to be able to override / compare.
- `--scenes N [N ...]` (1-based) — re-cut ONE scene per tuning iteration instead of all
  6 at ~5 min/scene. This is the knob that makes seam tuning by eye practical at all,
  and it makes crash recovery free (a VSCode crash already cost a partial run this
  session).
- Preserve and extend the existing `--self-test` idiom to cover the new paths.

**B. NEW `scripts/cockpit_tune.py` — the control surface**
- `--list` — every knob across all three stages (mip / detect / classify): current
  value, source file, one-line effect note, and which direction to move it
- `--set knob=value` (repeatable) — writes to the CORRECT file, prints `old -> new`
- validate after writing (reuse `scripts/validate_pipeline_config.py`) and deploy via
  `scripts/sync_project.py`
- `--log` — append the round to `<project>/results/tuning_log.csv`
- Project conventions: `argparse` + `RawDescriptionHelpFormatter`, `epilog=__doc__`,
  `type=Path`, `snake_case`, `_`-prefixed helpers, the 0/2/4-space print indent
  convention, and a `--self-test`

**C. Notebook** — a tuning section exposing the same operations. The operator
self-serves runs via the Jupyter cockpit; that is the established surface, so the
notebook is not optional garnish.

**D. Docs** — one reference table of every knob (stage, name, file, default, effect,
direction to move it), following the existing `docs/` structure.

</specifics>

<canonical_refs>
## Canonical References

- `CLAUDE.md` — hard constraints; D-14 config separation; relative-threshold rule;
  one-classification-path rule; CPU-only
- `pipeline.yml` (repo root) — header documents the D-14 separation and the
  `detection_threshold` span-fraction rationale
- `M3 Hipp1 072326 7scene/M3 Hipp1 072326 7 Scene QuPath/BraiAn.yml` — the detection
  params that must stay in BraiAn.yml
- `scripts/sync_project.py` — repo `scripts/` is SOURCE, project `scripts/` is
  DEPLOYED; `pipeline.yml` is merged, never overwritten
- `scripts/validate_pipeline_config.py` — existing validator to reuse
- `scripts/cockpit_threshold.py`, `scripts/cockpit_checks.py` — existing cockpit
  scripts; match their structure and idioms
- `czi_mip.py:62` (`DEFAULT_FEATHER_MARGIN`), `czi_mip.py:178` (`_stitch_scene_tiles`)

## Operational constraint — live job

A `czi_mip.py` background job is running against
`M3 Hipp2 072526/M3 Hippocampus 2 072526 scenes/-001-01_processed.czi`, writing to
`M3 Hipp2 072526/mips/`. **Do not kill it, do not write to that output directory, and
do not edit `czi_mip.py` in a way that would affect an already-running process.**
Editing the file on disk is safe (Python has already loaded it); deleting or truncating
it is not.

</canonical_refs>
