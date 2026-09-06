#!/usr/bin/env bash
# Generic replay must not enable the dedicated EKF replay handshake (-r).
# Otherwise old PX4 publishes an uninitialized attitude when EKF update fails.
set -euo pipefail
OLD=/root/hs-aerots-p9-v5
TASK=/root/hs-aerots-p9-ekf-generic-20260906
WIN=/mnt/d/UAV
OUT="$WIN/reports/p9/paired_residual/ekf_generic_repair"
mkdir -p "$TASK" "$OUT/reference/logs" "$OUT/normal/logs" "$OUT/consoles" "$OUT/rows"
run_source() {
  local source="$1" duration="$2"
  for condition in baseline fault normal; do
    local run_id="ekf2_innovation_bias__${source}__${condition}"
    local directory="$TASK/$run_id"
    if [[ -f "$OUT/rows/$run_id.tsv" ]]; then continue; fi
    [[ ! -e "$directory" ]] || return 2
    mkdir -p "$directory/rootfs"
    # Both conditions retain the same original innovation adapter binary.
    sed 's/^ekf2 start -r$/ekf2 start/' "$WIN/reports/p9/replay_scripts/ekf2_innovation_bias.rcS" > "$directory/rcS"
    local flag=0
    [[ "$condition" == fault ]] && flag=1
    local input="/root/hs-aerots-p9-native-20260906/inputs/$source.ulg"
    local code=0
    (cd "$directory"; HS_P9_EKF_FAULT="$flag" replay="$input" replay_mode=generic \
      timeout --signal=INT --kill-after=10 "$duration" "$OLD/bin/ekf2_innovation_bias/px4" -d "$OLD/PX4-Autopilot" "$directory/rcS" >console.log 2>&1) || code=$?
    grep -q 'Replay done' "$directory/console.log" || return 3
    local output
    output=$(find "$directory/rootfs/fs/microsd/log" -name '*.ulg' -type f | sort | tail -1)
    [[ -n "$output" ]] || return 4
    local target="$OUT/reference/logs/$run_id.ulg"
    if [[ "$condition" == normal ]]; then target="$OUT/normal/logs/ekf2_innovation_bias__${source}__baseline.ulg"; fi
    cp "$output" "$target"
    cp "$directory/console.log" "$OUT/consoles/$run_id.log"
    printf '%s\t%s\t%s\t%s\n' "$source" "$condition" "$target" "$code" > "$OUT/rows/$run_id.tsv"
    echo "Completed generic-mode correction $run_id"
  done
}
pids=()
for spec in '2019-01-18__08_39_38|85' '2019-01-25__17_38_05|110' '2019-03-06__08_02_26|115'; do
  IFS='|' read -r source duration <<< "$spec"
  run_source "$source" "$duration" &
  pids+=("$!")
done
for pid in "${pids[@]}"; do wait "$pid"; done
sha256sum "$OLD/bin/ekf2_innovation_bias/px4" /root/hs-aerots-p9-native-20260906/inputs/*.ulg > "$OUT/input_binary_sha256.txt"
