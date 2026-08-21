"""UAV-SEAD download, inventory, channel selection, and 10 Hz alignment."""

from __future__ import annotations

import argparse
import csv
import json
import os
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd
from huggingface_hub import HfApi, snapshot_download
from pyulog import ULog
from pyulog.px4 import PX4ULog


REPO_ID = "aykutkabaoglu/uav-flight-anomaly-dataset"
REPO_REVISION = "774a336a1d1d06b248927a35c2ea1f6869e9e1a4"
CORE_COVERAGE = 0.60
NORMAL_CLASSES = {"Normal", "Uncategorized"}
TOPIC_FIELDS: dict[str, list[str]] = {
    "actuator_controls_0": ["control[0]", "control[1]", "control[2]", "control[3]", "control[7]"],
    "actuator_outputs": [f"output[{index}]" for index in range(8)],
    "battery_status": [
        "voltage_v", "voltage_filtered_v", "current_a", "current_filtered_a", "discharged_mah", "remaining"
    ],
    "cpuload": ["load", "ram_usage"],
    "distance_sensor": ["current_distance", "variance", "signal_quality"],
    "ekf2_innovations": [
        "vel_pos_innov[0]", "vel_pos_innov[1]", "vel_pos_innov[2]", "vel_pos_innov[3]",
        "vel_pos_innov[4]", "vel_pos_innov[5]", "mag_innov[0]", "mag_innov[1]", "mag_innov[2]",
        "heading_innov", "hagl_innov", "output_tracking_error[0]", "output_tracking_error[1]",
        "output_tracking_error[2]",
    ],
    "estimator_status": [
        "pos_test_ratio", "vel_test_ratio", "hgt_test_ratio", "mag_test_ratio", "hagl_test_ratio",
        "pos_horiz_accuracy", "pos_vert_accuracy", "filter_fault_flags", "innovation_check_flags",
        "vibe[0]", "vibe[1]", "vibe[2]",
    ],
    "manual_control_setpoint": ["x", "y", "z", "r", "valid"],
    "rate_ctrl_status": ["rollspeed_integ", "pitchspeed_integ", "yawspeed_integ", "additional_integ1"],
    "sensor_combined": [
        "gyro_rad[0]", "gyro_rad[1]", "gyro_rad[2]", "accelerometer_m_s2[0]",
        "accelerometer_m_s2[1]", "accelerometer_m_s2[2]", "magnetometer_ga[0]",
        "magnetometer_ga[1]", "magnetometer_ga[2]", "baro_alt_meter",
    ],
    "sensor_preflight": ["accel_inconsistency_m_s_s", "gyro_inconsistency_rad_s", "mag_inconsistency_angle"],
    "system_power": ["voltage5v_v", "voltage3v3_v", "brick_valid", "usb_valid", "servo_valid"],
    "vehicle_air_data": ["baro_alt_meter", "baro_temp_celcius", "baro_pressure_pa", "rho"],
    "vehicle_angular_velocity": ["xyz[0]", "xyz[1]", "xyz[2]"],
    "vehicle_attitude": ["q[0]", "q[1]", "q[2]", "q[3]", "rollspeed", "pitchspeed", "yawspeed"],
    "vehicle_attitude_setpoint": ["roll_body", "pitch_body", "yaw_body", "thrust_body[2]"],
    "vehicle_land_detected": ["alt_max", "freefall", "ground_contact", "maybe_landed", "landed", "in_ground_effect"],
    "vehicle_local_position": [
        "x", "y", "z", "vx", "vy", "vz", "ax", "ay", "az", "dist_bottom", "dist_bottom_rate",
        "eph", "epv", "heading", "xy_valid", "z_valid", "v_xy_valid", "v_z_valid",
    ],
    "vehicle_magnetometer": ["magnetometer_ga[0]", "magnetometer_ga[1]", "magnetometer_ga[2]"],
    "vehicle_rates_setpoint": ["roll", "pitch", "yaw", "thrust_body[2]"],
    "vehicle_status": ["nav_state", "arming_state", "failsafe", "pre_flight_checks_pass", "rc_signal_lost"],
    "vehicle_status_flags": [
        "condition_global_position_valid", "condition_local_position_valid", "condition_local_velocity_valid",
        "condition_local_altitude_valid", "condition_battery_healthy",
    ],
    "vehicle_vision_position": ["x", "y", "z", "xy_valid", "z_valid", "v_xy_valid", "v_z_valid"],
    "vehicle_visual_odometry": ["x", "y", "z", "q[0]", "q[1]", "q[2]", "q[3]"],
}


@dataclass
class LogRecord:
    log_key: str
    relative_path: str
    status: str
    size_bytes: int = 0
    start_timestamp_us: int | None = None
    end_timestamp_us: int | None = None
    duration_s: float | None = None
    aligned_rows: int = 0
    topic_count: int = 0
    numeric_channel_count: int = 0
    annotation_classes: str = ""
    anomaly_interval_count: int = 0
    parse_error: str = ""


def load_mapping(path: Path) -> dict[str, dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("mapping.json must contain an object keyed by log path")
    return data


def relative_ulog_path(log_key: str) -> str:
    return f"ulg_files/{log_key}.ulg"


def annotation_intervals(entry: dict[str, Any]) -> list[dict[str, Any]]:
    """Flatten the dataset's [signal, [[start, end], ...]] range structure."""
    result: list[dict[str, Any]] = []
    for annotation in entry.get("annotations", []):
        label = str(annotation.get("class", ""))
        for group in annotation.get("ranges") or []:
            if not isinstance(group, list) or len(group) != 2:
                continue
            signal, ranges = group
            for bounds in ranges or []:
                if not isinstance(bounds, list) or len(bounds) != 2:
                    continue
                start, end = int(bounds[0]), int(bounds[1])
                if end < start:
                    start, end = end, start
                result.append(
                    {"class": label, "signal": str(signal), "start_us": start, "end_us": end}
                )
    return result


def annotation_classes(entry: dict[str, Any]) -> list[str]:
    return sorted({str(a.get("class", "")) for a in entry.get("annotations", [])})


def _numeric_channels(ulog: ULog) -> tuple[dict[str, np.ndarray], dict[str, str], int]:
    """Return numeric instance-0 channels using topic.field names."""
    try:
        PX4ULog(ulog).add_roll_pitch_yaw()
    except (KeyError, ValueError, IndexError, TypeError):
        pass

    channels: dict[str, np.ndarray] = {}
    dtypes: dict[str, str] = {}
    topics: set[str] = set()
    seen_topics: set[str] = set()
    for dataset in ulog.data_list:
        topic = dataset.name
        if topic in seen_topics:
            continue
        seen_topics.add(topic)
        try:
            data = ulog.get_dataset(topic).data
        except (KeyError, ValueError, IndexError):
            continue
        timestamp = np.asarray(data.get("timestamp", []))
        if timestamp.size == 0:
            continue
        topics.add(topic)
        for field, values in data.items():
            if field == "timestamp" or field.startswith("_padding"):
                continue
            array = np.asarray(values)
            if array.ndim != 1 or not np.issubdtype(array.dtype, np.number):
                continue
            if array.size != timestamp.size:
                continue
            name = f"{topic}.{field}"
            channels[name] = array
            dtypes[name] = str(array.dtype)
    return channels, dtypes, len(topics)


def _scan_one(args: tuple[str, str, dict[str, Any]]) -> tuple[dict[str, Any], dict[str, str]]:
    log_key, file_name, entry = args
    path = Path(file_name)
    rel = relative_ulog_path(log_key)
    classes = "|".join(annotation_classes(entry))
    intervals = annotation_intervals(entry)
    if not path.exists():
        return asdict(LogRecord(log_key, rel, "missing", annotation_classes=classes,
                                anomaly_interval_count=len(intervals))), {}
    try:
        ulog = ULog(str(path), message_name_filter_list=list(TOPIC_FIELDS))
        start = int(ulog.start_timestamp)
        end = int(ulog.last_timestamp)
        duration = (end - start) / 1_000_000
        if end <= start:
            return asdict(LogRecord(log_key, rel, "invalid_time_range", size_bytes=path.stat().st_size,
                                    start_timestamp_us=start, end_timestamp_us=end, duration_s=duration,
                                    annotation_classes=classes, anomaly_interval_count=len(intervals))), {}
        if duration < 5.0:
            return asdict(LogRecord(log_key, rel, "too_short", size_bytes=path.stat().st_size,
                                    start_timestamp_us=start, end_timestamp_us=end, duration_s=duration,
                                    annotation_classes=classes, anomaly_interval_count=len(intervals))), {}
        if duration > 7200.0:
            return asdict(LogRecord(log_key, rel, "too_long_or_corrupt", size_bytes=path.stat().st_size,
                                    start_timestamp_us=start, end_timestamp_us=end, duration_s=duration,
                                    annotation_classes=classes, anomaly_interval_count=len(intervals))), {}
        channels, dtypes, topic_count, aligned_rows = _aerots_candidate_channels(ulog, start, end)
        if not channels:
            return asdict(LogRecord(log_key, rel, "no_features", size_bytes=path.stat().st_size,
                                    start_timestamp_us=start, end_timestamp_us=end, duration_s=duration,
                                    aligned_rows=aligned_rows, annotation_classes=classes,
                                    anomaly_interval_count=len(intervals))), {}
        if len(channels) < 8:
            return asdict(LogRecord(log_key, rel, "too_few_features", size_bytes=path.stat().st_size,
                                    start_timestamp_us=start, end_timestamp_us=end, duration_s=duration,
                                    aligned_rows=aligned_rows, numeric_channel_count=len(channels),
                                    annotation_classes=classes, anomaly_interval_count=len(intervals))), {}
        record = LogRecord(
            log_key=log_key,
            relative_path=rel,
            status="usable",
            size_bytes=path.stat().st_size,
            start_timestamp_us=start,
            end_timestamp_us=end,
            duration_s=duration,
            aligned_rows=aligned_rows,
            topic_count=topic_count,
            numeric_channel_count=len(channels),
            annotation_classes=classes,
            anomaly_interval_count=len(intervals),
        )
        return asdict(record), dtypes
    except Exception as exc:  # a corrupt ULog must be recorded, not abort the inventory
        record = LogRecord(
            log_key=log_key,
            relative_path=rel,
            status="parse_error",
            size_bytes=path.stat().st_size,
            annotation_classes=classes,
            anomaly_interval_count=len(intervals),
            parse_error=f"{type(exc).__name__}: {exc}",
        )
        return asdict(record), {}


def _interpolate_dataset(grid: np.ndarray, timestamp: np.ndarray, values: np.ndarray) -> np.ndarray:
    timestamp = np.asarray(timestamp, dtype=np.float64)
    values = np.asarray(values, dtype=np.float64)
    ok = np.isfinite(timestamp) & np.isfinite(values)
    if ok.sum() < 2:
        return np.full(len(grid), np.nan, dtype=np.float32)
    timestamp = timestamp[ok]
    values = values[ok]
    order = np.argsort(timestamp)
    timestamp = timestamp[order]
    values = values[order]
    unique, indices = np.unique(timestamp, return_index=True)
    values = values[indices]
    if len(unique) < 2:
        return np.full(len(grid), np.nan, dtype=np.float32)
    return np.interp(grid.astype(np.float64), unique, values, left=np.nan, right=np.nan).astype(np.float32)


def _aerots_candidate_channels(
    ulog: ULog, start: int, end: int, frequency_hz: float = 10.0
) -> tuple[list[str], dict[str, str], int, int]:
    """Efficiently mirror AeroTSBoost's per-log validity/variance field filter."""
    step = max(1, int(round(1_000_000 / frequency_hz)))
    aligned_rows = int(np.floor((end - start) / step)) + 1
    good: list[str] = []
    dtypes: dict[str, str] = {}
    seen: set[str] = set()
    topics: set[str] = set()
    for dataset in ulog.data_list:
        fields = TOPIC_FIELDS.get(dataset.name)
        if not fields or "timestamp" not in dataset.data:
            continue
        topics.add(dataset.name)
        timestamps = dataset.data["timestamp"]
        for field in fields:
            if field not in dataset.data:
                continue
            channel = f"{dataset.name}.{field}"
            if channel in seen:
                continue
            seen.add(channel)
            timestamp_array = np.asarray(timestamps, dtype=np.float64)
            values = np.asarray(dataset.data[field], dtype=np.float64)
            valid = np.isfinite(timestamp_array) & np.isfinite(values)
            if valid.sum() < 2 or np.unique(timestamp_array[valid]).size < 2:
                continue
            if float(np.nanstd(values[valid], ddof=1)) <= 1e-10:
                continue
            good.append(channel)
            dtypes[channel] = str(np.asarray(dataset.data[field]).dtype)
    return good, dtypes, len(topics), aligned_rows


def download_annotated(data_root: Path, manifest_path: Path, workers: int) -> None:
    data_root.mkdir(parents=True, exist_ok=True)
    snapshot_download(
        repo_id=REPO_ID,
        repo_type="dataset",
        revision=REPO_REVISION,
        local_dir=str(data_root),
        allow_patterns=["README.md", "mapping.json"],
        max_workers=min(workers, 4),
    )
    mapping = load_mapping(data_root / "mapping.json")
    available = set(HfApi().list_repo_files(REPO_ID, repo_type="dataset", revision=REPO_REVISION))
    rows = []
    wanted = []
    for key in mapping:
        relative = relative_ulog_path(key)
        exists_upstream = relative in available
        rows.append({"log_key": key, "relative_path": relative, "exists_upstream": exists_upstream})
        if exists_upstream:
            wanted.append(relative)
    _write_csv(manifest_path, rows)
    snapshot_download(
        repo_id=REPO_ID,
        repo_type="dataset",
        revision=REPO_REVISION,
        local_dir=str(data_root),
        allow_patterns=wanted,
        max_workers=workers,
    )


def _write_csv(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    rows = list(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def build_inventory(data_root: Path, output_dir: Path, workers: int) -> dict[str, Any]:
    mapping = load_mapping(data_root / "mapping.json")
    tasks = [(key, str(data_root / relative_ulog_path(key)), entry) for key, entry in mapping.items()]
    records: list[dict[str, Any]] = []
    channel_counts: Counter[str] = Counter()
    channel_dtypes: dict[str, str] = {}

    if workers <= 1:
        results = map(_scan_one, tasks)
        for record, dtypes in results:
            records.append(record)
            if record["status"] == "usable":
                channel_counts.update(dtypes.keys())
                channel_dtypes.update(dtypes)
    else:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(_scan_one, task) for task in tasks]
            for index, future in enumerate(as_completed(futures), start=1):
                record, dtypes = future.result()
                records.append(record)
                if record["status"] == "usable":
                    channel_counts.update(dtypes.keys())
                    channel_dtypes.update(dtypes)
                if index % 100 == 0:
                    print(f"Scanned {index}/{len(tasks)} logs", flush=True)

    records.sort(key=lambda row: row["log_key"])
    usable = sum(row["status"] == "usable" for row in records)
    dictionary = []
    for channel in sorted(channel_counts):
        topic, field = channel.split(".", 1)
        coverage = channel_counts[channel] / usable if usable else 0.0
        dictionary.append(
            {
                "channel": channel,
                "topic": topic,
                "field": field,
                "dtype": channel_dtypes.get(channel, ""),
                "logs_present": channel_counts[channel],
                "coverage": round(coverage, 6),
                "selected_core_60pct": coverage >= CORE_COVERAGE,
            }
        )

    class_counts: Counter[str] = Counter()
    interval_counts: Counter[str] = Counter()
    empty_anomaly_annotations = 0
    annotation_rows: list[dict[str, Any]] = []
    for log_key, entry in mapping.items():
        for annotation_index, annotation in enumerate(entry.get("annotations", [])):
            label = str(annotation.get("class", ""))
            class_counts[label] += 1
            intervals = annotation_intervals({"annotations": [annotation]})
            interval_counts[label] += len(intervals)
            if label not in NORMAL_CLASSES and not intervals:
                empty_anomaly_annotations += 1
            if intervals:
                for range_index, interval in enumerate(intervals):
                    annotation_rows.append(
                        {
                            "log_key": log_key,
                            "annotation_index": annotation_index,
                            "class": label,
                            "note": str(annotation.get("note", "")),
                            "annotated_at": str(annotation.get("timestamp", "")),
                            "range_index": range_index,
                            "signal": interval["signal"],
                            "start_us": interval["start_us"],
                            "end_us": interval["end_us"],
                        }
                    )
            else:
                annotation_rows.append(
                    {
                        "log_key": log_key,
                        "annotation_index": annotation_index,
                        "class": label,
                        "note": str(annotation.get("note", "")),
                        "annotated_at": str(annotation.get("timestamp", "")),
                        "range_index": "",
                        "signal": "",
                        "start_us": "",
                        "end_us": "",
                    }
                )

    core = [row["channel"] for row in dictionary if row["selected_core_60pct"]]
    statuses = Counter(row["status"] for row in records)
    summary = {
        "dataset_repo": REPO_ID,
        "revision": REPO_REVISION,
        "mapping_logs": len(mapping),
        "status_counts": dict(sorted(statuses.items())),
        "usable_logs": usable,
        "annotation_counts": dict(sorted(class_counts.items())),
        "anomaly_interval_counts": dict(sorted(interval_counts.items())),
        "anomaly_annotations_without_ranges": empty_anomaly_annotations,
        "unique_numeric_channels": len(dictionary),
        "core_coverage_threshold": CORE_COVERAGE,
        "core_channel_count": len(core),
        "expected_aerotsboost_core_channels": 87,
        "core_channel_count_matches_expected": len(core) == 87,
        "total_usable_duration_s": round(
            sum(float(row["duration_s"] or 0.0) for row in records if row["status"] == "usable"), 3
        ),
        "aligned_rows_10hz": sum(int(row["aligned_rows"] or 0) for row in records if row["status"] == "usable"),
        "expected_aerotsboost_usable_logs": 1389,
        "usable_log_count_matches_expected": usable == 1389,
        "expected_aerotsboost_aligned_rows": 1892063,
        "aligned_row_count_matches_expected": (
            sum(int(row["aligned_rows"] or 0) for row in records if row["status"] == "usable") == 1892063
        ),
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(output_dir / "dataset_inventory.csv", records)
    _write_csv(output_dir / "data_dictionary.csv", dictionary)
    _write_csv(output_dir / "annotations.csv", annotation_rows)
    (output_dir / "core_channels.txt").write_text("\n".join(core) + "\n", encoding="utf-8")
    (output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return summary


def _channel_series(ulog: ULog) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    try:
        PX4ULog(ulog).add_roll_pitch_yaw()
    except (KeyError, ValueError, IndexError, TypeError):
        pass
    result: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    seen_topics: set[str] = set()
    for dataset in ulog.data_list:
        topic = dataset.name
        if topic in seen_topics:
            continue
        seen_topics.add(topic)
        try:
            data = ulog.get_dataset(topic).data
        except (KeyError, ValueError, IndexError):
            continue
        timestamps = np.asarray(data.get("timestamp", []), dtype=np.int64)
        if timestamps.size < 2:
            continue
        order = np.argsort(timestamps)
        timestamps = timestamps[order]
        unique_mask = np.r_[True, np.diff(timestamps) > 0]
        timestamps = timestamps[unique_mask]
        for field, values in data.items():
            if field == "timestamp" or field.startswith("_padding"):
                continue
            array = np.asarray(values)
            if array.ndim != 1 or array.size != order.size or not np.issubdtype(array.dtype, np.number):
                continue
            array = array[order][unique_mask].astype(np.float64, copy=False)
            result[f"{topic}.{field}"] = (timestamps, array)
    return result


def align_ulog(
    ulog_path: Path,
    channels: list[str],
    output_path: Path,
    entry: dict[str, Any] | None = None,
    frequency_hz: float = 10.0,
) -> dict[str, Any]:
    series = _channel_series(ULog(str(ulog_path)))
    present = [name for name in channels if name in series]
    if not present:
        raise ValueError(f"none of the requested channels exist in {ulog_path}")
    start = min(int(series[name][0][0]) for name in present)
    end = max(int(series[name][0][-1]) for name in present)
    step = int(round(1_000_000 / frequency_hz))
    grid = np.arange(start, end + 1, step, dtype=np.int64)
    frame: dict[str, Any] = {"timestamp": grid}
    for name in channels:
        if name not in series:
            frame[name] = np.full(grid.shape, np.nan)
            continue
        timestamps, values = series[name]
        finite = np.isfinite(values)
        if not finite.any():
            frame[name] = np.full(grid.shape, np.nan)
        elif finite.sum() == 1:
            frame[name] = np.full(grid.shape, values[finite][0])
        else:
            frame[name] = np.interp(grid, timestamps[finite], values[finite])

    labels = np.zeros(grid.shape, dtype=np.int8)
    anomaly_types = np.full(grid.shape, "", dtype=object)
    if entry:
        class_sets = [set() for _ in range(grid.size)]
        for interval in annotation_intervals(entry):
            mask = (grid >= interval["start_us"]) & (grid <= interval["end_us"])
            labels[mask] = 1
            for index in np.flatnonzero(mask):
                class_sets[index].add(interval["class"])
        anomaly_types = np.asarray(["|".join(sorted(values)) for values in class_sets], dtype=object)
    aligned = pd.DataFrame(frame)
    aligned[channels] = aligned[channels].interpolate(limit_direction="both").fillna(0.0)
    aligned["label"] = labels
    aligned["anomaly_type"] = anomaly_types

    output_path.parent.mkdir(parents=True, exist_ok=True)
    aligned.to_csv(output_path, index=False, compression="gzip" if output_path.suffix == ".gz" else None)
    return {
        "input": str(ulog_path),
        "output": str(output_path),
        "frequency_hz": frequency_hz,
        "rows": int(grid.size),
        "requested_channels": len(channels),
        "present_channels": len(present),
        "missing_channels": len(channels) - len(present),
        "anomalous_rows": int(labels.sum()),
    }


def _read_channels(path: Path) -> list[str]:
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def cli_download(args: argparse.Namespace) -> None:
    download_annotated(Path(args.data_root), Path(args.manifest), args.workers)


def cli_inventory(args: argparse.Namespace) -> None:
    summary = build_inventory(Path(args.data_root), Path(args.output_dir), args.workers)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def cli_align(args: argparse.Namespace) -> None:
    data_root = Path(args.data_root)
    mapping = load_mapping(data_root / "mapping.json")
    if args.log_key not in mapping:
        raise KeyError(f"log key not present in mapping.json: {args.log_key}")
    result = align_ulog(
        data_root / relative_ulog_path(args.log_key),
        _read_channels(Path(args.channels)),
        Path(args.output),
        mapping[args.log_key],
        args.frequency_hz,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    download = subparsers.add_parser("download", help="download metadata and annotated ULogs")
    download.add_argument("--data-root", default="data/raw/uav_sead")
    download.add_argument("--manifest", default="reports/p1/download_manifest.csv")
    download.add_argument("--workers", type=int, default=8)
    download.set_defaults(func=cli_download)

    inventory = subparsers.add_parser("inventory", help="parse all mapped ULogs and build reports")
    inventory.add_argument("--data-root", default="data/raw/uav_sead")
    inventory.add_argument("--output-dir", default="reports/p1")
    inventory.add_argument("--workers", type=int, default=max(1, min(4, os.cpu_count() or 1)))
    inventory.set_defaults(func=cli_inventory)

    align = subparsers.add_parser("align", help="align one mapped ULog to a fixed time grid")
    align.add_argument("log_key")
    align.add_argument("--data-root", default="data/raw/uav_sead")
    align.add_argument("--channels", default="reports/p1/core_channels.txt")
    align.add_argument("--output", required=True)
    align.add_argument("--frequency-hz", type=float, default=10.0)
    align.set_defaults(func=cli_align)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
