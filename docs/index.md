# Per-Region Cell-Counting Pipeline — Operator Tutorial

**Turn a registered brain section into a per-atlas-region count table of DAPI+/marker+/Double+ cells.**

## Read me first

This is a step-by-step checklist for the whole pipeline, from a raw microscope
export to a per-region table you can hand to a statistician. It is written for
an operator standing at the microscope-analysis workstation, not a programmer.

Two kinds of steps appear below, always tagged:

- **`[GUI]`** — you click around in an application (Fiji or QuPath). No typing
  commands. These steps cannot be automated because they require you to look
  at the image and make a judgment call (is the registration good? does this
  look like one nucleus per blob?).
- **`[SCRIPTABLE]`** — a single command does the work. You can either run the
  command yourself (shown under each step), or use the friendly launcher
  (`run_pipeline.py`, see the callout below) which prompts you in plain
  English and runs the command for you.

Every step reads its output from the step before it — if a step fails, the
error message tells you what to do (usually: go back one step).

> **The friendly launcher.** `run_pipeline.py` (repo root) is a numbered menu
> that runs every `[SCRIPTABLE]` step for you, with plain-English prompts, and
> tells you exactly what to do in the app when it reaches a `[GUI]` step. Run
> it with:
> ```
> python run_pipeline.py
> ```
> You never need to remember a `conda run` command — the launcher does that
> part. It never touches QuPath or Fiji itself; at each `[GUI]` seam it prints
> a "stop and do this in the app" message and waits for you.

## First-time setup

1. Install the conda environments and GUI tools once, per
   `SECTION_PIPELINE_SETUP.md` (QuPath v0.6.0, Fiji + ABBA, elastix 5.2.0, the
   `deepslice`/`braian`/`brainrender` conda environments). This is a one-time
   machine setup, not a per-slice-set step.
2. **How to view this tutorial as a website.** This page is part of an MkDocs
   Material site (searchable, with a sidebar). Preview it locally:
   ```
   pip install -r requirements-docs.txt
   mkdocs serve
   ```
   then open <http://127.0.0.1:8000> in a browser. Leave `mkdocs serve`
   running in a terminal while you read — it live-reloads as the docs change.
   (See "Publish this tutorial" at the bottom for the optional step of putting
   this site on the public internet — off by default.)

## Marker config (`pipeline.yml`)

Before running anything, declare **what you're looking for on this slice
set** in `pipeline.yml` (repo root). This one file drives every downstream
script — nothing marker-specific is hardcoded in the scripts themselves.

```yaml
anchor:
  name: "DAPI"                # the nucleus/segmentation channel
  channel: "DAPI-T4"           # must match the image's channel name exactly

markers:                       # 1..N entries — declare only what's on THIS slice set
  - name: "Fos"
    channel: "AF488-T3"
    compartment: "nuclear"      # Fos is a recall marker, read on the nucleus itself
  - name: "TdT"
    channel: "AF568-T2"
    compartment: "cytoplasmic"  # TdTomato is cytosolic, read on the cytoplasmic ring

exclude_acronyms: ["DG-sg", "VS"]   # atlas regions to skip (too dense / not tissue)
k_robust: 3.0                        # positive-threshold strictness (higher = stricter)
ring:
  gap_um: 1.0                        # cytoplasmic ring: gap from the nucleus edge
  width_um: 8.0                      # cytoplasmic ring: ring thickness
```

Key things to know:

- **`compartment` must be exactly `"nuclear"` or `"cytoplasmic"`** — nuclear
  markers (e.g. Fos, a recall marker) are measured on the segmented nucleus
  itself; cytoplasmic markers (e.g. TdTomato, which is cytosolic) are measured
  on a ring built outward from the nucleus. This wiring is fixed by project
  rule (nucleus-anchored colocalization, never proximity/overlap heuristics) —
  `pipeline.yml` only declares *which* marker gets *which* treatment.
- **Double+ only appears when you declare 2+ markers.** If a slice set only
  has one marker (TdTomato, no Fos immunostain run on it), declare just that
  one marker — the whole pipeline degenerates cleanly to DAPI+/TdT+ only, with
  no Fos or Double+ columns anywhere downstream.

**Worked TdT-only example** (a slice set with no Fos channel at all):

```yaml
anchor:
  name: "DAPI"
  channel: "DAPI-T4"
markers:
  - name: "TdT"
    channel: "AF568-T2"
    compartment: "cytoplasmic"
exclude_acronyms: ["DG-sg", "VS"]
k_robust: 3.0
ring:
  gap_um: 1.0
  width_um: 8.0
```

With this config, every downstream table has **DAPI+ and TdT+ columns only**
— no `Fos+` column, no `Double+` column, no `NaN`/placeholder values. This is
verified by `scripts/validate_pipeline_config.py --self-test`, which builds
exactly this kind of TdT-only config and a two-marker Fos+TdT config and
asserts the schema differs correctly between them.

`pipeline.yml` is separate from `BraiAn.yml`: `BraiAn.yml` stays
BraiAnDetect's *detection* parameters file (sigma, min/max area, histogram
threshold, cytoplasmic expansion radius — how cells are found); `pipeline.yml`
is the *marker/region* config (what the found cells are, and which regions to
skip). Validate your config any time with:

```
conda run -n braian python scripts/validate_pipeline_config.py --config pipeline.yml
```

This prints the full derived contract (measurement keys, class vocabulary,
table columns) and fails loud with the exact missing/invalid key if something
is wrong — before any groovy script runs against a broken config.

## The pipeline, stage by stage

### 1. czi → MIP `[SCRIPTABLE]`

Convert the raw Zeiss CZI mosaic (or multi-scene CZI) into single-plane,
multi-channel OME-TIFFs that QuPath can import.

```
conda run -n braian python czi_mip.py \
  --channels "TdTomato-AF568" "Fos-AF488" "DAPI"
```

**Always pass `--channels` explicitly** in this exact order — the CZI reader
(`aicspylibczi`) returns channels in a different order than the file's own
metadata claims, and passing the override is the only fix.

### 2. ABBA atlas registration `[GUI]`

Register each section to the Allen CCFv3 atlas in Fiji. This is one of the
two most error-prone manual steps in the whole pipeline — see the detailed
walkthrough: **[docs/runbook/01-registration.md](runbook/01-registration.md)**.

Short version: open Fiji, run ABBA (`Plugins > BIOP > Atlas > ABBA`), import
the image **from the QuPath project** (not directly from disk — see the
detail doc for why this matters), run DeepSlice, manually adjust the slicing
angle, then export:

```
Plugins > Atlas > Multi Image To Atlas > Export
  -> "ABBA - Export Registrations To QuPath Project"
```

This writes `ABBA-Transform-*.json` and `ABBA-RoiSet-*.zip` into the QuPath
project's `data/<entry>/` directory — the files step 3 reads.

### 3. Load ABBA ROIs into QuPath `[SCRIPTABLE]`

Copy `scripts/01_load_abba_rois.groovy` into the QuPath project's `scripts/`
folder (see "Deploy" below), then in QuPath:

```
Automate > Run for project...  (select 01_load_abba_rois.groovy)
```

This loads the atlas region annotations exported by Fiji/ABBA into the QuPath
entry and resolves the parent/child region hierarchy (`resolveHierarchy()`) —
required for the per-region rollups in step 6.

### 4. BraiAnDetect detection `[GUI]`

Detect nuclei and measure per-channel intensities using BraiAnDetect's
built-in QuPath detector (CPU-only, no Cellpose/StarDist). This is the other
error-prone manual step — see the detailed walkthrough:
**[docs/runbook/02-detection.md](runbook/02-detection.md)**.

Short version: in QuPath, open the entry with ABBA ROIs loaded, then run:

```
Automate > Script editor > Run   (on run_braian_detection.groovy)
```

Detection parameters (sigma, min/max nucleus area, histogram threshold,
cytoplasmic expansion radius) live in `BraiAn.yml`, **not** `pipeline.yml`
(see the "Marker config" section above). Tuning is a delete-detections →
edit `BraiAn.yml` → re-run loop — the detail doc walks through it.

### 5. Classify `[SCRIPTABLE-authored / GUI-run]`

Deploy `scripts/02_detect_classify.groovy` into the QuPath project's
`scripts/` folder, then in QuPath:

```
Automate > Run for project...  (select 02_detect_classify.groovy)
```

This reads `pipeline.yml`'s declared marker set, computes a per-marker
background-subtracted measure, derives a self-calibrating positive threshold
(robust median + `k_robust`·1.4826·MAD) per marker, and assigns each cell a
class (`<marker>+`, `Double+` only if ≥2 markers are declared and positive,
`Negative`, or `Excluded` if it falls in an `exclude_acronyms` region). Safe
to re-run any time detections already exist — it just overwrites classes.

### 6. Export per-region table `[SCRIPTABLE-authored / GUI-run]`

Deploy `scripts/03_export_region_table.groovy`, then:

```
Automate > Run for project...  (select 03_export_region_table.groovy)
```

This is the single consolidated export script (it replaces the retired
`classify_markers.groovy`, `export_region_dapi_reference.groovy`, and
`03_export_val01_metrics.groovy` — see "Retired scripts" below). Per entry it
writes three outputs:

1. **`results/<entry>__percell_export.tsv`** — one row per detected cell:
   class, atlas region, nucleus area, centroid, and one `<marker>_bgsub`
   column per declared marker.
2. **`results/<entry>__region_table.tsv`** — one row per atlas region (leaves
   *and* parent rollups, `is_leaf` flagged), with count + density
   (cells/mm²) columns per declared category (DAPI+/marker+/Double+). Parent
   rows are the leaf-summed ancestor-walk rollup, never re-counted
   independently — this is the fix that guarantees no cell is silently
   double-counted or lost between a region and its parent.
3. **`reference/region_marker_combined.csv`** — a single growing file, shared
   across every QuPath project, that every export run appends new rows to.
   Long/tidy format (one row per region × marker × class), tagged by slice
   name and detection `config_tag` (derived from `BraiAn.yml`), so absent
   markers on a TdT-only slice simply produce no Fos/Double+ rows — no blank
   columns, no schema conflicts.

### 7. Aggregate + verify `[SCRIPTABLE]`

Once several slices have been exported, aggregate the growing combined CSV
and re-prove the region rollup is leak-free:

```
conda run -n braian python scripts/build_dapi_reference.py --check-zero-leak
conda run -n braian python scripts/build_dapi_reference.py
conda run -n braian python scripts/verify_export_integrity.py --results-dir "<QuPath project>/results"
```

`--check-zero-leak` independently re-derives the parent-rollup invariant
straight from the CSV (sum of leaf counts == the atlas-root's count), as a
second witness alongside the export script's own in-script assertion.
`verify_export_integrity.py` confirms every entry produced exactly one
matched per-cell/per-region file pair with no filename clobbering across
entries.

The friendly launcher (`run_pipeline.py`) runs all three of these for you
from a menu.

## Deploy (dual-location convention)

Every groovy script above is **authored once in the canonical `scripts/`**
directory, then **hard-copied byte-identically** into the QuPath project's own
`scripts/` folder before you run it with "Run for project" (QuPath only sees
scripts inside the project). Also copy `pipeline.yml` into the QuPath
project's base directory (next to `BraiAn.yml`) — the groovy scripts read
`pipeline.yml` from `getProject().getBaseDirectory()`.

```
cp scripts/01_load_abba_rois.groovy      "<QuPath project>/scripts/"
cp scripts/02_detect_classify.groovy     "<QuPath project>/scripts/"
cp scripts/03_export_region_table.groovy "<QuPath project>/scripts/"
cp pipeline.yml                          "<QuPath project>/"
```

If you edit a script, always edit the canonical `scripts/` copy first, then
re-copy — never hand-edit the copy inside a QuPath project, or the two will
drift and the next re-copy will silently discard your edit.

## Retired scripts

`scripts/classify_markers.groovy`, `scripts/export_region_dapi_reference.groovy`,
and `scripts/03_export_val01_metrics.groovy` are **retired** — their logic was
folded into `02_detect_classify.groovy` (classification) and
`03_export_region_table.groovy` (export). They are archived, with a
supersession note, at `_archive/retired-scripts/06.1/` for reference only.
Do not deploy or run them — they are not part of the live pipeline.

## Publish this tutorial (optional)

This site can be published to GitHub Pages with one manual command, whenever
you want it public:

```
mkdocs gh-deploy
```

**Privacy caveat — read before running this.** This repository holds
unpublished research data and methods. `mkdocs gh-deploy` publishes the built
site (this tutorial + the two per-stage docs + any screenshots you've added)
to a public URL:

- If the repo is **already public**, the tutorial content itself isn't
  making anything more public that isn't already visible — but the tutorial
  is now indexable/linkable on its own.
- If the repo is **private**, GitHub Pages requires a **paid GitHub plan**,
  and publishing puts the tutorial (including any captured screenshots) on
  the public internet even though the repository itself stays private.

Nothing in this project auto-publishes on push — there is no
`.github/workflows/` deploy action. Publishing only ever happens when an
operator runs `mkdocs gh-deploy` by hand, so this is always a conscious,
opt-in decision.
