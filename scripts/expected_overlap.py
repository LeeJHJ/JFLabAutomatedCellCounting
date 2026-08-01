#!/usr/bin/env python3
"""expected_overlap.py -- observed vs EXPECTED colocalization under a fitted null.

WHY. The field's chance level is independence: if tagging and activity were unrelated,
P(activity+ | tagged+) would equal P(activity+). `overlap_above_chance` is exactly that
observed/expected ratio. The trouble is that independence is violated by things that
have nothing to do with biology, so the ratio sits above 1 even in regions that should
be quiet. Measured on M3 Hipp2 s3 (2026-07-31):

  * technical channel coupling -- activity+ rate rises with tagged-marker INTENSITY
    even among tagged-NEGATIVE cells (1.34x whole-cell, 2.23x nuclear, 1.10x ring-only).
    It tracks shared pixels: the activity marker is measured on the nucleus, so a
    tagged measure that also includes the nucleus manufactures colocalization.
  * spatial structure -- tagged cells sit in neighbourhoods already richer in activity
    (14.7% vs 11.4% region-wide).
  * nucleus size was tested and RULED OUT (2.39 -> 2.37 stratified).

Rather than pick a better comparison SET (see local_chance.py, which picks nearby
cells), this asks what activity+ probability each tagged cell WOULD have had given
everything measurable about it, by fitting that relationship on tagged-NEGATIVE cells:

    logit P(activity+) = b0 + b1*log1p(tagged intensity)
                            + b2*log1p(local density)
                            + b3*log1p(nucleus area)   [+ per-section offsets]

then evaluating it at each tagged+ cell's own covariates:

    above_chance_fitted = observed activity+ among tagged+  /  SUM of expected

Every confound above enters as a covariate, so it is PREDICTED rather than credited to
biology. If the covariates explain everything the ratio goes to 1.0, which is the
correct answer.

THE ASSUMPTION, STATED. Tagged+ cells sit above the tagged threshold, so the fit is
EXTRAPOLATED past the range it was trained on. That is checkable and this module checks
it: `--validate` fits on the lower 90% of negatives and reports predicted vs actual on
the top 10% (the part nearest the cut). A large miss there means the extrapolation is
not trustworthy and the number should not be used.

THIS DOES NOT DECIDE ANYTHING. It reports observed, expected, and the ratio next to the
naive ratio, so the operator can compare them against what the image shows. Nothing is
switched automatically (CLAUDE.md evidence hierarchy: SEEN outranks a fitted model).

Usage:
    python3 expected_overlap.py --project "<dir>" --regions CA1,CA3,STR
    python3 expected_overlap.py --project "<dir>" --validate
    python3 expected_overlap.py --self-test
"""

from __future__ import annotations

import argparse
import glob
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.spatial import cKDTree

sys.path.insert(0, str(Path(__file__).resolve().parent))

import cockpit_regions as creg  # noqa: E402  ontology + config -- do not fork
import cockpit_animal as ca     # noqa: E402  D-1 role resolution -- do not fork
import local_chance as lc       # noqa: E402  per-cell loader / flags -- do not fork

DENSITY_K = 20          # neighbours used to estimate local cell density
DEFAULT_BOOTSTRAP = 500


# ---------------------------------------------------------------------------
# Logistic regression (scipy only -- sklearn/statsmodels are not in the braian env,
# and adding one to a deliberately isolated env for ~30 lines is not a good trade)
# ---------------------------------------------------------------------------
def _fit_logistic(X: np.ndarray, y: np.ndarray, l2: float = 1e-4) -> np.ndarray:
    """MLE for logistic regression with a light ridge. X excludes the intercept."""
    Xd = np.hstack([np.ones((len(X), 1)), X])

    def nll(b):
        z = Xd @ b
        # log(1+exp(z)) computed stably
        ll = np.sum(y * z - np.logaddexp(0.0, z))
        return -ll + l2 * np.sum(b[1:] ** 2)

    def grad(b):
        p = 1.0 / (1.0 + np.exp(-(Xd @ b)))
        g = -(Xd.T @ (y - p))
        g[1:] += 2 * l2 * b[1:]
        return g

    res = minimize(nll, np.zeros(Xd.shape[1]), jac=grad, method="L-BFGS-B")
    return res.x


def _predict(beta: np.ndarray, X: np.ndarray) -> np.ndarray:
    Xd = np.hstack([np.ones((len(X), 1)), X])
    return 1.0 / (1.0 + np.exp(-(Xd @ beta)))


def _design(d: pd.DataFrame, tagged_col: str, mu: np.ndarray | None = None,
            sd: np.ndarray | None = None):
    """Covariate matrix: log1p of tagged intensity, local density, nucleus area.

    log1p because all three are right-skewed and non-negative; standardised so the
    optimiser is well conditioned and the coefficients are comparable.
    """
    cols = [np.log1p(np.clip(d[tagged_col].values, 0, None)),
            np.log1p(d["_local_density"].values),
            np.log1p(np.clip(d["nucleus_area_um2"].values, 0, None))]
    X = np.column_stack(cols)
    if mu is None:
        mu, sd = X.mean(axis=0), X.std(axis=0)
        sd[sd == 0] = 1.0
    return (X - mu) / sd, mu, sd


def add_local_density(d: pd.DataFrame, k: int = DENSITY_K) -> pd.DataFrame:
    """Local density = 1 / mean distance to the k nearest cells, per section."""
    out = []
    for _s, sub in d.groupby("section"):
        sub = sub.copy()
        xy = sub[["centroid_x_px", "centroid_y_px"]].values
        if len(sub) <= k:
            sub["_local_density"] = 0.0
        else:
            dist, _ = cKDTree(xy).query(xy, k=k + 1)
            md = dist[:, 1:].mean(axis=1)
            sub["_local_density"] = np.where(md > 0, 1.0 / md, 0.0)
        out.append(sub)
    return pd.concat(out)


# ---------------------------------------------------------------------------
def fitted_expectation(d: pd.DataFrame, tagged_col: str) -> dict:
    """Observed vs fitted-expected activity+ among tagged+ cells."""
    neg, pos = d[~d["tagged"]], d[d["tagged"]]
    if len(pos) == 0 or len(neg) < 200:
        return {"observed": np.nan, "expected": np.nan, "ratio": np.nan, "n_tagged": len(pos)}
    Xn, mu, sd = _design(neg, tagged_col)
    beta = _fit_logistic(Xn, neg["activity"].values.astype(float))
    Xp, _, _ = _design(pos, tagged_col, mu, sd)
    exp_p = _predict(beta, Xp)
    obs = float(pos["activity"].mean())
    exp = float(exp_p.mean())
    return {"observed": obs, "expected": exp, "ratio": obs / exp if exp > 0 else np.nan,
            "n_tagged": len(pos), "beta": beta}


def validate_extrapolation(d: pd.DataFrame, tagged_col: str, holdout_frac: float = 0.10) -> dict:
    """Fit on the lower (1-f) of tagged-NEGATIVE cells by tagged intensity, test on the
    top f -- the part closest to the threshold, i.e. most like the cells the model will
    actually be extrapolated to. A large miss here means the extrapolation is unsafe."""
    neg = d[~d["tagged"]].copy()
    if len(neg) < 1000:
        return {}
    cut = neg[tagged_col].quantile(1 - holdout_frac)
    lo, hi = neg[neg[tagged_col] <= cut], neg[neg[tagged_col] > cut]
    if len(hi) < 50:
        return {}
    Xl, mu, sd = _design(lo, tagged_col)
    beta = _fit_logistic(Xl, lo["activity"].values.astype(float))
    Xh, _, _ = _design(hi, tagged_col, mu, sd)
    pred, actual = float(_predict(beta, Xh).mean()), float(hi["activity"].mean())
    return {"holdout_n": len(hi), "predicted": pred, "actual": actual,
            "pred_over_actual": pred / actual if actual > 0 else np.nan}


def analyse(project_dir: Path, regions: list[str] | None = None,
            n_boot: int = DEFAULT_BOOTSTRAP, seed: int = 0,
            validate: bool = False) -> pd.DataFrame:
    config = creg.load_pipeline_config(Path(project_dir))
    roles = ca.resolve_roles(config)
    if not roles.tagged or not roles.activity:
        raise SystemExit(f"needs both roles; got tagged={roles.tagged} activity={roles.activity}")
    tagged_col = f"{roles.tagged}_bgsub"

    d = lc._flags(lc.load_percell(project_dir), roles.tagged, roles.activity)
    d[tagged_col] = pd.to_numeric(d[tagged_col], errors="coerce")
    d = d.dropna(subset=[tagged_col, "nucleus_area_um2"])
    d = add_local_density(d)

    ontology = creg.load_ontology(Path(project_dir))
    present = set(d["region_label"].dropna().unique())
    targets = regions or ["__ALL__"]
    rng = np.random.default_rng(seed)
    rows = []
    for region in targets:
        sub = d if region == "__ALL__" else d[
            d["region_label"].isin(ontology.descendants_or_self(region) & present)]
        if len(sub) < 500:
            if region != "__ALL__":
                print(f"  NOTE: '{region}' has too few cells ({len(sub)})")
            continue
        res = fitted_expectation(sub, tagged_col)
        naive = (sub[sub["tagged"]]["activity"].mean() / sub["activity"].mean()
                 if sub["activity"].mean() > 0 else np.nan)
        boot = []
        pos_idx = np.where(sub["tagged"].values)[0]
        for _ in range(n_boot):
            take = rng.integers(0, len(pos_idx), len(pos_idx))
            o = sub.iloc[pos_idx[take]]["activity"].mean()
            boot.append(o / res["expected"] if res["expected"] else np.nan)
        boot = [b for b in boot if np.isfinite(b)]
        row = {"region": region, "n_cells": len(sub), "n_tagged": res["n_tagged"],
               "observed": res["observed"], "expected": res["expected"],
               "above_chance_fitted": res["ratio"], "above_chance_naive": naive,
               "ci_lo": np.percentile(boot, 2.5) if boot else np.nan,
               "ci_hi": np.percentile(boot, 97.5) if boot else np.nan}
        if validate:
            row.update({f"val_{k}": v for k, v in
                        validate_extrapolation(sub, tagged_col).items()})
        rows.append(row)
    return pd.DataFrame(rows)


def _self_test() -> None:
    print("Running --self-test (synthetic cells, no project needed)...")
    rng = np.random.default_rng(3)
    check = lambda c, m: print(f"  {'ok  ' if c else 'FAIL'}  {m}") or (c or sys.exit(1))

    def make(n, coupling, real_effect):
        """Tagged intensity drives activity TECHNICALLY (coupling). Tagging above the
        cut adds `real_effect` on top. A perfect null model recovers exactly
        1 + real_effect."""
        inten = rng.lognormal(5.0, 0.8, n)
        area = rng.normal(45, 10, n).clip(5, None)
        dens = rng.normal(1.0, 0.15, n).clip(0.2, None)
        z = -2.2 + coupling * (np.log1p(inten) - 5.0)
        p = 1 / (1 + np.exp(-z))
        cut = np.quantile(inten, 0.93)
        tagged = inten > cut
        p = np.where(tagged, np.clip(p * (1 + real_effect), 0, 0.99), p)
        return pd.DataFrame({
            "tagged": tagged, "activity": rng.random(n) < p,
            "T_bgsub": inten, "nucleus_area_um2": area, "_local_density": dens,
            "section": "s1"})

    # (a) coupling but NO real effect -> naive inflated, fitted ~1.0
    d = make(60000, coupling=1.1, real_effect=0.0)
    naive = d[d.tagged].activity.mean() / d.activity.mean()
    r = fitted_expectation(d, "T_bgsub")
    check(naive > 1.4, f"naive ratio inflated by coupling alone ({naive:.2f}x)")
    check(abs(r["ratio"] - 1.0) < 0.15, f"fitted null returns ~1.0x ({r['ratio']:.2f}x)")

    # (b) a real 2x effect on top of the same coupling must survive
    d2 = make(60000, coupling=1.1, real_effect=1.0)
    r2 = fitted_expectation(d2, "T_bgsub")
    check(1.6 < r2["ratio"] < 2.4, f"genuine 2x effect recovered ({r2['ratio']:.2f}x)")

    # (c) extrapolation check reports something sane on a well-specified model
    v = validate_extrapolation(d, "T_bgsub")
    check(0.75 < v["pred_over_actual"] < 1.3,
          f"holdout extrapolation within 25% ({v['pred_over_actual']:.2f})")

    print("\nself-test PASSED: the fitted null removes a pure intensity-coupling "
          "confound (naive inflated, fitted ~1.0x), still recovers a genuine effect, "
          "and the holdout check validates the extrapolation.")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter,
                                epilog=__doc__)
    p.add_argument("--project", type=Path, default=None)
    p.add_argument("--regions", default=None, help="comma-separated acronyms (default: whole section)")
    p.add_argument("--bootstrap", type=int, default=DEFAULT_BOOTSTRAP)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--validate", action="store_true",
                   help="also report the held-out extrapolation check")
    p.add_argument("--out", type=Path, default=None)
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
    df = analyse(a.project, regions, n_boot=a.bootstrap, seed=a.seed, validate=a.validate)
    if df.empty:
        print("no regions with enough cells"); return 1
    show = df.copy()
    for c in ("observed", "expected"):
        show[c] = (100 * show[c]).round(2)
    for c in [c for c in show.columns if c.startswith(("above_chance", "ci_", "val_pred"))]:
        show[c] = show[c].round(2)
    print(show.to_string(index=False))
    print()
    print("  above_chance_fitted vs above_chance_naive: the gap is what the covariates")
    print("  (marker intensity, local density, nucleus area) explain WITHOUT biology.")
    print("  Neither number decides anything -- check them against the image.")
    if a.out:
        a.out.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(a.out, index=False)
        print(f"\n  wrote {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
