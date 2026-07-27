# VALIDATION — TdT-only end-to-end (D-17)

**Slice set:** wBA1-2_2-1 (072026), 5 coronal sections (s1–s5), 20× hybrid MIP, 0.4604 µm/px
**Markers:** DAPI-T4 (anchor) + AF568-T2 (TdT). **No Fos channel** — this is the single-marker (variable-marker) acceptance bar.
**Run date:** 2026-07-27 · **n = 1 animal (methods validation, provisional absolutes)**
**QuPath project:** `wBA/wBA1-2_2-1-tdt-only 072026 project/`

## What this validates

The generalized, config-driven pipeline (Phase 06.1) runs **end-to-end on a TdT-only set** and degrades cleanly to a single marker — no Fos/Double+ artifacts anywhere — producing biologically plausible whole-cell engram fractions in the amygdala.

## Pipeline configuration used

| Stage | Setting |
|---|---|
| MIP | hybrid: single sharpest DAPI plane per scene + full-Z TdT MIP (`czi_mip.py`) |
| Detection | BraiAnDetect, DAPI-T4 anchor, `peakProminence: 45` (captures dim nuclei — operator visual call on the LA), sigma 2.0, cellExpansion 5.0 µm |
| Classification | `02_detect_classify.groovy`, **TdT compartment = `whole-cell`** (area-weighted nucleus+ring `Cell: AF568-T2 mean`, bg-sub) — TdTomato fills the whole cell; robust cut `median + k·1.4826·MAD`, k_robust = 3.0 |
| Export | `03_export_region_table.groovy` (per-cell TSV + per-region table + growing combined CSV) |

## Results

### Per-slice cell counts

| slice | detections (DAPI+) | TdT+ (k=3) | TdT+ % | Excluded |
|---|---|---|---|---|
| s1 | 238,983 | 10,451 | 4.4% | 2,157 |
| s2 | 225,597 | 9,559 | 4.2% | 3,016 |
| s3 | 218,382 | 9,316 | 4.3% | 1,392 |
| s4 | 235,344 | 10,443 | 4.4% | 2,494 |
| s5 | 222,001 | 9,052 | 4.1% | 2,637 |

### D-17 variable-marker contract — PASS

Combined CSV (`wBA/reference/region_marker_combined.csv`) contains **only** `marker ∈ {DAPI, TdT}` and `class ∈ {DAPI+, TdT+}` — **zero Fos rows, zero Double+ rows**. Per-slice region tables emit DAPI+/TdT+ count+density columns only (no `Fos+`/`Double+` columns, no NaN placeholders). Confirmed structurally.

### Export integrity — PASS

`verify_export_integrity.py`: 5 paired per-cell/per-region stems, matched row counts, no cross-entry filename clobbering.

### Zero-leak (D-10) — PASS (authoritative Groovy assertion)

`03_export_region_table.groovy`'s in-script assertion passes for every slice: `sum(leaf own counts) + unresolved == total classified non-excluded` (the fix that reconciles the ~1 edge cell per slice whose centroid falls outside all atlas regions). This is the authoritative rollup proof.

> **Known issue (deferred):** the redundant Python re-proof `build_dapi_reference.py --check-zero-leak` hard-asserts `leaf_sum == root_rollup`, which assumes every cell lands on a geometric **leaf** region. On this amygdala set ~26% of cells legitimately resolve to **non-leaf** parent regions (the CR-01/LABEL-01 phenomenon on non-laminar tissue), so the Python check false-fails. The rollup itself is correct (root rollup = total). The Python re-proof needs a redesign that reconciles non-leaf-assigned cells (it lacks per-region OWN counts from the CSV to do so today). **Groovy `03` remains authoritative.**

### Detection-range k-sweep (whole-cell TdT+, % of classifiable)

| k | across s1–s5 |
|---|---|
| 2.0 | 7.8–8.1% |
| 2.5 | 5.5–5.8% |
| 3.0 (current) | 4.1–4.5% |

Stable across all 5 sections. Engram range ≈ **4.3% (strict) → 8% (lenient)**. Tool: `scripts/k_sweep_readout.py`.

### LA/BA regional readout (reactivation fraction, TdT+/DAPI, L+R)

Amygdala present in **s1, s2, s4**; absent in s3, s5 (AP levels without amygdala).

| nucleus | k=3 | k=2 | note |
|---|---|---|---|
| BMA | 3.8–5.2% | 6.8–7.8% | highest engram signal |
| BLA | ~2.8% (s1/s4) | ~5% | s2 7.6% on low n (474) — noisy |
| LA | 1.4–2.4% | ~3–5% | lowest |

Figure: `wBA/wBA1-2_2-1-tdt-only 072026 project/qc_LA-BA_wholecell_ksweep.png`.

### Bioplausibility (val01_metrics)

Fos+ control skipped (marker absent, correct). Nucleus-area peak 30–40 µm² and per-region density above the M3/hippocampus-calibrated gate — expected for denser amygdala + finer 0.46 µm imaging + intentional dim-cell capture; operator visual one-per-nucleus is the arbiter here, not the neuron-calibrated gate.

## Robustness note

TdT+ fractions and the BMA>BLA>LA pattern held **stable** across two mid-flight methodology changes — cytoplasm-ring → whole-cell TdT, and +13% dim-cell DAPI capture. The engram signal is not an artifact of a particular threshold or compartment choice.

## Carry-forward

- **LABEL-01 (Phase 8):** ~26% non-leaf region assignment on amygdala — re-audit the smallest-area-leaf heuristic on LA/BA before trusting per-region absolutes.
- **Detection params:** `peakProminence: 45` + whole-cell TdT are the wBA-series settings; lock into canonical config when the series params are finalized.
- **Python `--check-zero-leak`:** redesign to reconcile non-leaf assignment (see known issue above).
- **Stats:** n=1 methods validation — animal-level aggregation + group comparison is Phase 10.
