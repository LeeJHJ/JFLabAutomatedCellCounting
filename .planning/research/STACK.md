# Technology Stack — QuPath Scripting & BraiAnDetect API

**Project:** M3 Hippocampus Section Pipeline (TRAP2 / Steps 3–4)
**Researched:** 2026-06-30
**Scope:** QuPath Groovy scripting API, BraiAnDetect configuration, coordinate export

---

## Installed Extension Versions (verified on-disk)

| Extension | Version | Jar path |
|-----------|---------|----------|
| QuPath | 0.6.0 | `$HOME/section-pipeline/tools/QuPath/bin/QuPath` |
| qupath-extension-braian | 1.1.0 | `.../BraiAn catalog/QuPath BraiAn extension/v1.1.0/main-jar/` |
| qupath-extension-abba | 0.4.0 | `.../QuPath-BIOP catalog/QuPath ABBA extension/v0.4.0/main-jar/` |
| qupath-extension-warpy | 0.4.2 | `.../QuPath-BIOP catalog/QuPath Warpy extension/v0.4.2/main-jar/` |

---

## Actual Channel Names in the M3 20x MIP

From `project.qpproj` (M3 Hippocampus 20x 062926 3 plane, pixelWidth = 0.6905 µm/px):

| QuPath channel name | Marker | Role |
|--------------------|--------|------|
| `AF568-T2` | TdTomato | Encoding engram; cytosolic |
| `AF488-T3` | Fos | Recall IEG; nuclear |
| `DAPI-T4` | DAPI | Nuclear stain for segmentation |

BraiAn.yml must use these **exact** channel name strings — they come from the OME-TIFF metadata as written by `czi_mip.py` and are how QuPath labels channels internally. Cross-check with the project's channel list before running detection.

---

## BraiAn.yml Configuration

BraiAn reads a `BraiAn.yml` file placed in the QuPath project folder **or** its parent directory. It is the single source of truth for all detection, classification, and overlap parameters. The file must be present before running the main detection script.

### Full Annotated Schema (with TRAP2-specific values)

```yaml
# Place in the QuPath project dir or its parent dir.
# Channel names must match QuPath's internal channel labels exactly.

classForDetections: null        # null = run on whole image root annotation
                                # Set to an annotation class name (string) to restrict

detectionsCheck:
  apply: true                   # MANDATORY for TRAP2: ensures every Fos/TdT detection
                                #   is contained within a DAPI nucleus
  controlChannel: "AF568-T2"   # Use TdTomato (cytosolic, larger ROI) as the container
                                #   cell, not DAPI — DAPI detections are nuclear-only
                                #   while TdT detections include a cytoplasmic ring

channelDetections:
  # ── DAPI: nuclear segmentation basis ──────────────────────────────────────
  - name: "DAPI-T4"
    parameters:
      requestedPixelSizeMicrons: 0.69   # match native pixel size (no downsampling)
      backgroundRadiusMicrons: 10.0     # > largest nucleus; 10 µm is safe for neurons
      backgroundByReconstruction: true  # true = more accurate background, default
      medianRadiusMicrons: 0.0
      sigmaMicrons: 1.5                 # starting value from BraiAn example; tune up
                                        #   (e.g. 2.0) if nuclei fragment
      minAreaMicrons: 30.0              # mouse neuron nucleus ~5–8 µm diam → ~80 µm²
                                        #   start at 30 to reject debris; tune from overlay
      maxAreaMicrons: 500.0             # reject merged clumps; neurons rarely exceed 300 µm²
      threshold: 200                    # or use histogramThreshold (see below)
      watershedPostProcess: true        # split merged nuclei; keep true
      cellExpansionMicrons: 0.0         # DAPI detection = nuclei only; no expansion here
      includeNuclei: true
      smoothBoundaries: true
      makeMeasurements: true

  # ── TdTomato: cytosolic engram marker ─────────────────────────────────────
  - name: "AF568-T2"
    parameters:
      requestedPixelSizeMicrons: 0.69
      backgroundRadiusMicrons: 10.0
      backgroundByReconstruction: true
      medianRadiusMicrons: 0.0
      sigmaMicrons: 1.5                 # nucleus seed; tune to 2.0 if fragmented
      minAreaMicrons: 30.0
      maxAreaMicrons: 500.0
      # Use auto-threshold from histogram (recommended over fixed threshold):
      histogramThreshold:
        resolutionLevel: 4              # coarser level = faster; 4 is standard
        smoothWindowSize: 15
        peakProminence: 100             # raise if background peaks contaminate
        nPeak: 1                        # first local max above background = signal
      watershedPostProcess: true
      cellExpansionMicrons: 5.0         # CRITICAL: expands nucleus into cytoplasm
                                        #   to capture TdT signal (cytosolic dye).
                                        #   5 µm = starting point; tune visually.
                                        #   Increase to 7–8 µm if TdT signal missed.
      includeNuclei: true               # measure both nuclear + cytoplasmic compartments
      smoothBoundaries: true
      makeMeasurements: true
    classifiers:
      - name: "TdTomato_classifier"    # must exist in project classifiers/ dir

  # ── Fos: nuclear IEG marker ───────────────────────────────────────────────
  - name: "AF488-T3"
    parameters:
      requestedPixelSizeMicrons: 0.69
      backgroundRadiusMicrons: 10.0
      backgroundByReconstruction: true
      medianRadiusMicrons: 0.0
      sigmaMicrons: 1.5
      minAreaMicrons: 30.0
      maxAreaMicrons: 500.0
      histogramThreshold:
        resolutionLevel: 4
        smoothWindowSize: 15
        peakProminence: 100
        nPeak: 1
      watershedPostProcess: true
      cellExpansionMicrons: 0.0         # Fos is NUCLEAR; do NOT expand into cytoplasm.
                                        #   Expanding would merge adjacent nuclei and
                                        #   create false Fos+ calls.
      includeNuclei: true
      smoothBoundaries: true
      makeMeasurements: true
    classifiers:
      - name: "Fos_classifier"         # must exist in project classifiers/ dir
```

### Key Parameter Rationale for TRAP2

| Parameter | DAPI | TdTomato (AF568-T2) | Fos (AF488-T3) | Reason |
|-----------|------|---------------------|-----------------|--------|
| `cellExpansionMicrons` | 0 | **5.0** (start) | **0** | TdT is cytosolic — must measure in cytoplasmic ring. Fos is nuclear — expansion causes boundary errors. |
| `sigmaMicrons` | 1.5 | 1.5 | 1.5 | Gaussian smoothing; increase to 2.0 if nuclei fragment. Seed from BraiAn example. |
| `minAreaMicrons` | 30 | 30 | 30 | Mouse neuron nuclei ~5–8 µm diam. Adjust down to 20 if small cells missed, up to 50 to exclude debris. |
| `maxAreaMicrons` | 500 | 500 | 500 | Exclude glial clumps and merged nuclei. |
| `detectionsCheck.controlChannel` | — | `AF568-T2` | — | TdT has the cytoplasmic ring, so it is the containing cell object. All Fos detections must fall inside a TdT detection. |

### `detectionsCheck` logic

When `apply: true`, BraiAn checks that every detection in non-control channels (here, Fos/AF488-T3) is spatially contained within a detection in the `controlChannel` (here, TdTomato/AF568-T2). This enforces nucleus-anchored colocalization without proximity heuristics. Detections that fail the check are discarded or flagged, not counted as double+.

**Note:** `detectionsCheck` is BraiAn's colocalization guard. The OverlappingDetections class in the main script provides the actual double+ count.

---

## WatershedCellDetection — Raw `runPlugin` API (QuPath 0.6.x)

BraiAn calls this internally via `ChannelDetections`. For manual/one-off scripting, the raw form is:

```groovy
// Run detection on the current image, in all annotations
def detectionParams = [
    detectionImage: "DAPI-T4",
    requestedPixelSizeMicrons: 0.69,
    backgroundRadiusMicrons: 10.0,
    medianRadiusMicrons: 0.0,
    sigmaMicrons: 1.5,
    minAreaMicrons: 30.0,
    maxAreaMicrons: 500.0,
    threshold: 200.0,
    watershedPostProcess: true,
    cellExpansionMicrons: 0.0,
    includeNuclei: true,
    smoothBoundaries: true,
    makeMeasurements: true
]
runPlugin(
    'qupath.imagej.detect.cells.WatershedCellDetection',
    detectionParams
)
```

**QuPath 0.6.x note:** The `runPlugin` API accepting a `Map` is available in 0.6.x. Prefer BraiAn's `ChannelDetections` constructor over raw `runPlugin` for batch runs — it handles channel selection, parameter storage in the YAML, and consistent application across all project images.

---

## Main Detection Script

BraiAn ships a canonical script inside the jar at `scripts/compute_classify_overlap_export_exclude_detections.groovy`. Copy this script into the QuPath project `scripts/` directory and run it from the Script Editor (or via QuPath CLI for batch). It does, in order:

1. Reads `BraiAn.yml` (from project dir or parent)
2. For each `channelDetections` entry: runs `WatershedCellDetection` with YAML params
3. Applies classifiers per channel
4. Computes double+ (`OverlappingDetections`) using the control channel
5. Exports results to `<projectDir>/results/<imageName>_regions.tsv`
6. Exports excluded regions to `<projectDir>/regions_to_exclude/<imageName>_regions_to_exclude.txt`

```groovy
import qupath.ext.braian.AtlasManager
import qupath.ext.braian.OverlappingDetections
import qupath.ext.braian.ImageChannelTools
import qupath.ext.braian.ChannelDetections
import qupath.ext.braian.config.ProjectsConfig
import static qupath.lib.scripting.QP.*

var imageData = getCurrentImageData()
var server = imageData.getServer()      // avoid in 0.6.x hot-path — makes scripts slow
var hierarchy = imageData.getHierarchy()
var config = ProjectsConfig.read("BraiAn.yml")
var annotations = config.getAnnotationsForDetections(hierarchy)

// 1. Detect per channel
var allDetections = config.channelDetections.collect { detectionsConf ->
    var channel = new ImageChannelTools(detectionsConf.name, server)
    try {
        new ChannelDetections(channel, annotations, detectionsConf.parameters, hierarchy)
    } catch (IllegalArgumentException ignored) { null }
}.findAll { it != null }

// 2. Classify
allDetections.forEach { detections ->
    var detectionsConfig = config.channelDetections
        .find { it.name == detections.getId() }
    if (detectionsConfig.classifiers == null) return
    var partialClassifiers = detectionsConfig.classifiers.collect { it.toPartialClassifier(hierarchy) }
    detections.applyClassifiers(partialClassifiers, imageData)
}

// 3. Double+ overlap
var overlaps = []
Optional<String> control
if ((control = config.getControlChannel()).isPresent()) {
    var controlChannel = allDetections.find { it.getId() == control.get() }
    var otherChannels  = allDetections.findAll { it.getId() != control.get() }
    overlaps = [new OverlappingDetections(controlChannel, otherChannels, true, hierarchy)]
}

// 4. Export
var atlasName = "allen_mouse_10um_java"
if (AtlasManager.isImported(atlasName, hierarchy)) {
    var atlas = new AtlasManager(atlasName, hierarchy)
    def imageName = getProjectEntry().getImageName()
        .replaceAll('[<>:"/\\\\|?*]', '')
    var resultsFile = new File(buildPathInProject("results", imageName + "_regions.tsv"))
    atlas.saveResults(allDetections + overlaps, resultsFile)
    def exclusionsFile = new File(buildPathInProject("regions_to_exclude", imageName + "_regions_to_exclude.txt"))
    atlas.fixExclusions()
    atlas.saveExcludedRegions(exclusionsFile)
}
println getCurrentImageName() + " : DONE!"
```

**QuPath 0.6.x performance note:** The comment in the shipped script warns explicitly: "unless explicitly needed, from QuPath 0.6.* avoid calling `imageData.getServer()`. It makes scripts considerably slower." Use `imageData.getHierarchy()` and `getCurrentImageData()` instead; only call `getServer()` once for `ImageChannelTools` initialization.

---

## Export File Format (BraiAn TSV)

### Per-image results file: `<projectDir>/results/<imageName>_regions.tsv`

Tab-separated. The braian Python library reads these via `BrainSlice.from_qupath()`.

**Required columns (verified from braian Python library source):**

| Column | Type | Description |
|--------|------|-------------|
| `Name` | string | Atlas region annotation name (e.g. `"Root"`, `"CA1"`) |
| `Classification` | string | Region acronym with hemisphere: `"Left: CA1"`, `"Right: DG"` |
| `Num Detections` | int | Total detection count across all channels in this region |
| `Area um^2` | float | Region area in square microns |
| `Num <channelName>` | int | Per-channel detection count; one column per `channelDetections` entry |

**Example column set for TRAP2:**
```
Name  Classification  Num Detections  Area um^2  Num AF568-T2  Num AF488-T3  Num AF568-T2+AF488-T3
```

The `"Num AF568-T2+AF488-T3"` column is the double+ count from `OverlappingDetections`. The braian Python library maps these via `ch2marker`:

```python
ch2marker = {
    "AF568-T2": "TdTomato",
    "AF488-T3": "Fos",
}
# SlicedBrain.from_qupath(tsv_path, ch2marker, atlas="allen_mouse_10um_java")
```

### Exclusion file: `<projectDir>/regions_to_exclude/<imageName>_regions_to_exclude.txt`

Plain text, one region acronym per line. Regions to drop from braian Python analysis due to tissue damage or poor alignment.

---

## Atlas Coordinate Export (per-cell XYZ in Allen CCFv3 space)

BraiAn's `saveResults` exports **region-level counts**, not per-cell coordinates. For per-cell brainrender point clouds, add Atlas XYZ measurements to detections with this script (run after detection, before export):

```groovy
import net.imglib2.RealPoint
import qupath.lib.measurements.MeasurementList
import qupath.ext.biop.abba.AtlasTools
import static qupath.lib.gui.scripting.QPEx.*

def pixelToAtlasTransform =
    AtlasTools.getAtlasToPixelTransform(getCurrentImageData()).inverse()

getDetectionObjects().forEach { detection ->
    RealPoint atlasCoords = new RealPoint(3)
    MeasurementList ml = detection.getMeasurementList()
    atlasCoords.setPosition(
        [detection.getROI().getCentroidX(),
         detection.getROI().getCentroidY(), 0] as double[]
    )
    pixelToAtlasTransform.apply(atlasCoords, atlasCoords)
    ml.put("Atlas_X", atlasCoords.getDoublePosition(0))
    ml.put("Atlas_Y", atlasCoords.getDoublePosition(1))
    ml.put("Atlas_Z", atlasCoords.getDoublePosition(2))
}
fireHierarchyUpdate()
```

**Units:** `getCentroidX()` / `getCentroidY()` return **pixel** coordinates. The `AtlasTools` transform converts these to Allen CCFv3 coordinates in **mm** (the atlas is defined in µm/10 = 10 µm steps, but the transform output is typically in mm). Cross-check the brainrender import: `brainrender` expects CCFv3 coordinates in µm, so multiply by 1000 if the transform returns mm.

**Alternative micron approach** — if you want image-space microns (not atlas space), convert directly:

```groovy
double pixelWidth  = server.getPixelCalibration().getPixelWidthMicrons()
double pixelHeight = server.getPixelCalibration().getPixelHeightMicrons()
// per detection:
double xMicrons = roi.getCentroidX() * pixelWidth
double yMicrons = roi.getCentroidY() * pixelHeight
```

The image-space microns are only useful for intra-section measurements; use atlas-transform coordinates for cross-section point clouds in brainrender.

---

## MeasurementExporter — Standard QuPath 0.6.x Export

For exporting the QuPath measurement table (shape + intensity measurements per cell, not region counts):

```groovy
import qupath.lib.gui.tools.MeasurementExporter
import qupath.lib.objects.PathCellObject

def project = getProject()
def imagesToExport = project.getImageList()
def outputFile = new File(buildPathInProject("export", "all_detections.tsv"))
outputFile.parentFile.mkdirs()

new MeasurementExporter()
    .imageList(imagesToExport)
    .separator("\t")
    .exportType(PathCellObject.class)     // PathDetectionObject.class for non-cell detections
    .exportMeasurements(outputFile)
```

**Default columns in the exported TSV** (shape measurements added by `makeMeasurements: true`):
- `Image`, `Name`, `Class`, `Parent`
- `Centroid X µm`, `Centroid Y µm` — image-space centroids in microns (uses OME-XML pixel calibration)
- `Area µm^2`, `Perimeter µm`, `Circularity`, `Max diameter µm`, `Min diameter µm`
- Per-channel intensity: `<ChannelName>: Nucleus: Mean`, `<ChannelName>: Cell: Mean`, `<ChannelName>: Cytoplasm: Mean`

`Centroid X µm` and `Centroid Y µm` are **image-space microns** (not atlas space). They are correct for inter-channel comparisons within a section but cannot be used directly for 3D atlas mapping.

---

## Auto-Threshold Helper (for threshold tuning)

BraiAn ships `scripts/find_threshold.groovy` for interactive histogram inspection:

```groovy
import qupath.ext.braian.ImageChannelTools
import qupath.ext.braian.config.AutoThresholdParmameters
import qupath.ext.braian.config.WatershedCellDetectionConfig
import static qupath.lib.scripting.QP.*

var server = getCurrentImageData().getServer()
var channel = new ImageChannelTools("AF568-T2", server)   // adjust channel name
var thresholder = new AutoThresholdParmameters()           // defaults: resLevel=4, smooth=15, prominence=100, nPeak=1
WatershedCellDetectionConfig.findThreshold(channel, thresholder)
// Prints found threshold to QuPath log
```

Use this interactively on a representative image section before committing a `histogramThreshold` block to BraiAn.yml.

---

## Classifier Setup

BraiAn applies classifiers from `project/classifiers/` or its parent directory. The classifier JSON files are created in QuPath's GUI (Train Object Classifier or Simple Threshold Classifier). For TRAP2:

- `TdTomato_classifier.json` — trained on AF568-T2 cytoplasmic intensity; classifies cells as `TdTomato` or background
- `Fos_classifier.json` — trained on AF488-T3 nuclear intensity; classifies as `Fos` or background

The class names `Fos` and `TdTomato` are already present in the M3 Hippocampus 20x 062926 3 plane project's `classifiers/classes.json`. These class names are what BraiAn uses in `ChannelClassifierConfig` and what the braian Python library receives in the TSV `Classification` column to identify double+ cells.

**Create classifiers via:** QuPath GUI → Objects → Classify → Train Object Classifier → Simple Threshold Classifier on channel intensity → Save. Name the file exactly as referenced in BraiAn.yml `classifiers.name` field.

---

## Batch Run Across Multiple Images

BraiAn ships `scripts/run_script_for_multiple_projects.groovy` for one-script-across-all-projects execution. For a single project with multiple images (a series), use QuPath's built-in batch runner: Script Editor → Run → Run for Project. All images in the current project are processed in sequence using the same `BraiAn.yml` parameters.

---

## Key API Calls Reference

| Goal | Groovy call |
|------|-------------|
| Load ABBA atlas annotations | `AtlasTools.loadWarpedAtlasAnnotations(getCurrentImageData(), "acronym", true)` |
| Get all cell detections | `getCellObjects()` / `getDetectionObjects()` |
| Get annotations (atlas regions) | `getAnnotationObjects()` |
| Build path inside project | `buildPathInProject("results", imageName + "_regions.tsv")` |
| Get pixel calibration | `getCurrentImageData().getServer().getPixelCalibration().getPixelWidthMicrons()` |
| Get image hierarchy | `getCurrentImageData().getHierarchy()` |
| Get atlas→pixel transform | `AtlasTools.getAtlasToPixelTransform(getCurrentImageData())` |
| Check atlas imported | `AtlasManager.isImported("allen_mouse_10um_java", hierarchy)` |
| Save region results | `atlas.saveResults(allDetections + overlaps, resultsFile)` |
| Save excluded regions | `atlas.saveExcludedRegions(exclusionsFile)` |
| Read BraiAn config | `ProjectsConfig.read("BraiAn.yml")` |

---

## Critical Caveats (QuPath 0.6.x + BraiAnDetect 1.1.0)

1. **`getServer()` is slow in 0.6.x.** Call it once at script start, only when needed for `ImageChannelTools`. Do not call inside loops. The BraiAn script comment flags this explicitly.

2. **Channel names are case-sensitive and must match exactly.** BraiAn throws `IllegalChannelName` if the name in BraiAn.yml does not match the QuPath server channel name character-for-character. The names in this project are `AF568-T2`, `AF488-T3`, `DAPI-T4`.

3. **ABBA must be imported before running BraiAn detection.** `AtlasManager.isImported("allen_mouse_10um_java", hierarchy)` returns false if ABBA annotations have not been loaded; the export silently skips. Load atlas annotations via `Extensions > ABBA > Load Atlas Annotations` before running the detection script.

4. **`detectionsCheck` requires the control channel to be detected first.** BraiAn processes channels in YAML order. Place the control channel (`AF568-T2`) first or ensure it is detected before the others.

5. **Cytoplasmic expansion is the detection compartment for TdTomato.** Setting `cellExpansionMicrons: 0.0` on the TdT channel means TdT is measured in the nuclear compartment only — the DAPI nucleus. Because TdTomato is cytosolic, this would produce systematically low signal. The expansion ring is mandatory.

6. **braian Python `from_qupath` expects `"allen_mouse_10um_java"` as atlas name.** The atlas name string in the TSV header is set by BraiAn at export time from the QuPath ABBA atlas identifier. If the atlas name differs (e.g., `"allen_mouse_25um_java"`), the Python library's sanity check raises an `AssertionError`.

7. **Double+ count column name is `"Num AF568-T2+AF488-T3"`** (or whatever the channel names are, joined by `+`). The braian Python `_column_from_qupath_channel` function generates per-channel columns as `f"Num {channel}"`. The overlap column follows the same pattern with the two channel names concatenated with `+`.

---

## Sources

- BraiAn.yml canonical example: `https://raw.githubusercontent.com/carlocastoldi/qupath-extension-braian/master/BraiAn.yml`
- BraiAn extension README: `https://github.com/carlocastoldi/qupath-extension-braian`
- Bundled sample scripts: extracted from `/home/jflab/section-pipeline/tools/QuPath/extensions/catalogs/BraiAn catalog/QuPath BraiAn extension/v1.1.0/main-jar/qupath-extension-braian-1.1.0.jar`
- braian Python library source (installed): `/home/jflab/miniforge3/envs/braian/lib/python3.11/site-packages/braian/`
- ABBA atlas coordinate export script: `https://abba-documentation.readthedocs.io/en/latest/tutorial/4_qupath_analysis.html`
- QuPath 0.6.0 QP Javadoc: `https://qupath.github.io/javadoc/docs/qupath/lib/scripting/QP.html`
- QuPath project files verified on-disk: `project.qpproj` files in `/home/jflab/Analysis/`
- [WatershedCellDetection Javadoc (QuPath 0.6.0)](https://qupath.github.io/javadoc/docs/qupath/imagej/detect/cells/WatershedCellDetection.html)
- [MeasurementExporter usage (QuPath 0.5 docs)](https://qupath.readthedocs.io/en/0.5/docs/tutorials/exporting_measurements.html)
- [ABBA + QuPath cell detection Gist (NicoKiaru/BIOP)](https://gist.github.com/NicoKiaru/f45f56e3ff2d1fb708821c110fbdee62)
