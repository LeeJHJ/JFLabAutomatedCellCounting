# Phase 01: Atlas Registration and ROI Loading — Pattern Map

**Mapped:** 2026-07-01
**Files analyzed:** 2 (both new; no existing files modified)
**Analogs found:** 2 / 2 (role-match quality; exact analog does not exist — no ABBA ROI loading script exists in the codebase)

---

## File Classification

| New File | Role | Data Flow | Closest Analog | Match Quality |
|----------|------|-----------|----------------|---------------|
| `/home/jflab/Analysis/scripts/01_load_abba_rois.groovy` | utility / pipeline script | request-response (imperative: trigger API → receive annotations) | `Automated Cell Counting Test/scripts/Test 062026 1.groovy` (Warpy transfer script) | role-match (both are QuPath Groovy pipeline scripts; different API mechanism) |
| `M3 Hippocampus 20x 062926 3 plane/scripts/01_load_abba_rois.groovy` | deployment copy | identical | same as above | exact copy of canonical file |

**Note on analog quality:** No ABBA ROI loading script exists yet in `Analysis/` or any project `scripts/` directory. The closest analogs are the two Warpy transfer scripts (same role: QuPath Groovy automation) and `classify_cells.groovy` (same project, same channel/variable conventions). The complete verified API pattern comes from the RESEARCH.md Code Examples section, which was extracted directly from the bundled ABBA JAR example (`example_manipulate_atlas_annotations.groovy` inside `qupath-extension-abba-0.4.0.jar`).

---

## Pattern Assignments

### `/home/jflab/Analysis/scripts/01_load_abba_rois.groovy` (utility, request-response)

**Primary analog:** `Automated Cell Counting Test/scripts/Test 062026 1.groovy`
**Secondary analog:** `/home/jflab/section-pipeline/scripts/classify_cells.groovy`
**API source (verified):** `example_manipulate_atlas_annotations.groovy` bundled in `qupath-extension-abba-0.4.0.jar`

---

#### Imports pattern

Copy from `Automated Cell Counting Test/scripts/Test 062026 1.groovy` (line 60) — imports go at the **bottom** of the script, not the top. This is the QuPath Groovy convention on this project.

```groovy
// Imports at BOTTOM of script (QuPath convention; see Test 062026 1.groovy line 60)
import qupath.ext.biop.abba.AtlasTools
```

---

#### Header / Javadoc pattern

Copy structure from `Automated Cell Counting Test/scripts/Test 062026 1.groovy` (lines 1–18):

```groovy
/**
 * <One-line description of what this script does>
 *
 * REQUIREMENTS
 * ============
 * - <prerequisite 1>
 * - <prerequisite 2>
 *
 * USAGE
 * -----
 * <how to run>
 *
 * @author <researcher name>
 */
```

The `classify_cells.groovy` (lines 1–24) shows an extended variant with a THRESHOLDS section — use that model for scripts with tunable constants.

---

#### Configuration variable pattern

Copy from `/home/jflab/section-pipeline/scripts/classify_cells.groovy` (lines 26–33) — constants defined at the top of the script body with inline comments explaining units and decision rationale:

```groovy
// ── Configuration ──────────────────────────────────────────────────────────────
def atlasName = 'allen_mouse_10um_java'   // D-06: must match ABBA export atlas name
```

Use `def` (not typed declarations). Use `──` section dividers with a trailing row of dashes (pattern from `classify_cells.groovy` lines 31, 35, 45, 70).

---

#### Guard / pre-condition check pattern

No exact codebase analog — derived from RESEARCH.md Pitfall 1 (ABBA silent no-op when files absent). Apply the pattern from `Test 062026 1.groovy` lines 29–32 (warning on unexpected state + early return):

```groovy
// ── Guard: confirm ABBA files exist before loading ─────────────────────────────
def availableAtlases = qupath.ext.biop.abba.AtlasTools.getAvailableAtlasRegistration(
    getCurrentImageData()
)
if (availableAtlases.isEmpty()) {
    println "ERROR: No ABBA registration files found in data directory."
    println "       Run ABBA export from Fiji first (Plugins > Atlas > Multi Image To Atlas > Export)."
    return
}
println "Found ABBA registrations: ${availableAtlases}"
```

---

#### Core API pattern

**Source:** `example_manipulate_atlas_annotations.groovy` bundled in installed JAR (verified by RESEARCH.md). Four-argument form confirmed:

```groovy
// ── Clear existing objects ──────────────────────────────────────────────────────
// WARNING: clearAllObjects() removes ALL objects including cell detections.
// Safe to run in Phase 1 (no cells detected yet).
// If re-running after Phase 3 detection, either:
//   (a) comment out clearAllObjects() and use removeObjects(getAnnotationObjects(), false), OR
//   (b) re-run detection after re-running this script.
clearAllObjects()
println "Cleared all existing objects."

// ── Load atlas annotations ──────────────────────────────────────────────────────
// args: (ImageData, namingProperty, splitLeftRight, overwrite)
//   namingProperty "acronym" = short region codes (CA1, DG, etc.)
//   splitLeftRight = true splits each region into Left/Right child annotations
//   overwrite = true replaces previous ABBA annotations if atlas version matches
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
resolveHierarchy()
println "Hierarchy resolved."
```

**Do not** use the internal `(AtlasOntology, ImageData, String, Z, Z)` overload — only the 4-argument public form is safe for Groovy scripts (RESEARCH.md Anti-Patterns).

---

#### Entry confirmation print pattern

Copy from `Test 062026 1.groovy` (implicit: `println` for status). Add an explicit entry name print at script start to catch wrong-entry errors (RESEARCH.md Pitfall 5):

```groovy
println "Running on: " + getCurrentImageData().getServer().getMetadata().getName()
```

---

#### Summary / completion print pattern

Copy from `/home/jflab/section-pipeline/scripts/classify_cells.groovy` (lines 70–88) — structured summary block at end:

```groovy
// ── Summary ─────────────────────────────────────────────────────────────────────
def annotations = getAnnotationObjects()
println "Total annotations loaded: ${annotations.size()}"
println "Script complete. Check annotation list in QuPath viewer."
println "Next step: File > Save project, then take QC screenshot."
```

---

#### `fireHierarchyUpdate()` vs `resolveHierarchy()`

`Test 062026 1.groovy` (line 55) uses `fireHierarchyUpdate()` — this is a display refresh, not hierarchy resolution. For ABBA ROI loading, use `resolveHierarchy()` instead (establishes parent-child nesting). Call `fireHierarchyUpdate()` only if the UI does not update after `resolveHierarchy()`. Do not conflate the two.

---

## Shared Patterns

### Groovy variable declarations
**Source:** `Automated Cell Counting Test/scripts/Test 062026 1.groovy` (all lines) and `classify_cells.groovy` (all lines)
**Apply to:** All QuPath Groovy scripts in this project

```groovy
def variableName = value   // always 'def', never typed (String, int) at declaration
```

### println for output (not print, not System.out.println)
**Source:** `Test 062026 1.groovy` line 57; `classify_cells.groovy` lines 72–88
**Apply to:** All QuPath Groovy scripts

```groovy
println "Step complete."
println "  detail value: ${variable}"   // 2-space indent for sub-details
```

### Section divider style
**Source:** `classify_cells.groovy` lines 26, 31, 35, 45, 70
**Apply to:** All multi-section Groovy scripts

```groovy
// ── Section Name ───────────────────────────────────────────────────────────────
```

### Imports at bottom
**Source:** `Test 062026 1.groovy` line 60
**Apply to:** All QuPath Groovy scripts (QuPath convention)

Imports go at the **end** of the script file, after all executable code.

---

## No Analog Found

No files in this phase lack analogs entirely — the Warpy scripts provide structural/stylistic patterns and the verified JAR example provides the core API. However:

| Pattern Need | Reason No Codebase Analog |
|--------------|---------------------------|
| `AtlasTools.loadWarpedAtlasAnnotations` call | No ABBA ROI loading script exists in the repo yet; this is the first one |
| `AtlasTools.getAvailableAtlasRegistration` guard | No guard pattern for ABBA file presence exists in repo |

For these, use the RESEARCH.md Code Examples section (Complete `01_load_abba_rois.groovy` Skeleton) as the authoritative source — it was extracted from the installed production JAR, not invented.

---

## Metadata

**Analog search scope:** `/home/jflab/Analysis/` (all `.groovy` files), `/home/jflab/section-pipeline/scripts/`
**Files scanned:** 4 project Groovy files (`Test 062026.groovy`, `Test 062026 1.groovy`, `classify_cells.groovy`, `classify_cells_adaptive.groovy`)
**Pattern extraction date:** 2026-07-01
