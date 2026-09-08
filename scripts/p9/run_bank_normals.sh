#!/usr/bin/env bash
# One genuinely new healthy target per existing source/runtime condition.
set -euo pipefail
WIN=/mnt/d/UAV
OLD=/root/hs-aerots-p9-v5
TASK=/root/hs-aerots-p15-bank-normals-20260907
OUT="$WIN/reports/p15_reference_bank/healthy_repeats"
mkdir -p "$TASK/inputs" "$TASK/runs" "$OUT/logs" "$OUT/rows" "$OUT/consoles"
run_one() {
  local mutation="$1" module="$2" source="$3" duration="$4"
  local rid="${mutation}__${source}__baseline" directory="$TASK/runs/${mutation}__${source}"
  [[ ! -e "$directory" ]] || { echo "Existing attempt $directory" >&2; return 2; }
  mkdir -p "$directory/rootfs"
  local binary="$OLD/bin/baseline/px4"
  if [[ "$mutation" == ekf2_innovation_bias ]]; then
    binary="$OLD/bin/$mutation/px4"
    sed 's/^ekf2 start -r$/ekf2 start/' "$WIN/reports/p9/replay_scripts/$mutation.rcS" > "$directory/rcS"
  else
    cp "$WIN/reports/p9/replay_scripts/$mutation.rcS" "$directory/rcS"
    cp "$WIN/reports/p9/replay_scripts/$mutation.orb_publisher.rules" "$directory/rootfs/orb_publisher.rules"
  fi
  local code=0
  (cd "$directory"; HS_P9_EKF_FAULT=0 replay="$TASK/inputs/$source.ulg" replay_mode=generic \
    timeout --signal=INT --kill-after=10 "$duration" "$binary" -d "$OLD/PX4-Autopilot" "$directory/rcS" >console.log 2>&1) || code=$?
  cp "$directory/console.log" "$OUT/consoles/$rid.log"
  grep -q 'Replay done' "$directory/console.log" || { echo "Incomplete $rid" >&2; return 3; }
  local output
  output=$(find "$directory/rootfs/fs/microsd/log" -name '*.ulg' -type f | sort | tail -1)
  [[ -n "$output" ]] || return 4
  cp "$output" "$OUT/logs/$rid.ulg"
  cmp "$output" "$OUT/logs/$rid.ulg"
  printf '%s\tbaseline\t%s\t%s\t%s\tgeneric\t%s\t%s\n' "$rid" "$mutation" "$module" "$TASK/inputs/$source.ulg" "$OUT/logs/$rid.ulg" "$code" > "$OUT/rows/$rid.tsv"
  echo "Completed $rid exit=$code"
}
sha256sum "$OLD"/bin/*/px4 > "$OUT/binary_sha256.txt"
for spec in '2019-01-18__08_39_38|90' '2019-01-25__17_38_05|115' '2019-03-06__08_02_26|120' '2018-12-19__07_49_17|108' '2018-12-20__07_47_50|144' '2018-12-25__08_44_40|162'; do
  IFS='|' read -r source duration <<< "$spec"
  datepart=${source%%__*}; clockpart=${source#*__}
  cp "$WIN/data/raw/uav_sead/ulg_files/$datepart/$clockpart.ulg" "$TASK/inputs/$source.ulg"
  cmp "$WIN/data/raw/uav_sead/ulg_files/$datepart/$clockpart.ulg" "$TASK/inputs/$source.ulg"
  pids=()
  for pair in 'commander_nav_state_override|src/modules/commander' 'ekf2_innovation_bias|src/modules/ekf2' 'inav_local_z_freeze|src/modules/position_estimator_inav' 'land_detector_state_inversion|src/modules/land_detector'; do
    IFS='|' read -r mutation module <<< "$pair"
    run_one "$mutation" "$module" "$source" "$duration" &
    pids+=("$!")
  done
  failed=0
  for pid in "${pids[@]}"; do wait "$pid" || failed=1; done
  [[ "$failed" == 0 ]] || exit 5
done
printf 'run_id\tcondition\tmutation_id\tground_truth_module\treplay_log\treplay_mode\toutput_ulog\texit_code\n' > "$OUT/run_manifest.tsv"
cat "$OUT"/rows/*.tsv >> "$OUT/run_manifest.tsv"
sha256sum "$TASK"/inputs/*.ulg > "$OUT/input_sha256.txt"
echo 'COMPLETE: 24 new healthy targets'
