/**
 * run_braian_detection.groovy
 *
 * Runs BraiAnDetect (qupath-extension-braian v1.1.0) detection + classification on the
 * CURRENT image using the project's BraiAn.yml. Corrected copy of the extension's bundled
 * `compute_classify_overlap_export_exclude_detections.groovy`.
 *
 * WHY THIS COPY EXISTS (bug in the vendored example):
 *   The bundled script constructs `new ImageChannelTools(name, server)`. In v1.1.0 that
 *   (String, ImageServer) constructor leaves ImageChannelTools.imageData null, so the
 *   findNChannel() call inside the constructor throws:
 *     "Cannot invoke ImageData.getServerMetadata() because this.imageData is null" (line 40).
 *   Fix: pass `imageData` (the (String, ImageData) constructor) instead of `server`.
 *
 * USAGE (Plan 02-02 tuning loop):
 *   1. Open the M3 062926 3-plane project, double-click entry 1 (ABBA regions already loaded).
 *   2. Run this script (Automate > Script editor > Run).
 *   3. Run qc_detection_gates.groovy to read the D-05 gate metrics.
 *   4. To tune: edit BraiAn.yml, DELETE the previous DAPI-T4 detections
 *      (Objects > Delete > Delete all detections), then re-run this script.
 *
 * TOPOLOGY: single DAPI-T4 channelDetections entry with Fos + TdT classifiers nested under
 * it (nucleus-anchored, per CLAUDE.md). detectionsCheck.controlChannel is null, so the
 * OverlappingDetections step is skipped — Double+ arises from merged classifiers on the
 * same DAPI object set, not from geometric overlap.
 *
 * @author section-pipeline (corrected from Carlo Castoldi, AGPL-3.0-or-later)
 */
import qupath.ext.braian.AtlasManager
import qupath.ext.braian.OverlappingDetections
import qupath.ext.braian.ImageChannelTools
import qupath.ext.braian.ChannelDetections
import qupath.ext.braian.config.ProjectsConfig
import static qupath.lib.scripting.QP.*

var imageData = getCurrentImageData()
var hierarchy = imageData.getHierarchy()
var config = ProjectsConfig.read("BraiAn.yml")
var annotations = config.getAnnotationsForDetections(hierarchy)

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

// CLASSIFY CHANNEL DETECTIONS
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
}

println getCurrentImageName()+" : DONE!"
