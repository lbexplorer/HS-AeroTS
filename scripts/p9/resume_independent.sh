#!/usr/bin/env bash
# Infrastructure-only recovery. Preserve failed attempt; change only work directory.
set -euo pipefail
WIN=/mnt/d/UAV
OUT="$WIN/reports/p9/paired_residual/independent"
ORIGINAL="$WIN/scripts/p9/run_independent.sh"
RECOVERY=/root/hs-aerots-p9-independent-recovery-20260906
mkdir -p "$RECOVERY" "$OUT/infrastructure_failure/logs" "$OUT/infrastructure_failure/consoles"
for file in "$OUT"/reference/logs/*2018-12-20*.ulg; do
  [[ -e "$file" ]] && cp "$file" "$OUT/infrastructure_failure/logs/"
done
for file in "$OUT"/consoles/*2018-12-20*.log; do
  [[ -e "$file" ]] && cp "$file" "$OUT/infrastructure_failure/consoles/"
done
python3 - <<'PY'
from pathlib import Path
import json
root=Path('/root/hs-aerots-p9-independent-20260906/runs')
rows=[]
for p in sorted(root.glob('*2018-12-20*/console.log')):
    data=p.read_bytes()
    rows.append(dict(run_id=p.parent.name,console_bytes=len(data),nul_bytes=data.count(b'\0'),
                     replay_done=b'Replay done' in data,exit_code=137))
Path('/mnt/d/UAV/reports/p9/paired_residual/independent/infrastructure_failure/audit.json').write_text(json.dumps(dict(
    reason='Four contemporaneous baseline processes killed; Bad address copying outputs; local consoles corrupted. No prediction scores read.',
    action='Preserve first 12 completed trials; retry four incomplete baselines and run remaining planned trials in fresh work directories; unchanged binaries, inputs, timeouts and method.',
    attempts=rows),indent=2))
print(json.dumps(rows,indent=2))
PY
sed 's#TASK=/root/hs-aerots-p9-independent-20260906#TASK=/root/hs-aerots-p9-independent-recovery-20260906#' "$ORIGINAL" > "$RECOVERY/runner.sh"
bash "$RECOVERY/runner.sh"
