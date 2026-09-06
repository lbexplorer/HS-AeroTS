#!/usr/bin/env bash
# Identical inputs/binaries/mutations; only avoid high-latency /mnt/d seeks.
set -euo pipefail
SOURCE_HOME=/root/hs-aerots-p9-v5
TASK_HOME=/root/hs-aerots-p9-native-20260906
WIN=/mnt/d/UAV
OUT="$WIN/reports/p9/stage1_reassessment/native_replay"
mkdir -p "$TASK_HOME/inputs" "$TASK_HOME/runs" "$OUT/logs" "$OUT/consoles" "$OUT/rows"
run_one() {
  local mutation="$1" module="$2" log_id="$3" input="$4" duration="$5" condition="$6"
  local run_id="${mutation}__${log_id}__${condition}"
  local run_dir="$TASK_HOME/runs/$run_id"
  # Never delete or overwrite prior experimental runs.
  if [[ -e "$run_dir" ]]; then echo "Run exists: $run_dir" >&2; return 2; fi
  mkdir -p "$run_dir/rootfs"
  local binary="$SOURCE_HOME/bin/baseline/px4"
  if [[ "$condition" == fault || "$mutation" == ekf2_innovation_bias ]]; then binary="$SOURCE_HOME/bin/$mutation/px4"; fi
  if [[ "$mutation" != ekf2_innovation_bias ]]; then
    cp "$WIN/reports/p9/replay_scripts/$mutation.orb_publisher.rules" "$run_dir/rootfs/orb_publisher.rules"
  fi
  cp "$WIN/reports/p9/replay_scripts/$mutation.rcS" "$run_dir/rcS"
  local fault_flag=0
  [[ "$condition" == fault ]] && fault_flag=1
  local code=0
  (cd "$run_dir"; HS_P9_EKF_FAULT="$fault_flag" replay="$input" replay_mode=generic \
    timeout --signal=INT --kill-after=10 "$duration" "$binary" -d "$SOURCE_HOME/PX4-Autopilot" "$run_dir/rcS" >console.log 2>&1) || code=$?
  local output
  output=$(find "$run_dir/rootfs/fs/microsd/log" -type f -name '*.ulg' | sort | tail -1)
  [[ -n "$output" ]] || return 3
  cp "$output" "$OUT/logs/$run_id.ulg"
  cp "$run_dir/console.log" "$OUT/consoles/$run_id.log"
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$run_id" "$condition" "$mutation" "$module" "$input" generic "$OUT/logs/$run_id.ulg" "$code" > "$OUT/rows/$run_id.tsv"
  echo "Completed $run_id exit=$code replay_done=$(grep -c 'Replay done' "$run_dir/console.log" || true)"
}
for spec in '2019-01-18|08_39_38|85' '2019-01-25|17_38_05|110' '2019-03-06|08_02_26|115'; do
  IFS='|' read -r date clock duration <<< "$spec"
  log_id="${date}__${clock}"
  input="$TASK_HOME/inputs/$log_id.ulg"
  if [[ ! -e "$input" ]]; then cp "$WIN/data/raw/uav_sead/ulg_files/$date/$clock.ulg" "$input"; fi
  cmp "$WIN/data/raw/uav_sead/ulg_files/$date/$clock.ulg" "$input"
  if [[ "${1:-pilot}" == pilot ]]; then
    run_one commander_nav_state_override src/modules/commander "$log_id" "$input" "$duration" baseline
    break
  fi
  pids=()
  for pair in 'commander_nav_state_override|src/modules/commander' 'ekf2_innovation_bias|src/modules/ekf2' 'inav_local_z_freeze|src/modules/position_estimator_inav' 'land_detector_state_inversion|src/modules/land_detector'; do
    IFS='|' read -r mutation module <<< "$pair"
    (
      for condition in baseline fault; do
        if [[ -f "$OUT/rows/${mutation}__${log_id}__${condition}.tsv" ]]; then continue; fi
        run_one "$mutation" "$module" "$log_id" "$input" "$duration" "$condition"
      done
    ) &
    pids+=("$!")
  done
  for pid in "${pids[@]}"; do wait "$pid"; done
done
printf 'run_id\tcondition\tmutation_id\tground_truth_module\treplay_log\treplay_mode\toutput_ulog\texit_code\n' > "$OUT/run_manifest.tsv"
cat "$OUT"/rows/*.tsv >> "$OUT/run_manifest.tsv"
sha256sum "$TASK_HOME"/inputs/*.ulg "$SOURCE_HOME"/bin/*/px4 > "$OUT/input_binary_sha256.txt"
