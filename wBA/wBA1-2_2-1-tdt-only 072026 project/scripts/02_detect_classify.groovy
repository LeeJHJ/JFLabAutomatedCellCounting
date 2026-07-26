/**
 * 02_detect_classify.groovy — classify/label/report entry point (SCRI-03, generalized PIPE-01/02/05)
 *
 * SCOPE (D-01): This script does NOT detect. Detection stays in
 * run_braian_detection.groovy — that is the standalone, CPU-heavy BraiAnDetect
 * pass. This numbered script assumes detections already exist on the current
 * entry and performs classification + atlas region labeling + reporting only.
 * Keeping detection out of this script lets the fast threshold-iteration loop
 * re-run without re-detecting.
 *
 * CONFIG-DRIVEN MARKER SET (D-01/D-02/D-09/D-14, Phase 06.1): every marker
 * (name/channel/compartment), the segmentation anchor (name/channel), region
 * exclusions, k_robust, and cytoplasmic ring geometry are read from the
 * sidecar `pipeline.yml` at the QuPath project base dir — nothing
 * marker-specific is hardcoded here. 1..N markers are supported: a
 * single-marker (e.g. TdT-only) config degenerates to `<marker>+`/Negative
 * with no code path naming an absent marker; a >=2-marker config additionally
 * emits `Double+` (D-03) when >=2 declared markers are positive on a cell.
 *
 * GUARD + IDEMPOTENCY (D-02, D-15): if the current entry has zero detections,
 * or has no ABBA registration loaded, or the image is missing a
 * config-declared channel, this script aborts cleanly with a clear message
 * telling the operator what to do. Otherwise detections are (re)classified in
 * place — setPathClass overwrites, so re-running just refreshes classes; safe
 * to re-run freely during threshold tuning. Under "Run for project", any
 * entry that fails a guard simply aborts cleanly rather than erroring the
 * batch.
 *
 * CLASSIFICATION (nucleus-anchored, no proximity/overlap — CLAUDE.md, locked):
 * for each declared marker, `<marker>+` iff its bg-sub measure on its
 * declared compartment (nuclear -> nucleus ROI, cytoplasmic -> expanded
 * cell/cytoplasm ROI, whole-cell -> whole-cell/Cell area-weighted ROI) is >=
 * that marker's re-derived threshold. Compound
 * class per nucleus: `Double+` (only when >=2 markers declared AND >=2
 * positive) / `<marker>+` (exactly one positive) / `Negative`. This is the
 * exact classify_markers.groovy core (base for this script, now retired —
 * D-06), generalized to N markers — NOT BraiAn.yml's classifiers:/
 * OverlappingDetections path (Deviation #1, forbidden: that path cannot
 * classify one DAPI detection set by multiple independent markers without
 * proximity/overlap heuristics).
 *
 * D-03/D-05: classification reads each marker's (bg-sub) measure against a
 * threshold RE-DERIVED on that measure at runtime via a self-calibrating
 * robust cut (background median + k*1.4826*MAD, k from pipeline.yml's
 * k_robust) -- NOT any absolute cutoff, and NOT the superseded
 * nth-histogram-peak strategy (which assumed a bimodality that sparse
 * markers don't have -> NaN -> 100% Negative, the original D-05 gate
 * failure). The per-marker bg-sub classifier JSONs
 * (`<marker>_Classifier_bgsub.json`) are re-derived and overwritten on every
 * run (Pitfall 9: do not let any stale absolute cutoff leak back in against
 * the bg-sub measure).
 *
 * EXCLUSIONS: detections whose centroid falls in a config-declared excluded
 * region (`exclude_acronyms`, e.g. DG-sg + ventricular systems VS) are set to
 * "Excluded" and NOT marker-classified.
 *
 * BACKGROUND-ROBUST MEASURE (D-04): before classification, every detection
 * gains a compartment-agnostic local-background-subtracted measurement for
 * EACH declared marker -- "<CompartmentLabel>: <channel> mean (bg-sub)"
 * (nuclear markers: ring built outside the nucleus ROI; cytoplasmic/whole-cell
 * markers: ring built outside the expanded cell/cytoplasm ROI). This fixes the
 * original SSp-autofluorescence false-positive bug without introducing a
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
 * Run AFTER a BraiAnDetect detection pass, and AFTER pipeline.yml declares
 * the marker set for this slice-set.
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
import com.google.gson.JsonObject
import com.google.gson.JsonArray
import com.google.gson.GsonBuilder
import static qupath.lib.scripting.QP.*

// ── Entry confirmation ──────────────────────────────────────────────────────
// Print entry name to catch wrong-entry errors (guards against running on the
// wrong project entry under "Run for project").
println "Running on: " + getCurrentImageData().getServer().getMetadata().getName()

// ── D-01/D-02/D-09/D-14: pipeline.yml sidecar config reader ─────────────────
// No YAML library ships with QuPath's bundled Groovy (the same constraint that
// forces export_region_dapi_reference.groovy's regex "grab" idiom for
// BraiAn.yml). This reader is a line-based mini-parser targeted at
// pipeline.yml's known shape (D-14): anchor{name,channel},
// markers[]{name,channel,compartment}, exclude_acronyms[], k_robust,
// ring{gap_um,width_um}. Comments (# ...) are stripped before parsing,
// tracking quote state so a '#' inside a quoted string is never mistaken for
// a comment marker (not currently needed by pipeline.yml's values, but safe).
def pipelineYmlFile = new File(getProject().getBaseDirectory(), "pipeline.yml")
if (!pipelineYmlFile.exists()) {
    println "ERROR: pipeline.yml not found at ${pipelineYmlFile}."
    println "       Author the sidecar pipeline config (anchor/markers/exclude_acronyms/k_robust/ring) first."
    return
}

def stripComment = { String line ->
    int quoteCount = 0
    for (int i = 0; i < line.length(); i++) {
        char c = line.charAt(i)
        if (c == ('"' as char)) quoteCount++
        else if (c == ('#' as char) && quoteCount % 2 == 0) return line.substring(0, i)
    }
    return line
}
def indentOf = { String line -> line.length() - line.replaceAll(/^\s+/, "").length() }

def rawLines = pipelineYmlFile.readLines().collect { stripComment(it) }

String anchorName = null, anchorChannel = null
def markers = []            // [ [name:, channel:, compartment:], ... ] -- non-anchor markers only (D-01)
def excludeAcronyms = [] as Set
Double kRobust = null
Double gapUm = null, widthUm = null

int i = 0
int nLines = rawLines.size()
while (i < nLines) {
    def trimmed = rawLines[i].trim()
    if (trimmed.isEmpty()) { i++; continue }

    if (trimmed == "anchor:") {
        int j = i + 1
        while (j < nLines && (rawLines[j].trim().isEmpty() || indentOf(rawLines[j]) > 0)) {
            def t = rawLines[j].trim()
            def mName = (t =~ /^name:\s*"([^"]+)"/)
            def mChan = (t =~ /^channel:\s*"([^"]+)"/)
            if (mName.find()) anchorName = mName.group(1)
            if (mChan.find()) anchorChannel = mChan.group(1)
            j++
        }
        i = j
        continue
    }

    if (trimmed == "markers:") {
        int j = i + 1
        def current = null
        while (j < nLines && (rawLines[j].trim().isEmpty() || indentOf(rawLines[j]) > 0)) {
            def t = rawLines[j].trim()
            def mNew = (t =~ /^-\s*name:\s*"([^"]+)"/)
            if (mNew.find()) {
                if (current != null) markers << current
                current = [name: mNew.group(1), channel: null, compartment: null]
            } else if (current != null) {
                def mChan = (t =~ /^channel:\s*"([^"]+)"/)
                def mComp = (t =~ /^compartment:\s*"([^"]+)"/)
                if (mChan.find()) current.channel = mChan.group(1)
                if (mComp.find()) current.compartment = mComp.group(1)
            }
            j++
        }
        if (current != null) markers << current
        i = j
        continue
    }

    def mExcl = (trimmed =~ /^exclude_acronyms:\s*\[(.*)\]/)
    if (mExcl.find()) {
        def inner = mExcl.group(1)
        (inner =~ /"([^"]*)"/).each { m -> excludeAcronyms << m[1] }
        i++
        continue
    }

    def mK = (trimmed =~ /^k_robust:\s*([0-9.eE+-]+)/)
    if (mK.find()) { kRobust = mK.group(1) as Double; i++; continue }

    if (trimmed == "ring:") {
        int j = i + 1
        while (j < nLines && (rawLines[j].trim().isEmpty() || indentOf(rawLines[j]) > 0)) {
            def t = rawLines[j].trim()
            def mGap = (t =~ /^gap_um:\s*([0-9.eE+-]+)/)
            def mWid = (t =~ /^width_um:\s*([0-9.eE+-]+)/)
            if (mGap.find()) gapUm = mGap.group(1) as Double
            if (mWid.find()) widthUm = mWid.group(1) as Double
            j++
        }
        i = j
        continue
    }

    i++
}

// ── Fail-loud: every required key must be present (T-06.1-03) ──────────────
def missingKeys = []
if (anchorName == null)    missingKeys << "anchor.name"
if (anchorChannel == null) missingKeys << "anchor.channel"
if (markers.isEmpty())     missingKeys << "markers (empty or missing)"
markers.eachWithIndex { m, idx ->
    if (m.channel == null)     missingKeys << "markers[${idx}].channel (name=${m.name})"
    if (m.compartment == null) missingKeys << "markers[${idx}].compartment (name=${m.name})"
    else if (!(m.compartment in ["nuclear", "cytoplasmic", "whole-cell"]))
        missingKeys << "markers[${idx}].compartment invalid value '${m.compartment}' (name=${m.name}; must be nuclear, cytoplasmic, or whole-cell)"
}
if (kRobust == null) missingKeys << "k_robust"
if (gapUm == null)   missingKeys << "ring.gap_um"
if (widthUm == null) missingKeys << "ring.width_um"
if (!missingKeys.isEmpty()) {
    println "ERROR: pipeline.yml is missing/invalid required key(s): ${missingKeys}"
    println "       Fix pipeline.yml and re-run. Aborting."
    return
}
println "pipeline.yml loaded: anchor=${anchorName}/${anchorChannel}  markers=${markers.collect { it.name }}  " +
        "exclude_acronyms=${excludeAcronyms}  k_robust=${kRobust}  ring(gap_um=${gapUm}, width_um=${widthUm})"

// nuclear -> Nucleus, cytoplasmic -> Cytoplasm (06.1-01 contract, locked).
// whole-cell -> Cell (added w88, 2026-07-25): QuPath's area-weighted whole-cell
// mean over ALL cell pixels (nucleus + cytoplasm), for markers whose signal
// fills the whole cell (e.g. TdTomato, operator-confirmed domain call) rather
// than being strictly cytosolic. The "whole-cell" key is hyphenated and MUST
// stay quoted in this Groovy map literal.
def COMPARTMENT_LABELS = [nuclear: "Nucleus", cytoplasmic: "Cytoplasm", "whole-cell": "Cell"]
// D-03: Double+ is structurally possible only when >=2 non-anchor markers are declared.
boolean emitDouble = markers.size() >= 2

// ── image/server/hierarchy handles (shared: guards, bg-sub pass, threshold re-derivation, Atlas_X) ──
def imageData = getCurrentImageData()
def server = imageData.getServer()
def hierarchy = imageData.getHierarchy()

// ── D-15 guard 1: ABBA registration present (mirrors 01_load_abba_rois.groovy) ──
def availableAtlases = AtlasTools.getAvailableAtlasRegistration(imageData)
if (availableAtlases.isEmpty()) {
    println "ERROR: No ABBA registration files found in data directory."
    println "       Run ABBA export from Fiji first:"
    println "       Plugins > Atlas > Multi Image To Atlas > Export"
    println "       -> 'ABBA - Export Registrations To QuPath Project'"
    return
}
println "Found ABBA registrations: ${availableAtlases}"

// ── runtime classifier-JSON base dir (Gson; no groovy.json in QuPath) ───────
def base = new File(getProject().getBaseDirectory(), "classifiers/object_classifiers")
def readSpec = { fn ->
    def o = JsonParser.parseString(new File(base, fn).text).getAsJsonObject().getAsJsonObject("function")
    [meas: o.get("measurement").getAsString(), thr: o.get("threshold").getAsDouble()]
}

// build exclusion ROIs (parent region annotations whose acronym is in the config's exclude_acronyms)
def excludeRois = []
getAnnotationObjects().each { ann ->
    def label = ann.getPathClass()?.toString() ?: ann.getName()
    if (label == null || ann.getROI() == null) return
    def m = (label =~ /(?i)^(?:Left|Right):\s*(.+)$/)
    def acr = m.find() ? m.group(1) : label
    if (excludeAcronyms.contains(acr)) excludeRois << ann.getROI()
}
println "Exclusion regions (${excludeAcronyms}): ${excludeRois.size()} annotation ROI(s)"

// ── D-15 guard 2: detections present ────────────────────────────────────────
def dets = getDetectionObjects()
if (dets.isEmpty()) { println "No detections — run BraiAnDetect first. Aborting."; return }

// ── D-15 guard 3 (NEW): config-declared channels present on this image ─────
def imageChannelNames = server.getMetadata().getChannels().collect { it.getName() } as Set
def declaredChannels = ([anchorChannel] + markers.collect { it.channel }) as Set
def missingChannels = declaredChannels.findAll { !imageChannelNames.contains(it) }
if (!missingChannels.isEmpty()) {
    println "ERROR: pipeline.yml declares channel(s) not present on this image: ${missingChannels}"
    println "       Image channels available: ${imageChannelNames}"
    println "       Fix pipeline.yml (or re-check the image's channel names) and re-run. Aborting."
    return
}
println "Channel-match OK: all declared channels (${declaredChannels}) present on image (${imageChannelNames})."

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

// Ring-geometry (µm), from pipeline.yml (D-09) -- tune visually per slice-set,
// like Phase 2's cellExpansionMicrons; ring must not eat into the cell's own
// compartment. Buffer distances are in PIXELS (Pitfall 2), so convert before use.
double gapPx = gapUm / pixelUm
double outerPx = (gapUm + widthUm) / pixelUm

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
 * passes the nucleus ROI for a nuclear marker, the expanded cell/cytoplasm ROI
 * for a cytoplasmic marker -- Pitfall 3). Neighboring detections are excluded
 * from the annulus via exact geometric subtraction, using a bounding-box
 * "quick check" neighbor query (getAllObjectsForRegion, NOT the centroid-only
 * getAllObjectsForROI -- Pitfall 8) to avoid missing neighbors whose centroid
 * sits outside the ring but whose body intrudes into it. Uses
 * ObjectMeasurements (the same class QuPath's own Nucleus/Cytoplasm
 * measurements are built with) on a throwaway detection object that is never
 * added to the hierarchy -- Don't Hand-Roll.
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
        // A plain detection object (the annulus is NOT a cell with sub-ROIs) names
        // its intensity measurement "<channel>: Mean" -- NOT "Cell: <channel> mean".
        // The A5 self-check above empirically prints e.g. [AF488-T3: Mean, ...], so
        // resolve the key by matching the channel name rather than assuming a
        // compartment prefix (the old "Cell: ${channelName} mean" assumption returned
        // null -> NaN for every cell -> empty D-05 population -> 100% Negative).
        def key = tempObj.getMeasurements().keySet().find {
            it.startsWith(channelName) && it.toLowerCase().endsWith("mean")
        }
        def v = key == null ? null : tempObj.getMeasurements().get(key)
        return (v == null || Double.isNaN(v.doubleValue())) ? Double.NaN : v.doubleValue()
    } catch (Throwable t) {
        // JTS "side location conflict" & kin: geometry robustness failure on this
        // cell's annulus. Skip local-bg for it rather than aborting the whole batch.
        bgGeomFailures++
        return Double.NaN
    }
}

// ── D-15 guard 4: whole-cell markers require QuPath's Cell-compartment mean ──
// Without this guard, a missing "Cell: <channel> mean" key resolves rawKey ->
// null -> NaN -> every cell Negative for that marker -- the exact silent
// failure the A5/A5b self-checks warn about. Fail-loud (abort) is chosen over
// any Nucleus-area+Cytoplasm-area fallback, per the codebase's D-15 convention.
// Runs at TOP SCRIPT SCOPE (not inside dets.each) so `return` aborts the whole
// run rather than silently skipping one detection.
def wholeCellMarkers = markers.findAll { it.compartment == "whole-cell" }
if (!wholeCellMarkers.isEmpty()) {
    def sampleKeys = dets.first().getMeasurements().keySet()   // dets already guaranteed non-empty by guard 2
    def missingCellKeys = wholeCellMarkers.findAll { !sampleKeys.contains("Cell: ${it.channel} mean") }
            .collect { "Cell: ${it.channel} mean" }
    if (!missingCellKeys.isEmpty()) {
        println "ERROR: whole-cell marker(s) declared in pipeline.yml but missing QuPath's Cell-compartment measurement key(s): ${missingCellKeys}"
        println "       BraiAnDetect must emit the Cell-compartment mean for whole-cell markers to work --"
        println "       re-run detection with makeMeasurements including BOTH nuclei AND a cell expansion so the Cell compartment exists."
        println "       Actual measurement keys present on this entry's detections: ${sampleKeys}"
        println "       Aborting."
        return
    }
    println "Whole-cell guard OK: Cell-compartment mean present for ${wholeCellMarkers.collect { it.name }}."
}

println "Computing local-background-subtracted measures (D-04) for ${dets.size()} detections x ${markers.size()} marker(s)..."
// Self-diagnosing finite-value counters (per marker): isolate WHICH input goes
// NaN if the bg-sub population ends up empty again (raw compartment read vs
// local-bg annulus).
int bgProcessed = 0
def nFiniteRaw = markers.collectEntries { [(it.name): 0] }
def nFiniteBg = markers.collectEntries { [(it.name): 0] }
def nFiniteBgsub = markers.collectEntries { [(it.name): 0] }
boolean realKeySetPrinted = false
dets.each { d ->
    // Nuclear markers' ring anchors OUTSIDE the nucleus ROI; cytoplasmic markers'
    // ring anchors OUTSIDE the expanded cell/cytoplasm ROI -- distinct per-marker
    // anchors (Pitfall 3).
    def nucleusRoi = (d.respondsTo('getNucleusROI') && d.getNucleusROI() != null) ? d.getNucleusROI() : d.getROI()
    def cellRoi = d.getROI()

    // Print the REAL detection's key set once (the throwaway A5 print above only
    // reveals the plain-annulus keys, not the compartment keys on actual cells).
    if (!realKeySetPrinted) {
        println "A5b self-check: REAL detection key set = ${d.getMeasurements().keySet()}"
        realKeySetPrinted = true
    }

    markers.each { m ->
        String label = COMPARTMENT_LABELS[m.compartment]
        def baseRoi = (m.compartment == "nuclear") ? nucleusRoi : cellRoi
        String rawKey = "${label}: ${m.channel} mean"
        String bgsubKey = "${label}: ${m.channel} mean (bg-sub)"

        def rawM = d.getMeasurements().get(rawKey)
        double raw = rawM != null ? rawM.doubleValue() : Double.NaN
        double bg = localBackgroundSubtractedMean(baseRoi, m.channel, d)
        double bgsub = raw - bg
        d.getMeasurements().put(bgsubKey, bgsub)

        if (!Double.isNaN(raw))   nFiniteRaw[m.name]   = nFiniteRaw[m.name] + 1
        if (!Double.isNaN(bg))    nFiniteBg[m.name]    = nFiniteBg[m.name] + 1
        if (!Double.isNaN(bgsub)) nFiniteBgsub[m.name] = nFiniteBgsub[m.name] + 1
    }

    bgProcessed++
    if (bgProcessed % 1000 == 0) println "  ...background-subtracted ${bgProcessed}/${dets.size()} detections"
}
fireHierarchyUpdate()
if (bgGeomFailures > 0)
    println "  NOTE: ${bgGeomFailures} detection-marker annulus computation(s) hit a geometry-robustness failure and were assigned NaN bg-sub (→ Negative contribution). Negligible if small; investigate if large."
println "D-04 finite-value counts (of ${dets.size()} detections):"
markers.each { m -> println "  ${m.name}: raw=${nFiniteRaw[m.name]} bg=${nFiniteBg[m.name]} bgsub=${nFiniteBgsub[m.name]}" }
println "Background-subtracted measures written for ${dets.size()} detections (D-04)."

// ── isExcluded: shared centroid-in-excludeRois test (reused by threshold ───
// derivation population below AND the classification loop, replacing the
// previously-inlined check with a single named closure).
def isExcluded = { detection ->
    def r = detection.getROI()
    double x = r.getCentroidX(), y = r.getCentroidY()
    excludeRois.any { it.contains(x, y) }
}

// ── D-05 (redesign): self-calibrating robust threshold on the bg-sub measure ──
// The original strategy took the nth (2nd) histogram peak, assuming a BIMODAL
// distribution (background peak + positive peak). Sparse markers (a few %
// positive) give a unimodal/background-dominated bg-sub histogram, findPeaks
// returns 0 peaks -> NaN -> the safe-write guard kept placeholder JSONs
// carrying RAW-scale cutoffs, and 100% of cells classified Negative (the
// original D-05 gate failure). Replaced with a robust cut a few
// outlier-resistant SDs above the near-zero background band:
//     threshold = background_mode + k_robust * (1.4826 * MAD)
// background_mode: median of the bg-sub population (a cell in its own local
//   background has bg-sub ~= 0, so the median tracks the background mode). MAD:
//   median absolute deviation; 1.4826*MAD is a robust SD estimate. Auto-derives
//   per marker per section (D-01 series-scalability), needs no bimodality assumption.
def classifiable = dets.findAll { !isExcluded(it) }   // Pitfall 6: exclude config-declared regions from the derivation population
println "Threshold derivation population (excluding ${excludeAcronyms}): ${classifiable.size()} / ${dets.size()} detections"

/** Median of a list of Doubles (linear-interpolated for even n); NaN if empty. */
def medianOf = { List<Double> xs ->
    if (xs == null || xs.isEmpty()) return Double.NaN
    def s = xs.toSorted()
    int m = s.size()
    int mid = m.intdiv(2)
    return (m % 2 == 1) ? (s[mid] as double) : 0.5d * ((s[mid - 1] as double) + (s[mid] as double))
}
/** Median absolute deviation of xs about med (raw MAD, not yet scaled); NaN if empty. */
def madOf = { List<Double> xs, double med ->
    if (xs == null || xs.isEmpty() || Double.isNaN(med)) return Double.NaN
    return medianOf(xs.collect { Math.abs((it as double) - med) })
}
/**
 * Robust self-calibrating positive-call threshold for a sparse, background-
 * subtracted marker population (D-05 redesign): background_mode + k*(1.4826*MAD),
 * with the background_mode approximated by the population median (bg-sub ~= 0 for
 * a cell in its own local background) and 1.4826*MAD a robust SD. Returns NaN only
 * when there is no usable data, so the safe-write guard keeps the last-known-good
 * JSON rather than clobbering it.
 */
def robustThreshold = { List<Double> values, double k ->
    if (values == null || values.isEmpty()) return Double.NaN
    double med = medianOf(values)
    if (Double.isNaN(med)) return Double.NaN
    double mad = madOf(values, med)
    if (Double.isNaN(mad)) return Double.NaN
    return med + k * (1.4826d * mad)
}
/** Fraction of values at or above threshold (for the self-check sanity band); NaN if no data/threshold. */
def positiveFraction = { List<Double> values, double threshold ->
    if (values == null || values.isEmpty() || Double.isNaN(threshold)) return Double.NaN
    int pos = values.count { (it as double) >= threshold }
    return (double) pos / values.size()
}
/**
 * Mandatory self-check (per marker): instead of comparing to any superseded
 * RAW cutoff, verify each derived threshold lands in a sane band: finite,
 * strictly above the background band (> 0), and calling a SPARSE but non-zero
 * fraction of the classifiable population positive. posFrac == 0 reproduces the
 * exact D-05 gate failure (all-Negative); posFrac > ~0.5 means the cut is far too
 * low. Prints the median/robust-SD that fed each threshold for tuning k_robust.
 */
def selfCheck = { String marker, List<Double> values, double threshold ->
    double med = medianOf(values)
    double mad = madOf(values, med)
    double robustSd = 1.4826d * mad
    double posFrac = positiveFraction(values, threshold)
    String verdict
    if (Double.isNaN(threshold))                        verdict = "CHECK (no data -- threshold NaN, safe-write keeps last-known-good JSON)"
    else if (threshold <= 0.0d)                         verdict = "CHECK (threshold <= 0 -- background band not separated)"
    else if (Double.isNaN(posFrac) || posFrac <= 0.0d)  verdict = "CHECK (0% positive -- reproduces the D-05 all-Negative failure)"
    else if (posFrac > 0.5d)                            verdict = "CHECK (>50% positive -- cut implausibly low for a sparse marker)"
    else                                                verdict = String.format("PASS (%.2f%% positive -- sparse, non-zero)", 100.0d * posFrac)
    println String.format("  %s: n=%d  median=%.4f  robustSD(1.4826*MAD)=%.4f  threshold=%.4f  -> %s",
            marker, values.size(), med, robustSd, threshold, verdict)
}

/** Writes a bg-sub classifier JSON in the same shape as the legacy Fos/TdT classifier files, so readSpec parses it unmodified. */
def writeBgsubClassifierSpec = { String fn, String measurement, double threshold, double k ->
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
    obj.addProperty("note", "D-05: threshold re-derived by 02_detect_classify.groovy via the robust self-calibrating cut (background median + k*1.4826*MAD, k_robust=${k}, from pipeline.yml) on the (bg-sub) measure at ${new Date()}.")
    new File(base, fn).text = new GsonBuilder().setPrettyPrinting().create().toJson(obj)
}

// Re-derive the operative D-05 threshold PER MARKER on the bg-sub measure via
// the robust self-calibrating cut (background median + k_robust robust SDs).
// These are the values classification actually uses. Filenames/measurement
// keys are entirely config-driven (D-09) -- never the two legacy literal names.
def markerBgValues = [:]
def markerThresholds = [:]
def markerSpecs = [:]   // name -> [meas:, thr:] re-read from disk (safe-write round-trip)

markers.each { m ->
    String label = COMPARTMENT_LABELS[m.compartment]
    String bgsubKey = "${label}: ${m.channel} mean (bg-sub)"
    def values = classifiable.collect { it.getMeasurements().get(bgsubKey)?.doubleValue() }.findAll { it != null && !Double.isNaN(it) }
    markerBgValues[m.name] = values
    markerThresholds[m.name] = robustThreshold(values, kRobust)
    println "Re-derived ${m.name} threshold (bg-sub measure, median + ${kRobust}*1.4826*MAD): ${markerThresholds[m.name]}"
}

println "Self-check (D-05 redesign): robust-threshold sanity band on the bg-sub population, per marker"
markers.each { m -> selfCheck(m.name, markerBgValues[m.name], markerThresholds[m.name]) }

// Only overwrite the committed placeholder if this run actually produced a
// finite threshold (idempotent/safe: a run with insufficient/no data leaves the
// last-known-good JSON on disk rather than clobbering it with NaN).
markers.each { m ->
    String label = COMPARTMENT_LABELS[m.compartment]
    String bgsubKey = "${label}: ${m.channel} mean (bg-sub)"
    String fn = "${m.name}_Classifier_bgsub.json"
    double thr = markerThresholds[m.name]
    if (!Double.isNaN(thr)) {
        writeBgsubClassifierSpec(fn, bgsubKey, thr, kRobust)
    } else {
        println "  WARNING: ${m.name} bg-sub threshold re-derivation failed (NaN) -- keeping existing ${fn} unchanged."
    }
    // Re-read via the SAME readSpec closure used previously (schema-compatible round-trip).
    markerSpecs[m.name] = readSpec(fn)
    println "${m.name} rule (bg-sub, D-05, OPERATIVE): ${markerSpecs[m.name].meas} >= ${markerSpecs[m.name].thr}"
}

// ── compound classification core (nucleus-anchored, no proximity/overlap) ───
// D-03: Double+ emitted ONLY when >=2 non-anchor markers are declared AND >=2
// are positive on the cell. A single-marker config degenerates to
// "<marker>+"/Negative with no code path naming an absent marker.
int cExc = 0, cNeg = 0, cDbl = 0
def markerOnlyCounts = markers.collectEntries { [(it.name): 0] }
dets.each { d ->
    if (isExcluded(d)) {
        d.setPathClass(getPathClass("Excluded")); cExc++; return
    }
    def positiveMarkers = markers.findAll { m ->
        def spec = markerSpecs[m.name]
        def v = d.getMeasurements().get(spec.meas)
        v != null && !Double.isNaN(v.doubleValue()) && v.doubleValue() >= spec.thr
    }
    if (emitDouble && positiveMarkers.size() >= 2) {
        d.setPathClass(getPathClass("Double+")); cDbl++
    } else if (positiveMarkers.size() == 1) {
        def name = positiveMarkers[0].name
        d.setPathClass(getPathClass("${name}+"))
        markerOnlyCounts[name] = markerOnlyCounts[name] + 1
    } else {
        d.setPathClass(getPathClass("Negative")); cNeg++
    }
}
fireHierarchyUpdate()

// ── class-breakdown console print (config-driven; no fixed marker pair) ────
int n = dets.size()
int classified = n - cExc
def pct = { c -> classified > 0 ? 100.0 * c / classified : 0.0 }   // % of CLASSIFIED (non-excluded) nuclei
println "Total nuclei: ${n}  |  Excluded: ${cExc}  |  Classified: ${classified}"
println String.format("  Negative : %d (%.1f%%)", cNeg, pct(cNeg))
markers.each { m ->
    int c = markerOnlyCounts[m.name]
    println String.format("  %s+ only: %d (%.1f%%)", m.name, c, pct(c))
}
if (emitDouble) {
    println String.format("  Double+  : %d (%.1f%%)", cDbl, pct(cDbl))
}
markers.each { m ->
    int total = markerOnlyCounts[m.name] + (emitDouble ? cDbl : 0)
    println String.format("  => Total %s+ (incl. Double+): %d (%.1f%%)", m.name, total, pct(total))
}
if (emitDouble) {
    markers.each { m ->
        int totalM = markerOnlyCounts[m.name] + cDbl
        println String.format("  Advisory Double+/%s+ ratio: %s", m.name,
                totalM > 0 ? String.format("%.3f", (double) cDbl / totalM) : "n/a")
    }
}

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
// script's ground truth (RESEARCH Pitfall 1).
// NOTE: this rollup uses the OLD (pre-CR-01) child-annotation-emptiness leaf
// heuristic and independent centroid-in-parent-ROI counting -- it is
// SUPERSEDED by the consolidated export's CR-01 leaf-summed rollup (06.1-03,
// D-10). Left in place here as a lightweight in-QuPath sanity view only; the
// class-name LIST itself is built from the declared marker set (not a fixed
// Fos+/TdT+ pair) so it never silently omits a declared marker's counts.
def ROLLUP_CLASSES = (["Negative"] + markers.collect { "${it.name}+" } +
        (emitDouble ? ["Double+"] : []) + ["Excluded"])
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
// Atlas_X/Y/Z export column (that is the consolidated export, 06.1-03).
// Pattern 5 (RESEARCH.md): AtlasTools.getAtlasToPixelTransform is the official
// BIOP/ABBA-author pattern, cross-verified against the installed
// qupath-extension-abba-0.4.0.jar + bundled imglib2-realtransform.
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
    def positiveClassNames = (markers.collect { "${it.name}+" } + (emitDouble ? ["Double+"] : [])) as Set
    def sample = dets.findAll { positiveClassNames.contains(it.getPathClass()?.toString()) }.take(5)
    if (sample.isEmpty()) {
        println "  No positively-classified cells to sample from."
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
