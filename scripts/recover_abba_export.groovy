/**
 * recover_abba_export.groovy  — FIJI (ABBA) script, run in Fiji's Script Editor (Language: Groovy)  [v3]
 *
 * Recover a Bio-Formats-imported ABBA registration into a QuPath project WITHOUT re-registering.
 * Per slice, writes into the matching QuPath data/<N>/ folder:
 *   - ABBA-RoiSet-<atlas>.zip     via ABBA's ExportSliceRegionsToFileAction (async; polled below)
 *   - ABBA-Transform-<atlas>.json via ScijavaGsonHelper Gson (the exact writer for the M3 format)
 * ...and copies the atlas Ontology json to the project root.
 *
 * PREREQUISITE: ABBA open with your registration loaded (Load State on the .abba into an EMPTY session).
 * AFTER: in QuPath, run 01_load_abba_rois.groovy "for project".
 *
 * v3: transform serialized with ScijavaGsonHelper (bdv.util.RealTransformHelper.BigWarpFileFromRealTransform
 *     threw an internal NPE on this transform type); heartbeat while awaiting the async RoiSet writes.
 */

#@ ObjectService os
#@ Context ctx

import ch.epfl.biop.atlas.aligner.MultiSlicePositioner
import ch.epfl.biop.atlas.aligner.action.ExportSliceRegionsToFileAction
import net.imglib2.realtransform.RealTransform
import sc.fiji.persist.ScijavaGsonHelper

// ─────────── CONFIG ───────────
def ATLAS        = "allen_mouse_10um_java"
def NAMING       = "id"   // if RoiSets stay empty, change to "acronym" and re-run
def PROJECT_DIR  = "/home/jflab/Analysis/wBA 1-3 2-1 072026/wBA_1-3_2-1_072026"
def ONTOLOGY_SRC = "/home/jflab/Analysis/M3 Hippocampus 20x 062926 3 plane/allen_mouse_10um_java-Ontology.json"
def SLICE_TOKEN  = ~/wBA1-3_s\d+/
// ──────────────────────────────

def gson = ScijavaGsonHelper.getGson(ctx, true)

def mps = os.getObjects(MultiSlicePositioner.class)
println "MultiSlicePositioner instances open: ${mps.size()}"
if (mps.isEmpty()) { println "ABORT: open ABBA and Load State first."; return }
def mp = mps[0]
def slices = mp.getSlices()
println "Registered slices: ${slices.size()}"

def dataRoot = new File(PROJECT_DIR, "data")
def entryByToken = [:]
dataRoot.eachDir { d ->
    def sj = new File(d, "server.json")
    if (sj.exists()) { def m = SLICE_TOKEN.matcher(sj.text); if (m.find()) entryByToken[m.group()] = d }
}
println "QuPath entries: ${entryByToken.collectEntries { k, v -> [k, 'data/' + v.name] }}"

def expectedRoi = [:]
slices.each { slice ->
    def m = SLICE_TOKEN.matcher(slice.getName())
    if (!m.find()) { println "SKIP: no token in '${slice.getName()}'"; return }
    def token = m.group()
    def dir = entryByToken[token]
    if (dir == null) { println "SKIP: no entry for '${token}'"; return }

    def roiFile = new File(dir, "ABBA-RoiSet-${ATLAS}.zip")
    def trFile  = new File(dir, "ABBA-Transform-${ATLAS}.json")

    // 1) RoiSet — ABBA action pipeline (async)
    if (roiFile.exists()) roiFile.delete()
    try {
        new ExportSliceRegionsToFileAction(mp, slice, NAMING, roiFile, true).runRequest()
        expectedRoi[token] = roiFile
    } catch (Throwable t) { println "${token}: RoiSet action ERROR ${t}" }

    // 2) Transform — Gson (synchronous)
    try {
        def json = gson.toJson(slice.getSlicePixToCCFRealTransform(), RealTransform.class)
        trFile.text = json
        println "${token} -> data/${dir.name}   transform ${trFile.length()}B   head=${json.replaceAll('\\s+',' ').take(70)}"
    } catch (Throwable t) { println "${token}: transform ERROR ${t}" }
}

println "\nAwaiting async RoiSet exports (heartbeat every 5 s, up to ~120 s)..."
for (int i = 0; i < 24; i++) {
    def done = expectedRoi.values().count { it.exists() && it.length() > 0 }
    println "  [${i*5}s] RoiSets written: ${done}/${expectedRoi.size()}"
    if (!expectedRoi.isEmpty() && done == expectedRoi.size()) break
    Thread.sleep(5000)
}
println "\nFinal RoiSet status:"
expectedRoi.each { tok, f -> println "  ${tok}: ${f.exists() && f.length() > 0 ? f.length() + ' bytes' : '*** MISSING/EMPTY — try NAMING=\"acronym\" ***'}" }

def ontDst = new File(PROJECT_DIR, "${ATLAS}-Ontology.json")
if (!ontDst.exists()) {
    def src = new File(ONTOLOGY_SRC)
    if (src.exists()) { ontDst.bytes = src.bytes; println "\nOntology copied." } else println "\nWARN: ontology source missing."
} else println "\nOntology already present."

println "\nDONE. If RoiSets show real byte sizes, run 01_load_abba_rois.groovy in QuPath (Automate > Run for project)."
