/**
 * qc_handcount.groovy -- lay down small counting boxes so the machine count can be
 * checked against a human count, in QuPath, by eye.
 *
 * WHY THIS EXISTS
 *   Two <anatomical> QC gates have flagged on EVERY section ever run here: white
 *   matter denser than cortex (ratios 1.09-1.45, where it should be <= 0.6) and
 *   ventricles at 872-3,605 nuclei/mm^2 where CSF should be near-empty. Those are
 *   structural facts, not borrowed bands, so a violation is a real defect.
 *
 *   But nobody has ever counted by hand. Without that, "detection over-calls in white
 *   matter" is an inference from a ratio, and the obvious response -- raise the
 *   threshold -- may be wrong: the gate is WM/cortex, so a stricter cut that removes
 *   real cortical nuclei faster than it removes white-matter haze makes the ratio
 *   WORSE while improving the segmentation. Only counting settles it.
 *
 *   This script does the tedious half: it places a small box inside each named region,
 *   reports how many detections the machine put in each box, and leaves the boxes in
 *   the hierarchy for you to zoom into and count by eye.
 *
 * HOW TO USE
 *   1. Open the slice in QuPath. Run this from the Script editor.
 *   2. In the Annotations tab you now have one "handcount" box per region.
 *      Double-click one to zoom to it.
 *   3. Count nuclei by eye in the DAPI channel with the detection overlay OFF
 *      (View > Show detections), then turn it back ON and compare.
 *   4. Record both numbers. Two or three boxes per region is enough to tell a
 *      2x over-count from a 10% one, which is the distinction that matters.
 *
 * WHAT COUNTS AS A RESULT
 *   machine/human ~ 1.0        detection is sound; the gates' BANDS are what is wrong
 *   machine/human >> 1 in WM   real over-detection -- tune, and re-check cortex too
 *   machine/human >> 1 in VS   ventricle haze is being segmented; the cut is too low
 *                              OR the anchor channel has bleed-through there
 *
 * READ-ONLY with respect to detections: this adds annotations and touches no cell.
 * Delete them afterwards with Objects > Delete... or re-run with CLEAR_FIRST = true.
 *
 * @author section pipeline
 */

import qupath.lib.objects.PathObjects
import qupath.lib.roi.ROIs
import qupath.lib.roi.interfaces.ROI

// ── Settings ────────────────────────────────────────────────────────────────────
// Regions to sample. Defaults are the two that flag plus a cortical reference -- the
// comparison is the point, so always include a region you TRUST.
def REGIONS = ["cc", "VS", "Isocortex"]
// Preferred box side in microns, largest first. 150 um is a few dozen nuclei --
// countable by eye in under a minute. The list exists because the regions that MATTER
// most here are thin: corpus callosum and the ventricles are long and narrow, so a
// 150 um square does not fit inside them even though cc has >500,000 um^2 of area.
// The largest side that fits wins, and the density is computed from the side actually
// used, so a small box is still directly comparable to a large one.
def BOX_UM_LADDER = [150.0, 120.0, 100.0, 80.0, 60.0, 50.0, 40.0]
def BOXES_PER_REGION = 3
def CLEAR_FIRST = true    // remove handcount boxes from a previous run

def hierarchy = getCurrentHierarchy()
def server = getCurrentServer()
def cal = server.getPixelCalibration()
double umPerPx = cal.getAveragedPixelSizeMicrons()
if (!Double.isFinite(umPerPx) || umPerPx <= 0) {
    throw new RuntimeException(
        "no pixel calibration on this image -- box sizes would be meaningless. " +
        "Check the OME-XML PhysicalSizeX and BraiAn.yml requestedPixelSizeMicrons.")
}
println "pixel size ${String.format('%.6g', umPerPx)} um/px"

if (CLEAR_FIRST) {
    def old = getAnnotationObjects().findAll { it.getName()?.startsWith("handcount") }
    if (old) { removeObjects(old, true); println "removed ${old.size()} box(es) from a previous run" }
}

// Atlas annotations carry their acronym as the PathClass name (left/right split gives
// names like "Left: cc"), so match on the class name's trailing token rather than the
// annotation name -- that is what survives the hemisphere split.
def annotations = getAnnotationObjects()
def rng = new Random(42)     // fixed seed: the same boxes every run, so a re-count is
                             // comparable to the last one rather than a fresh sample
def rows = []

REGIONS.each { acronym ->
    def matches = annotations.findAll { ann ->
        def cls = ann.getPathClass()?.toString() ?: ""
        def nm = ann.getName() ?: ""
        cls.tokenize(":")*.trim().contains(acronym) || nm == acronym
    }
    if (matches.isEmpty()) {
        println "  ${acronym}: NOT PRESENT on this section -- skipped"
        return
    }
    // Largest match: the biggest instance of the region gives the most room for a box.
    def target = matches.max { it.getROI().getArea() }
    ROI roi = target.getROI()
    double areaUm2 = roi.getArea() * umPerPx * umPerPx

    // Largest side that actually fits. Thin structures fall through to a smaller box
    // rather than being skipped -- being skipped is what would lose the measurement
    // that matters, since cc and VS are precisely the flagged regions.
    int placed = 0
    for (double sideUm : BOX_UM_LADDER) {
        int boxPx = Math.round(sideUm / umPerPx)
        if (boxPx < 8) continue
        int attempts = 0
        while (placed < BOXES_PER_REGION && attempts < 3000) {
            attempts++
            double x = roi.getBoundsX() + rng.nextDouble() * Math.max(roi.getBoundsWidth() - boxPx, 1)
            double y = roi.getBoundsY() + rng.nextDouble() * Math.max(roi.getBoundsHeight() - boxPx, 1)
            // All four corners inside: a box straddling the boundary mixes populations
            // and makes the count uninterpretable.
            if (!(roi.contains(x, y) && roi.contains(x + boxPx, y) &&
                  roi.contains(x, y + boxPx) && roi.contains(x + boxPx, y + boxPx))) continue

            def box = ROIs.createRectangleROI(x, y, boxPx, boxPx, roi.getImagePlane())
            def ann = PathObjects.createAnnotationObject(box)
            ann.setName("handcount_${acronym}_${placed + 1}_${Math.round(sideUm)}um")
            addObject(ann)

            def inside = hierarchy.getDetectionObjects().findAll {
                box.contains(it.getROI().getCentroidX(), it.getROI().getCentroidY())
            }
            double boxMm2 = (sideUm * sideUm) / 1e6
            rows << [acronym, placed + 1, Math.round(sideUm), inside.size(),
                     Math.round(inside.size() / boxMm2)]
            placed++
        }
        if (placed >= BOXES_PER_REGION) break
    }
    if (placed == 0) {
        println "  ${acronym}: no box down to ${BOX_UM_LADDER[-1]} um fits inside it " +
                "(area ${Math.round(areaUm2)} um^2) -- too thin or too fragmented to sample"
    } else if (placed < BOXES_PER_REGION) {
        println "  ${acronym}: only ${placed}/${BOXES_PER_REGION} boxes placed"
    }
}

fireHierarchyUpdate()

println ""
println "=" * 72
println "MACHINE counts -- now count these boxes BY EYE and compare"
println "=" * 72
println String.format("  %-12s %-4s %8s %10s %14s %10s", "region", "box", "side", "machine", "per mm^2", "human")
rows.each { r ->
    println String.format("  %-12s %-4s %6d um %10d %14s %10s",
                          r[0], r[1], r[2], r[3], String.format("%,d", r[4]), "____")
}
println ""
println "  Box side varies per region (thin structures get a smaller one); the per-mm^2"
println "  column already accounts for it. Double-click a 'handcount_*' annotation"
println "  to zoom to it. Toggle detections (View > Show detections) to count clean."
println ""
println "  Write the human numbers next to these. What you are looking for is the RATIO,"
println "  not the absolute: is white matter over-counted relative to cortex, or is the"
println "  gate's 0.6x expectation simply wrong for this prep?"
println "=" * 72
