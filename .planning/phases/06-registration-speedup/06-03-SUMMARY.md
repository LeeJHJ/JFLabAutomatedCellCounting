# 06-03 SUMMARY — REG-03 DeepSlice batch registration

**Status:** Complete (operator GUI, 2026-07-20)

## What was done
Native ABBA "DeepSlice Registration (Local)" run on all 5 wBA1-3 sections in one pass. AP + initial
affine established for each; global slicing angle set manually (X=−8.6°, Y=3.9°, locked).

## Key outcomes / deviations from plan
- **Import mechanism corrected:** MIPs loaded via `Import > Import With Bio-Formats` (the SOP's "Multi
  Image To Atlas" load target does not exist). Dialog field labels reconciled with the live GUI.
- **D-02 reversed → `No post-processing`.** `s1..s5` are scene labels, not true AP order. DeepSlice's
  independent per-slice AP confirms the true order is **s4(7.19) < s1(7.59) < s2(7.79) < s5(8.01) <
  s3(8.44)** (atlas Z mm) — scrambled vs. labels, validating the reversal.
- **D-04 reversed → single global slicing angle.** ABBA's slicing angle is one global plane (no
  per-section through-plane tilt); inconsistent cut/mount handled by per-section in-plane + BigWarp.
- **DAPI B&C:** min 0 / max ≈ 20000 (16-bit data tops ~33k; ABBA's auto 0:255 over-saturated).

## Artifacts
- `06-REG03-SOP.md` — filled per-section run record + reconciled procedure.
- 5 registered ABBA slice states (DeepSlice + global angle).

## Carry-forward
- **LA-presence risk (Phase 8 LABEL-01):** s5 (8.01) and s3 (8.44) register posterior of LA (LA ends
  ~7.90mm) — likely BLA/BMA only; verify on QuPath annotation overlay.
- Sections suboptimally cut/mounted — improved technique for the real series.
