# Phase 3: Detection Script and Single-Section End-to-End Test - Research

**Researched:** 2026-07-09
**Domain:** QuPath 0.6.0 Groovy scripting — nucleus-anchored multichannel classification, per-cell local-background-subtracted intensity measurement, ABBA/CCFv3 atlas-coordinate transform, atlas-region count rollup
**Confidence:** HIGH (core mechanics verified directly against the **installed** QuPath 0.6.0 / BraiAn 1.1.0 / ABBA 0.4.0 jars — bytecode + bundled javadoc — not just web search)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Detection stays separate. `run_braian_detection.groovy` remains the standalone heavy BraiAnDetect pass. `02_detect_classify.groovy` performs classification + atlas labels + count table **only**, assuming detections already exist. (Note: the script name says "detect_classify" but the detection trigger lives elsewhere — the numbered script is the classify/label/report entry point.)
- **D-02:** Guard on zero detections, re-classify in place idempotently. If an entry has no detections, abort with a clear message (matches `classify_markers.groovy`'s existing "No detections — Aborting" guard). If detections exist, (re)classify them in place — `setPathClass` overwrites, so re-running just refreshes classes. Under "Run for project", undetected entries abort cleanly rather than erroring the batch.
- **D-03:** Fix the SSp autofluorescence problem now, not defer, even though SSp false-positives land outside the CA1/CA2/CA3/DG subfields Phase 3 validates — build the background-robust measure this phase so the classifier is series-ready before the batch run.
- **D-04:** Use **local-background subtraction / background-normalized per-compartment intensity — NOT a nucleus:cytoplasm compartment-contrast ratio**. Rationale: forward-scaling to a future **PNN** (pericellular ECM) compartment, which a two-compartment intracellular ratio has nowhere to host. Local-background subtraction is compartment-agnostic: define whatever compartment the marker occupies (nucleus for Fos, cytoplasmic ring for TdT, a pericellular annulus for a future PNN channel) and subtract the local peri-cellular tissue background around each cell. **This design constraint is deliberate and locked.**
- **D-05:** Re-derive the positive thresholds on the new background-subtracted measure. The locked absolute cutoffs (Fos ≥13000.4538 nuclear, TdT ≥16766.4671 cytoplasmic from `02-LOCK-RECORD.md`) are **superseded** for classification — new cutoffs are derived on the background-normalized measure, keeping the histogram-relative philosophy from Phase 2 (D-01/D-02 there). The old absolute cutoffs remain a documented reference point, not the operative rule.

### Claude's Discretion
- **Atlas coordinate check (SC3):** satisfy "printed Atlas_X in 5,000–10,000 µm" with a **lightweight sanity-print** of a sample of classified cells' CCFv3 atlas X coordinates. Do **not** build a full per-cell Atlas_X/Y/Z measurement column here — that is v2 `EXP-01`/`EXP-03` export territory.
- **Per-region count table (SC4):** roll per-class counts **up onto the region annotations as measurements** so they render in the QuPath annotation-pane measurement table for CA1/CA2/CA3/DG (at minimum); a console-printed table is a fine complement, and BraiAn's `_regions.tsv` (written by the separate detection script) **can be reused rather than reinvented** — see Common Pitfalls for a staleness caveat on this reuse.
- **Atlas-label mechanism** (resolveHierarchy / parent-annotation assignment so each cell carries its region label — SC2) is technical plumbing → researcher/planner's call. See Pattern 3 below.
- **Region exclusions** `DG-sg` + `VS` remain as locked in Phase 2 (`classify_markers.groovy` `EXCLUDE_ACRONYMS`). Whether the new background-robust measure reduces the need to exclude/flag SSp is an outcome to observe, not a Phase-3 exclusion decision to lock now.

### Deferred Ideas (OUT OF SCOPE)
- **PNN (perineuronal net / WFA) quantification** — future phase; needs a new stain/channel and a pericellular-annulus detection compartment. Its extracellular nature is *why* D-04 chose local-background subtraction over a nucleus:cytoplasm ratio.
- **Full per-cell Atlas_X/Y/Z micron export column + per-region TSV** — v2 `EXP-01`/`EXP-02`/`EXP-03`. Phase 3 does only a sanity-print of atlas coordinates.
- **Whole-brain / full-series autofluorescence validation** — series phase (SERIES-01/02).
- **Biological-plausibility gates** (Double+/TdT+ ratio, DAPI density, Fos negative-control) — Phase 4 (VAL-01).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SCRI-03 | `02_detect_classify.groovy` written and tested on one section — runs classification (Fos/TdT/Double+/Negative), atlas labeling, and per-region count rollup on BraiAnDetect-produced detections; produces `data.qpdata` with classified cells | Pattern 1 (background-robust measure), Pattern 2 (threshold re-derivation), Pattern 3 (atlas label), Pattern 4 (count rollup), Pattern 5 (Atlas_X sanity check), all Code Examples, Common Pitfalls 1–10 |
</phase_requirements>

## Summary

Phase 3 extends the already-proven `classify_markers.groovy` skeleton (nucleus-anchored compound Fos+/TdT+/Double+/Negative classification, reads thresholds at runtime from classifier JSON, DG-sg/VS exclusion) with four new capabilities: **(1)** a compartment-agnostic local-background-subtracted intensity measure that fixes the SSp autofluorescence false-positive bug found in Phase 2, **(2)** re-derivation of positive-classification thresholds on that new measure using the same histogram-relative (nPeak/valley) philosophy already locked in Phase 2, **(3)** an atlas-region label for every classified cell, and **(4)** roll-up of per-class counts onto the CA1/CA2/CA3/DG region annotations as QuPath measurements, plus a lightweight Atlas_X micron sanity-print.

None of these four capabilities require any new library. Every mechanism was located and verified directly inside the **already-installed** QuPath 0.6.0 core jars (`qupath-core-0.6.0.jar`, `qupath-core-processing-0.6.0.jar`, with their bundled javadoc jars) and the already-installed BraiAn (v1.1.0) and ABBA (v0.4.0) extension jars: `qupath.lib.roi.RoiTools` (buffer/subtract for annulus geometry), `qupath.lib.analysis.features.ObjectMeasurements` (official API for sampling mean pixel intensity over an arbitrary ROI, used internally by QuPath's own Nucleus/Cytoplasm measurements), `qupath.lib.objects.hierarchy.PathObjectHierarchy.getAllObjectsForRegion` (spatially-indexed neighbor lookup, non-deprecated in 0.6.0), `qupath.ext.braian.ChannelHistogram`'s public static `findPeaks`/`zeroPhaseFilter` methods (the exact histogram-peak-finding logic already locked into `BraiAn.yml`'s detection threshold — reusable on an arbitrary measurement histogram, not just the raw image channel histogram it was originally written for), and `qupath.ext.biop.abba.AtlasTools.getAtlasToPixelTransform(imageData).inverse()` (the official ABBA pixel↔atlas coordinate transform, confirmed against an official BIOP-author example script).

**Primary recommendation:** Extend `classify_markers.groovy` in place rather than rewriting; add a background-subtraction pre-pass (Pattern 1) that writes new per-cell measurements (`Nucleus: AF488-T3 mean (bg-sub)`, `Cytoplasm: AF568-T2 mean (bg-sub)`), re-derive thresholds by feeding a self-built histogram of those new measurements into `ChannelHistogram.findPeaks` (Pattern 2), keep the existing centroid-in-ROI region-containment idiom already proven in `qc_detection_gates.groovy` for both the atlas label and the count rollup (Patterns 3–4, safer than depending on an unverified BraiAnDetect container-nesting hypothesis), and do the Atlas_X sanity print with the official `AtlasTools.getAtlasToPixelTransform(...).inverse()` pattern on a small sample only (Pattern 5) — not a full per-cell export column, per CONTEXT.md discretion.

## Architectural Responsibility Map

This is a single-machine, GUI-mediated scientific pipeline, not a networked multi-tier application. The table below adapts the standard tiering to this project's actual layers (see `.claude/CLAUDE.md` "Layers"):

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Background-robust per-cell measurement (D-04) | QuPath Groovy scripting layer (`02_detect_classify.groovy`) | QuPath core API (`RoiTools`, `ObjectMeasurements`) | New derived measurement is per-cell, computed from already-detected pixel/ROI data already in memory — no new detection pass, no persistence layer beyond `data.qpdata` |
| Threshold re-derivation (D-05) | QuPath Groovy scripting layer | BraiAn extension (`ChannelHistogram` static utilities) | Reuses the extension's own histogram-peak-finding primitives rather than reimplementing D-01/D-02's philosophy from scratch |
| Compound classification (Fos+/TdT+/Double+/Negative) | QuPath Groovy scripting layer | — | Direct continuation of `classify_markers.groovy`; explicitly NOT `BraiAn.yml classifiers:`/`OverlappingDetections` (Deviation #1, incompatible topology) |
| Atlas region label per cell (SC2) | QuPath object hierarchy (in-memory PathObject graph) | ABBA extension (annotation load, already done in `01_load_abba_rois.groovy`) | Region membership is inherently a spatial/hierarchical relationship, not new data to fetch |
| Per-region count rollup (SC4) | QuPath Groovy scripting layer, written onto annotation `MeasurementList` | QuPath GUI annotation pane (rendering only) | Rollup is computed once per script run and persisted as annotation measurements inside `data.qpdata`, not a separate report artifact |
| Atlas_X micron sanity check (SC3) | ABBA extension (`AtlasTools.getAtlasToPixelTransform`) + imglib2-realtransform (bundled dependency) | QuPath Groovy scripting layer (println only) | Coordinate transform math belongs to ABBA's registration model, not something to reimplement; this phase only consumes it for a console printout |
| Persistence | `data.qpdata` (QuPath binary object store) | `data/<entry>/summary.json` (auto-refreshed count snapshot) | Established in Phase 1; unchanged this phase |

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| QuPath | 0.6.0 (already installed, pinned) | Host application + Groovy scripting engine + `qupath-core`/`qupath-core-processing` APIs used directly (`RoiTools`, `ObjectMeasurements`, `PathObjectHierarchy`, `PathObjects`, `MeasurementList`) | Project-pinned (CLAUDE.md); no upgrade this phase |
| BraiAn extension | 1.1.0 (already installed, `BraiAn catalog`) | `ChannelHistogram` static histogram-peak-finding utilities reused for D-05 threshold re-derivation; `AtlasManager` for the optional `regions.tsv` reuse path | Already locked in Phase 2; SC4's discretion note explicitly allows reusing its output mechanism |
| ABBA extension | 0.4.0 (already installed, `QuPath-BIOP catalog`) | `AtlasTools.getAtlasToPixelTransform(imageData)` for the Atlas_X sanity check (SC3) | Already locked in Phase 1; same extension that loaded the atlas ROIs |
| imglib2-realtransform | 3.1.2 (bundled transitive dependency of the ABBA/Warpy extensions, `required-dependencies/`) | `net.imglib2.realtransform.InvertibleRealTransform`/`RealPoint` — the concrete transform type returned by `getAtlasToPixelTransform` | Already present on the QuPath extension classpath; no separate install |

**No new libraries are installed this phase.** Every capability needed (annulus geometry, arbitrary-ROI intensity sampling, spatial neighbor queries, histogram peak-finding, coordinate transforms) is already available in the currently-installed QuPath 0.6.0 + BraiAn 1.1.0 + ABBA 0.4.0 toolchain.

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Gson (`com.google.gson`) | bundled with QuPath (used already in `classify_markers.groovy`, `qc_detection_gates.groovy`) | Parse classifier JSON (`JsonParser.parseString(...).getAsJsonObject()`) | Continue the exact pattern already established — QuPath's Groovy does not ship `groovy.json` |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `RoiTools.buffer`/`RoiTools.subtract` for annulus construction | Hand-written JTS `Geometry.buffer()`/`.difference()` via `ROI.getGeometry()` + `GeometryTools.geometryToROI(...)` | Equivalent result, more boilerplate; `RoiTools` already wraps this correctly and is the documented public API — no reason to drop to raw JTS |
| `ObjectMeasurements.addIntensityMeasurements(..., Compartments.CELL)` on a throwaway detection object | Manually `ImageServer.readRegion(...)` + iterate pixels inside the annulus polygon | Manual pixel iteration would have to reimplement bit-depth handling, downsample scaling, and polygon rasterization that `ObjectMeasurements` already does — classic "don't hand-roll" case (see below) |
| Reusing `qupath.ext.braian.ChannelHistogram.findPeaks`/`zeroPhaseFilter` (public static) for D-05 | Writing a fresh peak-finder for the new measurement's histogram | `ChannelHistogram`'s peak-finding is the *exact* mechanism that produced the locked `nPeak`/`peakProminence` detection threshold in `BraiAn.yml` — reusing it keeps D-05 continuous with D-01/D-02's philosophy instead of introducing a second, subtly different algorithm |
| `AtlasTools.getAtlasToPixelTransform(imageData).inverse()` for Atlas_X | Re-deriving the ABBA affine+spline transform from `ABBA-Transform-*.json` by hand | ABBA already exposes the composed, invertible transform through its public API; hand-parsing the transform JSON would duplicate ABBA's own (non-trivial) Affine3D+ThinplateSpline composition logic |

**Installation:** None — no `npm install`/`pip install`/`conda install` needed. All classes above are already present under `$HOME/section-pipeline/tools/QuPath/`.

**Version verification:** Confirmed directly by extracting and inspecting the installed jars this session (not `npm view`/`pip index` — this is a JVM/Groovy scripting phase with no package-manager-installed dependency):
```bash
# QuPath core (already pinned 0.6.0)
ls $HOME/section-pipeline/tools/QuPath/lib/app/qupath-core-0.6.0.jar
# BraiAn extension (already locked v1.1.0 in Phase 2)
find $HOME/section-pipeline/tools/QuPath/extensions -iname "qupath-extension-braian*.jar"
# ABBA extension (already locked v0.4.0 in Phase 1)
find $HOME/section-pipeline/tools/QuPath/extensions -iname "qupath-extension-abba*.jar"
```

## Package Legitimacy Audit

**Not applicable this phase.** No new external packages, npm/pip/cargo dependencies, or third-party libraries are installed. All APIs used (`RoiTools`, `ObjectMeasurements`, `PathObjectHierarchy`, `ChannelHistogram`, `AtlasTools`, imglib2-realtransform) come from software already installed and locked in Phase 1 (ABBA) and Phase 2 (BraiAn, QuPath itself). The Package Legitimacy Gate protocol is skipped.

## Architecture Patterns

### System Architecture Diagram

```text
 [existing state: run_braian_detection.groovy already ran]
     data.qpdata: DAPI-T4 detections with
       "Nucleus: AF488-T3 mean", "Cytoplasm: AF568-T2 mean", "Nucleus: Area µm^2"
       ABBA region annotations (CA1, CA2, CA3, DG-mo/DG-po/DG-sg, VS, SSp, ... )
                       │
                       ▼
     ┌─────────────────────────────────────────────────────────────┐
     │  02_detect_classify.groovy  ("Run for project" entry point)  │
     │                                                               │
     │  Step 0  Guard: getDetectionObjects().isEmpty() → abort (D-02)│
     │                                                               │
     │  Step 1  BACKGROUND-ROBUST MEASURE (D-04, Pattern 1)          │
     │     for each detection d:                                    │
     │       build annulus ROI outside d's own marker compartment    │
     │       (Nucleus ROI for Fos, expanded Cell/Cytoplasm ROI       │
     │        for TdT) via RoiTools.buffer                          │
     │       subtract neighboring detections' ROIs                  │
     │       (hierarchy.getAllObjectsForRegion → RoiTools.subtract)  │
     │       sample local background mean via a throwaway            │
     │       PathObjects.createDetectionObject(annulusRoi) +         │
     │       ObjectMeasurements.addIntensityMeasurements(..CELL..)   │
     │       write new measurement:                                  │
     │         "Nucleus: AF488-T3 mean (bg-sub)" = raw - localBg     │
     │         "Cytoplasm: AF568-T2 mean (bg-sub)" = raw - localBg   │
     │                                                               │
     │  Step 2  THRESHOLD RE-DERIVATION (D-05, Pattern 2)             │
     │     collect bg-sub measurement values (excluding DG-sg/VS)    │
     │     bin into a histogram array                                │
     │     ChannelHistogram.zeroPhaseFilter + findPeaks(bins, prom)  │
     │     pick nPeak-th peak → new Fos/TdT thresholds                │
     │                                                               │
     │  Step 3  COMPOUND CLASSIFICATION (extends classify_markers.groovy)│
     │     isF = bg-sub Fos measure >= new Fos threshold              │
     │     isT = bg-sub TdT measure >= new TdT threshold              │
     │     setPathClass(Double+ / Fos+ / TdT+ / Negative / Excluded) │
     │                                                               │
     │  Step 4  ATLAS LABEL (SC2, Pattern 3)                          │
     │     centroid-in-ROI containment test against ABBA leaf         │
     │     region annotations (same idiom as qc_detection_gates.groovy)│
     │                                                               │
     │  Step 5  COUNT ROLLUP (SC4, Pattern 4)                         │
     │     for each region annotation (CA1/CA2/CA3/DG at minimum):    │
     │       count classified cells inside by class                  │
     │       ann.getMeasurementList().put("Count: <class>", n)        │
     │     println console table (complement)                        │
     │                                                               │
     │  Step 6  ATLAS_X SANITY PRINT (SC3, Pattern 5)                 │
     │     sample N classified cells                                  │
     │     AtlasTools.getAtlasToPixelTransform(imageData).inverse()   │
     │       .apply(point, point)  → println Atlas_X (expect 5-10k µm)│
     │                                                               │
     │  fireHierarchyUpdate() ; QuPath auto-persists to data.qpdata   │
     └─────────────────────────────────────────────────────────────┘
                       │
                       ▼
   data.qpdata: classified cells (4 classes + Excluded) + atlas-labeled
   region annotations carrying "Count: <class>" measurements
   (visible in QuPath's annotation-pane measurement table)
```

### Recommended Project Structure

No new files/folders beyond what Phase 1/2 already established:
```
scripts/
├── 01_load_abba_rois.groovy       # Phase 1 — unchanged
├── run_braian_detection.groovy    # Phase 2 — unchanged (D-01: detection stays separate)
├── 02_detect_classify.groovy      # THIS PHASE — new, extends classify_markers.groovy
├── classify_markers.groovy        # Phase 2/3 base — superseded by 02_detect_classify.groovy,
│                                   #   keep as reference/fallback or fold into it (planner's call)
└── qc_detection_gates.groovy      # Phase 2 — unchanged, still useful for D-05-style QC
```
`02_detect_classify.groovy` is hard-copied into `<QuPath project>/scripts/` for "Run for project", per the established D-10/D-11 dual-location deploy pattern.

### Pattern 1: Compartment-Agnostic Local-Background Subtraction (D-04, the crux)

**What:** For every detection, build an annulus ROI immediately outside the marker's own compartment boundary, exclude neighboring detections' geometry from that annulus, measure the mean pixel intensity of the *same channel* inside the cleaned annulus, and subtract it from the raw compartment measurement.

**When to use:** Every classified cell, for both the Fos (nuclear) and TdT (cytoplasmic) measures — this is the D-04-mandated replacement for the raw `Nucleus: AF488-T3 mean` / `Cytoplasm: AF568-T2 mean` values the classifiers currently read.

**Why compartment-agnostic (not nucleus:cytoplasm ratio):** the ring is always built *outside* whatever ROI is being measured — nucleus ROI for Fos, expanded cell/cytoplasm ROI for TdT. A future PNN channel would anchor its own ring outside a pericellular annulus compartment using the identical mechanism. No redesign needed when PNN is added later (per CONTEXT.md's explicit forward-scaling rationale).

**Example (verified against QuPath 0.6.0 installed javadoc: `RoiTools`, `ObjectMeasurements`, `PathObjectHierarchy`, `PathObjects`, `MeasurementList`):**
```groovy
// Source: qupath-core-0.6.0 + qupath-core-processing-0.6.0 javadoc, verified against
// the installed jars at $HOME/section-pipeline/tools/QuPath/lib/app/
import qupath.lib.roi.RoiTools
import qupath.lib.objects.PathObjects
import qupath.lib.analysis.features.ObjectMeasurements
import qupath.lib.analysis.features.ObjectMeasurements.Measurements
import qupath.lib.analysis.features.ObjectMeasurements.Compartments
import qupath.lib.regions.ImageRegion

def imageData = getCurrentImageData()
def server = imageData.getServer()
def hierarchy = imageData.getHierarchy()
def cal = server.getPixelCalibration()
def pixelUm = cal.hasPixelSizeMicrons() ? cal.getAveragedPixelSizeMicrons() : 0.6905355

// ring geometry -- [ASSUMED] starting seed, tune visually on DG like Phase 2's
// cellExpansionMicrons (D-04 there); ring must not eat into the cell's own compartment
double GAP_UM = 1.0          // small gap so the ring doesn't touch the compartment edge
double RING_WIDTH_UM = 8.0   // ring thickness, tune per D-04-style DG bleed-check
double gapPx = GAP_UM / pixelUm
double outerPx = (GAP_UM + RING_WIDTH_UM) / pixelUm

/** Returns the local-background-subtracted mean for a channel around a base ROI. */
double localBackgroundSubtractedMean(def baseRoi, String channelName, def selfDetection) {
    def innerRoi = RoiTools.buffer(baseRoi, gapPx)
    def outerRoi = RoiTools.buffer(baseRoi, outerPx)
    def annulusRoi = RoiTools.subtract(outerRoi, innerRoi)

    // fast bbox candidate query (documented as "quick check" -- intentionally
    // over-inclusive, exact geometric subtract below narrows it), NOT the
    // centroid-only getAllObjectsForROI (would miss neighbors whose centroid
    // sits outside the ring but whose body intrudes into it)
    def region = ImageRegion.createInstance(annulusRoi)
    def neighborRois = hierarchy.getAllObjectsForRegion(region)
            .findAll { it.isDetection() && it != selfDetection }
            .collect { it.getROI() }
            .findAll { it != null }
    def cleanAnnulus = neighborRois.isEmpty() ? annulusRoi : RoiTools.subtract(annulusRoi, neighborRois)

    // throwaway detection object purely as a measurement container -- never
    // added to the hierarchy, discarded after reading the value back off it
    def tempObj = PathObjects.createDetectionObject(cleanAnnulus)
    ObjectMeasurements.addIntensityMeasurements(server, tempObj, 1.0,
            [Measurements.MEAN], [Compartments.CELL])
    // naming convention confirmed empirically: existing classifier JSONs already
    // show "Nucleus: AF488-T3 mean" / "Cytoplasm: AF568-T2 mean" produced by this
    // same class -- Compartments.CELL on a plain (non-cell) object should yield
    // "Cell: <channelName> mean". VERIFY on the first cell processed (println
    // tempObj.getMeasurements().keySet()) before trusting the key in a loop.
    def key = "Cell: ${channelName} mean"
    def v = tempObj.getMeasurements().get(key)
    return (v == null || Double.isNaN(v.doubleValue())) ? Double.NaN : v.doubleValue()
}

def dets = getDetectionObjects()
dets.each { d ->
    def nucleusRoi = d.hasProperty('getNucleusROI') ? d.getNucleusROI() : d.getROI()
    def cellRoi = d.getROI()   // outer boundary = expanded Cytoplasm compartment for TdT

    double rawFos = d.getMeasurements().get("Nucleus: AF488-T3 mean")?.doubleValue() ?: Double.NaN
    double bgFos = localBackgroundSubtractedMean(nucleusRoi, "AF488-T3", d)
    double rawTdt = d.getMeasurements().get("Cytoplasm: AF568-T2 mean")?.doubleValue() ?: Double.NaN
    double bgTdt = localBackgroundSubtractedMean(cellRoi, "AF568-T2", d)

    d.getMeasurementList().put("Nucleus: AF488-T3 mean (bg-sub)", rawFos - bgFos)
    d.getMeasurementList().put("Cytoplasm: AF568-T2 mean (bg-sub)", rawTdt - bgTdt)
}
fireHierarchyUpdate()
```

### Pattern 2: Threshold Re-Derivation on the Background-Subtracted Measure (D-05)

**What:** Reuse the same histogram-peak-finding logic already locked in `BraiAn.yml`'s `histogramThreshold` block (D-01), applied to the *new* per-cell measurement instead of the raw DAPI image channel histogram it was originally designed for.

**When to use:** Once per classifier (Fos, TdT), after Pattern 1 has written the bg-sub measurements to every detection.

**Key finding:** `qupath.ext.braian.ChannelHistogram` (already installed, `qupath-extension-braian-1.1.0.jar`) has `public static int[] findPeaks(double[], double)` and `public static double[] zeroPhaseFilter(double[], double[])` — both `public static`, verified via `javap` against the installed jar. These operate on a plain `double[]` bin-count array and have no dependency on `ImageProcessor`/`ImageStatistics` (the instance constructors are the only part tied to raw image data) — they can be fed a self-built histogram of *any* numeric distribution, including our per-cell measurement.

**Example:**
```groovy
// Source: verified via javap against the installed qupath-extension-braian-1.1.0.jar
// at $HOME/section-pipeline/tools/QuPath/extensions/catalogs/BraiAn catalog/...
import qupath.ext.braian.ChannelHistogram

// exclude DG-sg/VS from the derivation population, mirroring D-02's original scope
def classifiable = dets.findAll { it.getPathClass()?.toString() != "Excluded" }
def values = classifiable.collect { it.getMeasurements().get("Nucleus: AF488-T3 mean (bg-sub)")?.doubleValue() }
                          .findAll { it != null && !Double.isNaN(it) }

double binWidth = 50.0   // tune; matches the AREA_BIN_WIDTH_UM2=10.0 style already used
                          // in qc_detection_gates.groovy for a different measurement
def minV = values.min(), maxV = values.max()
int nBins = Math.ceil((maxV - minV) / binWidth) as int
double[] hist = new double[nBins + 1]
values.each { v -> hist[((int) ((v - minV) / binWidth))]++ }

double peakProminence = 500   // same D-01 seed value already locked in BraiAn.yml
def smoothed = ChannelHistogram.zeroPhaseFilter(hist, [1,2,3,2,1] as double[]) // example smoothing kernel; tune window size per BraiAn.yml smoothWindowSize:15
int[] peakIndices = ChannelHistogram.findPeaks(smoothed, peakProminence)
int nPeak = 2   // same locked semantic as BraiAn.yml's nPeak: 2 (skip background peak)
double newFosThreshold = minV + peakIndices[Math.min(nPeak - 1, peakIndices.length - 1)] * binWidth
println "Re-derived Fos threshold (bg-sub measure): ${newFosThreshold}"
```
**Note:** the exact smoothing-kernel argument shape for `zeroPhaseFilter` was not fully inspected via javadoc (BraiAn ships no javadoc jar, only bytecode) — verify the kernel/window semantics against `BraiAn.yml`'s `smoothWindowSize`/`peakProminence` fields by comparing a re-derivation of the *existing* raw-measure threshold (should approximately match `13000.4538`) before trusting the new bg-sub-measure threshold. This is a good self-check to include as a plan verification step.

### Pattern 3: Atlas-Region Label Per Cell (SC2)

**What:** Determine which ABBA leaf-region annotation each classified cell's centroid falls inside.

**Recommended (HIGH confidence, already proven in this codebase):** reuse the exact centroid-in-ROI idiom already working in `qc_detection_gates.groovy` and `classify_markers.groovy`'s exclusion-region logic — do **not** store a per-cell String label via `PathObject.storeMetadataValue`/`getMetadata()`. The QuPath 0.6.0 javadoc explicitly warns against this at detection-object scale: *"for objects that could be plentiful (e.g. detections) it is likely to be unwise to store any metadata values, since these can't be stored particularly efficiently"* (`PathObject.storeMetadataValue`, deprecated in 0.6.0 anyway — replaced by `getMetadata()`, same caveat applies). `MeasurementList` is numeric-only by design (*"only String keys and numeric values are included"*, `MeasurementList` javadoc) — a region acronym cannot go there either.

```groovy
// Source: same containment idiom already used in qc_detection_gates.groovy (Phase 2)
def regionAnnotations = getAnnotationObjects().findAll { ann ->
    def roi = ann.getROI()
    roi != null && !ann.getChildObjects().any { it.isAnnotation() }   // leaf regions only
}
def regionOf = { detection ->
    def r = detection.getROI()
    def x = r.getCentroidX(), y = r.getCentroidY()
    regionAnnotations.find { it.getROI().contains(x, y) }
}
// SC2 satisfaction: print a small sample proving the association exists
dets.take(5).each { d ->
    def region = regionOf(d)
    def label = region?.getPathClass()?.toString() ?: region?.getName() ?: "(no region)"
    println "Cell at (${d.getROI().getCentroidX()},${d.getROI().getCentroidY()}) -> ${label}"
}
```

**Secondary/unverified hypothesis worth a one-line check (MEDIUM confidence, derived from decompiled BraiAn method signatures, not javadoc):** `AbstractDetections.createContainer(PathAnnotationObject, boolean)` strongly suggests BraiAnDetect already nests each DAPI-T4 detection as a *grandchild* of its containing ABBA region annotation (`detection.getParent()` = a BraiAn-created container, `detection.getParent().getParent()` = the actual region annotation). If confirmed, this means the "region label" already exists natively in the object hierarchy with zero extra code — a single `println d.getParent()?.getParent()?.getPathClass()` on a sample cell is enough to check this before deciding whether the count rollup (Pattern 4) needs the centroid-in-ROI computation at all or can just group by parent chain. **Do not depend on this for the actual implementation without confirming it live** — the centroid-in-ROI approach above works regardless of the answer and is the same mechanism `qc_detection_gates.groovy` already validated in Phase 2.

### Pattern 4: Per-Region Count Rollup to Annotation Measurements (SC4)

**What:** Write per-class counts as numeric measurements directly onto the CA1/CA2/CA3/DG (at minimum) region annotation objects, so they render in QuPath's built-in annotation-pane measurement table — no export file required for this to satisfy SC4.

```groovy
// Source: qupath-core-0.6.0 javadoc — MeasurementList.put(String, double); same
// mechanism already used to read measurements is reused here in reverse to write
def classes = ["Negative", "Fos+", "TdT+", "Double+", "Excluded"]
regionAnnotations.each { ann ->
    def roi = ann.getROI()
    def counts = classes.collectEntries { [(it): 0] }
    dets.each { d ->
        def r = d.getROI()
        if (roi.contains(r.getCentroidX(), r.getCentroidY())) {
            def cls = d.getPathClass()?.toString() ?: "Negative"
            counts[cls] = (counts[cls] ?: 0) + 1
        }
    }
    def ml = ann.getMeasurementList()
    counts.each { cls, n -> ml.put("Count: ${cls}", n as double) }
}
fireHierarchyUpdate()
```
**Complementary reuse of `regions.tsv` (per CONTEXT.md discretion) — with a caveat:** `run_braian_detection.groovy`'s `AtlasManager.saveResults(allDetections + overlaps, resultsFile)` call happens *before* `02_detect_classify.groovy` runs and reflects BraiAnDetect's own (Deviation #1: incompatible) classifier application, not the final Double+/Fos+/TdT+/Negative ground truth this phase produces. **Do not treat the existing `results/<image>_regions.tsv` on disk as authoritative for SC4** — see Common Pitfall 1.

### Pattern 5: Atlas_X Micron Sanity Print (SC3)

**What:** Confirm the ABBA-registered CCFv3 coordinate for a small sample of classified cells falls in the 5,000–10,000 µm range (proves µm units, not mm/voxel-index), without building the full per-cell export column (that's v2 `EXP-01`).

**Source of the exact pattern:** an official BIOP-author (NicoKiaru, ABBA/AtlasTools' own developer) example gist, cross-checked against the installed `qupath-extension-abba-0.4.0.jar`'s bytecode signature for `AtlasTools.getAtlasToPixelTransform` and the bundled `imglib2-realtransform-3.1.2.jar`'s `InvertibleRealTransform` interface (`.inverse()`, `.apply(RealLocalizable, RealPositionable)`).

```groovy
// Source: gist.github.com/NicoKiaru (BIOP developer, ABBA extension author),
// cross-verified against installed qupath-extension-abba-0.4.0.jar (javap) and
// imglib2-realtransform-3.1.2.jar (bundled ABBA/Warpy dependency)
import qupath.ext.biop.abba.AtlasTools
import net.imglib2.RealPoint

def pixelToAtlasTransform = AtlasTools.getAtlasToPixelTransform(imageData).inverse()

def sample = dets.findAll { it.getPathClass()?.toString() in ["Fos+", "TdT+", "Double+"] }.take(5)
sample.each { d ->
    def point = new RealPoint(3)
    point.setPosition([d.getROI().getCentroidX(), d.getROI().getCentroidY(), 0d] as double[])
    pixelToAtlasTransform.apply(point, point)   // in-place: same RealPoint as source and target
    println "Atlas_X=${point.getDoublePosition(0)}  Atlas_Y=${point.getDoublePosition(1)}  Atlas_Z=${point.getDoublePosition(2)}  (expect Atlas_X in [5000, 10000] µm per SC3)"
}
```
**If the printed values land near 500–1000 instead of 5,000–10,000:** the transform is likely outputting atlas *voxel index* rather than µm — multiply by 10 (the `allen_mouse_10um_java` atlas is 10 µm/voxel) as a fallback and re-check. This exact ambiguity is why SC3 is designed as an empirical print-and-check gate rather than a hard-coded assumption — treat the acceptance criterion itself as the verification step for this open question.

### Anti-Patterns to Avoid

- **Nucleus:cytoplasm contrast ratio for background robustness:** explicitly rejected by D-04. Do not implement this even as a fallback — it doesn't generalize to the future PNN pericellular compartment.
- **Reusing `BraiAn.yml`'s `classifiers:`/`OverlappingDetections` for compound classification:** confirmed incompatible with this project's nucleus-anchored topology in Phase 2 (Deviation #1). Classification stays in Groovy script logic (`classify_markers.groovy` → `02_detect_classify.groovy`), not BraiAn.yml config.
- **Per-cell String metadata for atlas region labels:** `PathObject.storeMetadataValue`/`getMetadata()` explicitly documented as memory-inefficient at detection-object scale (10^4–10^5 objects in this dataset). Use centroid-in-ROI computation (ephemeral, no storage) instead.
- **Treating the pre-existing `results/<image>_regions.tsv` as ground truth for SC4** without regenerating it after this phase's classification — see Common Pitfall 1.
- **All-pairs O(n²) neighbor search for annulus cleaning:** use `PathObjectHierarchy.getAllObjectsForRegion` (spatially indexed, "quick check" per its own javadoc) to get candidates, then exact `RoiTools.subtract`, not a manual loop over all detections.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Peri-cellular annulus geometry | Custom polygon offset/buffer math | `qupath.lib.roi.RoiTools.buffer(roi, distancePx)` + `RoiTools.subtract(outer, [inner, ...neighbors])` | JTS-backed, handles self-intersecting/complex ROI shapes correctly; already the QuPath-documented way to dilate/erode an ROI |
| Mean pixel intensity inside an arbitrary ROI | Manual `ImageServer.readRegion(...)` + pixel-by-pixel masking loop | `qupath.lib.analysis.features.ObjectMeasurements.addIntensityMeasurements(server, tempObj, downsample, [MEAN], [Compartments.CELL])` on a throwaway `PathObjects.createDetectionObject(roi)` | This is the exact class QuPath's own built-in cell detection uses to produce the existing "Nucleus: AF488-T3 mean"/"Cytoplasm: AF568-T2 mean" measurements — correctly handles bit depth, downsample, and polygon rasterization |
| Efficient "which detections are near this ROI" lookup | Iterate all detections and test geometric intersection one by one | `PathObjectHierarchy.getAllObjectsForRegion(ImageRegion)` (spatially indexed, non-deprecated in 0.6.0; its own javadoc calls it a "quick check" meant to be followed by exact filtering) | O(log n)-ish spatial query vs. O(n) per annulus, critical at this dataset's scale (tens of thousands of detections) |
| Histogram-relative peak-finding for the new threshold | A new peak-detection algorithm | `qupath.ext.braian.ChannelHistogram.findPeaks`/`zeroPhaseFilter` (`public static`, verified via `javap`) | Reuses the *exact* algorithm already locked into `BraiAn.yml`'s D-01 detection threshold, keeping D-05 philosophically and numerically consistent with Phase 2 rather than introducing a second, subtly different peak-finder |
| Pixel↔atlas coordinate transform | Re-implement Affine3D+ThinplateSpline composition from `ABBA-Transform-*.json` | `qupath.ext.biop.abba.AtlasTools.getAtlasToPixelTransform(imageData).inverse()` | ABBA already exposes the fully-composed, invertible transform; hand-parsing the transform JSON duplicates non-trivial registration math for no benefit |

**Key insight:** every "novel" mechanic this phase needs (annulus, arbitrary-ROI pixel sampling, spatial neighbor query, histogram peak-finding, coordinate transform) already exists as a documented, public method inside software already installed and locked in this project. The work is *composition* of existing primitives (verified by reading the installed jars directly, following the same "verified from installed JAR bytecode" method this project already established in Phase 1/2), not new algorithm design.

## Common Pitfalls

### Pitfall 1: Stale `regions.tsv` from `run_braian_detection.groovy`
**What goes wrong:** Trusting the `results/<image>_regions.tsv` file already on disk (written by `run_braian_detection.groovy`'s `AtlasManager.saveResults(...)` call) as the SC4 count table.
**Why it happens:** That file was written using BraiAnDetect's own classifier application (the same mechanism Deviation #1 confirmed is incompatible with this project's nucleus-anchored topology) — it predates and does not reflect `02_detect_classify.groovy`'s Double+/Fos+/TdT+/Negative ground truth.
**How to avoid:** Treat the annotation-measurement rollup (Pattern 4) as the authoritative SC4 mechanism. If a fresh `regions.tsv` is also wanted, it requires reconstructing `ChannelDetections` wrapper objects fresh inside `02_detect_classify.groovy` (the ones built in `run_braian_detection.groovy`'s script scope are not accessible from a separately-run script) — treat this as optional, not required for SC4.
**Warning signs:** `regions.tsv` counts don't match the console-printed class breakdown from `02_detect_classify.groovy`.

### Pitfall 2: Buffer distance is in pixels, not microns
**What goes wrong:** Passing a micron value directly to `RoiTools.buffer(roi, distance)`.
**Why it happens:** `distance` is documented as "in pixels" — every other µm-denominated parameter in this codebase (`cellExpansionMicrons`, `AREA_BIN_WIDTH_UM2`, etc.) is converted before use.
**How to avoid:** Always divide by `pixelSizeUm` (read from `server.getPixelCalibration()`, matching the existing `qc_detection_gates.groovy`/`export_region_dapi_reference.groovy` pattern) before calling `buffer`.
**Warning signs:** Annulus rings that are visually far larger or smaller than intended when overlaid in QuPath.

### Pitfall 3: Wrong base ROI for the annulus per marker
**What goes wrong:** Anchoring both Fos and TdT annulus rings to the same base ROI (e.g., always the nucleus).
**Why it happens:** Easy to copy-paste one ring-building call for both markers.
**How to avoid:** Fos's ring must be built outside the **nucleus** ROI (Fos is nuclear); TdT's ring must be built outside the **expanded cell/cytoplasm** ROI (TdT is cytoplasmic) — this is what "compartment-agnostic" in D-04 actually means: the mechanism is shared, the anchor ROI is per-compartment.
**Warning signs:** TdT background-subtracted values come out systematically too high or negative (ring partially overlapping the cell's own cytoplasmic signal because it was built from the smaller nucleus ROI instead of the outer cell boundary).

### Pitfall 4: Per-cell metadata String storage at scale
**What goes wrong:** Using `PathObject.getMetadata().put("Region", acronym)` (or the deprecated `storeMetadataValue`) on every one of tens of thousands of detections to record the atlas label.
**Why it happens:** Seems like the most direct way to "attach a label."
**How to avoid:** The QuPath 0.6.0 javadoc explicitly warns against this for plentiful objects (memory inefficiency). Use the ephemeral centroid-in-ROI computation (Pattern 3) instead — no storage needed.
**Warning signs:** Noticeably increased QuPath memory usage or slower `data.qpdata` save after adding per-cell metadata at this dataset's scale.

### Pitfall 5: `MeasurementList` is numeric-only
**What goes wrong:** Trying to `put()` a region acronym (a String) into a detection's or annotation's `MeasurementList`.
**Why it happens:** `MeasurementList.put(String name, double value)` looks like a generic key-value store but the *value* must be numeric — confirmed in the javadoc ("only String keys and numeric values are included").
**How to avoid:** Region labels are either structural (parent-chain, Pattern 3 hypothesis) or ephemeral (recomputed per script run via centroid-in-ROI); counts are numeric and belong in `MeasurementList` (Pattern 4).

### Pitfall 6: Deriving thresholds on the un-excluded population
**What goes wrong:** Feeding DG-sg's ultra-dense, unseparable nuclei (or VS's non-nuclei) into the D-05 histogram-peak-finding population.
**Why it happens:** Easy to forget the `EXCLUDE_ACRONYMS` filter when switching from classification (which already excludes them) to threshold derivation (a separate pass that needs the same filter applied).
**How to avoid:** Filter to `getPathClass()?.toString() != "Excluded"` (or equivalently, apply the same `excludeRois` containment test) before building the histogram in Pattern 2 — mirrors D-02's original derivation scope from Phase 2.
**Warning signs:** Re-derived threshold is drastically different from a sanity re-derivation of the *existing* raw-measure threshold (which should land close to the already-locked `13000.4538`/`16766.4671`).

### Pitfall 7: Performance at ~10⁴–10⁵ detections
**What goes wrong:** Pattern 1's per-cell annulus construction + `ObjectMeasurements.addIntensityMeasurements` pixel read, run over every detection in the atlas-root-confined section (density was measured at ~2,900–4,000/mm² over ~56 mm² in Phase 2 — tens of thousands of cells), could be slow on CPU-only hardware.
**Why it happens:** Each call does real pixel I/O (`ImageServer` region read), not a cached lookup.
**How to avoid:** Time a small subset first (e.g., one region's detections) before committing to a full-population run; this is the same order of cost QuPath itself already pays computing the existing Nucleus/Cytoplasm measurements during detection, so it should be feasible but budget real wall-clock time in the plan rather than assuming it's instant.
**Warning signs:** Script appears to hang with no progress output — add a periodic `println` (e.g., every 1,000 detections) so a stalled run is distinguishable from a slow-but-progressing one.

### Pitfall 8: Trusting `getAllObjectsForROI`'s centroid-only rule for neighbor exclusion
**What goes wrong:** Using `hierarchy.getAllObjectsForROI(annulusRoi)` to find neighbors to subtract from the annulus.
**Why it happens:** Looks like the natural "objects inside this ROI" query.
**How to avoid:** Per its own javadoc, `getAllObjectsForROI` uses centroid-containment for detections ("detections need only have their centroid within the ROI") — a neighbor whose centroid sits just outside the ring but whose body still intrudes into it would be missed. Use `getAllObjectsForRegion` (bounding-box "quick check", intentionally over-inclusive) for candidates, then exact-subtract with `RoiTools.subtract` using the candidates' real ROIs.
**Warning signs:** Visually, neighbor-cell bright pixels still visible inside a supposedly "cleaned" annulus overlay.

### Pitfall 9: Superseded absolute thresholds leaking back in
**What goes wrong:** Accidentally leaving the classification step reading `Fos_Classifier_20x.json`/`TdT_classifier.json`'s old absolute thresholds (13000.4538 / 16766.4671) against the *new* bg-sub measurement, instead of the newly re-derived D-05 thresholds.
**Why it happens:** `classify_markers.groovy`'s `readSpec` closure reads threshold from a JSON file at runtime — easy to forget to point it at new classifier JSON(s) (or new in-script constants) for the bg-sub measure.
**How to avoid:** Either write new classifier JSON(s) (e.g., `Fos_Classifier_bgsub.json`) with the re-derived threshold and the new measurement name, or make the threshold source explicit and clearly separate from the old files in the script. Keep the old JSONs as documented reference points only (per D-05).
**Warning signs:** Classification results identical to Phase 2's (SSp still >50% false-positive) despite Pattern 1/2 having run.

### Pitfall 10: Atlas coordinate axis/unit ambiguity
**What goes wrong:** Assuming `Atlas_X` (index 0 of the transformed point) is always the anteroposterior axis, or always already in µm.
**Why it happens:** CCFv3 axis-order conventions vary slightly across tools/pipelines (AP/DV/ML ordering is not universally fixed), and the ABBA transform's output units were not confirmed live in this research session (only cross-checked against a community-documented CCF coordinate-scaling formula and an official example gist that names the outputs "Atlas_X"/"Y"/"Z" without stating units explicitly).
**How to avoid:** This is exactly what SC3 is designed to catch — print and inspect the values against the 5,000–10,000 µm expectation before assuming correctness; if values look like voxel indices (~500–1000), multiply by 10 (10 µm/voxel atlas resolution) as a documented fallback.
**Warning signs:** Printed Atlas_X values far outside [0, 13200] µm (full CCFv3 AP extent) or suspiciously small (~500–1000, suggesting voxel index not µm).

## Code Examples

See Patterns 1–5 above for the full verified snippets (annulus + local background subtraction, threshold re-derivation via `ChannelHistogram`, atlas-region centroid lookup, count rollup via `MeasurementList.put`, and the official Atlas_X transform pattern). All were checked against the QuPath 0.6.0 installed javadoc/bytecode this session; none required a fresh install.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| Absolute per-marker thresholds (Fos ≥13000.4538, TdT ≥16766.4671 on raw compartment mean) | Histogram-relative thresholds on a local-background-subtracted measure | This phase (D-04/D-05), superseding Phase 2's D-02 absolute-cutoff locks | Removes the SSp autofluorescence false-positive failure mode (Phase 2 Deviation #2); series-ready without per-section re-tuning |
| `BraiAn.yml classifiers:` + `OverlappingDetections` for compound classification | Direct Groovy nucleus-anchored compound classification (`classify_markers.groovy` → `02_detect_classify.groovy`) | Phase 2 (Deviation #1) | Only viable path for this project's single-DAPI-anchored, no-proximity-heuristic topology; not a QuPath/BraiAn version change, a project-specific architectural decision |

**Deprecated/outdated:**
- `PathObjectHierarchy.getObjectsForRegion(Class, ImageRegion, Collection)` — deprecated in QuPath 0.6.0, replaced by `getAllObjectsForRegion`/`getAllObjectsForROI` family (used throughout this research).
- `PathObject.storeMetadataValue`/`retrieveMetadataValue` — deprecated in 0.6.0, replaced by `getMetadata()` (a direct `Map<String,String>`); still discouraged for plentiful detection objects regardless of which API form is used.
- `MeasurementList.getMeasurementNames()`/`removeMeasurements()` — deprecated in 0.6.0, replaced by `getNames()`/`removeAll(String...)`.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|----------------|
| A1 | `ChannelHistogram.findPeaks`/`zeroPhaseFilter` (public static, verified via `javap`) are safe and semantically correct to reuse on a self-built measurement histogram outside their original per-channel-image-histogram context | Pattern 2 | If the smoothing-kernel/window semantics don't transfer cleanly, D-05's re-derived threshold could be wrong; mitigated by the recommended self-check (re-derive the *existing* raw-measure threshold first and compare to the already-locked 13000.4538) |
| A2 | BraiAnDetect nests each detection two levels below its containing ABBA region annotation (`detection.getParent().getParent()` = region) | Pattern 3 (secondary/optional path) | Low risk — this is explicitly marked as a check-before-relying-on-it hypothesis; the primary recommended mechanism (centroid-in-ROI) does not depend on it |
| A3 | `AtlasTools.getAtlasToPixelTransform(imageData).inverse().apply(point, point)` produces coordinates already in µm (not voxel index) for the `allen_mouse_10um_java` atlas, with index 0 = an axis that plausibly falls in [5000,10000] µm for hippocampus | Pattern 5 | If wrong, the SC3 print would show an obviously out-of-range or oddly-scaled value — the phase's own acceptance criterion is designed to catch this, with a documented ×10 fallback |
| A4 | Ring geometry seed (1 µm gap, 8 µm ring width) is a reasonable starting point for the annulus | Pattern 1 | Needs empirical DG-bleed-style visual tuning, same as Phase 2's `cellExpansionMicrons`; wrong values could pull in neighbor signal (too thin/no gap) or sample too far into non-representative tissue (too wide) |
| A5 | `Compartments.CELL` measurement on a plain (non-`PathCellObject`) `PathObjects.createDetectionObject` correctly measures using the object's own ROI and produces a `"Cell: <channel> mean"` key | Pattern 1 | If the key naming differs, the lookup after `addIntensityMeasurements` would return `null`; mitigated by the recommended one-time `println tempObj.getMeasurements().keySet()` check before trusting the key in a loop |

## Open Questions

1. **Does the ChannelHistogram-based re-derivation reproduce something close to the already-locked absolute thresholds when run on the *raw* (pre-bg-subtraction) measurements?**
   - What we know: the peak-finding algorithm and its `nPeak`/`peakProminence` parameters are already locked and working for the raw DAPI detection threshold in `BraiAn.yml`.
   - What's unclear: whether the same algorithm, applied to a *classifier measurement* histogram (rather than a raw image intensity histogram), needs different smoothing/prominence tuning.
   - Recommendation: run the re-derivation on the *existing* raw measurements first as a sanity check (should land near 13000.4538/16766.4671) before trusting a re-derivation on the new bg-sub measurement.

2. **Does the region-nesting hypothesis in Pattern 3 (Assumption A2) hold, and if so, is it more efficient to use for the count rollup than centroid-in-ROI?**
   - What we know: `AbstractDetections.createContainer(PathAnnotationObject, boolean)` exists in the decompiled bytecode.
   - What's unclear: exact nesting depth and whether the container's own `PathClass` mirrors the region's.
   - Recommendation: one-line printout check at the start of `02_detect_classify.groovy`; not blocking since the centroid-in-ROI fallback is already proven.

3. **What is the real wall-clock cost of Pattern 1 across the full atlas-root-confined detection population?**
   - What we know: density was ~2,900–4,000 cells/mm² over ~56 mm² in Phase 2 (tens of thousands of detections).
   - What's unclear: per-cell cost of the annulus+pixel-read+temp-object pattern on this CPU-only machine.
   - Recommendation: time a single region (e.g., CA1) first; budget accordingly before running the full section.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| QuPath | All Groovy scripting this phase | ✓ | 0.6.0 (pinned, confirmed via installed jar) | — |
| BraiAn extension | `ChannelHistogram` reuse (Pattern 2), optional `regions.tsv` regen | ✓ | 1.1.0 (locked Phase 2) | — |
| ABBA extension | `AtlasTools.getAtlasToPixelTransform` (Pattern 5) | ✓ | 0.4.0 (locked Phase 1) | — |
| imglib2-realtransform | `InvertibleRealTransform`/`RealPoint` (Pattern 5) | ✓ | 3.1.2 (bundled ABBA/Warpy transitive dependency) | — |
| M3 detections + ABBA annotations in `data.qpdata` | All patterns (prerequisite state) | ✓ | Entry 1 of `M3 Hippocampus 20x 062926 3 plane` — populated per Phase 1/2 | D-02 guard aborts cleanly if absent |

**Missing dependencies with no fallback:** None — everything needed is already installed and locked from Phase 1/2.
**Missing dependencies with fallback:** None.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | None (no automated test suite for this GUI-driven scientific pipeline, consistent with Phase 1/2) — validation is measurement-based visual/numeric QC inside QuPath |
| Config file | none |
| Quick run command | Manual: in QuPath, "Run for project" (or single-entry run) `02_detect_classify.groovy` on entry 1, read console output |
| Full suite command | Same manual run; inspect annotation-pane measurement table for CA1/CA2/CA3/DG "Count: *" columns, and `data.qpdata` mtime update |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SCRI-03 / SC1 | `02_detect_classify.groovy` runs via "Run for project" without errors, writes `data.qpdata` with classified cells | manual-only (requires QuPath GUI) | N/A — human runs script, checks no red error in QuPath's log/console and `data.qpdata` mtime updates | ❌ Wave 0 — script doesn't exist yet |
| SCRI-03 / SC2 | All 4 classes (TdT+/Fos+/Double+/Negative) present, each cell carries an atlas region label | manual + console printout | N/A — human reads the `classify_markers.groovy`-style class-breakdown printout plus the Pattern-3 sample region-label printout | ❌ Wave 0 |
| SCRI-03 / SC3 | Printed Atlas_X values fall in [5000, 10000] µm | manual, numeric console check | N/A — human reads the Pattern-5 printout | ❌ Wave 0 |
| SCRI-03 / SC4 | Per-region count table for CA1/CA2/CA3/DG readable in QuPath annotation pane | manual (GUI) + console printout complement | N/A — human opens QuPath's Annotations tab/measurement table, confirms "Count: *" columns for the four subfields | ❌ Wave 0 |

### Sampling Rate

- **Per task commit (each script edit):** re-run `02_detect_classify.groovy` on entry 1 (D-02 makes this idempotent/safe), inspect console output
- **Per wave merge:** full run through all 4 success criteria on entry 1
- **Phase gate:** all 4 SC pass on the M3 entry before Phase 3 is considered done; Phase 4's biological-plausibility gates (VAL-01) are separate and out of scope here

### Wave 0 Gaps

- [ ] `02_detect_classify.groovy` itself — does not exist yet; this phase's entire deliverable
- [ ] No automated static check currently exists for "does the classifier measurement key match the new bg-sub name" (mirrors Phase 2's CLASS-01 static-file check pattern) — worth a cheap `python3 -c` / `jq`-style check if new classifier JSON files are authored for the re-derived thresholds

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | N/A — single-user local scientific pipeline, no auth surface |
| V3 Session Management | No | N/A |
| V4 Access Control | No | N/A — local filesystem, single user |
| V5 Input Validation | Yes (narrow) | Classifier JSON continues to be read via `com.google.gson.JsonParser.parseString(...).getAsJsonObject()` (already-established safe pattern from Phase 2 — produces a generic `JsonElement` tree, not deserialization into arbitrary Java types; no RCE surface, unlike an unsafely-configured YAML/object deserializer) |
| V6 Cryptography | No | N/A — no secrets, no crypto operations in this phase |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Path traversal via any new classifier JSON `name`/path field | Tampering | Continue resolving relative to the QuPath project's `classifiers/object_classifiers/` base directory (established Phase 2 pattern via `BraiAn.resolvePath`); not a concern since all such values are hand-authored locally, never sourced from untrusted input |
| Unbounded/uncapped in-memory throwaway `PathObject` creation in Pattern 1's per-cell loop | Denial of Service (resource exhaustion, local only) | Temp objects are never added to the hierarchy and are discarded immediately after reading a measurement back off them — no accumulation; still worth the Pitfall-7 timing check to catch pathological slowness before a full-population run |

## Sources

### Primary (HIGH confidence — verified against installed software this session)
- `qupath-core-0.6.0.jar` + its bundled javadoc jar (`$HOME/section-pipeline/tools/QuPath/lib/app/`) — `PathObject`, `PathCellObject`, `PathObjects`, `MeasurementList`, `RoiTools`, `PathObjectHierarchy`, `ImageRegion` classes extracted and read directly.
- `qupath-core-processing-0.6.0.jar` + bundled javadoc jar — `ObjectMeasurements`, `ObjectMeasurements.Compartments`, `ObjectMeasurements.Measurements`.
- `qupath-extension-braian-1.1.0.jar` (`BraiAn catalog`) — decompiled class signatures via `javap` (using the JDK bundled inside Fiji.app) for `ChannelHistogram`, `AtlasManager`, `AbstractDetections`, `ChannelDetections`, `SingleClassifier`, `PartialClassifier`, `utils.BraiAn`.
- `qupath-extension-abba-0.4.0.jar` (`QuPath-BIOP catalog`) — decompiled `AtlasTools` class signature, confirming `getAtlasToPixelTransform(ImageData)` and `getAtlasToPixelTransform(ImageData, String)`.
- `imglib2-realtransform-3.1.2.jar` (bundled ABBA/Warpy transitive dependency) — decompiled `RealTransform`/`InvertibleRealTransform` interface signatures.
- Existing project files read directly: `scripts/classify_markers.groovy`, `scripts/run_braian_detection.groovy`, `scripts/qc_detection_gates.groovy`, `scripts/01_load_abba_rois.groovy`, `scripts/export_region_dapi_reference.groovy`, `M3 Hippocampus 20x 062926 3 plane/BraiAn.yml`, both classifier JSONs, `data/1/server.json`.

### Secondary (MEDIUM confidence)
- [gist.github.com/NicoKiaru — "Performs cell detection in QuPath from an ABBA registered project with imported regions"](https://gist.github.com/NicoKiaru/f45f56e3ff2d1fb708821c110fbdee62) — official BIOP-developer example confirming the `AtlasTools.getAtlasToPixelTransform(...).inverse().apply(point, point)` pattern and the "Atlas_X"/"Atlas_Y"/"Atlas_Z" naming convention.
- Allen CCFv3 axis-scaling formula (AP/DV/ML → µm) found via WebSearch, cross-referencing [Allen Mouse CCFv3 primer](https://alleninstitute.github.io/CCF-MAP/descriptions/mouse_ccf.html) and related community sources — used only as grounding context for interpreting SC3's printed values, not as a locked/operative conversion.

### Tertiary (LOW confidence)
- WebSearch on "QuPath local background subtraction peri-cellular annulus" — confirmed this is a known, unsolved community pain point (image.sc forum threads exist) with no ready-made script; did not surface a directly reusable implementation, reinforcing that Pattern 1 must be hand-composed from the primary-source APIs above.
- TRAP2-paper-specific background-subtraction methodology — not found (paper source previously returned HTTP 403 per Phase 2's `STATE.md`); not load-bearing since D-04's design is user-locked, not literature-derived.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new libraries; every class/method verified against installed jars this session
- Architecture (background-subtraction mechanism, count rollup, coordinate transform): HIGH for the API mechanics (installed-jar-verified), MEDIUM for a few semantic details (histogram-kernel exact shape, container-nesting depth, coordinate axis/unit) explicitly flagged in the Assumptions Log and designed to be caught by the phase's own success criteria
- Pitfalls: HIGH — sourced from explicit javadoc warnings (metadata memory cost, numeric-only MeasurementList, deprecated APIs) and direct reasoning about this project's already-documented Deviation #1/#2 (Phase 2 lock record)

**Research date:** 2026-07-09
**Valid until:** No expiry risk from external drift (all sources are locally-installed, version-pinned software); revisit only if QuPath/BraiAn/ABBA versions are ever bumped (currently forbidden by CLAUDE.md without explicit flag)
