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
 * Thresholds are read at runtime from the classifier JSONs (Fos_Classifier_20x.json,
 * TdT_classifier.json), so this stays correct after future threshold edits.
 * Run AFTER a BraiAnDetect detection pass.
 *
 * @author section-pipeline
 */
import com.google.gson.JsonParser
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
