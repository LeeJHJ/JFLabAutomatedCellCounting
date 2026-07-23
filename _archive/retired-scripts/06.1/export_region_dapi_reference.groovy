/**
 * RETIRED 2026-07-23 (Phase 06.1 Plan 04, D-07): superseded by
 * scripts/03_export_region_table.groovy, which folds in this script's
 * all-region loop + config_tag + growing-CSV append pattern (generalized from
 * DAPI-only to any N declared markers via pipeline.yml, D-13's long/tidy
 * schema) plus 03_export_val01_metrics.groovy's CR-01 leaf resolution and
 * per-cell export. Kept here for historical reference only — do not deploy or
 * run this file; no QuPath project scripts/ dir references it anymore (PIPE-02).
 *
 * export_region_dapi_reference.groovy
 *
 * Appends THIS image's per-region DAPI density to a central, growing internal
 * reference, so expected densities can be defined EMPIRICALLY from your own data
 * (SERIES-02 drift monitoring) instead of a literature seed.
 *
 * Run AFTER a BraiAnDetect detection pass on the current entry. Writes/appends to
 *     <Analysis>/reference/dapi_region_reference.csv        (the QuPath project's parent dir)
 * one row per atlas-region annotation. The detection config (sigma / threshold /
 * area limits / expansion) is auto-read from BraiAn.yml and stored as `config_tag`,
 * so only like-config rows are ever aggregated together.
 *
 * Aggregate + QC across accumulated images:
 *     conda run -n braian python scripts/build_dapi_reference.py
 *
 * NOTE: uses geometric containment (centroid-in-ROI), matching qc_detection_gates.groovy.
 * With ~450 regions x ~200k detections this can take a minute or two.
 *
 * @author section-pipeline
 */
import static qupath.lib.scripting.QP.*

def imageData = getCurrentImageData()
def server = imageData.getServer()
def cal = server.getPixelCalibration()
def pixelUm = (cal != null && cal.hasPixelSizeMicrons()) ? cal.getAveragedPixelSizeMicrons() : 0.6905355
def pxToMm2 = (pixelUm * 1e-3) ** 2

// --- detection config tag (auto-read from BraiAn.yml text; no YAML lib needed) ---
def yml = new File(getProject().getBaseDirectory(), "BraiAn.yml").text
def grab = { pat -> def m = (yml =~ pat); m.find() ? m.group(1) : "NA" }
def sigma = grab(/sigmaMicrons:\s*([0-9.]+)/)
def minA  = grab(/minAreaMicrons:\s*([0-9.]+)/)
def maxA  = grab(/maxAreaMicrons:\s*([0-9.]+)/)
def nPeak = grab(/nPeak:\s*([0-9]+)/)
def prom  = grab(/peakProminence:\s*([0-9.]+)/)
def expn  = grab(/cellExpansionMicrons:\s*([0-9.]+)/)
def configTag = "sigma${sigma}_nPeak${nPeak}_prom${prom}_min${minA}_max${maxA}_exp${expn}"

def entry = getProjectEntry()
def imageName = entry != null ? entry.getImageName() : server.getMetadata().getName()
def timestamp = new java.text.SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss").format(new Date())

def detections = getDetectionObjects()
if (detections.isEmpty()) { println "No detections — run BraiAnDetect first. Aborting."; return }

// precompute detection centroids once
int nDet = detections.size()
def cx = new double[nDet]; def cy = new double[nDet]
detections.eachWithIndex { d, i -> def r = d.getROI(); cx[i] = r.getCentroidX(); cy[i] = r.getCentroidY() }

def rows = []
getAnnotationObjects().each { ann ->
    def roi = ann.getROI()
    if (roi == null) return
    if (ann.getChildObjects().any { it.isDetection() }) return          // skip the detection container(s)
    def label = ann.getPathClass()?.toString() ?: ann.getName()
    if (label == null || label == "AllDetections") return
    def isLeaf = ann.getChildObjects().findAll { it.isAnnotation() }.isEmpty()
    def hemisphere = ""; def acronym = label
    def m = (label =~ /(?i)^(Left|Right):\s*(.+)$/)
    if (m.find()) { hemisphere = m.group(1); acronym = m.group(2) }
    def areaMm2 = roi.getArea() * pxToMm2
    if (areaMm2 <= 0) return
    int n = 0
    for (int i = 0; i < nDet; i++) if (roi.contains(cx[i], cy[i])) n++
    rows << [timestamp, configTag, imageName, label, hemisphere, acronym, isLeaf, areaMm2, n, n / areaMm2]
}

def refDir = new File(getProject().getBaseDirectory().getParentFile(), "reference")
refDir.mkdirs()
def csv = new File(refDir, "dapi_region_reference.csv")
def header = "timestamp,config_tag,image,region_label,hemisphere,acronym,is_leaf,area_mm2,n_dapi,density_per_mm2"
if (!csv.exists()) csv.text = header + "\n"
def sb = new StringBuilder()
rows.each { r ->
    sb.append(String.format('%s,%s,"%s","%s",%s,"%s",%s,%.6f,%d,%.3f%n',
        r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7], r[8], r[9]))
}
csv.append(sb.toString())
println "Appended ${rows.size()} region rows to ${csv}"
println "  config_tag = ${configTag}  |  image = ${imageName}"
