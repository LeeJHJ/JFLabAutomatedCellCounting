/**
 * calibrate_threshold.groovy
 *
 * Measures the anchor-channel intensity histogram of the CURRENT image, locates the
 * two peaks that are reliably findable on real sections, and reports where the
 * span-fraction detection threshold lands -- for a sweep of fractions, so the
 * operator can SEE the consequence of the knob before committing to it.
 *
 * Writes  <project>/results/<image>__threshold_calibration.json  which
 * notebooks/01_calibrate.ipynb plots (histogram + floor/bright peaks + the chosen
 * cut + the sweep). Nothing here changes the image or its objects: this script is
 * READ-ONLY and safe to re-run at any time.
 *
 * REPLACES the per-project `find_threshold().groovy` copies, which hardwired the
 * channel name ("DAPI-T4") and printed a prominence sweep whose meaning was easy
 * to misread: sweeping `peakProminence` changes WHICH PEAK is found, not where the
 * cut sits between peaks. The generalizable knob is the fraction of the span.
 *
 * WHY A SPAN FRACTION (see pipeline.yml `detection_threshold` for the long form):
 *   BraiAn's own `histogramThreshold` needs a distinct dim-nuclei peak; our
 *   sections have only a background floor and a bright-nuclei peak, so it can
 *   return only "background" (floods noise) or "bright only" (drops dim nuclei).
 *   An absolute threshold generalizes to nothing. Placing the cut a fixed
 *   fraction of the way between floor and bright peak re-derives itself from each
 *   section's own histogram, which is what keeps sections comparable.
 *
 * USAGE
 *   1. Open the project, double-click the calibration slice.
 *   2. Automate > Script editor > Run.
 *   3. Read the printed table; plot it in notebooks/01_calibrate.ipynb section 3.
 *   4. Set `detection_threshold.span_frac` in pipeline.yml, then run
 *      run_braian_detection.groovy (which re-derives the same cut per slice).
 *
 * Requires only the anchor channel to exist -- runs BEFORE any detection, and
 * does NOT require ABBA regions to be loaded.
 *
 * @author section-pipeline
 */
import qupath.ext.braian.ImageChannelTools
import qupath.ext.braian.config.AutoThresholdParmameters
import qupath.ext.braian.config.WatershedCellDetectionConfig
import static qupath.lib.scripting.QP.*

// ── Read anchor channel + detection_threshold from pipeline.yml ──────────────
// Same line-based mini-parser idiom as 02_detect_classify.groovy: no YAML library
// ships with QuPath's bundled Groovy. Only the keys this script needs are parsed.
def pipelineYml = new File(getProject().getBaseDirectory(), "pipeline.yml")
if (!pipelineYml.exists()) {
    println "ERROR: pipeline.yml not found at ${pipelineYml}"
    println "       Copy the repo-root pipeline.yml into the project and edit its channels."
    return
}

def stripComment = { String line ->
    int q = 0
    for (int i = 0; i < line.length(); i++) {
        char c = line.charAt(i)
        if (c == ('"' as char)) q++
        else if (c == ('#' as char) && q % 2 == 0) return line.substring(0, i)
    }
    return line
}
def indentOf = { String line -> line.length() - line.replaceAll(/^\s+/, "").length() }
def lines = pipelineYml.readLines().collect { stripComment(it) }

String anchorChannel = null
String mode = null
Double spanFrac = null
Double absolute = null
Integer resolutionLevel = null, smoothWindow = null
Double peakProminence = null
Map<String, Map> sliceOverrides = [:]

int i = 0
while (i < lines.size()) {
    def t = lines[i].trim()
    if (t.isEmpty()) { i++; continue }

    if (t == "anchor:") {
        int j = i + 1
        while (j < lines.size() && (lines[j].trim().isEmpty() || indentOf(lines[j]) > 0)) {
            def m = (lines[j].trim() =~ /^channel:\s*"([^"]+)"/)
            if (m.find()) anchorChannel = m.group(1)
            j++
        }
        i = j; continue
    }

    if (t == "detection_threshold:") {
        int j = i + 1
        while (j < lines.size() && (lines[j].trim().isEmpty() || indentOf(lines[j]) > 0)) {
            def s = lines[j].trim()
            def mMode = (s =~ /^mode:\s*"([^"]+)"/)
            def mFrac = (s =~ /^span_frac:\s*([0-9.eE+-]+)/)
            def mAbs  = (s =~ /^absolute:\s*([0-9.eE+-]+)/)
            def mRes  = (s =~ /^resolution_level:\s*([0-9]+)/)
            def mSm   = (s =~ /^smooth_window:\s*([0-9]+)/)
            def mProm = (s =~ /^peak_prominence:\s*([0-9.eE+-]+)/)
            if (mMode.find()) mode = mMode.group(1)
            if (mFrac.find()) spanFrac = mFrac.group(1) as Double
            if (mAbs.find())  absolute = mAbs.group(1) as Double
            if (mRes.find())  resolutionLevel = mRes.group(1) as Integer
            if (mSm.find())   smoothWindow = mSm.group(1) as Integer
            if (mProm.find()) peakProminence = mProm.group(1) as Double
            j++
        }
        i = j; continue
    }

    // Per-slice overrides -- TOP-LEVEL, never nested under detection_threshold (a
    // nested child `mode:` would be matched by the block reader above and clobber
    // the project-wide value for every section). Mirrors run_braian_detection.groovy
    // so calibration previews exactly what detection will do.
    if (t == "threshold_overrides:") {
        int j = i + 1
        String curKey = null
        while (j < lines.size() && (lines[j].trim().isEmpty() || indentOf(lines[j]) > 0)) {
            def raw = lines[j]
            def s = raw.trim()
            if (s.isEmpty()) { j++; continue }
            def mKey = (s =~ /^([^:\s][^:]*):\s*$/)
            if (indentOf(raw) <= 2 && mKey.find()) {
                curKey = mKey.group(1).replaceAll(/^["\']|["\']$/, "")
                sliceOverrides[curKey] = [:]
            } else if (curKey != null) {
                def oMode = (s =~ /^mode:\s*"([^"]+)"/)
                def oAbs  = (s =~ /^absolute:\s*([0-9.eE+-]+)/)
                def oFrac = (s =~ /^span_frac:\s*([0-9.eE+-]+)/)
                def oNote = (s =~ /^note:\s*"([^"]*)"/)
                if (oMode.find()) sliceOverrides[curKey].mode = oMode.group(1)
                if (oAbs.find())  sliceOverrides[curKey].absolute = oAbs.group(1) as Double
                if (oFrac.find()) sliceOverrides[curKey].span_frac = oFrac.group(1) as Double
                if (oNote.find()) sliceOverrides[curKey].note = oNote.group(1)
            }
            j++
        }
        i = j; continue
    }
    i++
}

def missing = []
if (anchorChannel == null)   missing << "anchor.channel"
if (mode == null)            missing << "detection_threshold.mode"
if (spanFrac == null)        missing << "detection_threshold.span_frac"
if (resolutionLevel == null) missing << "detection_threshold.resolution_level"
if (smoothWindow == null)    missing << "detection_threshold.smooth_window"
if (peakProminence == null)  missing << "detection_threshold.peak_prominence"
if (!missing.isEmpty()) {
    println "ERROR: pipeline.yml missing required key(s): ${missing}"
    println "       Add the detection_threshold block (see repo-root pipeline.yml). Aborting."
    return
}
if (!(mode in ["span_fraction", "absolute"])) {
    println "ERROR: detection_threshold.mode='${mode}' invalid -- must be \"span_fraction\" or \"absolute\". Aborting."
    return
}

var imageData = getCurrentImageData()
def imageName = getProjectEntry().getImageName()

// Apply this slice's override, if any, BEFORE reporting -- otherwise calibration
// shows the project default while detection uses something else.
String overrideKey = null
sliceOverrides.each { k, v -> if (overrideKey == null && imageName.contains(k)) overrideKey = k }
if (overrideKey != null) {
    def ov = sliceOverrides[overrideKey]
    if (ov.mode != null)      mode = ov.mode
    if (ov.span_frac != null) spanFrac = ov.span_frac
    if (ov.absolute != null)  absolute = ov.absolute
}

println "=" * 78
println "Threshold calibration -- ${imageName}"
if (overrideKey != null) {
    println "  PER-SLICE OVERRIDE : '${overrideKey}' from pipeline.yml threshold_overrides"
    if (sliceOverrides[overrideKey].note) println "    note: ${sliceOverrides[overrideKey].note}"
    println "    this slice does NOT use the project-wide rule"
}
println "  anchor channel : ${anchorChannel}"
println "  mode           : ${mode}   span_frac=${spanFrac}" + (mode == "absolute" ? "  absolute=${absolute}" : "")
println "  peak-finding   : resolutionLevel=${resolutionLevel} smoothWindow=${smoothWindow} prominence=${peakProminence}"

// ── Locate the two endpoints via BraiAn's own findThreshold ──────────────────
// nPeak=1 -> the background floor; nPeak=2 -> the next peak up, the bright nuclei.
// Using BraiAn's implementation (not our own peak finder) guarantees the numbers
// we report are the numbers detection would actually see.
var channel
try {
    channel = new ImageChannelTools(anchorChannel, imageData)   // (String, ImageData) ctor -- the (String, ImageServer) one NPEs in v1.1.0
} catch (Exception e) {
    println "ERROR: anchor channel '${anchorChannel}' not found in this image."
    println "       Channels present: " + imageData.getServer().getMetadata().getChannels().collect { it.getName() }
    println "       Fix anchor.channel in pipeline.yml to match exactly. Aborting."
    return
}

def peakAt = { int nPeak ->
    var p = new AutoThresholdParmameters()
    p.setResolutionLevel(resolutionLevel)
    p.setSmoothWindowSize(smoothWindow)
    p.setnPeak(nPeak)
    p.setPeakProminence(peakProminence)
    try { return WatershedCellDetectionConfig.findThreshold(channel, p) }
    catch (Exception e) { return null }
}

def floorVal  = peakAt(1)
def brightVal = peakAt(2)

if (floorVal == null) {
    println "ERROR: could not find even a background peak (nPeak=1)."
    println "       Most common cause: resolution_level != 0. Aborting."
    return
}
println "  background floor (nPeak=1) : ${floorVal}"
if (brightVal == null) {
    println "  bright peak      (nPeak=2) : NOT FOUND"
    println ""
    println "  Only one peak exists at prominence=${peakProminence}. Lower peak_prominence and"
    println "  re-run; if still absent, this channel has no bright-nuclei population and the"
    println "  span-fraction rule cannot be applied to it. Aborting."
    return
}
println "  bright peak      (nPeak=2) : ${brightVal}"

if (brightVal <= floorVal) {
    println "ERROR: bright peak (${brightVal}) <= background floor (${floorVal}) -- degenerate histogram. Aborting."
    return
}

double span = (brightVal - floorVal) as double
long chosen = mode == "absolute" ? Math.round(absolute)
                                 : Math.round(floorVal + spanFrac * span)

// ── Sweep: what the knob actually does on THIS section ──────────────────────
def sweepFracs = [0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50]
println ""
println "  span = ${brightVal} - ${floorVal} = ${span as long}"
println "  ---- span_frac sweep on this section ----"
println "     frac   threshold"
def sweepRows = []
sweepFracs.each { f ->
    long v = Math.round(floorVal + f * span)
    sweepRows << [frac: f, threshold: v]
    println String.format("    %5.2f   %6d%s", f, v, (Math.abs(f - spanFrac) < 1e-9 ? "   <-- pipeline.yml" : ""))
}
println ""
println "  CHOSEN THRESHOLD -> ${chosen}" + (mode == "absolute"
        ? "   (mode=absolute; does NOT generalize -- see pipeline.yml)"
        : "   (= ${floorVal} + ${spanFrac} x ${span as long})")

// ── Binned histogram for plotting ───────────────────────────────────────────
// Binned down from the native depth so the JSON stays small; the notebook plots
// bin centres. Uses the SAME resolution level as the peak finding above.
def histBins = []
try {
    var ip = channel.getImageProcessor(resolutionLevel)
    int[] full = ip.getHistogram()
    int nBins = 512
    int width = (int) Math.max(1, Math.ceil(full.length / (double) nBins))
    for (int b = 0; b * width < full.length; b++) {
        long c = 0
        int lo = b * width
        int hi = (int) Math.min(full.length, lo + width)
        for (int v = lo; v < hi; v++) c += full[v]
        histBins << [lo: lo, hi: hi - 1, count: c]
    }
    println "  histogram: ${full.length} native bins -> ${histBins.size()} plot bins (width ${width})"
} catch (Exception e) {
    println "  WARNING: could not read histogram for plotting (${e.message}); JSON will carry peaks + sweep only."
}

// ── Write JSON ──────────────────────────────────────────────────────────────
def invalidChars = (['<', '>', ':', '"', '/', '\\', '|', '?', '*'] as Set)
        .collect { java.util.regex.Pattern.quote(it) }.join('|')
def safeName = imageName.replaceAll(invalidChars, '')
def outFile = new File(buildPathInProject("results", safeName + "__threshold_calibration.json"))
outFile.getParentFile().mkdirs()

def esc = { String s -> s.replace("\\", "\\\\").replace('"', '\\"') }
def sb = new StringBuilder()
sb.append("{\n")
sb.append("  \"image\": \"").append(esc(imageName)).append("\",\n")
sb.append("  \"anchor_channel\": \"").append(esc(anchorChannel)).append("\",\n")
sb.append("  \"mode\": \"").append(esc(mode)).append("\",\n")
sb.append("  \"span_frac\": ").append(spanFrac).append(",\n")
sb.append("  \"resolution_level\": ").append(resolutionLevel).append(",\n")
sb.append("  \"smooth_window\": ").append(smoothWindow).append(",\n")
sb.append("  \"peak_prominence\": ").append(peakProminence).append(",\n")
sb.append("  \"floor\": ").append(floorVal).append(",\n")
sb.append("  \"bright_peak\": ").append(brightVal).append(",\n")
sb.append("  \"span\": ").append(span as long).append(",\n")
sb.append("  \"threshold\": ").append(chosen).append(",\n")
sb.append("  \"sweep\": [")
sb.append(sweepRows.collect { "{\"frac\": ${it.frac}, \"threshold\": ${it.threshold}}" }.join(", "))
sb.append("],\n")
sb.append("  \"histogram\": [")
sb.append(histBins.collect { "{\"lo\": ${it.lo}, \"hi\": ${it.hi}, \"count\": ${it.count}}" }.join(", "))
sb.append("]\n}\n")
outFile.text = sb.toString()

println ""
println "  wrote ${outFile}"
println "  -> plot it: notebooks/01_calibrate.ipynb section 3"
println "=" * 78
