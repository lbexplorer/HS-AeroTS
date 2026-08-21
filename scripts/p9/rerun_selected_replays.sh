#!/usr/bin/env bash
set -euo pipefail

# Re-run selected replay pairs without rebuilding PX4.  This is intended for
# publisher-rule or replay-mode corrections after the fixed binaries exist.
P9_HOME="/root/hs-aerots-p9-v5"
PX4_SOURCE="$P9_HOME/PX4-Autopilot"
BIN_ROOT="$P9_HOME/bin"
RUN_ROOT="$P9_HOME/runs"
WINDOWS_ROOT="/mnt/d/UAV"
WINDOWS_LOG_ROOT="$WINDOWS_ROOT/reports/p9/replay_logs"
MANIFEST="$WINDOWS_ROOT/reports/p9/run_manifest.tsv"
SELECTION="${1:-ekf2_innovation_bias,land_detector_state_inversion}"
LOG_LIMIT="${2:-3}"
CONDITION_SELECTION="${3:-baseline,fault}"
LOG_START="${4:-1}"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root under Ubuntu-20.04." >&2
  exit 2
fi
if [[ ! -x "$BIN_ROOT/baseline/px4" ]]; then
  echo "Baseline replay binary is missing; run run_replay_pipeline.sh first." >&2
  exit 3
fi

update_manifest() {
  local run_id="$1" condition="$2" mutation="$3" module="$4"
  local log_path="$5" mode="$6" output_ulog="$7" exit_code="$8"
  local temporary="${MANIFEST}.tmp"
  awk -F '\t' -v OFS='\t' -v id="$run_id" -v cond="$condition" \
    -v mut="$mutation" -v mod="$module" -v input="$log_path" \
    -v replay_mode="$mode" -v output="$output_ulog" -v code="$exit_code" '
      NR == 1 { print; next }
      $1 == id { print id, cond, mut, mod, input, replay_mode, output, code; found=1; next }
      { print }
      END { if (!found) print id, cond, mut, mod, input, replay_mode, output, code }
    ' "$MANIFEST" > "$temporary"
  mv -f "$temporary" "$MANIFEST"
}

run_pair() {
  local mutation="$1" module="$2" mode="$3" log_path="$4" log_id="$5" duration="$6"
  local condition binary run_id run_dir output_ulog exit_code fault_flag
  IFS=',' read -r -a CONDITIONS <<< "$CONDITION_SELECTION"
  for condition in "${CONDITIONS[@]}"; do
    binary="$BIN_ROOT/baseline/px4"
    if [[ "$condition" == "fault" || "$mutation" == "ekf2_innovation_bias" ]]; then
      binary="$BIN_ROOT/$mutation/px4"
    fi
    fault_flag=0
    [[ "$condition" == "fault" ]] && fault_flag=1
    run_id="${mutation}__${log_id}__${condition}"
    run_dir="$RUN_ROOT/$run_id"
    rm -rf "$run_dir"
    mkdir -p "$run_dir/rootfs"
    # Legacy source logs lack ekf2_timestamps, so generic replay keeps the
    # recorded EKF output while the fault binary adds its controlled bias.
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
    update_manifest "$run_id" "$condition" "$mutation" "$module" "$log_path" "$mode" "$output_ulog" "$exit_code"
    echo "$run_id exit=$exit_code output=$output_ulog"
  done
}

REPLAY_LOGS=(
  "$WINDOWS_ROOT/data/raw/uav_sead/ulg_files/2019-01-18/08_39_38.ulg|2019-01-18__08_39_38|85"
  "$WINDOWS_ROOT/data/raw/uav_sead/ulg_files/2019-01-25/17_38_05.ulg|2019-01-25__17_38_05|110"
  "$WINDOWS_ROOT/data/raw/uav_sead/ulg_files/2019-03-06/08_02_26.ulg|2019-03-06__08_02_26|115"
)

IFS=',' read -r -a MUTATIONS <<< "$SELECTION"
log_index=0
for spec in "${REPLAY_LOGS[@]}"; do
  ((log_index += 1))
  ((log_index > LOG_LIMIT)) && break
  ((log_index < LOG_START)) && continue
  IFS='|' read -r log_path log_id duration <<< "$spec"
  for mutation in "${MUTATIONS[@]}"; do
    case "$mutation" in
      commander_nav_state_override)
        run_pair "$mutation" src/modules/commander generic "$log_path" "$log_id" "$duration" ;;
      ekf2_innovation_bias)
        run_pair "$mutation" src/modules/ekf2 generic "$log_path" "$log_id" "$duration" ;;
      inav_local_z_freeze)
        run_pair "$mutation" src/modules/position_estimator_inav generic "$log_path" "$log_id" "$duration" ;;
      land_detector_state_inversion)
        run_pair "$mutation" src/modules/land_detector generic "$log_path" "$log_id" "$duration" ;;
      *) echo "Unknown mutation: $mutation" >&2; exit 4 ;;
    esac
  done
done

echo "Selected replay runs completed. Manifest: $MANIFEST"
