# Phase 1: Atlas Registration and ROI Loading - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-01
**Phase:** 1-Atlas Registration and ROI Loading
**Areas discussed:** Target project and scope, clearAllObjects scope, QC image capture, Script location and project structure

---

## Target Project and Scope

| Option | Description | Selected |
|--------|-------------|----------|
| M3 Hippocampus 20x 062926 3 plane | Most recent project, correct channel names (AF568-T2 / AF488-T3 / DAPI-T4), 2 entries, no ABBA yet | ✓ |
| M3 Hippocampus 20x 062226 | Older project with ABBA done but wrong channel names | |
| New QuPath project | Start fresh with all M3 sections imported | |

**User's choice:** `M3 Hippocampus 20x 062926 3 plane` — confirmed as registration target

| Option | Description | Selected |
|--------|-------------|----------|
| Two processing versions of one section | One entry is Z1-3 MIP, other is re-MIP — duplicate | ✓ |
| Two separate sections | Different hippocampal slices at different AP positions | |
| Placeholder entries | Project needs new MIPs imported first | |

**User's choice:** "Likely a duplicate" — the two entries represent the same section processed twice

| Option | Description | Selected |
|--------|-------------|----------|
| Just 1 section for now | Single section validation run | ✓ |
| Multiple sections in project | All M3 slices already imported | |
| Multiple sections, project incomplete | Need to import all MIPs first | |

**User's choice:** 1 section for this validation run

| Option | Description | Selected |
|--------|-------------|----------|
| M3_20x_MIP_Z1-3.ome.tiff | 3-plane MIP, correct channel names, entry 1 | ✓ |
| M3_20x_MIP.ome.tiff | Older MIP from June 22 run, different channel names | |
| You decide | Use whichever entry is cleanest | |

**User's choice:** `M3_20x_MIP_Z1-3.ome.tiff` — canonical MIP for this run

---

## clearAllObjects Scope

| Option | Description | Selected |
|--------|-------------|----------|
| clearAllObjects() | Simple, full wipe before ROI load; acceptable pre-detection | ✓ |
| Clear annotations only | removeObjects(getAnnotationObjects(), true); safer for re-runs after detection | |
| Skip if annotations present | Only reload if no ABBA annotations exist yet | |

**User's choice:** `clearAllObjects()` — Phase 1 runs before detection; simplicity preferred

| Option | Description | Selected |
|--------|-------------|----------|
| Hardcode 'allen_mouse_10um_java' | Only one atlas in use; keeps script simple | |
| Configurable variable at top of script | def atlasName = 'allen_mouse_10um_java'; easy to edit | ✓ |
| You decide | Standard BIOP/BraiAn pattern | |

**User's choice:** Configurable variable at top of script

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — resolveHierarchy() after loading | Required for correct parent-child nesting | |
| No — BraiAnDetect handles internally | Skip resolveHierarchy() | |
| You decide | Follow BIOP reference pattern | ✓ |

**User's choice:** Claude decides — see Claude's Discretion below

---

## QC Image Capture

| Option | Description | Selected |
|--------|-------------|----------|
| Manual screenshot from QuPath viewer | Researcher takes snapshot via File → Export snapshot | ✓ |
| Scripted QuPath snapshot export | 01_load_abba_rois.groovy exports PNG automatically | |
| Fiji screenshot during ABBA registration | Capture overlay in Fiji before export | |

**User's choice:** Manual screenshot from QuPath viewer

| Option | Description | Selected |
|--------|-------------|----------|
| Hippocampal subfields visible — CA1, CA3, DG aligned | Primary biology check | |
| Any atlas region boundary visible | Minimal correctness check | |
| Full hippocampus + surrounding cortex | Broader error detection | |

**User's choice (free text):** "Hippocampal subfields visible, boundaries aligned, surrounding cortex visible, and bottom of the brain matches atlas, we need to be accurate here" — comprehensive requirement: CA1/CA3/DG + cortex + ventral brain edge all aligned

| Option | Description | Selected |
|--------|-------------|----------|
| In the QuPath project's data/ directory for that entry | Alongside ABBA transform and ROI files | ✓ |
| In a top-level QC/ folder in the Analysis directory | Central QC location | |
| You decide | Save wherever convenient | |

**User's choice:** Save in `data/1/` directory alongside ABBA transform files

---

## Script Location and Project Structure

| Option | Description | Selected |
|--------|-------------|----------|
| Inside the QuPath project's scripts/ folder | QuPath 'Run for project' reads from project scripts/ | |
| Central Analysis/scripts/ shared folder | One scripts/ dir for all QuPath projects | |
| Both — canonical in Analysis/scripts/, copies in project scripts/ | Central source + project copies | ✓ |

**User's choice:** Both — central canonical in `Analysis/scripts/`, hard copies in project `scripts/`

| Option | Description | Selected |
|--------|-------------|----------|
| /home/jflab/Analysis/scripts/ | Top-level of Analysis directory; alongside czi_mip.py | ✓ |
| /home/jflab/section-pipeline/scripts/ | Inside section-pipeline tools dir | |
| You decide | Most natural location given layout | |

**User's choice:** `/home/jflab/Analysis/scripts/`

| Option | Description | Selected |
|--------|-------------|----------|
| Hard copies in project scripts/ | Copy from Analysis/scripts/ into project | ✓ |
| Symlinks from project scripts/ to Analysis/scripts/ | Symlinks; one canonical file | |
| Absolute path in QuPath script editor | Skip 'Run for project'; open from Analysis/scripts/ directly | |

**User's choice:** Hard copies — simple, no symlink complexity

---

## Claude's Discretion

- **resolveHierarchy():** Include a `resolveHierarchy()` call after `loadWarpedAtlasAnnotations`. Standard BIOP/BraiAnDetect pattern; ensures parent-child region nesting is correct for BraiAnDetect cell-to-region assignment. User deferred to Claude.

## Deferred Ideas

- Multi-section batch registration — deferred until single-section validation is confirmed; belongs in full series run
- Cleanup of duplicate second entry (`M3_20x_MIP_Z1-3_MIP.ome.tiff`) in the project — not a Phase 1 task
