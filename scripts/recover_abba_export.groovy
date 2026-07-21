/**
 * recover_abba_export.groovy  — FIJI (ABBA) script, run in Fiji's Script Editor (Language: Groovy)  [v2]
 *
 * Recover a Bio-Formats-imported ABBA registration into a QuPath project WITHOUT re-registering,
 * when "Export Registrations To QuPath Project" fails (slices not QuPath-linked). Per slice it writes
 * into the matching QuPath data/<N>/ folder:
 *   - ABBA-RoiSet-<atlas>.zip     via ABBA's own ExportSliceRegionsToFileAction (runs the real pipeline)
 *   - ABBA-Transform-<atlas>.json via bdv.util.RealTransformHelper.BigWarpFileFromRealTransform
 * ...and copies the atlas Ontology json to the project root.
 *
 * PREREQUISITE: ABBA open with your registration loaded (File > Load State on the .abba into an EMPTY
 * ABBA session so the 5 registered slices are present). Then run this in Fiji.
 * AFTER: in QuPath, run 01_load_abba_rois.groovy "for project".
 *
 * v2 fixes: correct RealTransformHelper class; export via the action pipeline (not the direct call);
 *           poll for the (async) RoiSet writes.
 */

#@ ObjectService os

import ch.epfl.biop.atlas.aligner.MultiSlicePositioner
import ch.epfl.biop.atlas.aligner.action.ExportSliceRegionsToFileAction
import bdv.util.RealTransformHelper

// ─────────── CONFIG ───────────
def ATLAS        = "allen_mouse_10um_java"
def NAMING       = "id"   // numeric-id ROI names (matches M3 export + the QuPath loader). If RoiSets
                          // stay empty, try "acronym" here and re-run.
def PROJECT_DIR  = "/home/jflab/Analysis/wBA 1-3 2-1 072026/wBA_1-3_2-1_072026"
def ONTOLOGY_SRC = "/home/jflab/Analysis/M3 Hippocampus 20x 062926 3 plane/allen_mouse_10um_java-Ontology.json"
def SLICE_TOKEN  = ~/wBA1-3_s\d+/
// ──────────────────────────────

def mps = os.getObjects(MultiSlicePositioner.class)
println "MultiSlicePositioner instances open: ${mps.size()}"
if (mps.isEmpty()) { println "ABORT: no ABBA session — open ABBA and Load State first."; return }
def mp = mps[0]
def slices = mp.getSlices()
println "Registered slices: ${slices.size()}"

// Map QuPath entry folders (data/<N>) by section token, from server.json text
def dataRoot = new File(PROJECT_DIR, "data")
def entryByToken = [:]
dataRoot.eachDir { d ->
    def sj = new File(d, "server.json")
    if (sj.exists()) { def m = SLICE_TOKEN.matcher(sj.text); if (m.find()) entryByToken[m.group()] = d }
}
println "QuPath entries: ${entryByToken.collectEntries { k, v -> [k, 'data/' + v.name] }}"

def expectedRoi = [:]   // token -> roiFile
slices.each { slice ->
    def m = SLICE_TOKEN.matcher(slice.getName())
    if (!m.find()) { println "SKIP: no token in slice '${slice.getName()}'"; return }
    def token = m.group()
    def dir = entryByToken[token]
    if (dir == null) { println "SKIP: no QuPath entry for '${token}'"; return }

    def roiFile = new File(dir, "ABBA-RoiSet-${ATLAS}.zip")
    def trFile  = new File(dir, "ABBA-Transform-${ATLAS}.json")

    // 1) RoiSet — through ABBA's action pipeline (async; polled below)
    if (roiFile.exists()) roiFile.delete()
    try {
        new ExportSliceRegionsToFileAction(mp, slice, NAMING, roiFile, true).runRequest()
        expectedRoi[token] = roiFile
    } catch (Throwable t) { println "${token}: RoiSet action ERROR ${t}"; t.printStackTrace() }

    // 2) Transform — synchronous
    try {
        def json = RealTransformHelper.BigWarpFileFromRealTransform(slice.getSlicePixToCCFRealTransform())
        trFile.text = json
        println "${token} -> data/${dir.name}   transform ${trFile.length()}B   head=${json.replaceAll('\\s+',' ').take(70)}"
    } catch (Throwable t) { println "${token}: transform ERROR ${t}" }
}

// Wait for async RoiSet writes (up to 120 s)
println "\nWaiting for RoiSet exports to finish..."
for (int i = 0; i < 120; i++) {
    if (!expectedRoi.isEmpty() && expectedRoi.values().every { it.exists() && it.length() > 0 }) break
    Thread.sleep(1000)
}
expectedRoi.each { tok, f -> println "  ${tok}: RoiSet ${f.exists() && f.length() > 0 ? f.length() + ' bytes' : '*** MISSING/EMPTY — try NAMING=\"acronym\" ***'}" }

// Ontology at project root
def ontDst = new File(PROJECT_DIR, "${ATLAS}-Ontology.json")
if (!ontDst.exists()) {
    def src = new File(ONTOLOGY_SRC)
    if (src.exists()) { ontDst.bytes = src.bytes; println "\nOntology copied -> ${ontDst.name}" }
    else println "\nWARN: ontology source missing at ${ONTOLOGY_SRC}"
} else println "\nOntology already present."

println "\nDONE. If RoiSets have real byte sizes, run 01_load_abba_rois.groovy in QuPath (Automate > Run for project)."
