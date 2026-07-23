/**
 * RETIRED 2026-07-23 (Phase 06.1 Plan 04, D-07): superseded by
 * scripts/03_export_region_table.groovy, which folds in this script's per-cell
 * export role (CR-01 leaf resolution, per-entry non-clobbering stem) plus
 * export_region_dapi_reference.groovy's all-region loop + growing-CSV pattern,
 * generalized from a fixed Fos/TdT pair to any N declared markers (pipeline.yml).
 * Kept here for historical reference only — do not deploy or run this file; no
 * QuPath project scripts/ dir references it anymore (PIPE-02).
 *
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
 * Emits TWO tab-delimited outputs into THIS QuPath project's results/ dir,
 * one pair PER PROJECT ENTRY (EXP-02, D-06/D-07 — fixed 2026-07-18: the prior
 * hardcoded filenames truncated to only the last-processed entry on "Run for
 * project"; output paths are now a function of the sanitized running entry
 * name, evaluated per-entry via getProjectEntry(), so N entries produce 2*N
 * distinct files with no cross-entry clobbering):
 *   1. results/<stem>__val01_percell_export.tsv — one row per detection:
 *      class, region_label, nucleus_area_um2, centroid_x, centroid_y,
 *      fos_bgsub, tdt_bgsub
 *   2. results/<stem>__val01_region_area.tsv — one row per leaf atlas-region
 *      annotation (D-04): region_label, hemisphere, acronym, is_leaf,
 *      area_mm2
 * Each individual entry's pair is still a single-run snapshot (truncated
 * fresh each run for that entry), unlike the growing cross-image
 * reference/dapi_region_reference.csv.
 *
 * Downstream: scripts/val01_metrics.py (braian env) reads both TSVs and
 * computes the four VAL-01 bioplausibility metrics. Column names here are
 * the exact contract that script parses against — do not rename without
 * updating both sides. Use scripts/verify_export_integrity.py to check the
 * multi-entry non-clobbering property against a results/ directory.
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

// ── region resolution (CR-01 fix, Phase-4 code review) ──────────────────────────────────────
// Candidate atlas-region annotations = every annotation carrying a region label that is NOT a
// detection container. The OLD "leaf = no annotation children" heuristic was unreliable on the
// real ABBA hierarchy: rollups like `grey` came back child-empty on one hemisphere and so slipped
// in as false leaves, and first-match assignment then let that ~24 mm² rollup absorb ~95k cells
// from their true subfields. Instead we keep ALL regions as candidates and resolve to the finest.
def regionAnnotations = getAnnotationObjects().findAll { ann ->
    def roi = ann.getROI()
    if (roi == null) return false
    if (ann.getChildObjects().any { it.isDetection() }) return false     // skip the detection container(s)
    def lbl = ann.getPathClass()?.toString() ?: ann.getName()
    lbl != null && lbl != "AllDetections"
}
// Pre-sort ascending by ROI area so a short-circuiting `.find` returns the SMALLEST containing
// region (finest/most-specific) without an O(cells×regions) findAll+min blowup on ~200k cells.
def regionAnnotationsByArea = regionAnnotations.toSorted { it.getROI().getArea() }
println "Candidate region annotations for labeling: ${regionAnnotations.size()}"

def regionOf = { detection ->
    def r = detection.getROI()
    double x = r.getCentroidX(), y = r.getCentroidY()
    regionAnnotationsByArea.find { it.getROI().contains(x, y) }          // smallest containing = true leaf
}

// Geometric is_leaf (CR-01 fix): a region is a leaf iff NO smaller region's centroid falls inside
// it — nothing finer is nested within. Topology-independent, so it cannot disagree across
// hemispheres the way the child-annotation heuristic did (which double-counted rollup area in the
// density metric). O(regions²) but short-circuits; fine for the few-hundred atlas annotations.
def isLeafOf = { ann ->
    def roi = ann.getROI()
    double a = roi.getArea()
    !regionAnnotations.any { other ->
        if (other.is(ann)) return false
        def oroi = other.getROI()
        oroi.getArea() < a && roi.contains(oroi.getCentroidX(), oroi.getCentroidY())
    }
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

// ── per-entry output path (EXP-02 fix, D-06/D-07) ───────────────────────────────────────────
// Output filenames MUST be a function of the running project entry, evaluated per-entry INSIDE
// "Run for project" — a fixed filename here means every entry after the first truncates/overwrites
// the previous one's export (RESEARCH Pitfall 5). Sanitization idiom reused verbatim from
// run_braian_detection.groovy lines 79-81 (invalidChars) with the defensive null-fallback from
// export_region_dapi_reference.groovy lines 41-42.
def invalidChars = (['<', '>', ':', '"', '/', '\\', '|', '?', '*'] as Set)
    .collect { java.util.regex.Pattern.quote(it) }.join('|')
def entry = getProjectEntry()
def rawName = (entry != null ? entry.getImageName() : getCurrentImageData().getServer().getMetadata().getName())
def safeName = (rawName != null ? rawName : "").replaceAll(invalidChars, '')
// EXP-02 / WR-03 collision guard: sanitizing the display name can collapse two
// DISTINCT entries onto one stem (e.g. "s1:A" and "s1/A" both -> "s1A"), so the
// second entry's TSV overwrites the first -- exactly the "Run for project"
// clobbering D-06/D-07 was rewritten to eliminate, just re-triggered by a
// sanitization collision instead of a fixed filename. "Run for project" executes
// this script once per entry in SEPARATE runs, so there is no shared in-memory
// set to dedup against, and a filesystem "already exists" check would
// false-positive on a legitimate whole-project re-run. Anchor the stem on the
// project entry's STABLE, UNIQUE id so distinct entries can never share a
// filename; keep the sanitized display name only as a human-readable prefix. The
// id is stable across runs, so each entry still truncates its OWN pair fresh.
def entryId = (entry != null ? entry.getID() : "").replaceAll(invalidChars, '')
def stem = (entryId != null && !entryId.trim().isEmpty()) ? "${safeName}__id${entryId}" : safeName
if (stem == null || stem.trim().isEmpty()) {
    throw new RuntimeException("EXP-02: sanitized entry stem is empty -- refusing to write an unnamed export file (T-05-02-02). Check getProjectEntry().getID()/getImageName() for this entry.")
}

def percellFile = new File(buildPathInProject("results", "${stem}__val01_percell_export.tsv"))
// centroid_*_px are IMAGE-space pixel coordinates (not CCFv3 atlas microns) — the _px suffix keeps
// that explicit per CLAUDE.md's micron-export rule; they are diagnostic only, unused downstream.
def percellHeader = ["class", "region_label", "nucleus_area_um2", "centroid_x_px", "centroid_y_px", "fos_bgsub", "tdt_bgsub"].join("\t")
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

// ── per-region area export (D-04) — iterate the SAME candidate region set used for per-cell
//    labeling; hemisphere/acronym regex-split; is_leaf computed GEOMETRICALLY (isLeafOf, CR-01
//    fix) instead of the unreliable child-annotation-emptiness heuristic. ─────────────────────
def regionRows = []
regionAnnotations.each { ann ->
    def roi = ann.getROI()
    def label = ann.getPathClass()?.toString() ?: ann.getName()
    def isLeaf = isLeafOf(ann)
    def hemisphere = ""; def acronym = label
    def m = (label =~ /(?i)^(Left|Right):\s*(.+)$/)
    if (m.find()) { hemisphere = m.group(1); acronym = m.group(2) }
    def areaMm2 = roi.getArea() * pxToMm2
    if (areaMm2 <= 0) return
    regionRows << [label, hemisphere, acronym, isLeaf, areaMm2]
}

def regionFile = new File(buildPathInProject("results", "${stem}__val01_region_area.tsv"))
def regionHeader = ["region_label", "hemisphere", "acronym", "is_leaf", "area_mm2"].join("\t")
def regionSb = new StringBuilder()
regionSb.append(regionHeader).append("\n")
regionRows.each { row ->
    regionSb.append(String.format('%s\t%s\t%s\t%s\t%.6f%n', row[0], row[1], row[2], row[3], row[4]))
}
regionFile.text = regionSb.toString()
println "Wrote ${regionRows.size()} per-region area rows -> ${regionFile}"

println "VAL-01 export complete: ${percellFile.name} (${percellRows.size()} cells), ${regionFile.name} (${regionRows.size()} regions)."
