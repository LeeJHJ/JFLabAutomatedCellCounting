# Section Pipeline (TRAP2 / Airyscan) — Linux Setup Runbook

**For:** Claude Code, executing on the dedicated section-analysis **desktop** (Ubuntu, has a monitor, *not* the ClearMap machine "engram").
**Goal:** Install and configure the QuPath + ABBA(Fiji) + elastix + DeepSlice + BraiAn + brainrender pipeline that turns ZEN-exported OME-TIFFs of TRAP2 vibratome sections into an Allen-CCFv3-registered whole-brain map of TdTomato+ (encoding), Fos+ (recall), and double+ (reactivated) cell densities.

> **You are the agent.** Do the scriptable steps yourself (downloads, extraction, conda envs, pip installs, verification). The GUI-only steps in **Section 6** require a human at the monitor — surface them clearly and stop there for those.

---

## 0. Pre-flight: gather system specs and adapt

Run this first and use the output to set values later (QuPath max memory, GPU acceleration, OpenGL check):

```bash
echo "===== OS / KERNEL ====="; (lsb_release -ds 2>/dev/null || grep PRETTY_NAME /etc/os-release); uname -srm
echo "===== GLIBC =====";       ldd --version | head -1
echo "===== CPU =====";         lscpu | grep -E "^(Model name|Architecture|CPU\(s\)|Thread|Core)"
echo "===== RAM =====";         free -h | grep -E "Mem|Swap"
echo "===== DISK =====";        df -h "$HOME" /
echo "===== GPU (hw) =====";    lspci | grep -Ei "vga|3d|display"
echo "===== NVIDIA/CUDA ====="; nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv 2>/dev/null || echo "no NVIDIA driver"
echo "===== OpenGL/GLX =====";  glxinfo 2>/dev/null | grep -E "OpenGL renderer|OpenGL version|direct rendering" || echo "install mesa-utils"
echo "===== conda/mamba ====="; conda --version 2>/dev/null; mamba --version 2>/dev/null
```

**RESOLVED PROFILE FOR THIS MACHINE** (Ubuntu 26.04 LTS, kernel 7.0.0, glibc 2.43):

| Spec | Value | Consequence for setup |
|---|---|---|
| CPU | Intel i9-9900K, 8C/16T, x86_64 | use the x86_64 URLs; detection is CPU-bound but fine for scouting |
| RAM | 61 GB (58 free) | **QuPath `-Xmx32G`** |
| Disk | 915 GB NVMe, 854 GB free, single `/` partition | ample headroom |
| GPU | **Intel UHD 630 integrated — NO NVIDIA/CUDA** | **all detection + DeepSlice = CPU-only**; prefer DeepSlice *online* + BraiAnDetect built-in detection over Cellpose |
| Display | `DISPLAY=:0` (real X session, monitor attached) | interactive QuPath/Fiji/brainrender all work; no xvfb needed |
| conda | **not installed** | install Miniforge in Section 4 |
| java | not installed | fine — QuPath & Fiji bundle their own JREs |

**One check to run before brainrender** (verify hardware OpenGL, not software `llvmpipe`):
```bash
sudo apt-get install -y mesa-utils && glxinfo | grep -E "OpenGL renderer|direct rendering"
```
Expect `Mesa Intel(R) UHD Graphics 630` + `direct rendering: Yes`. If it says `llvmpipe`, fix the Intel/Mesa driver before relying on smooth interactive 3D (point clouds still render under llvmpipe, just slowly).

**Set QuPath memory to 32 GB** after install — *Edit > Preferences > set maximum memory*, or edit `…/tools/QuPath/lib/app/QuPath.cfg` (`-Xmx32G`).

**26.04 note:** brand-new release; conda envs below pin Python 3.11 independent of the system Python, and the only externally-compiled binary (elastix) runs under forward-compatible glibc 2.43 (use the `LD_LIBRARY_PATH` fallback in §5 if its bundled libs need pointing to).

---

## 1. What does NOT get installed here

Pipeline **Step 1 (ZEN — Airyscan processing, tile stitching, z-projection, OME-TIFF export)** is Zeiss-proprietary and runs on the **Windows microscope acquisition PC**. This desktop only **ingests the exported OME-TIFFs**. Do not attempt to install ZEN.

---

## 2. Architecture / components to install

| Stage | Tool | Role | Install type |
|---|---|---|---|
| 2 | **QuPath** | DAPI nuclear segmentation; TdT+/Fos+/double+ classification; import ABBA atlas regions | binary (tar.xz) |
| 3 | **Fiji + ABBA** (PTBIOP update site) | register sections to Allen CCFv3 (DeepSlice → affine/spline → BigWarp) | binary + update site |
| 3 | **elastix 5.2.0** | 2D in-plane affine/spline engine ABBA calls under the hood | binary |
| 3 | **DeepSlice** | initial Z/angle estimate (online by default; local optional) | conda env *(optional)* |
| 4 | **BraiAn** = BraiAnDetect (QuPath ext) + BraiAnalyse (`braian` py) | consistent multichannel detection + whole-brain region stats | catalog + conda env |
| 5 | **brainrender** | 3D point cloud of classified cells in Allen reference space | conda env |

---

## 3. Key decisions already made (do not deviate without flagging)

- **ABBA install = Method 2** (standalone Fiji + `PTBIOP` update site). The Windows one-click installer does **not** exist for Linux. Method 2 covers everything needed: the **Allen mouse CCFv3 is a built-in default atlas**, plus DeepSlice, elastix, BigWarp. (Method 3 = `abba-python` is only needed if other BrainGlobe atlases are ever required — not the case for a TRAP2 mouse.)
- **QuPath pinned to `v0.6.0`** — the ABBA and BraiAn QuPath extensions are documented/tested against 0.6.x via the BIOP catalog. QuPath 0.7.0 exists (Apr 2026) but verify catalog-extension compatibility before bumping.
- **elastix pinned to `5.2.0`** — ABBA requires exactly this version.
- **Separate conda envs** (`deepslice`, `braian`, `brainrender`) — keep them isolated; brainrender is finicky with vedo/VTK/allensdk.
- **This is a separate machine from the ClearMap box**, so no ClearMap2 env to avoid — but still keep these envs self-contained.

---

## 4. Install root

```bash
export SECTION_PIPELINE_ROOT="$HOME/section-pipeline"
mkdir -p "$SECTION_PIPELINE_ROOT/tools"
```

If `conda`/`mamba` is missing, install Miniforge first:
```bash
wget -O /tmp/mf.sh https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-x86_64.sh
bash /tmp/mf.sh -b -p "$HOME/miniforge3"
source "$HOME/miniforge3/etc/profile.d/conda.sh"
```

---

## 5. Scriptable install (run this)

> Agent: save as `setup_section_pipeline.sh`, `chmod +x`, run it. It is safe to re-run. Resolve QuPath/elastix asset URLs via the GitHub API so they don't go stale.

```bash
#!/usr/bin/env bash
set -euo pipefail
ROOT="${SECTION_PIPELINE_ROOT:-$HOME/section-pipeline}"; TOOLS="$ROOT/tools"
QUPATH_TAG="${QUPATH_TAG:-v0.6.0}"; ELASTIX_TAG="${ELASTIX_TAG:-5.2.0}"; PY_VER="3.11"
FIJI_URL="https://downloads.imagej.net/fiji/latest/fiji-linux64.zip"
mkdir -p "$TOOLS"; cd "$TOOLS"
CONDA=$(command -v mamba || command -v conda)

# --- QuPath ---
if [ ! -d "$TOOLS/QuPath" ]; then
  QP_URL=$(curl -fsSL "https://api.github.com/repos/qupath/qupath/releases/tags/${QUPATH_TAG}" | grep -oE 'https://[^"]*Linux\.tar\.xz' | head -n1)
  curl -fL "$QP_URL" -o qupath.tar.xz
  mkdir -p QuPath && tar -xf qupath.tar.xz -C QuPath --strip-components=1 && rm -f qupath.tar.xz
  chmod u+x "$TOOLS"/QuPath/bin/QuPath || true
fi

# --- Fiji ---
if [ ! -d "$TOOLS/Fiji.app" ]; then
  curl -fL "$FIJI_URL" -o fiji.zip && unzip -q fiji.zip && rm -f fiji.zip
  chmod u+x "$TOOLS"/Fiji.app/ImageJ-linux64 || true
fi

# --- elastix 5.2.0 ---
if [ ! -d "$TOOLS/elastix" ]; then
  EX_URL=$(curl -fsSL "https://api.github.com/repos/SuperElastix/elastix/releases/tags/${ELASTIX_TAG}" | grep -oE 'https://[^"]*[Ll]inux[^"]*\.(tar\.(gz|bz2)|zip)' | head -n1)
  mkdir -p elastix
  case "$EX_URL" in
    *.zip)     curl -fL "$EX_URL" -o ex.zip && unzip -q ex.zip -d elastix && rm -f ex.zip ;;
    *.tar.bz2) curl -fL "$EX_URL" -o ex.tbz && tar -xjf ex.tbz -C elastix --strip-components=1 && rm -f ex.tbz ;;
    *.tar.gz)  curl -fL "$EX_URL" -o ex.tgz && tar -xzf ex.tgz -C elastix --strip-components=1 && rm -f ex.tgz ;;
  esac
  echo "If elastix won't launch, add to ~/.bashrc: export LD_LIBRARY_PATH=\"$TOOLS/elastix/lib:\$LD_LIBRARY_PATH\""
fi

# --- conda env: deepslice (optional local) ---
conda env list | grep -qE '^\s*deepslice\s' || { $CONDA create -y -n deepslice python=3.10; conda run -n deepslice pip install -U pip DeepSlice; }

# --- conda env: braian ---
conda env list | grep -qE '^\s*braian\s' || { $CONDA create -y -n braian python=$PY_VER; conda run -n braian pip install -U pip braian jupyterlab; }

# --- conda env: brainrender ---
conda env list | grep -qE '^\s*brainrender\s' || { $CONDA create -y -n brainrender python=$PY_VER; conda run -n brainrender pip install -U pip brainrender; $CONDA install -y -n brainrender -c conda-forge ffmpeg || true; }

echo "DeepSlice env prefix (for Fiji):"; conda run -n deepslice python -c "import sys,os;print(os.path.dirname(os.path.dirname(sys.executable)))"
echo "Scriptable install complete. Proceed to GUI steps (Section 6)."
```

---

## 6. GUI-only steps (HUMAN at the monitor — agent cannot click these)

**A. Fiji / ABBA** — launch `$SECTION_PIPELINE_ROOT/tools/Fiji.app/ImageJ-linux64`
1. `Help > Update... > Manage update sites` → tick **PTBIOP** (tick *OMERO 5.5-5.6* only if images live on an OMERO server) → *Apply and close* → *Apply changes* → restart Fiji.
2. `Plugins > BIOP > Elastix > Test elastix` → set:
   - `elastix` → `…/tools/elastix/bin/elastix` (verify exact path)
   - `transformix` → `…/tools/elastix/bin/transformix`
   - Console should print `Elastix -> set :-)` and `Transformix -> set :-)`. Run the offered registration test.
3. *(Optional)* point ABBA's DeepSlice at the `deepslice` conda env prefix printed by the script — or just use DeepSlice **online** (no setup).

**B. QuPath** — launch `$SECTION_PIPELINE_ROOT/tools/QuPath/bin/QuPath`
1. `Extensions > Manage extensions > Manage extension catalogs` → add **both**:
   - ABBA / Warpy: `https://github.com/BIOP/qupath-biop-catalog`
   - BraiAnDetect: `https://github.com/carlocastoldi/qupath-extension-braian-catalog`
2. Install latest **abba** + **braian** extensions (the `+` buttons) → restart QuPath.
3. Confirm under `Extensions > Manage extensions`: **ABBA, Image Combiner Warpy, Warpy, BraiAn**.

**C. First registration** downloads the Allen mouse CCFv3 atlas once (needs internet) — let it finish.

---

## 7. Critical analysis gotchas (bake into config, not afterthoughts)

- **DAPI nuclear vs TdTomato cytosolic mismatch.** In QuPath: detect nuclei on **DAPI**, then add a **cytoplasmic expansion ring** to measure **TdTomato** correctly; classify **Fos** on the nuclear compartment. Colocalization must be **nucleus-anchored** (does a detected cell contain a Fos+ / TdT+ centroid), not proximity-based.
- **Detection engine.** Prefer **BraiAnDetect** (the QuPath extension) over hand-rolled StarDist for the multichannel detection — it enforces identical settings across all sections and animals, which is what makes cross-condition reactivation-density comparison valid. Reserve StarDist only if DAPI nuclear segmentation quality is poor. Pull starting params (threshold, min/max area, sigma, cytoplasmic expansion radius) from the F1000Research 2026 / bioRxiv 2024.09.16.611953 TRAP2 paper.
- **Atlas-space consistency.** ABBA's built-in Allen atlas and brainrender's `allen_mouse` are both CCFv3 — point clouds will land correctly **as long as you export coordinates from QuPath/ABBA in microns, not pixels**.
- **3D = atlas-space point cloud** (cells plotted in the Allen reference brain), **not** a physical reconstruction of the tissue slices. Confirm with PI this is the intended "3D" before scaling — literal tissue reconstruction from distorted, unevenly-spaced sections is a much larger, approximate effort.

---

## 8. Verification (agent can run these)

```bash
ls "$SECTION_PIPELINE_ROOT"/tools/QuPath/bin/QuPath
ls "$SECTION_PIPELINE_ROOT"/tools/Fiji.app/ImageJ-linux64
find "$SECTION_PIPELINE_ROOT"/tools/elastix -name 'elastix' -type f
conda run -n braian python -c "import braian; print('braian', getattr(braian,'__version__','ok'))"
conda run -n brainrender python -c "import brainrender; print('brainrender ok')"
conda run -n deepslice python -c "import DeepSlice; print('deepslice ok')"
```

For brainrender (this desktop has a monitor, so interactive works):
```bash
conda run -n brainrender python -c "from brainrender import Scene; s=Scene(atlas_name='allen_mouse_25um'); s.add_brain_region('LA'); print('scene ok')"
```

---

## 9. Daily entry points

- QuPath: `…/tools/QuPath/bin/QuPath`
- Fiji/ABBA: `…/tools/Fiji.app/ImageJ-linux64`
- Stats: `conda activate braian && jupyter lab`
- 3D viz: `conda activate brainrender && python my_render.py`

---

## 10. References (templates to follow)

- ABBA + BraiAn — Chiaruttini, Castoldi, Requie et al., *Cell Reports* 2025 (nucleus-containment colocalization; IEG whole-brain mapping).
- TRAP2 tdTomato + c-Fos QuPath/ABBA workflow — F1000Research 2026 / bioRxiv 2024.09.16.611953 (closest match; use for detection/classification starting params).
- ABBA docs: abba-documentation.readthedocs.io · QuPath: qupath.readthedocs.io · BraiAn: silvalab.codeberg.page/BraiAn · brainrender: brainglobe.info
