/**
 * roi_count.groovy — count cells inside HAND-DRAWN ROIs, in QuPath, one button.
 *
 * WHAT THIS IS
 *   The manual counterpart to the whole-brain route. You open an image, draw one or
 *   more ROIs by eye, press Run, and get: nuclei detected inside those ROIs, marker
 *   classification, and CSVs of the counts. No ABBA, no atlas, no registration, no
 *   BraiAn.yml — just the image and your shapes.
 *
 *   It reuses the whole-brain route's ACTUAL machinery, not an imitation of it:
 *     * segmentation   BraiAnDetect's ChannelDetections, the same watershed the
 *                      registered route runs, pointed at your annotations instead
 *                      of the atlas Root (a supported constructor, not a hack)
 *     * threshold      floor + span_frac x (bright - floor), re-measured per image
 *                      from its own histogram, using BraiAn's own peak finder
 *     * measurement    nucleus-anchored compartments (nuclear / cytoplasmic ring /
 *                      whole-cell), each with the local-background-subtracted
 *                      annulus measure — the SSp-autofluorescence fix
 *     * positivity     robust self-calibrating cut, median + k*1.4826*MAD, per marker
 *     * colocalization nucleus-anchored only; Double+ means one nucleus called
 *                      positive for >=2 markers. Never proximity or overlap.
 *
 *   The marker set itself is NOT redeclared here. It is read from `pipeline.yml`,
 *   the same file the registered route reads, so a project has exactly one place
 *   that says which markers exist and how each is measured.
 *
 * WHAT THE OPERATOR SEES IS THE GROUND TRUTH
 *   Every number this script produces is meant to be checked against the image with
 *   the detections overlaid. That is why:
 *     * it prints the three candidate anchor thresholds — whole-image, in-ROI, and
 *       your absolute — BEFORE committing to one, so you can see them disagree
 *     * "Classify + export only" re-runs the marker cut in seconds without
 *       re-detecting, so tuning k is something you do while looking, not a 30-minute
 *       round trip
 *     * every setting used is written next to the counts it produced
 *   If the detections look wrong, they ARE wrong, whatever the numbers say. Change
 *   the settings until the overlay looks right; do not reason the overlay away.
 *
 * ACQUISITION VARIES HERE, AND THAT IS THE POINT (operator, 2026-08-05)
 *   Images counted this way may differ drastically in magnification, Z handling and
 *   intensity. So settings are stored PER IMAGE in `roi_settings.yml`, seeded from
 *   `defaults:` but never silently shared: an image that has been tuned keeps its own
 *   block, and re-running reproduces it exactly.
 *
 *   Two consequences this script enforces rather than assumes:
 *     1. Micron-denominated parameters (sigma, min/max area, expansion, ring) are
 *        reported in PIXELS for the current image, because that is what decides
 *        whether segmentation can work at all. A 10 um nucleus is 22 px across at
 *        0.46 um/px and 5 px across at 2.0 um/px — the same sigma is a different
 *        operation.
 *     2. Counts carry a settings_hash. Rows with different hashes were produced by
 *        different rules and must not be pooled without saying so. The notebook
 *        flags it; nothing here refuses to run.
 *
 * WHAT IT WRITES  (all under <project>/results/roi/)
 *   <stem>__percell_export.tsv   one row per cell. Deliberately the SAME schema the
 *                                registered route emits, so scripts/cockpit_marker_gui.py
 *                                (set k by eye) works on ROI data with no changes.
 *                                `region_label` carries the ROI name.
 *   <stem>__roi_counts.tsv       one row per drawn shape + one pooled row per ROI name.
 *   roi_counts_combined.csv      growing, one row per (image x roi x class), with the
 *                                full settings provenance on every row.
 *
 * HOW TO USE
 *   1. Open the image in QuPath. Draw ROIs (rectangle, polygon, brush — any area tool).
 *      Name them in the Annotations pane if you want named regions; unnamed shapes are
 *      auto-named ROI_1, ROI_2, ... and the name is written back so what you see in
 *      QuPath matches the CSV.
 *   2. Run this script (Automate > Script editor > Run).
 *   3. A settings dialog appears, seeded from this image's saved block if it has one.
 *      Adjust, press OK.
 *   4. Look at the result. Not happy? Re-run — "Classify + export only" skips detection.
 *
 *   Selecting annotations before running restricts counting to the selection.
 *   Selecting nothing counts every top-level area annotation on the image.
 *
 * SAFE TO RE-RUN. Detections inside the target ROIs are cleared and rebuilt; nothing
 * outside them is touched. This script never reads or writes any atlas artifact, and
 * never touches pipeline.yml.
 *
 * @author section-pipeline
 */
import qupath.ext.braian.ChannelDetections
import qupath.ext.braian.ChannelHistogram
import qupath.ext.braian.ImageChannelTools
import qupath.ext.braian.config.AutoThresholdParmameters
import qupath.ext.braian.config.WatershedCellDetectionConfig
import qupath.lib.analysis.features.ObjectMeasurements
import qupath.lib.analysis.features.ObjectMeasurements.Compartments
import qupath.lib.analysis.features.ObjectMeasurements.Measurements
import qupath.lib.awt.common.BufferedImageTools
import qupath.lib.gui.dialogs.Dialogs
import qupath.lib.objects.PathObjects
import qupath.lib.plugins.parameters.ParameterList
import qupath.lib.regions.ImageRegion
import qupath.lib.regions.RegionRequest
import qupath.lib.roi.RoiTools
import ij.process.ByteProcessor
import ij.process.ShortProcessor
import static qupath.lib.scripting.QP.*

// ═══════════════════════════════════════════════════════════════════════════════
// 0. HANDLES, CALIBRATION, CHANNELS
// ═══════════════════════════════════════════════════════════════════════════════
def imageData = getCurrentImageData()
def server = imageData.getServer()
def hierarchy = imageData.getHierarchy()
def project = getProject()
def entry = getProjectEntry()
def imageName = entry != null ? entry.getImageName() : server.getMetadata().getName()

println "=" * 78
println "roi_count — manual-ROI cell counting"
println "image: ${imageName}"

// Pixel size is not optional here. Every segmentation parameter below is denominated
// in microns, so an uncalibrated image would silently be segmented at whatever scale
// the numbers happen to mean — the failure mode that makes counts from two
// magnifications look comparable when they are not.
def cal = server.getPixelCalibration()
if (cal == null || !cal.hasPixelSizeMicrons()) {
    println "ERROR: this image has no pixel calibration, so micron-denominated"
    println "       parameters (sigma, min/max area, cell expansion, ring) have no"
    println "       meaning on it. Set the pixel size (Image tab > Set pixel size),"
    println "       or re-export the image with PhysicalSizeX in its OME-XML, then re-run."
    throw new RuntimeException("roi_count: no pixel calibration on ${imageName}")
}
double pixelUm = cal.getAveragedPixelSizeMicrons()
double pxToUm2 = pixelUm * pixelUm
double pxToMm2 = pxToUm2 / 1e6

def channelNames = server.getMetadata().getChannels().collect { it.getName() }
int nZ = server.nZSlices()
int nT = server.nTimepoints()
println "pixel size: ${String.format('%.6g', pixelUm)} um/px   channels: ${channelNames}   Z-planes: ${nZ}"

// ═══════════════════════════════════════════════════════════════════════════════
// 1. MARKER SET — read from pipeline.yml (the SAME declaration the registered route uses)
// ═══════════════════════════════════════════════════════════════════════════════
// One place declares which markers exist and which compartment each is measured on.
// Duplicating that here is how a project ends up classifying the same cells by two
// different rules (CLAUDE.md, "one classification path"), so this script reads the
// existing file rather than introducing a second marker declaration.
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

def pipelineYmlFile = new File(project.getBaseDirectory(), "pipeline.yml")
if (!pipelineYmlFile.exists()) {
    println "ERROR: pipeline.yml not found at ${pipelineYmlFile}."
    println "       It declares the marker set (anchor + markers + compartments + ring)."
    println "       Copy the repo-root pipeline.yml into this project and edit the"
    println "       channel names to match this image, or run:"
    println "           python3 scripts/sync_project.py --project \"${project.getBaseDirectory()}\""
    throw new RuntimeException("roi_count: pipeline.yml missing")
}
def ymlLines = pipelineYmlFile.readLines().collect { stripComment(it) }

String anchorName = null, anchorChannel = null
def markers = []
Double kRobustGlobal = null
Double gapUm = null, widthUm = null
int li = 0
while (li < ymlLines.size()) {
    def t = ymlLines[li].trim()
    if (t.isEmpty()) { li++; continue }
    if (t == "anchor:") {
        int j = li + 1
        while (j < ymlLines.size() && (ymlLines[j].trim().isEmpty() || indentOf(ymlLines[j]) > 0)) {
            def s = ymlLines[j].trim()
            def mName = (s =~ /^name:\s*"([^"]+)"/)
            def mChan = (s =~ /^channel:\s*"([^"]+)"/)
            if (mName.find()) anchorName = mName.group(1)
            if (mChan.find()) anchorChannel = mChan.group(1)
            j++
        }
        li = j; continue
    }
    if (t == "markers:") {
        int j = li + 1
        def current = null
        while (j < ymlLines.size() && (ymlLines[j].trim().isEmpty() || indentOf(ymlLines[j]) > 0)) {
            def s = ymlLines[j].trim()
            def mNew = (s =~ /^-\s*name:\s*"([^"]+)"/)
            if (mNew.find()) {
                if (current != null) markers << current
                current = [name: mNew.group(1), channel: null, compartment: null, k_robust: null]
            } else if (current != null) {
                def mChan = (s =~ /^channel:\s*"([^"]+)"/)
                def mComp = (s =~ /^compartment:\s*"([^"]+)"/)
                def mKm   = (s =~ /^k_robust:\s*([0-9.eE+-]+)/)
                if (mChan.find()) current.channel = mChan.group(1)
                if (mComp.find()) current.compartment = mComp.group(1)
                if (mKm.find())   current.k_robust = mKm.group(1) as Double
            }
            j++
        }
        if (current != null) markers << current
        li = j; continue
    }
    if (t == "ring:") {
        int j = li + 1
        while (j < ymlLines.size() && (ymlLines[j].trim().isEmpty() || indentOf(ymlLines[j]) > 0)) {
            def s = ymlLines[j].trim()
            def mGap = (s =~ /^gap_um:\s*([0-9.eE+-]+)/)
            def mWid = (s =~ /^width_um:\s*([0-9.eE+-]+)/)
            if (mGap.find()) gapUm = mGap.group(1) as Double
            if (mWid.find()) widthUm = mWid.group(1) as Double
            j++
        }
        li = j; continue
    }
    def mK = (t =~ /^k_robust:\s*([0-9.eE+-]+)/)
    if (mK.find()) { kRobustGlobal = mK.group(1) as Double; li++; continue }
    li++
}

def missingKeys = []
if (anchorName == null)    missingKeys << "anchor.name"
if (anchorChannel == null) missingKeys << "anchor.channel"
if (markers.isEmpty())     missingKeys << "markers (empty or missing)"
markers.eachWithIndex { m, idx ->
    if (m.channel == null)     missingKeys << "markers[${idx}].channel (name=${m.name})"
    if (m.compartment == null) missingKeys << "markers[${idx}].compartment (name=${m.name})"
    else if (!(m.compartment in ["nuclear", "cytoplasmic", "whole-cell"]))
        missingKeys << "markers[${idx}].compartment='${m.compartment}' (must be nuclear, cytoplasmic or whole-cell)"
}
if (kRobustGlobal == null) missingKeys << "k_robust"
if (gapUm == null)         missingKeys << "ring.gap_um"
if (widthUm == null)       missingKeys << "ring.width_um"
if (!missingKeys.isEmpty()) {
    println "ERROR: pipeline.yml is missing/invalid key(s): ${missingKeys}. Aborting."
    throw new RuntimeException("roi_count: invalid pipeline.yml — see message above")
}

// Channels declared must actually exist on THIS image. Different acquisitions name
// their channels differently, and a typo here produces NaN measurements for every
// cell rather than an error, so it is checked before anything expensive runs.
def declaredChannels = ([anchorChannel] + markers.collect { it.channel }) as Set
def missingChannels = declaredChannels.findAll { !channelNames.contains(it) }
if (!missingChannels.isEmpty()) {
    println "ERROR: pipeline.yml declares channel(s) absent from this image: ${missingChannels}"
    println "       This image's channels: ${channelNames}"
    println "       Fix the channel names in pipeline.yml (they differ between acquisitions)."
    throw new RuntimeException("roi_count: channel mismatch on ${imageName}")
}
def COMPARTMENT_LABELS = [nuclear: "Nucleus", cytoplasmic: "Cytoplasm", "whole-cell": "Cell"]
boolean emitDouble = markers.size() >= 2
println "markers (from pipeline.yml): anchor=${anchorName}/${anchorChannel}, " +
        markers.collect { "${it.name}/${it.channel}/${it.compartment}" }.join(", ")

// ═══════════════════════════════════════════════════════════════════════════════
// 2. roi_settings.yml — per-image segmentation settings, self-scaffolding
// ═══════════════════════════════════════════════════════════════════════════════
// Kept SEPARATE from pipeline.yml on purpose. pipeline.yml answers "what markers are
// on this slide-set" and is stable; this file answers "how was THIS image segmented"
// and legitimately differs per image, because magnification, Z handling and intensity
// differ per image. Mixing them would make the marker set look image-specific.
def SETTING_KEYS = [
    "threshold_mode", "span_frac", "absolute", "resolution_level", "smooth_window",
    "peak_prominence", "requested_pixel_size_um", "background_radius_um",
    "background_by_reconstruction", "median_radius_um", "sigma_um", "min_area_um2",
    "max_area_um2", "cell_expansion_um", "watershed_post_process", "smooth_boundaries",
    "k_scope",
]
def BOOL_KEYS = ["background_by_reconstruction", "watershed_post_process", "smooth_boundaries"] as Set
def STR_KEYS  = ["threshold_mode", "k_scope"] as Set

// Built-in seeds. Physical (micron) quantities, so they carry across magnification in
// the only sense they can — they describe a nucleus, not a pixel count. Section 5
// re-expresses them in pixels for this image, which is where a bad fit shows up.
def BUILTIN = [
    threshold_mode              : "image_span",
    span_frac                   : 0.25d,
    absolute                    : 0.0d,
    resolution_level            : 0,
    smooth_window               : 15,
    peak_prominence             : 100.0d,
    requested_pixel_size_um     : 0.0d,     // 0 = use the image's own size, no resampling
    background_radius_um        : 10.0d,
    background_by_reconstruction: true,
    median_radius_um            : 0.0d,
    sigma_um                    : 2.0d,
    min_area_um2                : 20.0d,
    max_area_um2                : 250.0d,
    cell_expansion_um           : 5.0d,
    watershed_post_process      : true,
    smooth_boundaries           : true,
    k_scope                     : "image",
]

def settingsFile = new File(project.getBaseDirectory(), "roi_settings.yml")

/** Parse roi_settings.yml into [defaults: Map, images: [name -> Map]]. Tolerates absence. */
def parseSettings = { File f ->
    def out = [defaults: [:], images: [:] as LinkedHashMap]
    if (!f.exists()) return out
    def lines = f.readLines().collect { stripComment(it) }
    def coerce = { String key, String val ->
        val = val.trim().replaceAll(/^["']|["']$/, "")
        if (val.isEmpty() || val == "null") return null
        if (BOOL_KEYS.contains(key)) return val.toLowerCase() in ["true", "yes", "on"]
        if (STR_KEYS.contains(key)) return val
        if (key in ["resolution_level", "smooth_window"]) return val as Integer
        if (key.startsWith("k_")) return val as Double
        try { return val as Double } catch (Exception ignored) { return val }
    }
    int i = 0
    while (i < lines.size()) {
        def t = lines[i].trim()
        if (t == "defaults:") {
            int j = i + 1
            while (j < lines.size() && (lines[j].trim().isEmpty() || indentOf(lines[j]) > 0)) {
                def m = (lines[j].trim() =~ /^([A-Za-z_][A-Za-z0-9_]*):\s*(.*)$/)
                if (m.find()) {
                    def v = coerce(m.group(1), m.group(2))
                    if (v != null) out.defaults[m.group(1)] = v
                }
                j++
            }
            i = j; continue
        }
        if (t == "images:") {
            int j = i + 1
            String cur = null
            while (j < lines.size() && (lines[j].trim().isEmpty() || indentOf(lines[j]) > 0)) {
                def raw = lines[j]
                def s = raw.trim()
                if (s.isEmpty()) { j++; continue }
                def mKey = (s =~ /^(.+?):\s*$/)
                if (indentOf(raw) <= 2 && mKey.find()) {
                    cur = mKey.group(1).trim().replaceAll(/^["']|["']$/, "")
                    out.images[cur] = [:]
                } else if (cur != null) {
                    def m = (s =~ /^([A-Za-z_][A-Za-z0-9_]*):\s*(.*)$/)
                    if (m.find()) {
                        String k = m.group(1)
                        String rawVal = m.group(2).trim()
                        if (k == "note" || k == "marker_k") {
                            out.images[cur][k] = rawVal.replaceAll(/^["']|["']$/, "")
                        } else {
                            def v = coerce(k, rawVal)
                            if (v != null) out.images[cur][k] = v
                        }
                    }
                }
                j++
            }
            i = j; continue
        }
        i++
    }
    return out
}

def stored = parseSettings(settingsFile)

// Which stored block applies to this image: exact name first, then the first key that
// is a substring of it (so "s1" can carry a whole family without retyping the full
// OME-TIFF name). Printed, because a silently-matched block is a silently-different rule.
String settingsKey = null
if (stored.images.containsKey(imageName)) settingsKey = imageName
else stored.images.keySet().each { k -> if (settingsKey == null && k && imageName.contains(k)) settingsKey = k }

def resolved = [:]
SETTING_KEYS.each { k -> resolved[k] = BUILTIN[k] }
stored.defaults.each { k, v -> if (SETTING_KEYS.contains(k)) resolved[k] = v }
if (settingsKey != null) {
    println "settings: matched saved block '${settingsKey}' for this image"
    stored.images[settingsKey].each { k, v -> if (SETTING_KEYS.contains(k)) resolved[k] = v }
    // A block saved at a different pixel size describes a different physical
    // segmentation. Carrying it silently is the cross-magnification bug this whole
    // per-image design exists to prevent, so say so and let the operator judge.
    def savedPx = stored.images[settingsKey]["pixel_um"]
    if (savedPx != null && Math.abs((savedPx as double) - pixelUm) > 1e-6) {
        println "  WARNING: that block was saved at ${savedPx} um/px; this image is ${pixelUm} um/px."
        println "  Area and expansion parameters describe a nucleus in PIXELS as well as microns,"
        println "  so they may not transfer. Check the overlay before trusting the counts."
    }
} else if (!stored.images.isEmpty()) {
    println "settings: no saved block for this image — using defaults (blocks on file: ${stored.images.keySet()})"
} else {
    println "settings: no saved blocks yet — using built-in defaults, seeded for ${pixelUm} um/px"
}

// Per-marker positivity settings live alongside, keyed by marker name. `k` is the
// robust multiplier; `absolute_bgsub` overrides it outright with a cut you set by eye.
def markerSettings = [:]
markers.each { m ->
    double kSeed = (m.k_robust != null) ? (m.k_robust as double) : (kRobustGlobal as double)
    markerSettings[m.name] = [k: kSeed, absolute_bgsub: null]
}
[stored.defaults, (settingsKey != null ? stored.images[settingsKey] : [:])].each { blk ->
    blk.each { k, v ->
        def mk = (k =~ /^k_(.+)$/)
        if (mk.find() && markerSettings.containsKey(mk.group(1))) markerSettings[mk.group(1)].k = v as double
        def ma = (k =~ /^abs_(.+)$/)
        if (ma.find() && markerSettings.containsKey(ma.group(1))) markerSettings[ma.group(1)].absolute_bgsub = v as double
    }
}

// ═══════════════════════════════════════════════════════════════════════════════
// 3. TARGET ROIs — what the operator drew
// ═══════════════════════════════════════════════════════════════════════════════
// Selection wins when there is one; otherwise every top-level area annotation counts.
// Top-level is the right test: a hand-drawn shape sits at the root, while BraiAnDetect's
// own detection containers are always children of the shape they were detected in.
def selected = getSelectedObjects().findAll { it.isAnnotation() && it.getROI() != null && it.getROI().isArea() }
def targets
if (!selected.isEmpty()) {
    targets = new ArrayList(selected)
    println "ROIs: using the ${targets.size()} selected annotation(s)"
} else {
    targets = getAnnotationObjects().findAll { ann ->
        def roi = ann.getROI()
        roi != null && roi.isArea() && (ann.getParent() == null || !ann.getParent().isAnnotation())
    }
    println "ROIs: nothing selected — using all ${targets.size()} top-level area annotation(s)"
}
if (targets.isEmpty()) {
    println ""
    println "NOTHING TO COUNT. Draw at least one area ROI (rectangle, polygon, brush or"
    println "wand) on this image and run again. To count only some of the shapes on the"
    println "image, select them first."
    throw new RuntimeException("roi_count: no ROI annotations on ${imageName}")
}

// Name every shape, and write the name back so QuPath's Annotations pane shows exactly
// what the CSV will say. An unnamed shape in a spreadsheet is an uncheckable number.
int autoIdx = 0
targets.each { ann ->
    if (ann.getName() == null || ann.getName().trim().isEmpty()) {
        autoIdx++
        ann.setName("ROI_${autoIdx}")
    }
}
fireHierarchyUpdate()

// Overlapping shapes double-count: a nucleus inside both is counted in both rows.
// Advisory, because overlapping ROIs are sometimes exactly what you want (a subregion
// inside a region), and the pooled rollup is what would mislead.
def overlapping = []
for (int a = 0; a < targets.size(); a++) {
    for (int b = a + 1; b < targets.size(); b++) {
        def ra = targets[a].getROI(), rb = targets[b].getROI()
        if (ra.getImagePlane() != rb.getImagePlane()) continue
        if (ra.getGeometry().intersects(rb.getGeometry()))
            overlapping << "${targets[a].getName()} / ${targets[b].getName()}"
    }
}
targets.each { ann ->
    def r = ann.getROI()
    println String.format("  %-24s  %10.1f um^2   z=%d", ann.getName(), r.getArea() * pxToUm2, r.getImagePlane().getZ())
}
if (!overlapping.isEmpty()) {
    println "  NOTE: these ROI pairs overlap, so cells in the shared area are counted in both:"
    overlapping.each { println "        ${it}" }
    println "        Per-shape rows are still correct individually; the pooled rows sum them."
}

// ═══════════════════════════════════════════════════════════════════════════════
// 4. SETTINGS DIALOG
// ═══════════════════════════════════════════════════════════════════════════════
// The dialog IS the tuning interface — everything adjustable is here, seeded from what
// this image last used, so tuning never means editing YAML by hand. Skipped
// automatically when QuPath is running headless (batch/CLI), where the saved settings
// are used verbatim.
boolean headless = false
try {
    headless = (qupath.lib.gui.QuPathGUI.getInstance() == null)
} catch (Throwable ignored) {
    headless = true
}

// ── Script arguments (QuPath `-a`) ─────────────────────────────────────────────
// Two ways to run this matter, and they want opposite defaults.
//
//   ONE IMAGE, in the GUI      the dialog IS the interface; you are tuning while looking
//   A WHOLE FOLDER, re-run     settings are already decided and saved per image; a dialog
//                              per image would be twenty dialogs and no decisions
//
// "Run for project" from the Script editor takes the first path and will prompt once per
// image -- usually what you want here, since the per-image settings are the point. For
// the second, pass arguments:
//
//   QuPath script -p <project> -s -a no-dialog -a stage=classify scripts/roi_count.groovy
//
// stage= accepts full | classify | export. Unknown values abort rather than silently
// running the expensive stage.
def scriptArgs = []
try {
    if (binding.hasVariable("args") && args != null) scriptArgs = (args as List).collect { it.toString() }
} catch (Throwable ignored) { }
if (!scriptArgs.isEmpty()) println "script args: ${scriptArgs}"
if (scriptArgs.any { it == "no-dialog" }) headless = true

def STAGE_FULL = "Detect + classify + export"
def STAGE_CLASSIFY = "Classify + export only (keep detections)"
def STAGE_EXPORT = "Export only (keep classes)"
String stage = STAGE_FULL
def THRESHOLD_MODES = ["image_span", "roi_span", "absolute"]

if (!headless) {
    def params = new ParameterList()
        .addChoiceParameter("stage", "Stage", STAGE_FULL, [STAGE_FULL, STAGE_CLASSIFY, STAGE_EXPORT],
            "Detection is the slow step. Tuning marker positivity only needs the second option.")
        .addTitleParameter("Anchor threshold (${anchorChannel}) — which pixels are nucleus")
        .addChoiceParameter("threshold_mode", "Mode", resolved.threshold_mode as String, THRESHOLD_MODES,
            "image_span: the whole-brain route's rule, measured on the WHOLE image. " +
            "roi_span: the same rule measured only inside your ROIs. " +
            "absolute: a number you set by eye.")
        .addDoubleParameter("span_frac", "Span fraction", resolved.span_frac as double, "",
            "Used by image_span and roi_span. cut = floor + frac x (bright - floor). Higher = stricter.")
        .addDoubleParameter("absolute", "Absolute cut", resolved.absolute as double, "",
            "Used by absolute mode only. Set it in notebooks/04_roi.ipynb by looking at the mask.")
        .addIntParameter("resolution_level", "Histogram resolution level", resolved.resolution_level as int, "",
            "0 = full resolution. Higher levels bin more coarsely, which keeps the peak finder out of background wrinkles.")
        .addIntParameter("smooth_window", "Histogram smoothing window", resolved.smooth_window as int, "", "")
        .addDoubleParameter("peak_prominence", "Peak prominence", resolved.peak_prominence as double, "", "")
        .addTitleParameter("Segmentation — tune these first when the overlay looks wrong")
        .addDoubleParameter("sigma_um", "Sigma", resolved.sigma_um as double, "um",
            "Smoothing scale. The first knob to move at an unfamiliar magnification.")
        .addDoubleParameter("min_area_um2", "Min nucleus area", resolved.min_area_um2 as double, "um^2", "")
        .addDoubleParameter("max_area_um2", "Max nucleus area", resolved.max_area_um2 as double, "um^2", "")
        .addDoubleParameter("background_radius_um", "Background radius", resolved.background_radius_um as double, "um", "")
        .addDoubleParameter("median_radius_um", "Median filter radius", resolved.median_radius_um as double, "um", "")
        .addDoubleParameter("cell_expansion_um", "Cell expansion", resolved.cell_expansion_um as double, "um",
            "Builds the cytoplasm/whole-cell compartment. Required for non-nuclear markers.")
        .addBooleanParameter("watershed_post_process", "Watershed post-process", resolved.watershed_post_process as boolean)
        .addBooleanParameter("smooth_boundaries", "Smooth boundaries", resolved.smooth_boundaries as boolean)
        .addBooleanParameter("background_by_reconstruction", "Background by reconstruction", resolved.background_by_reconstruction as boolean)
        .addTitleParameter("Marker positivity — cut = median + k x 1.4826 x MAD")
    markers.each { m ->
        params.addDoubleParameter("k_${m.name}", "k for ${m.name}", markerSettings[m.name].k as double, "",
                "Lower catches dimmer ${m.name}+ cells; higher is stricter. Set it by eye in the notebook.")
        params.addDoubleParameter("abs_${m.name}", "…or absolute ${m.name} bg-sub cut",
                (markerSettings[m.name].absolute_bgsub ?: 0.0d) as double, "",
                "0 = use k above. Any other value overrides k with a cut you chose by looking.")
    }
    params.addChoiceParameter("k_scope", "Derive marker cuts from", resolved.k_scope as String, ["image", "roi"],
            "image: one cut from all cells in all ROIs (comparable between ROIs — recommended). " +
            "roi: a separate cut per ROI (each self-calibrating, NOT comparable between ROIs).")

    if (!Dialogs.showParameterDialog("Manual ROI counting — ${imageName}", params)) {
        println "Cancelled by the operator. Nothing was changed."
        return
    }
    stage = params.getChoiceParameterValue("stage") as String
    ["span_frac", "absolute", "peak_prominence", "sigma_um", "min_area_um2", "max_area_um2",
     "background_radius_um", "median_radius_um", "cell_expansion_um"].each {
        resolved[it] = params.getDoubleParameterValue(it) as double
    }
    ["resolution_level", "smooth_window"].each { resolved[it] = params.getIntParameterValue(it) as int }
    ["watershed_post_process", "smooth_boundaries", "background_by_reconstruction"].each {
        resolved[it] = params.getBooleanParameterValue(it) as boolean
    }
    resolved.threshold_mode = params.getChoiceParameterValue("threshold_mode") as String
    resolved.k_scope = params.getChoiceParameterValue("k_scope") as String
    markers.each { m ->
        markerSettings[m.name].k = params.getDoubleParameterValue("k_${m.name}") as double
        double abs = params.getDoubleParameterValue("abs_${m.name}") as double
        markerSettings[m.name].absolute_bgsub = (abs != 0.0d) ? abs : null
    }
} else {
    println "settings: no dialog — using this image's saved settings without prompting"
}

// stage= applies whether or not the dialog ran, so a batch can re-classify without
// re-detecting exactly as the dialog's Stage control does.
def stageArg = scriptArgs.find { it.startsWith("stage=") }?.substring(6)
if (stageArg != null) {
    def stageMap = ["full": STAGE_FULL, "classify": STAGE_CLASSIFY, "export": STAGE_EXPORT]
    if (!stageMap.containsKey(stageArg)) {
        println "ERROR: stage=${stageArg} is not one of ${stageMap.keySet()}."
        println "       Refusing to guess -- 'full' re-detects and costs real time."
        throw new RuntimeException("roi_count: unknown stage argument '${stageArg}'")
    }
    stage = stageMap[stageArg]
    println "stage (from args): ${stage}"
}

// ═══════════════════════════════════════════════════════════════════════════════
// 5. ACQUISITION ADVISORY — the micron parameters, expressed in this image's pixels
// ═══════════════════════════════════════════════════════════════════════════════
// Micron parameters are the right way to write these down, but they are not what
// decides whether segmentation works. A pixel count does. At 0.46 um/px a 10 um
// nucleus is 22 px across and everything below is comfortable; at 2.5 um/px it is 4 px
// and the same settings cannot possibly segment it. This block makes that visible
// before 30 minutes of detection, not after.
println ""
println "-" * 78
println "ACQUISITION CHECK — what these settings mean in pixels on THIS image"
double sigmaPx = (resolved.sigma_um as double) / pixelUm
double minAreaPx = (resolved.min_area_um2 as double) / pxToUm2
double maxAreaPx = (resolved.max_area_um2 as double) / pxToUm2
double expansionPx = (resolved.cell_expansion_um as double) / pixelUm
double nucleus10umPx = 10.0d / pixelUm
double minDiameterPx = 2.0d * Math.sqrt(minAreaPx / Math.PI)
println String.format("  a 10 um nucleus spans        %.1f px", nucleus10umPx)
println String.format("  sigma %.2f um                = %.2f px", resolved.sigma_um as double, sigmaPx)
println String.format("  min area %.1f um^2           = %.0f px  (>= %.1f px across)", resolved.min_area_um2 as double, minAreaPx, minDiameterPx)
println String.format("  max area %.1f um^2          = %.0f px", resolved.max_area_um2 as double, maxAreaPx)
println String.format("  cell expansion %.2f um       = %.2f px", resolved.cell_expansion_um as double, expansionPx)
println String.format("  bg-sub ring %.1f-%.1f um      = %.2f-%.2f px", gapUm, gapUm + widthUm, gapUm / pixelUm, (gapUm + widthUm) / pixelUm)
def advisories = []
// Two bands, because "too coarse to count" and "below the regime we validated" are
// different claims. The ~1.0 um/px floor is IMAGING-MINIMUM-VIABLE-ACQUISITION.md's,
// measured on this project's own data; 10 um is a typical nucleus, so the floor is
// about 10 px across it.
if (nucleus10umPx < 5.0d)
    advisories << String.format("a typical nucleus is only %.1f px across at %.3g um/px. Counting is PIXEL-LIMITED here: " +
            "touching nuclei cannot be split reliably at any setting. Treat the counts as a lower bound and check by eye.", nucleus10umPx, pixelUm)
else if (nucleus10umPx < 10.0d)
    advisories << String.format("a typical nucleus is %.1f px across at %.3g um/px, below this project's ~1.0 um/px " +
            "acquisition floor (IMAGING-MINIMUM-VIABLE-ACQUISITION.md, ~10 px per nucleus). Segmentation still works, " +
            "but touching nuclei merge more often than on the validated regime -- check the overlay before trusting densities.",
            nucleus10umPx, pixelUm)
if (sigmaPx < 0.8d)
    advisories << String.format("sigma is %.2f px — below one pixel it does almost nothing. Raise sigma_um toward %.1f for this pixel size.", sigmaPx, pixelUm)
if (sigmaPx > 6.0d)
    advisories << String.format("sigma is %.1f px — heavy smoothing at this magnification will merge adjacent nuclei. Consider lowering sigma_um.", sigmaPx)
if (minAreaPx < 6.0d)
    advisories << String.format("min area is %.1f px — that admits single-pixel noise as a nucleus. Raise min_area_um2.", minAreaPx)
if (expansionPx > 0 && expansionPx < 1.0d)
    advisories << String.format("cell expansion is %.2f px — the cytoplasm/whole-cell compartment will be near-empty, so non-nuclear markers cannot be measured. Raise cell_expansion_um.", expansionPx)
if (nZ > 1)
    advisories << "this image has ${nZ} Z-planes. Detection runs on the plane each ROI was drawn on, " +
                  "and the counts below are for that plane only — not a projection through the stack. " +
                  "The plane is recorded per ROI in the exports."
if (advisories.isEmpty()) {
    println "  no advisories — the settings sit in a workable range for this pixel size"
} else {
    advisories.each { println "  ADVISORY: ${it}" }
}
println "-" * 78

// ═══════════════════════════════════════════════════════════════════════════════
// 6. ANCHOR THRESHOLD — resolve, but print all three candidates first
// ═══════════════════════════════════════════════════════════════════════════════
// Showing every candidate is the point. When whole-image and in-ROI disagree, that
// disagreement is real information about the image (usually: the ROI is on tissue and
// the rest of the frame is not), and it is far easier to judge from two numbers side
// by side than from either one alone.
def channelTools = new ImageChannelTools(anchorChannel, imageData)
int resLevel = resolved.resolution_level as int
int smoothWin = resolved.smooth_window as int
double prominence = resolved.peak_prominence as double
double spanFrac = resolved.span_frac as double

/**
 * BraiAn's own nth-valid-peak selection, reached by reflection rather than reimplemented.
 * A private method is a real constraint, but a second copy of the peak-validity rule is
 * a worse one: it would drift from the registered route silently, whereas reflection
 * fails loudly the day BraiAn changes the signature.
 */
def nthValidPeak = { ChannelHistogram hist, int nPeak ->
    int[] peaks = hist.findHistogramPeaks(smoothWin, prominence)
    def m = WatershedCellDetectionConfig.class.getDeclaredMethod(
            "getNthValidPeak", ChannelHistogram.class, int[].class, int.class, int.class)
    m.setAccessible(true)
    try {
        return (m.invoke(null, hist, peaks, nPeak, smoothWin) as Integer).intValue()
    } catch (java.lang.reflect.InvocationTargetException e) {
        // Reflection wraps whatever the target threw, and the wrapper's own message is
        // null. Rethrowing the cause is the difference between "InvocationTargetException:
        // null" and BraiAn's actual, actionable complaint about the histogram.
        throw (e.getCause() != null ? e.getCause() : e)
    }
}
/** Root-cause message for a reported failure -- reflection and Groovy both nest causes. */
def rootMessage = { Throwable t ->
    Throwable r = t
    while (r.getCause() != null && r.getCause() != r) r = r.getCause()
    return "${r.class.simpleName}: ${r.message ?: '(no message)'}"
}

/** Histogram of the anchor channel over the union of the target ROIs only. */
def roiHistogram = {
    double downsample = server.getDownsampleForResolution(Math.min(resLevel, server.nResolutions() - 1))
    int anchorIdx = channelNames.indexOf(anchorChannel)
    def acc = new ArrayList<Integer>()
    boolean is8bit = server.getPixelType().getBitsPerPixel() <= 8
    targets.each { ann ->
        def roi = ann.getROI()
        def request = RegionRequest.createInstance(server.getPath(), downsample, roi)
        def img = server.readRegion(request)
        def mask = BufferedImageTools.createROIMask(img.getWidth(), img.getHeight(), roi, request)
        def raster = img.getRaster()
        def maskRaster = mask.getRaster()
        for (int y = 0; y < img.getHeight(); y++) {
            for (int x = 0; x < img.getWidth(); x++) {
                if (maskRaster.getSample(x, y, 0) == 0) continue
                acc.add(raster.getSample(x, y, anchorIdx))
            }
        }
    }
    if (acc.isEmpty()) return null
    // Pack the in-ROI values into a 1-row image and let BraiAn build the histogram from
    // it. The multiset of intensities is all a histogram is, so this yields exactly the
    // histogram of the ROI pixels — with no reimplementation of the binning.
    if (is8bit) {
        def bp = new ByteProcessor(acc.size(), 1)
        for (int i = 0; i < acc.size(); i++) bp.set(i, 0, acc[i] & 0xFF)
        return new ChannelHistogram(anchorChannel, bp)
    }
    def sp = new ShortProcessor(acc.size(), 1)
    for (int i = 0; i < acc.size(); i++) sp.set(i, 0, Math.min(acc[i], 65535))
    return new ChannelHistogram(anchorChannel, sp)
}

def spanCut = { Integer floorV, Integer brightV ->
    if (floorV == null || brightV == null || brightV <= floorV) return null
    return Math.round(floorV + spanFrac * (double) (brightV - floorV))
}

Long imageSpanThr = null, roiSpanThr = null
String imageSpanNote = "", roiSpanNote = ""
try {
    def p = { int nPeak ->
        def ap = new AutoThresholdParmameters()
        ap.setResolutionLevel(resLevel); ap.setSmoothWindowSize(smoothWin)
        ap.setnPeak(nPeak); ap.setPeakProminence(prominence)
        return WatershedCellDetectionConfig.findThreshold(channelTools, ap)
    }
    int fl = p(1), br = p(2)
    imageSpanThr = spanCut(fl, br)
    imageSpanNote = "floor ${fl}, bright ${br}"
    if (imageSpanThr == null) imageSpanNote += " — unusable (bright <= floor)"
} catch (Throwable t) {
    imageSpanNote = "could not be measured -- ${rootMessage(t)}"
}
try {
    def hist = roiHistogram()
    if (hist == null) {
        roiSpanNote = "no pixels inside the ROIs"
    } else {
        int fl = nthValidPeak(hist, 1), br = nthValidPeak(hist, 2)
        roiSpanThr = spanCut(fl, br)
        roiSpanNote = "floor ${fl}, bright ${br}"
        if (roiSpanThr == null) roiSpanNote += " — unusable (bright <= floor)"
    }
} catch (Throwable t) {
    roiSpanNote = "could not be measured -- ${rootMessage(t)}"
}

println ""
println "ANCHOR THRESHOLD CANDIDATES on ${anchorChannel} (span_frac ${spanFrac})"
println String.format("  image_span  %-10s  %s", imageSpanThr != null ? imageSpanThr.toString() : "n/a", imageSpanNote)
println String.format("  roi_span    %-10s  %s", roiSpanThr != null ? roiSpanThr.toString() : "n/a", roiSpanNote)
println String.format("  absolute    %-10s  %s", (resolved.absolute as double) > 0 ? Math.round(resolved.absolute as double).toString() : "not set",
        (resolved.absolute as double) > 0 ? "set by eye" : "set it in notebooks/04_roi.ipynb")

long anchorThreshold
String thrMode = resolved.threshold_mode as String
if (thrMode == "absolute") {
    if ((resolved.absolute as double) <= 0) {
        println "ERROR: threshold_mode is 'absolute' but no absolute value is set."
        throw new RuntimeException("roi_count: absolute threshold mode with no value")
    }
    anchorThreshold = Math.round(resolved.absolute as double)
} else if (thrMode in ["roi_span", "image_span"]) {
    Long chosen = (thrMode == "roi_span") ? roiSpanThr : imageSpanThr
    if (chosen == null) {
        // Refusing is correct here: this is "cannot be computed", not "may not mean what
        // you think". Silently falling back to the other rule -- or to a remembered
        // number -- is exactly how counts stop being comparable. But the operator must
        // leave this message knowing what to do next, so both candidates are restated
        // and the by-eye route is named explicitly.
        boolean bothFailed = (imageSpanThr == null && roiSpanThr == null)
        println "ERROR: threshold_mode is '${thrMode}' and it could not be measured on this image."
        println "  image_span : ${imageSpanThr != null ? imageSpanThr : 'FAILED'}  ${imageSpanNote}"
        println "  roi_span   : ${roiSpanThr != null ? roiSpanThr : 'FAILED'}  ${roiSpanNote}"
        println ""
        if (bothFailed) {
            println "  BOTH automatic rules failed, so this is not a matter of picking the other"
            println "  one. The peak finder needs two separable peaks in the anchor histogram and"
            println "  this image does not present them -- common on 8-bit data, on a frame that is"
            println "  mostly empty, and at magnifications the seed parameters were never set for."
            println ""
            println "  SET THE CUT BY EYE. That is tier-1 evidence here, not a workaround:"
            println "      notebooks/04_roi.ipynb section 3   (or scripts/cockpit_threshold_gui.py)"
            println "  Then set threshold_mode 'absolute' with that value in the dialog."
            println ""
            println "  Worth trying first if you would rather keep an automatic rule: lower"
            println "  peak_prominence (currently ${prominence}), or raise resolution_level"
            println "  (currently ${resLevel}) so the histogram is binned more coarsely."
        } else {
            String other = (thrMode == "roi_span") ? "image_span" : "roi_span"
            println "  '${other}' DID measure a value on this image. Switching to it is reasonable,"
            println "  but it is a different rule -- ${other == 'image_span' ? 'the whole frame' : 'your ROIs only'} sets the endpoints."
            println "  Setting the cut by eye (notebooks/04_roi.ipynb section 3, then mode"
            println "  'absolute') is the tier-1 option and needs no such tradeoff."
        }
        println ""
        println "  Refusing to substitute a different rule silently."
        throw new RuntimeException("roi_count: ${thrMode} threshold unavailable on ${imageName}")
    }
    anchorThreshold = chosen
} else {
    throw new RuntimeException("roi_count: unknown threshold_mode '${thrMode}' (expected image_span, roi_span or absolute)")
}
println "  USING ${thrMode} -> ${anchorThreshold}"
if (imageSpanThr != null && roiSpanThr != null) {
    double ratio = (double) Math.max(imageSpanThr, roiSpanThr) / Math.max(1L, Math.min(imageSpanThr, roiSpanThr))
    if (ratio > 1.5d)
        println String.format("  NOTE: the two automatic rules disagree by %.1fx. That is a fact about this " +
                "image (usually: the ROIs are on tissue, the rest of the frame is not). Look at the mask before trusting either.", ratio)
}

// ═══════════════════════════════════════════════════════════════════════════════
// 7. DETECTION
// ═══════════════════════════════════════════════════════════════════════════════
def targetRois = targets.collect { it.getROI() }
def insideTargets = { detection ->
    def r = detection.getROI()
    double x = r.getCentroidX(), y = r.getCentroidY()
    return targetRois.any { it.contains(x, y) }
}

if (stage == STAGE_FULL) {
    // Clear whatever a previous run left inside these shapes, and only inside them.
    // Everything under a target annotation is this script's own output (detections and
    // BraiAnDetect's containers); a nested ROI the operator also wants counted is
    // preserved explicitly.
    def targetSet = targets as Set
    def toRemove = []
    targets.each { ann ->
        ann.getChildObjects().each { ch -> if (!targetSet.contains(ch)) toRemove << ch }
    }
    if (!toRemove.isEmpty()) {
        removeObjects(toRemove, false)
        println "cleared ${toRemove.size()} object(s) from a previous run inside these ROIs"
    }

    def wsConfig = new WatershedCellDetectionConfig()
    // 0 means "this image's own pixel size" — never resample, which is what keeps
    // measured nucleus areas honest at any magnification.
    double reqPx = (resolved.requested_pixel_size_um as double)
    wsConfig.setRequestedPixelSizeMicrons(reqPx > 0 ? reqPx : pixelUm)
    wsConfig.setBackgroundRadiusMicrons(resolved.background_radius_um as double)
    wsConfig.setBackgroundByReconstruction(resolved.background_by_reconstruction as boolean)
    wsConfig.setMedianRadiusMicrons(resolved.median_radius_um as double)
    wsConfig.setSigmaMicrons(resolved.sigma_um as double)
    wsConfig.setMinAreaMicrons(resolved.min_area_um2 as double)
    wsConfig.setMaxAreaMicrons(resolved.max_area_um2 as double)
    wsConfig.setThreshold(anchorThreshold as double)
    wsConfig.setHistogramThreshold(null)          // the cut above is the only one that may apply
    wsConfig.setWatershedPostProcess(resolved.watershed_post_process as boolean)
    wsConfig.setCellExpansionMicrons(resolved.cell_expansion_um as double)
    wsConfig.setIncludeNuclei(true)
    wsConfig.setSmoothBoundaries(resolved.smooth_boundaries as boolean)
    wsConfig.setMakeMeasurements(true)            // produces the Nucleus:/Cell: means read below

    println ""
    println "detecting on ${anchorChannel} inside ${targets.size()} ROI(s) — this is the slow step..."
    long t0 = System.currentTimeMillis()
    try {
        new ChannelDetections(channelTools, targets, wsConfig, hierarchy)
    } catch (Throwable t) {
        println "ERROR: detection failed (${t.class.simpleName}: ${t.message})"
        throw t
    }
    println "detection done in ${Math.round((System.currentTimeMillis() - t0) / 1000.0)} s"
}

def dets = getDetectionObjects().findAll { insideTargets(it) }
if (dets.isEmpty()) {
    println ""
    println "NO DETECTIONS inside the ROIs."
    if (stage != STAGE_FULL) {
        println "  This run was '${stage}', which does not detect. Re-run with '${STAGE_FULL}'."
    } else {
        println "  The anchor cut (${anchorThreshold}) may be far too high for this image, or"
        println "  min/max area may exclude every object at this pixel size (see the acquisition"
        println "  check above). Set the cut by eye in notebooks/04_roi.ipynb and try again."
    }
    throw new RuntimeException("roi_count: no detections inside the ROIs on ${imageName}")
}
println "detections inside the ROIs: ${dets.size()}"

// ── Measurement-key self-check ─────────────────────────────────────────────────
// The anchor's own nuclear mean is exported so a negative-control pseudo-marker can be
// built downstream. It is read by an exact key string, and the failure mode when that
// key is wrong is SILENT: every cell reads null, the column exports blank, and nothing
// else misbehaves. So the key is resolved once, here, against the real key set, and a
// miss aborts with the available keys printed rather than shipping an empty column.
String anchorMeanKey = "Nucleus: ${anchorChannel} mean".toString()
def sampleKeySet = dets.first().getMeasurements().keySet()
if (!sampleKeySet.contains(anchorMeanKey)) {
    println "ERROR: expected anchor measurement '${anchorMeanKey}' is not present on the detections."
    println "       Keys actually present: ${sampleKeySet.toList()}"
    println "       Most likely BraiAn.yml-style makeMeasurements did not run, or the anchor"
    println "       channel name in pipeline.yml does not match the image's channel."
    throw new RuntimeException("roi_count: anchor measurement key missing on ${imageName}")
}

// ═══════════════════════════════════════════════════════════════════════════════
// 8. LOCAL-BACKGROUND-SUBTRACTED MEASURES  (mirrors 02_detect_classify.groovy)
// ═══════════════════════════════════════════════════════════════════════════════
// Each marker is measured on its declared compartment, minus the local background in a
// thin annulus just outside that compartment, with neighbouring cells geometrically
// subtracted out of the annulus. Without this, regional autofluorescence reads as
// marker signal and produces confident false positives.
double gapPx = gapUm / pixelUm
double outerPx = (gapUm + widthUm) / pixelUm
int bgGeomFailures = 0

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
        ObjectMeasurements.addIntensityMeasurements(server, tempObj, 1.0, [Measurements.MEAN], [Compartments.CELL])
        def key = tempObj.getMeasurements().keySet().find {
            it.startsWith(channelName) && it.toLowerCase().endsWith("mean")
        }
        def v = key == null ? null : tempObj.getMeasurements().get(key)
        return (v == null || Double.isNaN(v.doubleValue())) ? Double.NaN : v.doubleValue()
    } catch (Throwable t) {
        // JTS geometry-robustness failures hit a small number of pathological ROIs. One
        // bad cell must not abort the run, so it becomes NaN — which falls conservatively
        // to Negative — and the total is reported below.
        bgGeomFailures++
        return Double.NaN
    }
}

// A whole-cell marker needs QuPath's Cell-compartment mean to exist. When it does not,
// every cell reads NaN and every cell is called Negative — a silent all-negative result
// that looks like biology. Checked before classification, not after.
def wholeCellMarkers = markers.findAll { it.compartment == "whole-cell" }
if (!wholeCellMarkers.isEmpty() && stage != STAGE_EXPORT) {
    def sampleKeys = dets.first().getMeasurements().keySet()
    def missingCellKeys = wholeCellMarkers.collect { "Cell: ${it.channel} mean".toString() }
            .findAll { !sampleKeys.contains(it) }
    if (!missingCellKeys.isEmpty()) {
        println "ERROR: whole-cell marker(s) declared but the Cell-compartment measurement is missing: ${missingCellKeys}"
        println "       cell_expansion_um must be > 0 so the cell compartment exists. It is currently ${resolved.cell_expansion_um}."
        println "       Raise it and re-run with '${STAGE_FULL}'."
        println "       Measurement keys actually present: ${sampleKeys}"
        throw new RuntimeException("roi_count: whole-cell compartment missing on ${imageName}")
    }
}

if (stage != STAGE_EXPORT) {
    println ""
    println "measuring local background for ${dets.size()} cells x ${markers.size()} marker(s)..."
    int processed = 0
    dets.each { d ->
        def nucleusRoi = (d.respondsTo('getNucleusROI') && d.getNucleusROI() != null) ? d.getNucleusROI() : d.getROI()
        def cellRoi = d.getROI()
        markers.each { m ->
            String label = COMPARTMENT_LABELS[m.compartment]
            def baseRoi = (m.compartment == "nuclear") ? nucleusRoi : cellRoi
            String rawKey = "${label}: ${m.channel} mean"
            String bgsubKey = "${label}: ${m.channel} mean (bg-sub)"
            def rawM = d.getMeasurements().get(rawKey)
            double raw = rawM != null ? rawM.doubleValue() : Double.NaN
            double bg = localBackgroundSubtractedMean(baseRoi, m.channel, d)
            d.getMeasurements().put(bgsubKey, raw - bg)
        }
        processed++
        if (processed % 1000 == 0) println "  ...${processed}/${dets.size()}"
    }
    fireHierarchyUpdate()
    if (bgGeomFailures > 0)
        println "  NOTE: ${bgGeomFailures} annulus computation(s) failed geometrically and became NaN (they classify Negative). Negligible if small."
}

// ═══════════════════════════════════════════════════════════════════════════════
// 9. CLASSIFICATION  (mirrors 02_detect_classify.groovy — pinned by smoke_test.py)
// ═══════════════════════════════════════════════════════════════════════════════
// cut = median + k * 1.4826 * MAD on the bg-sub population. Robust, self-calibrating,
// and assumes no bimodality — sparse markers do not have one, and a peak-based cut on
// them returns NaN and calls everything Negative.
def medianOf = { List<Double> xs ->
    if (xs == null || xs.isEmpty()) return Double.NaN
    def s = xs.toSorted()
    int m = s.size(); int mid = m.intdiv(2)
    return (m % 2 == 1) ? (s[mid] as double) : 0.5d * ((s[mid - 1] as double) + (s[mid] as double))
}
def madOf = { List<Double> xs, double med ->
    if (xs == null || xs.isEmpty() || Double.isNaN(med)) return Double.NaN
    return medianOf(xs.collect { Math.abs((it as double) - med) })
}
def robustThreshold = { List<Double> values, double k ->
    if (values == null || values.isEmpty()) return Double.NaN
    double med = medianOf(values)
    if (Double.isNaN(med)) return Double.NaN
    double mad = madOf(values, med)
    if (Double.isNaN(mad)) return Double.NaN
    return med + k * (1.4826d * mad)
}

def bgsubKeyFor = { m -> "${COMPARTMENT_LABELS[m.compartment]}: ${m.channel} mean (bg-sub)".toString() }
def valuesFor = { List cells, m ->
    cells.collect { it.getMeasurements().get(bgsubKeyFor(m))?.doubleValue() }
         .findAll { it != null && !Double.isNaN(it) }
}

// One cut per marker from all cells in all ROIs (k_scope=image), or one per ROI
// (k_scope=roi). Pooled is the default because a per-ROI cut is self-calibrating in a
// way that makes ROIs incomparable with each other: each would be measured against its
// own background, so a real difference between two ROIs is normalised away.
def cutsByRoi = [:]     // roi name -> [marker -> cut]
boolean perRoiK = (resolved.k_scope as String) == "roi"
if (stage != STAGE_EXPORT) {
    println ""
    println "marker cuts (k_scope=${resolved.k_scope}):"
    if (perRoiK) {
        println "  WARNING: each ROI gets its OWN cut, derived from its own cells. The ROIs are"
        println "  then NOT comparable with each other — a difference between them may be a"
        println "  threshold difference. Use k_scope=image unless you specifically want this."
        targets.each { ann ->
            def roi = ann.getROI()
            def cells = dets.findAll { roi.contains(it.getROI().getCentroidX(), it.getROI().getCentroidY()) }
            def cuts = [:]
            markers.each { m ->
                def abs = markerSettings[m.name].absolute_bgsub
                cuts[m.name] = (abs != null) ? (abs as double) : robustThreshold(valuesFor(cells, m), markerSettings[m.name].k as double)
                println String.format("    %-16s %-8s n=%-6d cut=%.4f", ann.getName(), m.name, cells.size(), cuts[m.name])
            }
            cutsByRoi[ann.getName()] = cuts
        }
    } else {
        def cuts = [:]
        markers.each { m ->
            def vals = valuesFor(dets, m)
            def abs = markerSettings[m.name].absolute_bgsub
            double cut = (abs != null) ? (abs as double) : robustThreshold(vals, markerSettings[m.name].k as double)
            cuts[m.name] = cut
            double med = medianOf(vals), mad = madOf(vals, med)
            int nPos = vals.count { (it as double) >= cut }
            double posFrac = vals.isEmpty() ? Double.NaN : (double) nPos / vals.size()
            String how = (abs != null) ? "absolute (set by eye)" : "k=${markerSettings[m.name].k}"
            String verdict
            if (Double.isNaN(cut))            verdict = "CHECK — no usable data"
            else if (Double.isNaN(posFrac))   verdict = "CHECK — no values"
            else if (posFrac <= 0.0d)         verdict = "CHECK — 0% positive; the cut is above every cell"
            else if (posFrac > 0.5d)          verdict = "CHECK — >50% positive; implausibly low for a sparse marker"
            else                              verdict = String.format("%.2f%% positive", 100.0d * posFrac)
            println String.format("  %-8s n=%-6d median=%.4f robustSD=%.4f cut=%.4f (%s) -> %s",
                    m.name, vals.size(), med, 1.4826d * mad, cut, how, verdict)
        }
        targets.each { ann -> cutsByRoi[ann.getName()] = cuts }
    }

    // Assign one class per nucleus. Double+ only exists when >=2 markers are declared,
    // and only ever means "this one nucleus was positive for both" — never proximity.
    dets.each { d ->
        def r = d.getROI()
        def owner = targets.find { it.getROI().contains(r.getCentroidX(), r.getCentroidY()) }
        def cuts = cutsByRoi[owner?.getName()] ?: [:]
        def positive = markers.findAll { m ->
            def v = d.getMeasurements().get(bgsubKeyFor(m))
            def c = cuts[m.name]
            c != null && !Double.isNaN(c as double) && v != null && !Double.isNaN(v.doubleValue()) && v.doubleValue() >= (c as double)
        }
        if (emitDouble && positive.size() >= 2)  d.setPathClass(getPathClass("Double+"))
        else if (positive.size() == 1)           d.setPathClass(getPathClass("${positive[0].name}+"))
        else                                     d.setPathClass(getPathClass("Negative"))
    }
    fireHierarchyUpdate()
}

// Class colours, so which cells were called what is legible on the image at a glance —
// the overlay is what the operator is meant to judge, so it should be readable.
def CLASS_COLORS = [:]
CLASS_COLORS["Negative"] = getColorRGB(150, 150, 150)
def palette = [[255, 80, 80], [80, 200, 255], [255, 200, 60], [180, 120, 255]]
markers.eachWithIndex { m, idx ->
    def c = palette[idx % palette.size()]
    CLASS_COLORS["${m.name}+".toString()] = getColorRGB(c[0], c[1], c[2])
}
if (emitDouble) CLASS_COLORS["Double+"] = getColorRGB(120, 255, 120)
CLASS_COLORS.each { name, rgb ->
    def pc = getPathClass(name)
    if (pc != null) pc.setColor(rgb)
}

// ═══════════════════════════════════════════════════════════════════════════════
// 10. PER-ROI COUNTS
// ═══════════════════════════════════════════════════════════════════════════════
def CATEGORIES = [anchorName] + markers.collect { it.name } + (emitDouble ? ["Double+"] : [])
// Column and class naming are taken verbatim from 03_export_region_table.groovy so the
// ROI tables have the SAME shape as the registered route's region tables. That is what
// lets scripts/cockpit_regions.py and cockpit_animal.py read ROI output with no changes,
// including the locked engram metric family.
def columnPrefixFor = { String cat -> (cat == "Double+" || cat == anchorName) ? cat : "${cat}+" }
def classFor = { String cat -> cat == "Double+" ? "Double+" : "${cat}+" }
def zeroCounts = { CATEGORIES.collectEntries { [(it): 0] } }

def perShape = []
targets.each { ann ->
    def roi = ann.getROI()
    def counts = zeroCounts()
    def cells = dets.findAll { roi.contains(it.getROI().getCentroidX(), it.getROI().getCentroidY()) }
    cells.each { d ->
        def cls = d.getPathClass()?.toString() ?: "Negative"
        counts[anchorName] = counts[anchorName] + 1     // every detected nucleus in the ROI
        markers.each { m ->
            // A marker's total INCLUDES Double+ cells: a Double+ cell is positive for
            // this marker, it merely happens to be positive for another one too.
            if (cls == "${m.name}+" || cls == "Double+") counts[m.name] = counts[m.name] + 1
        }
        if (emitDouble && cls == "Double+") counts["Double+"] = counts["Double+"] + 1
    }
    // Roll the counts onto the annotation so they show in QuPath's measurement table.
    def ml = ann.getMeasurementList()
    CATEGORIES.each { cat -> ml.put("Count: ${classFor(cat)}".toString(), (counts[cat] ?: 0) as double) }
    ml.put("Area um^2", roi.getArea() * pxToUm2)
    perShape << [name: ann.getName(), roi: roi, z: roi.getImagePlane().getZ(),
                 areaMm2: roi.getArea() * pxToMm2, areaUm2: roi.getArea() * pxToUm2, counts: counts]
}
fireHierarchyUpdate()

// Pooled rollup by name: three shapes named "LA" become one "LA" row alongside their
// three individual rows. Both are emitted; neither replaces the other.
def pooled = [:] as LinkedHashMap
perShape.each { s ->
    def p = pooled.computeIfAbsent(s.name) { [name: s.name, nShapes: 0, areaMm2: 0.0d, areaUm2: 0.0d, counts: zeroCounts()] }
    p.nShapes = p.nShapes + 1
    p.areaMm2 = p.areaMm2 + s.areaMm2
    p.areaUm2 = p.areaUm2 + s.areaUm2
    CATEGORIES.each { cat -> p.counts[cat] = p.counts[cat] + (s.counts[cat] ?: 0) }
}

// ═══════════════════════════════════════════════════════════════════════════════
// 11. EXPORTS
// ═══════════════════════════════════════════════════════════════════════════════
def invalidChars = (['<', '>', ':', '"', '/', '\\', '|', '?', '*'] as Set)
        .collect { java.util.regex.Pattern.quote(it) }.join('|')
def safeName = (imageName ?: "").replaceAll(invalidChars, '')
def entryId = (entry != null ? entry.getID() : "").replaceAll(invalidChars, '')
def stem = (entryId != null && !entryId.trim().isEmpty()) ? "${safeName}__id${entryId}" : safeName
def outDir = new File(buildPathInProject("results", "roi"))
outDir.mkdirs()

// Settings provenance travels on every count row. A settings_hash makes "were these two
// numbers made the same way" a lookup instead of an argument.
def provenance = [
    image                 : imageName,
    pixel_um              : String.format('%.9g', pixelUm),
    n_z_planes            : nZ,
    anchor_channel        : anchorChannel,
    threshold_mode        : thrMode,
    anchor_threshold      : anchorThreshold,
    span_frac             : spanFrac,
    image_span_candidate  : imageSpanThr != null ? imageSpanThr : "",
    roi_span_candidate    : roiSpanThr != null ? roiSpanThr : "",
    sigma_um              : resolved.sigma_um,
    min_area_um2          : resolved.min_area_um2,
    max_area_um2          : resolved.max_area_um2,
    cell_expansion_um     : resolved.cell_expansion_um,
    background_radius_um  : resolved.background_radius_um,
    ring_gap_um           : gapUm,
    ring_width_um         : widthUm,
    k_scope               : resolved.k_scope,
]
markers.each { m ->
    provenance["k_${m.name}".toString()] = markerSettings[m.name].absolute_bgsub != null ?
            "abs:${markerSettings[m.name].absolute_bgsub}" : markerSettings[m.name].k
}
// The hash answers "was the same RULE applied", which is the question you ask before
// pooling two images. So it deliberately excludes the RESOLVED threshold and the
// candidate values: under image_span/roi_span every image gets its own number BY
// DESIGN — re-measuring the cut from each image's own histogram is precisely what makes
// them comparable — and hashing it in would mark every image as incompatible with every
// other. In absolute mode the number IS the rule, so there it counts. pixel_um stays in
// either way: a different pixel size is a different measurement, not a different scaling
// (CLAUDE.md comparability rule).
def HASH_EXCLUDE = (["image", "image_span_candidate", "roi_span_candidate"] +
        (thrMode == "absolute" ? [] : ["anchor_threshold"])) as Set
def hashSource = provenance.findAll { k, v -> !HASH_EXCLUDE.contains(k) }.collect { k, v -> "${k}=${v}" }.join("|")
def settingsHash = String.format("%08x", hashSource.hashCode())
provenance["settings_hash"] = settingsHash

// -- per-cell TSV. Schema matches the registered route's __percell_export.tsv exactly,
// so scripts/cockpit_marker_gui.py (set k by looking at the cells) reads ROI data with
// no changes at all. `region_label` carries the ROI name.
def fmt = { double v, String pattern -> Double.isNaN(v) ? "" : String.format(pattern, v) }
def percellSb = new StringBuilder()
percellSb.append((["class", "region_label", "nucleus_area_um2", "centroid_x_px", "centroid_y_px",
                   "anchor_mean"] + markers.collect { "${it.name}_bgsub" } + ["z"]).join("\t")).append("\n")
dets.each { d ->
    def r = d.getROI()
    def owner = targets.find { it.getROI().contains(r.getCentroidX(), r.getCentroidY()) }
    def nucleusRoi = (d.respondsTo('getNucleusROI') && d.getNucleusROI() != null) ? d.getNucleusROI() : d.getROI()
    // .toString() is REQUIRED, not tidiness: a Groovy GString does not equal the
    // equivalent String in QuPath's MeasurementList, so a GString key silently reads
    // back null and the whole column exports blank. Verified on this exact key,
    // 2026-08-05 (GString -> null, String -> 28.167 for the same measurement).
    def anchorM = d.getMeasurements().get(anchorMeanKey)
    def cols = [d.getPathClass()?.toString() ?: "Negative",
                owner?.getName() ?: "(outside)",
                fmt(nucleusRoi != null ? nucleusRoi.getArea() * pxToUm2 : Double.NaN, '%.4f'),
                fmt(r.getCentroidX(), '%.3f'), fmt(r.getCentroidY(), '%.3f'),
                fmt(anchorM != null ? anchorM.doubleValue() : Double.NaN, '%.4f')]
    markers.each { m ->
        def v = d.getMeasurements().get(bgsubKeyFor(m))
        cols << fmt(v != null ? v.doubleValue() : Double.NaN, '%.4f')
    }
    cols << r.getImagePlane().getZ()
    percellSb.append(cols.join("\t")).append("\n")
}
def percellFile = new File(outDir, "${stem}__percell_export.tsv")
percellFile.text = percellSb.toString()

// -- per-ROI TSV: every shape, then every pooled name.
def countHeader = (["scope", "roi_name", "n_shapes", "z", "area_um2", "area_mm2"] +
        CATEGORIES.collectMany { c -> ["${columnPrefixFor(c)}_count", "${columnPrefixFor(c)}_density"] }).join("\t")
def countsSb = new StringBuilder().append(countHeader).append("\n")
def countRow = { String scope, String name, int nShapes, def z, double areaUm2, double areaMm2, Map counts ->
    def cells = [scope, name, nShapes, z == null ? "" : z, String.format('%.2f', areaUm2), String.format('%.6f', areaMm2)]
    CATEGORIES.each { cat ->
        int cnt = (counts[cat] ?: 0) as int
        cells << cnt
        cells << (areaMm2 > 0 ? String.format('%.2f', cnt / areaMm2) : "")
    }
    return cells.join("\t")
}
perShape.each { s -> countsSb.append(countRow("shape", s.name, 1, s.z, s.areaUm2, s.areaMm2, s.counts)).append("\n") }
pooled.each { name, p -> countsSb.append(countRow("pooled", name, p.nShapes, null, p.areaUm2, p.areaMm2, p.counts)).append("\n") }
def countsFile = new File(outDir, "${stem}__roi_counts.tsv")
countsFile.text = countsSb.toString()

// -- growing combined CSV: one row per (image x roi x class), provenance on every row.
def provKeys = provenance.keySet().toList()
def combined = new File(outDir, "roi_counts_combined.csv")
def combinedHeader = (["scope", "roi_name", "n_shapes", "z", "area_mm2", "marker", "class", "count", "density"] + provKeys).join(",")
def csvQ = { v -> def s = (v == null ? "" : v.toString()); s.contains(",") || s.contains('"') ? '"' + s.replace('"', '""') + '"' : s }
/** Split one CSV line on commas that are outside quotes, unescaping doubled quotes. */
def csvSplit = { String line ->
    def out = []; def cur = new StringBuilder(); boolean inQ = false
    for (int i = 0; i < line.length(); i++) {
        char c = line.charAt(i)
        if (c == ('"' as char)) {
            if (inQ && i + 1 < line.length() && line.charAt(i + 1) == ('"' as char)) { cur.append('"'); i++ }
            else inQ = !inQ
        } else if (c == (',' as char) && !inQ) { out << cur.toString(); cur = new StringBuilder() }
        else cur.append(c)
    }
    out << cur.toString()
    return out
}
if (!combined.exists()) {
    combined.text = combinedHeader + "\n"
} else {
    def existing = combined.readLines().findAll { !it.trim().isEmpty() }
    if (existing.isEmpty() || existing[0] != combinedHeader) {
        // A different header means a different marker set or provenance schema. Appending
        // under it would produce a file whose columns do not mean the same thing in every
        // row, so the old one is moved aside intact rather than mangled or silently lost.
        def stamp = new java.text.SimpleDateFormat('yyyyMMdd-HHmmss').format(new Date())
        def aside = new File(outDir, "roi_counts_combined.${stamp}.csv")
        combined.renameTo(aside)
        println "NOTE: roi_counts_combined.csv had a different column set (marker set or"
        println "      provenance schema changed). Moved it to ${aside.name} and started a new one."
        combined.text = combinedHeader + "\n"
    } else {
        // Drop this image's previous rows so a re-run after a tuning change REPLACES its
        // numbers rather than stacking a second, contradictory set beside them.
        int imageCol = existing[0].split(",", -1).findIndexOf { it == "image" }
        def kept = existing.drop(1).findAll { imageCol < 0 || csvSplit(it)[imageCol] != imageName }
        int dropped = existing.size() - 1 - kept.size()
        if (dropped > 0) println "replacing ${dropped} row(s) for this image in roi_counts_combined.csv"
        combined.text = ([combinedHeader] + kept).join("\n") + "\n"
    }
}
def combinedSb = new StringBuilder()
int nRows = 0
def emit = { String scope, String name, int nShapes, def z, double areaMm2, Map counts ->
    CATEGORIES.each { cat ->
        int cnt = (counts[cat] ?: 0) as int
        def cells = [scope, name, nShapes, z == null ? "" : z, String.format('%.6f', areaMm2), cat, classFor(cat), cnt,
                     areaMm2 > 0 ? String.format('%.2f', cnt / areaMm2) : ""]
        provKeys.each { k -> cells << provenance[k] }
        combinedSb.append(cells.collect { csvQ(it) }.join(",")).append("\n")
        nRows++
    }
}
perShape.each { s -> emit("shape", s.name, 1, s.z, s.areaMm2, s.counts) }
pooled.each { name, p -> emit("pooled", name, p.nShapes, null, p.areaMm2, p.counts) }
combined.append(combinedSb.toString())

// ═══════════════════════════════════════════════════════════════════════════════
// 12. SAVE SETTINGS BACK — this image's block, so a re-run reproduces this run
// ═══════════════════════════════════════════════════════════════════════════════
def ymlVal = { v ->
    if (v == null) return "null"
    if (v instanceof Boolean) return v.toString()
    if (v instanceof Number) return (v instanceof Integer || v instanceof Long) ? v.toString() : String.format('%.6g', v.doubleValue())
    return '"' + v.toString().replace('"', '\\"') + '"'
}
def block = [:] as LinkedHashMap
// FULL precision, deliberately not ymlVal's %.6g. This value is compared against the
// image's own pixel size on the next run to decide whether a saved block still
// describes this image; rounding it to 6 significant figures makes that comparison fail
// against the image it was written from, so every subsequent run would warn about a
// mismatch that does not exist.
// Double.toString gives the shortest decimal that round-trips to the SAME double, which
// is exactly the property this comparison needs.
block["pixel_um"] = Double.toString(pixelUm)
SETTING_KEYS.each { k -> block[k] = resolved[k] }
markers.each { m ->
    block["k_${m.name}".toString()] = markerSettings[m.name].k
    if (markerSettings[m.name].absolute_bgsub != null) block["abs_${m.name}".toString()] = markerSettings[m.name].absolute_bgsub
}
def priorNote = (settingsKey != null ? stored.images[settingsKey]["note"] : null)
block["note"] = priorNote ?: "written by roi_count.groovy " +
        new java.text.SimpleDateFormat('yyyy-MM-dd HH:mm').format(new Date())

// Rewrite under this image's EXACT name. A block previously matched by substring is
// left alone: it may be carrying a whole family of images deliberately.
def outImages = new LinkedHashMap(stored.images)
outImages[imageName] = block
def sb = new StringBuilder()
sb.append("""\
# roi_settings.yml — per-image settings for manual-ROI counting (scripts/roi_count.groovy)
#
# MACHINE-MANAGED. roi_count.groovy rewrites this file after every run, recording the
# settings that produced that image's counts. Editing values by hand is fine and
# expected; free-form comments inside the blocks will not survive a rewrite, so put
# anything you want to keep in a block's `note:` field.
#
# WHY PER IMAGE. Images counted this way vary in magnification, Z handling and
# intensity. Micron-denominated parameters describe a nucleus, but whether they can
# segment one depends on how many PIXELS that nucleus spans — which changes with
# magnification. So each image keeps the settings it was actually tuned with, and a
# re-run reproduces its numbers exactly.
#
# `defaults:` seeds any image without a block of its own. `images:` keys are matched
# against the QuPath entry name: exact match first, then substring (so a short key can
# carry a family of images). The matched key is printed on every run.
#
# threshold_mode:
#   image_span  floor + span_frac x (bright - floor) from the WHOLE image histogram —
#               the same rule the registered whole-brain route uses
#   roi_span    the same rule, measured only inside the drawn ROIs. Often the right one
#               when the ROIs are on tissue and most of the frame is not
#   absolute    a cut you set by eye. Tier-1 evidence by this project's own hierarchy;
#               pick it in notebooks/04_roi.ipynb while looking at the mask
#
# The marker set (which markers exist, which compartment each is measured on) is NOT
# here — it lives in pipeline.yml, so a project has exactly one marker declaration.
# k_<marker> sets that marker's robust multiplier; abs_<marker> replaces it with an
# absolute bg-sub cut you chose by looking.

version: 1

defaults:
""")
SETTING_KEYS.each { k -> sb.append("  ${k}: ${ymlVal(stored.defaults.containsKey(k) ? stored.defaults[k] : BUILTIN[k])}\n") }
markers.each { m ->
    def dk = "k_${m.name}".toString()
    sb.append("  ${dk}: ${ymlVal(stored.defaults.containsKey(dk) ? stored.defaults[dk] : markerSettings[m.name].k)}\n")
}
sb.append("\nimages:\n")
outImages.each { name, blk ->
    sb.append("  \"${name.replace('"', '\\"')}\":\n")
    blk.each { k, v -> sb.append("    ${k}: ${ymlVal(v)}\n") }
}
settingsFile.text = sb.toString()

// ═══════════════════════════════════════════════════════════════════════════════
// 13. SUMMARY
// ═══════════════════════════════════════════════════════════════════════════════
println ""
println "=" * 78
println "COUNTS — check these against the image with the detections overlaid"
println "=" * 78
def hdr = String.format("  %-22s %6s %10s", "ROI", "z", "area mm^2") +
        CATEGORIES.collect { String.format(" %10s %10s", classFor(it), "per mm^2") }.join("")
println hdr
perShape.each { s ->
    println String.format("  %-22s %6d %10.5f", s.name, s.z, s.areaMm2) +
            CATEGORIES.collect { cat ->
                int c = (s.counts[cat] ?: 0) as int
                String.format(" %10d %10s", c, s.areaMm2 > 0 ? String.format("%,.0f", c / s.areaMm2) : "-")
            }.join("")
}
if (pooled.size() != perShape.size()) {
    println "  " + "-" * (hdr.length() - 2)
    pooled.each { name, p ->
        println String.format("  %-22s %6s %10.5f", "${name} (x${p.nShapes})", "", p.areaMm2) +
                CATEGORIES.collect { cat ->
                    int c = (p.counts[cat] ?: 0) as int
                    String.format(" %10d %10s", c, p.areaMm2 > 0 ? String.format("%,.0f", c / p.areaMm2) : "-")
                }.join("")
    }
}
if (emitDouble) {
    println ""
    println "  Double+ means ONE nucleus called positive for two markers — never two nearby cells."
    markers.each { m ->
        int tot = perShape.sum { (it.counts[m.name] ?: 0) as int } as int
        int dbl = perShape.sum { (it.counts["Double+"] ?: 0) as int } as int
        println String.format("  Double+ / %s+ over all ROIs: %s", m.name, tot > 0 ? String.format("%.3f", (double) dbl / tot) : "n/a")
    }
}
println ""
println "  anchor cut ${anchorThreshold} (${thrMode})   settings_hash ${settingsHash}"
println "  Rows with a different settings_hash were produced by a different rule."
println "  Pool them only deliberately — notebooks/04_roi.ipynb flags it."
println ""
println "  wrote  ${percellFile.name}   (${dets.size()} cells)"
println "         ${countsFile.name}    (${perShape.size()} shapes, ${pooled.size()} pooled)"
println "         ${combined.name}      (+${nRows} rows)"
println "         roi_settings.yml      (this image's block updated)"
println "  in     ${outDir}"
println ""
println "  NEXT: look at the overlay. If the DAPI segmentation or the marker calls look"
println "  wrong, they are wrong — re-run with different settings. '${STAGE_CLASSIFY}'"
println "  re-cuts the markers in seconds without re-detecting."
println "=" * 78
