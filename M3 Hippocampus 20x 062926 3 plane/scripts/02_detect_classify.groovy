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
 *   Fos+  iff  (Nucleus:  AF488-T3 mean (bg-sub)) >= Fos threshold   (nuclear compartment)
 *   TdT+  iff  (Cytoplasm: AF568-T2 mean (bg-sub)) >= TdT threshold   (cytoplasmic ring)
 * Compound class per nucleus: Double+ / Fos+ / TdT+ / Negative. This is the
 * exact classify_markers.groovy core (base for this script) — reused verbatim,
 * NOT BraiAn.yml's classifiers:/OverlappingDetections path (Deviation #1,
 * forbidden: that path cannot classify one DAPI detection set by two
 * independent markers without proximity/overlap heuristics).
 *
 * D-03/D-05: classification reads the (bg-sub) measure (D-04 above) against
 * thresholds RE-DERIVED on that measure via qupath.ext.braian.ChannelHistogram
 * peak-finding (Pattern 2) -- NOT the old absolute cutoffs (Fos 13000.4538 /
 * TdT 16766.4671, Fos_Classifier_20x.json / TdT_classifier.json). Those two
 * JSONs and their thresholds are SUPERSEDED for classification and retained
 * only as a documented reference point / self-check anchor (see below). The
 * operative bg-sub thresholds live in Fos_Classifier_20x_bgsub.json /
 * TdT_classifier_bgsub.json, which this script re-derives and overwrites on
 * every run (Pitfall 9: do not let the old absolute cutoffs leak back in
 * against the new measure).
 *
 * EXCLUSIONS: detections whose centroid falls in an excluded region (DG-sg +
 * ventricular systems VS) are set to "Excluded" and NOT marker-classified.
 * Locked in Phase 2 — not a Phase-3 decision; EXCLUDE_ACRONYMS unchanged.
 *
 * BACKGROUND-ROBUST MEASURE (D-04): before classification, every detection
 * gains a compartment-agnostic local-background-subtracted measurement for
 * each marker -- "Nucleus: AF488-T3 mean (bg-sub)" (Fos, ring built outside
 * the nucleus ROI) and "Cytoplasm: AF568-T2 mean (bg-sub)" (TdT, ring built
 * outside the expanded cell/cytoplasm ROI). This fixes Phase 2's Deviation #2
 * SSp-autofluorescence false-positive bug without introducing a
 * nucleus:cytoplasm contrast ratio (that alternative is forbidden by D-04 --
 * it does not generalize to a future PNN pericellular-annulus compartment).
 * See localBackgroundSubtractedMean below.
 *
 * ATLAS REGION LABEL (SC2): each classified cell resolves to its ABBA
 * leaf-region label via the SAME centroid-in-ROI containment idiom used for
 * exclusions. Region membership is recomputed EPHEMERALLY per run via the
 * regionOf closure — never persisted as per-cell String metadata. QuPath
 * 0.6.0 javadoc warns storing metadata on plentiful objects (detections) is
 * memory-inefficient, and MeasurementList is numeric-only by design (cannot
 * hold a region acronym string). See regionOf below.
 *
 * Thresholds are read at runtime from the bg-sub classifier JSONs
 * (Fos_Classifier_20x_bgsub.json, TdT_classifier_bgsub.json), which this
 * script itself (re-)derives and writes each run (D-05), so this stays
 * correct after future re-derivation without a separate edit step.
 * Run AFTER a BraiAnDetect detection pass.
 *
 * @author section-pipeline
 */
import com.google.gson.JsonParser
import qupath.ext.biop.abba.AtlasTools
import net.imglib2.RealPoint
import qupath.lib.roi.RoiTools
import qupath.lib.objects.PathObjects
import qupath.lib.analysis.features.ObjectMeasurements
import qupath.lib.analysis.features.ObjectMeasurements.Measurements
import qupath.lib.analysis.features.ObjectMeasurements.Compartments
import qupath.lib.regions.ImageRegion
import qupath.ext.braian.ChannelHistogram
import com.google.gson.JsonObject
import com.google.gson.JsonArray
import com.google.gson.GsonBuilder
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

// ── image/server/hierarchy handles (shared: bg-sub pass, threshold re-derivation, Atlas_X) ──
def imageData = getCurrentImageData()
def server = imageData.getServer()
def hierarchy = imageData.getHierarchy()

// ── D-04 / Pattern 1: compartment-agnostic local-background-subtracted measure ──
// Resolve pixel size (µm/px) the same fallback way as qc_detection_gates.groovy:
// prefer the image server's own calibration (matches OME-XML PhysicalSizeX),
// fall back to the known entry-1 value only if the server exposes none.
def FALLBACK_PIXEL_SIZE_UM = 0.6905355   // server.json PhysicalSizeX, M3 062926 3 plane entry 1
def cal = server.getPixelCalibration()
def pixelUm = FALLBACK_PIXEL_SIZE_UM
if (cal != null && cal.hasPixelSizeMicrons()) {
    pixelUm = cal.getAveragedPixelSizeMicrons()
    println "Pixel size read from image server: ${pixelUm} µm/px"
} else {
    println "WARNING: image server has no pixel calibration -- falling back to hard-coded ${FALLBACK_PIXEL_SIZE_UM} µm/px (server.json PhysicalSizeX)"
}

// Ring-geometry seed constants (µm) -- [ASSUMED] starting point (Assumption A4),
// tune visually on DG like Phase 2's cellExpansionMicrons; ring must not eat
// into the cell's own compartment. Buffer distances are in PIXELS (Pitfall 2),
// so convert before use.
double GAP_UM = 1.0
double RING_WIDTH_UM = 8.0
double gapPx = GAP_UM / pixelUm
double outerPx = (GAP_UM + RING_WIDTH_UM) / pixelUm

// A5 guard: print the throwaway measurement object's key set exactly once, so
// the "Cell: <channel> mean" key name assumption is confirmed before the loop
// trusts it on every detection.
boolean bgKeySetPrinted = false
// D-04 robustness: JTS OverlayNG can throw "side location conflict" (a geometry
// robustness failure) on a small number of pathological detection ROIs during the
// annulus subtract. One bad cell must NOT abort the full detection batch, so the
// closure below catches it and returns NaN for that cell (which falls conservatively
// to Negative in classification); the total skipped count is reported after the loop.
int bgGeomFailures = 0

/**
 * Returns the local-background-subtracted mean intensity for channelName in
 * an annulus built immediately outside baseRoi (compartment-agnostic: caller
 * passes the nucleus ROI for Fos, the expanded cell/cytoplasm ROI for TdT --
 * Pitfall 3). Neighboring detections are excluded from the annulus via exact
 * geometric subtraction, using a bounding-box "quick check" neighbor query
 * (getAllObjectsForRegion, NOT the centroid-only getAllObjectsForROI --
 * Pitfall 8) to avoid missing neighbors whose centroid sits outside the ring
 * but whose body intrudes into it. Uses ObjectMeasurements (the same class
 * QuPath's own Nucleus/Cytoplasm measurements are built with) on a throwaway
 * detection object that is never added to the hierarchy -- Don't Hand-Roll.
 */
def localBackgroundSubtractedMean = { baseRoi, String channelName, selfDetection ->
    try {
        def innerRoi = RoiTools.buffer(baseRoi, gapPx)
        def outerRoi = RoiTools.buffer(baseRoi, outerPx)
        def annulusRoi = RoiTools.subtract(outerRoi, innerRoi)

        def region = ImageRegion.createInstance(annulusRoi)
        def neighborRois = hierarchy.getAllObjectsForRegion(region)
                .findAll { it.isDetection() && it != selfDetection }
                .collect { it.getROI() }
                .findAll { it != null }
        def cleanAnnulus = neighborRois.isEmpty() ? annulusRoi : RoiTools.subtract(annulusRoi, neighborRois)

        def tempObj = PathObjects.createDetectionObject(cleanAnnulus)
        ObjectMeasurements.addIntensityMeasurements(server, tempObj, 1.0,
                [Measurements.MEAN], [Compartments.CELL])
        if (!bgKeySetPrinted) {
            println "A5 self-check: throwaway measurement object key set = ${tempObj.getMeasurements().keySet()}"
            bgKeySetPrinted = true
        }
        def key = "Cell: ${channelName} mean"
        def v = tempObj.getMeasurements().get(key)
        return (v == null || Double.isNaN(v.doubleValue())) ? Double.NaN : v.doubleValue()
    } catch (Throwable t) {
        // JTS "side location conflict" & kin: geometry robustness failure on this
        // cell's annulus. Skip local-bg for it rather than aborting the whole batch.
        bgGeomFailures++
        return Double.NaN
    }
}

println "Computing local-background-subtracted measures (D-04) for ${dets.size()} detections..."
int bgProcessed = 0
dets.each { d ->
    // Fos ring anchors OUTSIDE the nucleus ROI; TdT ring anchors OUTSIDE the
    // expanded cell/cytoplasm ROI -- distinct per-marker anchors (Pitfall 3).
    def nucleusRoi = (d.respondsTo('getNucleusROI') && d.getNucleusROI() != null) ? d.getNucleusROI() : d.getROI()
    def cellRoi = d.getROI()

    def rawFosM = d.getMeasurements().get("Nucleus: AF488-T3 mean")
    double rawFos = rawFosM != null ? rawFosM.doubleValue() : Double.NaN
    double bgFos = localBackgroundSubtractedMean(nucleusRoi, "AF488-T3", d)

    def rawTdtM = d.getMeasurements().get("Cytoplasm: AF568-T2 mean")
    double rawTdt = rawTdtM != null ? rawTdtM.doubleValue() : Double.NaN
    double bgTdt = localBackgroundSubtractedMean(cellRoi, "AF568-T2", d)

    d.getMeasurementList().put("Nucleus: AF488-T3 mean (bg-sub)", rawFos - bgFos)
    d.getMeasurementList().put("Cytoplasm: AF568-T2 mean (bg-sub)", rawTdt - bgTdt)

    bgProcessed++
    if (bgProcessed % 1000 == 0) println "  ...background-subtracted ${bgProcessed}/${dets.size()} detections"
}
fireHierarchyUpdate()
if (bgGeomFailures > 0)
    println "  NOTE: ${bgGeomFailures}/${dets.size()} detections hit a geometry-robustness failure in the local-bg annulus and were assigned NaN bg-sub (→ Negative). Negligible if small; investigate if large."
println "Background-subtracted measures written for ${dets.size()} detections (D-04)."

// ── isExcluded: shared centroid-in-excludeRois test (reused by threshold ───
// derivation population below AND the classification loop, replacing the
// previously-inlined check with a single named closure).
def isExcluded = { detection ->
    def r = detection.getROI()
    double x = r.getCentroidX(), y = r.getCentroidY()
    excludeRois.any { it.contains(x, y) }
}

// ── D-05 / Pattern 2: re-derive positive thresholds on the bg-sub measure ──
// Reuses qupath.ext.braian.ChannelHistogram.findPeaks/zeroPhaseFilter -- the
// exact histogram-peak-finding primitives already locked into BraiAn.yml's
// D-01 detection threshold -- applied here to a self-built histogram of the
// per-cell (bg-sub) measurement rather than a raw image channel histogram.
def classifiable = dets.findAll { !isExcluded(it) }   // Pitfall 6: exclude DG-sg/VS from the derivation population
println "Threshold derivation population (excluding DG-sg/VS): ${classifiable.size()} / ${dets.size()} detections"

double BIN_WIDTH = 50.0                    // seed bin width for the self-built histogram
double[] SMOOTH_KERNEL = [1, 2, 3, 2, 1] as double[]   // example smoothing kernel (RESEARCH Pattern 2)
double PEAK_PROMINENCE = 500               // same D-01 seed value locked in BraiAn.yml
int N_PEAK = 2                             // same locked semantic as BraiAn.yml's nPeak: 2 (skip background peak)

/** Bins values into a histogram, smooths + finds peaks via ChannelHistogram, returns the nPeak-th peak's bin-center threshold (or NaN if no data/peaks). */
def derivePeakThreshold = { List<Double> values, double binWidth, double[] kernel, double peakProminence, int nPeak ->
    if (values == null || values.isEmpty()) return Double.NaN
    double minV = values.min(), maxV = values.max()
    if (!(maxV > minV)) return Double.NaN
    int nBins = Math.max(1, Math.ceil((maxV - minV) / binWidth) as int)
    double[] hist = new double[nBins + 1]
    values.each { v ->
        int idx = Math.min(nBins, (int) ((v - minV) / binWidth))
        hist[idx]++
    }
    def smoothed = ChannelHistogram.zeroPhaseFilter(hist, kernel)
    int[] peakIndices = ChannelHistogram.findPeaks(smoothed, peakProminence)
    if (peakIndices.length == 0) return Double.NaN
    int pick = Math.min(nPeak - 1, peakIndices.length - 1)
    return minV + peakIndices[pick] * binWidth
}

// Mandatory self-check (RESEARCH Open Question 1): re-derive on the EXISTING
// raw measures first and compare to the already-locked absolute thresholds --
// validates the histogram-kernel/window semantics transfer to a measurement
// histogram before trusting the bg-sub-measure re-derivation below.
def rawFosValues = classifiable.collect { it.getMeasurements().get("Nucleus: AF488-T3 mean")?.doubleValue() }.findAll { it != null && !Double.isNaN(it) }
def rawTdtValues = classifiable.collect { it.getMeasurements().get("Cytoplasm: AF568-T2 mean")?.doubleValue() }.findAll { it != null && !Double.isNaN(it) }
double rawFosRederived = derivePeakThreshold(rawFosValues, BIN_WIDTH, SMOOTH_KERNEL, PEAK_PROMINENCE, N_PEAK)
double rawTdtRederived = derivePeakThreshold(rawTdtValues, BIN_WIDTH, SMOOTH_KERNEL, PEAK_PROMINENCE, N_PEAK)
println "Self-check (Open Question 1): raw-measure re-derivation vs the locked absolute cutoffs"
println String.format("  Fos raw re-derived=%.4f  vs locked %.4f  -> %s", rawFosRederived, fos.thr,
        (Double.isNaN(rawFosRederived) ? "CHECK (no data / no peak found)" :
                (Math.abs(rawFosRederived - fos.thr) <= 0.2 * fos.thr ? "PASS (within 20%)" : "CHECK (>20% off -- inspect kernel/window semantics)")))
println String.format("  TdT raw re-derived=%.4f  vs locked %.4f  -> %s", rawTdtRederived, tdt.thr,
        (Double.isNaN(rawTdtRederived) ? "CHECK (no data / no peak found)" :
                (Math.abs(rawTdtRederived - tdt.thr) <= 0.2 * tdt.thr ? "PASS (within 20%)" : "CHECK (>20% off -- inspect kernel/window semantics)")))

// Re-derive on the bg-sub measure -- these are the operative D-05 thresholds.
def bgFosValues = classifiable.collect { it.getMeasurements().get("Nucleus: AF488-T3 mean (bg-sub)")?.doubleValue() }.findAll { it != null && !Double.isNaN(it) }
def bgTdtValues = classifiable.collect { it.getMeasurements().get("Cytoplasm: AF568-T2 mean (bg-sub)")?.doubleValue() }.findAll { it != null && !Double.isNaN(it) }
double newFosThreshold = derivePeakThreshold(bgFosValues, BIN_WIDTH, SMOOTH_KERNEL, PEAK_PROMINENCE, N_PEAK)
double newTdtThreshold = derivePeakThreshold(bgTdtValues, BIN_WIDTH, SMOOTH_KERNEL, PEAK_PROMINENCE, N_PEAK)
println "Re-derived Fos threshold (bg-sub measure): ${newFosThreshold}"
println "Re-derived TdT threshold (bg-sub measure): ${newTdtThreshold}"

/** Writes a bg-sub classifier JSON in the same shape as the existing Fos/TdT classifier files, so readSpec parses it unmodified. */
def writeBgsubClassifierSpec = { String fn, String measurement, double threshold ->
    def obj = new JsonObject()
    obj.addProperty("object_classifier_type", "SimpleClassifier")
    def func = new JsonObject()
    func.addProperty("classifier_fun", "ClassifyByMeasurementFunction")
    func.addProperty("measurement", measurement)
    func.addProperty("pathClassBelow", "Negative")
    func.addProperty("pathClassEquals", "Positive")
    func.addProperty("pathClassAbove", "Positive")
    func.addProperty("threshold", threshold)
    obj.add("function", func)
    def pathClasses = new JsonArray()
    pathClasses.add("Negative")
    pathClasses.add("Positive")
    obj.add("pathClasses", pathClasses)
    obj.addProperty("filter", "DETECTIONS_ALL")
    obj.addProperty("note", "D-05: threshold re-derived by 02_detect_classify.groovy via ChannelHistogram peak-finding on the (bg-sub) measure at ${new Date()}.")
    new File(base, fn).text = new GsonBuilder().setPrettyPrinting().create().toJson(obj)
}
// Only overwrite the committed placeholder if this run actually produced a
// valid peak (idempotent/safe: a run with insufficient/no data leaves the
// last-known-good JSON on disk rather than clobbering it with NaN).
if (!Double.isNaN(newFosThreshold)) {
    writeBgsubClassifierSpec("Fos_Classifier_20x_bgsub.json", "Nucleus: AF488-T3 mean (bg-sub)", newFosThreshold)
} else {
    println "  WARNING: Fos bg-sub threshold re-derivation failed (NaN) -- keeping existing Fos_Classifier_20x_bgsub.json unchanged."
}
if (!Double.isNaN(newTdtThreshold)) {
    writeBgsubClassifierSpec("TdT_classifier_bgsub.json", "Cytoplasm: AF568-T2 mean (bg-sub)", newTdtThreshold)
} else {
    println "  WARNING: TdT bg-sub threshold re-derivation failed (NaN) -- keeping existing TdT_classifier_bgsub.json unchanged."
}

// Re-read via the SAME readSpec closure used for the old JSONs (schema-compatible round-trip).
def fosBg = readSpec("Fos_Classifier_20x_bgsub.json")
def tdtBg = readSpec("TdT_classifier_bgsub.json")
println "Fos rule (bg-sub, D-05, OPERATIVE): ${fosBg.meas} >= ${fosBg.thr}"
println "TdT rule (bg-sub, D-05, OPERATIVE): ${tdtBg.meas} >= ${tdtBg.thr}"
println "(Superseded reference only, NOT operative: Fos raw >= ${fos.thr}, TdT raw >= ${tdt.thr} -- Pitfall 9)"

// ── compound classification core (nucleus-anchored, no proximity/overlap) ───
int cFos = 0, cTdt = 0, cDbl = 0, cNeg = 0, cExc = 0
dets.each { d ->
    if (isExcluded(d)) {
        d.setPathClass(getPathClass("Excluded")); cExc++; return
    }
    def vf = d.getMeasurements().get(fosBg.meas)
    def vt = d.getMeasurements().get(tdtBg.meas)
    boolean isF = vf != null && !Double.isNaN(vf.doubleValue()) && vf.doubleValue() >= fosBg.thr
    boolean isT = vt != null && !Double.isNaN(vt.doubleValue()) && vt.doubleValue() >= tdtBg.thr
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
    counts.each { cls, cnt -> ml.put("Count: ${cls}", cnt as double) }
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
// imageData already resolved above (shared handle, D-04 pre-pass) -- do not redeclare.
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
