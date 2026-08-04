# Section Pipeline — TRAP2 / Airyscan

Turn ZEN-exported Zeiss CZI mosaics of **TRAP2 vibratome sections** into an **Allen
CCFv3-registered** whole-brain map of cell densities: **TdTomato+** (engram, cytosolic),
**Fos+** (recall, nuclear), and **Double+** (reactivated), counted per atlas region.

Chain: `czi_mip.py` → QuPath → ABBA (Fiji) → BraiAnDetect → per-region tables → figures.

> This is the **section** pipeline. A separate cleared-tissue / light-sheet / ClearMap2
> project answers the same biological question on a different machine. Do not conflate
> the two codebases.

---

## Setting up on a new machine

### 1. Prerequisites (once, per machine)

- Ubuntu x86_64 with a **real X display** — QuPath, Fiji/ABBA and brainrender are
  interactive GUI tools and there is no headless path for registration.
- **Miniforge** (conda). Install per `SECTION_PIPELINE_SETUP.md`.
- ~10 GB free for tools, plus room for image data (multi-GB per session; image data is
  **never** committed to this repo).

### 2. Clone and build the environments

```bash
git clone https://github.com/LeeJHJ/JFLabAutomatedCellCounting.git Analysis
cd Analysis
bash envs/create_envs.sh
```

Three **isolated** environments are created — `braian` (py3.11, analysis + JupyterLab),
`brainrender` (py3.11, 3D atlas rendering), `deepslice` (py3.10, optional local AP
estimation). **Never merge them:** brainrender is fragile with vedo/VTK/allensdk and
will break `braian` if co-installed.

### 3. Verify

```bash
~/miniforge3/envs/braian/bin/python scripts/smoke_test.py
```

Expect **`24/24 checks passed`**. This is the install gate, not a formality — it builds
a throwaway project from nothing and runs the chain against it, so a PASS means the
pipeline works independent of whatever state the workspace happens to be in. Every bug
it pins was originally found by a human hitting it mid-run.

If it fails, stop and fix the install before touching real data.

### 4. GUI tools (a human at the monitor — these cannot be scripted)

`SECTION_PIPELINE_SETUP.md` has the click-path. Summary of what must be installed by
hand:

| tool | version | note |
| --- | --- | --- |
| QuPath | **v0.6.0** — pinned | ABBA + BraiAnDetect extensions are tested against 0.6.x via the BIOP catalog |
| Fiji | latest + JDK | add the **PTBIOP** update site for ABBA |
| elastix | **5.2.0** — pinned | ABBA requires exactly this; needs `LD_LIBRARY_PATH` set |

Also set QuPath's max memory to `-Xmx32G` (or ~half the machine's RAM) in
`QuPath/lib/app/QuPath.cfg`.

Scripts find QuPath at `~/section-pipeline/tools/QuPath/bin/QuPath` by default;
override with `export QUPATH_BIN=/your/path/to/QuPath`.

---

## Running it

**Start here: [`docs/runbook/00-run-a-new-dataset.md`](docs/runbook/00-run-a-new-dataset.md)**
— the end-to-end walkthrough for one dataset, with every command and both GUI seams.

| you want | read |
| --- | --- |
| run a dataset start to finish | `docs/runbook/00-run-a-new-dataset.md` |
| the ABBA registration click-path | `docs/runbook/01-registration.md` |
| QuPath detection detail | `docs/runbook/02-detection.md` |
| working in the QuPath GUI | `docs/runbook/04-qupath-gui.md` |
| a knob, and which way to turn it | `docs/runbook/03-tuning.md` |
| what the stages are + their status | `docs/pipeline-stages.yml` |
| how to image so the data is usable | `ACQUISITION-CHECKLIST.md` |
| where the data currently stands | `NEXT-SESSION.md` |
| durable rules and constraints | `CLAUDE.md` |

There is also a guided launcher for the scriptable steps:

```bash
python3 run_pipeline.py
```

Every Python script here takes `-h` and `--self-test`. The self-tests assert what the
code actually does — if you doubt a script, run it.

---

## Rules that are not negotiable

These are not style preferences; each one is a correctness constraint that cost real
time to learn. Full versions in `CLAUDE.md`.

- **CPU-only.** No CUDA anywhere. Do not install GPU builds of anything.
- **Version pins:** QuPath 0.6.0, elastix 5.2.0. Do not bump without verifying
  extension compatibility.
- **Nucleus-anchored colocalization only.** A cell is TdT+/Fos+/Double+ iff the
  detected nucleus contains the marker centroid. Never proximity or overlap heuristics.
- **Detection thresholds are RELATIVE, never absolute** — the anchor cut is
  `floor + span_frac × (bright_peak − floor)`, re-measured from *each section's own*
  histogram. An absolute cut silently under-detects on any section dimmer than the one
  it was tuned on. That is a comparability bug, not a preference.
- **Pixel size comes from the CZI, never a default.** Every micron-denominated
  parameter downstream is scaled by it.
- **One classification path** — `scripts/02_detect_classify.groovy`, driven by
  `pipeline.yml`. Every `BraiAn.yml` `classifiers:` block is empty by design.
- **One acquisition regime per comparison.** Relative thresholds absorb brightness
  drift but **not** geometry (pixel size, Z depth) or separability (SNR). Animals
  imaged under different parameters are not directly comparable.
- **Aggregate to the animal level before any group comparison.** Sections are serial
  samples of one brain, not independent replicates.
- **Export atlas coordinates in microns, not pixels.**

### Two doctrines worth internalising

**Evidence hierarchy — SEEN > STRUCTURAL > ASSUMED.** What the operator sees on the
image outranks any borrowed band, seed value or reference paper. QC gates print their
evidence tier (`<anatomical>` / `<internal>` / `<assumed>`). Never tune a parameter to
move an `<assumed>` number into its expected band — tune only to match what is visible.

**Tooling advises, never refuses.** QC gates and comparability checks report and rank;
they do not block or silently drop data. Fail loud only on a genuine defect. The line:
refuse on *cannot be computed*, advise on *may not mean what you think*.

---

## Repository layout

```
czi_mip.py                  CZI mosaic -> per-scene hybrid MIP OME-TIFF
run_pipeline.py             guided launcher for the scriptable steps
scripts/                    SOURCE of truth for all pipeline code
  *.groovy                  QuPath stages (deployed into each project)
  cockpit_*.py              the operator's analysis surface
  smoke_test.py             install + regression gate
  sync_project.py           deploy scripts/ + merge config into a QuPath project
notebooks/                  01_calibrate, 02_batch, 03_animal
docs/runbook/               operator documentation
envs/                       pinned requirements + create_envs.sh
<Animal Region Date>/       one directory per imaging session
  raw/  mips/  <...> QuPath/
```

**`scripts/` is SOURCE; `<project>/scripts/` is a DEPLOYED copy.** QuPath can only run
Groovy that lives inside the project. Never hand-copy — use `scripts/sync_project.py`,
which overwrites Groovy wholesale but only *merges* missing blocks into `pipeline.yml`,
so per-slice-set tuning survives.

Image data (`*.czi`, `*.tif`, `*.qpdata`) and per-run exports (`results/`) are
gitignored. A clone gives you the pipeline, not the pilots' data.
