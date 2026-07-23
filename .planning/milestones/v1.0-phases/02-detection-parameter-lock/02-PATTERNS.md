# Phase 2: Detection Parameter Lock - Pattern Map

**Mapped:** 2026-07-07
**Files analyzed:** 3 (1 new config, 1 rebuild, 1 reuse-with-edit)
**Analogs found:** 3 / 3

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|--------------------|------|-----------|-----------------|----------------|
| `M3 Hippocampus 20x 062926 3 plane/BraiAn.yml` (NEW) | config | batch (declarative detection-run spec, consumed by QuPath extension at Phase-3 runtime) | Official `qupath-extension-braian` example `BraiAn.yml` (upstream, quoted verbatim in 02-RESEARCH.md) — **no local `.yml` of this schema exists anywhere on disk**; the only local `.yml` hit (`~/section-pipeline/tools/Fiji.app/config/environment.yml`) is an unrelated Fiji conda-env file, not a pattern source | role-match (schema-verified from jar bytecode + upstream example; no project-local analog exists — this is a genuinely new artifact type for the repo) |
| `M3 Hippocampus 20x 062926 3 plane/classifiers/object_classifiers/TdT_classifier.json` (REBUILD) | config (declarative classifier) | transform (single-measurement threshold → class label) | `M3 Hippocampus 20x 062226/M3 Hippocampus 20x 062226 Redo/classifiers/object_classifiers/TRAP2TdT_Classifier_20x.json` | exact (same role, same schema — analog is wrong on the one field that must change: compartment) |
| `M3 Hippocampus 20x 062926 3 plane/classifiers/object_classifiers/Fos_Classifier_20x.json` (REUSE, threshold edit only) | config (declarative classifier) | transform (single-measurement threshold → class label) | `M3 Hippocampus 20x 062226/M3 Hippocampus 20x 062226 Redo/classifiers/object_classifiers/Fos_Classifier_20x.json` | exact (copy verbatim, edit only the `threshold` value per D-02) |

Note: target project `M3 Hippocampus 20x 062926 3 plane/classifiers/` currently contains only `classes.json` — no `object_classifiers/` subdirectory exists yet there. It must be created when these two classifier files are written/copied in.

## Pattern Assignments

### `M3 Hippocampus 20x 062926 3 plane/BraiAn.yml` (config, batch/declarative)

**Analog:** upstream `qupath-extension-braian` official example (`github.com/carlocastoldi/qupath-extension-braian/blob/master/BraiAn.yml`), field names cross-verified against the installed jar `~/section-pipeline/tools/QuPath/extensions/catalogs/BraiAn catalog/QuPath BraiAn extension/v1.1.0/main-jar/qupath-extension-braian-1.1.0.jar` (per 02-RESEARCH.md "Standard Stack"/"Code Examples"). No project-local `.yml` of this schema exists to copy from — this is the first one authored in this repo.

**Full schema + adapted example** (verbatim from 02-RESEARCH.md "Pattern 1: Single-Entry, Multi-Classifier `channelDetections`"):
```yaml
# Source: qupath-extension-braian v1.1.0 config schema
# (github.com/carlocastoldi/qupath-extension-braian/blob/master/BraiAn.yml,
#  field names cross-checked against qupath/ext/braian/config/*.class)
classForDetections: null
detectionsCheck:
  apply: false          # D-07: negative-control gate deferred, not this phase
  controlChannel: null

channelDetections:
  - name: "DAPI-T4"                 # nuclear anchor — matches project channel name exactly
    parameters:
      requestedPixelSizeMicrons: 0.6905355   # match OME-XML PhysicalSizeX (server.json, confirmed below)
      backgroundRadiusMicrons: 10
      backgroundByReconstruction: true
      medianRadiusMicrons: 0.0
      sigmaMicrons: 2.0            # seed — tune per D-04/D-05
      minAreaMicrons: 20.0
      maxAreaMicrons: 150.0        # seed toward D-05's 50-150 µm² peak gate
      histogramThreshold:          # D-01/D-02: histogram-relative, not absolute
        resolutionLevel: 0
        smoothWindowSize: 15
        peakProminence: 100
        nPeak: 1
      watershedPostProcess: true
      cellExpansionMicrons: 5.0    # Claude's-discretion seed (TRAP2 paper / QuPath default)
      includeNuclei: true
      smoothBoundaries: true
      makeMeasurements: true
    classifiers:
      - channel: "AF488-T3"
        name: "Fos_Classifier_20x"
        annotationsToClassify: []   # empty = apply to all detections
      - channel: "AF568-T2"
        name: "TdT_classifier"
        annotationsToClassify: []
```

**Confirmed pixel calibration to plug in** (verified directly this session, not from RESEARCH):
```
Source: M3 Hippocampus 20x 062926 3 plane/data/1/server.json
"pixelWidth": { "value": 0.6905355, "unit": "µm" }
```
Use `0.6905355` for `requestedPixelSizeMicrons` — matches the entry-1 tuning substrate exactly (A4 in 02-RESEARCH.md Assumptions Log resolved).

**Topology note (structural, not cosmetic):** Do NOT copy the upstream example's literal per-marker `channelDetections` list structure (their example has separate entries per marker channel, no DAPI at all). This project's single correct topology is **one entry rooted at `name: "DAPI-T4"`** with both classifiers nested under it — see 02-RESEARCH.md "Pattern 1" and Pitfall 1 for why the naive per-marker copy would be wrong here.

**Path resolution convention to preserve:** classifier `name` fields resolve relative to the QuPath project base dir → `classifiers/object_classifiers/<name>.json` (confirmed via decompiled `qupath/ext/braian/utils/BraiAn.resolvePath`, 02-RESEARCH.md Anti-Patterns). `BraiAn.yml` itself lives at the project root, sibling to `project.qpproj`, matching the canonical scripts-hard-copy convention below.

---

### `classifiers/object_classifiers/TdT_classifier.json` (config classifier, transform — REBUILD)

**Analog:** `M3 Hippocampus 20x 062226/M3 Hippocampus 20x 062226 Redo/classifiers/object_classifiers/TRAP2TdT_Classifier_20x.json` (read verbatim this session):
```json
{
  "object_classifier_type": "SimpleClassifier",
  "function": {
    "classifier_fun": "ClassifyByMeasurementFunction",
    "measurement": "Nucleus: AF568-T2 mean",
    "pathClassBelow": "Negative",
    "pathClassEquals": "Other",
    "pathClassAbove": "Other",
    "threshold": 10200.8443
  },
  "pathClasses": [
    "Negative",
    "Other"
  ],
  "filter": "DETECTIONS_ALL",
  "timestamp": 1782251202151
}
```

**Required change (the whole point of the rebuild):** `"measurement"` must become `"Cytoplasm: AF568-T2 mean"` — the analog reads `Nucleus:`, which is wrong per CLAUDE.md's cytosolic-TdTomato rule (this measurement string only exists once `cellExpansionMicrons > 0` in `BraiAn.yml`, satisfied above). Everything else in the JSON (schema shape, `object_classifier_type`, `filter`, `pathClasses` list) copies structurally unchanged. The `threshold` numeric value must be re-derived (histogram-relative per D-02) during tuning on entry 1 — the analog's `10200.8443` is only a reference starting point, not the locked value. Planner should also decide whether to keep `pathClassEquals`/`pathClassAbove` as `"Other"` (matches analog) or standardize to `"Positive"` (matches the Fos classifier's convention below) — 02-RESEARCH.md flags this as worth reconsidering for naming consistency but does not mandate a change.

---

### `classifiers/object_classifiers/Fos_Classifier_20x.json` (config classifier, transform — REUSE + threshold edit)

**Analog:** `M3 Hippocampus 20x 062226/M3 Hippocampus 20x 062226 Redo/classifiers/object_classifiers/Fos_Classifier_20x.json` (read verbatim this session):
```json
{
  "object_classifier_type": "SimpleClassifier",
  "function": {
    "classifier_fun": "ClassifyByMeasurementFunction",
    "measurement": "Nucleus: AF488-T3 mean",
    "pathClassBelow": "Negative",
    "pathClassEquals": "Positive",
    "pathClassAbove": "Positive",
    "threshold": 9341.31736526946
  },
  "pathClasses": [
    "Negative",
    "Positive"
  ],
  "filter": "DETECTIONS_ALL",
  "timestamp": 1782494166107
}
```

**Required change:** none structural — this file already satisfies CLASS-01 (`Nucleus: AF488-T3 mean` is correct for a nuclear marker; do not touch the `measurement` field). Only the `threshold` value (`9341.31736526946`) needs re-derivation to a histogram-relative value computed from entry 1's own Fos measurement distribution (D-02); `pathClassEquals`/`pathClassAbove: "Positive"` naming is already the desired convention — use as the reference for standardizing the TdT classifier's class names if the planner chooses to do so.

---

## Shared Patterns

### Classifier JSON schema (both files)
**Source:** both existing 062226-Redo classifier files above (identical shape)
**Apply to:** both `TdT_classifier.json` and `Fos_Classifier_20x.json`
```json
{
  "object_classifier_type": "SimpleClassifier",
  "function": {
    "classifier_fun": "ClassifyByMeasurementFunction",
    "measurement": "<Compartment>: <ChannelName> mean",
    "pathClassBelow": "Negative",
    "pathClassEquals": "<Positive|Other>",
    "pathClassAbove": "<Positive|Other>",
    "threshold": <numeric>
  },
  "pathClasses": ["Negative", "<Positive|Other>"],
  "filter": "DETECTIONS_ALL",
  "timestamp": <epoch-ms, QuPath auto-writes on save>
}
```
Only 3 fields ever vary across these two files: `measurement` (compartment + channel string), the class-name pair, and `threshold`. Everything else is boilerplate to copy exactly.

### Canonical scripts/classifiers hard-copy convention (established Phase 1)
**Source:** 02-CONTEXT.md "Established Patterns"; confirmed on disk — `M3 Hippocampus 20x 062926 3 plane/scripts/01_load_abba_rois.groovy` exists both as a canonical copy under repo-root `scripts/` and hard-copied into the QuPath project's own `scripts/` dir.
**Apply to:** `BraiAn.yml` and both classifier JSONs — they are per-project artifacts that live at:
```
M3 Hippocampus 20x 062926 3 plane/BraiAn.yml                                    # project root, sibling to project.qpproj
M3 Hippocampus 20x 062926 3 plane/classifiers/object_classifiers/TdT_classifier.json
M3 Hippocampus 20x 062926 3 plane/classifiers/object_classifiers/Fos_Classifier_20x.json
```
Confirmed: `M3 Hippocampus 20x 062926 3 plane/classifiers/` currently only contains `classes.json` — the `object_classifiers/` subdirectory must be created as part of this phase's work (it does not yet exist in the target project, only in the older `062226 Redo` project).

### Channel names (verified, must match exactly in both BraiAn.yml and classifier `measurement` strings)
**Source:** 02-CONTEXT.md "Reusable Assets", confirmed via `crop_to_tissue.py` on `M3_20x_MIP_Z1-3.ome.tiff`
```
AF568-T2  → TdTomato
AF488-T3  → Fos
DAPI-T4   → DAPI (nuclear anchor)
```

## No Analog Found

None — all 3 target files have a directly usable analog (2 exact JSON analogs read verbatim; 1 schema-verified upstream example for the wholly-new `BraiAn.yml` file type, since no project-local `.yml` of this kind exists yet).

## Metadata

**Analog search scope:** `/home/jflab/Analysis` (recursive) for `*.yml`, `*Classifier*.json`, `scripts/` directories; `~/section-pipeline` for any existing BraiAn.yml examples
**Files scanned:** 5 classifier JSONs found (`Automated Cell Counting Test/classifiers/object_classifiers/{TdT,Fos}_*.json` — stale, excluded per CONTEXT.md; `M3 Hippocampus 20x 062226/.../object_classifiers/{Fos_Classifier_20x,TRAP2TdT_Classifier_20x,Morphine Project Cell Classifier,Fos_Classifier}.json`); 1 unrelated `.yml` (Fiji conda env file)
**Pattern extraction date:** 2026-07-07
