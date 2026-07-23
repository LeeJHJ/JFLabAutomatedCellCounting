# Phase 01: Atlas Registration and ROI Loading — Research

**Researched:** 2026-07-01
**Domain:** QuPath ABBA Extension (v0.4.0), Fiji ABBA Plugin (ImageToAtlasRegister v0.11.1), Groovy scripting
**Confidence:** HIGH for API (extracted from installed JAR bytecode); MEDIUM for GUI workflow (inferred from plugin class metadata)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Target QuPath project is `M3 Hippocampus 20x 062926 3 plane/`. Channel names confirmed: `AF568-T2`, `AF488-T3`, `DAPI-T4`.
- **D-02:** Canonical entry to register is **entry 1: `M3_20x_MIP_Z1-3.ome.tiff`**. Entry 2 is a duplicate and is ignored.
- **D-03:** Scope is one section for this validation run. Multi-section batch registration is deferred.
- **D-04:** The older `M3 Hippocampus 20x 062226/` project (old channel names) is NOT the target.
- **D-05:** Script calls `clearAllObjects()` before reloading atlas annotations. A comment must warn that re-running after Phase 3 detection wipes cell data.
- **D-06:** Atlas name variable at script top: `def atlasName = 'allen_mouse_10um_java'`.
- **D-07:** QC is a manual screenshot. No programmatic export.
- **D-08:** QC image must show CA1, CA3, DG subfields + surrounding cortex + ventral brain edge aligned to atlas outlines.
- **D-09:** Screenshot saved at `data/1/registration_QC.jpg` alongside ABBA files.
- **D-10:** Central canonical script location: `/home/jflab/Analysis/scripts/` (must be created).
- **D-11:** Scripts hard-copied into each QuPath project's `scripts/` for "Run for project" access.

### Claude's Discretion

- **resolveHierarchy():** Include after `loadWarpedAtlasAnnotations`. This is the standard BIOP/BraiAnDetect pattern. User deferred this to Claude.

### Deferred Ideas (OUT OF SCOPE)

- Multi-section batch registration (deferred until single-section validation confirmed)
- Duplicate second entry removal (no action in Phase 1)
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| REG-01 | M3 hippocampus sections registered in ABBA (Fiji GUI) — DeepSlice → manual angle → export; ABBA-Transform-*.json + ABBA-RoiSet-*.zip written per entry | GUI workflow documented; Fiji export command class confirmed |
| REG-02 | Registration overlay QC image produced — atlas region boundaries visually aligned to tissue before proceeding to detection | Manual screenshot workflow; QC criteria documented |
| SCRI-01 | `01_load_abba_rois.groovy` written and tested — calls `clearAllObjects()` then `loadWarpedAtlasAnnotations`; runs cleanly on M3 QuPath project via "Run for project" | Exact API verified from installed JAR; example script extracted from JAR |
</phase_requirements>

---

## Summary

Phase 1 has two distinct tracks: a GUI track (ABBA registration in Fiji) and a scripting track (Groovy script to load those registrations into QuPath). The GUI track is not automatable and must be handed to the researcher; the scripting track is fully scriptable and the API has been verified from the installed JAR.

The key API discovery is that `AtlasTools.loadWarpedAtlasAnnotations` in ABBA extension v0.4.0 takes **(ImageData, String namingProperty, boolean splitLeftRight, boolean overwrite)** — four arguments, with `ImageData` first and no `AtlasOntology` parameter in the public Groovy call form. This was extracted directly from the bundled example script inside the installed JAR at `/home/jflab/section-pipeline/tools/QuPath/extensions/catalogs/QuPath-BIOP catalog/QuPath ABBA extension/v0.4.0/main-jar/qupath-extension-abba-0.4.0.jar`.

The target project `M3 Hippocampus 20x 062926 3 plane/` is in a clean pre-registration state: entry 1 has no ABBA files in `data/1/`, no annotations in its hierarchy (only root object), and `scripts/` directory does not exist yet. The central `Analysis/scripts/` directory also does not exist. Both must be created as part of Phase 1.

**Primary recommendation:** Write `01_load_abba_rois.groovy` using the 4-argument form `AtlasTools.loadWarpedAtlasAnnotations(getCurrentImageData(), "acronym", true, true)` after `clearAllObjects()`, then call `resolveHierarchy()`. Copy to project `scripts/` directory and confirm via "Run for project". ABBA registration must be completed in Fiji first (GUI step).

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Atlas registration (DeepSlice + BigWarp) | Fiji GUI (interactive) | — | ABBA requires a human at the monitor; cannot be automated |
| Registration output files | Filesystem (`data/1/`) | QuPath project tree | ABBA export writes directly to project entry data directory |
| ROI loading into QuPath | Groovy script | QuPath ABBA extension | Script calls the extension API; extension reads from `data/1/` |
| Annotation hierarchy resolution | QuPath core (`getHierarchy()`) | — | Must be called after ROI load for parent-child nesting |
| QC image capture | Researcher (manual screenshot) | QuPath viewer | Non-automatable; researcher visually verifies alignment |
| Script distribution | Filesystem copy | — | Central `Analysis/scripts/` → QuPath project `scripts/` |

---

## Standard Stack

### Core (this phase)

| Component | Version | Purpose | Why Standard |
|-----------|---------|---------|--------------|
| QuPath ABBA Extension | v0.4.0 (installed) | `AtlasTools.loadWarpedAtlasAnnotations` API | The official BIOP QuPath extension for ABBA; installed via BIOP catalog |
| Fiji ABBA Plugin | ImageToAtlasRegister v0.11.1 | Atlas registration GUI; produces transform + ROI files | Official BIOP Fiji plugin; only way to generate ABBA-Transform and ABBA-RoiSet files |
| QuPath v0.6.0 | v0.6.0 (pinned) | Host for Groovy scripting, annotation storage | Pinned per CLAUDE.md constraint |
| Groovy (bundled) | QuPath built-in | Script language for `01_load_abba_rois.groovy` | QuPath's native scripting language; no extra install |

### Supporting

| Component | Purpose | When to Use |
|-----------|---------|-------------|
| Allen CCFv3 atlas (`allen_mouse_10um_java`) | Target atlas; generates region names | Standard for mouse brain; 10 µm resolution; ABBA bundled |
| `resolveHierarchy()` | Fixes parent-child nesting of atlas regions after loading | Always after `loadWarpedAtlasAnnotations`; required for correct BraiAnDetect region assignment |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `clearAllObjects()` | `removeObjects(getAnnotationObjects(), false)` | `clearAllObjects()` is simpler and guaranteed fresh; safe here since no cells exist yet |
| `"acronym"` naming property | `"name"` (full names) | Acronyms are shorter, match BraiAnalyse conventions; full names are more readable but longer |

**No package installation needed:** Both the QuPath ABBA extension and Fiji plugin are already installed.

---

## Package Legitimacy Audit

> Not applicable — no new packages are installed in this phase. The ABBA extension (v0.4.0) and Fiji plugin (v0.11.1) are already installed and operational on this machine.

**Packages removed due to [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

---

## Architecture Patterns

### System Architecture Diagram

```
 Fiji ABBA GUI (interactive)
 ┌─────────────────────────────────────┐
 │  Open QuPath project in ABBA        │
 │  Load M3_20x_MIP_Z1-3.ome.tiff     │
 │  DeepSlice AP estimate              │
 │  Manual DV/ML tilt review           │
 │  Export: "ABBA - Export             │
 │   Registrations To QuPath Project"  │
 └────────────────┬────────────────────┘
                  │ writes to project entry data dir
                  ▼
 QuPath project: M3 Hippocampus 20x 062926 3 plane/
 data/1/
 ├── ABBA-Transform-allen_mouse_10um_java.json  ← 8 transform chain
 └── ABBA-RoiSet-allen_mouse_10um_java.zip      ← 260 ROI files
                  │
                  │ (QuPath "Run for project" → 01_load_abba_rois.groovy)
                  ▼
 01_load_abba_rois.groovy
 ┌────────────────────────────────────────┐
 │  clearAllObjects()                     │  ← wipes existing objects
 │  AtlasTools.loadWarpedAtlasAnnotations │  ← reads ABBA files, creates annotations
 │    (getCurrentImageData(),             │
 │     "acronym", true, true)             │
 │  resolveHierarchy()                    │  ← fixes parent-child nesting
 └────────────────┬───────────────────────┘
                  │ saves to data/1/data.qpdata
                  ▼
 data/1/data.qpdata  (~5 MB, ~260 atlas annotations)
 data/1/summary.json (updated: nAnnotations ≈ 260)
                  │
                  │ (researcher screenshots QuPath viewer)
                  ▼
 data/1/registration_QC.jpg
```

### Recommended Project Structure

```
/home/jflab/Analysis/
├── scripts/                          ← CREATE THIS (central canonical location, D-10)
│   └── 01_load_abba_rois.groovy      ← authored here first
└── M3 Hippocampus 20x 062926 3 plane/
    ├── scripts/                      ← CREATE THIS (QuPath project scripts dir, D-11)
    │   └── 01_load_abba_rois.groovy  ← hard-copy from Analysis/scripts/
    └── data/
        └── 1/
            ├── ABBA-Transform-allen_mouse_10um_java.json  ← written by Fiji ABBA (REG-01)
            ├── ABBA-RoiSet-allen_mouse_10um_java.zip      ← written by Fiji ABBA (REG-01)
            ├── data.qpdata                                ← updated after script run
            ├── summary.json                               ← updated after script run
            └── registration_QC.jpg                        ← manual screenshot (REG-02, D-09)
```

### Pattern 1: AtlasTools ROI Loading (verified from bundled example)

**What:** Loads ABBA-registered atlas annotations into the currently open QuPath image entry.
**When to use:** After ABBA export has written `ABBA-Transform-*.json` and `ABBA-RoiSet-*.zip` into `data/<N>/`.

```groovy
// Source: example_manipulate_atlas_annotations.groovy from qupath-extension-abba-0.4.0.jar
// (bundled example from BIOP ABBA extension installed on this machine)

// 1. Clear existing objects
// WARNING: clearAllObjects() also removes cell detection objects (Phase 3 data).
// Safe to run here (Phase 1) because detection has not been performed yet.
// Do NOT re-run this script after Phase 3 without removing clearAllObjects() first.
clearAllObjects()

// 2. Load atlas annotations
// args: (ImageData, namingProperty, splitLeftRight, overwrite)
//   namingProperty: "acronym" (short codes) or "name" (full names)
//   splitLeftRight: true splits each region into Left/Right children
//   overwrite: true replaces any previously imported atlas annotations if atlas version matches
def atlasRoot = qupath.ext.biop.abba.AtlasTools.loadWarpedAtlasAnnotations(
    getCurrentImageData(),
    "acronym",
    true,
    true
)

// 3. Resolve hierarchy (parent-child nesting for BraiAnDetect region assignment)
resolveHierarchy()
```

**Import required:**
```groovy
import qupath.ext.biop.abba.AtlasTools
```

### Pattern 2: `clearAllObjects()` vs. `removeObjects(getAnnotationObjects(), false)`

**What:** `clearAllObjects()` removes ALL objects (annotations + detections). `removeObjects(getAnnotationObjects(), false)` removes only annotations and optionally keeps child objects.

**Decision (D-05):** Use `clearAllObjects()` in Phase 1. Detection has not run yet; the guard comment must make the risk explicit for Phase 3.

### Pattern 3: Fiji ABBA Export Sequence (GUI — hand to researcher)

Menu path confirmed from `ExportRegistrationToQuPathCommand.class` in `ImageToAtlasRegister-0.11.1.jar`:

```
Fiji (ABBA loaded) → Plugins > Atlas > Multi Image To Atlas > Export
→ "ABBA - Export Registrations To QuPath Project"
```

This command calls `ExportSliceRegionsToQuPathProjectAction.exportToQuPathProject()` for each selected slice, writing:
- `ABBA-Transform-{atlasName}.json` — 8-transform InvertibleRealTransformSequence
- `ABBA-RoiSet-{atlasName}.zip` — ImageJ ROI files (one per atlas region), ~260 files for mouse hippocampus section

### Anti-Patterns to Avoid

- **Calling `loadWarpedAtlasAnnotations` with AtlasOntology as first arg:** The internal method signature has `(AtlasOntology, ImageData, String, Z, Z)` in the constant pool, but the public Groovy API (and the bundled example) uses `(ImageData, namingProperty, splitLeftRight, overwrite)`. Do not construct an `AtlasOntology` object manually.
- **Omitting `resolveHierarchy()`:** Without it, atlas regions are flat — BraiAnDetect cannot assign cells to parent regions (e.g., "Hippocampal region > CA1"). Call it after every `loadWarpedAtlasAnnotations`.
- **Running script before ABBA export:** `loadWarpedAtlasAnnotations` reads `ABBA-Transform-*.json` and `ABBA-RoiSet-*.zip` from `data/1/`. If these files are absent, `getAvailableAtlasOntologyFiles()` returns empty and the load silently produces no annotations. Check for file presence before running.
- **Using Affine+Spline elastix registration:** Locked out-of-scope per CONTEXT.md D-decision. DeepSlice → manual angle → export only.
- **Putting scripts anywhere other than `<project>/scripts/`:** QuPath "Run for project" only finds scripts in the project's own `scripts/` directory.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Atlas-to-pixel coordinate transform | Custom affine math | `AtlasTools.getAtlasToPixelTransform()` | 8-step transform chain; manual math will be wrong |
| ROI warping from atlas space | Custom polygon warp | ABBA export + `loadWarpedAtlasAnnotations` | BigWarp ThinplateSpline + Affine chain handles it |
| Atlas region hierarchy | Custom parent-child linking | `resolveHierarchy()` | QuPath's built-in hierarchy resolution handles all edge cases |
| Atlas region name lookup | Custom JSON parser | `AtlasTools` built-in | ABBA reads `allen_mouse_10um_java-Ontology.json` automatically |

**Key insight:** Every aspect of coordinate warping and region hierarchy is handled by the ABBA extension. The script's job is to trigger the load, not to re-implement any transformation logic.

---

## Runtime State Inventory

> Not applicable — this is greenfield work for the target project. No prior state exists in `M3 Hippocampus 20x 062926 3 plane/data/1/` that needs migration.

**Confirmed empty state of target project (data/1/):**
- No ABBA files: ABBA-Transform-*.json — NOT PRESENT (registration not yet done)
- No ABBA files: ABBA-RoiSet-*.zip — NOT PRESENT
- Hierarchy: root object only (nObjects: 1, no annotations, no cells)
- data.qpdata: 2.9 KB (empty project data)
- scripts/ directory: DOES NOT EXIST

**Central scripts directory:** `/home/jflab/Analysis/scripts/` — DOES NOT EXIST; must be created in Phase 1.

**Reference project state (for comparison):**
- `Automated Cell Counting Test/data/1/` has ABBA files, 259 annotations, 5.4 MB data.qpdata after a complete ABBA load + cell detection run.
- `Automated Cell Counting Test/data/1/summary.json` shows `"Annotations": 259` as the post-load expected state for a single hippocampal section.

---

## Common Pitfalls

### Pitfall 1: ABBA Files Absent — Silent No-Op

**What goes wrong:** `loadWarpedAtlasAnnotations` is called but no annotations appear. No error is thrown.

**Why it happens:** `AtlasTools.getAvailableAtlasRegistration()` scans `data/1/` for `ABBA-Transform-*.json`. If the file is absent (ABBA export not yet done), it returns an empty list and the load is silently skipped.

**How to avoid:** Before running the Groovy script, verify that `data/1/ABBA-Transform-allen_mouse_10um_java.json` and `data/1/ABBA-RoiSet-allen_mouse_10um_java.zip` both exist. Add a guard check in the script.

**Warning signs:** `summary.json` still shows `nObjects: 1` after script runs; annotation list is empty in QuPath.

### Pitfall 2: Duplicate Annotation Loading

**What goes wrong:** Running the script twice without `clearAllObjects()` results in 2× the annotation count. Each `loadWarpedAtlasAnnotations` call adds a new set of atlas regions on top of the existing ones.

**Why it happens:** Without `clearAllObjects()`, old annotations persist and new ones are appended.

**How to avoid:** Always call `clearAllObjects()` as the first line of the script. The `overwrite: true` 4th argument to `loadWarpedAtlasAnnotations` handles atlas-version matching but does NOT replace existing annotations outright; `clearAllObjects()` is the reliable guard.

**Warning signs:** `summary.json` shows `"Annotations": 518` (2×260) after a second run.

### Pitfall 3: `resolveHierarchy()` Omitted — Flat Annotation List

**What goes wrong:** BraiAnDetect assigns cells to the most specific region (e.g., `CA1sp`) but cannot roll up counts to parent regions (e.g., `CA1`, `HPF`). BraiAnalyse region aggregation breaks.

**Why it happens:** Atlas annotations load as a flat list; parent-child relationships are not established until `resolveHierarchy()` is called.

**How to avoid:** Always call `resolveHierarchy()` immediately after `loadWarpedAtlasAnnotations`. Confirmed pattern from BIOP documentation and classify_cells.groovy example.

**Warning signs:** QuPath annotation list shows all regions at the same nesting level; parent region counts are zero in BraiAnalyse output.

### Pitfall 4: Atlas Name Mismatch Between ABBA Export and Script

**What goes wrong:** Script uses `'allen_mouse_10um'` but files on disk are `ABBA-Transform-allen_mouse_10um_java.json`. The atlas detection finds no matching files and loads nothing.

**Why it happens:** The exact atlas key depends on which atlas was selected in ABBA at registration time. This project uses `allen_mouse_10um_java` (confirmed in the reference ABBA transform files and CONTEXT.md D-06).

**How to avoid:** Set `def atlasName = 'allen_mouse_10um_java'` at the top of the script. Verify by listing `data/1/` after ABBA export.

**Warning signs:** No annotations after script run; `getAvailableAtlasOntologyFiles()` would return empty.

### Pitfall 5: Wrong Entry Open in QuPath When Running Script

**What goes wrong:** Script runs on entry 2 (`M3_20x_MIP_Z1-3_MIP.ome.tiff`) instead of entry 1.

**Why it happens:** "Run for project" runs on the currently active entry. If the researcher has entry 2 selected, `getCurrentImageData()` returns the wrong entry's data.

**How to avoid:** Add a print statement at script start: `println "Running on: " + getCurrentImageData().getServer().getMetadata().getName()`. Confirm entry 1 is active before running.

**Warning signs:** `data/2/` gets ABBA annotations instead of `data/1/`; entry 1 remains at `nObjects: 1`.

### Pitfall 6: `clearAllObjects()` Warning Not Understood by Future Researcher

**What goes wrong:** Script is re-run in Phase 3 or later after cells are detected, wiping all detected cells.

**Why it happens:** `clearAllObjects()` is unconditional; it removes both annotation objects AND cell detection objects.

**How to avoid:** Include a prominent comment block in the script:

```groovy
// ⚠️  WARNING: clearAllObjects() removes ALL objects including cell detections.
// Safe to run in Phase 1 (no cells yet).
// If re-running after Phase 3 detection, either:
//   (a) comment out clearAllObjects() and use removeObjects(getAnnotationObjects(), false) instead, OR
//   (b) re-run detection after re-running this script.
```

---

## Code Examples

### Complete `01_load_abba_rois.groovy` Skeleton

```groovy
/**
 * Load ABBA Atlas Annotations into Current QuPath Entry
 *
 * REQUIREMENTS
 * ============
 * - QuPath ABBA Extension installed (BIOP catalog, qupath-extension-abba-0.4.0)
 * - Image registered in Fiji ABBA (DeepSlice → manual angle → export)
 * - ABBA export done: ABBA-Transform-allen_mouse_10um_java.json and
 *   ABBA-RoiSet-allen_mouse_10um_java.zip must exist in data/<N>/
 *
 * USAGE
 * -----
 * Copy this script to <QuPath project>/scripts/ and run via
 * Automate → "Run for project" (or Script Editor → Run on the active entry).
 *
 * @author [researcher name]
 */

// ── Configuration ──────────────────────────────────────────────────────────────
def atlasName = 'allen_mouse_10um_java'   // D-06: must match ABBA export atlas name

// ── Guard: confirm ABBA files exist before loading ─────────────────────────────
def availableAtlases = qupath.ext.biop.abba.AtlasTools.getAvailableAtlasRegistration(
    getCurrentImageData()
)
if (availableAtlases.isEmpty()) {
    println "ERROR: No ABBA registration files found in data directory."
    println "       Run ABBA export from Fiji first."
    return
}
println "Found ABBA registrations: ${availableAtlases}"

// ── Clear existing objects ──────────────────────────────────────────────────────
// WARNING: clearAllObjects() removes ALL objects including cell detections.
// Safe to run in Phase 1 (no cells detected yet).
// If re-running after Phase 3 detection, comment out clearAllObjects() and use:
//   removeObjects(getAnnotationObjects(), false)
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

// ── Summary ─────────────────────────────────────────────────────────────────────
def annotations = getAnnotationObjects()
println "Total annotations loaded: ${annotations.size()}"
println "Script complete. Check annotation list in QuPath viewer."

import qupath.ext.biop.abba.AtlasTools
```

**Source:** API from `example_manipulate_atlas_annotations.groovy` bundled in `qupath-extension-abba-0.4.0.jar` (installed on this machine); guard pattern and comment conventions follow existing project scripts.

### Checking ABBA File Presence (shell verification before opening QuPath)

```bash
# Verify ABBA export files are present in target entry
ls -lh "/home/jflab/Analysis/M3 Hippocampus 20x 062926 3 plane/data/1/ABBA-"*
```

Expected after successful ABBA export:
```
ABBA-RoiSet-allen_mouse_10um_java.zip   ~1.3 MB (260 ROI files)
ABBA-Transform-allen_mouse_10um_java.json ~7 KB (8-transform chain)
```

### Verifying ROI Load Succeeded (shell)

```bash
# Check annotation count in summary.json after script run
python3 -c "
import json
with open('/home/jflab/Analysis/M3 Hippocampus 20x 062926 3 plane/data/1/summary.json') as f:
    d = json.load(f)
h = d['hierarchy']
print('Total objects:', h['nObjects'])
print('Annotations:', h['objectTypeCounts'].get('Annotations', 0))
print('Cells:', h['objectTypeCounts'].get('Cells', 0))
"
```

Expected after successful load: `Annotations: ~250–270` (exact count depends on section).

### Creating Required Directories (shell)

```bash
mkdir -p /home/jflab/Analysis/scripts
mkdir -p "/home/jflab/Analysis/M3 Hippocampus 20x 062926 3 plane/scripts"
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Elastix Affine+Spline in ABBA | DeepSlice + manual angle only | 2026-06-23 (confirmed on this project) | Elastix degrades without tissue mask; excluded permanently per locked decision |
| ABBA standalone script (`abba-python`, Method 3) | Fiji ABBA plugin (Method 2, PTBIOP update site) | — | Method 3 required non-Allen atlases; Method 2 is standard for Allen CCFv3 on Linux |

**Deprecated/outdated:**
- `abba-python` (Method 3): Not used on this project; requires BrainGlobe atlas infrastructure not needed here.
- Elastix spline without tissue mask: Known to degrade registration; excluded from this pipeline.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | "Run for project" in QuPath finds scripts only in `<project>/scripts/` directory | Architecture Patterns | If wrong, another directory works and copy step is unnecessary — low risk |
| A2 | ABBA export writes directly to the QuPath project's `data/<N>/` without user selecting a save path | Common Pitfalls / Architecture | If wrong, files land elsewhere and script cannot find them — medium risk; verify on first export |
| A3 | ~260 atlas annotations expected for a single hippocampal section | Code Examples | Actual count varies by section position; this is a reference from a different section (10x, different AP) |

---

## Open Questions (RESOLVED)

1. **Which entry number in `M3 Hippocampus 20x 062926 3 plane/` will receive the ABBA files?**
   - What we know: Decision D-02 says entry 1 (`M3_20x_MIP_Z1-3.ome.tiff`). ABBA in Fiji writes to the entry directory that corresponds to the loaded slice.
   - What's unclear: ABBA must be configured to point to the correct QuPath project. The researcher needs to open the `M3 Hippocampus 20x 062926 3 plane/` project in ABBA (not the older 062226 project). Confirm this is done before export.
   - Recommendation: Include explicit instructions in the plan to open `M3 Hippocampus 20x 062926 3 plane/project.qpproj` in ABBA.

2. **Does the ABBA project already have the M3 section loaded for registration?**
   - What we know: No ABBA session file was found for the `M3 Hippocampus 20x 062926 3 plane/` project. A fresh ABBA session is required.
   - What's unclear: Whether DeepSlice was run previously for this image in a different session.
   - Recommendation: Treat this as a fresh registration (no prior session to resume).

3. **Will the `summary.json` file update automatically after running the Groovy script?**
   - What we know: In the reference project (Automated Cell Counting Test), `summary.json` was updated after detection ran. QuPath may only write summary.json on explicit save.
   - What's unclear: Whether "Run for project" triggers an auto-save after script completion.
   - Recommendation: Have the researcher explicitly save the project (File > Save) after the script runs. Add this to the verification checklist.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| QuPath ABBA Extension | `loadWarpedAtlasAnnotations` API | ✓ | v0.4.0 (installed in BIOP catalog) | — |
| Fiji ABBA Plugin | Registration GUI | ✓ | ImageToAtlasRegister v0.11.1 (installed) | — |
| elastix | ABBA Spline (excluded) | ✓ | 5.2.0 | N/A — elastix excluded from this workflow |
| `Analysis/scripts/` directory | Canonical script storage | ✗ | — | Create with `mkdir -p` |
| `M3 Hippocampus 20x 062926 3 plane/scripts/` | QuPath "Run for project" | ✗ | — | Create with `mkdir -p` |
| ABBA-Transform-allen_mouse_10um_java.json | ROI loading script | ✗ | — | Must run Fiji ABBA export first (GUI, REG-01) |
| ABBA-RoiSet-allen_mouse_10um_java.zip | ROI loading script | ✗ | — | Must run Fiji ABBA export first (GUI, REG-01) |

**Missing dependencies that block script execution:**
- ABBA registration files in `data/1/` — blocked on REG-01 (GUI step)
- `Analysis/scripts/` directory — create in Wave 0
- `M3 Hippocampus 20x 062926 3 plane/scripts/` directory — create in Wave 0

**Missing dependencies with fallback:** none that are blocking.

---

## Validation Architecture

> `workflow.nyquist_validation: true` in `.planning/config.json` — section included.

### Test Framework

| Property | Value |
|----------|-------|
| Framework | Manual verification (no automated test framework; GUI + filesystem checks) |
| Config file | None |
| Quick run command | `python3 -c "import json; d=json.load(open('/home/jflab/Analysis/M3 Hippocampus 20x 062926 3 plane/data/1/summary.json')); print(d['hierarchy'])"` |
| Full suite command | Same as quick + visual QC in QuPath viewer |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| REG-01 | ABBA-Transform-*.json and ABBA-RoiSet-*.zip exist in data/1/ | smoke | `ls /home/jflab/Analysis/M3\ Hippocampus\ 20x\ 062926\ 3\ plane/data/1/ABBA-*.{json,zip} 2>/dev/null && echo OK` | ✗ (depends on GUI step) |
| REG-02 | Registration overlay QC image exists with correct anatomy | manual | Researcher screenshots QuPath viewer showing CA1/CA3/DG alignment | ✗ (manual-only) |
| SCRI-01 | Script runs without errors; annotations populate entry 1 | smoke | `python3 -c "import json; d=json.load(open('/home/jflab/Analysis/M3 Hippocampus 20x 062926 3 plane/data/1/summary.json')); assert d['hierarchy']['objectTypeCounts'].get('Annotations',0) > 50, 'No annotations loaded'; print('PASS:', d['hierarchy'])"` | ✗ Wave 0 |
| SCRI-01 (idempotency) | Re-run does not duplicate annotations | smoke | Run check command twice; count must not double | ✗ Wave 0 |

### Sampling Rate

- **Per task:** `ls /home/jflab/Analysis/M3\ Hippocampus\ 20x\ 062926\ 3\ plane/data/1/ABBA-*.json 2>/dev/null && echo ABBA files present`
- **Per wave merge:** Annotation count check via `summary.json` Python one-liner above
- **Phase gate:** REG-01 (files present) + REG-02 (visual QC passed) + SCRI-01 (>50 annotations loaded, idempotency confirmed) before proceeding to Phase 2

### Wave 0 Gaps

- [ ] `Analysis/scripts/` directory — create with `mkdir -p /home/jflab/Analysis/scripts`
- [ ] `M3 Hippocampus 20x 062926 3 plane/scripts/` directory — create with `mkdir -p`
- [ ] `01_load_abba_rois.groovy` — author in `Analysis/scripts/`, copy to project `scripts/`
- [ ] REG-01 gate is blocked on the GUI step (ABBA registration in Fiji); all script tasks depend on it

---

## Security Domain

> `security_enforcement: true`, `security_asvs_level: 1` per config. Applicable categories assessed.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | No user authentication in local desktop pipeline |
| V3 Session Management | No | No sessions; stateless GUI + script execution |
| V4 Access Control | No | Local single-user machine; no multi-user access |
| V5 Input Validation | Partial | Atlas name variable is hardcoded in script (no user input); ABBA file paths come from QuPath project structure only |
| V6 Cryptography | No | No encryption or secrets involved |

### Known Threat Patterns for QuPath + Groovy Scripts

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Groovy script executing arbitrary code | Tampering | Scripts are authored by researcher; no external input to script content |
| Atlas file path traversal | Tampering | Paths are derived from QuPath project structure, not user input |
| Accidental data loss from `clearAllObjects()` | Spoofing/DoS | Prominent comment warning; Phase 3 will use `removeObjects(getAnnotationObjects(), false)` instead |

**Risk profile:** Very low. This is a local, single-user, offline scientific pipeline. Security concerns are limited to accidental data loss from script execution.

---

## Sources

### Primary (HIGH confidence)

- `qupath-extension-abba-0.4.0.jar` (installed at `/home/jflab/section-pipeline/tools/QuPath/extensions/catalogs/QuPath-BIOP catalog/QuPath ABBA extension/v0.4.0/main-jar/`) — exact method signatures extracted via bytecode inspection; bundled example scripts confirm public API

### Secondary (MEDIUM confidence)

- `ImageToAtlasRegister-0.11.1.jar` (installed at `/home/jflab/section-pipeline/tools/Fiji.app/jars/`) — Fiji ABBA export menu path and command class confirmed
- `Automated Cell Counting Test/data/1/` — reference post-registration state (260 ROI files, 259 annotations, 5.4 MB data.qpdata)
- `example_manipulate_atlas_annotations.groovy` and `Compute_cell_centroid_atlas_coordinates.groovy` — bundled inside ABBA JAR; verified as BIOP official examples

### Tertiary (LOW confidence)

- `classify_cells.groovy` in `section-pipeline/scripts/` — confirms channel name conventions and Groovy style; not ABBA-specific

---

## Metadata

**Confidence breakdown:**
- ABBA Groovy API (`loadWarpedAtlasAnnotations` signature): HIGH — extracted directly from installed JAR bytecode + confirmed in bundled example script
- Fiji ABBA export menu path: MEDIUM — extracted from command class bytecode; not directly observed running
- Expected annotation count (~260): MEDIUM — observed in reference project at different section position and magnification
- `resolveHierarchy()` requirement: HIGH — confirmed by CONTEXT.md decision, `classify_cells.groovy` pattern, and absence of hierarchy call causing flat annotation problems (documented BIOP pattern)
- Script directory convention (`<project>/scripts/`): MEDIUM — inferred from reference project structure; QuPath documentation not directly consulted [ASSUMED]

**Research date:** 2026-07-01
**Valid until:** 2026-09-01 (ABBA extension versions are stable; QuPath v0.6.0 is pinned)
