# Next session — start here

**Written 2026-08-03** as a cold-start handoff. Assumes no memory of the session that
wrote it. Supersedes `NEXT-TASK-m3-hipp2.md`, which is now history.

> **Active task, 2026-08-04:** `NEXT-TASK-finish-m5hipp3-m3str1.md` — two datasets to
> take end to end, and a `k_robust` omission on M5 Hipp3 to settle before its numbers
> mean anything. Read that first; this file is the standing context behind it.

Branch `generalize-pipeline-260729`, ~45 commits ahead of `main`, still unmerged.

**Framing (operator, 2026-08-03): M3 and M5 were PROOF-OF-CONCEPT runs.** A fresh set
of brains is being cut and imaged. Treat the M3/M5 numbers as pipeline validation, not
as results to be rescued — the open questions in §2 are expected to be answered by the
new cohort under a settled acquisition regime, not by further reanalysis of the pilots.
What the pilots taught us about acquisition is distilled in `ACQUISITION-CHECKLIST.md`,
which is the most actionable document in the repo right now.

---

## 1. What state the data is in

| dataset | sections | pixel µm | Z | TdT k | status |
| --- | --- | --- | --- | --- | --- |
| M3 Hipp1 072326 | 7 | 0.460357 | 4 | 2.0 | clean, re-run 2026-08-02 |
| M3 Hipp2 072526 | 6 | 0.460357 | 4 | 2.0 | clean, repaired 2026-08-02 |
| M5 073026 | 8 of 10 | 0.6905355 | 2 | 2.0 | clean; 2 excluded, see below |

**M3 Hipp1 + Hipp2 are pooled** as animal `M3_072326-072526` (same brain, two sessions
a month apart). Both `pipeline.yml` files declare it; `cockpit_animal --pool-same-animal`
merges them. Splitting is free — run one project alone, or read the `projects` column.

**M5 exclusions** are documented with their rule in `M5 072526/EXCLUSIONS.md`:
`M5c_s5` (autofocus gradient) and `M5c_s2` (untrusted registration). Two further
sections, `M5c_s3`/`s4`, produced no exports — their histograms have only one peak, so
the span-fraction rule cannot be applied. A prominence sweep gave thresholds from 1,073
to 6,328 with no stable answer, so this is not a tuning problem. The operator intends
to set those by eye.

Current outputs live in **`results/animal/clean/`**. Everything older was built on
corrupted data and was deleted.

---

## 2. The open scientific question — read this before touching the biology

**The direction of the M3 vs M5 difference is not determined by the current data.**
It flips depending on which technical floor you normalise to, and both floors are
defensible.

Two independent floor estimates:

```
                        M3      M5
control regions       1.46    2.13     mean of SSp and MOp
anchor pseudo-marker  1.48    1.25     anchor channel thresholded at the same prevalence
agree?                 YES      NO
```

For M3 the two agree almost exactly (1.46 vs 1.48) — good validation that the method
works. For M5 they disagree badly, which means **M5's SSp and MOp sit well above M5's
technical floor**. Either those regions are genuinely engaged in M5 (making them bad
controls for that animal), or something else inflates M5's regional values.

The consequence, on the only three regions with ≥2 sections in both animals:

```
region   M3 raw  M5 raw    ÷control          ÷anchor floor
STR        2.93    3.07    2.01 vs 1.44 M3   1.98 vs 2.46 M5
HY         2.80    2.76    1.91 vs 1.29 M3   1.89 vs 2.21 M5
ACA        1.47    1.78    1.00 vs 0.84 M3   0.99 vs 1.43 M5
```

**Same data, opposite conclusion.** With n=1 per group there is no way to arbitrate.
Do not report a direction until this is resolved. The likely resolution is the
`M5a_s1` re-image (below), which restores the hippocampal regions and gives M5 more
multi-section coverage.

The operator's hypothesis is that M5 (same context) should be higher. Note the
hypothesis has NOT been supported yet — an earlier session claimed it was, on
corrupted data. Do not repeat that.

---

## 3. Corrections made — do not re-derive these wrongly

- **`inspect_marker_band.groovy` used to overwrite cell classes.** Batch-running it
  corrupted classification in M3 Hipp2 (27,632 cells). Fixed to use derived classes;
  all projects repaired and verified `InspectBand`-free. If counts ever drop
  inexplicably, check for stray `InspectBand` classes first.
- **`cockpit_animal` was never wrong.** A previous session doubted it on the strength
  of the corrupted exports. Its roll-up is correct; the per-cell `region_label` is a
  LEAF, so a parent acronym must be rolled down via
  `cockpit_regions.Ontology.descendants_or_self()`.
- **"Do not register on DAPI" was a documentation error**, since corrected. We DO
  register the section's DAPI against the atlas's Nissl channel.
- The pipeline **is** reproducible — export verified byte-identical across three runs.

---

## 4. What needs doing, in order

1. **Re-image `M5a_s1`** (hippocampus) at the `M5b`/`M5c` settings. It is the only M5
   material overlapping M3's coverage, it has a bright peak of 253 versus ~5,000 for
   its siblings, and every region where M5 currently leads rests on it alone. This
   single session unblocks the comparison.
2. **M3 anterior + caudal sections** — M3 lacks ACA/ACB/BST/PVH and PB/CU. Whole-brain
   cutting is standard here, so this is an imaging-coverage task, not a protocol change.
3. **Resolve the floor ambiguity** (section 2). Candidate approaches already built:
   `scripts/chance_methods.py` computes five definitions side by side;
   `scripts/compare_datasets.py` rates which metrics survive which parameter changes.
4. **Fresh-project smoke test** — still unbuilt, and the highest-value engineering item.
   Ten bugs in four days were the same shape: code that works on the state the
   workspace happens to be in. Spec is in `DEPLOYMENT-READINESS.md`.
5. **Notebook portability** — `PARAMS` still defaults to the wBA project and carries
   absolute `/home/jflab/` paths. Blocks use on other machines.

---

## 5. Ground rules that are not negotiable

- **Tooling advises, never refuses.** QC gates and comparability checks report and
  rank; they never block or drop data. Fail loud only on a genuine defect (a threshold
  that cannot be calibrated, a missing file, a self-contradictory config). The line:
  refuse on *cannot be computed*, advise on *may not mean what you think*.
- **Evidence hierarchy: SEEN > STRUCTURAL > ASSUMED.** What the operator sees on the
  image outranks any band, seed or model. Never tune a parameter to move an `<assumed>`
  number into range.
- **One acquisition regime per comparison.** Relative thresholds absorb brightness
  drift but not geometry (pixel size, Z depth) or separability (SNR).
- **LA is the trusted region, not CA1.** TdT expression is unreliable in CA1 in this
  lab. CA1 and DG top the enrichment ranking and are the least trustworthy.
- **One classification path** — `02_detect_classify.groovy`, driven by `pipeline.yml`.
  Every `BraiAn.yml` `classifiers:` block is empty by design.

---

## 6. Where things are

```
docs/pipeline-stages.yml     structured stage list with status fields (active /
                             standby / optional / diagnostic / unwired). elastix is
                             STANDBY, not retired -- it may return depending on
                             mounting and slicing quality.
docs/runbook/03-tuning.md    every knob, what it does, which way to move it
DEPLOYMENT-READINESS.md      what stands between this and other machines
M5 072526/EXCLUSIONS.md      exclusion RULES, stated before any counts existed
results/animal/clean/        the only trustworthy outputs
scratchpad/                  gitignored; test fixtures carry .pipeline-nosync
```

Durable facts live in the memory directory and are loaded automatically — check the
index there before re-deriving anything about ABBA, thresholds, or comparability.
