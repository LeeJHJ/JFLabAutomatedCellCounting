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
    // which passes run
    "count_nuclei", "detect_markers", "measure_area",
    // anchor cut + segmentation
    "threshold_mode", "span_frac", "absolute", "resolution_level", "smooth_window",
    "peak_prominence", "requested_pixel_size_um", "background_radius_um",
    "background_by_reconstruction", "median_radius_um", "sigma_um", "min_area_um2",
    "max_area_um2", "cell_expansion_um", "watershed_post_process", "smooth_boundaries",
    "k_scope",
    // independent marker detection + overlap
    "overlap_min_frac",
    // area / intensity measurement
    "area_downsample", "area_min_blob_um2",
]
def BOOL_KEYS = ["background_by_reconstruction", "watershed_post_process", "smooth_boundaries",
                 "count_nuclei", "detect_markers", "measure_area"] as Set
def STR_KEYS  = ["threshold_mode", "k_scope"] as Set

// Per-marker settings are DYNAMIC keys: their names contain a marker name that is only
// known once pipeline.yml has been read, so they cannot live in the fixed list above.
// Recognised by prefix:
//   k_<M>      / abs_<M>      marker positivity (robust multiplier / absolute bg-sub cut)
//   mdet_<M>_* independent detection of <M> on its OWN channel
//   acut_<M>_* the cut used by the area/intensity pass for <M>'s channel
def DYNAMIC_PREFIXES = ["k_", "abs_", "mdet_", "acut_"]
def isDynamicKey = { String key ->
    if (key == "k_scope") return false          // fixed key that merely starts with k_
    return DYNAMIC_PREFIXES.any { key.startsWith(it) }
}
def DYNAMIC_STR_SUFFIXES = ["_mode"] as Set     // e.g. mdet_TdT_mode, acut_Fos_mode

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
    // Which passes run. Counting is the default; the other two are opt-in because each
    // costs time and answers a different question.
    count_nuclei                : true,
    detect_markers              : false,
    measure_area                : false,
    // Independent-detection overlap. intersection_area / min(area_a, area_b) must reach
    // this for two independently detected objects to be called the same cell. [ASSUMED]
    // seed -- never validated against hand counts, and the whole overlap metric is
    // weaker than the nucleus-anchored one by construction (see the header).
    overlap_min_frac            : 0.20d,
    // Area/intensity pass. 1.0 = full resolution. Raise it for very large ROIs.
    area_downsample             : 1.0d,
    // Blobs smaller than this are dropped from the BLOB statistics only -- area
    // fraction, means and integrated density are never filtered, because those are
    // meant to be raw occupancy. 0 = keep everything. A blob median equal to one pixel
    // means the mask is speckle, which the advisory below says out loud.
    area_min_blob_um2           : 0.0d,
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
        if (DYNAMIC_STR_SUFFIXES.any { key.endsWith(it) }) return val
        if (key in ["resolution_level", "smooth_window"]) return val as Integer
        try { return val as Double } catch (Exception ignored) { return val }
    }
    int i = 0
    while (i < lines.size()) {
        def t = lines[i].trim()
        if (t == "defaults:") {
            int j = i + 1
            while (j < lines.size() && (lines[j].trim().isEmpty() || indentOf(lines[j]) > 0)) {
                def m = (lines[j].trim() =~ /^([A-Za-z_][A-Za-z0-9_.-]*):\s*(.*)$/)
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
                    def m = (s =~ /^([A-Za-z_][A-Za-z0-9_.-]*):\s*(.*)$/)
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
def keepKey = { String k -> SETTING_KEYS.contains(k) || isDynamicKey(k) }
stored.defaults.each { k, v -> if (keepKey(k)) resolved[k] = v }
if (settingsKey != null) {
    println "settings: matched saved block '${settingsKey}' for this image"
    stored.images[settingsKey].each { k, v -> if (keepKey(k)) resolved[k] = v }
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

// ── Dynamic per-marker defaults ────────────────────────────────────────────────
// mdet_* (independent detection) and acut_* (area-pass cut) are seeded here, AFTER the
// marker set is known, for any marker whose keys the settings file does not already
// carry. Seeded from the anchor's own values rather than from invented numbers: they
// are at least a parameter set that segments SOMETHING on this image, which is a
// better starting point than a constant borrowed from another acquisition.
//
// The area-pass cut is seeded for the anchor too -- DAPI+ area is the denominator of
// the "<marker> count per DAPI+ area" readout, so it is a first-class measurement here
// and not merely a by-product of segmentation.
def areaCutChannels = [[name: anchorName, channel: anchorChannel]] +
        markers.collect { [name: it.name, channel: it.channel] }
def seedIfAbsent = { String key, Object val -> if (!resolved.containsKey(key)) resolved[key] = val }
markers.each { m ->
    seedIfAbsent("mdet_${m.name}_mode".toString(), resolved.threshold_mode)
    seedIfAbsent("mdet_${m.name}_span_frac".toString(), resolved.span_frac)
    seedIfAbsent("mdet_${m.name}_absolute".toString(), 0.0d)
    seedIfAbsent("mdet_${m.name}_sigma_um".toString(), resolved.sigma_um)
    seedIfAbsent("mdet_${m.name}_min_area_um2".toString(), resolved.min_area_um2)
    seedIfAbsent("mdet_${m.name}_max_area_um2".toString(), resolved.max_area_um2)
}
areaCutChannels.each { c ->
    seedIfAbsent("acut_${c.name}_mode".toString(), resolved.threshold_mode)
    seedIfAbsent("acut_${c.name}_span_frac".toString(), resolved.span_frac)
    seedIfAbsent("acut_${c.name}_absolute".toString(), 0.0d)
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
    params.addTitleParameter("Independent marker detection — NOT nucleus-anchored")
    params.addBooleanParameter("detect_markers", "Detect each marker on its own channel",
            resolved.detect_markers as boolean,
            "Finds marker objects without reference to DAPI. Useful where nuclei cannot be segmented. " +
            "A blob on a marker channel is not necessarily a cell, so these counts are weaker than the ones above.")
    markers.each { m ->
        params.addChoiceParameter("mdet_${m.name}_mode", "  ${m.name} cut mode",
                resolved["mdet_${m.name}_mode".toString()] as String, THRESHOLD_MODES, "")
        params.addDoubleParameter("mdet_${m.name}_span_frac", "  ${m.name} span fraction",
                resolved["mdet_${m.name}_span_frac".toString()] as double, "", "")
        params.addDoubleParameter("mdet_${m.name}_absolute", "  ${m.name} absolute cut",
                resolved["mdet_${m.name}_absolute".toString()] as double, "", "0 = use the mode above.")
        params.addDoubleParameter("mdet_${m.name}_sigma_um", "  ${m.name} sigma",
                resolved["mdet_${m.name}_sigma_um".toString()] as double, "um", "")
        params.addDoubleParameter("mdet_${m.name}_min_area_um2", "  ${m.name} min area",
                resolved["mdet_${m.name}_min_area_um2".toString()] as double, "um^2", "")
        params.addDoubleParameter("mdet_${m.name}_max_area_um2", "  ${m.name} max area",
                resolved["mdet_${m.name}_max_area_um2".toString()] as double, "um^2", "")
    }
    params.addDoubleParameter("overlap_min_frac", "Overlap fraction for Double_overlap",
            resolved.overlap_min_frac as double, "",
            "intersection / smaller object. Reported in its OWN columns; never merged with the nucleus-anchored Double+.")

    params.addTitleParameter("Area / intensity — for fields where nuclei cannot be segmented")
    params.addBooleanParameter("measure_area", "Measure area + intensity per channel",
            resolved.measure_area as boolean,
            "Occupancy and brightness per ROI, no segmentation. This is the DG-sg answer: " +
            "area fractions and a DAPI+ area you can divide marker counts by.")
    areaCutChannels.each { c ->
        params.addChoiceParameter("acut_${c.name}_mode", "  ${c.name} area cut mode",
                resolved["acut_${c.name}_mode".toString()] as String, THRESHOLD_MODES, "")
        params.addDoubleParameter("acut_${c.name}_span_frac", "  ${c.name} area span fraction",
                resolved["acut_${c.name}_span_frac".toString()] as double, "", "")
        params.addDoubleParameter("acut_${c.name}_absolute", "  ${c.name} area absolute cut",
                resolved["acut_${c.name}_absolute".toString()] as double, "", "0 = use the mode above.")
    }
    params.addDoubleParameter("area_downsample", "Area measurement downsample",
            resolved.area_downsample as double, "x",
            "1 = full resolution. Raise it for very large ROIs to keep the pass fast.")
    params.addDoubleParameter("area_min_blob_um2", "Minimum blob size", resolved.area_min_blob_um2 as double, "um^2",
            "Drops specks from the BLOB statistics only. Area fraction and intensities are never filtered.")

    params.addTitleParameter("Passes")
    params.addBooleanParameter("count_nuclei", "Nucleus-anchored counting",
            resolved.count_nuclei as boolean,
            "Switch OFF for a field like DG-sg where you only want the area measures.")
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
    ["count_nuclei", "detect_markers", "measure_area"].each {
        resolved[it] = params.getBooleanParameterValue(it) as boolean
    }
    resolved.overlap_min_frac = params.getDoubleParameterValue("overlap_min_frac") as double
    resolved.area_downsample = params.getDoubleParameterValue("area_downsample") as double
    resolved.area_min_blob_um2 = params.getDoubleParameterValue("area_min_blob_um2") as double
    markers.each { m ->
        resolved["mdet_${m.name}_mode".toString()] = params.getChoiceParameterValue("mdet_${m.name}_mode") as String
        ["span_frac", "absolute", "sigma_um", "min_area_um2", "max_area_um2"].each { fld ->
            resolved["mdet_${m.name}_${fld}".toString()] = params.getDoubleParameterValue("mdet_${m.name}_${fld}") as double
        }
    }
    areaCutChannels.each { c ->
        resolved["acut_${c.name}_mode".toString()] = params.getChoiceParameterValue("acut_${c.name}_mode") as String
        ["span_frac", "absolute"].each { fld ->
            resolved["acut_${c.name}_${fld}".toString()] = params.getDoubleParameterValue("acut_${c.name}_${fld}") as double
        }
    }
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

/** Histogram of ONE channel over the union of the target ROIs only. */
def roiHistogram = { String chName ->
    double downsample = server.getDownsampleForResolution(Math.min(resLevel, server.nResolutions() - 1))
    int chIdx = channelNames.indexOf(chName)
    if (chIdx < 0) return null
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
                acc.add(raster.getSample(x, y, chIdx))
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
        return new ChannelHistogram(chName, bp)
    }
    def sp = new ShortProcessor(acc.size(), 1)
    for (int i = 0; i < acc.size(); i++) sp.set(i, 0, Math.min(acc[i], 65535))
    return new ChannelHistogram(chName, sp)
}

/**
 * Resolve a cut on ANY channel by the project's own rule, and report what every mode
 * would have given. Used three times over -- the anchor's segmentation cut, each
 * marker's independent-detection cut, and each channel's area-pass cut -- so all three
 * behave identically and a value can be compared between them without a footnote.
 *
 * Returns [value: Long|null, mode: String, image: Long|null, roi: Long|null,
 *          imageNote: String, roiNote: String].
 */
def resolveCut = { String chName, String mode, double frac, double absolute ->
    Long imgThr = null, roiThr = null
    String imgNote = "", roiNote = ""
    def cutFrom = { Integer floorV, Integer brightV ->
        if (floorV == null || brightV == null || brightV <= floorV) return null
        return Math.round(floorV + frac * (double) (brightV - floorV))
    }
    try {
        def tools = new ImageChannelTools(chName, imageData)
        def peak = { int nPeak ->
            def ap = new AutoThresholdParmameters()
            ap.setResolutionLevel(resLevel); ap.setSmoothWindowSize(smoothWin)
            ap.setnPeak(nPeak); ap.setPeakProminence(prominence)
            return WatershedCellDetectionConfig.findThreshold(tools, ap)
        }
        int fl = peak(1), br = peak(2)
        imgThr = cutFrom(fl, br)
        imgNote = "floor ${fl}, bright ${br}" + (imgThr == null ? " — unusable (bright <= floor)" : "")
    } catch (Throwable t) {
        imgNote = "could not be measured -- ${rootMessage(t)}"
    }
    try {
        def hist = roiHistogram(chName)
        if (hist == null) {
            roiNote = "no pixels inside the ROIs"
        } else {
            int fl = nthValidPeak(hist, 1), br = nthValidPeak(hist, 2)
            roiThr = cutFrom(fl, br)
            roiNote = "floor ${fl}, bright ${br}" + (roiThr == null ? " — unusable (bright <= floor)" : "")
        }
    } catch (Throwable t) {
        roiNote = "could not be measured -- ${rootMessage(t)}"
    }
    Long chosen
    if (mode == "absolute")      chosen = (absolute > 0) ? Math.round(absolute) : null
    else if (mode == "roi_span") chosen = roiThr
    else                         chosen = imgThr
    return [value: chosen, mode: mode, image: imgThr, roi: roiThr,
            imageNote: imgNote, roiNote: roiNote]
}

/** One-line report of every candidate for a channel, so disagreements stay visible. */
def printCutCandidates = { String label, String chName, Map r, double frac, double absolute ->
    println "${label} on ${chName} (span_frac ${frac})"
    println String.format("  image_span  %-10s  %s", r.image != null ? r.image.toString() : "n/a", r.imageNote)
    println String.format("  roi_span    %-10s  %s", r.roi != null ? r.roi.toString() : "n/a", r.roiNote)
    println String.format("  absolute    %-10s  %s", absolute > 0 ? Math.round(absolute).toString() : "not set",
            absolute > 0 ? "set by eye" : "set it in ROI Counting/notebooks/04_roi.ipynb")
    println "  USING ${r.mode} -> ${r.value != null ? r.value : 'UNAVAILABLE'}"
    if (r.image != null && r.roi != null) {
        double ratio = (double) Math.max(r.image, r.roi) / Math.max(1L, Math.min(r.image, r.roi))
        if (ratio > 1.5d)
            println String.format("  NOTE: the two automatic rules disagree by %.1fx. That is a fact about this " +
                    "image (usually: the ROIs are on tissue, the rest of the frame is not). Look at the mask before trusting either.", ratio)
    }
}

def spanCut = { Integer floorV, Integer brightV ->
    if (floorV == null || brightV == null || brightV <= floorV) return null
    return Math.round(floorV + spanFrac * (double) (brightV - floorV))
}

String thrMode = resolved.threshold_mode as String
println ""
def anchorCut = resolveCut(anchorChannel, thrMode, spanFrac, resolved.absolute as double)
printCutCandidates("ANCHOR THRESHOLD CANDIDATES", anchorChannel, anchorCut, spanFrac, resolved.absolute as double)
Long imageSpanThr = anchorCut.image, roiSpanThr = anchorCut.roi
String imageSpanNote = anchorCut.imageNote, roiSpanNote = anchorCut.roiNote

long anchorThreshold
if (thrMode == "absolute") {
    if ((resolved.absolute as double) <= 0) {
        println "ERROR: threshold_mode is 'absolute' but no absolute value is set."
        throw new RuntimeException("roi_count: absolute threshold mode with no value")
    }
    anchorThreshold = Math.round(resolved.absolute as double)
} else if (thrMode in ["roi_span", "image_span"]) {
    Long chosen = anchorCut.value
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
            println "      ROI Counting/notebooks/04_roi.ipynb section 3"
            println "  Then set threshold_mode 'absolute' with that value in the dialog."
            println ""
            println "  Worth trying first if you would rather keep an automatic rule: lower"
            println "  peak_prominence (currently ${prominence}), or raise resolution_level"
            println "  (currently ${resLevel}) so the histogram is binned more coarsely."
        } else {
            String other = (thrMode == "roi_span") ? "image_span" : "roi_span"
            println "  '${other}' DID measure a value on this image. Switching to it is reasonable,"
            println "  but it is a different rule -- ${other == 'image_span' ? 'the whole frame' : 'your ROIs only'} sets the endpoints."
            println "  Setting the cut by eye (ROI Counting/notebooks/04_roi.ipynb section 3, then mode"
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

// ═══════════════════════════════════════════════════════════════════════════════
// 7. DETECTION
// ═══════════════════════════════════════════════════════════════════════════════
def targetRois = targets.collect { it.getROI() }
def insideTargets = { detection ->
    def r = detection.getROI()
    double x = r.getCentroidX(), y = r.getCentroidY()
    return targetRois.any { it.contains(x, y) }
}

boolean countNuclei = resolved.count_nuclei as boolean
boolean detectMarkers = resolved.detect_markers as boolean
boolean measureArea = resolved.measure_area as boolean
if (!countNuclei && !detectMarkers && !measureArea) {
    println "ERROR: all three passes are switched off (count_nuclei, detect_markers,"
    println "       measure_area). There is nothing to compute. Enable at least one."
    throw new RuntimeException("roi_count: no pass enabled on ${imageName}")
}
println ""
println "passes: nucleus counting=${countNuclei}  independent marker detection=${detectMarkers}  area/intensity=${measureArea}"

// PathClass used for independently detected marker objects. It has to be distinct from
// the nucleus-anchored classes, because both live in the same hierarchy and every later
// step separates the two populations by class alone.
def markerObjClass = { m -> "${m.name}_obj".toString() }
def markerObjClassNames = markers.collect { markerObjClass(it) } as Set

if (countNuclei && stage == STAGE_FULL) {
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

// Independently detected marker objects share the hierarchy with the anchor-derived
// cells, so every later step separates them by PathClass. Without this filter a marker
// object would be treated as a nucleus and counted twice.
def allInside = getDetectionObjects().findAll { insideTargets(it) }
def dets = allInside.findAll { !markerObjClassNames.contains(it.getPathClass()?.toString()) }
if (countNuclei && dets.isEmpty()) {
    println ""
    println "NO DETECTIONS inside the ROIs."
    if (stage != STAGE_FULL) {
        println "  This run was '${stage}', which does not detect. Re-run with '${STAGE_FULL}'."
    } else {
        println "  The anchor cut (${anchorThreshold}) may be far too high for this image, or"
        println "  min/max area may exclude every object at this pixel size (see the acquisition"
        println "  check above). Set the cut by eye in ROI Counting/notebooks/04_roi.ipynb."
        println ""
        println "  If this ROI is somewhere nuclei genuinely cannot be segmented -- DG-sg and"
        println "  other densely packed layers -- that is what the area/intensity pass is for."
        println "  Switch count_nuclei off and measure_area on, and you get area fractions and"
        println "  intensities instead of counts, with no segmentation involved."
    }
    throw new RuntimeException("roi_count: no detections inside the ROIs on ${imageName}")
}
if (countNuclei) println "detections inside the ROIs: ${dets.size()}"

// ── Measurement-key self-check ─────────────────────────────────────────────────
// The anchor's own nuclear mean is exported so a negative-control pseudo-marker can be
// built downstream. It is read by an exact key string, and the failure mode when that
// key is wrong is SILENT: every cell reads null, the column exports blank, and nothing
// else misbehaves. So the key is resolved once, here, against the real key set, and a
// miss aborts with the available keys printed rather than shipping an empty column.
String anchorMeanKey = "Nucleus: ${anchorChannel} mean".toString()
def sampleKeySet = dets.isEmpty() ? ([] as Set) : dets.first().getMeasurements().keySet()
if (countNuclei && !dets.isEmpty() && !sampleKeySet.contains(anchorMeanKey)) {
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
if (countNuclei && !dets.isEmpty() && !wholeCellMarkers.isEmpty() && stage != STAGE_EXPORT) {
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

if (countNuclei && stage != STAGE_EXPORT) {
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
if (countNuclei && stage != STAGE_EXPORT) {
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
// 9b. INDEPENDENT MARKER DETECTION  (opt-in — NOT nucleus-anchored)
// ═══════════════════════════════════════════════════════════════════════════════
// Detects each marker on its OWN channel, with no reference to the anchor. Enabled by
// the operator (2026-08-06), overriding this project's nucleus-anchored-only rule.
//
// READ THIS BEFORE USING THE NUMBERS. Everything here is a WEAKER measurement than the
// nucleus-anchored counts above, for reasons that do not go away with tuning:
//
//   * A blob on the marker channel is not a cell. It can be a process, a piece of
//     neuropil, an autofluorescent speck, or two cells touching. The anchor channel is
//     what makes "one object = one cell" a defensible claim, and this pass does not
//     use it.
//   * `Double_overlap` is a PROXIMITY/OVERLAP metric. Two markers in the same place is
//     not the same statement as one nucleus carrying both, and on dense fields it is
//     systematically higher. It is emitted under its own column names and NEVER merged
//     with the nucleus-anchored `Double+`.
//
// What it is genuinely good for: fields where DAPI cannot be segmented at all, marker
// signal that is real but not nuclear, and a sanity check on whether the anchor-derived
// counts are missing whole populations.
def markerObjects = [:]        // marker name -> List<PathDetectionObject>
if (detectMarkers) {
    println ""
    println "-" * 78
    println "INDEPENDENT MARKER DETECTION — not nucleus-anchored, see the caveat in the log header"
    if (stage == STAGE_FULL) {
        // Clear only the previous run's marker objects; the anchor cells stay.
        def stale = allInside.findAll { markerObjClassNames.contains(it.getPathClass()?.toString()) }
        if (!stale.isEmpty()) {
            removeObjects(stale, false)
            println "  cleared ${stale.size()} marker object(s) from a previous run"
        }
        markers.each { m ->
            String mode = resolved["mdet_${m.name}_mode".toString()] as String
            double frac = resolved["mdet_${m.name}_span_frac".toString()] as double
            double abs  = resolved["mdet_${m.name}_absolute".toString()] as double
            def cut = resolveCut(m.channel, mode, frac, abs)
            println ""
            printCutCandidates("  ${m.name} DETECTION CUT", m.channel, cut, frac, abs)
            if (cut.value == null) {
                println "  ERROR: no usable cut for ${m.name} on ${m.channel}; skipping its independent detection."
                println "         Set mdet_${m.name}_absolute by eye and re-run, or switch detect_markers off."
                return
            }
            def cfg = new WatershedCellDetectionConfig()
            double reqPx = (resolved.requested_pixel_size_um as double)
            cfg.setRequestedPixelSizeMicrons(reqPx > 0 ? reqPx : pixelUm)
            cfg.setBackgroundRadiusMicrons(resolved.background_radius_um as double)
            cfg.setBackgroundByReconstruction(resolved.background_by_reconstruction as boolean)
            cfg.setMedianRadiusMicrons(resolved.median_radius_um as double)
            cfg.setSigmaMicrons(resolved["mdet_${m.name}_sigma_um".toString()] as double)
            cfg.setMinAreaMicrons(resolved["mdet_${m.name}_min_area_um2".toString()] as double)
            cfg.setMaxAreaMicrons(resolved["mdet_${m.name}_max_area_um2".toString()] as double)
            cfg.setThreshold(cut.value as double)
            cfg.setHistogramThreshold(null)
            cfg.setWatershedPostProcess(resolved.watershed_post_process as boolean)
            // No cell expansion: these ARE the objects, not nuclei to be grown from.
            cfg.setCellExpansionMicrons(0.0d)
            cfg.setIncludeNuclei(true)
            cfg.setSmoothBoundaries(resolved.smooth_boundaries as boolean)
            cfg.setMakeMeasurements(true)
            try {
                def cd = new ChannelDetections(new ImageChannelTools(m.channel, imageData),
                                               targets, cfg, hierarchy)
                def found = cd.toStream().collect(java.util.stream.Collectors.toList())
                found.each { it.setPathClass(getPathClass(markerObjClass(m))) }
                println "  ${m.name}: ${found.size()} object(s) detected on ${m.channel}"
            } catch (Throwable t) {
                println "  ERROR: ${m.name} detection failed (${rootMessage(t)}); skipping it."
            }
        }
        fireHierarchyUpdate()
    }
    // Harvest by class, so a classify-only or export-only re-run finds what a previous
    // full run detected instead of silently reporting zero.
    def afterInside = getDetectionObjects().findAll { insideTargets(it) }
    markers.each { m ->
        markerObjects[m.name] = afterInside.findAll { it.getPathClass()?.toString() == markerObjClass(m) }
    }
    if (stage != STAGE_FULL)
        println "  reusing marker objects from the previous run: " +
                markers.collect { "${it.name}=${markerObjects[it.name].size()}" }.join(", ")
    println "-" * 78
}

// ── Overlap-based Double+, greedy 1:1 ─────────────────────────────────────────────
// Pairs two markers' independently detected objects when
//     intersection_area / min(area_a, area_b) >= overlap_min_frac
// Matching is GREEDY AND ONE-TO-ONE, best overlap first: without that, one large blob
// would claim every small object near it and the "double" count could exceed the number
// of cells present. Still weaker than the nucleus-anchored call -- see the caveat above.
double overlapMinFrac = resolved.overlap_min_frac as double
def overlapPairs = [:]     // "A|B" -> matched pair count
if (detectMarkers && markers.size() >= 2) {
    for (int a = 0; a < markers.size(); a++) {
        for (int b = a + 1; b < markers.size(); b++) {
            def ma = markers[a], mb = markers[b]
            def objA = markerObjects[ma.name] ?: []
            def objB = markerObjects[mb.name] ?: []
            def candidates = []
            objA.each { oa ->
                def ga = oa.getROI().getGeometry()
                double areaA = ga.getArea()
                if (areaA <= 0) return
                objB.each { ob ->
                    def gb = ob.getROI().getGeometry()
                    double areaB = gb.getArea()
                    if (areaB <= 0) return
                    if (!ga.getEnvelopeInternal().intersects(gb.getEnvelopeInternal())) return
                    double inter
                    try { inter = ga.intersection(gb).getArea() } catch (Throwable ignored) { return }
                    if (inter <= 0) return
                    double frac = inter / Math.min(areaA, areaB)
                    if (frac >= overlapMinFrac) candidates << [a: oa, b: ob, frac: frac]
                }
            }
            candidates.sort { -it.frac }
            def usedA = [] as Set, usedB = [] as Set
            int matched = 0
            candidates.each { c ->
                if (usedA.contains(c.a) || usedB.contains(c.b)) return
                usedA << c.a; usedB << c.b; matched++
            }
            overlapPairs["${ma.name}|${mb.name}".toString()] = matched
            println String.format("  overlap %s x %s (>= %.2f of the smaller): %d matched pair(s) " +
                    "from %d and %d objects", ma.name, mb.name, overlapMinFrac, matched, objA.size(), objB.size())
        }
    }
}

// ═══════════════════════════════════════════════════════════════════════════════
// 9c. AREA / INTENSITY  (opt-in — no segmentation involved)
// ═══════════════════════════════════════════════════════════════════════════════
// For fields where per-nucleus segmentation is not defensible -- DG-sg and other
// densely packed layers -- this measures how much of the ROI each channel OCCUPIES,
// and how bright it is, with no object detection at all.
//
// Measured on RAW pixels, deliberately. The per-channel cut comes from the same
// floor + frac x (bright - floor) rule used everywhere else, and that rule's `floor` IS
// the background peak -- so the cut already sits above background and subtracting a
// background first would double-count the correction.
//
// The denominator that matters: `<anchor>_pos_area_mm2` is the area actually occupied
// by nuclei, which is what turns a marker count into "per mm^2 of DAPI+ tissue" rather
// than "per mm^2 of whatever shape I happened to draw".
def areaRows = []
def areaChannelOrder = areaCutChannels.collect { it.name }
if (measureArea) {
    println ""
    println "-" * 78
    println "AREA / INTENSITY — occupancy and brightness per ROI, no segmentation"
    double areaDs = Math.max(1.0d, resolved.area_downsample as double)
    double areaPxUm2 = (pixelUm * areaDs) * (pixelUm * areaDs)
    double minBlobUm2 = resolved.area_min_blob_um2 as double
    println String.format("  one pixel = %.3f um^2 at downsample %.1f; blobs below %.3f um^2 are dropped from the BLOB stats only",
            areaPxUm2, areaDs, minBlobUm2)

    // Resolve one cut per channel up front, from the WHOLE set of ROIs, so every shape
    // is measured against the same number. A per-shape cut would make two ROIs on one
    // section incomparable -- the same trap as k_scope=roi.
    def areaCuts = [:]
    areaCutChannels.each { c ->
        String mode = resolved["acut_${c.name}_mode".toString()] as String
        double frac = resolved["acut_${c.name}_span_frac".toString()] as double
        double abs  = resolved["acut_${c.name}_absolute".toString()] as double
        def cut = resolveCut(c.channel, mode, frac, abs)
        println ""
        printCutCandidates("  ${c.name} AREA CUT", c.channel, cut, frac, abs)
        areaCuts[c.name] = cut.value
        if (cut.value == null)
            println "  ${c.name}: no usable cut -- its area columns will be blank for this image."
    }

    println ""
    targets.each { ann ->
        def roi = ann.getROI()
        def request = RegionRequest.createInstance(server.getPath(), areaDs, roi)
        def img = server.readRegion(request)
        def mask = BufferedImageTools.createROIMask(img.getWidth(), img.getHeight(), roi, request)
        def raster = img.getRaster()
        def maskRaster = mask.getRaster()
        int w = img.getWidth(), h = img.getHeight()

        // In-ROI pixel indices, computed once and reused for every channel.
        boolean[] inRoi = new boolean[w * h]
        int nRoiPx = 0
        for (int y = 0; y < h; y++) {
            for (int x = 0; x < w; x++) {
                if (maskRaster.getSample(x, y, 0) != 0) { inRoi[y * w + x] = true; nRoiPx++ }
            }
        }
        def row = [roi_name: ann.getName(), z: roi.getImagePlane().getZ(),
                   roi_area_mm2: roi.getArea() * pxToMm2, per: [:]]

        areaCutChannels.each { c ->
            int chIdx = channelNames.indexOf(c.channel)
            Long cut = areaCuts[c.name]
            double sum = 0.0d, sumPos = 0.0d
            int nPos = 0
            boolean[] pos = new boolean[w * h]
            for (int i = 0; i < w * h; i++) {
                if (!inRoi[i]) continue
                int v = raster.getSample(i % w, (int) (i / w), chIdx)
                sum += v
                if (cut != null && v >= cut) { pos[i] = true; nPos++; sumPos += v }
            }
            // Connected above-cut blobs, 4-connected, iterative flood fill (an explicit
            // stack, not recursion -- a large ROI would blow the JVM stack).
            def blobAreas = []
            if (cut != null) {
                boolean[] seen = new boolean[w * h]
                int[] stack = new int[w * h]
                for (int start = 0; start < w * h; start++) {
                    if (!pos[start] || seen[start]) continue
                    int sp = 0; stack[sp++] = start; seen[start] = true; int size = 0
                    while (sp > 0) {
                        int cur = stack[--sp]; size++
                        int cx = cur % w, cy = (int) (cur / w)
                        if (cx > 0     && pos[cur - 1] && !seen[cur - 1]) { seen[cur - 1] = true; stack[sp++] = cur - 1 }
                        if (cx < w - 1 && pos[cur + 1] && !seen[cur + 1]) { seen[cur + 1] = true; stack[sp++] = cur + 1 }
                        if (cy > 0     && pos[cur - w] && !seen[cur - w]) { seen[cur - w] = true; stack[sp++] = cur - w }
                        if (cy < h - 1 && pos[cur + w] && !seen[cur + w]) { seen[cur + w] = true; stack[sp++] = cur + w }
                    }
                    double blobUm2 = size * areaPxUm2
                    if (blobUm2 >= minBlobUm2) blobAreas << blobUm2
                }
            }
            blobAreas.sort()
            def pct = { List xs, double q ->
                if (xs.isEmpty()) return Double.NaN
                int idx = (int) Math.min(xs.size() - 1, Math.max(0, Math.round(q * (xs.size() - 1))))
                return xs[idx] as double
            }
            row.per[c.name] = [
                cut          : cut,
                pos_area_mm2 : cut == null ? Double.NaN : nPos * areaPxUm2 / 1e6,
                area_frac    : cut == null || nRoiPx == 0 ? Double.NaN : (double) nPos / nRoiPx,
                mean         : nRoiPx == 0 ? Double.NaN : sum / nRoiPx,
                mean_pos     : nPos == 0 ? Double.NaN : sumPos / nPos,
                intden       : sum,
                blob_count   : cut == null ? -1 : blobAreas.size(),
                blob_median  : pct(blobAreas, 0.5d),
                blob_p90     : pct(blobAreas, 0.9d),
            ]
        }
        areaRows << row
        println String.format("  %-22s roi %8.5f mm^2   " + areaChannelOrder.collect { "%s %5.1f%%" }.join("  "),
                ([ann.getName(), row.roi_area_mm2] +
                 areaChannelOrder.collectMany { n ->
                     def pr = row.per[n]
                     [n, Double.isNaN(pr.area_frac) ? Double.NaN : 100.0d * pr.area_frac]
                 }) as Object[])
    }
    // A blob median at or near one pixel means the above-cut mask is SPECKLE, not
    // objects: the blob count is then counting noise, and it will swing wildly with a
    // small change in cut. Area fraction and the intensity measures are still fine --
    // they do not care about connectivity -- so this flags the blob columns only.
    def speckly = []
    areaChannelOrder.each { n ->
        def meds = areaRows.collect { it.per[n]?.blob_median }.findAll { it != null && !Double.isNaN(it) }
        if (!meds.isEmpty() && meds.min() <= 2.0d * areaPxUm2) speckly << n
    }
    if (!speckly.isEmpty()) {
        println ""
        println "  ADVISORY: ${speckly} have a median blob of 1-2 PIXELS. The above-cut mask is"
        println "  speckle rather than objects there, so blob_count is counting noise and will"
        println "  swing with any small change of cut. area_frac / mean / intden are unaffected."
        println "  Either raise that channel's cut, or set area_min_blob_um2 to a plausible"
        println "  minimum object size (a nucleus here is about ${String.format('%.0f', Math.PI * 25.0d)} um^2)."
    }
    println "-" * 78
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

// Independently detected objects and their overlap pairings are counted alongside, but
// under NAMES OF THEIR OWN -- "<M>_obj", "Double_overlap_<A>_<B>". They are never folded
// into CATEGORIES, so no consumer can add a nucleus-anchored count to an overlap-derived
// one by accident, which is the whole reason the two are kept apart.
def OBJ_CATEGORIES = detectMarkers ? (markers.collect { "${it.name}_obj".toString() } +
        overlapPairs.keySet().collect { "Double_overlap_${it.replace('|', '_')}".toString() }) : []
def zeroCounts = { (CATEGORIES + OBJ_CATEGORIES).collectEntries { [(it): 0] } }

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
    // Independently detected marker objects whose centroid falls in this shape.
    if (detectMarkers) {
        markers.each { m ->
            counts["${m.name}_obj".toString()] = (markerObjects[m.name] ?: []).count {
                roi.contains(it.getROI().getCentroidX(), it.getROI().getCentroidY())
            }
        }
        // Overlap pairs are matched over ALL ROIs at once (the matching is global and
        // one-to-one), so a per-shape split would have to re-match and could disagree
        // with the total. Attribute each pair to the shape containing the FIRST marker's
        // object instead, and say so in the docs.
        overlapPairs.each { key, total ->
            def parts = key.split("\\|")
            def objA = markerObjects[parts[0]] ?: []
            int inShape = objA.count { roi.contains(it.getROI().getCentroidX(), it.getROI().getCentroidY()) }
            int share = objA.isEmpty() ? 0 : (int) Math.round(total * (inShape / (double) objA.size()))
            counts["Double_overlap_${parts[0]}_${parts[1]}".toString()] = share
        }
    }
    // Roll the counts onto the annotation so they show in QuPath's measurement table.
    def ml = ann.getMeasurementList()
    CATEGORIES.each { cat -> ml.put("Count: ${classFor(cat)}".toString(), (counts[cat] ?: 0) as double) }
    OBJ_CATEGORIES.each { cat -> ml.put("Count: ${cat}".toString(), (counts[cat] ?: 0) as double) }
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
    (CATEGORIES + OBJ_CATEGORIES).each { cat -> p.counts[cat] = p.counts[cat] + (s.counts[cat] ?: 0) }
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
    count_nuclei          : countNuclei,
    detect_markers        : detectMarkers,
    measure_area          : measureArea,
    overlap_min_frac      : detectMarkers ? resolved.overlap_min_frac : "",
    area_downsample       : measureArea ? resolved.area_downsample : "",
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
// Only written when there are anchor-derived cells to describe. An area-only run on a
// field like DG-sg produces no per-cell rows by design, and an empty file with a header
// would read as "detection found nothing" rather than "detection was not attempted".
if (countNuclei) percellFile.text = percellSb.toString()

// -- per-ROI TSV: every shape, then every pooled name.
def countHeader = (["scope", "roi_name", "n_shapes", "z", "area_um2", "area_mm2"] +
        CATEGORIES.collectMany { c -> ["${columnPrefixFor(c)}_count", "${columnPrefixFor(c)}_density"] } +
        OBJ_CATEGORIES.collectMany { c -> ["${c}_count", "${c}_density"] }).join("\t")
def countsSb = new StringBuilder().append(countHeader).append("\n")
def countRow = { String scope, String name, int nShapes, def z, double areaUm2, double areaMm2, Map counts ->
    def cells = [scope, name, nShapes, z == null ? "" : z, String.format('%.2f', areaUm2), String.format('%.6f', areaMm2)]
    (CATEGORIES + OBJ_CATEGORIES).each { cat ->
        int cnt = (counts[cat] ?: 0) as int
        cells << cnt
        cells << (areaMm2 > 0 ? String.format('%.2f', cnt / areaMm2) : "")
    }
    return cells.join("\t")
}
perShape.each { s -> countsSb.append(countRow("shape", s.name, 1, s.z, s.areaUm2, s.areaMm2, s.counts)).append("\n") }
pooled.each { name, p -> countsSb.append(countRow("pooled", name, p.nShapes, null, p.areaUm2, p.areaMm2, p.counts)).append("\n") }
def countsFile = new File(outDir, "${stem}__roi_counts.tsv")
if (countNuclei || detectMarkers) countsFile.text = countsSb.toString()

// -- growing combined CSV: one row per (image x roi x class), provenance on every row.
def provKeys = provenance.keySet().toList()
def combined = new File(outDir, "roi_counts_combined.csv")
// `anchoring` is the column that keeps the override honest downstream: every row says
// whether its count came from the nucleus-anchored rule or from independent detection +
// overlap. A consumer that ignores it can still not confuse the two, because the class
// names differ as well -- but this makes filtering a one-liner.
def combinedHeader = (["scope", "roi_name", "n_shapes", "z", "area_mm2", "marker", "class",
                       "anchoring", "count", "density"] + provKeys).join(",")
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
        def cells = [scope, name, nShapes, z == null ? "" : z, String.format('%.6f', areaMm2), cat, classFor(cat),
                     "nucleus-anchored", cnt, areaMm2 > 0 ? String.format('%.2f', cnt / areaMm2) : ""]
        provKeys.each { k -> cells << provenance[k] }
        combinedSb.append(cells.collect { csvQ(it) }.join(",")).append("\n")
        nRows++
    }
    // Independently detected objects and their overlap pairings, in the SAME long table
    // but tagged anchoring=independent-overlap. Filtering on that column is what keeps a
    // downstream consumer from adding a nucleus-anchored count to an overlap-derived one.
    OBJ_CATEGORIES.each { cat ->
        int cnt = (counts[cat] ?: 0) as int
        def cells = [scope, name, nShapes, z == null ? "" : z, String.format('%.6f', areaMm2), cat, cat,
                     "independent-overlap", cnt, areaMm2 > 0 ? String.format('%.2f', cnt / areaMm2) : ""]
        provKeys.each { k -> cells << provenance[k] }
        combinedSb.append(cells.collect { csvQ(it) }.join(",")).append("\n")
        nRows++
    }
}
perShape.each { s -> emit("shape", s.name, 1, s.z, s.areaMm2, s.counts) }
pooled.each { name, p -> emit("pooled", name, p.nShapes, null, p.areaMm2, p.counts) }
if (countNuclei || detectMarkers) combined.append(combinedSb.toString())

// ── Area / intensity exports ──────────────────────────────────────────────────
// Kept in FILES OF THEIR OWN rather than as extra columns on the count tables. An
// area-only run (DG-sg and friends) then produces a complete, self-consistent file
// instead of a count table full of blanks, and a run with both produces two files that
// join cleanly on (image, roi_name, scope).
def areaFile = new File(outDir, "${stem}__roi_area.tsv")
def areaCombined = new File(outDir, "roi_area_combined.csv")
int nAreaRows = 0
if (measureArea) {
    def areaMetrics = ["cut", "pos_area_mm2", "area_frac", "mean", "mean_pos", "intden",
                       "blob_count", "blob_median_um2", "blob_p90_um2"]
    def areaHeader = (["scope", "roi_name", "n_shapes", "z", "roi_area_mm2"] +
            areaChannelOrder.collectMany { n -> areaMetrics.collect { "${n}_${it}" } }).join("\t")
    def num = { v, String pat -> (v == null || (v instanceof Double && Double.isNaN(v))) ? "" : String.format(pat, v) }
    def areaCells = { String scope, String name, int nShapes, def z, double roiMm2, Map per ->
        def cells = [scope, name, nShapes, z == null ? "" : z, String.format('%.6f', roiMm2)]
        areaChannelOrder.each { n ->
            def r = per[n]
            cells << (r?.cut == null ? "" : r.cut)
            cells << num(r?.pos_area_mm2, '%.8f')
            cells << num(r?.area_frac, '%.6f')
            cells << num(r?.mean, '%.4f')
            cells << num(r?.mean_pos, '%.4f')
            cells << num(r?.intden, '%.1f')
            cells << ((r?.blob_count == null || r.blob_count < 0) ? "" : r.blob_count)
            cells << num(r?.blob_median, '%.3f')
            cells << num(r?.blob_p90, '%.3f')
        }
        return cells
    }
    // Pooled area rows SUM the areas and RE-DERIVE the fractions from those sums --
    // never an average of per-shape fractions, which would weight a small shape as
    // heavily as a large one (the same rule the registered route follows for rates).
    def areaPooled = [:] as LinkedHashMap
    areaRows.each { r ->
        def q = areaPooled.computeIfAbsent(r.roi_name) {
            [n: 0, roiMm2: 0.0d, per: areaChannelOrder.collectEntries { [(it): [pos: 0.0d, sum: 0.0d, sumPos: 0.0d, nPos: 0.0d, blobs: 0, cut: null]] }]
        }
        q.n = q.n + 1
        q.roiMm2 = q.roiMm2 + r.roi_area_mm2
        areaChannelOrder.each { n ->
            def src = r.per[n], dst = q.per[n]
            if (src.cut != null) dst.cut = src.cut
            if (!Double.isNaN(src.pos_area_mm2)) dst.pos = dst.pos + src.pos_area_mm2
            if (!Double.isNaN(src.intden)) dst.sum = dst.sum + src.intden
            if (src.blob_count != null && src.blob_count >= 0) dst.blobs = dst.blobs + src.blob_count
        }
    }
    def areaSb = new StringBuilder().append(areaHeader).append("\n")
    areaRows.each { r ->
        areaSb.append(areaCells("shape", r.roi_name, 1, r.z, r.roi_area_mm2, r.per).join("\t")).append("\n")
    }
    areaPooled.each { name, q ->
        def per = [:]
        areaChannelOrder.each { n ->
            def d = q.per[n]
            per[n] = [cut: d.cut, pos_area_mm2: d.pos,
                      area_frac: q.roiMm2 > 0 ? d.pos / q.roiMm2 : Double.NaN,
                      mean: Double.NaN, mean_pos: Double.NaN, intden: d.sum,
                      blob_count: d.blobs, blob_median: Double.NaN, blob_p90: Double.NaN]
        }
        areaSb.append(areaCells("pooled", name, q.n, null, q.roiMm2, per).join("\t")).append("\n")
    }
    areaFile.text = areaSb.toString()

    // Growing cross-image area CSV, same replace-this-image semantics as the counts one.
    def areaCombinedHeader = (["scope", "roi_name", "n_shapes", "z", "roi_area_mm2", "channel"] +
            ["cut", "pos_area_mm2", "area_frac", "mean", "mean_pos", "intden",
             "blob_count", "blob_median_um2", "blob_p90_um2"] + provKeys).join(",")
    if (!areaCombined.exists() || areaCombined.readLines().findAll { !it.trim().isEmpty() }[0] != areaCombinedHeader) {
        if (areaCombined.exists()) {
            def stamp2 = new java.text.SimpleDateFormat('yyyyMMdd-HHmmss').format(new Date())
            areaCombined.renameTo(new File(outDir, "roi_area_combined.${stamp2}.csv"))
            println "NOTE: roi_area_combined.csv had a different column set; moved it aside."
        }
        areaCombined.text = areaCombinedHeader + "\n"
    } else {
        def ex = areaCombined.readLines().findAll { !it.trim().isEmpty() }
        int ic = ex[0].split(",", -1).findIndexOf { it == "image" }
        def kept = ex.drop(1).findAll { ic < 0 || csvSplit(it)[ic] != imageName }
        areaCombined.text = ([areaCombinedHeader] + kept).join("\n") + "\n"
    }
    def acSb = new StringBuilder()
    def emitArea = { String scope, String name, int nShapes, def z, double roiMm2, Map per ->
        areaChannelOrder.each { n ->
            def r = per[n]
            def cells = [scope, name, nShapes, z == null ? "" : z, String.format('%.6f', roiMm2), n,
                         r?.cut == null ? "" : r.cut,
                         num(r?.pos_area_mm2, '%.8f'), num(r?.area_frac, '%.6f'),
                         num(r?.mean, '%.4f'), num(r?.mean_pos, '%.4f'), num(r?.intden, '%.1f'),
                         (r?.blob_count == null || r.blob_count < 0) ? "" : r.blob_count,
                         num(r?.blob_median, '%.3f'), num(r?.blob_p90, '%.3f')]
            provKeys.each { k -> cells << provenance[k] }
            acSb.append(cells.collect { csvQ(it) }.join(",")).append("\n")
            nAreaRows++
        }
    }
    areaRows.each { r -> emitArea("shape", r.roi_name, 1, r.z, r.roi_area_mm2, r.per) }
    areaPooled.each { name, q ->
        def per = [:]
        areaChannelOrder.each { n ->
            def d = q.per[n]
            per[n] = [cut: d.cut, pos_area_mm2: d.pos,
                      area_frac: q.roiMm2 > 0 ? d.pos / q.roiMm2 : Double.NaN,
                      mean: Double.NaN, mean_pos: Double.NaN, intden: d.sum,
                      blob_count: d.blobs, blob_median: Double.NaN, blob_p90: Double.NaN]
        }
        emitArea("pooled", name, q.n, null, q.roiMm2, per)
    }
    areaCombined.append(acSb.toString())
}

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
// Dynamic per-marker keys (mdet_* independent detection, acut_* area cuts). Written
// even when their pass did not run this time, so the values you tuned are still there
// the next time you switch the pass on.
resolved.keySet().toSorted().each { k ->
    if (isDynamicKey(k) && !block.containsKey(k)) block[k] = resolved[k]
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
resolved.keySet().toSorted().each { k ->
    if (!isDynamicKey(k) || k.startsWith("k_") || k.startsWith("abs_")) return
    sb.append("  ${k}: ${ymlVal(stored.defaults.containsKey(k) ? stored.defaults[k] : resolved[k])}\n")
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
def SHOW = CATEGORIES + OBJ_CATEGORIES
def labelFor = { String cat -> OBJ_CATEGORIES.contains(cat) ? cat : classFor(cat) }
def hdr = String.format("  %-22s %6s %10s", "ROI", "z", "area mm^2") +
        SHOW.collect { String.format(" %14s %10s", labelFor(it), "per mm^2") }.join("")
if (countNuclei || detectMarkers) println hdr
if (countNuclei || detectMarkers) perShape.each { s ->
    println String.format("  %-22s %6d %10.5f", s.name, s.z, s.areaMm2) +
            SHOW.collect { cat ->
                int c = (s.counts[cat] ?: 0) as int
                String.format(" %14d %10s", c, s.areaMm2 > 0 ? String.format("%,.0f", c / s.areaMm2) : "-")
            }.join("")
}
if ((countNuclei || detectMarkers) && pooled.size() != perShape.size()) {
    println "  " + "-" * (hdr.length() - 2)
    pooled.each { name, p ->
        println String.format("  %-22s %6s %10.5f", "${name} (x${p.nShapes})", "", p.areaMm2) +
                SHOW.collect { cat ->
                    int c = (p.counts[cat] ?: 0) as int
                    String.format(" %14d %10s", c, p.areaMm2 > 0 ? String.format("%,.0f", c / p.areaMm2) : "-")
                }.join("")
    }
}
if (emitDouble && countNuclei) {
    println ""
    println "  Double+ means ONE nucleus called positive for two markers — never two nearby cells."
    markers.each { m ->
        int tot = perShape.sum { (it.counts[m.name] ?: 0) as int } as int
        int dbl = perShape.sum { (it.counts["Double+"] ?: 0) as int } as int
        println String.format("  Double+ / %s+ over all ROIs: %s", m.name, tot > 0 ? String.format("%.3f", (double) dbl / tot) : "n/a")
    }
}
if (detectMarkers) {
    println ""
    println "  <M>_obj and Double_overlap_* are NOT nucleus-anchored."
    println "  A marker-channel blob is not necessarily a cell, and 'two markers in the same"
    println "  place' is a weaker claim than 'one nucleus carrying both'. They are reported in"
    println "  their own columns and tagged anchoring=independent-overlap in the combined CSV."
    println "  Do not add them to, or compare them against, the nucleus-anchored numbers above."
}
if (measureArea) {
    println ""
    println "  AREA / INTENSITY (per ROI, no segmentation)"
    println String.format("  %-22s %10s", "ROI", "area mm^2") +
            areaChannelOrder.collect { String.format(" %10s %12s", "${it} %", "${it} mm^2") }.join("")
    areaRows.each { r ->
        println String.format("  %-22s %10.5f", r.roi_name, r.roi_area_mm2) +
                areaChannelOrder.collect { n ->
                    def pr = r.per[n]
                    String.format(" %10s %12s",
                        Double.isNaN(pr.area_frac) ? "-" : String.format("%.2f", 100.0d * pr.area_frac),
                        Double.isNaN(pr.pos_area_mm2) ? "-" : String.format("%.6f", pr.pos_area_mm2))
                }.join("")
    }
    if (countNuclei) {
        println ""
        println "  MARKER COUNT PER ${anchorName}+ AREA — counts normalised to the area actually"
        println "  occupied by nuclei rather than to the shape you drew:"
        areaRows.each { r ->
            def shape = perShape.find { it.name == r.roi_name }
            double denom = r.per[anchorName]?.pos_area_mm2 ?: Double.NaN
            if (shape == null || Double.isNaN(denom) || denom <= 0) return
            println String.format("    %-20s %s", r.roi_name,
                markers.collect { m ->
                    String.format("%s %,.0f/mm^2 ${anchorName}+", m.name, ((shape.counts[m.name] ?: 0) as int) / denom)
                }.join("   "))
        }
    }
}
println ""
println "  anchor cut ${anchorThreshold} (${thrMode})   settings_hash ${settingsHash}"
println "  Rows with a different settings_hash were produced by a different rule."
println "  Pool them only deliberately — ROI Counting/notebooks/04_roi.ipynb flags it."
println ""
println "  wrote:"
if (countNuclei)                    println "    ${percellFile.name}   (${dets.size()} cells)"
if (countNuclei || detectMarkers)   println "    ${countsFile.name}    (${perShape.size()} shapes, ${pooled.size()} pooled)"
if (countNuclei || detectMarkers)   println "    ${combined.name}      (+${nRows} rows)"
if (measureArea)                    println "    ${areaFile.name}      (${areaRows.size()} shapes x ${areaChannelOrder.size()} channels)"
if (measureArea)                    println "    ${areaCombined.name}  (+${nAreaRows} rows)"
println "    roi_settings.yml      (this image's block updated)"
println "  in  ${outDir}"
println ""
println "  NEXT: look at the overlay. If the DAPI segmentation or the marker calls look"
println "  wrong, they are wrong — re-run with different settings. '${STAGE_CLASSIFY}'"
println "  re-cuts the markers in seconds without re-detecting."
println "=" * 78
