/**
 * inspect_marker_band.groovy -- make a threshold decision VISIBLE.
 *
 * Tags the detections whose background-subtracted measure for one marker falls
 * between two thresholds, so the cells that a `k_robust` change would flip can be
 * looked at directly instead of being argued about from summary counts.
 *
 * The problem this solves: lowering k for a marker adds cells. The counts tell you
 * HOW MANY, never WHICH. On M3 Hipp2 s3, TdT k 3.0 -> 2.0 added 7,313 cells and the
 * reactivation rate of that added set (18.4% Fos+) sat between the original set
 * (35.8%) and chance (11.2%) -- consistent EITHER with dimmer real engram cells or
 * with a large false-positive tail. Summary numbers cannot separate those. Looking
 * at the cells can (CLAUDE.md evidence hierarchy: SEEN outranks inferred).
 *
 * NON-DESTRUCTIVE: tags with a DERIVED class ("Fos+: InspectBand"), so the existing
 * call is preserved and still visible. It never re-runs detection, never re-derives a
 * threshold, and never writes a config. Measurements are never touched, so
 * 02_detect_classify.groovy restores a pristine classification at any time.
 *
 * HISTORY: the first version called setPathClass() outright, replacing the class.
 * Run across a whole project (2026-07-31) that wiped Fos+/Double+ on every cell in
 * the band and presented as a real drop in Fos. Exports were unaffected (they
 * predated it) but the scare was real. A diagnostic must never be mistakable for a
 * finding.
 *
 * Usage: edit MARKER / LOW / HIGH below, run on ONE image, then in QuPath's
 * Annotations pane show only the "InspectBand" class and zoom in.
 *
 * @author section-pipeline
 */

import qupath.lib.objects.classes.PathClassFactory

// ── EDIT THESE ──────────────────────────────────────────────────────────────
// Marker name as declared in pipeline.yml (e.g. "TdT", "Fos").
String MARKER = "TdT"
// The band to inspect. Defaults below are the M3 Hipp2 s3 TdT k=3.0 -> k=2.0 band:
// cells in here were Negative at k=3.0 and became TdT+ at k=2.0.
double LOW  = 327.09
double HIGH = 494.50
// ────────────────────────────────────────────────────────────────────────────

def project = getProject()
if (project == null) { println "ERROR: no project open."; return }

// Resolve the marker's compartment from pipeline.yml so the measurement key is
// never hardcoded -- the same config-driven rule the classify stage follows.
def ymlFile = new File(project.getBaseDirectory(), "pipeline.yml")
if (!ymlFile.exists()) { println "ERROR: no pipeline.yml in ${project.getBaseDirectory()}"; return }

String channel = null, compartment = null
boolean inMarkers = false
String currentName = null
ymlFile.eachLine { line ->
    def t = line.trim()
    if (t.startsWith("markers:")) { inMarkers = true; return }
    if (inMarkers && !line.startsWith(" ") && !t.isEmpty() && !t.startsWith("#")) { inMarkers = false }
    if (!inMarkers) return
    def mNew = (t =~ /^-\s*name:\s*"([^"]+)"/)
    if (mNew.find()) { currentName = mNew.group(1); return }
    if (currentName != MARKER) return
    def mChan = (t =~ /^channel:\s*"([^"]+)"/)
    def mComp = (t =~ /^compartment:\s*"([^"]+)"/)
    if (mChan.find()) channel = mChan.group(1)
    if (mComp.find()) compartment = mComp.group(1)
}

if (channel == null || compartment == null) {
    println "ERROR: marker '${MARKER}' not found in pipeline.yml (or missing channel/compartment)."
    return
}

def COMPARTMENT_LABELS = ["nuclear": "Nucleus", "cytoplasmic": "Cytoplasm", "whole-cell": "Cell"]
String label = COMPARTMENT_LABELS[compartment]
if (label == null) { println "ERROR: unknown compartment '${compartment}' for ${MARKER}."; return }
String key = "${label}: ${channel} mean (bg-sub)"

println "Inspecting ${MARKER}  (${compartment} -> '${key}')"
println "  band: ${LOW} < value <= ${HIGH}"

def detections = getDetectionObjects()
if (detections.isEmpty()) { println "ERROR: no detections -- run detection first."; return }

// Tag with a DERIVED class ("Fos+: InspectBand") rather than replacing the class.
// An earlier version called setPathClass() outright, which DESTROYED the existing
// call -- run across a whole project it silently wiped Fos+/Double+ labels on every
// cell in the band and looked exactly like a real drop in Fos (2026-07-31). A
// diagnostic must never be able to be mistaken for a finding.
int tagged = 0, missing = 0
detections.each { d ->
    def v = d.getMeasurements().get(key)
    if (v == null) { missing++; return }
    double val = v.doubleValue()
    if (!Double.isNaN(val) && val > LOW && val <= HIGH) {
        def existing = d.getPathClass()
        d.setPathClass(existing == null
                ? PathClassFactory.getPathClass("InspectBand")
                : PathClassFactory.getDerivedPathClass(existing, "InspectBand", null))
        tagged++
    }
}
fireHierarchyUpdate()

println "  ${tagged} detection(s) tagged 'InspectBand' out of ${detections.size()}"
if (missing > 0) {
    println "  WARNING: ${missing} detection(s) had no '${key}' measurement -- run 02_detect_classify.groovy first."
}
println ""
println "NEXT: in the Annotations pane show ONLY 'InspectBand', then zoom into a field you"
println "have NOT already inspected -- judging on the field that prompted the change confirms"
println "the hypothesis on its own evidence."
println "  * mostly real cells you can see are marker+  -> the lower k is right"
println "  * mostly bystander nuclei under passing axons -> try cellExpansionMicrons DOWN"
println "    rather than k back up; that targets axon contamination specifically."
println ""
println "Re-run 02_detect_classify.groovy afterwards to restore the real classification."
