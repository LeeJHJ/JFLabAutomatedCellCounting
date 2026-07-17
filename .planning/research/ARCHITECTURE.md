# Architecture Research — v1.1 Integration (First Full-Series Run, wBA1-3)

**Domain:** Internal pipeline integration (TRAP2/Airyscan section pipeline, existing 4-stage architecture)
**Researched:** 2026-07-17
**Confidence:** HIGH — grounded directly in the actual scripts on disk (`czi_mip.py`, `scripts/01_load_abba_rois.groovy`, `scripts/run_braian_detection.groovy`, `scripts/02_detect_classify.groovy`, `scripts/03_export_val01_metrics.groovy`, `scripts/export_region_dapi_reference.groovy`, `scripts/build_dapi_reference.py`, `scripts/crop_to_tissue.py`, `scripts/val01_metrics.py`) plus the v1.0 phase record (`04-REVIEW.md`, `04-VALIDATION-RECORD.md`, `deferred-items.md`). This supersedes the prior (2026-06-30, pre-implementation) version of this file, which described a hypothetical QuPath layout from web documentation before any of Stages 3/4 were actually built. Everything below is a read of the real, working code plus the v1.0 phase closeout, not external-ecosystem research.

## Standard Architecture (as-built, v1.0)

### System Overview

```
┌───────────────────────────────────────────────────────────────────────────┐
│ STAGE 1  CZI → MIP            czi_mip.py (braian env)                     │
│          aicspylibczi + numpy + tifffile, single-scene, hardcoded I/O     │
└───────────────────────────────┬───────────────────────────────────────────┘
                                │ 1 MIP OME-TIFF (C,Y,X; OME-XML PhysicalSizeX)
                                ▼
┌───────────────────────────────────────────────────────────────────────────┐
│ STAGE 2  ATLAS REGISTRATION   ABBA in Fiji (GUI)                          │
│          DeepSlice → manual angle review → export (no Affine/Spline)     │
│          writes ABBA-Transform-*.json + ABBA-RoiSet-*.zip into           │
│          <project>/data/<entry>/                                          │
└───────────────────────────────┬───────────────────────────────────────────┘
                                │ per-entry transform + region ROIs
                                ▼
┌───────────────────────────────────────────────────────────────────────────┐
│ STAGE 3  DETECT + CLASSIFY    QuPath 0.6.0 project, single project,       │
│          per-entry Groovy, all "Run for project"-safe already:            │
│            01_load_abba_rois.groovy   → loads atlas ROIs onto the entry  │
│            run_braian_detection.groovy → BraiAnDetect nuclear detection  │
│            02_detect_classify.groovy   → bg-sub compartment measures,    │
│                robust-threshold classify, ephemeral region label,        │
│                per-region Count: <class> rollup                          │
│          state lives in data/<entry>/{server.json,data.qpdata,          │
│          summary.json}                                                   │
└───────────────────────────────┬───────────────────────────────────────────┘
                                │ classified cells + per-region counts (per entry)
                                ▼
┌───────────────────────────────────────────────────────────────────────────┐
│ STAGE 4  VAL-01 EXPORT         03_export_val01_metrics.groovy (Groovy,    │
│          per-entry, OVERWRITES results/*.tsv) → val01_metrics.py         │
│          (braian env) bioplausibility metrics                            │
└───────────────────────────────────────────────────────────────────────────┘

  [NOT YET BUILT — v1.0 stopped here]
  STAGE 5  BraiAnalyse aggregation (animal-level stats)
  STAGE 6  brainrender CCFv3 micron point cloud
```

**Key structural fact that changes the v1.1 build plan:** three of the four Stage-3 Groovy scripts (`01_load_abba_rois.groovy`, `run_braian_detection.groovy`, `02_detect_classify.groovy`) already operate on `getCurrentImageData()` and are explicitly documented in their own headers as "Run for project"-safe (per-entry guards, not project-wide assumptions). **They need zero code changes to run across 5 entries instead of 1.** Only `03_export_val01_metrics.groovy` breaks under multi-entry batch execution today, because it **truncates** `results/val01_percell_export.tsv` / `results/val01_region_area.tsv` on every run — running it via "Run for project" across 5 entries silently leaves only the 5th entry's data on disk. This is the single concrete Stage-4 defect v1.1 must fix before anything downstream (aggregation, brainrender) can trust the exports.

### Component Responsibilities (v1.0 baseline, annotated for v1.1)

| Component | Responsibility | v1.1 status |
|-----------|-----------------|-------------|
| `czi_mip.py` | Single-scene CZI mosaic → 1 MIP OME-TIFF | **MODIFIED** — extend to iterate scenes |
| `crop_to_tissue.py` | DAPI Otsu tissue-mask auto-crop, preserves calibration/channel names | **EXISTING, UNUSED IN PIPELINE** — this is v1.1's registration-speedup lever, already built |
| ABBA (Fiji) | Per-image registration; natively multi-image (`Multi Image To Atlas`) | **UNCHANGED** — already designed for N sections |
| `01_load_abba_rois.groovy` | Load ABBA ROIs onto current entry | **UNCHANGED** — already per-entry/batch-safe |
| `run_braian_detection.groovy` | BraiAnDetect nuclear detection + BraiAn.yml classifiers | **UNCHANGED** (re-run only if D-05 drift gate fails) |
| `02_detect_classify.groovy` | bg-sub measures, robust-threshold classify, ephemeral region label, per-region rollup | **UNCHANGED** — already series-ready (k=3 locked) |
| `export_region_dapi_reference.groovy` | Cross-image growing DAPI density reference (`reference/dapi_region_reference.csv`), config-tagged | **EXISTING PATTERN TO REUSE** for the new area-based readout |
| `build_dapi_reference.py` | Aggregate + drift-flag the DAPI density reference | **EXISTING PATTERN TO REUSE/EXTEND** |
| `03_export_val01_metrics.groovy` | Per-cell + per-region TSV export (pixel-space only) | **MODIFIED (bug fix)** — per-entry output naming; **EXTENDED** — add Atlas_X/Y/Z micron columns |
| `val01_metrics.py` | Bioplausibility metrics from the TSVs | **UNCHANGED**, consumed by new validation harness |
| — | Area-based density readout for compact-nuclei regions | **NEW** Groovy script |
| — | Brain-wide region-labeling validation harness | **NEW** Python script |
| — | Section→animal aggregation (BraiAnalyse) | **NEW** Stage 5 (Python, `braian` env) |
| — | CCFv3-micron point-cloud export/render | **NEW** Stage 6 (Python, `brainrender` env) |

## Integration Points — one per question

### 1. Multi-scene handling

**Where it lives:** Stage 1 only. Nothing downstream needs new architecture — ABBA and the Stage-3 Groovy scripts are already multi-entry-capable (see above).

- **Modify `czi_mip.py`:** it currently reads `S` (scenes) into `n_s` and prints it but never loops over it — the loop body only iterates `C`/`Z`. Extend it to loop `s in range(n_s)`, calling `czi.read_mosaic(C=c, Z=z, S=s, scale_factor=1.0)`, and write one OME-TIFF per scene. While doing this, also bring it up to the project's current CLI convention (argparse + `Path` args + `--self-test`, the pattern already established in `crop_to_tissue.py`) instead of the hardcoded `F_IN`/`F_OUT`/`PIXEL_SIZE_UM` constants at the top of the file — the hardcoded-constant style is what the v1.0 script still has, and editing constants for a 5-scene loop is exactly the kind of manual-edit-per-run mistake that invites a wrong-scene error.
- **Output naming:** `{stem}_S{scene:02d}.ome.tiff` (zero-padded scene index), one file per scene, same `(C,Y,X)` uint16 + OME-XML shape as today — this preserves the existing "MIP OME-TIFF" abstraction so nothing downstream needs to know scenes exist.
- **QuPath side:** import all 5 scene MIPs as 5 image entries into **one** `.qpproj` (`Add images` / drag-batch), matching the existing `data/<entry>/` per-section state-store pattern already seen with `data/1`, `data/3` in this repo. Do **not** create 5 separate QuPath projects — the classifiers directory and `BraiAn.yml` are project-scoped, and animal-level aggregation (Stage 5) wants one project's `results/` tree to hold all 5 sections' exports side by side.
- **ABBA side:** register each of the 5 entries independently through `Multi Image To Atlas` (DeepSlice → manual angle → export) — this is literally what that Fiji tool is built for; scaling from 1 to 5 images is a matter of doing it 5 times in the same ABBA project state, not new tooling.
- **Concrete new-vs-modified:** `czi_mip.py` — MODIFIED. Everything else in this integration point — UNCHANGED, just exercised at N=5 instead of N=1.

### 2. Registration speedup

**Where it slots in:** a new optional step between Stage 1 and Stage 2 (call it **Stage 1.5**), not inside ABBA itself, and it must run **before** QuPath import — not after.

- `crop_to_tissue.py` **already exists and is fully built** (Otsu tissue mask on the DAPI channel, morphological clean, bbox + margin, crops all channels, rewrites OME-XML preserving `PhysicalSizeX`/channel names — verified by its own `--self-test`). It has just never been wired into the pipeline. Insert it as: `czi_mip.py` (per scene) → `crop_to_tissue.py` (per scene MIP) → import the **cropped** MIP into QuPath/ABBA.
- **Why order matters (do-not-break-the-contract rule):** ABBA's `ABBA-Transform-*.json` encodes a pixel-space transform tied to the exact canvas the registration was run against. If you crop *after* registering, the transform's pixel coordinates no longer match the cropped canvas and the exported ROIs land in the wrong place. Crop must happen **before** the image ever enters QuPath/ABBA, so the transform is native to the cropped canvas from the start. This is why the export→QuPath contract is unaffected: QuPath/ABBA never see the uncropped image at all, so there is nothing to reconcile.
- **What this buys:** the existing anti-pattern ("Elastix spline registration without tissue mask" — degrades because background pixels dominate optimization, confirmed 2026-06-23) is *exactly* the failure mode a tissue mask is supposed to fix. With `crop_to_tissue.py` producing a mostly-tissue frame, re-testing elastix Affine+Spline becomes a fair trial rather than a repeat of the known-bad case. Treat this as a **validation gate, not an assumption**: test crop+Affine+Spline on ONE section first (visual atlas-boundary-fit QC, same check already used for DeepSlice-only), and only adopt it series-wide if it beats DeepSlice-only on both fit quality and manual-effort time. If it doesn't help, DeepSlice → manual angle → export remains the fallback — no regression risk because Stage 1.5 is additive/optional.
- **Landmark reuse:** BigWarp landmarks are anatomy-specific per section and cannot be literally copied between sections (different AP level, different tilt). The realistic "reuse" here is procedural, not a code component: pick a small, consistent set of fiducials (e.g., ventricle corners, corpus-callosum notches) that recur across the LA/BA series and place landmarks at the *same anatomical features* each time, which speeds up manual placement without any new tooling. Document this as an SOP note, not an architecture component.
- **Concrete new-vs-modified:** `crop_to_tissue.py` — **EXISTING, now wired in** (no code change needed, just added to the pipeline sequence). ABBA/QuPath contract — **UNCHANGED** (crop happens strictly before either tool sees the image).

### 3. Generalizable area-based density readout

**Where it lives relative to `02_detect_classify.groovy`:** a **new, separate Groovy script** (e.g. `04_area_density.groovy`), run strictly **after** `02_detect_classify.groovy` on the same entry, in the same "numbered pipeline stage" convention already used by `01_`/`02_`/`03_`.

- **Why it must be separate, not folded in:** `02_detect_classify.groovy` already has a documented exclusion for exactly this problem — `EXCLUDE_ACRONYMS = ["DG-sg", "VS"]` sets those cells to `"Excluded"` and skips nucleus-anchored classification, because DAPI segmentation over-merges in compact-nuclei layers. The area-based readout is the **alternate measurement** for those same regions (and, per the roadmap intent, any future compact-nuclei region) — it does not reclassify per-nucleus objects, it computes a region-level density directly from pixel intensity/area over the region ROI, independent of whether individual nuclei were ever segmented correctly.
- **How it coexists safely with the nucleus-anchored objects (the quality-gate requirement):**
  - It reads the **region annotation ROI** and the **raw image pixels** inside it (via `ObjectMeasurements`/pixel-classifier style intensity summation, the same `ObjectMeasurements.addIntensityMeasurements` idiom `02_detect_classify.groovy` already uses for its background-subtraction ring) — it never calls `setPathClass()` on a detection and never deletes/rewrites a `PathObject`.
  - It writes its own new measurement keys onto the **same region annotation's** `MeasurementList` — e.g. `AreaDensity: TdT+ pxArea_um2`, `AreaDensity: TdT+ frac` — alongside (not overwriting) the `Count: <class>` keys `02_detect_classify.groovy`'s SC4 rollup already writes there. Same object, disjoint key namespace: this is the exact pattern the codebase already uses to layer independent measurements onto one annotation without collision.
  - Because it never touches per-nucleus `PathClass` or detection geometry, re-running it is idempotent and cannot corrupt the primary nucleus-anchored counts; if it produces a bad value the worst case is a bad `AreaDensity:` key, not a wrong `Count: Fos+`.
- **Generalizability requirement:** parameterize by region acronym list (a config array at the top of the script, not hardcoded to `DG`), so the same script later targets any compact-nuclei region brain-wide — matching PROJECT.md's explicit framing ("reusable/brain-wide-ready; DG as the in-section test case").
- **Output recording, modeled on the existing cross-image reference pattern:** reuse `export_region_dapi_reference.groovy`'s shape almost verbatim (region loop → area in mm² → append CSV row, `config_tag`-keyed so only like-detection-config rows aggregate) but keyed on **marker + region acronym** instead of raw DAPI count. Two outputs, mirroring the existing two-tier convention:
  - A per-run snapshot TSV in `results/` (mirrors `val01_region_area.tsv`'s overwrite-per-run behavior — but fixed for multi-entry per Integration Point 1/4, i.e. **per-entry filename**).
  - A growing, config-tagged CSV in `reference/` (mirrors `dapi_region_reference.csv`) so the density baseline for compact-nuclei regions accumulates across sections/animals for future brain-wide use, aggregated the same way `build_dapi_reference.py` already aggregates DAPI density.
- **Concrete new-vs-modified:** `04_area_density.groovy` — **NEW**. `export_region_dapi_reference.groovy` / `build_dapi_reference.py` — **UNCHANGED**, used only as the structural template to copy, not modified in place (the DAPI reference stays about raw DAPI density; the new script is its marker-density sibling).

### 4. Brain-wide region-labeling validation

**What CR-01 was:** the Phase-4 code review found the *old* "leaf = no annotation children" heuristic unreliable on the real ABBA hierarchy — rollup regions (`grey`, `root`, etc.) came back child-empty on one hemisphere and absorbed ~95k cells via first-match assignment. The fix, already committed in `03_export_val01_metrics.groovy` (commit `29dbfdc`), is **geometric**: `regionOf` assigns each cell to the **smallest-area containing region** (area-sorted short-circuit `.find`), and `isLeafOf` computes leaf-ness as "no smaller region's centroid falls inside me" — both topology-independent, so they cannot disagree across hemispheres or ABBA-export quirks the way the old child-annotation heuristic did.

**Validation harness needed for v1.1 (this is genuinely new — CR-01 was verified by hand on one section):**

- **New Python script** (e.g. `scripts/validate_region_labels.py`, `braian` env), built on `val01_metrics.py`'s existing CLI/pandas conventions, run **after** all 5 entries have both `02_detect_classify.groovy` and the (fixed, per-entry) `03_export_val01_metrics.groovy` exports on disk, and **before** Stage 5 aggregation trusts the region labels. It should assert, across all 5 sections combined:
  1. **Zero-cell rollup check** — the known non-leaf rollup acronyms (`grey`, `root`, `CH`, `CTX`, `Isocortex`, `HPF`, `fiber tracts`, …, the exact list named in `04-REVIEW.md`'s CR-01 resolution) receive **zero** classified cells in every section's `val01_percell_export.tsv`. This is precisely the check that caught CR-01 by hand on one section; automating it across all 5 sections/all regions is what makes it "brain-wide" instead of hippocampus-only.
  2. **Area non-overlap / non-gap sanity** — per section, sum the `area_mm2` of all rows flagged `is_leaf=true` in `val01_region_area.tsv` and compare against total tissue area (from `crop_to_tissue.py`'s own tissue-mask area, or total DAPI-detection bounding extent) to catch double-counted or missing leaf area — a symptom the old heuristic produced (rollup area double-counted into the density denominator, per `04-VALIDATION-RECORD.md`).
  3. **Cross-section is_leaf consistency** — the same acronym should resolve to `is_leaf=true`/`false` consistently across all 5 sections (it's a property of the atlas ontology at that AP level, not of a specific section's ABBA export quirks); flag any acronym whose leaf-flag disagrees across sections for manual review, since that is exactly the failure mode CR-01 exposed.
- This harness is a **companion gate to `val01_metrics.py`**, not a replacement — `val01_metrics.py` answers "are the counts biologically plausible," this harness answers "are the region labels themselves structurally trustworthy before we trust the counts."
- **Concrete new-vs-modified:** `validate_region_labels.py` — **NEW**. `03_export_val01_metrics.groovy`'s CR-01 fix — **UNCHANGED**, reused/exercised at scale, not re-derived.

### 5. Section→animal aggregation + micron export

**Where these sit:** genuinely new Stage 5 (BraiAnalyse, `braian` env) and Stage 6 (brainrender, `brainrender` env) — the prior codebase map already documented these as "not yet present." v1.1 is the milestone where they become due, and the groundwork for the micron piece already exists as a *sanity print*, not yet a real export.

**Concrete gap to close first (blocks both new stages):** `03_export_val01_metrics.groovy`'s per-cell TSV currently exports `centroid_x_px`/`centroid_y_px` — explicitly commented "diagnostic only, unused downstream" — because full Atlas_X/Y/Z micron export was deferred to "v2 EXP-01/EXP-03." `02_detect_classify.groovy`'s SC3 block already proves the mechanism works: it calls `AtlasTools.getAtlasToPixelTransform(imageData).inverse()` and prints Atlas_X/Y/Z for a handful of classified cells as a sanity check (with a documented gotcha — values print in whatever unit the transform's atlas is defined in; the project's own memory note records that `AtlasTools` atlas coordinates are **millimeters**, requiring `×1000` to reach the microns brainrender needs). v1.1 turns that proven-but-throwaway sanity print into a real per-cell column.

**Data flow, concretely:**

```
Stage 3 (per entry, ×5)          Stage 4 (per entry, ×5 — FIXED for multi-entry)
02_detect_classify.groovy   →    03_export_val01_metrics.groovy (extended)
  classified PathObjects           writes per-entry-named TSVs:
  + region ROIs                      results/<entry>/val01_percell_export.tsv
                                        (+ Atlas_X/Y/Z µm columns, ×1000 from
                                         AtlasTools' native mm)
                                      results/<entry>/val01_region_area.tsv
                                                │
                     ┌──────────────────────────┴───────────────────────────┐
                     ▼                                                      ▼
        NEW Stage 5 — aggregate_animal.py (braian env)         NEW Stage 6 — render_pointcloud.py (brainrender env)
        concatenates 5 region TSVs with a section_id column,   concatenates 5 per-cell TSVs (Atlas_X/Y/Z µm,
        derives per-region density per section, then           class) into one animal-level cell table,
        aggregates 5 sections → 1 animal-level table           scatters into the `allen_mouse` CCFv3 scene
        (mean ± SD density per region; Welch's t-test /        colored by TdT+/Fos+/Double+/Negative
        Hedges' g deferred until >1 animal exists — Out of
        Scope per PROJECT.md)
```

- **`aggregate_animal.py`** (new, `braian` env): modeled on `build_dapi_reference.py`'s load → groupby → CLI pattern. Reads the 5 (now correctly per-entry) `val01_region_area.tsv` + rollup `Count:` measurements, adds a `section_id` column, and produces one animal-level table (`wBA1-3_animal_region_density.csv`) — this is the first real BraiAnalyse roll-up the project has ever produced, matching CLAUDE.md's "aggregate to animal level before any group comparison" rule even though there is only one animal so far (no group comparison happens yet; that's still Out of Scope until a second animal exists).
- **`render_pointcloud.py`** (new, `brainrender` env): consumes the concatenated per-cell micron table directly — no additional transform needed once Stage 4's export carries real Atlas_X/Y/Z in microns. This is where the CLAUDE.md non-negotiable ("export atlas coordinates in microns, not pixels — otherwise the brainrender point cloud lands in the wrong place") gets enforced in code for the first time; today it is enforced only by convention/sanity-print.
- **Concrete new-vs-modified:** `03_export_val01_metrics.groovy` — **MODIFIED** (per-entry output paths + Atlas_X/Y/Z µm columns). `aggregate_animal.py`, `render_pointcloud.py` — **NEW**.

## New vs. Modified Components — summary table

| File | Status | Change |
|------|--------|--------|
| `czi_mip.py` | MODIFIED | Loop over scenes (S dim), emit 5 MIPs; adopt argparse/`Path` CLI convention |
| `crop_to_tissue.py` | EXISTING, newly wired in | No code change — inserted as optional Stage 1.5 before QuPath import |
| ABBA (Fiji) | UNCHANGED | Run its native multi-image workflow 5× into one QuPath project |
| `01_load_abba_rois.groovy` | UNCHANGED | Already per-entry/"Run for project"-safe |
| `run_braian_detection.groovy` | UNCHANGED | Re-run only if D-05 drift gate fails on the new imaging params |
| `02_detect_classify.groovy` | UNCHANGED | Already series-ready (k=3 locked); `EXCLUDE_ACRONYMS` stays as-is |
| `04_area_density.groovy` | **NEW** | Area-based density readout for compact-nuclei regions, parameterized by acronym |
| `export_region_dapi_reference.groovy` / `build_dapi_reference.py` | UNCHANGED | Structural template only, not modified |
| `03_export_val01_metrics.groovy` | MODIFIED | Fix overwrite-per-run bug (per-entry filenames); add Atlas_X/Y/Z µm columns |
| `val01_metrics.py` | UNCHANGED | Consumed as-is by the new validation harness |
| `validate_region_labels.py` | **NEW** | Brain-wide CR-01 validation across all 5 sections |
| `aggregate_animal.py` | **NEW** | Stage 5 — section→animal BraiAnalyse roll-up |
| `render_pointcloud.py` | **NEW** | Stage 6 — CCFv3-micron point cloud |

## Suggested Build Order (dependency-respecting)

1. **Multi-scene MIP conversion** — extend `czi_mip.py` (nothing else can start without 5 MIPs).
2. **Registration-speedup trial** — wire `crop_to_tissue.py` in as Stage 1.5; validate crop+Affine/Spline vs. DeepSlice-only on ONE section before deciding the series-wide path.
3. **ABBA registration ×5 + `01_load_abba_rois.groovy`** ("Run for project" across the 5 entries) using whichever path step 2 validates.
4. **Imaging re-validation / detection re-lock** — `run_braian_detection.groovy` "Run for project"; re-lock params only if the D-05 gate shows drift on the new 4-plane/lower-laser acquisition.
5. **LA/BA nucleus-anchored classification** — `02_detect_classify.groovy` "Run for project" across the 5 entries (no code change; this is the primary readout).
6. **Fix `03_export_val01_metrics.groovy` for multi-entry** (per-entry output paths) **and** add the Atlas_X/Y/Z micron columns — this must land before step 7 or step 9/10 can trust the exports.
7. **Area-based density readout** — build/test `04_area_density.groovy` on DG in one section first (confirm measurement-key non-collision with step 5's rollup), then run across all 5 entries.
8. **Brain-wide region-labeling validation harness** — `validate_region_labels.py`, run against all 5 sections' step-6 exports; this is the gate before trusting anything aggregated next.
9. **Section→animal aggregation** — `aggregate_animal.py` (depends on 6 + 8 being clean).
10. **CCFv3-micron point-cloud export/render** — `render_pointcloud.py` (depends on 6's micron columns; can run in parallel with 9 since it operates per-cell, not per-animal-aggregate).

## Anti-Patterns to Avoid in v1.1

### Cropping after registration instead of before
**What people do:** run `crop_to_tissue.py` on an already-ABBA-registered image to "clean it up."
**Why it's wrong:** the ABBA transform is tied to the exact pixel canvas it was computed against; cropping afterward silently invalidates every exported ROI's coordinate space.
**Do this instead:** crop before the image ever enters QuPath/ABBA (Stage 1.5, strictly before Stage 2).

### Letting `03_export_val01_metrics.groovy` run "as-is" under "Run for project"
**What people do:** assume all four Stage-3/4 Groovy scripts are equally series-ready because three of them already are.
**Why it's wrong:** the export script truncates its output files every run; batched across 5 entries, only the last entry's data survives on disk, and nothing downstream will notice until the animal-level table looks wrong.
**Do this instead:** fix the output path to be per-entry before running any multi-section batch.

### Folding the area-based readout into `02_detect_classify.groovy`
**What people do:** add the compact-nuclei density logic directly into the classification script since "it's related."
**Why it's wrong:** it blurs the nucleus-anchored classification's clean scope (D-01/D-02 in that script's own header) and risks a bug in the new area logic corrupting `PathClass`/`Count:` values that downstream stats already depend on.
**Do this instead:** a separate script, reading the same annotations/pixels but writing disjoint measurement keys, run strictly after classification.

### Treating micron export as "the same as the existing sanity print"
**What people do:** assume the SC3 Atlas_X/Y/Z println in `02_detect_classify.groovy` already satisfies the micron-export requirement.
**Why it's wrong:** it prints 5 sample cells to console for a unit sanity-check; it is not a persisted per-cell column, and it does not apply the mm→µm ×1000 conversion the project's own memory note documents as necessary.
**Do this instead:** promote the proven transform call into a real, persisted TSV column in the (fixed) Stage-4 export script, with the ×1000 conversion applied explicitly and asserted (not just eyeballed).

## Sources

- `/home/jflab/Analysis/czi_mip.py` (current single-scene implementation, read in full)
- `/home/jflab/Analysis/scripts/01_load_abba_rois.groovy`
- `/home/jflab/Analysis/scripts/02_detect_classify.groovy` (full file)
- `/home/jflab/Analysis/scripts/03_export_val01_metrics.groovy` (full file, CR-01-fixed version)
- `/home/jflab/Analysis/scripts/run_braian_detection.groovy`
- `/home/jflab/Analysis/scripts/export_region_dapi_reference.groovy`
- `/home/jflab/Analysis/scripts/build_dapi_reference.py`
- `/home/jflab/Analysis/scripts/crop_to_tissue.py` (full file, incl. self-test)
- `/home/jflab/Analysis/.planning/phases/04-.../04-REVIEW.md`, `04-VALIDATION-RECORD.md`, `deferred-items.md`, `04-03-SUMMARY.md`, `04-VERIFICATION.md` (CR-01 root cause + fix + verification)
- `/home/jflab/Analysis/.planning/phases/03-.../03-PATTERNS.md` (Phase-3 pattern map)
- `/home/jflab/Analysis/.planning/PROJECT.md` (v1.1 milestone scope, decisions log)
- `/home/jflab/Analysis/.claude/CLAUDE.md` (architecture/component tables, entry points)
- User memory note `atlas_coords_mm_units.md` (AtlasTools atlas coords are mm; ×1000 for brainrender microns)

---
*Architecture research for: TRAP2/Airyscan section pipeline v1.1 milestone integration*
*Researched: 2026-07-17*
