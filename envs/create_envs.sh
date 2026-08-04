#!/usr/bin/env bash
# create_envs.sh -- rebuild the three conda environments on a new machine.
#
# The three envs are deliberately ISOLATED and must never be merged: brainrender
# is fragile with vedo/VTK/allensdk and will break `braian` if co-installed.
#
# CPU-ONLY. Do not substitute GPU/CUDA builds of anything here -- the lab boxes
# have Intel iGPUs, and every stage (detection, DeepSlice, elastix) is CPU-bound
# by design. A CUDA build will either fail to import or silently pick a different
# numerical path.
#
# Usage:
#     bash envs/create_envs.sh            # all three
#     bash envs/create_envs.sh braian     # just one
#
# Pins come from `pip freeze` on the reference machine (Ubuntu 26.04, x86_64,
# 2026-08-04). They are exact by intent: this pipeline's numbers depend on
# library versions, and "latest" is not a reproducible target.

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# env name -> python version
declare -A PYVER=(
  [braian]=3.11
  [brainrender]=3.11
  [deepslice]=3.10
)

targets=("$@")
if [ ${#targets[@]} -eq 0 ]; then
  targets=(braian brainrender deepslice)
fi

if ! command -v conda >/dev/null 2>&1; then
  echo "FATAL: conda not on PATH. Install Miniforge first -- see SECTION_PIPELINE_SETUP.md" >&2
  exit 1
fi

for env in "${targets[@]}"; do
  if [ -z "${PYVER[$env]:-}" ]; then
    echo "FATAL: unknown env '$env' (expected: braian, brainrender, deepslice)" >&2
    exit 1
  fi
  req="$HERE/requirements-$env.txt"
  if [ ! -f "$req" ]; then
    echo "FATAL: $req missing" >&2
    exit 1
  fi

  echo "=== $env (python ${PYVER[$env]}) ==="
  if conda env list | grep -qE "^${env}\s"; then
    echo "  already exists -- skipping create. Delete it first to rebuild:"
    echo "      conda env remove -n $env"
  else
    conda create -y -n "$env" "python=${PYVER[$env]}"
  fi
  echo "  installing $(wc -l < "$req") pinned packages..."
  conda run -n "$env" python -m pip install -r "$req"
  echo "  $env done."
done

cat <<'EOF'

All requested environments built. Verify the install with:

    ~/miniforge3/envs/braian/bin/python scripts/smoke_test.py

Expect "24/24 checks passed". That is the install-verification gate -- it builds a
throwaway project from nothing and runs the chain against it, so a PASS means the
pipeline works independent of whatever state the workspace happens to be in.
EOF
