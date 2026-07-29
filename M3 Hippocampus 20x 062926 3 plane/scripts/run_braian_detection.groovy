/**
 * run_braian_detection.groovy
 *
 * Runs BraiAnDetect (qupath-extension-braian v1.1.0) detection on the CURRENT image
 * using the project's BraiAn.yml, with the anchor-channel intensity threshold
 * RE-DERIVED FROM THIS SECTION'S OWN HISTOGRAM (see "SELF-CALIBRATING THRESHOLD"
 * below). Corrected copy of the extension's bundled
 * `compute_classify_overlap_export_exclude_detections.groovy`.
 *
 * WHY THIS COPY EXISTS (bug in the vendored example):
 *   The bundled script constructs `new ImageChannelTools(name, server)`. In v1.1.0 that
 *   (String, ImageServer) constructor leaves ImageChannelTools.imageData null, so the
 *   findNChannel() call inside the constructor throws:
 *     "Cannot invoke ImageData.getServerMetadata() because this.imageData is null" (line 40).
 *   Fix: pass `imageData` (the (String, ImageData) constructor) instead of `server`.
 *
 * SELF-CALIBRATING THRESHOLD (added 2026-07-29)
 *   BraiAn.yml's own two options both fail to generalize on our sections:
 *   `histogramThreshold` needs a distinct dim-nuclei peak that our data does not
 *   have, and a fixed `threshold:` is pinned to whichever section it was tuned on
 *   and silently under-detects on any dimmer one. So for the ANCHOR channel this
 *   script overrides whatever BraiAn.yml says with
 *
 *       threshold = floor + span_frac * (bright_peak - floor)
 *
 *   where floor and bright_peak are re-measured from THIS image's histogram via
 *   BraiAn's own findThreshold. `span_frac` comes from pipeline.yml. The cut
 *   therefore tracks staining/laser drift automatically, which is what keeps
 *   counts comparable across sections, animals and acquisitions.
 *
 *   Non-anchor channelDetections entries (if a project ever declares any) keep
 *   their BraiAn.yml values untouched.
 *
 *   To inspect or tune the fraction, run scripts/calibrate_threshold.groovy on one
 *   slice and plot it in notebooks/01_calibrate.ipynb section 3. Set
 *   detection_threshold.mode: "absolute" in pipeline.yml to opt out (not advised --
 *   it reintroduces the non-generalizing behaviour on purpose).
 *
 * CLASSIFICATION IS NOT DONE HERE. Every project's BraiAn.yml `classifiers:` block
 * is now empty by design; marker classification (nuclear / cytoplasmic / whole-cell
 * compartments, robust median + k_robust*1.4826*MAD per marker, Double+ derivation)
 * happens downstream in 02_detect_classify.groovy from pipeline.yml. This script
 * does DETECTION + per-channel makeMeasurements only. The classifier-application
 * loop below is retained solely so a project that re-populates `classifiers:` still
 * behaves as BraiAnDetect intends.
 *
 * USAGE
 *   1. Load ABBA regions first (01_load_abba_rois.groovy) -- detection is confined
 *      to the atlas Root annotation, else watershed floods background.
 *   2. Open the project, double-click the entry (or Run > Run for project).
 *   3. Run this script; then qc_detection_gates.groovy for the QC gates.
 *   4. To re-tune: edit pipeline.yml / BraiAn.yml, DELETE previous detections
 *      (Objects > Delete > Delete all detections), re-run.
 *
 * TOPOLOGY: single anchor channelDetections entry (nucleus-anchored, per CLAUDE.md).
 * detectionsCheck.controlChannel is null, so the OverlappingDetections step is
 * skipped -- Double+ arises downstream from per-marker classification on the same
 * anchor-derived object set, never from geometric overlap.
 *
 * @author section-pipeline (corrected from Carlo Castoldi, AGPL-3.0-or-later)
 */
import qupath.ext.braian.AtlasManager
import qupath.ext.braian.OverlappingDetections
import qupath.ext.braian.ImageChannelTools
import qupath.ext.braian.ChannelDetections
import qupath.ext.braian.config.ProjectsConfig
import qupath.ext.braian.config.AutoThresholdParmameters
import qupath.ext.braian.config.WatershedCellDetectionConfig
import static qupath.lib.scripting.QP.*

var imageData = getCurrentImageData()
var hierarchy = imageData.getHierarchy()
var config = ProjectsConfig.read("BraiAn.yml")
var annotations = config.getAnnotationsForDetections(hierarchy)

// ── Fail-loud guard: unregistered entries ───────────────────────────────────
// getAnnotationsForDetections returns annotations of BraiAn.yml's classForDetections
// (the ABBA atlas class). An entry that was never registered has none, so detection
// would be meaningless. This matters for "Run for project": a project can accumulate
// stray entries (wrong animal, wrong region, duplicate imports) that were imported
// but never registered, and they must not silently enter a batch run.
if (annotations == null || annotations.isEmpty()) {
    println "=" * 78
    println getCurrentImageName() + " : SKIPPED -- no '" + config.getClassForDetections() + "' annotations."
    println "  This entry is NOT atlas-registered. Either register it in ABBA and run"
    println "  01_load_abba_rois.groovy, or remove it from the project (it will keep"
    println "  being skipped, and it produces no exports, so it cannot reach the readout)."
    println "=" * 78
    return
}

// ── Self-calibrating anchor threshold (pipeline.yml detection_threshold) ─────
// Minimal line-based reader for just the keys needed here. The full pipeline.yml
// parser lives in 02_detect_classify.groovy; QuPath's bundled Groovy ships no YAML
// library and scripts cannot import each other, hence the narrow duplicate.
def pipelineYml = new File(getProject().getBaseDirectory(), "pipeline.yml")
if (!pipelineYml.exists()) {
    println "ERROR: pipeline.yml not found at ${pipelineYml} -- cannot calibrate the detection"
    println "       threshold. Copy the repo-root pipeline.yml into the project. Aborting."
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
def ymlLines = pipelineYml.readLines().collect { stripComment(it) }

String anchorChannel = null, thrMode = null
Double spanFrac = null, absoluteThr = null
Integer resLevel = null, smoothWin = null
Double prominence = null

int li = 0
while (li < ymlLines.size()) {
    def t = ymlLines[li].trim()
    if (t.isEmpty()) { li++; continue }
    if (t == "anchor:") {
        int j = li + 1
        while (j < ymlLines.size() && (ymlLines[j].trim().isEmpty() || indentOf(ymlLines[j]) > 0)) {
            def m = (ymlLines[j].trim() =~ /^channel:\s*"([^"]+)"/)
            if (m.find()) anchorChannel = m.group(1)
            j++
        }
        li = j; continue
    }
    if (t == "detection_threshold:") {
        int j = li + 1
        while (j < ymlLines.size() && (ymlLines[j].trim().isEmpty() || indentOf(ymlLines[j]) > 0)) {
            def s = ymlLines[j].trim()
            def mMode = (s =~ /^mode:\s*"([^"]+)"/)
            def mFrac = (s =~ /^span_frac:\s*([0-9.eE+-]+)/)
            def mAbs  = (s =~ /^absolute:\s*([0-9.eE+-]+)/)
            def mRes  = (s =~ /^resolution_level:\s*([0-9]+)/)
            def mSm   = (s =~ /^smooth_window:\s*([0-9]+)/)
            def mPr   = (s =~ /^peak_prominence:\s*([0-9.eE+-]+)/)
            if (mMode.find()) thrMode = mMode.group(1)
            if (mFrac.find()) spanFrac = mFrac.group(1) as Double
            if (mAbs.find())  absoluteThr = mAbs.group(1) as Double
            if (mRes.find())  resLevel = mRes.group(1) as Integer
            if (mSm.find())   smoothWin = mSm.group(1) as Integer
            if (mPr.find())   prominence = mPr.group(1) as Double
            j++
        }
        li = j; continue
    }
    li++
}

def missing = []
if (anchorChannel == null) missing << "anchor.channel"
if (thrMode == null)       missing << "detection_threshold.mode"
if (resLevel == null)      missing << "detection_threshold.resolution_level"
if (smoothWin == null)     missing << "detection_threshold.smooth_window"
if (prominence == null)    missing << "detection_threshold.peak_prominence"
if (thrMode == "span_fraction" && spanFrac == null) missing << "detection_threshold.span_frac"
if (thrMode == "absolute" && absoluteThr == null)   missing << "detection_threshold.absolute (required when mode=absolute)"
if (!missing.isEmpty()) {
    println "ERROR: pipeline.yml missing/invalid key(s): ${missing}. Aborting."
    return
}
if (!(thrMode in ["span_fraction", "absolute"])) {
    println "ERROR: detection_threshold.mode='${thrMode}' -- must be \"span_fraction\" or \"absolute\". Aborting."
    return
}

var anchorConf = config.channelDetections.find { it.name == anchorChannel }
if (anchorConf == null) {
    println "ERROR: BraiAn.yml declares no channelDetections entry named '${anchorChannel}'"
    println "       (pipeline.yml anchor.channel). Entries present: " +
            config.channelDetections.collect { it.name } + ". Aborting."
    return
}

long resolvedThreshold
if (thrMode == "absolute") {
    resolvedThreshold = Math.round(absoluteThr)
    println "THRESHOLD (mode=absolute): ${resolvedThreshold} on ${anchorChannel}"
    println "  WARNING: an absolute cut does not transfer across sections/acquisitions."
    println "  It will under-detect on any section dimmer than the one it was tuned on."
} else {
    var thrChannel = new ImageChannelTools(anchorChannel, imageData)
    def peakAt = { int nPeak ->
        var p = new AutoThresholdParmameters()
        p.setResolutionLevel(resLevel)
        p.setSmoothWindowSize(smoothWin)
        p.setnPeak(nPeak)
        p.setPeakProminence(prominence)
        try { return WatershedCellDetectionConfig.findThreshold(thrChannel, p) }
        catch (Exception e) { return null }
    }
    def floorVal = peakAt(1)
    def brightVal = peakAt(2)
    if (floorVal == null || brightVal == null || brightVal <= floorVal) {
        println "ERROR: could not calibrate a threshold on '${anchorChannel}' for this image."
        println "       floor(nPeak=1)=${floorVal}  bright(nPeak=2)=${brightVal}"
        println "       Run scripts/calibrate_threshold.groovy on this slice to diagnose"
        println "       (most common cause: peak_prominence too high, or resolution_level != 0)."
        println "       Refusing to fall back to a hardcoded value -- that is what made counts"
        println "       incomparable in the first place. Aborting."
        return
    }
    resolvedThreshold = Math.round(floorVal + spanFrac * (double) (brightVal - floorVal))
    println "THRESHOLD (mode=span_fraction) on ${anchorChannel}: ${resolvedThreshold}"
    println "  = floor ${floorVal} + ${spanFrac} x span ${brightVal - floorVal}   (bright peak ${brightVal})"
    println "  re-derived from THIS section's histogram; BraiAn.yml's own threshold value is ignored."
}

// Set BOTH: an explicit absolute threshold AND histogramThreshold=null, so that
// whatever precedence WatershedCellDetectionConfig.build() applies internally,
// only the value computed above can be used.
anchorConf.parameters.setThreshold(resolvedThreshold as double)
anchorConf.parameters.setHistogramThreshold(null)

// COMPUTE CHANNEL DETECTIONS -- pass imageData (NOT server): the (String, ImageServer)
// ctor in braian v1.1.0 leaves ImageChannelTools.imageData null -> NPE in findNChannel.
var allDetections = config.channelDetections.collect { detectionsConf ->
    var channel = new ImageChannelTools(detectionsConf.name, imageData)
    try {
        new ChannelDetections(channel, annotations, detectionsConf.parameters, hierarchy)
    } catch (IllegalArgumentException ignored) {
        null
    }
}.findAll { it != null }

if (allDetections.isEmpty()) {
    println getCurrentImageName()+" : DONE! No annotations found to compute on"
    return
}

// CLASSIFY CHANNEL DETECTIONS -- no-op while every `classifiers:` block is empty
// (the current design; 02_detect_classify.groovy does classification instead).
allDetections.forEach { detections ->
    var detectionsConfig = config.channelDetections.find { it.name == detections.getId() }
    if (detectionsConfig.classifiers == null) return
    var partialClassifiers = detectionsConfig.classifiers.collect { it.toPartialClassifier(hierarchy) }
    detections.applyClassifiers(partialClassifiers, imageData)
}

// OVERLAPS -- skipped when detectionsCheck.controlChannel is null (nucleus-anchored topology)
var overlaps = []
Optional<String> control
if ((control = config.getControlChannel()).isPresent()) {
    String controlChannelName = control.get()
    var controlChannel = allDetections.find { it.getId() == controlChannelName }
    var otherChannels = allDetections.findAll { it.getId() != controlChannelName }
    overlaps = [new OverlappingDetections(controlChannel, otherChannels, true, hierarchy)]
}

// EXPORT RESULTS (only if the Allen atlas is imported)
var atlasName = "allen_mouse_10um_java"
if (AtlasManager.isImported(atlasName, hierarchy)) {
    var atlas = new AtlasManager(atlasName, hierarchy)
    def invalidChars = (['<', '>', ':', '"', '/', '\\', '|', '?', '*'] as Set).collect { java.util.regex.Pattern.quote(it) }.join('|')
    def imageName = getProjectEntry().getImageName().replaceAll(invalidChars, '')
    var resultsFile = new File(buildPathInProject("results", imageName + "_regions.tsv"))
    atlas.saveResults(allDetections + overlaps, resultsFile)
    def exclusionsFile = new File(buildPathInProject("regions_to_exclude", imageName + "_regions_to_exclude.txt"))
    atlas.fixExclusions()
    atlas.saveExcludedRegions(exclusionsFile)

    // Provenance: the threshold actually used, next to the counts it produced.
    // Without this, a re-run months later cannot tell which cut made which numbers.
    def provFile = new File(buildPathInProject("results", imageName + "__detection_threshold.tsv"))
    provFile.text = "image\tanchor_channel\tmode\tspan_frac\tthreshold\n" +
            "${getProjectEntry().getImageName()}\t${anchorChannel}\t${thrMode}\t" +
            "${thrMode == 'span_fraction' ? spanFrac : ''}\t${resolvedThreshold}\n"
}

println getCurrentImageName()+" : DONE!  (anchor threshold ${resolvedThreshold})"
