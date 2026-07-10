/**
 * 02_detect_classify.groovy — classify/label/report entry point (SCRI-03)
 *
 * SCOPE (D-01): This script does NOT detect. Detection stays in
 * run_braian_detection.groovy — that is the standalone, CPU-heavy BraiAnDetect
 * pass. This numbered script assumes detections already exist on the current
 * entry and performs classification + atlas region labeling + reporting only.
 * Keeping detection out of this script lets the fast threshold-iteration loop
 * re-run without re-detecting.
 *
 * GUARD + IDEMPOTENCY (D-02): if the current entry has zero detections, this
 * script aborts cleanly with a clear message telling the user to run
 * run_braian_detection.groovy first. If detections exist, they are
 * (re)classified in place — setPathClass overwrites, so re-running just
 * refreshes classes; safe to re-run freely during threshold tuning. Under
 * "Run for project", any entry other than the registered/detected entry
 * (M3 062926 3 plane, entry 1) simply aborts cleanly rather than erroring
 * the batch.
 *
 * CLASSIFICATION (nucleus-anchored, no proximity/overlap — CLAUDE.md, locked):
 *   Fos+  iff  (Nucleus:  AF488-T3 mean) >= Fos threshold   (nuclear compartment)
 *   TdT+  iff  (Cytoplasm: AF568-T2 mean) >= TdT threshold   (cytoplasmic ring)
 * Compound class per nucleus: Double+ / Fos+ / TdT+ / Negative. This is the
 * exact classify_markers.groovy core (base for this script) — reused verbatim,
 * NOT BraiAn.yml's classifiers:/OverlappingDetections path (Deviation #1,
 * forbidden: that path cannot classify one DAPI detection set by two
 * independent markers without proximity/overlap heuristics).
 *
 * EXCLUSIONS: detections whose centroid falls in an excluded region (DG-sg +
 * ventricular systems VS) are set to "Excluded" and NOT marker-classified.
 * Locked in Phase 2 — not a Phase-3 decision; EXCLUDE_ACRONYMS unchanged.
 *
 * ATLAS REGION LABEL (SC2): each classified cell resolves to its ABBA
 * leaf-region label via the SAME centroid-in-ROI containment idiom used for
 * exclusions. Region membership is recomputed EPHEMERALLY per run via the
 * regionOf closure — never persisted as per-cell String metadata. QuPath
 * 0.6.0 javadoc warns storing metadata on plentiful objects (detections) is
 * memory-inefficient, and MeasurementList is numeric-only by design (cannot
 * hold a region acronym string). See regionOf below.
 *
 * Thresholds are read at runtime from the classifier JSONs (Fos_Classifier_20x.json,
 * TdT_classifier.json), so this stays correct after future threshold edits.
 * Run AFTER a BraiAnDetect detection pass.
 *
 * @author section-pipeline
 */
import com.google.gson.JsonParser
import qupath.ext.biop.abba.AtlasTools
import net.imglib2.RealPoint
import static qupath.lib.scripting.QP.*

// ── Entry confirmation ──────────────────────────────────────────────────────
// Print entry name to catch wrong-entry errors (guards against running on the
// wrong project entry under "Run for project").
println "Running on: " + getCurrentImageData().getServer().getMetadata().getName()

// ── excluded regions (Allen acronyms; parent ROI covers its subfields) ──────
def EXCLUDE_ACRONYMS = ["DG-sg", "VS"] as Set   // DG granule cell layer (too dense) + ventricular systems. (DG-mo/DG-po stay in.)

// ── runtime classifier-JSON threshold read (Gson; no groovy.json in QuPath) ─
def base = new File(getProject().getBaseDirectory(), "classifiers/object_classifiers")
def readSpec = { fn ->
    def o = JsonParser.parseString(new File(base, fn).text).getAsJsonObject().getAsJsonObject("function")
    [meas: o.get("measurement").getAsString(), thr: o.get("threshold").getAsDouble()]
}
def fos = readSpec("Fos_Classifier_20x.json")
def tdt = readSpec("TdT_classifier.json")
println "Fos rule: ${fos.meas} >= ${fos.thr}"
println "TdT rule: ${tdt.meas} >= ${tdt.thr}"

// build exclusion ROIs (parent region annotations whose acronym is in EXCLUDE_ACRONYMS)
def excludeRois = []
getAnnotationObjects().each { ann ->
    def label = ann.getPathClass()?.toString() ?: ann.getName()
    if (label == null || ann.getROI() == null) return
    def m = (label =~ /(?i)^(?:Left|Right):\s*(.+)$/)
    def acr = m.find() ? m.group(1) : label
    if (EXCLUDE_ACRONYMS.contains(acr)) excludeRois << ann.getROI()
}
println "Exclusion regions (${EXCLUDE_ACRONYMS}): ${excludeRois.size()} annotation ROI(s)"

// ── D-02 zero-detection guard ────────────────────────────────────────────────
def dets = getDetectionObjects()
if (dets.isEmpty()) { println "No detections — run BraiAnDetect first. Aborting."; return }

// ── compound classification core (nucleus-anchored, no proximity/overlap) ───
int cFos = 0, cTdt = 0, cDbl = 0, cNeg = 0, cExc = 0
dets.each { d ->
    def r = d.getROI()
    double x = r.getCentroidX(), y = r.getCentroidY()
    if (excludeRois.any { it.contains(x, y) }) {
        d.setPathClass(getPathClass("Excluded")); cExc++; return
    }
    def vf = d.getMeasurements().get(fos.meas)
    def vt = d.getMeasurements().get(tdt.meas)
    boolean isF = vf != null && !Double.isNaN(vf.doubleValue()) && vf.doubleValue() >= fos.thr
    boolean isT = vt != null && !Double.isNaN(vt.doubleValue()) && vt.doubleValue() >= tdt.thr
    def cls = (isF && isT) ? "Double+" : isF ? "Fos+" : isT ? "TdT+" : "Negative"
    d.setPathClass(getPathClass(cls))
    if (cls == "Double+") cDbl++ else if (cls == "Fos+") cFos++ else if (cls == "TdT+") cTdt++ else cNeg++
}
fireHierarchyUpdate()

// ── class-breakdown console print ────────────────────────────────────────────
int n = dets.size()
int classified = n - cExc
def pct = { c -> classified > 0 ? 100.0 * c / classified : 0.0 }   // % of CLASSIFIED (non-excluded) nuclei
println "Total nuclei: ${n}  |  Excluded (DG/ventricles): ${cExc}  |  Classified: ${classified}"
println String.format("  Negative : %d (%.1f%%)", cNeg, pct(cNeg))
println String.format("  Fos+ only: %d (%.1f%%)", cFos, pct(cFos))
println String.format("  TdT+ only: %d (%.1f%%)", cTdt, pct(cTdt))
println String.format("  Double+  : %d (%.1f%%)", cDbl, pct(cDbl))
println String.format("  => Total Fos+ (incl. Double+): %d (%.1f%%)", cFos + cDbl, pct(cFos + cDbl))
println String.format("  => Total TdT+ (incl. Double+): %d (%.1f%%)", cTdt + cDbl, pct(cTdt + cDbl))
def denom = cTdt + cDbl
println String.format("  Advisory Double+/TdT+ ratio: %s",
        denom > 0 ? String.format("%.3f", (double) cDbl / denom) : "n/a")

// ── SC2: atlas region label per cell (ephemeral centroid-in-ROI lookup) ─────
// Leaf region annotations only: an ABBA/Allen annotation with no annotation
// children (parent regions like "HPF" are excluded so cells resolve to their
// most specific subfield, e.g. CA1/CA1sp/DG-mo).
def regionAnnotations = getAnnotationObjects().findAll { ann ->
    def roi = ann.getROI()
    roi != null && !ann.getChildObjects().any { it.isAnnotation() }
}
println "Leaf region annotations available for labeling: ${regionAnnotations.size()}"

// regionOf: for a detection, returns the leaf annotation whose ROI contains
// the detection's centroid. Recomputed on demand every call — NOT stored on
// the detection object (Pitfall 4: metadata is memory-inefficient at
// 10^4-10^5 detections; Pitfall 5: MeasurementList is numeric-only, cannot
// hold a region acronym string). Region labels stay computed-on-demand.
def regionOf = { detection ->
    def r = detection.getROI()
    double x = r.getCentroidX(), y = r.getCentroidY()
    regionAnnotations.find { it.getROI().contains(x, y) }
}

// regionLabel: normalize a resolved region annotation to a bare acronym,
// stripping the Left/Right hemisphere prefix (same normalization already
// applied to the exclusion-region label above).
def regionLabel = { region ->
    if (region == null) return "(no region)"
    def label = region.getPathClass()?.toString() ?: region.getName()
    if (label == null) return "(no region)"
    def m = (label =~ /(?i)^(?:Left|Right):\s*(.+)$/)
    return m.find() ? m.group(1) : label
}

// Sample println for the first 5 classified cells: cell centroid -> resolved
// region acronym, proving SC2's per-cell region association exists.
println "Sample cell -> atlas region (first 5 classified cells):"
dets.take(5).each { d ->
    def r = d.getROI()
    def region = regionOf(d)
    println "  Cell at (${r.getCentroidX()}, ${r.getCentroidY()}) [${d.getPathClass()}] -> ${regionLabel(region)}"
}

// Diagnostic-only probe of the BraiAnDetect container-nesting hypothesis (A2):
// does detection.getParent().getParent() already resolve to the containing
// ABBA region annotation? The implementation above does NOT depend on the
// answer either way — the centroid-in-ROI path (regionOf) is authoritative
// regardless. This println is purely informational.
if (!dets.isEmpty()) {
    def sample = dets[0]
    println "Diagnostic (A2, not depended on): sample cell parent.parent.pathClass = " +
            "${sample.getParent()?.getParent()?.getPathClass()}"
}

// ── SC4: per-region per-class count rollup onto annotation measurements ────
// Rolls per-class counts UP onto each leaf region annotation (CA1/CA2/CA3/
// DG-mo/DG-po/DG-sg/... ) as numeric MeasurementList entries so they render
// natively in QuPath's annotation-pane measurement table (RESEARCH Pattern 4).
// Counted via the SAME centroid-in-ROI containment idiom as regionOf/exclusion
// above (qc_detection_gates.groovy template) — NOT by reading the pre-existing
// results/<image>_regions.tsv on disk, which reflects BraiAnDetect's own
// (incompatible, Deviation #1) classifier application and predates this
// script's Double+/Fos+/TdT+/Negative ground truth (RESEARCH Pitfall 1).
def ROLLUP_CLASSES = ["Negative", "Fos+", "TdT+", "Double+", "Excluded"]
println "Per-region class count rollup (Count: <class> written onto each leaf region annotation):"
regionAnnotations.each { ann ->
    def roi = ann.getROI()
    def counts = ROLLUP_CLASSES.collectEntries { [(it): 0] }
    dets.each { d ->
        def r = d.getROI()
        if (roi.contains(r.getCentroidX(), r.getCentroidY())) {
            def cls = d.getPathClass()?.toString() ?: "Negative"
            counts[cls] = (counts[cls] ?: 0) + 1
        }
    }
    def ml = ann.getMeasurementList()
    counts.each { cls, n -> ml.put("Count: ${cls}", n as double) }
    println "  ${regionLabel(ann)}: " + ROLLUP_CLASSES.collect { "${it}=${counts[it]}" }.join(", ")
}
fireHierarchyUpdate()

// ── SC3: Atlas_X micron sanity print (lightweight, NOT a per-cell export) ──
// Confirms the ABBA-registered CCFv3 coordinate for a handful of classified
// cells falls in the 5,000-10,000 µm range (proves µm units, not mm or a raw
// atlas voxel index). This is a sanity check only, not the full per-cell
// Atlas_X/Y/Z export column (that is v2 EXP-01/EXP-03 — Claude's-Discretion,
// 03-CONTEXT.md). Pattern 5 (RESEARCH.md): AtlasTools.getAtlasToPixelTransform
// is the official BIOP/ABBA-author pattern, cross-verified against the
// installed qupath-extension-abba-0.4.0.jar + bundled imglib2-realtransform.
println "Atlas_X sanity print (sample of classified cells, expect Atlas_X in [5000, 10000] µm per SC3):"
def imageData = getCurrentImageData()
def pixelToAtlasTransform = null
try {
    pixelToAtlasTransform = AtlasTools.getAtlasToPixelTransform(imageData)?.inverse()
} catch (Exception e) {
    println "  Could not obtain atlas<->pixel transform (${e.class.simpleName}: ${e.message}) — skipping Atlas_X sanity print."
}
if (pixelToAtlasTransform == null) {
    println "  No ABBA registration transform available on this entry — skipping Atlas_X sanity print."
} else {
    def sample = dets.findAll { it.getPathClass()?.toString() in ["Fos+", "TdT+", "Double+"] }.take(5)
    if (sample.isEmpty()) {
        println "  No Fos+/TdT+/Double+ classified cells to sample from."
    }
    sample.each { d ->
        def r = d.getROI()
        def point = new RealPoint(3)
        point.setPosition([r.getCentroidX(), r.getCentroidY(), 0d] as double[])
        pixelToAtlasTransform.apply(point, point)   // in-place: same RealPoint as source and target
        println "  [${d.getPathClass()}] Atlas_X=${point.getDoublePosition(0)}  Atlas_Y=${point.getDoublePosition(1)}  Atlas_Z=${point.getDoublePosition(2)}"
    }
    // Documented ×10 voxel-index fallback (RESEARCH Pitfall 10 / Assumption A3):
    // if the printed Atlas_X values look like voxel indices (~500-1000) rather
    // than microns (~5000-10000), the allen_mouse_10um_java atlas is 10 µm/voxel
    // -- multiply the printed values by 10 by hand and re-check against SC3's
    // range. No unit conversion is hard-coded here; SC3 itself is the
    // print-and-inspect verification of this open unit question.
    println "  NOTE: if the values above look like ~500-1000 (voxel indices) rather than"
    println "  ~5000-10000 (µm), the allen_mouse_10um_java atlas is 10 µm/voxel -- multiply"
    println "  by 10 and re-check against the SC3 target range. Do not hard-code this; it is"
    println "  an empirical print-and-check gate (RESEARCH Pitfall 10 / A3)."
}
