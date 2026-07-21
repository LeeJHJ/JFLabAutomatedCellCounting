/**
 * recover_abba_export.groovy  — FIJI (ABBA) script, run in Fiji's Script Editor (Language: Groovy)
 *
 * PURPOSE
 *   Recover a Bio-Formats-imported ABBA registration into a QuPath project WITHOUT re-registering,
 *   when "Export Registrations To QuPath Project" fails because the slices aren't QuPath-linked.
 *   For each registered slice it writes, straight into the QuPath entry folders, the two files the
 *   QuPath ABBA loader needs:
 *     - ABBA-RoiSet-<atlas>.zip   (warped atlas regions; via SliceSources.exportRegionsToFile — no
 *                                  QuPath link required; prepareExport is called internally)
 *     - ABBA-Transform-<atlas>.json (pix->CCF real-transform; via RealTransformHelper)
 *   ...and copies the atlas Ontology json to the project root.
 *
 * PREREQUISITE
 *   ABBA must be OPEN with your registration loaded (File > Load State on your saved .abba into an
 *   EMPTY ABBA session so the 5 registered slices are present). Then run this script in Fiji.
 *
 * After it finishes: in QuPath, run 01_load_abba_rois.groovy "for project".
 */

#@ ObjectService os

import ch.epfl.biop.atlas.aligner.MultiSlicePositioner
import ch.epfl.biop.atlas.aligner.SliceSources
import net.imglib2.realtransform.RealTransformHelper

// ─────────── CONFIG ───────────
def ATLAS        = "allen_mouse_10um_java"
def NAMING       = "id"   // M3 export used numeric-id ROI names (1026.roi, 260.roi ...) — matches loader
def PROJECT_DIR  = "/home/jflab/Analysis/wBA 1-3 2-1 072026/wBA_1-3_2-1_072026"
def ONTOLOGY_SRC = "/home/jflab/Analysis/M3 Hippocampus 20x 062926 3 plane/allen_mouse_10um_java-Ontology.json"
def SLICE_TOKEN  = ~/wBA1-3_s\d+/   // how slices map to QuPath entries (by section token)
// ──────────────────────────────

def mps = os.getObjects(MultiSlicePositioner.class)
println "MultiSlicePositioner instances open: ${mps.size()}"
if (mps.isEmpty()) { println "ABORT: no ABBA session found — open ABBA and Load State first."; return }
def mp = mps[0]
def slices = mp.getSlices()
println "Registered slices in ABBA: ${slices.size()}"
slices.eachWithIndex { s, i -> println "  slice[$i]: name='${s.getName()}'" }

// Map QuPath entry folders (data/<N>) by their section token, read from server.json text
def dataRoot = new File(PROJECT_DIR, "data")
def entryByToken = [:]
dataRoot.eachDir { d ->
    def sj = new File(d, "server.json")
    if (sj.exists()) {
        def m = SLICE_TOKEN.matcher(sj.text)
        if (m.find()) entryByToken[m.group()] = d
    }
}
println "QuPath entries by token: ${entryByToken.collectEntries { k, v -> [k, v.name] }}"

def okCount = 0
slices.each { slice ->
    try {
        def m = SLICE_TOKEN.matcher(slice.getName())
        if (!m.find()) { println "SKIP: no token in slice '${slice.getName()}'"; return }
        def token = m.group()
        def dir = entryByToken[token]
        if (dir == null) { println "SKIP: no QuPath entry for token '${token}'"; return }

        def roiFile = new File(dir, "ABBA-RoiSet-${ATLAS}.zip")
        def trFile  = new File(dir, "ABBA-Transform-${ATLAS}.json")
        println "\n${token}  ->  data/${dir.name}"

        // 1) RoiSet (prepareExport is called inside exportRegionsToFile)
        slice.exportRegionsToFile(NAMING, roiFile, true)
        println "   RoiSet:    ${roiFile.exists() ? roiFile.length() + ' bytes' : '*** NOT WRITTEN ***'}"

        // 2) Transform (pix -> CCF real transform)
        def tr = slice.getSlicePixToCCFRealTransform()
        def json = RealTransformHelper.BigWarpFileFromRealTransform(tr)
        trFile.text = json
        println "   Transform: ${trFile.length()} bytes"
        if (okCount == 0) println "   Transform head (verify format): " + json.take(140).replaceAll("\\s+", " ")

        okCount++
    } catch (Throwable t) {
        println "   ERROR on slice '${slice.getName()}': ${t}"
        t.printStackTrace()
    }
}

// Ontology at project root
def ontDst = new File(PROJECT_DIR, "${ATLAS}-Ontology.json")
if (!ontDst.exists()) {
    def src = new File(ONTOLOGY_SRC)
    if (src.exists()) { ontDst.bytes = src.bytes; println "\nOntology copied -> ${ontDst.name}" }
    else println "\nWARN: ontology source missing at ${ONTOLOGY_SRC} (copy allen_mouse_10um_java-Ontology.json to the project root manually)"
} else println "\nOntology already present: ${ontDst.name}"

println "\nDONE — ${okCount}/${slices.size()} slices exported."
println "Next: in QuPath, open the project and run scripts/01_load_abba_rois.groovy (Automate > Run for project)."
