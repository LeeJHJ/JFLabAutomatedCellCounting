# _archive/

Cold storage for completed-animal and raw-acquisition microscopy data that the
active pipeline no longer reads. Moved here to keep the working tree uncluttered —
**not** deleted, because raw acquisition data is irreplaceable.

Contents are gitignored by file extension (`.czi`, `.tiff`, etc.); this README is
the only tracked file. Nothing here is referenced by any QuPath `server.json` or
ABBA state (verified before moving on 2026-07-23).

## raw-acquisition/

| File | Why archived |
|------|--------------|
| `-001-07.czi` (23 GB) | Raw wBA1-3 acquisition; superseded by `-001-07_processed.czi` (still active in `Automated Cell Counting/wBA Sungmo/`), which is what the pipeline consumes. |
| `M3 Hippocampus 20x 062026.czi` (8.4 GB) | Raw M3 hippocampus acquisition; M3 is the v1.0-shipped completed animal. |
| `M3 Hippocampus - part 1 scene 1_s1.ome.tiff` (1 GB) | Early single-scene M3 MIP export, superseded by the project MIPs. |

## Deleted (not archived)

- `wBA1-3_Batch2-2_071726_…6 Scenes_Merged.ome.tiff` (31.6 GB) — deleted 2026-07-23;
  STATE.md declared it unusable (scenes fused, Z not projected).

## Convention

When an animal's milestone ships, move its raw `.czi`/`.lif` and any superseded
intermediate MIPs here. Leave active-project directories and processed files that
QuPath entries point to in place. Verify `grep -rl <filename> --include='*.json'
--include='*.qpproj' --include='*.abba' .` returns nothing before moving.
