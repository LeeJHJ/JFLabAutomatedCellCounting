# Testing Patterns

**Last verified against the codebase:** 2026-07-29
*(Supersedes the 2026-06-30 version, which described a `pytest` layout that was never
built, pointed at an out-of-repo script that has since been superseded, and reported
"0% automated coverage" — all three are now wrong.)*

## Test framework

**Runner:** none, deliberately. The project convention is a **`--self-test` flag on
every script**, asserting against synthetic in-process data. No pytest, no `tests/`
directory, no fixtures on disk.

Why this shape rather than pytest: the units worth testing here are numeric
transforms (projection, thresholding, rollup arithmetic) whose inputs are cheap to
synthesise in a few lines, while everything else is either a GUI step or needs a
multi-GB image. A self-test that ships inside the script it tests cannot drift away
from it, and an operator can run it on the acquisition machine with no dev install.

## Running the tests

Every one of these must exit 0 before a script is trusted:

```bash
conda activate braian          # or prefix each with: conda run -n braian

python3 czi_mip.py                      --self-test   # projection / stitching / OME-XML
python3 scripts/cockpit_threshold.py    --self-test   # detection-threshold rule + plots
python3 scripts/cockpit_checks.py       --self-test   # QC gates
python3 scripts/sync_project.py         --self-test   # project deploy + config merge
python3 scripts/validate_pipeline_config.py --self-test   # pipeline.yml contract
python3 scripts/crop_to_tissue.py       --self-test   # tissue mask
python3 run_pipeline.py                 --self-test   # launcher menu (prints, runs nothing)
```

Groovy scripts have no self-test — QuPath's script engine is not scriptable from the
CLI in this setup. They fail loud instead: every one validates its `pipeline.yml`
keys up front and aborts with the exact missing key rather than proceeding on a
default. See `02_detect_classify.groovy` and `run_braian_detection.groovy`.

Notebooks are checked by executing them headless with `dry_run: True`, which
exercises every cheap cell while expensive cells only print the command they would
run:

```bash
conda run -n braian python3 -c "
import nbformat; from nbclient import NotebookClient
nb = nbformat.read('notebooks/01_calibrate.ipynb', as_version=4)
NotebookClient(nb, timeout=600, resources={'metadata': {'path': 'notebooks'}}).execute()"
```

## Which script is canonical (important)

There are **two** CZI→MIP scripts on this machine. Use the in-repo one.

| | path | status |
|---|---|---|
| **canonical** | `/home/jflab/Analysis/czi_mip.py` | current. Hybrid projection (single sharpest DAPI plane + full-Z marker MIP), per-scene bbox isolation, tile-stitch with feathered seams, flat-field correction, pixel size read from CZI metadata, `--self-test`. |
| superseded | `/home/jflab/section-pipeline/scripts/czi_to_mip.py` | **do not use.** Older, plain per-channel MIP over all Z. |

Running the superseded one reintroduces the DAPI over-projection that fused touching
nuclei into blobs — the exact problem hybrid projection was built to fix (see
`IMAGING_OPTIMIZATION_NOTES.md`: nucleus separation degraded monotonically from
single-plane → 2 → 3 → 6 planes). It is retained only as history.

## What the self-tests actually cover

`czi_mip.py` — the var-of-Laplacian sharpest-plane selector picks the known-sharp
plane; hybrid output is byte-identical to `stack[dapi_z]` on the anchor and to
`np.max(stack, axis=0)` on markers; plane selection is independent per scene;
tile-stitch never leaks a neighbouring scene's pixels and resolves seams to a value
strictly between the two tiles; flat-field correction flattens a known radial
vignette; OME channel colours and the `PhysicalSizeX` round-trip hold; the
`--isolate auto/region/tiles` decision table including its refusal case.

`cockpit_threshold.py` — the span-fraction arithmetic
(`floor + span_frac × (bright − floor)`); that the historical absolute cut of 700
corresponds to fraction 0.256 on the section it was tuned on, so the default 0.25
reproduces the operator's own visual call; robust-z outlier detection across a
series; that an out-of-range cut is FLAGged; headless plot rendering; empty-project
and absent-config degradation.

`sync_project.py` — config-block extraction keeps its comment paragraph and does not
bleed into neighbouring keys; a project's own marker set and `k_robust` survive a
sync untouched; retired scripts are removed; deploy is byte-identical and idempotent;
`--dry-run` writes nothing; a non-QuPath directory is refused.

`validate_pipeline_config.py` — the full `pipeline.yml` contract: marker/compartment
vocabulary, `Double+` emitted only when ≥2 non-anchor markers are declared, the
per-marker background-subtracted measurement-key strings, and the
`detection_threshold` block including the `resolution_level == 0` requirement.

## Validation that is not automatable

These are operator judgment and stay manual:

1. **Registration fit** — ABBA overlay against tissue anatomy. No ground-truth
   metric exists; established doctrine is operator visual review (tilt before
   elastix, not more spline control points).
2. **Detection sanity on one section** — tune on ONE section before scaling
   (`CLAUDE.md`). The cockpit's QC gates report numbers next to PASS/FLAG verdicts;
   they are advisory prompts, not a gate that can be passed mechanically.
3. **Threshold placement** — `notebooks/01_calibrate.ipynb` §3 plots where the cut
   lands on the real histogram. Judgment call, made while looking at the data.
4. **Scene→section identity** — that MIP `s3` really is the third physical section.
   Only the operator can confirm this against the slide.

## Real gaps

1. **No ground-truth cell counts.** Measured density (2,500–5,500/mm²) sits above the
   500–2,000/mm² literature seed while nucleus area (40–50 µm²) sits below the
   50–150 µm² seed — smaller objects and more of them, with total nuclear area
   roughly conserved, which is the signature of watershed splitting nuclei. Nothing
   in the pipeline can detect this; it needs hand counts on one section.
2. **No end-to-end regression fixture.** The v1.0 numbers (213,106 cells; CA1
   bilateral 6,354; `grey` ≈ 0) are recorded in prose in
   `.planning/milestones/v1.0-phases/04-.../04-VALIDATION-RECORD.md`, not asserted by
   anything. Two of them are canaries for real historical bugs: a non-trivial `grey`
   count means the CR-01 region-labelling bug is back; an all-`Negative`
   classification means the D-05 measurement-key bug is back.
   Note that the TdT-derived figures in that record predate the 2026-07-25 move to
   whole-cell TdTomato measurement and are **not** reproducible as written.
3. **Atlas coordinate units** are not asserted anywhere — exports must be µm, and
   `AtlasTools` returns mm (×1000 needed).

---

*Verified by reading the scripts and running every `--self-test` listed above, 2026-07-29.*
