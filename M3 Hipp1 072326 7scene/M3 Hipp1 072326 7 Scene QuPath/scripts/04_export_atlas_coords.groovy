/**
 * 04_export_atlas_coords.groovy — per-cell CCFv3 atlas-µm coordinates + class export (for brainrender)
 *
 * SCOPE: runs AFTER 02_detect_classify.groovy has classified + been saved on the entry.
 * Emits results/<stem>__atlas_cells.tsv — one row per detection:
 *   class, atlas_x_um, atlas_y_um, atlas_z_um, region_label
 * Atlas coords via AtlasTools.getAtlasToPixelTransform(imageData).inverse() (Pattern 5, the
 * BIOP/ABBA-author idiom used in 02_detect_classify's SC3 sanity print). AtlasTools returns
 * millimetres, so ×1000 → microns (the units brainrender's allen_mouse atlas expects;
 * [[atlas-coords-mm-units]]). Deploy to <project>/scripts/, run via "Run for project".
 *
 * @author section-pipeline
 */
import qupath.ext.biop.abba.AtlasTools
import net.imglib2.RealPoint
import static qupath.lib.scripting.QP.*

def imageData = getCurrentImageData()
println "Running on: " + imageData.getServer().getMetadata().getName()

def t = null
try { t = AtlasTools.getAtlasToPixelTransform(imageData)?.inverse() }
catch (Exception e) { println "  atlas transform error (${e.class.simpleName}): ${e.message} — skipping entry"; return }
if (t == null) { println "  No ABBA registration transform on this entry — skipping."; return }

def FOS_KEY = "Nucleus: AF488-T3 mean (bg-sub)"
def TDT_KEY = "Cytoplasm: AF568-T2 mean (bg-sub)"

def dets = getDetectionObjects()
def sb = new StringBuilder("class\tatlas_x_um\tatlas_y_um\tatlas_z_um\tfos_bgsub\ttdt_bgsub\tregion_label\n")
def pt = new RealPoint(3)
int n = 0
for (d in dets) {
    def r = d.getROI()
    if (r == null) continue
    pt.setPosition([r.getCentroidX(), r.getCentroidY(), 0d] as double[])
    t.apply(pt, pt)
    def cls = d.getPathClass()?.toString() ?: "Negative"
    def m = d.getMeasurements()
    def fos = m.get(FOS_KEY); def tdt = m.get(TDT_KEY)
    def par = d.getParent()
    def reg = par?.getPathClass()?.toString() ?: (par?.getName() ?: "")
    sb.append(cls).append('\t')
      .append(pt.getDoublePosition(0) * 1000.0).append('\t')
      .append(pt.getDoublePosition(1) * 1000.0).append('\t')
      .append(pt.getDoublePosition(2) * 1000.0).append('\t')
      .append(fos == null ? '' : fos).append('\t')
      .append(tdt == null ? '' : tdt).append('\t')
      .append(reg).append('\n')
    n++
}

def invalid = (['<','>',':','"','/','\\','|','?','*'] as Set).collect { java.util.regex.Pattern.quote(it) }.join('|')
def stem = getProjectEntry().getImageName().replaceAll(invalid, '')
def f = new File(buildPathInProject("results", stem + "__atlas_cells.tsv"))
f.getParentFile().mkdirs()   // fresh project: results/ may not exist yet
f.text = sb.toString()
println "Wrote ${n} cells with atlas-µm coords -> ${f.name}"
