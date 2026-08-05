#!/usr/bin/env python3
"""k_vs_chance.py -- does the above-chance overlap survive tightening the marker cuts?

THE QUESTION THIS ANSWERS
    Operator, 2026-08-04: "it's interesting that there is always an above-chance
    overlap; visually I feel it's due to the thresholding we do for TdT and Fos."

    That is a real hypothesis with a decisive test. `overlap_above_chance` is
    (D*N)/(T*A), and T, A, D all move when `k_robust` moves. If the overlap is built
    out of MARGINAL calls, then removing those calls -- raising k -- must collapse it
    toward 1.0. If it lives in the CONFIDENT population, it survives or strengthens.

    Nothing existing answers this. `chance_methods.py` computes the floor beautifully
    but on ALREADY-CLASSIFIED data, at whatever k the pipeline happened to run (its
    own `--k` is a neighbour count for the local null, not k_robust). This module
    supplies the missing axis: every statistic recomputed across a k_robust sweep.

    It needs no QuPath. `<marker>_bgsub` in *__percell_export.tsv is exactly the
    column 02_detect_classify.groovy thresholds, so k can be swept on disk.

WHAT IT MEASURED (M3 Hipp2, 1,303,700 cells pooled over 6 sections, 2026-08-05)

        k     TdT+     Fos+   above-chance   anchor floor   real/floor   shuffled
        1.5  10.58%   18.45%      2.04           1.31          1.56        1.01
        2.0   6.76%   15.42%      2.34           1.36          1.72        1.01
        3.0   3.35%   11.82%      2.99           1.53          1.95        1.00
        5.0   1.43%    8.12%      4.29           1.70          2.52        1.00
       10.0   0.57%    4.24%      7.73           1.78          4.34        1.01

    THE HYPOTHESIS IS NOT SUPPORTED, and the direction is informative. Above-chance
    RISES as the cut tightens: the most confident TdT+ cells are the most Fos-enriched.
    Marginal calls DILUTE the effect rather than creating it. The shuffled control sits
    at 1.00-1.01 throughout, so the arithmetic is not manufacturing anything.

    BUT THE HYPOTHESIS IS NOT WRONG EITHER, in a way that matters more. The anchor
    pseudo-marker -- DAPI thresholded to the same prevalence as TdT, containing zero
    engram biology by construction -- reads 1.31 rising to 1.78 across the same sweep.
    So a technical floor exists, it is large, AND IT MOVES WITH k. An above-chance
    number quoted without its k and its floor is not interpretable.

    The reassuring part is that real/floor also grows, 1.56 -> 4.34: the real signal
    strengthens FASTER than the floor. That is the strongest evidence available here
    that much of the effect is biology.

    Separately measured on the same cells: TdT and Fos brightness correlate at
    Spearman rho +0.18 among the TdT-NEGATIVE half, where no engram biology can exist.
    DAPI correlates with neither (-0.08, -0.10), so this is NOT "thick tissue makes
    everything bright" -- it is specific to the two marker channels, pointing at shared
    pixels or bleed-through rather than a global brightness confound.

HOW TO READ A RESULT
    above-chance falls toward 1.0 as k rises   the effect WAS marginal calls; the
                                               operator's hypothesis would be confirmed
    above-chance rises, floor flat             effect concentrated in confident cells
    above-chance rises, floor rises with it    what we see; report real/floor, not raw
    shuffled != 1.0                            STOP: the metric itself is broken

Usage:
    python3 scripts/k_vs_chance.py --project "<project dir>"
    python3 scripts/k_vs_chance.py --project "<dir>" --regions LA,BLA,CA1
    python3 scripts/k_vs_chance.py --self-test
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import k_sweep_readout as ksr   # noqa: E402  -- the validated reproduction of the

# classifier rule. NEVER re-implement median/MAD/threshold here: two copies of a
# classification rule is how this project got a silent double-classification bug
# (CLAUDE.md, "one classification path").

DEFAULT_K_LADDER = (1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 7.0, 10.0)


def positive_mask(values: np.ndarray, k: float) -> np.ndarray:
    """Positivity at k, using k_sweep_readout's threshold. Strict >, as the Groovy does."""
    return np.asarray(values, dtype=float) > ksr.robust_threshold(np.asarray(values, dtype=float), k)


def above_chance(tagged: np.ndarray, activity: np.ndarray) -> float:
    """(D*N)/(T*A) -- identical to cockpit_animal's overlap_above_chance.

    NaN when either marginal is empty, rather than a plausible-looking number: an
    empty positive set has no conditional probability, and 0/0 dressed as 1.0 would
    enter a comparison as a real "exactly at chance" observation.
    """
    t = np.asarray(tagged, dtype=bool)
    a = np.asarray(activity, dtype=bool)
    n, T, A = t.size, int(t.sum()), int(a.sum())
    if not (n and T and A):
        return float("nan")
    return (int((t & a).sum()) * n) / (T * A)


def shuffled_control(tagged: np.ndarray, activity: np.ndarray, seed: int = 0) -> float:
    """Above-chance after permuting the tagged labels. Must be ~1.0 or the metric is broken."""
    rng = np.random.default_rng(seed)
    return above_chance(rng.permutation(np.asarray(tagged, dtype=bool)), activity)


def anchor_floor(anchor: np.ndarray, activity: np.ndarray, prevalence: float) -> float:
    """Above-chance of a DAPI pseudo-marker matched in prevalence to the real tagged set.

    Same construction as chance_methods.anchor_floor_ratio, evaluated here at each k so
    the floor can be compared against the real value on equal terms. The anchor says
    nothing about co-expression, so whatever this returns is technical.
    """
    v = np.asarray(anchor, dtype=float)
    ok = np.isfinite(v)
    if ok.sum() < 200 or not (0 < prevalence < 1):
        return float("nan")
    return above_chance(ok & (v > np.quantile(v[ok], 1 - prevalence)), activity)


def sweep(tagged_values: np.ndarray, activity_values: np.ndarray,
          anchor_values: np.ndarray | None = None,
          ks: tuple[float, ...] = DEFAULT_K_LADDER) -> pd.DataFrame:
    """One row per k, with both controls recomputed AT THAT k.

    Recomputing the floor per k is the whole point: it is not a constant, and treating
    it as one is what makes a bare above-chance value look more meaningful than it is.
    """
    rows = []
    for k in ks:
        T = positive_mask(tagged_values, k)
        A = positive_mask(activity_values, k)
        n = T.size
        row = {"k": float(k), "N": n, "T": int(T.sum()), "A": int(A.sum()),
               "D": int((T & A).sum())}
        row["tagged_pct"] = 100.0 * row["T"] / n if n else np.nan
        row["activity_pct"] = 100.0 * row["A"] / n if n else np.nan
        row["reactivation_pct"] = 100.0 * row["D"] / row["T"] if row["T"] else np.nan
        row["above_chance"] = above_chance(T, A)
        row["shuffled"] = shuffled_control(T, A)
        row["anchor_floor"] = (anchor_floor(anchor_values, A, T.mean())
                               if anchor_values is not None and row["T"] else np.nan)
        row["real_over_floor"] = (row["above_chance"] / row["anchor_floor"]
                                  if row["anchor_floor"] and np.isfinite(row["anchor_floor"])
                                  else np.nan)
        rows.append(row)
    return pd.DataFrame(rows)


def verdict(df: pd.DataFrame) -> str:
    """Plain-language read of the sweep, in the operator's own terms."""
    ok = df.dropna(subset=["above_chance"])
    if len(ok) < 2:
        return "not enough finite points to judge a direction"
    lo, hi = ok.iloc[0], ok.iloc[-1]
    bad_shuffle = ok["shuffled"].sub(1.0).abs().max() > 0.15
    if bad_shuffle:
        return ("STOP: the shuffled control is not 1.0. The metric is broken and nothing "
                "else here means anything.")
    lines = []
    if hi["above_chance"] < lo["above_chance"] * 0.8:
        lines.append(
            f"above-chance FALLS with k ({lo['above_chance']:.2f} -> {hi['above_chance']:.2f}). "
            "The overlap is built from marginal calls -- thresholding is creating it.")
    elif hi["above_chance"] > lo["above_chance"] * 1.2:
        lines.append(
            f"above-chance RISES with k ({lo['above_chance']:.2f} -> {hi['above_chance']:.2f}). "
            "The overlap lives in the CONFIDENT calls; marginal calls dilute it rather "
            "than create it. Thresholding is not manufacturing the effect.")
    else:
        lines.append(f"above-chance is flat in k ({lo['above_chance']:.2f} -> "
                     f"{hi['above_chance']:.2f}) -- insensitive to the cut.")
    if np.isfinite(hi.get("anchor_floor", np.nan)):
        if hi["anchor_floor"] > lo["anchor_floor"] * 1.2:
            lines.append(
                f"But the technical floor rises too ({lo['anchor_floor']:.2f} -> "
                f"{hi['anchor_floor']:.2f}), so no above-chance value is interpretable "
                f"without the k it was measured at. Report real/floor "
                f"({lo['real_over_floor']:.2f} -> {hi['real_over_floor']:.2f}).")
        else:
            lines.append(f"The technical floor stays near {hi['anchor_floor']:.2f}, so the "
                         "rise is not a floor artifact.")
    return " ".join(lines)


def load(project_dir: Path, regions: list[str] | None = None) -> tuple[pd.DataFrame, str, str, int]:
    """Pooled per-cell table for a project, plus the tagged/activity column names."""
    results = Path(project_dir) / "results"
    hits = sorted(results.glob("*percell_export.tsv"))
    if not hits:
        raise FileNotFoundError(f"no *percell_export.tsv in {results}")
    df = pd.concat([pd.read_csv(h, sep="\t") for h in hits], ignore_index=True)
    markers = [c for c in df.columns if c.endswith("_bgsub")]
    if len(markers) < 2:
        raise ValueError(f"need two markers, found {markers}")
    # Roles by compartment, never by column order: the tagged marker is the whole-cell /
    # cytoplasmic one. pipeline.yml is the authority; fall back to file order only if it
    # cannot be read.
    tagged, activity = markers[-1], markers[0]
    try:
        import yaml
        doc = yaml.safe_load((Path(project_dir) / "pipeline.yml").read_text()) or {}
        for m in doc.get("markers") or []:
            col = f"{m['name']}_bgsub"
            if col not in markers:
                continue
            if m.get("compartment") in ("whole-cell", "cytoplasmic"):
                tagged = col
            elif m.get("compartment") == "nuclear":
                activity = col
    except Exception:
        pass
    if regions:
        want = {r.strip() for r in regions}
        df = df[df["region_label"].astype(str).isin(want)]
    df = df[np.isfinite(df[tagged]) & np.isfinite(df[activity])]
    return df, tagged, activity, len(hits)


def print_report(project_dir: Path, regions: list[str] | None = None) -> int:
    df, tagged, activity, n_files = load(project_dir, regions)
    if df.empty:
        print("no cells left after filtering")
        return 1
    print(f"k_robust vs chance -- {project_dir}")
    print(f"  {len(df):,} cells from {n_files} section(s)"
          + (f", regions {regions}" if regions else ""))
    print(f"  tagged={tagged[:-6]}   activity={activity[:-6]}\n")
    out = sweep(df[tagged].to_numpy(dtype=float), df[activity].to_numpy(dtype=float),
                df["anchor_mean"].to_numpy(dtype=float) if "anchor_mean" in df else None)
    print(f"  {'k':>5} {'tagged%':>8} {'activity%':>10} {'react%':>8} "
          f"{'above-chance':>13} {'floor':>7} {'real/floor':>11} {'shuffled':>9}")
    for _, r in out.iterrows():
        print(f"  {r.k:>5.1f} {r.tagged_pct:>7.2f}% {r.activity_pct:>9.2f}% "
              f"{r.reactivation_pct:>7.1f}% {r.above_chance:>13.2f} "
              f"{r.anchor_floor:>7.2f} {r.real_over_floor:>11.2f} {r.shuffled:>9.2f}")
    print(f"\n  {verdict(out)}")
    return 0


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------
def _self_test() -> None:
    print("k_vs_chance self-test")
    rng = np.random.default_rng(11)
    n = 400_000
    # Marker measures are HEAVY-TAILED (real Fos_bgsub: median 57, mean 375, max 27,009),
    # so the synthetic is lognormal. A Gaussian empties its tail by k=5 and every
    # statistic goes NaN -- an artifact of the fixture, not of the method.
    def heavy(loc=0.0):
        return np.exp(rng.normal(loc, 1.0, n))

    # (a) Independent markers sit at chance at every k, and the shuffle agrees.
    ind = sweep(heavy(), heavy(), ks=(1.0, 2.0, 4.0))
    assert ind.above_chance.notna().all(), ind.above_chance.tolist()
    assert ((ind.above_chance - 1).abs() < 0.25).all(), ind.above_chance.tolist()
    assert ((ind.shuffled - 1).abs() < 0.25).all()
    print(f"  (a) independent markers ~1.0 at every k {ind.above_chance.round(2).tolist()}")

    # (b) THE OPERATOR'S HYPOTHESIS as a positive control: markers that are ONLY
    #     coupled near the threshold must show above-chance COLLAPSING as k rises.
    #     If this test cannot produce a falling curve, the real rising curve means
    #     nothing -- so the falling case has to be demonstrable.
    base_t, base_a = heavy(), heavy()
    # The band must sit BETWEEN the two cuts (1.88 at k=1, 4.54 at k=4 on this base):
    # above k=1 so it inflates there, below k=4 so tightening removes it. Placing it
    # above BOTH cuts makes the curve RISE instead -- which is how this fixture was
    # wrong on first writing, and is worth knowing when reading a real sweep.
    edge = rng.random(n) < 0.06
    band = np.exp(rng.normal(1.1, 0.05, n))   # ~3.00
    marg_t = np.where(edge, band, base_t)
    marg_a = np.where(edge, band, base_a)
    fall = sweep(marg_t, marg_a, ks=(1.0, 4.0))
    assert fall.above_chance.iloc[-1] < fall.above_chance.iloc[0] * 0.8, fall.above_chance.tolist()
    assert "FALLS" in verdict(fall), verdict(fall)
    print(f"  (b) marginal-only coupling COLLAPSES with k "
          f"{fall.above_chance.iloc[0]:.2f} -> {fall.above_chance.iloc[-1]:.2f}, "
          f"and the verdict says so")

    # (c) Genuinely coupled markers RISE with k -- the pattern the real data shows.
    shared = rng.normal(0, 1, n)
    rise = sweep(np.exp(shared + rng.normal(0, 0.6, n)),
                 np.exp(shared + rng.normal(0, 0.6, n)), ks=(1.0, 4.0))
    assert rise.above_chance.iloc[-1] > rise.above_chance.iloc[0], rise.above_chance.tolist()
    assert "RISES" in verdict(rise)
    print(f"  (c) genuine coupling RISES with k "
          f"{rise.above_chance.iloc[0]:.2f} -> {rise.above_chance.iloc[-1]:.2f} "
          f"(matches M3 Hipp2: 2.04 -> 7.73)")

    # (d) The anchor floor is >1 when the anchor shares the confound, and ~1 when it
    #     does not -- so a high floor is a property of the data, not of the construction.
    with_conf = sweep(np.exp(shared + rng.normal(0, 0.6, n)),
                      np.exp(shared + rng.normal(0, 0.6, n)),
                      anchor_values=shared, ks=(2.0,))
    without = sweep(np.exp(shared + rng.normal(0, 0.6, n)),
                    np.exp(shared + rng.normal(0, 0.6, n)),
                    anchor_values=rng.normal(0, 1, n), ks=(2.0,))
    assert with_conf.anchor_floor.iloc[0] > 1.3, with_conf.anchor_floor.iloc[0]
    assert abs(without.anchor_floor.iloc[0] - 1.0) < 0.2, without.anchor_floor.iloc[0]
    print(f"  (d) anchor floor {with_conf.anchor_floor.iloc[0]:.2f} when it shares the "
          f"confound, {without.anchor_floor.iloc[0]:.2f} when it does not")

    # (e) A broken metric must be caught rather than explained away.
    broken = rise.copy(); broken["shuffled"] = 1.9
    assert verdict(broken).startswith("STOP"), verdict(broken)
    print("  (e) a shuffled control away from 1.0 -> verdict STOPs")

    # (f) Empty positive sets give NaN, never a fabricated 1.0. This is also what a
    #     too-thin tail produces, so it must be NaN rather than a silent 1.0.
    empty = sweep(rng.normal(0, 1, 5_000), rng.normal(0, 1, 5_000), ks=(8.0,))
    assert np.isnan(empty.above_chance.iloc[0]), empty.above_chance.iloc[0]
    assert np.isnan(above_chance(np.zeros(50, bool), np.ones(50, bool)))
    assert np.isnan(anchor_floor(np.arange(500.0), np.ones(500, bool), 0.0))
    print("  (f) empty positive set -> NaN")

    # (g) The threshold arithmetic is k_sweep_readout's, not a second copy.
    v = np.array([0.0, 1.0, 2.0, 3.0, 4.0])
    assert positive_mask(v, 0).tolist() == (v > ksr.robust_threshold(v, 0)).tolist()
    print("  (g) thresholds delegate to k_sweep_readout (one classification rule)")

    print("\nSELF-TEST PASSED")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__.splitlines()[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--project", type=Path, default=None)
    parser.add_argument("--regions", type=str, default=None,
                        help="comma-separated leaf region labels to restrict to")
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.self_test:
        _self_test()
        return 0
    if args.project is None:
        print("nothing to do: pass --project <dir> or --self-test")
        return 1
    return print_report(args.project,
                        args.regions.split(",") if args.regions else None)


if __name__ == "__main__":
    sys.exit(main())
