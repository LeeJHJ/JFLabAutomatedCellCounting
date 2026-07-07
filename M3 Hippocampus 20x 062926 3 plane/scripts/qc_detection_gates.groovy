/**
 * QC Detection Gates — D-05 Measurement Validation Harness
 *
 * REQUIREMENTS
 * ============
 * - Run AFTER a BraiAnDetect detection pass (WatershedCellDetection anchored on
 *   DAPI-T4, per BraiAn.yml) has produced cell detections + classifications on
 *   the current image entry.
 * - Detections must carry a nucleus-area measurement (produced automatically by
 *   WatershedCellDetection when makeMeasurements: true).
 * - Fos_Classifier_20x.json and TdT_classifier.json must exist under
 *   <project>/classifiers/object_classifiers/ (authored in this phase, Task 2).
 *
 * USAGE
 * -----
 * Copy this script to <QuPath project>/scripts/ and run via
 * Script Editor -> Run on the active entry, AFTER detection + classification.
 * This script prints RAW NUMBERS ONLY — it does NOT assert pass/fail. The
 * researcher compares the printed values against the D-05 hard gates
 * (see .planning/phases/02-detection-parameter-lock/02-CONTEXT.md):
 *   Gate 1: detected nucleus-area distribution peaks in 50-150 µm^2
 *   Gate 2: DAPI nucleus density in 500-2000 /mm^2
 * It also prints the D-06 Double+/TdT+ ratio as an ADVISORY REPORT ONLY —
 * D-06 is explicitly NOT a lock gate (gating on the expected biological result
 * risks tuning toward the hypothesis / circularity). Do not use this ratio to
 * decide pass/fail on detection parameters.
 *
 * @author [researcher name]
 */

import groovy.json.JsonSlurper

// ── Configuration ────────────────────────────────────────────────────────────
def FALLBACK_PIXEL_SIZE_UM = 0.6905355   // server.json PhysicalSizeX, M3 062926 3 plane entry 1
def AREA_BIN_WIDTH_UM2 = 10.0
def D05_AREA_PEAK_MIN = 50.0
def D05_AREA_PEAK_MAX = 150.0
def D05_DENSITY_MIN = 500.0
def D05_DENSITY_MAX = 2000.0
def D06_RATIO_MIN = 0.10
def D06_RATIO_MAX = 0.40

println "=" * 70
println "QC DETECTION GATES -- D-05 validation harness"
println "Running on: " + getCurrentImageData().getServer().getMetadata().getName()
println "=" * 70

// ── Resolve pixel size (µm/px) ─────────────────────────────────────────────
// Read from the image server when available (matches OME-XML PhysicalSizeX)
// rather than hard-coding, per Task 1 instructions; fall back to the known
// entry-1 value if the server exposes no calibration for some reason.
def server = getCurrentImageData().getServer()
def cal = server.getPixelCalibration()
def pixelSizeUm = FALLBACK_PIXEL_SIZE_UM
if (cal != null && cal.hasPixelSizeMicrons()) {
    pixelSizeUm = cal.getAveragedPixelSizeMicrons()
    println "Pixel size read from image server: ${pixelSizeUm} µm/px"
} else {
    println "WARNING: image server has no pixel calibration -- falling back to hard-coded ${FALLBACK_PIXEL_SIZE_UM} µm/px (server.json PhysicalSizeX)"
}
def pxToMm2 = (pixelSizeUm * 1e-3) ** 2

def detections = getDetectionObjects()
def annotations = getAnnotationObjects()
println "Total detections: ${detections.size()}"
println "Total annotations: ${annotations.size()}"

if (detections.isEmpty()) {
    println "ERROR: no detections found. Run BraiAnDetect (WatershedCellDetection on DAPI-T4) first."
    return
}

// ── Gate 1: nucleus-area distribution peak bin ──────────────────────────────
// Prefer the exact key produced by WatershedCellDetection; fall back to the
// first measurement name containing "Area" if that exact key is absent.
def sampleMeasurementNames = detections[0].getMeasurementList().getMeasurementNames()
def areaKey = "Nucleus: Area µm^2"
if (!sampleMeasurementNames.contains(areaKey)) {
    def fallbackKey = sampleMeasurementNames.find { it.toLowerCase().contains("area") }
    if (fallbackKey == null) {
        println "ERROR: no measurement containing 'Area' found on detections. Available measurements: ${sampleMeasurementNames}"
        return
    }
    println "WARNING: exact key '${areaKey}' not found on detections -- using fallback measurement key '${fallbackKey}'"
    areaKey = fallbackKey
} else {
    println "Using nucleus-area measurement key: '${areaKey}'"
}

def areas = detections.collect { it.getMeasurementList().getMeasurementValue(areaKey) }
                       .findAll { it != null && !it.isNaN() }
println "Detections with a valid area measurement: ${areas.size()} / ${detections.size()}"

def bins = [:].withDefault { 0 }
areas.each { a ->
    def binStart = ((int) Math.floor(a / AREA_BIN_WIDTH_UM2)) * AREA_BIN_WIDTH_UM2
    bins[binStart] = bins[binStart] + 1
}
def peakEntry = bins.max { it.value }
def peakBinStart = peakEntry?.key
def peakBinEnd = peakBinStart != null ? peakBinStart + AREA_BIN_WIDTH_UM2 : null

println "-" * 70
println "GATE 1 -- Nucleus area distribution peak"
if (peakBinStart != null) {
    println "  Peak bin: [${peakBinStart}, ${peakBinEnd}) µm^2  (count=${peakEntry.value})"
} else {
    println "  Peak bin: n/a (no valid area measurements)"
}
println "  D-05 target range: ${D05_AREA_PEAK_MIN}-${D05_AREA_PEAK_MAX} µm^2"
println "  (raw numbers only -- no pass/fail asserted here; researcher judges against the target range)"

// ── Gate 2: DAPI nucleus density per mm^2 ───────────────────────────────────
// Whole-section denominator = union of all loaded (ABBA) annotation ROI areas,
// which cover the full registered tissue extent (Phase 1 output).
def totalAreaPx2 = annotations.collect { it.getROI()?.getArea() ?: 0.0 }.sum() ?: 0.0
def totalAreaMm2 = totalAreaPx2 * pxToMm2
def wholeSectionDensity = totalAreaMm2 > 0 ? detections.size() / totalAreaMm2 : Double.NaN

println "-" * 70
println "GATE 2 -- DAPI nucleus density"
println "  Whole-section: ${detections.size()} detections / ${String.format('%.4f', totalAreaMm2)} mm^2 = ${String.format('%.1f', wholeSectionDensity)} /mm^2"
println "  D-05 target range: ${D05_DENSITY_MIN}-${D05_DENSITY_MAX} /mm^2"

// Per-annotation density for every loaded region (context for the researcher).
println "  Per-annotation density:"
annotations.each { ann ->
    def roi = ann.getROI()
    if (roi == null) return
    def areaMm2 = roi.getArea() * pxToMm2
    if (areaMm2 <= 0) return
    def nInside = detections.count { d ->
        def dRoi = d.getROI()
        dRoi != null && roi.contains(dRoi.getCentroidX(), dRoi.getCentroidY())
    }
    def density = nInside / areaMm2
    def label = ann.getPathClass()?.toString() ?: ann.getName() ?: "(unnamed)"
    println "    ${label}: ${nInside} detections / ${String.format('%.4f', areaMm2)} mm^2 = ${String.format('%.1f', density)} /mm^2"
}

// D-04 explicit stress-pair call-out: dense DG (worst case) + CA1 (clean check).
println "  D-04 stress-pair regions (explicit call-out):"
def dgAnn = annotations.find { ((it.getPathClass()?.toString() ?: it.getName() ?: "")).toUpperCase().contains("DG") }
def ca1Ann = annotations.find { ((it.getPathClass()?.toString() ?: it.getName() ?: "")).toUpperCase().contains("CA1") }
[DG: dgAnn, CA1: ca1Ann].each { label, ann ->
    if (ann == null) {
        println "    ${label}: no matching annotation found (check getPathClass()/getName() against expected region label)"
        return
    }
    def roi = ann.getROI()
    def areaMm2 = roi.getArea() * pxToMm2
    def nInside = detections.count { d ->
        def dRoi = d.getROI()
        dRoi != null && roi.contains(dRoi.getCentroidX(), dRoi.getCentroidY())
    }
    def density = areaMm2 > 0 ? nInside / areaMm2 : Double.NaN
    println "    ${label} (${ann.getPathClass() ?: ann.getName()}): ${nInside} detections / ${String.format('%.4f', areaMm2)} mm^2 = ${String.format('%.1f', density)} /mm^2"
}

// ── D-06 advisory: Double+ / TdT+ ratio (NOT a gate) ────────────────────────
// Computed directly from the classifier JSONs' own measurement + threshold
// fields (re-applied here to each detection's own measurements) rather than
// by parsing the merged PathClass name string produced by BraiAnDetect's
// SingleClassifier merge (qupath/ext/braian: PathClassTools.mergeClasses).
// The exact merged-class naming convention is not documented/verified
// (02-RESEARCH.md Assumptions A2) and both classifiers currently share the
// literal class names "Negative"/"Positive" (Task 2), so re-deriving directly
// from each classifier's own (measurement, threshold) pair is the robust,
// unambiguous way to compute this ADVISORY number.
println "-" * 70
println "D-06 ADVISORY -- Double+ / TdT+ ratio (NOT a lock gate; report only)"

def project = getProject()
def classifiersDir = new File(project.getBaseDirectory(), "classifiers/object_classifiers")

def loadClassifierSpec = { String fileName ->
    def f = new File(classifiersDir, fileName)
    if (!f.exists()) {
        println "  WARNING: classifier file not found: ${f} -- skipping D-06 computation for it"
        return null
    }
    def json = new JsonSlurper().parse(f)
    return [
        fileName   : fileName,
        measurement: json.function.measurement,
        threshold  : (json.function.threshold as double),
    ]
}

def fosSpec = loadClassifierSpec("Fos_Classifier_20x.json")
def tdtSpec = loadClassifierSpec("TdT_classifier.json")

def isPositive = { detection, spec ->
    if (spec == null) return false
    def v = detection.getMeasurementList().getMeasurementValue(spec.measurement)
    return v != null && !v.isNaN() && v >= spec.threshold
}

if (fosSpec != null) {
    println "  Fos spec: ${fosSpec.measurement} >= ${fosSpec.threshold}  (from ${fosSpec.fileName})"
}
if (tdtSpec != null) {
    println "  TdT spec: ${tdtSpec.measurement} >= ${tdtSpec.threshold}  (from ${tdtSpec.fileName})"
}

if (fosSpec != null && tdtSpec != null) {
    def fosPosCount = detections.count { isPositive(it, fosSpec) }
    def tdtPosCount = detections.count { isPositive(it, tdtSpec) }
    def doublePosCount = detections.count { isPositive(it, fosSpec) && isPositive(it, tdtSpec) }
    def ratio = tdtPosCount > 0 ? (doublePosCount / (double) tdtPosCount) : Double.NaN

    println "  Fos+ count: ${fosPosCount}"
    println "  TdT+ count: ${tdtPosCount}"
    println "  Double+ count (Fos+ AND TdT+): ${doublePosCount}"
    println "  Double+ / TdT+ ratio: ${String.format('%.3f', ratio)}"
    println "  D-06 advisory target range: ${D06_RATIO_MIN}-${D06_RATIO_MAX} (ADVISORY ONLY -- do not gate parameter tuning on this)"
} else {
    println "  Skipped: one or both classifier JSONs were not found."
}

println "=" * 70
println "QC DETECTION GATES complete. Compare printed numbers to the D-05 target"
println "ranges above; do NOT treat this script's output as a pass/fail verdict."
println "=" * 70
