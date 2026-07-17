/**
 * 03_export_val01_metrics.groovy — VAL-01 per-cell + per-region export (D-03/D-04)
 *
 * SCOPE: This script does NOT detect or classify. It MUST run AFTER
 * 02_detect_classify.groovy has already run and been SAVED on the current
 * entry — it reads getPathClass() (set by 02_detect_classify.groovy's
 * compound classification loop) and the local-background-subtracted
 * measurement keys that script writes ("Nucleus: AF488-T3 mean (bg-sub)",
 * "Cytoplasm: AF568-T2 mean (bg-sub)"). Running this before classification
 * will produce a per-cell export with class="Negative" for everything and
 * NaN bg-sub columns (RESEARCH Pitfall 4 — the exact Phase-3 D-04/D-05
 * all-Negative symptom).
 *
 * Emits TWO tab-delimited outputs into THIS QuPath project's results/ dir
 * (a single-run Phase-4 snapshot — overwritten/truncated fresh each run,
 * unlike the growing cross-image reference/dapi_region_reference.csv):
 *   1. results/val01_percell_export.tsv — one row per detection:
 *      class, region_label, nucleus_area_um2, centroid_x, centroid_y,
 *      fos_bgsub, tdt_bgsub
 *   2. results/val01_region_area.tsv — one row per leaf atlas-region
 *      annotation (D-04): region_label, hemisphere, acronym, is_leaf,
 *      area_mm2
 *
 * Downstream: scripts/val01_metrics.py (braian env) reads both TSVs and
 * computes the four VAL-01 bioplausibility metrics. Column names here are
 * the exact contract that script parses against — do not rename without
 * updating both sides.
 *
 * Deploy: author in canonical scripts/, hard-copy byte-identically into
 * <QuPath project>/scripts/ (dual-location deploy, established convention).
 * Run via "Run for project" (human-run, per the GUI/scriptable split).
 *
 * @author section-pipeline
 */
import static qupath.lib.scripting.QP.*

println "Running on: " + getCurrentImageData().getServer().getMetadata().getName()

// ── pixel calibration (verbatim idiom, shared across export_region_dapi_reference.groovy /
//    qc_detection_gates.groovy / 02_detect_classify.groovy) ─────────────────────────────────
def imageData = getCurrentImageData()
def server = imageData.getServer()
def cal = server.getPixelCalibration()
def FALLBACK_PIXEL_SIZE_UM = 0.6905355   // server.json PhysicalSizeX, M3 062926 3 plane entry 1
def pixelUm = FALLBACK_PIXEL_SIZE_UM
if (cal != null && cal.hasPixelSizeMicrons()) {
    pixelUm = cal.getAveragedPixelSizeMicrons()
    println "Pixel size read from image server: ${pixelUm} µm/px"
} else {
    println "WARNING: image server has no pixel calibration -- falling back to hard-coded ${FALLBACK_PIXEL_SIZE_UM} µm/px (server.json PhysicalSizeX)"
}
def pxToMm2 = (pixelUm * 1e-3) ** 2
def pxToUm2 = pixelUm * pixelUm   // px² → µm²; nucleus area computed from ROI geometry (below), not a stored shape measurement

def dets = getDetectionObjects()
if (dets.isEmpty()) {
    println "No detections — run BraiAnDetect (run_braian_detection.groovy) and 02_detect_classify.groovy first. Aborting."
    return
}

// ── SC2-style region resolution (reused verbatim from 02_detect_classify.groovy) ────────────
def regionAnnotations = getAnnotationObjects().findAll { ann ->
    def roi = ann.getROI()
    roi != null && !ann.getChildObjects().any { it.isAnnotation() }
}
println "Leaf region annotations available for labeling: ${regionAnnotations.size()}"

def regionOf = { detection ->
    def r = detection.getROI()
    double x = r.getCentroidX(), y = r.getCentroidY()
    regionAnnotations.find { it.getROI().contains(x, y) }
}

def regionLabel = { region ->
    if (region == null) return "(no region)"
    def label = region.getPathClass()?.toString() ?: region.getName()
    if (label == null) return "(no region)"
    def m = (label =~ /(?i)^(?:Left|Right):\s*(.+)$/)
    return m.find() ? m.group(1) : label
}

// ── measurement keys (CRITICAL: exact literals 02_detect_classify.groovy writes;
//    RESEARCH Pitfall 4 — the Phase-3 all-Negative root cause was a key mismatch) ────────────
// Nucleus area is NOT read from a stored shape measurement: BraiAnDetect detections carry the
// intensity measurements written by 02_detect_classify.groovy (the bg-sub keys below) but no
// "Nucleus: Area µm^2" shape measurement was ever computed, so that key returns null on every
// cell (the all-null nucleus_area_um2 column caught at the 04-03 human-verify gate). Compute area
// directly from the detection's nucleus ROI geometry instead — the same roi.getArea()×calibration
// idiom used for per-region area below (line ~150).
def fosKey  = "Nucleus: AF488-T3 mean (bg-sub)"
def tdtKey  = "Cytoplasm: AF568-T2 mean (bg-sub)"

// Safe numeric read: never dereference a measurement without a null guard.
def numOrNaN = { measMap, String key ->
    def v = measMap.get(key)
    return (v == null || Double.isNaN(v.doubleValue())) ? Double.NaN : v.doubleValue()
}

// ── per-cell export ───────────────────────────────────────────────────────────────────────
println "Exporting per-cell measurements for ${dets.size()} detections..."
def percellRows = []
int nProcessed = 0
dets.each { d ->
    def m = d.getMeasurements()
    def cls = d.getPathClass()?.toString() ?: "Negative"
    def region = regionOf(d)
    def label = regionLabel(region)
    def nucleusRoi = (d.respondsTo('getNucleusROI') && d.getNucleusROI() != null) ? d.getNucleusROI() : d.getROI()
    def areaUm2 = (nucleusRoi != null) ? nucleusRoi.getArea() * pxToUm2 : Double.NaN
    def r = d.getROI()
    double cx = r != null ? r.getCentroidX() : Double.NaN
    double cy = r != null ? r.getCentroidY() : Double.NaN
    def fosBgsub = numOrNaN(m, fosKey)
    def tdtBgsub = numOrNaN(m, tdtKey)
    percellRows << [cls, label, areaUm2, cx, cy, fosBgsub, tdtBgsub]
    nProcessed++
    if (nProcessed % 5000 == 0) println "  ...exported ${nProcessed}/${dets.size()} detections"
}

def resultsDir = new File(getProject().getBaseDirectory(), "results")
resultsDir.mkdirs()

def percellFile = new File(resultsDir, "val01_percell_export.tsv")
def percellHeader = ["class", "region_label", "nucleus_area_um2", "centroid_x", "centroid_y", "fos_bgsub", "tdt_bgsub"].join("\t")
def percellSb = new StringBuilder()
percellSb.append(percellHeader).append("\n")
percellRows.each { row ->
    percellSb.append(String.format('%s\t%s\t%s\t%s\t%s\t%s\t%s%n',
        row[0], row[1],
        Double.isNaN(row[2]) ? "" : String.format('%.4f', row[2]),
        Double.isNaN(row[3]) ? "" : String.format('%.3f', row[3]),
        Double.isNaN(row[4]) ? "" : String.format('%.3f', row[4]),
        Double.isNaN(row[5]) ? "" : String.format('%.4f', row[5]),
        Double.isNaN(row[6]) ? "" : String.format('%.4f', row[6])))
}
// Overwrite (truncate) each run — this is a per-run Phase-4 snapshot, not a growing
// cross-image reference like dapi_region_reference.csv.
percellFile.text = percellSb.toString()
println "Wrote ${percellRows.size()} per-cell rows -> ${percellFile}"

// ── per-region area export (D-04) — reuses export_region_dapi_reference.groovy's
//    region loop verbatim (skip detection-container annotations, skip AllDetections,
//    hemisphere/acronym regex-split, is_leaf via child-annotation emptiness) ────────────────
def regionRows = []
getAnnotationObjects().each { ann ->
    def roi = ann.getROI()
    if (roi == null) return
    if (ann.getChildObjects().any { it.isDetection() }) return          // skip the detection container(s)
    def label = ann.getPathClass()?.toString() ?: ann.getName()
    if (label == null || label == "AllDetections") return
    def isLeaf = ann.getChildObjects().findAll { it.isAnnotation() }.isEmpty()
    def hemisphere = ""; def acronym = label
    def m = (label =~ /(?i)^(Left|Right):\s*(.+)$/)
    if (m.find()) { hemisphere = m.group(1); acronym = m.group(2) }
    def areaMm2 = roi.getArea() * pxToMm2
    if (areaMm2 <= 0) return
    regionRows << [label, hemisphere, acronym, isLeaf, areaMm2]
}

def regionFile = new File(resultsDir, "val01_region_area.tsv")
def regionHeader = ["region_label", "hemisphere", "acronym", "is_leaf", "area_mm2"].join("\t")
def regionSb = new StringBuilder()
regionSb.append(regionHeader).append("\n")
regionRows.each { row ->
    regionSb.append(String.format('%s\t%s\t%s\t%s\t%.6f%n', row[0], row[1], row[2], row[3], row[4]))
}
regionFile.text = regionSb.toString()
println "Wrote ${regionRows.size()} per-region area rows -> ${regionFile}"

println "VAL-01 export complete: ${percellFile.name} (${percellRows.size()} cells), ${regionFile.name} (${regionRows.size()} regions)."
