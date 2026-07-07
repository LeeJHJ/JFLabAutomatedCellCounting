# Architecture Patterns: QuPath Batch Detection for TRAP2 Series

**Domain:** Fluorescence microscopy cell detection and atlas registration (TRAP2 vibratome sections)
**Researched:** 2026-06-30
**Confidence:** MEDIUM (cross-checked web sources; no proprietary access to BraiAnDetect source)

---

## Recommended Architecture

### Single-Project-Per-Animal Layout

Use **one QuPath project per animal** (e.g., `M3_hippocampus/`), with every section from that animal as a separate project entry. Do not create per-section projects.

Rationale: QuPath's batch execution machinery ("Run for project") is project-scoped. Classifiers, scripts, and the BraiAn.yaml configuration file all live at the project root and apply uniformly to every entry. Splitting sections into individual projects defeats the batch mechanism and forces manual parameter re-entry per section.

```
M3_hippocampus/                         ← QuPath project root
├── project.qpproj                      ← Entry manifest (JSON); lists all sections
├── BraiAn.yaml                         ← Locked detection parameters (BraiAnDetect reads this)
├── data/
│   ├── 1/                              ← Section 1 entry
│   │   ├── server.json                 ← Image URI + BioFormats metadata
│   │   ├── data.qpdata                 ← PathObjects (nuclei, annotations, classifiers)
│   │   ├── summary.json                ← Per-region counts (audit checkpoint)
│   │   ├── ABBA-Transform-allen_mouse_10um_java.json
│   │   └── ABBA-RoiSet-allen_mouse_10um_java.zip
│   ├── 2/                              ← Section 2 entry (same structure)
│   └── ...
├── classifiers/
│   └── object_classifiers/
│       ├── TdT_classifier.json         ← Threshold on cytoplasmic TdTomato mean
│       └── Fos_classifier.json         ← Threshold on nuclear Fos mean
└── scripts/
    ├── 01_load_abba_rois.groovy        ← Run first; loads atlas annotations per entry
    ├── 02_detect_classify.groovy       ← Reads BraiAn.yaml; runs detection + classification
    └── 03_export_cells.groovy          ← MeasurementExporter; outputs micron-coordinate TSV
```

---

## Component Boundaries

| Component | Mode | Responsibility | Inputs | Outputs |
|-----------|------|----------------|--------|---------|
| ABBA (Fiji) | **GUI only** | Register each section to Allen CCFv3; export transform + ROI files | MIP OME-TIFF in QuPath project | `ABBA-Transform-*.json` + `ABBA-RoiSet-*.zip` per entry |
| `01_load_abba_rois.groovy` | **Scriptable** (Run for project) | Load warped atlas annotations from ABBA files into QuPath entry hierarchy | ABBA-RoiSet-*.zip per entry | Atlas-region annotation PathObjects in data.qpdata |
| BraiAn.yaml | **Artifact** (parameter lock) | Stores all tuned detection parameters outside script code | Human-edited after tuning | Consumed by `02_detect_classify.groovy` |
| `02_detect_classify.groovy` | **Scriptable** (Run for project) | Run WatershedCellDetection on DAPI; expand to cytoplasm; apply TdT+/Fos+ classifiers | BraiAn.yaml; atlas annotations already loaded | Cell PathObjects in data.qpdata; summary.json |
| `03_export_cells.groovy` | **Scriptable** (Run for project without save) | Export all detected cell measurements to TSV in micron coordinates | data.qpdata for all entries | `cells_all_sections.tsv` (centroid X/Y in µm, class, atlas region) |
| Object classifiers (*.json) | **Artifact** (portable) | Single-threshold rules for TdT+/Fos+/Double+ | Stored at project root | Applied per cell during step 02 |

---

## Build Order and Dependencies

The order is strict. Each step depends on all prior steps completing for all sections before the next step begins.

```
[ABBA Fiji GUI — all sections]
        │
        │  Prerequisite: ABBA-Transform-*.json + ABBA-RoiSet-*.zip
        │  present in every entry directory before QuPath scripts run.
        ▼
[01_load_abba_rois.groovy — Run for project]
        │
        │  Prerequisite: Atlas annotation PathObjects in hierarchy.
        │  Detection assigns cells to regions via containment;
        │  if no regions exist, cells get no atlas label.
        ▼
[Parameter tuning — ONE section, GUI]
        │
        │  Tune sigma, min/max area, threshold, cytoplasmic expansion
        │  in BraiAnDetect GUI on representative section.
        │  Lock values into BraiAn.yaml. Do NOT proceed to batch
        │  until F1-score on test section is acceptable.
        ▼
[BraiAn.yaml — commit locked params to file]
        │
        ▼
[02_detect_classify.groovy — Run for project, all entries]
        │
        │  Detection is CPU-bound on i9-9900K; allow ~10–30 min
        │  per section at 20x. Run overnight if needed.
        │  QuPath auto-saves data.qpdata after each entry.
        ▼
[03_export_cells.groovy — Run for project without save]
        │
        ▼
[cells_all_sections.tsv → braian conda env → BraiAnalyse]
```

---

## Patterns to Follow

### Pattern 1: Load ABBA ROIs via Groovy (scriptable)

Run as a standalone script via "Run for project" before detection.

```groovy
// 01_load_abba_rois.groovy
// Loads warped Allen CCFv3 region annotations into the current entry.
// "acronym" labels each region by its atlas acronym (e.g. "CA1", "DG").
// false = do not split hemispheres (change to true if left/right comparison needed).
qupath.ext.biop.abba.AtlasTools.loadWarpedAtlasAnnotations(
    getCurrentImageData(), "acronym", false
)
```

This reads `ABBA-Transform-allen_mouse_10um_java.json` and `ABBA-RoiSet-allen_mouse_10um_java.zip`
from the entry directory automatically (ABBA extension handles path resolution).

### Pattern 2: BraiAn.yaml as the parameter lock

All detection parameters live in this file, not in the Groovy script. After tuning on one section, editing the YAML propagates the change to every section on the next batch run without touching script code.

```yaml
# BraiAn.yaml — place in QuPath project root
# Parameters below are starting seeds from bioRxiv 2024.09.16.611953;
# tune on ONE section before locking.
channels:
  nucleus: "DAPI"            # channel name in QuPath
  markers:
    - name: "TdTomato"
      channel: "TdTomato-AF568"
      compartment: "cytoplasm"   # cytoplasmic expansion ring measurement
    - name: "Fos"
      channel: "Fos-AF488"
      compartment: "nucleus"     # nuclear measurement only
detection:
  sigma: 2.0                 # Gaussian smoothing radius (µm); tune first
  background_radius: 8.0     # background subtraction radius (µm)
  min_area: 20               # minimum nucleus area (µm²)
  max_area: 400              # maximum nucleus area (µm²)
  threshold: 200             # intensity threshold; run find_threshold.groovy first
  cell_expansion: 5.0        # cytoplasmic ring width (µm); tune for TdTomato
classifiers:
  TdTomato: "classifiers/object_classifiers/TdT_classifier.json"
  Fos: "classifiers/object_classifiers/Fos_classifier.json"
```

### Pattern 3: Batch detection via "Run for project"

Write the detection script for `getCurrentImageData()` (single entry). Then invoke via Script Editor menu: Run > Run for project. QuPath iterates all entries sequentially, runs the script, and auto-saves each entry's data.qpdata.

```groovy
// 02_detect_classify.groovy
// BraiAnDetect reads BraiAn.yaml automatically when Extensions > BraiAn script is invoked.
// If calling directly, ensure BraiAn.yaml is at project root.
import qupath.ext.braian.BraiAnDetect

def imageData = getCurrentImageData()
// BraiAnDetect picks up BraiAn.yaml from project root:
BraiAnDetect.runDetection(imageData)
BraiAnDetect.runClassification(imageData)
// Results saved automatically to data.qpdata by Run-for-project machinery.
```

Note: The exact BraiAnDetect API calls may differ — the `compute_classify_overlap_export_exclude_detections.groovy`
prebaked script is the authoritative entry point. Use it rather than constructing calls manually.

### Pattern 4: Batch export in micron coordinates

```groovy
// 03_export_cells.groovy
// Export all detections from all entries into a single TSV.
// Use "Run for project (without save)" — pure export, no state change.
import qupath.lib.gui.tools.MeasurementExporter
import qupath.lib.objects.PathDetectionObject

def project = getProject()
def outputFile = new File(project.getPath().toFile().parent, "cells_all_sections.tsv")

new MeasurementExporter()
    .imageList(project.getImageList())
    .separator("\t")
    .exportType(PathDetectionObject.class)
    .exportMeasurements(outputFile)

print "Exported to: ${outputFile}"
```

Coordinates are in calibrated microns because the OME-TIFF carries `PhysicalSizeX` in its
OME-XML header, which QuPath reads at import and stores in `server.json` as `pixelCalibration`.
Verify: open one entry, go to Image tab, confirm pixel size shows ~0.69 µm/px (20x Airyscan).

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Per-section QuPath projects

**What happens:** Each section gets its own `*.qpproj` file and directory. Classifiers and scripts must be copied to each project manually. BraiAn.yaml must be duplicated.
**Why bad:** No batch execution path. Parameter changes require updating N files. Summary across sections requires stitching outputs manually.
**Do this instead:** One project per animal; all sections as entries. Classifiers live at project root and apply to all entries automatically.

### Anti-Pattern 2: Tuning parameters in the Groovy script

**What happens:** Detection sigma, threshold, expansion radius are hardcoded in the `.groovy` file. Script is modified between tuning iterations.
**Why bad:** No single source of truth. Easy to accidentally run batch with intermediate (un-locked) values. Prevents reproducibility audit.
**Do this instead:** All numeric parameters in BraiAn.yaml only. Scripts are immutable after initial writing. YAML is the artifact that gets documented in the lab notebook.

### Anti-Pattern 3: Running detection before ABBA ROIs are loaded

**What happens:** `02_detect_classify.groovy` runs before `01_load_abba_rois.groovy`. Cells are detected but have no atlas region assignment.
**Why bad:** BraiAnDetect assigns cells to regions via spatial containment at detection time. If no atlas annotation objects exist, cells get no region label. Re-running detection after loading ROIs is the only fix — double the compute time.
**Do this instead:** Script 01 (ROI load) is always run to completion for all entries before Script 02 (detection) is invoked. Verify ROIs are present by checking that the Annotations panel shows named regions (CA1, DG, etc.) in at least one entry before launching batch detection.

### Anti-Pattern 4: Batch detection before parameter lock on one section

**What happens:** Batch detection is run immediately across all sections while parameters are still being tuned.
**Why bad:** Must re-run detection for all sections if parameters change. On i9-9900K (CPU-only), 10–30 min/section means a full series re-run costs hours.
**Do this instead:** Tune on ONE representative section using the BraiAnDetect GUI. Confirm biologically plausible counts (compare to expected cell density from TRAP2 literature). Then lock BraiAn.yaml. Only then run batch.

### Anti-Pattern 5: Exporting pixel coordinates

**What happens:** Export script omits MeasurementExporter calibration step, or QuPath pixel calibration was never set.
**Why bad:** BraiAnalyse and brainrender both expect CCFv3 micron coordinates. Pixel coordinates at 0.69 µm/px will place cells in entirely wrong atlas positions.
**Do this instead:** Verify pixel calibration before batch export: Image tab > Pixel size must show ~0.69 µm x 0.69 µm. Source of truth is `PhysicalSizeX` in MIP OME-TIFF header. `czi_mip.py` embeds this correctly if `PIXEL_SIZE_UM` is set at the top of the script.

---

## Scalability Considerations

| Concern | Single section (now) | Full M3 series (~10–20 sections) | Multi-animal (future) |
|---------|---------------------|----------------------------------|-----------------------|
| Project layout | One project, one entry (current test project) | One project, N entries — no change | One project per animal; BraiAn.yaml shared or per-animal |
| Detection runtime | ~10–30 min per section (CPU) | Run overnight as batch | Same; run per-animal overnight |
| Parameter management | YAML tuned on one section | Same YAML applied to all entries | Copy tuned YAML to each animal project, or use parent-dir YAML (BraiAnDetect supports parent-dir lookup) |
| Export size | Small | One TSV per project (~N × cells) | Concat across animals before BraiAnalyse |
| Memory | 32 GB QuPath cap sufficient | Same; entries loaded one at a time | Same |

---

## Phase Ordering Implications

Based on these architecture findings, the correct phase sequence is:

1. **ABBA registration for all M3 sections (GUI)** — must complete for all entries before any scripting begins; ABBA-Transform + ABBA-RoiSet files must exist in every entry directory.

2. **Parameter tuning on one section (GUI + BraiAn.yaml authoring)** — use `find_threshold.groovy` for threshold suggestion; tune cytoplasmic expansion manually; validate nucleus-anchored colocalization rule; lock BraiAn.yaml.

3. **Script authoring: 01, 02, 03 (scriptable)** — write the three Groovy scripts; test 01 and 02 on the tuned section before batch.

4. **Batch execution: 01 → 02 → 03 for all entries (scriptable)** — run in order; verify summary.json for each entry after step 02; run step 03 only after all detections look clean.

5. **BraiAnalyse stats (Python, braian conda env)** — consumes `cells_all_sections.tsv`; aggregate to animal level before any comparison.

---

## Sources

- QuPath project structure and "Run for project" batch pattern: [QuPath docs — Project structure](https://qupath.readthedocs.io/en/latest/docs/reference/projects_structure.html), [QuPath scripting overview](https://qupath.readthedocs.io/en/latest/docs/scripting/overview.html)
- BraiAnDetect YAML config and prebaked scripts: [BraiAn for QuPath documentation](https://silvalab.codeberg.page/BraiAn/braian-qupath/), [GitHub: qupath-extension-braian](https://github.com/carlocastoldi/qupath-extension-braian)
- ABBA ROI loading Groovy call: [ABBA documentation — QuPath analysis](https://abba-documentation.readthedocs.io/en/latest/tutorial/4_qupath_analysis.html), [NicoKiaru Gist — cell detection after ABBA](https://gist.github.com/NicoKiaru/f45f56e3ff2d1fb708821c110fbdee62)
- BraiAn+ABBA combined scripts: [Codeberg — qupath-scripts-braian](https://codeberg.org/Bsilva/qupath-scripts-braian)
- MeasurementExporter API: [QuPath 0.6.0 Javadoc](https://qupath.github.io/javadoc/docs/qupath/lib/gui/tools/MeasurementExporter.html), [QuPath exporting measurements](https://qupath.readthedocs.io/en/stable/docs/tutorials/exporting_measurements.html)
- "Run for project" auto-save behavior: [Image.sc forum — global variables in batch scripts](https://forum.image.sc/t/global-variables-qupath-script-for-run-for-project-batch-processing/80246)

*Confidence: MEDIUM — core patterns are cross-checked across official QuPath docs and the ABBA/BraiAn documentation; exact BraiAnDetect API method signatures need verification against the installed extension version.*
