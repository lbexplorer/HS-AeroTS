#!/usr/bin/env bash
# New sources, frozen existing binaries/rcS; no adaptive resampling or tuning.
set -euo pipefail
OLD=/root/hs-aerots-p9-v5
TASK=/root/hs-aerots-p9-independent-20260906
WIN=/mnt/d/UAV
OUT="$WIN/reports/p9/paired_residual/independent"
test -f "$OUT/sealed/protocol.json"
mkdir -p "$TASK/inputs" "$TASK/runs" "$OUT/reference/logs" "$OUT/normal/logs" "$OUT/consoles" "$OUT/rows"
run_pair() {
  local mutation="$1" module="$2" source="$3" duration="$4"
  for condition in baseline fault normal; do
    local rid="${mutation}__${source}__${condition}"
    local directory="$TASK/runs/$rid"
    if [[ -f "$OUT/rows/$rid.tsv" ]]; then continue; fi
    [[ ! -e "$directory" ]] || { echo "Incomplete existing run $rid" >&2; return 2; }
    mkdir -p "$directory/rootfs"
    local binary="$OLD/bin/baseline/px4" flag=0
    if [[ "$condition" == fault ]]; then binary="$OLD/bin/$mutation/px4"; flag=1; fi
    if [[ "$mutation" == ekf2_innovation_bias ]]; then
      binary="$OLD/bin/$mutation/px4"
      sed 's/^ekf2 start -r$/ekf2 start/' "$OUT/sealed/$mutation.rcS" > "$directory/rcS"
    else
      cp "$OUT/sealed/$mutation.rcS" "$directory/rcS"
      cp "$OUT/sealed/$mutation.orb_publisher.rules" "$directory/rootfs/orb_publisher.rules"
    fi
    local code=0
    (cd "$directory"; HS_P9_EKF_FAULT="$flag" replay="$TASK/inputs/$source.ulg" replay_mode=generic \
      timeout --signal=INT --kill-after=10 "$duration" "$binary" -d "$OLD/PX4-Autopilot" "$directory/rcS" >console.log 2>&1) || code=$?
    cp "$directory/console.log" "$OUT/consoles/$rid.log"
    grep -q 'Replay done' "$directory/console.log" || { echo "Incomplete replay $rid exit=$code" >&2; return 3; }
    local output target run_id="$rid" stored_condition="$condition" group=reference
    output=$(find "$directory/rootfs/fs/microsd/log" -name '*.ulg' -type f | sort | tail -1)
    [[ -n "$output" ]] || return 4
    if [[ "$condition" == normal ]]; then group=normal; run_id="${mutation}__${source}__baseline"; stored_condition=baseline; fi
    target="$OUT/$group/logs/$run_id.ulg"
    cp "$output" "$target"
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$run_id" "$stored_condition" "$mutation" "$module" "$TASK/inputs/$source.ulg" generic "$target" "$code" > "$OUT/rows/$rid.tsv"
    echo "Completed $rid exit=$code"
  done
}
sha256sum "$OLD"/bin/*/px4 > "$OUT/binary_sha256_before.txt"
for spec in '2018-12-19__07_49_17|108' '2018-12-20__07_47_50|144' '2018-12-25__08_44_40|162'; do
  IFS='|' read -r source duration <<< "$spec"
  datepart=${source%%__*}; clockpart=${source#*__}
  cp "$WIN/data/raw/uav_sead/ulg_files/$datepart/$clockpart.ulg" "$TASK/inputs/$source.ulg"
  cmp "$WIN/data/raw/uav_sead/ulg_files/$datepart/$clockpart.ulg" "$TASK/inputs/$source.ulg"
  pids=()
  for pair in 'commander_nav_state_override|src/modules/commander' 'ekf2_innovation_bias|src/modules/ekf2' 'inav_local_z_freeze|src/modules/position_estimator_inav' 'land_detector_state_inversion|src/modules/land_detector'; do
    IFS='|' read -r mutation module <<< "$pair"
    run_pair "$mutation" "$module" "$source" "$duration" &
    pids+=("$!")
  done
  failed=0
  for pid in "${pids[@]}"; do wait "$pid" || failed=1; done
  [[ "$failed" == 0 ]] || exit 5
done
for group in reference normal; do
  printf 'run_id\tcondition\tmutation_id\tground_truth_module\treplay_log\treplay_mode\toutput_ulog\texit_code\n' > "$OUT/$group/run_manifest.tsv"
done
for row in "$OUT"/rows/*.tsv; do
  if [[ "$row" == *__normal.tsv ]]; then cat "$row" >> "$OUT/normal/run_manifest.tsv";
  else cat "$row" >> "$OUT/reference/run_manifest.tsv"; fi
done
sha256sum "$TASK"/inputs/*.ulg > "$OUT/input_sha256.txt"
sha256sum "$OLD"/bin/*/px4 > "$OUT/binary_sha256_after.txt"
cmp "$OUT/binary_sha256_before.txt" "$OUT/binary_sha256_after.txt"
echo 'COMPLETE: 36 independent validation replays'
