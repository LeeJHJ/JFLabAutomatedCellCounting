# Codebase Structure

**Analysis Date:** 2026-06-30

## Directory Layout

```
/home/jflab/Analysis/                         # Project root — all analysis work
├── czi_mip.py                                # CZI mosaic → MIP OME-TIFF conversion script
├── CLAUDE.md                                 # Project memory / rules-of-the-road for Claude Code
├── SECTION_PIPELINE_SETUP (1).md             # Full install runbook (tools, conda envs, GUI steps)
├── Analysis.code-workspace                   # VS Code workspace file
│
├── Automated Cell Counting/                  # Intermediate / working image files
│   ├── M3 Hippocampus 20x 062026.czi        # Source CZI (mosaic, multi-scene)
│   ├── M3_20x_MIP.ome.tiff                  # MIP produced by czi_mip.py (full mosaic)
│   ├── M3_scene1_MIP.ome.tiff               # MIP for scene 1 only
│   ├── M3 Hippocampus - part 1 scene 1_s1.ome.tiff
│   ├── cohort 1 ant_ LP #1 whole.ome.tiff
│   └── cohort 1 ant_ LP #1 whole.ome_MIP_Z1_2.ome.tiff
│
├── Automated Cell Counting Test/             # QuPath project — development/test project
│   ├── project.qpproj                       # QuPath project manifest
│   ├── project.qpproj.backup                # Auto-backup of project manifest
│   ├── allen_mouse_10um_java-Ontology.json  # Allen CCFv3 ontology (region hierarchy)
│   ├── classifiers/
│   │   ├── classes.json                     # QuPath annotation class definitions
│   │   └── object_classifiers/
│   │       ├── TdT_classifier.json          # Threshold classifier: TdTomato+ (Cy3 mean > 4.0)
│   │       └── Fos_Classifier.json          # Threshold classifier: Fos+ (EGFP mean > 24.66)
│   ├── scripts/
│   │   ├── Test 062026.groovy               # Warpy object transfer script (v1)
│   │   └── Test 062026 1.groovy             # Warpy object transfer script (v2)
│   ├── data/
│   │   └── 1/                              # Entry 1 (one registered section)
│   │       ├── server.json                  # BioFormats URI + channel/pyramid metadata
│   │       ├── data.qpdata                  # Binary PathObject store (cells + annotations)
│   │       ├── summary.json                 # Per-region object counts snapshot
│   │       ├── thumbnail.jpg                # Section thumbnail
│   │       ├── ABBA-Transform-allen_mouse_10um_java.json   # Registration transform sequence
│   │       └── ABBA-RoiSet-allen_mouse_10um_java.zip       # Atlas region ROIs in image space
│   └── elastix_spline_backup/              # Archived elastix spline run (not used in prod)
│       ├── elastix.log
│       ├── TransformParameters.0.txt
│       └── IterationInfo.0.R*.txt
│
├── M3 Hippocampus 20x 062226/               # QuPath project — M3 mouse, 062226 session
│   ├── project.qpproj
│   ├── project.qpproj.backup
│   ├── M3 Hippocampus 20x 062226.ome.tiff  # Original ZEN export (full stack)
│   ├── M3 Hippocampus 20x 062226_MIP.ome.tiff
│   ├── M3_20x_MIP.ome.tiff                 # Working MIP (used for registration)
│   ├── M3_20x_MIP_Z1-3.ome.tiff            # MIP limited to Z-planes 1-3
│   ├── M3_20x_MIP_Z1-3_MIP.ome.tiff
│   ├── classifiers/
│   │   └── classes.json
│   ├── data/
│   │   └── 1/                              # Entry 1 — registered section
│   │       ├── server.json
│   │       ├── data.qpdata
│   │       ├── summary.json
│   │       ├── thumbnail.jpg
│   │       ├── ABBA-Transform-allen_mouse_10um_java.json
│   │       └── ABBA-RoiSet-allen_mouse_10um_java.zip
│   └── Old 20x/                            # Superseded MIP files
│       ├── M3_20x_MIP.ome.tiff
│       └── M3_20x_MIP_8bit.ome.tiff
│
├── M3 Hippocampus 20x 062926 3 plane/       # QuPath project — M3 mouse, 062926 session (3-plane)
│   ├── project.qpproj
│   ├── project.qpproj.backup
│   ├── classifiers/
│   │   └── classes.json
│   └── data/
│       └── 1/
│           └── metadata.json
│
├── cohort 1 ant_ LP #1 whole/               # QuPath project — cohort 1, whole-brain section
│   ├── project.qpproj
│   ├── project.qpproj.backup
│   ├── allen_mouse_10um_java-Ontology.json
│   ├── classifiers/
│   │   └── classes.json
│   └── data/
│       ├── metadata.json
│       └── 1/
│
├── presentation_screenshots/                 # Slides / presentation assets
│   ├── SCREENSHOT_INDEX.md                  # Index of required screenshots per slide
│   └── PRESENTATION_DISCUSSION_POINTS.md
│
└── .planning/                               # GSD planning artifacts (this directory)
    └── codebase/
        ├── ARCHITECTURE.md
        └── STRUCTURE.md
```

**Installed tools** (outside project root, under `$HOME/section-pipeline/`):
```
$HOME/section-pipeline/tools/
├── QuPath/              # QuPath v0.6.0 — cell detection & classification GUI
│   ├── bin/QuPath       # Launch executable
│   └── lib/app/QuPath.cfg   # JVM config (-Xmx32G set here)
├── Fiji.app/            # Fiji with PTBIOP update site — ABBA registration GUI
│   └── ImageJ-linux64   # Launch executable (symlink; actual binary is fiji-linux-x64)
└── elastix/             # elastix 5.2.0 — 2D registration engine used by ABBA
    ├── bin/elastix
    ├── bin/transformix
    └── lib/             # Shared libs; LD_LIBRARY_PATH must include this
```

**Conda environments** (`$HOME/miniforge3/envs/`):
```
braian/      # Python 3.11 — BraiAnalyse stats + JupyterLab + aicspylibczi (runs czi_mip.py)
brainrender/ # Python 3.11 — brainrender 3D atlas visualization
deepslice/   # Python 3.10 — DeepSlice local AP estimation (optional; online preferred)
```

## Directory Purposes

**Project root `/home/jflab/Analysis/`:**
- Purpose: All analysis artifacts for the section pipeline
- Contains: Python scripts, QuPath project directories, working image files, documentation

**`Automated Cell Counting/`:**
- Purpose: Staging area for intermediate image files (CZI inputs, MIP outputs before loading into a QuPath project)
- Contains: Raw `.czi` files and derived `.ome.tiff` MIPs
- Key files: `M3_20x_MIP.ome.tiff` (full-mosaic MIP used in test project)

**`<project-name>/` (QuPath project directories):**
- Purpose: Self-contained QuPath project — holds all state for one imaging session / cohort subset
- Contains: `project.qpproj`, `classifiers/`, `scripts/`, `data/`
- Key files: `project.qpproj` (manifest), `data/1/ABBA-Transform-*.json` (registration), `data/1/data.qpdata` (detections)

**`<project>/data/<entry>/`:**
- Purpose: Per-section state store for one QuPath image entry
- Contains: Image server config, binary PathObjects, registration transforms, atlas ROIs, detection summary
- Generated by: QuPath (server.json, data.qpdata, summary.json, thumbnail.jpg), ABBA/Fiji (ABBA-Transform-*.json, ABBA-RoiSet-*.zip)
- Committed: Yes (these are the primary analysis outputs)

**`<project>/classifiers/object_classifiers/`:**
- Purpose: Reusable threshold classifiers for TdTomato and Fos channel intensity
- Contains: `TdT_classifier.json`, `Fos_Classifier.json`
- Format: `SimpleClassifier` JSON — one measurement name, one threshold, two output classes

**`<project>/scripts/`:**
- Purpose: QuPath Groovy automation scripts
- Contains: Warpy object transfer scripts
- Key files: `Test 062026 1.groovy` (transfer PathObjects between registered images using Warpy)

**`<project>/elastix_spline_backup/`:**
- Purpose: Archived elastix output from a spline registration run (not used in production; kept for reference)
- Generated: Yes (by elastix)
- Committed: Yes (for reference)

**`presentation_screenshots/`:**
- Purpose: Slide assets for lab presentations; index of needed vs captured screenshots
- Contains: `SCREENSHOT_INDEX.md` (inventory of all required screenshots and their status)

## Key File Locations

**Entry Points:**
- `/home/jflab/Analysis/czi_mip.py`: CZI → MIP conversion (edit `F_IN`, `F_OUT`, `PIXEL_SIZE_UM` constants at top)
- `$HOME/section-pipeline/tools/QuPath/bin/QuPath`: Cell detection, classification, ABBA ROI import
- `$HOME/section-pipeline/tools/Fiji.app/ImageJ-linux64`: ABBA atlas registration

**Configuration:**
- `$HOME/section-pipeline/tools/QuPath/lib/app/QuPath.cfg`: JVM memory (`-Xmx32G`)
- `~/.bashrc`: `LD_LIBRARY_PATH` for elastix libs, conda init
- `CLAUDE.md`: Project rules, hard constraints, pipeline status

**Core Logic:**
- `/home/jflab/Analysis/czi_mip.py`: Only Python script; all other logic is in GUI tools
- `<project>/classifiers/object_classifiers/TdT_classifier.json`: TdTomato classification rule
- `<project>/classifiers/object_classifiers/Fos_Classifier.json`: Fos classification rule

**Key Data:**
- `<project>/data/<entry>/ABBA-Transform-allen_mouse_10um_java.json`: Registration transform
- `<project>/data/<entry>/ABBA-RoiSet-allen_mouse_10um_java.zip`: Atlas region ROIs
- `<project>/data/<entry>/summary.json`: Per-region detection counts
- `<project>/allen_mouse_10um_java-Ontology.json`: Allen CCFv3 region hierarchy

**Documentation:**
- `/home/jflab/Analysis/SECTION_PIPELINE_SETUP (1).md`: Full install + configuration runbook
- `/home/jflab/Analysis/CLAUDE.md`: Durable project rules and constraints
- `/home/jflab/Analysis/presentation_screenshots/SCREENSHOT_INDEX.md`: Slide asset checklist

## Naming Conventions

**Files:**
- MIP OME-TIFFs: `<AnimalID>_<magnification>_MIP[_suffix].ome.tiff` — e.g., `M3_20x_MIP.ome.tiff`
- QuPath projects: named by subject/session — e.g., `M3 Hippocampus 20x 062226/`
- ABBA outputs: `ABBA-Transform-<atlas-name>.json`, `ABBA-RoiSet-<atlas-name>.zip`
- Classifiers: `<MarkerName>_classifier.json` (PascalCase marker, underscore before `classifier`)
- Groovy scripts: `<description> <MMDDYY>[space<version>].groovy`

**Directories:**
- QuPath project dirs use human-readable names with spaces: `M3 Hippocampus 20x 062226/`
- QuPath data entries are numbered integers: `data/1/`
- Old / superseded files are moved to `Old <descriptor>/` subdirectory

## Where to Add New Code

**New Python analysis script (stats, visualization):**
- Place in: `/home/jflab/Analysis/` (alongside `czi_mip.py`)
- Run with: `conda run -n braian python3 /home/jflab/Analysis/<script>.py` or `conda run -n brainrender ...`
- If it reads/writes CZI or OME-TIFF: use `braian` env (has aicspylibczi, tifffile)
- If it renders 3D atlas: use `brainrender` env

**New QuPath project (new mouse / cohort):**
- Create as: `/home/jflab/Analysis/<AnimalID or cohort descriptor>/`
- Copy classifier JSONs from `Automated Cell Counting Test/classifiers/object_classifiers/` as starting point
- Copy `allen_mouse_10um_java-Ontology.json` from an existing project if needed

**New object classifier:**
- Place in: `<project>/classifiers/object_classifiers/<MarkerName>_classifier.json`
- Format: `SimpleClassifier` JSON with `ClassifyByMeasurementFunction` — see existing files

**New Groovy automation script:**
- Place in: `<project>/scripts/<description> <MMDDYY>.groovy`
- Run from: QuPath Script Editor (`Automate > Script editor`)

**New intermediate image files:**
- Place in: `/home/jflab/Analysis/Automated Cell Counting/` (staging)
- Or directly in the relevant QuPath project directory if project-specific

## Special Directories

**`<project>/data/`:**
- Purpose: QuPath-managed per-entry state (binary + JSON)
- Generated: Partially (QuPath writes data.qpdata, summary.json, thumbnail; human/ABBA writes transform files)
- Committed: Yes — these files are the primary analysis outputs

**`<project>/elastix_spline_backup/`:**
- Purpose: Reference copy of an elastix spline registration that was superseded (elastix degrades results without tissue mask)
- Generated: Yes (by elastix during ABBA registration)
- Committed: Yes (reference only)

**`.planning/`:**
- Purpose: GSD workflow artifacts — codebase maps, phase plans
- Generated: Yes (by GSD commands)
- Committed: Yes

---

*Structure analysis: 2026-06-30*
