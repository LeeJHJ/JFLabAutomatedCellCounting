"""k-sweep (k=2..3) of the robust TdT+ cut, section-level + LA/BA regions, from
the exported per-cell TSVs. Reproduces 02_detect_classify's cut exactly:
  classifiable = non-Excluded detections; threshold = median + k*1.4826*MAD(bgsub);
  positive iff bgsub >= threshold.  (verified vs JSON: k=3 -> ~636 on s1)
Prints a k-sweep table + an LA/BA regional table and writes a figure.
"""
import csv, glob, os, numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

PROJ = "/home/jflab/Analysis/wBA/wBA1-2_2-1-tdt-only 072026 project"
KS = [2.0, 2.25, 2.5, 2.75, 3.0]
KLO, KMID, KHI = 3.0, 2.5, 2.0   # higher k = stricter = fewer positives
# LA/BA amygdala nuclei (NOT 'LAT' = thalamus). Grouped to major nuclei.
GROUPS = {"LA": {"LA"}, "BLA": {"BLA","BLAa","BLAp","BLAv"}, "BMA": {"BMA","BMAa","BMAp"}}

def load(f):
    rows = list(csv.DictReader(open(f), delimiter="\t"))
    cls = np.array([r["class"] for r in rows])
    bg  = np.array([float(r["TdT_bgsub"]) if r.get("TdT_bgsub","").strip() not in ("","nan") else np.nan for r in rows])
    acr = np.array([r["region_label"].split(": ")[-1] if ": " in r["region_label"] else r["region_label"] for r in rows])
    return cls, bg, acr

def thresholds(bg_classifiable):
    med = np.median(bg_classifiable); mad = np.median(np.abs(bg_classifiable - med))
    return {k: med + k * 1.4826 * mad for k in KS}, med, 1.4826*mad

secs = sorted(glob.glob(f"{PROJ}/results/*__percell_export.tsv"))
slabels = [os.path.basename(s).split(" - ")[-1].split("__")[0] for s in secs]

print("="*84)
print("SECTION-LEVEL k-SWEEP  (TdT+ count | % of classifiable)")
print("="*84)
print(f"{'section':10} {'median':>8} {'robSD':>8} " + " ".join(f'k={k:<4}' for k in KS))
sec_data = {}
for f, sl in zip(secs, slabels):
    cls, bg, acr = load(f)
    keep = (cls != "Excluded") & ~np.isnan(bg)
    bgc = bg[keep]
    thr, med, rsd = thresholds(bgc)
    counts = {k: int((bgc >= thr[k]).sum()) for k in KS}
    pct = {k: 100*counts[k]/len(bgc) for k in KS}
    sec_data[sl] = dict(cls=cls, bg=bg, acr=acr, keep=keep, thr=thr)
    print(f"{sl:10} {med:8.1f} {rsd:8.1f} " + " ".join(f'{counts[k]:>5}' for k in KS))
    print(f"{'':10} {'':8} {'(%)':>8} " + " ".join(f'{pct[k]:>5.1f}' for k in KS))
# sanity vs JSON (s1 @ k=3 should be ~636)
s1 = slabels[0]; print(f"\n[check] {s1} threshold@k=3.0 = {sec_data[s1]['thr'][3.0]:.1f}  (classifier JSON = 636.08)")

print("\n" + "="*84)
print("LA/BA REGIONAL COUNTS per slice  (DAPI | TdT+ at k=3.0 / 2.5 / 2.0), L+R summed")
print("="*84)
print(f"{'region':6} {'slice':10} {'DAPI':>7} {'TdT+@k3':>8} {'TdT+@k2.5':>10} {'TdT+@k2':>8} {'%@k2.5':>7}")
reg_counts = {g: {sl: {} for sl in slabels} for g in GROUPS}
for g, acrs in GROUPS.items():
    for sl in slabels:
        d = sec_data[sl]; inreg = np.isin(d["acr"], list(acrs)) & d["keep"]
        dapi = int(inreg.sum()); bgr = d["bg"][inreg]
        tk = {k: int((bgr >= d["thr"][k]).sum()) for k in (KLO,KMID,KHI)}
        reg_counts[g][sl] = dict(dapi=dapi, **{f"k{k}": tk[k] for k in (KLO,KMID,KHI)})
        pct = 100*tk[KMID]/dapi if dapi else 0
        print(f"{g:6} {sl:10} {dapi:>7} {tk[KLO]:>8} {tk[KMID]:>10} {tk[KHI]:>8} {pct:>6.1f}%")

# ---- figure: TdT+ counts (panel A) + TdT+ % of DAPI (panel B), LA/BA x slice ----
fig, (axA, axB) = plt.subplots(1, 2, figsize=(13.5, 5.2))
cols = {"LA": "#d1495b", "BLA": "#2a9d8f", "BMA": "#e9a13b"}
x = np.arange(len(slabels)); w = 0.26
for i, g in enumerate(GROUPS):
    mid = np.array([reg_counts[g][sl][f"k{KMID}"] for sl in slabels], float)
    lo  = np.array([reg_counts[g][sl][f"k{KLO}"]  for sl in slabels], float)  # strict (fewer)
    hi  = np.array([reg_counts[g][sl][f"k{KHI}"]  for sl in slabels], float)  # lenient (more)
    dap = np.array([reg_counts[g][sl]["dapi"] for sl in slabels], float)
    off = (i-1)*w
    axA.bar(x+off, mid, w, color=cols[g], label=g,
            yerr=[mid-lo, hi-mid], capsize=3, error_kw=dict(lw=1, ecolor="#333"))
    pmid, plo, phi = 100*mid/np.where(dap==0,1,dap), 100*lo/np.where(dap==0,1,dap), 100*hi/np.where(dap==0,1,dap)
    axB.bar(x+off, pmid, w, color=cols[g], label=g,
            yerr=[pmid-plo, phi-pmid], capsize=3, error_kw=dict(lw=1, ecolor="#333"))
for ax, ttl, yl in [(axA,"TdT+ cell count (L+R)","TdT+ cells"),
                    (axB,"TdT+ as % of DAPI (reactivation fraction)","% TdT+ / DAPI")]:
    ax.set_title(ttl, fontsize=11, weight="bold"); ax.set_ylabel(yl)
    ax.set_xticks(x); ax.set_xticklabels(slabels, rotation=20, ha="right", fontsize=8)
    ax.grid(axis="y", alpha=0.25); ax.legend(title="nucleus", fontsize=9)
fig.suptitle("wBA1-2_2-1 TdT-only — LA/BA per-slice readout (bar = k2.5, whiskers = k3↔k2)",
             fontsize=12, weight="bold")
fig.tight_layout(rect=[0,0,1,0.95])
OUT = f"{PROJ}/qc_LA-BA_TdT_ksweep.png"
fig.savefig(OUT, dpi=130, bbox_inches="tight")
print(f"\nfigure -> {OUT}")
