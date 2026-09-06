#!/usr/bin/env bash
# Independent healthy targets. Do not subtract any reference from itself.
set -euo pipefail
OLD=/root/hs-aerots-p9-v5
TASK=/root/hs-aerots-p9-normal-repeats-20260906
WIN=/mnt/d/UAV
OUT="$WIN/reports/p9/paired_residual/normal_repeats"
mkdir -p "$TASK/runs" "$OUT/logs" "$OUT/consoles" "$OUT/rows"
run_one() {
  local mutation="$1" module="$2" source="$3" duration="$4"
  local run_id="${mutation}__${source}__baseline"
  local directory="$TASK/runs/$run_id"
  if [[ -f "$OUT/rows/$run_id.tsv" ]]; then return; fi
  [[ ! -e "$directory" ]] || { echo "Existing incomplete run: $directory" >&2; return 2; }
  mkdir -p "$directory/rootfs"
  local input="/root/hs-aerots-p9-native-20260906/inputs/$source.ulg"
  local binary="$OLD/bin/baseline/px4"
  if [[ "$mutation" == ekf2_innovation_bias ]]; then
    binary="$OLD/bin/$mutation/px4"
  else
    cp "$WIN/reports/p9/replay_scripts/$mutation.orb_publisher.rules" "$directory/rootfs/orb_publisher.rules"
  fi
  cp "$WIN/reports/p9/replay_scripts/$mutation.rcS" "$directory/rcS"
  local code=0
  (cd "$directory"; HS_P9_EKF_FAULT=0 replay="$input" replay_mode=generic \
    timeout --signal=INT --kill-after=10 "$duration" "$binary" -d "$OLD/PX4-Autopilot" "$directory/rcS" >console.log 2>&1) || code=$?
  grep -q 'Replay done' "$directory/console.log" || { echo "Incomplete replay $run_id" >&2; return 3; }
  local output
  output=$(find "$directory/rootfs/fs/microsd/log" -name '*.ulg' -type f | sort | tail -1)
  [[ -n "$output" ]] || return 4
  cp "$output" "$OUT/logs/$run_id.ulg"
  cp "$directory/console.log" "$OUT/consoles/$run_id.log"
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$run_id" baseline "$mutation" "$module" "$input" generic "$OUT/logs/$run_id.ulg" "$code" > "$OUT/rows/$run_id.tsv"
  echo "Completed independent normal $run_id"
}
for spec in '2019-01-18__08_39_38|85' '2019-01-25__17_38_05|110' '2019-03-06__08_02_26|115'; do
  IFS='|' read -r source duration <<< "$spec"
  pids=()
  for pair in 'commander_nav_state_override|src/modules/commander' 'ekf2_innovation_bias|src/modules/ekf2' 'inav_local_z_freeze|src/modules/position_estimator_inav' 'land_detector_state_inversion|src/modules/land_detector'; do
    IFS='|' read -r mutation module <<< "$pair"
    run_one "$mutation" "$module" "$source" "$duration" &
    pids+=("$!")
  done
  for pid in "${pids[@]}"; do wait "$pid"; done
done
printf 'run_id\tcondition\tmutation_id\tground_truth_module\treplay_log\treplay_mode\toutput_ulog\texit_code\n' > "$OUT/run_manifest.tsv"
cat "$OUT"/rows/*.tsv >> "$OUT/run_manifest.tsv"
sha256sum /root/hs-aerots-p9-native-20260906/inputs/*.ulg "$OLD"/bin/*/px4 > "$OUT/input_binary_sha256.txt"
