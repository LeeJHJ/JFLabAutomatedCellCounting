# Vendored atlas ontology

`allen_mouse_10um_java-Ontology.json` — the Allen Mouse Brain Common Coordinate
Framework v3 structure graph, as ABBA writes it into every QuPath project.

**Why a copy lives here.** `docs/build_acronym_lookup.py` builds a general-purpose
acronym lookup that must not depend on any particular experiment. Every QuPath
project in this repo ships its own copy of this file, and all of them are
**byte-identical** (md5 `70ccd19dda9d9324aa97b6d62346a72a`, verified across all 11
copies including `_archive/` on 2026-08-03). So this is the atlas, not a project's
view of it — pointing the builder at a neutral copy makes that obvious and keeps a
project rename or archive from breaking the build.

Verify the copies still agree:

```bash
find . -name "allen_mouse_10um_java-Ontology.json" -print0 | xargs -0 md5sum | sort -u -k1,1
```

More than one hash means a project registered against a different atlas build, and
the difference needs explaining before anything is pooled across those projects.

## What is in it

1,327 structures, 1,038 of them leaves, nesting up to 10 deep. Each node carries
`acronym`, `name`, numeric Allen `id`, `color_hex_triplet`, and `st_level`.

## It is a superset of BrainGlobe's `allen_mouse`

BrainGlobe's `allen_mouse_10um_v1.2` (`~/.brainglobe/.../structures.json`) lists
**840** structures — a strict subset. Where the two overlap they agree exactly:
0 disagreements in id, name, or colour across all 840.

The 487 structures BrainGlobe omits are the finer subdivisions, mostly at depth 7–9:
cortical layers (`ACA1`, `ACA2/3`, `ACA6a`), hippocampal layers (`CA1sp`, `CA1slm`),
hypothalamic and cerebellar parts (`AHNa`, `ANcr1gr`).

Consequence, and the reason the lookup page flags it per row: an acronym can be a
valid CCFv3 structure that ABBA and QuPath resolve happily, and still fail to
resolve in `brainglobe-atlasapi` or brainrender. That bites the `render3d` stage,
not the region readouts.

## Not the annotation volume

This is the structure graph only — names, hierarchy, colours. The registered label
volume lives with the atlas ABBA downloads, not here.
