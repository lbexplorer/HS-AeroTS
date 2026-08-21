#!/usr/bin/env bash
set -euo pipefail

run_root="/root/hs-aerots-p9-v5/runs"
output_root="/mnt/d/UAV/reports/p9/replay_consoles"
mkdir -p "$output_root"

count=0
for console in "$run_root"/*/console.log; do
  run_id="$(basename "$(dirname "$console")")"
  cp -f "$console" "$output_root/$run_id.log"
  count=$((count + 1))
done
echo "consoles=$count"
