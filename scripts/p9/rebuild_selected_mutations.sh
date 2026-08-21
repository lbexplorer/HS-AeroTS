#!/usr/bin/env bash
set -euo pipefail

P9_HOME="/root/hs-aerots-p9-v5"
PX4_SOURCE="$P9_HOME/PX4-Autopilot"
BIN_ROOT="$P9_HOME/bin"
WINDOWS_ROOT="/mnt/d/UAV"
FIRST_REPLAY="$WINDOWS_ROOT/data/raw/uav_sead/ulg_files/2019-01-18/08_39_38.ulg"
SELECTION="${1:-ekf2_innovation_bias,land_detector_state_inversion}"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root under Ubuntu-20.04." >&2
  exit 2
fi

cd "$PX4_SOURCE"
export replay="$FIRST_REPLAY"
cleanup_patch() {
  if [[ -n "${ACTIVE_PATCH:-}" ]] && git apply --reverse --check "$ACTIVE_PATCH" >/dev/null 2>&1; then
    git apply --reverse "$ACTIVE_PATCH"
  fi
}
trap cleanup_patch EXIT

IFS=',' read -r -a MUTATIONS <<< "$SELECTION"
for mutation in "${MUTATIONS[@]}"; do
  ACTIVE_PATCH="$WINDOWS_ROOT/reports/p9/mutation_patches/${mutation}.patch"
  git apply --check "$ACTIVE_PATCH"
  git apply "$ACTIVE_PATCH"
  make posix_sitl_default
  mkdir -p "$BIN_ROOT/$mutation"
  cp -f build/posix_sitl_default_replay/px4 "$BIN_ROOT/$mutation/px4"
  git apply --reverse "$ACTIVE_PATCH"
  ACTIVE_PATCH=""
  echo "rebuilt $mutation"
done
