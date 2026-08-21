"""Validate source-level mutation effects in the controlled P9 PX4 ULog replay."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from pyulog import ULog

from hs_aerots.baseline import _ulog_time_bounds


ROOT = Path(__file__).resolve().parents[2]
LOG_ROOT = ROOT / "reports" / "p9" / "replay_logs"
LOG_IDS = ["2019-01-18__08_39_38", "2019-01-25__17_38_05", "2019-03-06__08_02_26"]
SPECS = {
    "commander_nav_state_override": ("vehicle_status", "nav_state", "target_fraction", 18.0),
    "ekf2_innovation_bias": ("ekf2_innovations", "vel_pos_innov[3]", "post_mean", 20.0),
    "inav_local_z_freeze": ("vehicle_local_position", "z", "post_std", 0.0),
    "land_detector_state_inversion": ("vehicle_land_detected", "landed", "target_fraction", 1.0),
}


def load_post(mutation: str, log_id: str, condition: str, topic: str, field: str) -> tuple[np.ndarray, np.ndarray]:
    path = LOG_ROOT / f"{mutation}__{log_id}__{condition}.ulg"
    ulog = ULog(str(path))
    start, _ = _ulog_time_bounds(ulog)
    dataset = next(item for item in ulog.data_list if item.name == topic)
    times = (np.asarray(dataset.data["timestamp"], dtype=float) - start) / 1e6
    values = np.asarray(dataset.data[field], dtype=float)
    return times[times >= 30.0], values[times >= 30.0]


def main() -> None:
    rows = []
    for mutation, (topic, field, measure, target) in SPECS.items():
        for log_id in LOG_IDS:
            baseline_times, baseline = load_post(mutation, log_id, "baseline", topic, field)
            fault_times, fault = load_post(mutation, log_id, "fault", topic, field)
            if measure == "target_fraction":
                baseline_value = float(np.mean(baseline == target))
                fault_value = float(np.mean(fault == target))
                passed = baseline_value < 0.1 and fault_value > 0.9
            elif measure == "post_mean":
                baseline_value = float(np.mean(baseline))
                fault_value = float(np.mean(fault))
                passed = abs(baseline_value) < 0.1 and fault_value > 15.0
            else:
                baseline_value = float(np.std(baseline))
                fault_value = float(np.std(fault))
                passed = baseline_value > 0.1 and fault_value < 0.25 * baseline_value
            target_hits = fault_times[np.isclose(fault, target)] if measure != "post_std" else np.array([])
            rows.append({
                "mutation_id": mutation, "log_id": log_id, "topic": topic, "field": field,
                "measure": measure, "baseline_value": baseline_value, "fault_value": fault_value,
                "first_target_time_s": float(target_hits.min()) if len(target_hits) else np.nan,
                "passed": bool(passed),
            })
    frame = pd.DataFrame(rows)
    output = ROOT / "reports" / "p9" / "injection_effect_validation.csv"
    frame.to_csv(output, index=False, encoding="utf-8-sig")
    if not frame["passed"].all():
        raise SystemExit(f"injection effect validation failed:\n{frame.loc[~frame['passed']].to_string(index=False)}")
    print(f"validated {len(frame)} mutation/log pairs: {output}")


if __name__ == "__main__":
    main()
