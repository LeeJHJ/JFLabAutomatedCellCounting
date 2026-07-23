/**
 * 03_export_region_table.groovy — consolidated config-driven per-region readout (D-07)
 *
 * SCOPE: This script does NOT detect or classify. It MUST run AFTER
 * 02_detect_classify.groovy has already run and been SAVED on the current
 * entry — it reads getPathClass() (set by 02_detect_classify.groovy's
 * config-driven compound classification loop) and the local-background-
 * subtracted measurement keys that script writes
 * ("<CompartmentLabel>: <channel> mean (bg-sub)"). Running this before
 * classification will produce a per-cell export with class="Negative" for
 * everything and NaN bg-sub columns (the exact Phase-3 D-04/D-05
 * all-Negative symptom).
 *
 * This is the phase-06.1 consolidated export (D-07): it fuses
 * export_region_dapi_reference.groovy's all-region loop + config_tag +
 * growing-CSV append pattern with 03_export_val01_metrics.groovy's CR-01
 * geometric leaf resolution + per-cell TSV + per-entry non-clobbering stem,
 * generalized from DAPI-only to every marker declared in pipeline.yml (D-01).
 * It takes over the numbered "03 = export" slot; the old
 * 03_export_val01_metrics.groovy and export_region_dapi_reference.groovy are
 * archived once this script is validated end-to-end (06.1-04).
 *
 * Emits, per project entry (EXP-02: output paths are a function of the
 * sanitized running entry name + stable entry id, so "Run for project"
 * never truncates/clobbers across entries):
 *   1. results/<stem>__percell_export.tsv — one row per detection: class,
 *      region_label, nucleus_area_um2, centroid_x_px, centroid_y_px, then one
 *      "<marker>_bgsub" column PER declared non-anchor marker (D-04 — no
 *      fixed Fos/TdT pair; a TdT-only config emits only a TdT_bgsub column).
 *   2. results/<stem>__region_table.tsv — one row per atlas-region
 *      annotation (leaves AND parent rollups, D-10): region_label,
 *      hemisphere, acronym, is_leaf, area_mm2, then per-declared-category
 *      count+density columns (D-11: density = count / area_mm2). Parent rows
 *      are the leaf-summed ancestor-walk rollup — NEVER an independent
 *      centroid-in-parent-ROI containment pass (that would reintroduce the
 *      CR-01 leak this script's zero-leak assertion guards against).
 *   3. reference/region_marker_combined.csv — growing long/tidy combined CSV
 *      (D-12/D-13), header-guarded idempotent append, one row per
 *      region x declared-category, tagged by slice + BraiAn.yml config_tag.
 *
 * Downstream: Phase 10 (AGG-01, EXP-03/04) consumes the per-slice region
 * table and the growing combined CSV as the per-slice/per-region spine.
 *
 * Deploy: author in canonical scripts/, hard-copy byte-identically into
 * <QuPath project>/scripts/ (dual-location deploy, established convention).
 * Run via "Run for project" (human-run, per the GUI/scriptable split).
 *
 * @author section-pipeline
 */
import qupath.ext.biop.abba.AtlasTools
import static qupath.lib.scripting.QP.*

// ── Entry confirmation ──────────────────────────────────────────────────────
println "Running on: " + getCurrentImageData().getServer().getMetadata().getName()

// ── D-01/D-02/D-09/D-14: pipeline.yml sidecar config reader ─────────────────
// Same line-based mini-parser as 02_detect_classify.groovy (no YAML library
// ships with QuPath's bundled Groovy): anchor{name,channel},
// markers[]{name,channel,compartment}, exclude_acronyms[], k_robust,
// ring{gap_um,width_um}. Comments (# ...) stripped before parsing, tracking
// quote state so a '#' inside a quoted string is never mistaken for a
// comment marker.
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

// ── Fail-loud: every required key must be present (D-15) ───────────────────
def missingKeys = []
if (anchorName == null)    missingKeys << "anchor.name"
if (anchorChannel == null) missingKeys << "anchor.channel"
if (markers.isEmpty())     missingKeys << "markers (empty or missing)"
markers.eachWithIndex { m, idx ->
    if (m.channel == null)     missingKeys << "markers[${idx}].channel (name=${m.name})"
    if (m.compartment == null) missingKeys << "markers[${idx}].compartment (name=${m.name})"
    else if (!(m.compartment in ["nuclear", "cytoplasmic"]))
        missingKeys << "markers[${idx}].compartment invalid value '${m.compartment}' (name=${m.name}; must be nuclear or cytoplasmic)"
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
def COMPARTMENT_LABELS = [nuclear: "Nucleus", cytoplasmic: "Cytoplasm"]
// D-03: Double+ is structurally possible only when >=2 non-anchor markers are declared.
boolean emitDouble = markers.size() >= 2

// ── image/server/hierarchy handles ──────────────────────────────────────────
def imageData = getCurrentImageData()
def server = imageData.getServer()
def hierarchy = imageData.getHierarchy()

// ── D-15 guard 1: ABBA registration present ─────────────────────────────────
def availableAtlases = AtlasTools.getAvailableAtlasRegistration(imageData)
if (availableAtlases.isEmpty()) {
    println "ERROR: No ABBA registration files found in data directory."
    println "       Run ABBA export from Fiji first:"
    println "       Plugins > Atlas > Multi Image To Atlas > Export"
    println "       -> 'ABBA - Export Registrations To QuPath Project'"
    return
}
println "Found ABBA registrations: ${availableAtlases}"

// ── D-15 guard 2: detections present ────────────────────────────────────────
def dets = getDetectionObjects()
if (dets.isEmpty()) {
    println "No detections — run BraiAnDetect (run_braian_detection.groovy) and 02_detect_classify.groovy first. Aborting."
    return
}

// ── D-15 guard 3: config-declared channels present on this image ───────────
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

// ── pixel calibration (verbatim idiom, shared across the project's scripts) ─
def FALLBACK_PIXEL_SIZE_UM = 0.6905355   // server.json PhysicalSizeX, M3 062926 3 plane entry 1
def cal = server.getPixelCalibration()
def pixelUm = FALLBACK_PIXEL_SIZE_UM
if (cal != null && cal.hasPixelSizeMicrons()) {
    pixelUm = cal.getAveragedPixelSizeMicrons()
    println "Pixel size read from image server: ${pixelUm} µm/px"
} else {
    println "WARNING: image server has no pixel calibration -- falling back to hard-coded ${FALLBACK_PIXEL_SIZE_UM} µm/px (server.json PhysicalSizeX)"
}
def pxToMm2 = (pixelUm * 1e-3) ** 2
def pxToUm2 = pixelUm * pixelUm   // px² → µm²; nucleus area computed from ROI geometry (below), never a stored shape measurement

// ── region resolution (CR-01 fix, reused verbatim from 03_export_val01_metrics.groovy) ──
// Candidate atlas-region annotations = every annotation carrying a region label that is NOT a
// detection container. Keep ALL regions as candidates (leaves AND parents) and resolve each
// detection to the SMALLEST containing region (finest/true leaf) rather than trusting any
// child-emptiness heuristic (which let ~95k cells leak into a `grey` rollup in Phase 4).
def regionAnnotations = getAnnotationObjects().findAll { ann ->
    def roi = ann.getROI()
    if (roi == null) return false
    if (ann.getChildObjects().any { it.isDetection() }) return false     // skip the detection container(s)
    def lbl = ann.getPathClass()?.toString() ?: ann.getName()
    lbl != null && lbl != "AllDetections"
}
// Pre-sort ascending by ROI area so a short-circuiting `.find` returns the SMALLEST containing
// region (finest/most-specific) without an O(cells×regions) findAll+min blowup on ~200k cells.
def regionAnnotationsByArea = regionAnnotations.toSorted { it.getROI().getArea() }
def regionAnnotationSet = regionAnnotations as Set
println "Candidate region annotations for labeling: ${regionAnnotations.size()}"

def regionOf = { detection ->
    def r = detection.getROI()
    double x = r.getCentroidX(), y = r.getCentroidY()
    regionAnnotationsByArea.find { it.getROI().contains(x, y) }          // smallest containing = true leaf
}

// Geometric is_leaf (CR-01 fix): a region is a leaf iff NO smaller region's centroid falls inside
// it — nothing finer is nested within. Topology-independent, so it cannot disagree across
// hemispheres the way the child-annotation heuristic did.
def isLeafOf = { ann ->
    def roi = ann.getROI()
    double a = roi.getArea()
    !regionAnnotations.any { other ->
        if (other.is(ann)) return false
        def oroi = other.getROI()
        oroi.getArea() < a && roi.contains(oroi.getCentroidX(), oroi.getCentroidY())
    }
}

def regionLabel = { region ->
    if (region == null) return "(no region)"
    def label = region.getPathClass()?.toString() ?: region.getName()
    if (label == null) return "(no region)"
    def m = (label =~ /(?i)^(?:Left|Right):\s*(.+)$/)
    return m.find() ? m.group(1) : label
}

// ── measurement-key read helper (per declared marker, config-driven — D-04) ─
// Safe numeric read: never dereference a measurement without a null guard.
def numOrNaN = { measMap, String key ->
    def v = measMap.get(key)
    return (v == null || Double.isNaN(v.doubleValue())) ? Double.NaN : v.doubleValue()
}

// ── per-entry output stem (EXP-02 fix, D-06/D-07 idiom, reused verbatim) ───
// Output filenames MUST be a function of the running project entry, evaluated per-entry INSIDE
// "Run for project" — a fixed filename here means every entry after the first truncates/overwrites
// the previous one's export. Anchor the stem on the project entry's STABLE, UNIQUE id so distinct
// entries can never share a filename; keep the sanitized display name only as a human-readable prefix.
def invalidChars = (['<', '>', ':', '"', '/', '\\', '|', '?', '*'] as Set)
    .collect { java.util.regex.Pattern.quote(it) }.join('|')
def entry = getProjectEntry()
def rawName = (entry != null ? entry.getImageName() : getCurrentImageData().getServer().getMetadata().getName())
def safeName = (rawName != null ? rawName : "").replaceAll(invalidChars, '')
def entryId = (entry != null ? entry.getID() : "").replaceAll(invalidChars, '')
def stem = (entryId != null && !entryId.trim().isEmpty()) ? "${safeName}__id${entryId}" : safeName
if (stem == null || stem.trim().isEmpty()) {
    throw new RuntimeException("EXP-02: sanitized entry stem is empty -- refusing to write an unnamed export file (T-05-02-02). Check getProjectEntry().getID()/getImageName() for this entry.")
}

// ── per-cell export (D-07, generalized to N declared markers — D-04) ───────
println "Exporting per-cell measurements for ${dets.size()} detections..."
def percellRows = []
int nProcessed = 0
dets.each { d ->
    def m = d.getMeasurements()
    def cls = d.getPathClass()?.toString() ?: "Negative"
    def region = regionOf(d)
    def label = regionLabel(region)
    // Nucleus area from ROI geometry (never a stored shape measurement -- BraiAnDetect
    // detections carry no "Nucleus: Area µm^2" measurement; reading one returns null -> NaN
    // for every cell, the exact all-null column caught at the Phase-4 human-verify gate).
    def nucleusRoi = (d.respondsTo('getNucleusROI') && d.getNucleusROI() != null) ? d.getNucleusROI() : d.getROI()
    def areaUm2 = (nucleusRoi != null) ? nucleusRoi.getArea() * pxToUm2 : Double.NaN
    def r = d.getROI()
    double cx = r != null ? r.getCentroidX() : Double.NaN
    double cy = r != null ? r.getCentroidY() : Double.NaN
    def row = [cls, label, areaUm2, cx, cy]
    // One <marker>_bgsub column PER declared non-anchor marker (D-04) -- never a fixed
    // two-column fos/tdt read; a TdT-only config emits only a TdT_bgsub column here.
    markers.each { marker ->
        String compLabel = COMPARTMENT_LABELS[marker.compartment]
        String bgsubKey = "${compLabel}: ${marker.channel} mean (bg-sub)"
        row << numOrNaN(m, bgsubKey)
    }
    percellRows << row
    nProcessed++
    if (nProcessed % 5000 == 0) println "  ...exported ${nProcessed}/${dets.size()} detections"
}

def percellFile = new File(buildPathInProject("results", "${stem}__percell_export.tsv"))
// centroid_*_px are IMAGE-space pixel coordinates (not CCFv3 atlas microns) — the _px suffix keeps
// that explicit per CLAUDE.md's micron-export rule; they are diagnostic only, unused downstream.
def percellHeader = (["class", "region_label", "nucleus_area_um2", "centroid_x_px", "centroid_y_px"] +
        markers.collect { "${it.name}_bgsub" }).join("\t")
def percellSb = new StringBuilder()
percellSb.append(percellHeader).append("\n")
percellRows.each { row ->
    def fixedCols = [row[0], row[1],
        Double.isNaN(row[2]) ? "" : String.format('%.4f', row[2]),
        Double.isNaN(row[3]) ? "" : String.format('%.3f', row[3]),
        Double.isNaN(row[4]) ? "" : String.format('%.3f', row[4])]
    def markerCols = (5..<row.size()).collect { idx -> Double.isNaN(row[idx]) ? "" : String.format('%.4f', row[idx]) }
    percellSb.append((fixedCols + markerCols).join("\t")).append("\n")
}
// Overwrite (truncate) each run — this is a per-run snapshot, not a growing cross-image reference.
percellFile.text = percellSb.toString()
println "Wrote ${percellRows.size()} per-cell rows -> ${percellFile}"

// ── D-10: leaf tally + ancestor-walk parent rollup (zero-leak) ─────────────
// Category order matches the D-04/derive_contract column order: anchor total
// first, then per-marker positive (including Double+), then Double+ itself
// (only when emitDouble). columnPrefixFor is the WIDE-TABLE column prefix
// (anchor gets NO "+" -- matches scripts/validate_pipeline_config.py's
// derive_contract columns: "<anchor>_count"/"<anchor>_density"); classFor is
// the combined-CSV class LABEL (anchor DOES get a "+" -- "<anchor.name>+",
// per D-13). These intentionally differ; do not collapse them into one.
def CATEGORIES = ([anchorName] + markers.collect { it.name } + (emitDouble ? ["Double+"] : []))
def columnPrefixFor = { String cat -> (cat == "Double+" || cat == anchorName) ? cat : "${cat}+" }
def classFor = { String cat -> cat == "Double+" ? "Double+" : "${cat}+" }
def zeroCounts = { CATEGORIES.collectEntries { [(it): 0] } }

// ownCounts: per-resolved-annotation, per-category tally -- the "leaf" bucket
// as CR-01's regionOf resolves it (occasionally a non-geometric-leaf rollup
// annotation, for a cell whose centroid falls in no finer subregion).
def ownCounts = [:]   // annotation -> [category: count]
int nClassified = 0, nExcluded = 0, nUnresolved = 0
dets.each { d ->
    def cls = d.getPathClass()?.toString() ?: "Negative"
    if (cls == "Excluded") { nExcluded++; return }
    nClassified++
    def region = regionOf(d)
    if (region == null) { nUnresolved++; return }
    def counts = ownCounts.computeIfAbsent(region) { zeroCounts() }
    // Anchor total: every non-excluded classified nucleus in the leaf (D-13).
    counts[anchorName] = counts[anchorName] + 1
    // Per-marker positive count, INCLUDING Double+ (D-13 category definition:
    // a cell positive for this marker, whether it ended up "<marker>+" alone
    // or "Double+" with another marker).
    markers.each { marker ->
        if (cls == "${marker.name}+" || cls == "Double+") {
            counts[marker.name] = counts[marker.name] + 1
        }
    }
    if (emitDouble && cls == "Double+") {
        counts["Double+"] = counts["Double+"] + 1
    }
}
if (nUnresolved > 0) {
    println "WARNING: ${nUnresolved} classified, non-excluded detection(s) had no resolvable atlas region (regionOf returned null) -- excluded from the region table and the zero-leak sum below."
}

// Ancestor-walk rollup (D-10, NEW code -- no independent parent-ROI containment
// pass, do NOT copy 02_detect_classify.groovy's lines ~483-507, which predates
// CR-01). Initialize every candidate region annotation's rolled-up counts from
// its OWN bucket (zero if it received no direct cells), then walk each
// contributing annotation's already-resolved parent chain via ann.getParent()
// (resolveHierarchy() in 01_load_abba_rois.groovy makes this available) and ADD
// its own-bucket counts into every ancestor still within the candidate region
// set. This makes each parent row the exact SUM of its descendant-leaf counts.
def rolledCounts = [:]
regionAnnotations.each { ann -> rolledCounts[ann] = zeroCounts() }
ownCounts.each { ann, counts ->
    counts.each { cat, cnt -> rolledCounts[ann][cat] = rolledCounts[ann][cat] + cnt }
    def p = ann.getParent()
    while (p != null && regionAnnotationSet.contains(p)) {
        counts.each { cat, cnt -> rolledCounts[p][cat] = rolledCounts[p][cat] + cnt }
        p = p.getParent()
    }
}

// ── D-10 zero-leak assertion (fail-loud) ────────────────────────────────────
// The sum of ALL own-bucket anchor counts must equal the total non-excluded
// classified detections. Parent rows are summed FROM these same own-buckets
// (never independently re-counted via centroid-in-parent-ROI containment), so
// this single check proves no cell was silently lost or double-counted
// anywhere in the rollup.
int sumAnchorOwn = (ownCounts.values().collect { it[anchorName] }.sum()) ?: 0
if (sumAnchorOwn != nClassified) {
    println "ERROR: zero-leak FAILED -- summed leaf ${anchorName} counts (${sumAnchorOwn}) != total classified non-excluded detections (${nClassified})."
    println "       (${nUnresolved} unresolved detection(s) with no containing region account for part of any gap.)"
    throw new RuntimeException("D-10 zero-leak assertion failed: ${sumAnchorOwn} != ${nClassified}")
}
println "zero-leak PASS: summed leaf ${anchorName} counts = ${sumAnchorOwn} == total classified non-excluded detections = ${nClassified}"

// ── per-slice wide region table (D-11: density = count / area_mm2) ─────────
// One row per region annotation (leaves AND parent rollups); is_leaf is the
// GEOMETRIC isLeafOf flag regardless of whether a cell happened to resolve
// directly onto that annotation. Columns adapt to the declared marker set
// (D-04) -- absent-marker columns are never emitted because CATEGORIES is
// built purely from pipeline.yml's declared markers.
def regionRows = []
regionAnnotations.each { ann ->
    def roi = ann.getROI()
    def label = ann.getPathClass()?.toString() ?: ann.getName()
    def isLeaf = isLeafOf(ann)
    def hemisphere = ""; def acronym = label
    def mm = (label =~ /(?i)^(Left|Right):\s*(.+)$/)
    if (mm.find()) { hemisphere = mm.group(1); acronym = mm.group(2) }
    def areaMm2 = roi.getArea() * pxToMm2
    if (areaMm2 <= 0) return
    def counts = rolledCounts[ann] ?: zeroCounts()
    regionRows << [label: label, hemisphere: hemisphere, acronym: acronym, isLeaf: isLeaf, areaMm2: areaMm2, counts: counts]
}

def regionHeader = (["region_label", "hemisphere", "acronym", "is_leaf", "area_mm2"] +
        CATEGORIES.collectMany { cat -> ["${columnPrefixFor(cat)}_count", "${columnPrefixFor(cat)}_density"] }).join("\t")
def regionFile = new File(buildPathInProject("results", "${stem}__region_table.tsv"))
def regionSb = new StringBuilder()
regionSb.append(regionHeader).append("\n")
regionRows.each { row ->
    def cells = [row.label, row.hemisphere, row.acronym, row.isLeaf, String.format('%.6f', row.areaMm2)]
    CATEGORIES.each { cat ->
        int cnt = (row.counts[cat] ?: 0) as int
        double dens = row.areaMm2 > 0 ? (cnt / row.areaMm2) : Double.NaN
        cells << cnt
        cells << (Double.isNaN(dens) ? "" : String.format('%.3f', dens))
    }
    regionSb.append(cells.join("\t")).append("\n")
}
regionFile.text = regionSb.toString()
println "Wrote ${regionRows.size()} per-region rows -> ${regionFile} (categories: ${CATEGORIES})"

// ── D-12/D-13: config_tag (verbatim regex-grab idiom) + growing long/tidy combined CSV ──
// config_tag is derived from BraiAn.yml's detection params (NOT pipeline.yml -- D-14 keeps
// these concerns separate), so only like-config rows ever aggregate together downstream.
def braianYmlFile = new File(getProject().getBaseDirectory(), "BraiAn.yml")
def yml = braianYmlFile.exists() ? braianYmlFile.text : ""
def grab = { pat -> def mm = (yml =~ pat); mm.find() ? mm.group(1) : "NA" }
def sigma = grab(/sigmaMicrons:\s*([0-9.]+)/)
def minA  = grab(/minAreaMicrons:\s*([0-9.]+)/)
def maxA  = grab(/maxAreaMicrons:\s*([0-9.]+)/)
def nPeak = grab(/nPeak:\s*([0-9]+)/)
def prom  = grab(/peakProminence:\s*([0-9.]+)/)
def expn  = grab(/cellExpansionMicrons:\s*([0-9.]+)/)
def configTag = "sigma${sigma}_nPeak${nPeak}_prom${prom}_min${minA}_max${maxA}_exp${expn}"

// Reference dir = the QuPath project base's PARENT dir's "reference" subdir (same as
// export_region_dapi_reference.groovy) -- shared across all QuPath projects in this Analysis tree.
def refDir = new File(getProject().getBaseDirectory().getParentFile(), "reference")
refDir.mkdirs()
def combinedCsv = new File(refDir, "region_marker_combined.csv")
def combinedHeader = "slice,config_tag,region,hemisphere,is_leaf,marker,class,count,density"
if (!combinedCsv.exists()) combinedCsv.text = combinedHeader + "\n"   // idempotent header guard -- never rewrites the file

// One row per (region x declared-category), leaves AND parent rollups both. marker/class both
// derive from the SAME category value (D-13): anchor -> marker="<anchor>", class="<anchor>+";
// declared marker -> marker="<name>", class="<name>+"; Double+ -> marker=class="Double+". Absent
// markers produce NO rows here (D-04/D-13 -- CATEGORIES only ever contains declared markers).
def combinedSb = new StringBuilder()
int nAppended = 0
regionRows.each { row ->
    CATEGORIES.each { cat ->
        int cnt = (row.counts[cat] ?: 0) as int
        double dens = row.areaMm2 > 0 ? (cnt / row.areaMm2) : Double.NaN
        combinedSb.append(String.format('%s,%s,"%s","%s",%s,%s,%s,%d,%s%n',
            safeName, configTag, row.label, row.hemisphere, row.isLeaf,
            cat, classFor(cat), cnt, Double.isNaN(dens) ? "" : String.format('%.3f', dens)))
        nAppended++
    }
}
combinedCsv.append(combinedSb.toString())
println "Appended ${nAppended} rows to ${combinedCsv} (config_tag=${configTag}, slice=${safeName})"

println "Consolidated export complete: ${percellFile.name} (${percellRows.size()} cells), ${regionFile.name} (${regionRows.size()} regions), ${combinedCsv.name} (+${nAppended} rows)."
