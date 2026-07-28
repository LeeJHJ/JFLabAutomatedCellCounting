/**
 * Load ABBA Atlas Annotations into Current QuPath Entry
 *
 * REQUIREMENTS
 * ============
 * - QuPath ABBA Extension installed (BIOP catalog, qupath-extension-abba-0.4.0)
 * - Image registered in Fiji ABBA (DeepSlice -> manual angle -> export)
 * - ABBA export done: ABBA-Transform-allen_mouse_10um_java.json and
 *   ABBA-RoiSet-allen_mouse_10um_java.zip must exist in data/<N>/
 *
 * USAGE
 * -----
 * Copy this script to <QuPath project>/scripts/ and run via
 * Automate -> "Run for project" (or Script Editor -> Run on the active entry).
 *
 * @author [researcher name]
 */

// ── Configuration ──────────────────────────────────────────────────────────────
def atlasName = 'allen_mouse_10um_java'   // D-06: must match ABBA export atlas name

// ── Entry confirmation ─────────────────────────────────────────────────────────
// Print entry name to catch wrong-entry errors (Pitfall 5: script runs on entry 2
// instead of the canonical entry 1 if the wrong entry is active in QuPath).
println "Running on: " + getCurrentImageData().getServer().getMetadata().getName()

// ── Guard: confirm ABBA files exist before loading ─────────────────────────────
// AtlasTools.getAvailableAtlasRegistration() scans data/<N>/ for ABBA-Transform-*.json.
// If no registration files are found (ABBA export not yet run in Fiji), the load
// would silently produce no annotations. This guard catches that case early.
def availableAtlases = qupath.ext.biop.abba.AtlasTools.getAvailableAtlasRegistration(
    getCurrentImageData()
)
if (availableAtlases.isEmpty()) {
    println "ERROR: No ABBA registration files found in data directory."
    println "       Run ABBA export from Fiji first:"
    println "       Plugins > Atlas > Multi Image To Atlas > Export"
    println "       -> 'ABBA - Export Registrations To QuPath Project'"
    return
}
println "Found ABBA registrations: ${availableAtlases}"

// ── Clear existing objects ──────────────────────────────────────────────────────
// WARNING: clearAllObjects() removes ALL objects including cell detections.
// This is safe to run in Phase 1 because detection has not been performed yet.
//
// If re-running after Phase 3 detection, cell data will be lost. Two remedies:
//   (a) Comment out clearAllObjects() below and use instead:
//         removeObjects(getAnnotationObjects(), false)
//   (b) Re-run the full detection pipeline after re-running this script to
//       rebuild cell detections from scratch.
//
// The overwrite=true argument to loadWarpedAtlasAnnotations (below) replaces
// matching atlas annotations but does NOT remove unrelated objects; clearAllObjects()
// is required to guarantee a clean state before each reload.
clearAllObjects()
println "Cleared all existing objects."

// ── Load atlas annotations ──────────────────────────────────────────────────────
// Four-argument public form (verified from installed JAR: qupath-extension-abba-0.4.0):
//   args: (ImageData, namingProperty, splitLeftRight, overwrite)
//     namingProperty "acronym" = short region codes (CA1, DG, etc.)
//       "name" would give full names (e.g., "Field CA1") -- longer, less compact
//     splitLeftRight = true splits each region into Left/Right child annotations
//     overwrite = true replaces previously imported ABBA annotations if atlas version matches
// Do NOT use the internal (AtlasOntology, ImageData, String, Z, Z) overload --
// that is an internal method not meant for Groovy scripts (RESEARCH Anti-Patterns).
def atlasRoot = qupath.ext.biop.abba.AtlasTools.loadWarpedAtlasAnnotations(
    getCurrentImageData(),
    "acronym",
    true,
    true
)
println "Loaded atlas annotations. Root: ${atlasRoot}"

// ── Resolve annotation hierarchy ────────────────────────────────────────────────
// Required: establishes parent-child nesting so BraiAnDetect can assign cells
// to both leaf regions (e.g., CA1sp) and parent regions (CA1, HPF).
// Without this call, atlas regions are loaded as a flat list and BraiAnDetect
// cannot roll up counts to parent regions; BraiAnalyse aggregation breaks.
resolveHierarchy()
println "Hierarchy resolved."

// ── Summary ─────────────────────────────────────────────────────────────────────
def annotations = getAnnotationObjects()
println "Total annotations loaded: ${annotations.size()}"
println "Script complete. Check annotation list in QuPath viewer."
println "Next step: File > Save project, then take QC screenshot."

import qupath.ext.biop.abba.AtlasTools
