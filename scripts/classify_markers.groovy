/**
 * classify_markers.groovy — nucleus-anchored Fos/TdT/Double classification
 *
 * WHY: BraiAnDetect's config-driven classifier list (BraiAn.yml `classifiers:`) can only
 * apply ONE classifier per detection entry, and it must output [<entry>, Other: <entry>]
 * (AbstractDetections.applyClassifiers, v1.1.0). It cannot classify one DAPI detection set
 * by TWO independent markers (the research A3 risk). Its multi-marker path is per-channel
 * detection + OverlappingDetections — which CLAUDE.md forbids (nucleus-anchored only).
 *
 * So we detect with BraiAnDetect (DAPI-T4) and classify HERE, directly on each nucleus:
 *   Fos+  iff  (Nucleus:  AF488-T3 mean) >= Fos threshold      (nuclear compartment)
 *   TdT+  iff  (Cytoplasm: AF568-T2 mean) >= TdT threshold      (cytoplasmic ring)
 * Compound class per nucleus: Double+ / Fos+ / TdT+ / Negative. No proximity/overlap.
 *
 * Thresholds are read at runtime from the classifier JSONs, so this stays correct after
 * the D-02 re-derivation writes the locked cutoffs into those files.
 *
 * Run AFTER a BraiAnDetect detection pass. Sets visible classes (for CLASS-01 overlay)
 * and prints per-class counts + the advisory Double+/TdT+ ratio.
 *
 * @author section-pipeline
 */
import com.google.gson.JsonParser
import static qupath.lib.scripting.QP.*

def base = new File(getProject().getBaseDirectory(), "classifiers/object_classifiers")
def readSpec = { fn ->
    def o = JsonParser.parseString(new File(base, fn).text).getAsJsonObject().getAsJsonObject("function")
    [meas: o.get("measurement").getAsString(), thr: o.get("threshold").getAsDouble()]
}
def fos = readSpec("Fos_Classifier_20x.json")
def tdt = readSpec("TdT_classifier.json")
println "Fos rule: ${fos.meas} >= ${fos.thr}"
println "TdT rule: ${tdt.meas} >= ${tdt.thr}"

def dets = getDetectionObjects()
if (dets.isEmpty()) { println "No detections — run BraiAnDetect first. Aborting."; return }

int cFos = 0, cTdt = 0, cDbl = 0, cNeg = 0
dets.each { d ->
    def vf = d.getMeasurements().get(fos.meas)
    def vt = d.getMeasurements().get(tdt.meas)
    boolean isF = vf != null && !Double.isNaN(vf.doubleValue()) && vf.doubleValue() >= fos.thr
    boolean isT = vt != null && !Double.isNaN(vt.doubleValue()) && vt.doubleValue() >= tdt.thr
    def cls = (isF && isT) ? "Double+" : isF ? "Fos+" : isT ? "TdT+" : "Negative"
    d.setPathClass(getPathClass(cls))
    if (cls == "Double+") cDbl++ else if (cls == "Fos+") cFos++ else if (cls == "TdT+") cTdt++ else cNeg++
}
fireHierarchyUpdate()

int n = dets.size()
def pct = { c -> 100.0 * c / n }
println "Classified ${n} nuclei (nucleus-anchored, no overlap):"
println String.format("  Negative : %d (%.1f%%)", cNeg, pct(cNeg))
println String.format("  Fos+ only: %d (%.1f%%)", cFos, pct(cFos))
println String.format("  TdT+ only: %d (%.1f%%)", cTdt, pct(cTdt))
println String.format("  Double+  : %d (%.1f%%)", cDbl, pct(cDbl))
println String.format("  => Total Fos+ (incl. Double+): %d (%.1f%%)", cFos + cDbl, pct(cFos + cDbl))
println String.format("  => Total TdT+ (incl. Double+): %d (%.1f%%)", cTdt + cDbl, pct(cTdt + cDbl))
def denom = cTdt + cDbl
println String.format("  Advisory Double+/TdT+ ratio: %s",
        denom > 0 ? String.format("%.3f", (double) cDbl / denom) : "n/a")
