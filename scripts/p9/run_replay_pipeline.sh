#!/usr/bin/env bash
set -euo pipefail

P9_HOME="/root/hs-aerots-p9-v5"
PX4_SOURCE="$P9_HOME/PX4-Autopilot"
PX4_COMMIT="82aa24adfca29321cfd1209e287eab6c2b16780e"
WINDOWS_ROOT="/mnt/d/UAV"
FIRST_REPLAY="$WINDOWS_ROOT/data/raw/uav_sead/ulg_files/2019-01-18/08_39_38.ulg"
BIN_ROOT="$P9_HOME/bin"
RUN_ROOT="$P9_HOME/runs"
WINDOWS_LOG_ROOT="$WINDOWS_ROOT/reports/p9/replay_logs"
MANIFEST="$WINDOWS_ROOT/reports/p9/run_manifest.tsv"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root under the configured WSL distribution." >&2
  exit 2
fi

mkdir -p "$P9_HOME" "$BIN_ROOT" "$RUN_ROOT" "$WINDOWS_LOG_ROOT"

# The Windows host may inject a loopback-only sandbox proxy. It is not
# reachable from WSL2 NAT and must not leak into Git/submodule downloads.
unset HTTP_PROXY HTTPS_PROXY ALL_PROXY http_proxy https_proxy all_proxy
unset GIT_HTTP_PROXY GIT_HTTPS_PROXY git_http_proxy git_https_proxy

if [[ ! -d "$PX4_SOURCE/.git" ]]; then
  if [[ -d "$WINDOWS_ROOT/third_party/PX4-Autopilot/.git" ]]; then
    mkdir -p "$PX4_SOURCE"
    cp -a "$WINDOWS_ROOT/third_party/PX4-Autopilot/.git" "$PX4_SOURCE/.git"
    git -C "$PX4_SOURCE" config core.autocrlf false
    git -C "$PX4_SOURCE" checkout-index --all --force
  else
    git clone --filter=blob:none --no-checkout https://github.com/PX4/PX4-Autopilot.git "$PX4_SOURCE"
  fi
fi

if [[ "$(git -C "$PX4_SOURCE" rev-parse HEAD)" != "$PX4_COMMIT" ]]; then
  git -C "$PX4_SOURCE" fetch --depth 1 origin "$PX4_COMMIT"
fi
git -C "$PX4_SOURCE" checkout --detach "$PX4_COMMIT"
git -C "$PX4_SOURCE" submodule sync --recursive
git -C "$PX4_SOURCE" submodule update --init --no-fetch \
  mavlink/include/mavlink/v2.0 \
  msg/tools/genmsg \
  msg/tools/gencpp \
  src/lib/matrix \
  src/lib/DriverFramework \
  src/lib/ecl \
  src/drivers/gps/devices

BUILD_PATCHES=(
  "$WINDOWS_ROOT/reports/p9/build_patches/no_gazebo_configure.patch"
  "$WINDOWS_ROOT/reports/p9/build_patches/gcc9_stringop_truncation.patch"
  "$WINDOWS_ROOT/reports/p9/build_patches/gcc9_packed_member.patch"
)
for build_patch in "${BUILD_PATCHES[@]}"; do
  if git -C "$PX4_SOURCE" apply --check "$build_patch" >/dev/null 2>&1; then
    git -C "$PX4_SOURCE" apply "$build_patch"
  elif git -C "$PX4_SOURCE" apply --reverse --check "$build_patch" >/dev/null 2>&1; then
    echo "Build patch already applied: $(basename "$build_patch")"
  else
    echo "Build patch does not match the fixed source checkout: $build_patch" >&2
    exit 3
  fi
done

cd "$PX4_SOURCE"
export replay="$FIRST_REPLAY"
make posix_sitl_default
mkdir -p "$BIN_ROOT/baseline"
cp -f build/posix_sitl_default_replay/px4 "$BIN_ROOT/baseline/px4"

MUTATIONS=(
  commander_nav_state_override
  ekf2_innovation_bias
  inav_local_z_freeze
  land_detector_state_inversion
)

cleanup_patch() {
  if [[ -n "${ACTIVE_PATCH:-}" ]] && git apply --reverse --check "$ACTIVE_PATCH" >/dev/null 2>&1; then
    git apply --reverse "$ACTIVE_PATCH"
  fi
}
trap cleanup_patch EXIT

for mutation in "${MUTATIONS[@]}"; do
  ACTIVE_PATCH="$WINDOWS_ROOT/reports/p9/mutation_patches/${mutation}.patch"
  git apply --check "$ACTIVE_PATCH"
  git apply "$ACTIVE_PATCH"
  make posix_sitl_default
  mkdir -p "$BIN_ROOT/$mutation"
  cp -f build/posix_sitl_default_replay/px4 "$BIN_ROOT/$mutation/px4"
  git apply --reverse "$ACTIVE_PATCH"
  ACTIVE_PATCH=""
done

printf 'run_id\tcondition\tmutation_id\tground_truth_module\treplay_log\treplay_mode\toutput_ulog\texit_code\n' > "$MANIFEST"

run_pair() {
  local mutation="$1"
  local module="$2"
  local mode="$3"
  local log_path="$4"
  local log_id="$5"
  local duration="$6"
  local condition binary run_id run_dir output_ulog exit_code fault_flag

  for condition in baseline fault; do
    if [[ "$condition" == "baseline" && "$mutation" != "ekf2_innovation_bias" ]]; then
      binary="$BIN_ROOT/baseline/px4"
    else
      binary="$BIN_ROOT/$mutation/px4"
    fi
    fault_flag=0
    [[ "$condition" == "fault" ]] && fault_flag=1
    run_id="${mutation}__${log_id}__${condition}"
    run_dir="$RUN_ROOT/$run_id"
    rm -rf "$run_dir"
    mkdir -p "$run_dir/rootfs"
    if [[ "$mutation" != "ekf2_innovation_bias" ]]; then
      cp "$WINDOWS_ROOT/reports/p9/replay_scripts/${mutation}.orb_publisher.rules" "$run_dir/rootfs/orb_publisher.rules"
    fi
    cp "$WINDOWS_ROOT/reports/p9/replay_scripts/${mutation}.rcS" "$run_dir/rcS"

    set +e
    (
      cd "$run_dir"
      HS_P9_EKF_FAULT="$fault_flag" \
        replay="$log_path" replay_mode="$mode" timeout --signal=INT --kill-after=10 "$duration" \
        "$binary" -d "$PX4_SOURCE" "$run_dir/rcS" > "$run_dir/console.log" 2>&1
    )
    exit_code=$?
    set -e

    output_ulog="$(find "$run_dir/rootfs/fs/microsd/log" -type f -name '*.ulg' -print 2>/dev/null | sort | tail -n 1)"
    if [[ -n "$output_ulog" && -f "$output_ulog" ]]; then
      cp -f "$output_ulog" "$WINDOWS_LOG_ROOT/${run_id}.ulg"
      output_ulog="$WINDOWS_LOG_ROOT/${run_id}.ulg"
    else
      output_ulog=""
    fi
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
      "$run_id" "$condition" "$mutation" "$module" "$log_path" "$mode" "$output_ulog" "$exit_code" >> "$MANIFEST"
  done
}

REPLAY_LOGS=(
  "$WINDOWS_ROOT/data/raw/uav_sead/ulg_files/2019-01-18/08_39_38.ulg|2019-01-18__08_39_38|85"
  "$WINDOWS_ROOT/data/raw/uav_sead/ulg_files/2019-01-25/17_38_05.ulg|2019-01-25__17_38_05|110"
  "$WINDOWS_ROOT/data/raw/uav_sead/ulg_files/2019-03-06/08_02_26.ulg|2019-03-06__08_02_26|115"
)

for spec in "${REPLAY_LOGS[@]}"; do
  IFS='|' read -r log_path log_id duration <<< "$spec"
  run_pair commander_nav_state_override src/modules/commander generic "$log_path" "$log_id" "$duration"
  run_pair ekf2_innovation_bias src/modules/ekf2 ekf2 "$log_path" "$log_id" "$duration"
  run_pair inav_local_z_freeze src/modules/position_estimator_inav generic "$log_path" "$log_id" "$duration"
  run_pair land_detector_state_inversion src/modules/land_detector generic "$log_path" "$log_id" "$duration"
done

echo "Replay runs completed. Manifest: $MANIFEST"
