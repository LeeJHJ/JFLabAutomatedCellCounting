# Phase 2: Detection Parameter Lock - Research

**Researched:** 2026-07-07
**Domain:** QuPath BraiAnDetect extension (Groovy/Java, YAML config) + WatershedCellDetection cell-detection parameters + QuPath object-classifier JSON compartment semantics
**Confidence:** MEDIUM-HIGH (schema is VERIFIED directly from the installed jar bytecode + the extension's own official example file; biological seed values are LOW/ASSUMED — primary paper text was not reachable this session)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Threshold strategy (series-scaling)**
- **D-01:** Nucleus **detection** threshold in BraiAn.yml is **histogram-relative** (computed per-section from the DAPI histogram, e.g. percentile or median+k·MAD), NOT a fixed absolute value. Rationale: the same BraiAn.yml must work across the full series without re-tuning; absolute thresholds drift with staining/exposure (SERIES-02 risk). Note: prior M3 062226 classifiers used *absolute* (~10200 TdT / ~9341 Fos on 16-bit) — those are a starting reference for the relative calibration, not the locked approach.
- **D-02:** TdT+/Fos+ **classifier positive cutoffs** follow the **same histogram-relative philosophy** — derived from each section's measurement distribution, consistent with D-01. A globally dim/bright section must not fool the classifier.
- **D-03:** **One global BraiAn.yml** locked for every section. Do NOT re-tune per section. Instead use the Fos+-rate-vs-section-position plot (SERIES-02, later phase) to flag outlier sections for manual review. Maximizes cross-section consistency and statistical defensibility.

**Tuning reference + lock/accept bar**
- **D-04:** Tune on **M3 062926 3 plane, entry 1** (the section registered in Phase 1). Use dense **DG** as the worst-case stress test (expansion-ring bleed, merged nuclei) and **CA1** as a cleaner separability check. Params must hold on both before locking.
- **D-05:** **Hard acceptance gates** to lock the params (both must PASS): (1) detected **nucleus area distribution peaks in 50–150 µm²**; (2) **DAPI nucleus density in 500–2000/mm²**. These validate sigma + min/max area + detection threshold are catching real nuclei.
- **D-06:** **Double+ = 10–40% of TdT+** is **advisory, NOT a hard gate.** Deliberately excluded from lock criteria: gating parameters on the expected biological result risks tuning toward the hypothesis (circularity). Report the ratio, don't lock on it.
- **D-07:** The **Fos+ ≈1–3% negative-control gate is SKIPPED for Phase 2** — a single hippocampal section has no trustworthy low-activity control region. Defer the strict negative-control check to the full series (where a proper control region exists). Do not block param-lock on it.

### Claude's Discretion
- **Cytoplasmic expansion radius / DG bleeding:** default to the TRAP2-paper seed of **5 µm** (`cellExpansionMicrons`), with rings constrained so they do not overlap adjacent nuclei (QuPath cell expansion clips at neighboring cell boundaries). Tune/verify visually on dense DG per D-04. This is where TdT over/under-count risk lives — planner should make the DG bleed-check explicit.
- **Reuse vs rebuild classifiers:** **reuse** `Fos_Classifier_20x.json` (062226 Redo) as the starting point — it already correctly reads `Nucleus: AF488-T3 mean` (satisfies CLASS-01) — but **re-derive its threshold as histogram-relative** per D-02. **Rebuild the TdT classifier** to read `Cytoplasm: AF568-T2 mean`: the existing `TRAP2TdT_Classifier_20x.json` wrongly reads `Nucleus: AF568-T2 mean`, violating the cytosolic-TdTomato rule. Discard the stale "Automated Cell Counting Test" classifiers (wrong channel names `Cy3-T1`/`EGFP-T2`, wrong compartments).
- **Sigma + min/max nucleus area:** seed from the TRAP2 paper, tune on the section; gated by D-05.

### Deferred Ideas (OUT OF SCOPE)
- **Fos+ ≈1–3% negative-control validation** — deferred to the full-series phase where a proper control region exists (D-07).
- **Double+ 10–40% of TdT+ as a validation report** — computed and reported, but as an outcome, not a Phase-2 lock gate (D-06); revisit at series-stats time.
- **crop_to_tissue.py / masked-elastix registration pilot** — registration-domain (Phase 1 lineage), not detection; belongs to the series-scaling registration decision, not this phase.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SCRI-02 | `BraiAn.yml` authored at project root — locked sigma, min/max area, threshold (histogram-relative), `cellExpansionMicrons > 0` for TdT channel; channel names match project | Full YAML schema reverse-engineered from the installed extension jar (`qupath-extension-braian-1.1.0.jar`) and cross-verified against the extension's own official example `BraiAn.yml` on GitHub — see Standard Stack / Code Examples. Native histogram-relative threshold support confirmed (`histogramThreshold` block) — resolves D-01/D-02 feasibility question. |
| CLASS-01 | Fos classifier verified: `Fos_classifier.json` reads `Nucleus: AF488-T3 mean` (nuclear, not cytoplasmic) | Existing `Fos_Classifier_20x.json` already satisfies this exactly (confirmed by direct read of the file). Compartment-string mechanics (`Nucleus: <channel> mean` vs `Cytoplasm: <channel> mean`) confirmed as a QuPath-core naming convention, gated on `cellExpansionMicrons > 0` producing the Cytoplasm compartment. See Common Pitfalls and Code Examples. |
</phase_requirements>

## Summary

`BraiAn.yml` is **not** produced by the Python `braian` (BraiAnalyse, v1.0.5) package — that package's own `BraiAnConfig`/YAML schema (in `config.py`) is for the **stats-aggregation** side (experiment/groups/atlas/output-dir mapping) and has no detection parameters at all. The detection-parameter schema this phase must author belongs to the **QuPath Java/Groovy extension** `qupath-extension-braian` (the "BraiAnDetect" extension), version **1.1.0**, already installed at `~/section-pipeline/tools/QuPath/extensions/catalogs/BraiAn catalog/QuPath BraiAn extension/v1.1.0/main-jar/qupath-extension-braian-1.1.0.jar`. This research decompiled that jar directly (no `javap`/Java available on this box, so `strings` was used against the `.class` constant pool — reliable for field/getter/setter names since the extension ships with full debug symbols and no obfuscation) and cross-checked the result against the extension's own official example `BraiAn.yml` fetched from `github.com/carlocastoldi/qupath-extension-braian`. The two sources agree exactly on every field name, confirming the schema below at VERIFIED confidence.

The schema is a straight SnakeYAML JavaBean binding (`Constructor(ProjectsConfig.class, LoaderOptions)` — a **typed** constructor, not generic `Object`, which is the safe SnakeYAML usage pattern and avoids the classic YAML-deserialization RCE class of bug). Top-level: `classForDetections`, `detectionsCheck` (`apply`, `controlChannel`), `channelDetections` (a list of `{name, parameters, classifiers}`). `parameters` maps 1:1 onto QuPath's built-in `qupath.imagej.detect.cells.WatershedCellDetection` plugin parameters (the extension literally calls `runPlugin("qupath.imagej.detect.cells.WatershedCellDetection", params)` with a map built by reflecting over the parameter object's fields). Critically, `WatershedCellDetectionConfig` has **two mutually-relevant threshold fields**: a plain numeric `threshold`, and a `histogramThreshold` block (`resolutionLevel`, `smoothWindowSize`, `peakProminence`, `nPeak`) that **natively computes a per-image, histogram-peak-relative threshold at runtime** — this directly answers the D-01/D-02 feasibility question: **yes, BraiAnDetect supports a relative threshold natively**, no absolute-value workaround needed.

**Architecture caution (read before writing `channelDetections`):** the extension's own official example config runs WatershedCellDetection **independently on each marker channel** (`AF568`, `AF647` — no DAPI channel at all in that example), then applies a same-channel `SingleClassifier` to each. This is *not* the design this project needs. `CLAUDE.md` mandates one DAPI-anchored detection with a `Cytoplasm` compartment (via `cellExpansionMicrons`) for the cytosolic TdTomato marker, and nucleus-anchored containment only — never proximity/overlap across independently-segmented object sets. Decompilation of `SingleClassifier` shows it calls `PathClassTools.mergeClasses(currentClass, previousClass)` when classifying — meaning **multiple classifiers listed under the same `channelDetections` entry are applied sequentially to the same detected-cell set and their resulting classes are merged onto the same object** (compound classification), which is exactly the mechanism this project needs and requires **no** geometric cross-channel overlap. **Recommendation: `BraiAn.yml` should have a single `channelDetections` entry rooted at `DAPI-T4`, with two classifiers (Fos, TdT) nested under it — not one entry per marker channel.** This reconciles the schema with `CLAUDE.md` and with the already-correct, reusable `Fos_Classifier_20x.json`. Flagged explicitly in Open Questions/Assumptions because it also affects how Phase 3 (`SCRI-03`, which names `OverlappingDetections`) should be planned — that class exists in the jar for the *other* (per-marker, cross-channel-overlap) topology and, on this evidence, is probably not the right tool if the single-DAPI-entry design is used.

**Primary recommendation:** Author `BraiAn.yml` at the QuPath project root (`/home/jflab/Analysis/M3 Hippocampus 20x 062926 3 plane/BraiAn.yml`) with one `channelDetections` entry (`name: "DAPI-T4"`), seed `WatershedCellDetectionConfig` parameters from the TRAP2-paper/QuPath-default values in this document, use `histogramThreshold` (not `threshold`) to satisfy D-01, set `cellExpansionMicrons: 5.0`, and list the two classifiers (`Fos_Classifier_20x` reused as-is for compartment, `TdT_classifier` rebuilt to read `Cytoplasm: AF568-T2 mean`) under that single entry. Tune visually in QuPath GUI (human-in-the-loop, per CLAUDE.md's GUI-only rule) against the D-05 gates on DG + CA1.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Detection-parameter authoring (`BraiAn.yml`) | Config Authoring (Claude, file write) | QuPath BraiAnDetect engine (consumer) | YAML is hand-authored/scripted; the extension only *reads* it at detection-run time (Phase 3), so Phase 2 is a pure artifact-authoring + visual-QC task |
| Nucleus detection (WatershedCellDetection) | QuPath BraiAnDetect engine (Java) | Human visual QC (GUI) | Parameters are declared in YAML but the actual segmentation runs inside QuPath/ImageJ core code — Claude cannot execute or preview this without the human running it in the GUI |
| Histogram-relative threshold computation | QuPath BraiAnDetect engine (Java, `AutoThresholdParmameters`) | — | Fully internal to the extension at runtime; Claude only sets the 4 config knobs (`resolutionLevel`, `smoothWindowSize`, `peakProminence`, `nPeak`) |
| Fos/TdT classifier definitions (JSON) | Config Authoring (Claude, file write/edit) | QuPath object-classifier engine (consumer) | JSON is a simple declarative `SimpleClassifier`; Claude can safely read/write/verify these files directly |
| Cytoplasm/Nucleus compartment measurement | QuPath core (`WatershedCellDetection` + `CellMeasurements`) | — | Compartment measurements are computed automatically by QuPath core for every channel once `cellExpansionMicrons > 0`; not something the extension or Claude computes |
| Visual QC (DG bleed check, nucleus-area histogram inspection, gate pass/fail) | Human visual QC (GUI) | Config Authoring (Claude, records the outcome) | Requires a live QuPath viewer session on `DISPLAY=:0`; per CLAUDE.md, GUI-only steps are handed back to the human, Claude authors the artifacts and records results |

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `qupath-extension-braian` (BraiAnDetect) | 1.1.0 [VERIFIED: installed jar at `~/section-pipeline/tools/QuPath/extensions/catalogs/BraiAn catalog/QuPath BraiAn extension/v1.1.0/main-jar/qupath-extension-braian-1.1.0.jar`] | Reads `BraiAn.yml`, drives multi-channel `WatershedCellDetection` + classifier application inside QuPath | Project-mandated (CLAUDE.md: "BraiAnDetect's built-in QuPath detection… over Cellpose"); already installed and pinned to the QuPath 0.6.0-compatible BIOP/BraiAn catalog |
| QuPath | 0.6.0 [VERIFIED: `~/section-pipeline/tools/QuPath/bin/QuPath`, project-pinned] | Hosts the extension, runs `qupath.imagej.detect.cells.WatershedCellDetection`, stores/edits object-classifier JSON | Version-pinned per CLAUDE.md; do not bump |
| SnakeYAML | bundled inside the QuPath/extension classpath [VERIFIED: `org/yaml/snakeyaml/*` classes referenced in `ProjectsConfig.class`] | Parses `BraiAn.yml` into `ProjectsConfig` via a typed `Constructor(ProjectsConfig.class, LoaderOptions)` | Ships with the extension; no separate install needed |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `braian` (Python) | 1.0.5 [VERIFIED: `pip show braian` in `braian` conda env] | Stats-side `BraiAnConfig` YAML (experiment/groups/atlas/output-dir) — a **different, unrelated** YAML file also conventionally named with a `.yml` extension | Only relevant to later stats phases (STATS-01, v2); **not** the schema for this phase's `BraiAn.yml` — do not conflate |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Histogram-peak `histogramThreshold` (native) | Manual percentile/median+k·MAD computed in a Groovy pre-pass, written as a plain numeric `threshold` per section | Native peak-based approach requires zero extra scripting and is exactly what the extension's own maintainers ship in their example config; a custom percentile pre-pass would violate D-03 ("one global BraiAn.yml", no per-section files) unless computed live inside the detection run — worse, not better |
| One `channelDetections` entry (DAPI-anchored, merged classifiers) | Three `channelDetections` entries (DAPI, AF568, AF488) + `OverlappingDetections` for Double+ | The 3-entry pattern is what the extension's own official example demonstrates, and what SCRI-03's task description literally names ("OverlappingDetections (Double+)"). It is a legitimate BraiAnDetect pattern for experiments that don't have a shared nuclear counterstain, but conflicts with CLAUDE.md's DAPI-anchored/no-overlap-heuristic mandate. **Flagged as an open question for Phase 3 planning to resolve explicitly**, see Open Questions #1 |

**Installation:**
No new package installs required for this phase — QuPath 0.6.0 and `qupath-extension-braian` v1.1.0 are already installed and catalog-pinned. `BraiAn.yml` and any classifier JSON are hand-authored/scripted text files, not packages.

**Version verification:** `qupath-extension-braian` v1.1.0 confirmed present on disk at the path above (catalog-installed via BIOP/BraiAn catalog, matching CLAUDE.md's pinned-catalog requirement). No registry lookup applies (this is a QuPath extension jar distributed via a BIOP update-site catalog, not npm/PyPI/crates).

## Package Legitimacy Audit

**Not applicable this phase.** No new external packages are installed in Phase 2 — `qupath-extension-braian` v1.1.0 and the `braian` (Python) 1.0.5 package were already installed and verified during project setup (see `CLAUDE.md` Status log, 2026-06-19/2026-06-22). This phase only authors YAML/JSON text artifacts consumed by already-installed tooling.

**Packages removed due to [SLOP] verdict:** none — no packages evaluated.
**Packages flagged as suspicious [SUS]:** none — no packages evaluated.

## Architecture Patterns

### System Architecture Diagram

```text
┌─────────────────────────────────────────────────────────────────────────┐
│ PHASE 2 SCOPE: config authoring + visual tuning                         │
└─────────────────────────────────────────────────────────────────────────┘

  [Human, Claude]                [Claude, file write]
  TRAP2 paper seed values   ──►   BraiAn.yml (project root)
  + prior classifier refs        ├─ classForDetections
                                  ├─ detectionsCheck {apply,controlChannel}
                                  └─ channelDetections:
                                       - name: DAPI-T4
                                         parameters: {WatershedCellDetectionConfig}
                                           ├─ sigmaMicrons, minAreaMicrons,
                                           │  maxAreaMicrons, cellExpansionMicrons
                                           └─ histogramThreshold {resolutionLevel,
                                              smoothWindowSize, peakProminence, nPeak}
                                         classifiers:
                                           - Fos_Classifier_20x.json  (reused, verify)
                                           - TdT_classifier.json      (rebuilt: Cytoplasm)
                                                │
                                                ▼
                          [Human, QuPath GUI — "Run for project" / single-entry test]
                          Runs WatershedCellDetection on DAPI-T4 using BraiAn.yml params
                                                │
                                                ▼
                    Detected cell objects (Nucleus ROI + Cytoplasm ring, per D-04 entry 1)
                    Each object carries per-channel per-compartment measurements:
                       "Nucleus: AF488-T3 mean", "Cytoplasm: AF568-T2 mean", …
                                                │
                          ┌─────────────────────┴─────────────────────┐
                          ▼                                           ▼
              Fos classifier reads                        TdT classifier reads
              "Nucleus: AF488-T3 mean"                    "Cytoplasm: AF568-T2 mean"
              (CLASS-01 verification point)               (rebuilt this phase)
                          │                                           │
                          └─────────────────────┬─────────────────────┘
                                                 ▼
                          [Human, visual QC in QuPath viewer]
                          D-05 hard gates: nucleus area peak 50–150 µm²
                                           DAPI density 500–2000/mm²
                          DG bleed-check (cytoplasm rings not crossing neighbors)
                          CA1 clean-separability check
                                                 │
                                    PASS both ──►│◄── FAIL either
                                                 ▼            │
                              LOCK BraiAn.yml + classifiers   └─► adjust sigma/area/
                              (Phase 2 done, feeds SCRI-03)        threshold params,
                                                                    re-tune, re-check
```

### Recommended Project Structure

```
M3 Hippocampus 20x 062926 3 plane/     # QuPath project root
├── BraiAn.yml                          # NEW this phase — SCRI-02
├── classifiers/
│   ├── classes.json                    # already present
│   └── object_classifiers/
│       ├── Fos_Classifier_20x.json     # copied/reused from 062226 Redo, threshold re-derived
│       └── TdT_classifier.json         # rebuilt: Cytoplasm compartment, histogram-relative threshold
├── scripts/
│   └── 01_load_abba_rois.groovy        # already present (Phase 1)
└── data/
    └── 1/                              # entry 1 — tuning substrate (D-04)
```

### Pattern 1: Single-Entry, Multi-Classifier `channelDetections` (recommended)

**What:** One `channelDetections` list item, `name` set to the nuclear-anchor channel (`DAPI-T4`), with `parameters.cellExpansionMicrons > 0` and a `classifiers` list containing every downstream marker classifier that should run against the SAME detected-object set.

**When to use:** Whenever a shared nuclear counterstain (DAPI) exists and colocalization must be nucleus-anchored (this project, per CLAUDE.md).

**Example (adapted from the extension's own official example, field names VERIFIED against jar bytecode):**
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
      requestedPixelSizeMicrons: 0.6905355   # match OME-XML PhysicalSizeX (server.json)
      backgroundRadiusMicrons: 10
      backgroundByReconstruction: true
      medianRadiusMicrons: 0.0
      sigmaMicrons: 2.0            # seed — see Code Examples / Open Questions #3 for exact value
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

### Anti-Patterns to Avoid

- **Per-marker independent `channelDetections` entries for a project that has DAPI:** running separate WatershedCellDetection passes on `AF568-T2` and `AF488-T3` themselves (segmenting each marker's own signal as if it were the nuclear channel) creates two independently-segmented object sets that then require geometric-overlap merging (`OverlappingDetections`) to compute Double+ — this is the extension's own official example pattern, but it violates CLAUDE.md's "nucleus contains marker centroid, never proximity/overlap heuristics" when a true DAPI channel exists. Use the single-entry pattern above instead.
- **Absolute numeric `threshold` for a series meant to scale:** satisfies nothing beyond the single tuning section; will silently drift across a real multi-section, multi-day-imaging series (staining/exposure variance) — use `histogramThreshold` instead (D-01).
- **Classifying TdTomato on the `Nucleus` compartment:** this is the exact mistake already present in the existing `TRAP2TdT_Classifier_20x.json` (`"measurement": "Nucleus: AF568-T2 mean"`) that this phase must fix — TdTomato is cytosolic; it must read `Cytoplasm: AF568-T2 mean`, which only exists if `cellExpansionMicrons > 0`.
- **Skipping `resolvePathIfPresent`/relative-path awareness:** `qupath/ext/braian/utils/BraiAn.resolvePath` resolves classifier and config paths **relative to the QuPath project's base directory** (`Projects.getBaseDirectory(project)`), not relative to the working directory the script happens to run from — classifier JSON referenced by `name` in `BraiAn.yml` must exist under `<project>/classifiers/object_classifiers/<name>.json`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Per-section adaptive threshold | A Groovy pre-pass computing percentile/median+k·MAD on the DAPI histogram and writing a per-section absolute `threshold` | `histogramThreshold` (`resolutionLevel`, `smoothWindowSize`, `peakProminence`, `nPeak`) in `WatershedCellDetectionConfig` | Native, already handles smoothing + peak-finding + "Nth valid peak within a trust-worthy window" edge cases (empty/insufficient-peaks errors are already implemented and logged) — reinventing this in Groovy duplicates tested logic and risks subtly different edge-case behavior |
| Nucleus vs. cytoplasm measurement computation | A Groovy script manually computing mean intensity inside a manually-drawn expansion ring | QuPath core `WatershedCellDetection` with `cellExpansionMicrons > 0` + `makeMeasurements: true` (built into `WatershedCellDetectionConfig`) | QuPath core already produces the `Cytoplasm: <channel> mean` / `Nucleus: <channel> mean` measurement set for every channel automatically, with expansion clipped at neighboring-cell boundaries by construction |
| Compound (double-positive) classification on a single detected-object set | A custom Groovy "if Fos+ and TdT+ then Double+" post-processing pass | Sequential `SingleClassifier` application within the same `channelDetections.classifiers` list (`PathClassTools.mergeClasses` merges the resulting classes onto the same object automatically) | This is literally how `SingleClassifier.classifyObjects` is implemented in the extension — no custom merge logic needed for the single-entry topology recommended above |

**Key insight:** BraiAnDetect's config-driven design already encodes every mechanism this phase needs (relative threshold, cytoplasm-compartment classification, compound classification) as declarative YAML/JSON — the risk in this phase is almost entirely about **choosing the right topology** (single DAPI-anchored entry vs. per-marker entries), not about missing functionality.

## Common Pitfalls

### Pitfall 1: Wrong `channelDetections` topology silently produces proximity-based Double+ later

**What goes wrong:** If Phase 3's `02_detect_classify.groovy` follows SCRI-03's literal wording ("OverlappingDetections (Double+)") and the extension's own official example pattern, it would configure `channelDetections` with separate entries per marker channel — which requires WatershedCellDetection to run **on the marker channels themselves**, not on DAPI. This produces two independently-segmented object sets whose geometric overlap (not nucleus-containment) determines Double+.
**Why it happens:** The extension's only published example (`BraiAn.yml` in the upstream repo) uses exactly this per-marker pattern, because that experiment had no shared nuclear counterstain channel to anchor on.
**How to avoid:** Decide the topology explicitly in Phase 2's `BraiAn.yml` (single DAPI-anchored entry, recommended above) and flag for Phase 3 planning that `OverlappingDetections` may not be the applicable mechanism if this topology is used — the merged-classification approach (`SingleClassifier` + `PathClassTools.mergeClasses`) already produces Double+ as a compound class on the same object, with no separate merge step needed.
**Warning signs:** If Phase 3 planning proposes calling `OverlappingDetections`/`getOverlappingObjectIfPresent` against detection sets that both trace back to the same DAPI-derived container, that is redundant (they're already the same objects) — a sign the topology decision was not actually made explicit.

### Pitfall 2: Absolute threshold silently baked in via a JSON classifier, not BraiAn.yml

**What goes wrong:** `histogramThreshold` in `BraiAn.yml` only controls the WatershedCellDetection **detection** threshold (which pixels count as "nucleus" at all). The Fos/TdT **classifier** JSONs are a separate mechanism (`SimpleClassifier` / `ClassifyByMeasurementFunction`) with their own hardcoded numeric `threshold` field (e.g. `9341.31736526946` in the existing `Fos_Classifier_20x.json`) — fixing D-01 in `BraiAn.yml` does **not** automatically fix D-02 in the classifier JSONs.
**Why it happens:** Two different config surfaces (extension YAML vs. QuPath-core classifier JSON) both have a field literally named `threshold`, easy to conflate.
**How to avoid:** D-02 requires a **separate** histogram-relative re-derivation of the classifier JSON thresholds (e.g., computed from the section's own Fos/TdT measurement distribution at tuning time and written into the classifier JSON's numeric `threshold` field) — this is not solved by `BraiAn.yml` alone. Confirm with the planner whether this is a one-time manual re-derivation on the tuning section (Phase 2, matching D-04's single-section scope) or a per-section computation deferred to the Phase-3 script.
**Warning signs:** A classifier JSON with a `threshold` value that was never touched during tuning is a sign D-02 was skipped.

### Pitfall 3: `cellExpansionMicrons` bleeding in dense DG despite QuPath's built-in clipping

**What goes wrong:** QuPath's cell expansion is documented to clip cytoplasm rings at neighboring detected-cell boundaries — but in very dense regions (DG granule cell layer) with small inter-nuclear spacing, a 5 µm ring can still functionally merge with an adjacent nucleus's true cytoplasm if `sigmaMicrons`/`minAreaMicrons` under-segments touching nuclei into one blob first (the clipping only helps if neighboring nuclei were correctly separated in the first place).
**Why it happens:** Expansion-ring clipping assumes correct nucleus separation upstream; a segmentation problem (merged nuclei) manifests downstream as an apparent expansion-bleed problem.
**How to avoid:** This is exactly why D-04 requires tuning on DG specifically and why the DG bleed-check must be visual, not just numeric (the D-05 gates check area/density distribution, which can mask localized DG-specific merging even if the whole-section average passes).
**Warning signs:** Nucleus area histogram passes the 50–150 µm² gate globally, but DG sub-region visually shows fused/oversized nuclei blobs.

### Pitfall 4: `qupath.imagej.detect.cells.WatershedCellDetection` parameter name drift across QuPath versions

**What goes wrong:** QuPath's built-in cell detection plugin has had parameter renames/behavior changes across versions (e.g., `WatershedCellDetection` vs. the newer `Cell detection`/StarDist-based commands in some 0.5.x+ builds); a config schema copied from a slightly different QuPath/extension version pairing than 0.6.0 + extension 1.1.0 could silently no-op unrecognized keys.
**Why it happens:** `WatershedCellDetectionConfig.build()` uses Java reflection over declared fields to build the parameter map passed to `runPlugin` — if a key doesn't match what the specific bundled `WatershedCellDetection` plugin version expects, the extension has no way to detect the mismatch at config-parse time (SnakeYAML would silently ignore or error only on structurally-invalid YAML, not semantically-wrong keys for a different plugin version).
**How to avoid:** All field names in this document were extracted directly from the **installed** jar (v1.1.0) matched to the **installed** QuPath (0.6.0) — do not substitute field names from documentation for a different extension version without re-verifying against the actual jar on this machine.
**Warning signs:** Detection run with `BraiAn.yml` produces zero cells project-wide (not just a channel-name mismatch, per Critical Risks in STATE.md) — check QuPath's log/console for unrecognized-parameter warnings.

## Code Examples

### Reading the config from a Groovy script (for Phase 3 reference, not this phase's task)
```groovy
// Source: reconstructed from qupath/ext/braian/config/ProjectsConfig.class bytecode
// (static-ish `read(String yamlFileName)` throws IOException, YAMLException;
//  resolves the path relative to the QuPath project's base directory via
//  qupath.ext.braian.utils.BraiAn.resolvePath)
import qupath.ext.braian.config.ProjectsConfig

def config = ProjectsConfig.read("BraiAn.yml")
println "classForDetections: ${config.getClassForDetections()}"
println "channels configured: ${config.getChannelDetections()*.getName()}"
```

### Existing, reusable Fos classifier (CLASS-01 already satisfied)
```json
// Source: M3 Hippocampus 20x 062226/M3 Hippocampus 20x 062226 Redo/classifiers/object_classifiers/Fos_Classifier_20x.json
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
  "pathClasses": ["Negative", "Positive"],
  "filter": "DETECTIONS_ALL"
}
```
This file already satisfies CLASS-01's compartment requirement (`Nucleus:`, not `Cytoplasm:`). Only the numeric `threshold` needs re-derivation per D-02 during this phase's tuning pass.

### Existing, WRONG-compartment TdT classifier (must be rebuilt)
```json
// Source: M3 Hippocampus 20x 062226/M3 Hippocampus 20x 062226 Redo/classifiers/object_classifiers/TRAP2TdT_Classifier_20x.json
{
  "object_classifier_type": "SimpleClassifier",
  "function": {
    "classifier_fun": "ClassifyByMeasurementFunction",
    "measurement": "Nucleus: AF568-T2 mean",   // WRONG — TdTomato is cytosolic
    "pathClassBelow": "Negative",
    "pathClassEquals": "Other",
    "pathClassAbove": "Other",
    "threshold": 10200.8443
  },
  "pathClasses": ["Negative", "Other"],
  "filter": "DETECTIONS_ALL"
}
```
Rebuild with `"measurement": "Cytoplasm: AF568-T2 mean"` and a histogram-relative-derived threshold. Note: `pathClassEquals`/`pathClassAbove` here is `"Other"`, not `"Positive"` — recommend standardizing to `"Positive"`/`"Negative"` for consistency with the Fos classifier and with downstream BraiAnalyse marker naming conventions, unless the planner has a reason to keep `"Other"`.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| Absolute pixel-intensity threshold per classifier (~10200 TdT / ~9341 Fos, 16-bit) | Histogram-relative threshold (`histogramThreshold` block in `BraiAn.yml`; classifier JSON thresholds re-derived per-section-distribution) | This phase (D-01/D-02, 2026-07-07) | Removes brightness-drift as a source of series-wide false negatives/positives; makes one global `BraiAn.yml` viable across the whole series (D-03) |
| Nucleus-compartment TdT classification (`TRAP2TdT_Classifier_20x.json`) | Cytoplasm-compartment TdT classification (rebuilt this phase) | This phase (CLASS-02 prep, Claude's Discretion) | Fixes a real mis-counting bug: cytosolic TdTomato signal was being read from the nuclear ROI, systematically under/over-counting depending on nuclear TdTomato bleed-through |

**Deprecated/outdated:**
- `Automated Cell Counting Test/classifiers/object_classifiers/{TdT,Fos}_*.json`: wrong channel names (`Cy3-T1`/`EGFP-T2` instead of `AF568-T2`/`AF488-T3`) — stale from an earlier acquisition naming convention, explicitly excluded from reuse in CONTEXT.md.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | TRAP2-paper-seeded numeric values (sigma ~2.5 µm optimized vs. 1.5 µm QuPath default, min area 20 µm², max area 400 µm², an "intensity threshold of 0.15" reported as a normalized/relative value) were obtained via a WebSearch synthesis after two direct attempts to fetch the primary source (bioRxiv 2024.09.16.611953 full-text and F1000Research 15:410) both returned HTTP 403. **These numbers were not read directly from the paper this session.** | Code Examples / State of the Art seed values | If the WebSearch synthesis mis-attributed generic-QuPath-default values as paper-reported values, the tuning starting point could be off; low real risk because D-05's hard gates (area peak 50–150 µm², density 500–2000/mm²) will catch a badly-seeded sigma/area during the mandatory visual tuning pass regardless |
| A2 | `histogramThreshold`'s peak-finding semantics (picks the `nPeak`-th valid intensity-histogram peak within a "trust-worthy interval [windowSize:end]", after smoothing with `smoothWindowSize` and filtering by `peakProminence`) were reconstructed from decompiled bytecode logic (`getNthValidPeak`, `findHistogramPeaks`, debug log strings) rather than from prose documentation, since no separate documentation page for this specific mechanism was found | Summary, Standard Stack, Code Examples | If the actual peak-selection semantics differ subtly from this reconstruction (e.g., off-by-one in which peak counts as "background" vs. "signal"), the resulting threshold could sit on the wrong side of the true nucleus/background boundary — mitigated because the tuning pass is visual and gated (D-05), so a wrong `nPeak` choice will be visible as gross over/under-detection |
| A3 | The recommended single-`channelDetections`-entry (DAPI-anchored, merged-classifier) topology is the correct one for `SCRI-02`/`CLASS-01`, even though `SCRI-03`'s own requirement text names `OverlappingDetections` (which implies the extension's alternate per-marker-channel topology) | Summary, Anti-Patterns, Pitfall 1 | If Phase 3 planning actually needs the per-marker topology (e.g., because DAPI signal quality at 20x Airyscan proves insufficient to independently anchor nuclei, or because `OverlappingDetections` turns out to serve a different, compatible purpose not fully resolved by this research), Phase 2's `BraiAn.yml` structure would need to be revised before Phase 3 can proceed — flagged explicitly as Open Question #1 for the planner to resolve, ideally by discussing with the project owner or re-inspecting `OverlappingDetections`'s exact merge semantics before Phase 3 planning locks in |
| A4 | `requestedPixelSizeMicrons` should be set to match the OME-XML `PhysicalSizeX` (0.6905355 µm/px, confirmed in `server.json`) rather than left at a round number like `1.0` (as in the extension's own example) | Code Examples (Pattern 1) | If left at a mismatched value, WatershedCellDetection would internally resample, potentially altering effective sigma/area in physical units — low risk since it's visually gated, but worth an explicit planner decision rather than copy-pasting the upstream example's `1` |

**If this table is empty:** N/A — see entries above; all are flagged with concrete mitigations already in the D-05 gate design.

## Open Questions

1. **Is the single-DAPI-entry `channelDetections` topology (this research's recommendation) or the per-marker-channel + `OverlappingDetections` topology (matching `SCRI-03`'s literal wording and the extension's official example) the one Phase 3 should actually implement?**
   - What we know: `CLAUDE.md`'s nucleus-anchored/no-overlap-heuristic rule and the already-correct `Fos_Classifier_20x.json` (reading `Nucleus: AF488-T3 mean` on what is presumably a DAPI-derived object) both point to the single-entry design. The extension's own official example and `SCRI-03`'s wording point to the per-marker design.
   - What's unclear: Whether `SCRI-03`'s mention of `OverlappingDetections` was written with full knowledge of the single-DAPI-entry alternative, or was written by pattern-matching the extension's public example without considering CLAUDE.md's constraint.
   - Recommendation: Resolve this explicitly in Phase 2 planning (it fully determines the shape of `channelDetections` in `BraiAn.yml`, this phase's deliverable) rather than deferring silently to Phase 3 — recommend the single-DAPI-entry design per the Anti-Patterns/Pitfall 1 reasoning above, and add a note to STATE.md flagging that `SCRI-03`'s wording may need revision once Phase 3 is discussed.

2. **Exact TRAP2-paper-reported sigma / min-max-area / threshold / cell-expansion values.**
   - What we know: CONTEXT.md already commits to a 5 µm cytoplasmic expansion "TRAP2-paper seed" (matches QuPath's own documented default, corroborating evidence). A WebSearch synthesis (not primary-source-verified this session) suggests sigma ≈ 2.5 µm (optimized, vs. 1.5 µm QuPath default), min area 20 µm², max area 400 µm², an "intensity threshold of 0.15" (likely a normalized/relative value, not raw 16-bit).
   - What's unclear: Whether these are literally the paper's numbers or blended with generic QuPath-default knowledge (primary source access failed with HTTP 403 twice).
   - Recommendation: Planner should treat these as a starting point only, seed the tuning pass with them, and rely on D-05's hard gates (area peak 50–150 µm², density 500–2000/mm²) as the actual acceptance criterion — the exact paper provenance of the seed values is not load-bearing since the gates are empirical, not paper-derived.

3. **Whether classifier-JSON threshold re-derivation (D-02) is a one-time manual step this phase, or needs to be computed programmatically per-section in the Phase-3 script.**
   - What we know: `BraiAn.yml`'s `histogramThreshold` only affects detection, not classifier JSON thresholds (Pitfall 2).
   - What's unclear: CONTEXT.md's D-02 says classifier cutoffs should follow "the same histogram-relative philosophy" but doesn't specify the delivery mechanism (a fixed number derived once from the tuning section's own histogram vs. a script-computed-per-section value applied at Phase-3 runtime).
   - Recommendation: For Phase 2's scope (SCRI-02/CLASS-01, single tuning section only), a one-time manual re-derivation on entry 1's own measurement histogram is sufficient and matches D-04's single-section scope; flag for Phase 3 planning whether a programmatic per-section version is needed to fully satisfy D-03's "one global config, no per-section re-tuning" for the classifier thresholds specifically (as opposed to just the detection threshold).

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| QuPath | Running WatershedCellDetection, editing classifier JSON, visual QC | ✓ | 0.6.0 [VERIFIED: `~/section-pipeline/tools/QuPath/bin/QuPath`] | — |
| `qupath-extension-braian` (BraiAnDetect) | Reading `BraiAn.yml`, running the detection+classification pipeline | ✓ | 1.1.0 [VERIFIED: catalog-installed jar found on disk] | — |
| Real X display (`DISPLAY=:0`) | Human visual QC of detection overlay, DG bleed-check, gate measurement | ✓ [VERIFIED: CLAUDE.md status log, "OpenGL verified hardware-accelerated"] | — | — |
| Java runtime | Required to run QuPath itself | ✓ (QuPath ships its own bundled jlink runtime under `lib/runtime/`) | bundled, no standalone `java`/`javap` binary exposed on `PATH` | None needed — QuPath's own launcher (`bin/QuPath`) is self-contained; this research had to work around the *absence* of a standalone `java`/`javap` for decompilation (used `strings` on `.class` files instead), but this does not block the actual pipeline, only ad-hoc jar inspection |

**Missing dependencies with no fallback:** none.
**Missing dependencies with fallback:** standalone `java`/`javap` for future jar inspection — worked around this session via `strings`; if deeper decompilation is ever needed, install a JDK (`sudo apt install openjdk-21-jdk-headless` or similar) is a scriptable option but was not needed here.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | None (no automated test suite for this GUI-driven scientific pipeline) — validation is measurement-based visual/numeric QC inside QuPath |
| Config file | none — see Wave 0 |
| Quick run command | Manual: in QuPath, run "Run for project" (or single-entry run) with the tuning `BraiAn.yml`, then read the nucleus-area histogram and cell count from the Measurements panel / exported `summary.json` |
| Full suite command | Same manual run, extended to compute density (`cell count / annotation area in mm²`) via a short Groovy snippet or the exported measurement table, checked against both D-05 gates |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|---------------------|-------------|
| SCRI-02 | `BraiAn.yml` produces non-zero cells in Fos and TdT channels on entry 1 | manual-only (requires QuPath GUI + live image data) | N/A — human runs detection in QuPath, inspects `summary.json` cell counts by class | ❌ Wave 0 — `summary.json` will be written by QuPath itself once detection runs; no pre-existing test file needed |
| SCRI-02 | Nucleus area distribution peaks 50–150 µm² (D-05 gate 1) | manual-only, numeric check on exported measurements | N/A — human reads histogram/exports measurement CSV and checks the peak bin | ❌ Wave 0 — no measurement-export script currently exists for this check; Phase 2 plan should include a small Groovy or Python snippet to compute the peak from exported data, OR rely on QuPath's built-in histogram view |
| SCRI-02 | DAPI nucleus density 500–2000/mm² (D-05 gate 2) | manual-only, numeric check (`cell count / annotation area mm²`) | N/A — same as above; requires annotation area in mm² (from ABBA-derived atlas-region annotations, already present from Phase 1) | ❌ Wave 0 — same snippet as above should compute both gates together |
| CLASS-01 | `Fos_Classifier_20x.json` reads `Nucleus: AF488-T3 mean` | automatable (static file check) | `python3 -c "import json,sys; d=json.load(open(sys.argv[1])); assert d['function']['measurement']=='Nucleus: AF488-T3 mean'" "<path>/Fos_Classifier_20x.json"` | ✅ — file already exists and already passes this check (confirmed this session by direct read) |
| CLASS-01 | Detection overlay shows Fos+ only in nuclei (visual confirmation) | manual-only (requires QuPath viewer) | N/A — human visually inspects overlay on DG + CA1 per D-04 | ❌ Wave 0 — no automated overlay-diff tooling exists; this is inherently a human visual-QC step per CLAUDE.md's GUI-only rule |

### Sampling Rate

- **Per task commit (each parameter-tuning iteration):** manual QuPath re-run on entry 1 + visual DG/CA1 inspection; the automatable CLASS-01 static-file check (`Fos_Classifier_20x.json` measurement field) can run on every classifier-JSON edit
- **Per wave merge:** full D-05 gate computation (area peak + density) on entry 1, both DG and CA1
- **Phase gate:** both D-05 gates PASS on entry 1 (DG + CA1) before `BraiAn.yml` and both classifier JSONs are considered locked; D-06 (Double+ ratio) and D-07 (Fos+ negative-control) are reported but not gating, per CONTEXT.md

### Wave 0 Gaps

- [ ] A small Groovy (or Python, post-export) snippet to compute (1) the nucleus-area-distribution peak bin and (2) DAPI density per mm² from a detection run's measurement export — currently no such script exists anywhere in the repo (`find . -iname "*.groovy"` shows only the Phase-1 ABBA-loading script; no measurement-QC script)
- [ ] A static-check script (even a one-line `python3 -c` or `jq` invocation) to assert classifier JSON `function.measurement` strings match the required compartment string, runnable as a fast automated check per CLASS-01/CLASS-02
- Framework install: none needed — no test framework gap, this is inherently GUI/measurement-based validation

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | N/A — single-user local scientific pipeline, no auth surface |
| V3 Session Management | No | N/A |
| V4 Access Control | No | N/A — local filesystem, single user |
| V5 Input Validation | Yes (narrow) | `BraiAn.yml` is parsed via a **typed** SnakeYAML `Constructor(ProjectsConfig.class, LoaderOptions)` rather than the generic `Constructor()` — this is the correct, safer SnakeYAML usage pattern (restricts deserialization to the declared bean graph, not arbitrary Java types) and was confirmed directly in the decompiled bytecode; no action needed beyond not changing this at authoring time. Classifier JSON is read via QuPath's own `ObjectClassifiers.readClassifier`, not hand-parsed |
| V6 Cryptography | No | N/A — no secrets, no crypto operations in this phase |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| YAML deserialization RCE (generic SnakeYAML `Constructor()` executing arbitrary Java types from untrusted YAML) | Tampering / Elevation of Privilege | Already mitigated upstream — the extension uses the typed `Constructor(ProjectsConfig.class, LoaderOptions)` form, confirmed in bytecode. Not a concern for this phase since `BraiAn.yml` is authored locally by Claude/the researcher, not accepted from an untrusted external source |
| Path traversal via classifier `name` field resolving outside the project directory | Tampering | `qupath/ext/braian/utils/BraiAn.resolvePath` resolves relative to the QuPath project's base directory; only a concern if classifier `name` values are ever sourced from untrusted input (they are not — hand-authored by the researcher) |

## Sources

### Primary (HIGH confidence)
- Decompiled `.class` files inside the **installed** `qupath-extension-braian-1.1.0.jar` at `~/section-pipeline/tools/QuPath/extensions/catalogs/BraiAn catalog/QuPath BraiAn extension/v1.1.0/main-jar/qupath-extension-braian-1.1.0.jar` — `strings`-extracted field/method names for `ProjectsConfig`, `ChannelDetectionsConfig`, `ChannelClassifierConfig`, `DetectionsCheckConfig`, `WatershedCellDetectionConfig`, `AutoThresholdParmameters`, `AbstractDetections`, `ChannelDetections`, `SingleClassifier`, `OverlappingDetections`, `IncompatibleDetections`.
- Existing project files read directly: `Fos_Classifier_20x.json`, `TRAP2TdT_Classifier_20x.json` (both under `M3 Hippocampus 20x 062226/M3 Hippocampus 20x 062226 Redo/classifiers/object_classifiers/`), `server.json` and `classes.json` under `M3 Hippocampus 20x 062926 3 plane/`, `braian` Python package's `config.py` (installed at `~/miniforge3/envs/braian/lib/python3.11/site-packages/braian/config.py`).

### Secondary (MEDIUM confidence)
- [Official example `BraiAn.yml`](https://raw.githubusercontent.com/carlocastoldi/qupath-extension-braian/master/BraiAn.yml) — fetched verbatim via WebFetch; every field name matches the decompiled bytecode exactly, cross-verifying the schema at effectively VERIFIED confidence for structure (values in that example are illustrative for a different experiment, not this project's numbers).

### Tertiary (LOW confidence)
- WebSearch synthesis citing TRAP2/F1000Research (15:410) numeric parameter values (sigma, min/max area, "intensity threshold of 0.15") — direct fetch of both the bioRxiv full-text (2024.09.16.611953) and the F1000Research article page returned HTTP 403 in this session; values are marked `[ASSUMED]` in Assumptions Log A1 and should be treated as a starting seed only, validated by the D-05 empirical gates.

## Metadata

**Confidence breakdown:**
- Standard stack (BraiAn.yml schema): HIGH — verified directly from the installed jar bytecode, cross-checked against the extension's own official example file, matching exactly
- Architecture (topology recommendation): MEDIUM — schema mechanism is verified, but the single-entry-vs-per-marker topology decision required inference from CLAUDE.md constraints + `SingleClassifier`'s merge behavior since no explicit "recommended topology for a project with DAPI" documentation was found; flagged as Open Question #1
- Pitfalls: HIGH for the compartment/threshold-conflation pitfalls (directly evidenced by existing project files); MEDIUM for the histogram-peak semantics reconstruction (bytecode-inferred, not documentation-confirmed)
- TRAP2-paper seed values: LOW — primary source unreachable this session (HTTP 403 twice); explicitly flagged and not load-bearing due to D-05's empirical gates

**Research date:** 2026-07-07
**Valid until:** 2026-08-06 (30 days — stable, locally-installed, version-pinned tooling; re-verify if QuPath or the BraiAn extension catalog version changes)
