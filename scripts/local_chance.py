#!/usr/bin/env python3
"""local_chance.py -- a chance baseline that is actually local, with CIs.

THE PROBLEM. `overlap_above_chance` divides P(activity+ | tagged+) by
P(activity+ | all cells in the region). That treats every cell in a region as an
equally valid comparison for every other. It is not: activity is spatially
structured, and tagged cells are not scattered uniformly. Measured on M3 Hipp2 s3
(2026-07-31), tagged cells sit in neighbourhoods that are ALREADY richer in activity
than the region average -- 14.7% vs 11.4% -- so the region-wide baseline credits that
head start to the engram:

    region-wide baseline      27.29% / 11.42%  =  2.39x
    local (k=50 neighbours)   27.29% / 14.68%  =  1.86x

About a fifth of the apparent enrichment is spatial structure, not co-labelling.
(Nucleus size was tested first and ruled out: stratifying by area moved the ratio
2.39 -> 2.37, because activity rises with size but tagging does not.)

THE BASELINE USED HERE. For each tagged+ cell, look at its `k` nearest NOT-tagged
cells in the same section and ask what fraction of them are activity+. Average that
over tagged cells. This is a matched case-control contrast -- engram cells versus the
non-engram cells physically beside them -- so local density, regional gradients, and
anything else that varies smoothly across tissue cancels.

Excluding tagged cells from the neighbourhood matters. Tagged cells cluster and are
more likely to be active; leaving them in the comparison set contaminates the baseline
with the very effect being measured.

CONFIDENCE INTERVALS. None of the existing readouts carry uncertainty, which with one
animal per group is the larger problem. Two resampling schemes:

  * section-level (DEFAULT when >=3 sections) -- resample whole sections with
    replacement. Sections are the unit that actually repeats; cells within one are not
    independent, so a cell-level interval on pooled cells is far too narrow.
  * cell-level (fallback, and loudly labelled) -- only honest as a within-section
    precision statement, never as a between-animal one.

This module ADDS a column; it does not replace `overlap_above_chance`. Nothing already
reported silently changes.

Usage:
    python3 local_chance.py --project "<project dir>" --regions CA1,CA3,STR
    python3 local_chance.py --project "<dir>" --k 100 --bootstrap 2000 --out out.csv
    python3 local_chance.py --self-test
"""

from __future__ import annotations

import argparse
import glob
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

sys.path.insert(0, str(Path(__file__).resolve().parent))

import cockpit_regions as creg  # noqa: E402  pipeline.yml Config loader -- do not fork
import cockpit_animal as ca     # noqa: E402  D-1 role resolution -- do not fork

DEFAULT_K = 100
DEFAULT_BOOTSTRAP = 1000
MIN_SECTIONS_FOR_CLUSTER = 3


def load_percell(project_dir: Path) -> pd.DataFrame:
    """Every per-cell export in a project, tagged with its section label."""
    frames = []
    for f in sorted(glob.glob(str(Path(project_dir) / "results" / "*percell_export.tsv"))):
        m = re.search(r"- ([^/]+?)__id\d+__percell_export\.tsv$", f)
        label = m.group(1) if m else Path(f).stem
        d = pd.read_csv(f, sep="\t")
        d["section"] = label
        frames.append(d)
    if not frames:
        raise FileNotFoundError(f"no *percell_export.tsv under {project_dir}/results")
    return pd.concat(frames, ignore_index=True)


def _flags(df: pd.DataFrame, tagged: str, activity: str) -> pd.DataFrame:
    """Boolean tagged/activity columns from the class label.

    'Double+' counts for BOTH, which is what makes it the intersection. Excluded cells
    are dropped -- they were removed from the analysis upstream and must not enter a
    baseline either.
    """
    d = df[df["class"] != "Excluded"].copy()
    d["tagged"] = d["class"].isin([f"{tagged}+", "Double+"])
    d["activity"] = d["class"].isin([f"{activity}+", "Double+"])
    return d.dropna(subset=["centroid_x_px", "centroid_y_px"])


def local_baseline(d: pd.DataFrame, k: int = DEFAULT_K) -> tuple[float, float, int]:
    """(observed, local_chance, n_tagged) for ONE section's cells.

    Neighbours are the k nearest NOT-tagged cells. Returns NaNs when a section has too
    few of either population to support the comparison rather than inventing a number.
    """
    tagged = d["tagged"].values
    activity = d["activity"].values
    n_tagged = int(tagged.sum())
    pool = ~tagged
    if n_tagged == 0 or pool.sum() < k:
        return (float("nan"), float("nan"), n_tagged)

    xy = d[["centroid_x_px", "centroid_y_px"]].values
    tree = cKDTree(xy[pool])
    pool_activity = activity[pool]
    _, idx = tree.query(xy[tagged], k=k)
    idx = np.atleast_2d(idx)
    return (float(activity[tagged].mean()), float(pool_activity[idx].mean(axis=1).mean()),
            n_tagged)


def _ratio_from_sections(per_section: list[tuple[float, float, int]]) -> float:
    """Pool sections by tagged-cell weight, then divide -- never a mean of per-section
    ratios (CLAUDE.md D-8: pool counts, recompute the ratio)."""
    obs_num = sum(o * n for o, _c, n in per_section if np.isfinite(o))
    loc_num = sum(c * n for _o, c, n in per_section if np.isfinite(c))
    den = sum(n for o, _c, n in per_section if np.isfinite(o))
    if den == 0 or loc_num == 0:
        return float("nan")
    return (obs_num / den) / (loc_num / den)


def region_local_chance(d: pd.DataFrame, k: int = DEFAULT_K,
                        n_boot: int = DEFAULT_BOOTSTRAP,
                        rng: np.random.Generator | None = None) -> dict:
    """Local-baseline ratio for one region, with a bootstrap CI."""
    rng = rng or np.random.default_rng(0)
    sections = sorted(d["section"].unique())
    per_section = [local_baseline(d[d["section"] == s], k) for s in sections]
    usable = [(s, v) for s, v in zip(sections, per_section) if np.isfinite(v[0])]

    ratio = _ratio_from_sections([v for _s, v in usable])
    obs_all = sum(o * n for o, _c, n in (v for _s, v in usable))
    n_all = sum(n for _o, _c, n in (v for _s, v in usable))

    boot = []
    if len(usable) >= MIN_SECTIONS_FOR_CLUSTER:
        scheme = "section-level"
        for _ in range(n_boot):
            pick = rng.integers(0, len(usable), len(usable))
            boot.append(_ratio_from_sections([usable[i][1] for i in pick]))
    elif n_all > 0:
        # Too few sections to resample. Cell-level, and the label says so.
        scheme = f"cell-level ({len(usable)} section(s) -- WITHIN-section precision only)"
        cells = pd.concat([d[d["section"] == s] for s, _v in usable]) if usable else d
        tg = cells[cells["tagged"]]
        for _ in range(n_boot):
            samp = tg.sample(len(tg), replace=True, random_state=int(rng.integers(1 << 31)))
            o = samp["activity"].mean()
            base = sum(c * n for _o, c, n in (v for _s, v in usable)) / n_all
            boot.append(o / base if base else float("nan"))
    else:
        scheme = "n/a"

    boot = [b for b in boot if np.isfinite(b)]
    lo, hi = (float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))) if boot \
        else (float("nan"), float("nan"))
    return {
        "n_sections": len(usable),
        "tagged_n": n_all,
        "observed": obs_all / n_all if n_all else float("nan"),
        "local_chance": sum(c * n for _o, c, n in (v for _s, v in usable)) / n_all
        if n_all else float("nan"),
        "above_chance_local": ratio,
        "ci_lo": lo,
        "ci_hi": hi,
        "ci_scheme": scheme,
    }


def build(project_dir: Path, regions: list[str] | None = None, k: int = DEFAULT_K,
          n_boot: int = DEFAULT_BOOTSTRAP, seed: int = 0) -> pd.DataFrame:
    config = creg.load_pipeline_config(Path(project_dir))
    roles = ca.resolve_roles(config)
    if not roles.tagged or not roles.activity:
        raise SystemExit(
            "local_chance needs BOTH a tagged and an activity marker; this project "
            f"resolved tagged={roles.tagged!r} activity={roles.activity!r}.")
    d = _flags(load_percell(project_dir), roles.tagged, roles.activity)

    if regions:
        # region_label in the per-cell export is the LEAF region a cell was assigned to,
        # so a parent acronym ('SSp', 'BLA') matches nothing -- its cells are labelled
        # with descendants ('SSp-bfd', 'BLAa'). Say so instead of silently returning
        # fewer rows than were asked for.
        present = set(d["region_label"].unique())
        missing = [r for r in regions if r not in present]
        if missing:
            print(f"  NOTE: no cells carry these labels: {missing}")
            print(f"        per-cell region_label is the LEAF region; a parent acronym will")
            print(f"        not match. Use the leaf acronyms, e.g. "
                  f"{sorted(a for a in present if any(a.startswith(m) for m in missing))[:6]}")
        d = d[d["region_label"].isin(regions)]
    rng = np.random.default_rng(seed)
    rows = []
    for region, sub in d.groupby("region_label"):
        if regions is None and len(sub) < 500:
            continue
        r = region_local_chance(sub, k=k, n_boot=n_boot, rng=rng)
        r["region_acronym"] = region
        rows.append(r)
    out = pd.DataFrame(rows)
    cols = ["region_acronym", "n_sections", "tagged_n", "observed", "local_chance",
            "above_chance_local", "ci_lo", "ci_hi", "ci_scheme"]
    return out[cols].sort_values("above_chance_local", ascending=False) if len(out) else out


def _self_test() -> None:
    print("Running --self-test (synthetic point patterns, no project needed)...")
    rng = np.random.default_rng(7)

    def frame(n, grad, tag_bias, section="s1"):
        """Activity probability rises along x (a spatial gradient); tagged cells are
        placed preferentially at high x when tag_bias is True. Tagging carries NO
        genuine effect on activity -- any apparent enrichment is purely spatial."""
        x = rng.uniform(0, 1000, n)
        y = rng.uniform(0, 1000, n)
        p_act = 0.05 + grad * (x / 1000.0)
        act = rng.random(n) < p_act
        w = (x / 1000.0) ** 3 if tag_bias else np.ones(n)
        tag_idx = rng.choice(n, size=n // 12, replace=False, p=w / w.sum())
        tag = np.zeros(n, bool); tag[tag_idx] = True
        cls = np.where(tag & act, "Double+", np.where(tag, "T+", np.where(act, "A+", "Negative")))
        return pd.DataFrame({"class": cls, "region_label": "R1", "centroid_x_px": x,
                             "centroid_y_px": y, "section": section})

    d = _flags(frame(30000, grad=0.30, tag_bias=True), "T", "A")
    obs, loc, n = local_baseline(d, k=100)
    region_p = d["activity"].mean()
    check = lambda c, m: print(f"  {'ok  ' if c else 'FAIL'}  {m}") or (c or sys.exit(1))

    check(obs / region_p > 1.25,
          f"region-wide baseline shows FALSE enrichment {obs/region_p:.2f}x on a "
          f"purely spatial confound")
    check(abs(obs / loc - 1.0) < 0.12,
          f"local baseline correctly returns ~1.0x ({obs/loc:.2f}x) -- the confound is removed")
    check(loc > region_p, f"local chance ({loc:.3f}) exceeds region chance ({region_p:.3f}), "
                          f"i.e. tagged cells sit in richer neighbourhoods")

    # A REAL effect must still be detected: tagged cells get extra activity outright.
    d2 = _flags(frame(30000, grad=0.0, tag_bias=False), "T", "A")
    flip = d2["tagged"] & (rng.random(len(d2)) < 0.5)
    d2.loc[flip, "activity"] = True
    o2, l2, _ = local_baseline(d2, k=100)
    check(o2 / l2 > 2.0, f"a genuine effect survives the local baseline ({o2/l2:.2f}x)")

    # Bootstrap: >=3 sections -> section-level scheme; fewer -> labelled cell-level.
    multi = pd.concat([_flags(frame(8000, 0.2, True, f"s{i}"), "T", "A") for i in range(4)])
    r = region_local_chance(multi, k=50, n_boot=200, rng=np.random.default_rng(1))
    check(r["ci_scheme"] == "section-level", "4 sections -> section-level bootstrap")
    check(r["ci_lo"] < r["above_chance_local"] < r["ci_hi"], "CI brackets the point estimate")
    one = region_local_chance(_flags(frame(8000, 0.2, True), "T", "A"), k=50, n_boot=200,
                              rng=np.random.default_rng(1))
    check("cell-level" in one["ci_scheme"], "1 section -> cell-level scheme, labelled as such")

    print("\nself-test PASSED: the local baseline removes a purely spatial confound "
          "(region-wide reports false enrichment, local returns ~1.0x), still detects a "
          "genuine effect, and the bootstrap picks section-level resampling when enough "
          "sections exist and says so when it cannot.")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    p.add_argument("--project", type=Path, default=None, help="QuPath project directory")
    p.add_argument("--regions", default=None, help="comma-separated acronyms (default: all "
                                                   "regions with >=500 cells)")
    p.add_argument("--k", type=int, default=DEFAULT_K, help=f"neighbours (default {DEFAULT_K})")
    p.add_argument("--bootstrap", type=int, default=DEFAULT_BOOTSTRAP,
                   help=f"resamples (default {DEFAULT_BOOTSTRAP})")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--out", type=Path, default=None, help="write CSV here")
    p.add_argument("--self-test", action="store_true")
    a = p.parse_args()
    if not a.self_test and a.project is None:
        p.error("--project is required unless --self-test is set")
    return a


def main() -> int:
    a = parse_args()
    if a.self_test:
        _self_test()
        return 0
    regions = [r.strip() for r in a.regions.split(",")] if a.regions else None
    df = build(a.project, regions, k=a.k, n_boot=a.bootstrap, seed=a.seed)
    if df.empty:
        print("no regions with enough cells"); return 1
    show = df.copy()
    for c in ("observed", "local_chance"):
        show[c] = (100 * show[c]).round(2)
    for c in ("above_chance_local", "ci_lo", "ci_hi"):
        show[c] = show[c].round(2)
    print(show.to_string(index=False))
    if a.out:
        a.out.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(a.out, index=False)
        print(f"\n  wrote {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
