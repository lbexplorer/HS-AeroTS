"""AeroTSBoost-compatible P2 feature and LightGBM baseline pipeline."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Iterable

import joblib
import lightgbm as lgb
import numpy as np
import pandas as pd
import yaml
from numpy.lib.format import open_memmap
from pyulog import ULog
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import average_precision_score, f1_score, precision_recall_curve, roc_auc_score

from .data_prep import TOPIC_FIELDS, annotation_intervals, load_mapping, relative_ulog_path


DESCRIPTORS = [
    "mean", "std", "min", "max", "range", "q10", "q25", "q50", "q75", "q90",
    "start", "end", "endpoint_delta", "diff_mean", "diff_std", "diff_abs_mean",
    "diff_abs_max", "lag1",
]
CLASS_TO_ID = {
    "Normal": 0,
    "External Position": 1,
    "Global Position": 2,
    "Altitude": 3,
    "Mechanical": 4,
    "Uncategorized": 5,
}
EXPECTED = {
    "logs": 1389,
    "windows": 218537,
    "positive_windows": 15694,
    "train_windows": 152340,
    "validation_windows": 32138,
    "test_windows": 34059,
    "train_positive": 9011,
    "validation_positive": 3081,
    "test_positive": 3602,
    "channels": 87,
    "features": 1566,
}


def load_config(path: str | Path) -> dict[str, Any]:
    config = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if config["data"]["protocol"] not in {"original", "purged", "leave_log_out"}:
        raise ValueError("feature construction supports original, purged, or leave_log_out")
    return config


def _resolve(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def safe_log_name(log_key: str) -> str:
    return log_key.replace("/", "__").replace(" ", "_")


def window_count(rows: int, window_size: int, horizon: int, stride: int) -> int:
    limit = rows - window_size - horizon + 1
    return 0 if limit <= 0 else (limit - 1) // stride + 1


def split_counts(n: int, train_fraction: float, validation_fraction: float, purge_n: int = 0) -> tuple[int, int, int]:
    if n <= 0:
        return 0, 0, 0
    train_end = max(1, int(n * train_fraction))
    validation_end = min(n, train_end + max(1, int(n * validation_fraction)))
    if purge_n:
        train = max(0, train_end - purge_n)
        val_start = min(n, train_end + purge_n)
        val_end = max(val_start, validation_end - purge_n)
        test_start = min(n, validation_end + purge_n)
        return train, max(0, val_end - val_start), max(0, n - test_start)
    return train_end, max(0, validation_end - train_end), max(0, n - validation_end)


def split_window_indices(n: int, train_fraction: float, validation_fraction: float, purge_n: int = 0) -> dict[str, np.ndarray]:
    train_end = max(1, int(n * train_fraction)) if n else 0
    validation_end = min(n, train_end + max(1, int(n * validation_fraction))) if n else 0
    if purge_n:
        return {
            "train": np.arange(0, max(0, train_end - purge_n), dtype=np.int64),
            "validation": np.arange(min(n, train_end + purge_n), max(min(n, train_end + purge_n), validation_end - purge_n), dtype=np.int64),
            "test": np.arange(min(n, validation_end + purge_n), n, dtype=np.int64),
        }
    return {
        "train": np.arange(0, train_end, dtype=np.int64),
        "validation": np.arange(train_end, validation_end, dtype=np.int64),
        "test": np.arange(validation_end, n, dtype=np.int64),
    }


def leave_log_out_assignments(records: list[dict[str, Any]], train_fraction: float, validation_fraction: float, seed: int) -> dict[str, str]:
    """Assign complete flight logs to deterministic, label-stratified partitions."""
    assignments: dict[str, str] = {}
    by_label: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        intervals = annotation_intervals(record["entry"])
        label = str(intervals[0]["class"]) if intervals else "Normal"
        by_label.setdefault(label, []).append(record)
    for label, part in by_label.items():
        ordered = sorted(
            part,
            key=lambda record: hashlib.sha256(f"{seed}:{label}:{record['log_key']}".encode()).hexdigest(),
        )
        n = len(ordered)
        train_end = max(1, int(n * train_fraction))
        validation_end = min(n, train_end + max(1, int(n * validation_fraction)))
        for index, record in enumerate(ordered):
            assignments[record["log_key"]] = "train" if index < train_end else "validation" if index < validation_end else "test"
    return assignments


def _interpolate(grid: np.ndarray, timestamps: np.ndarray, values: np.ndarray) -> np.ndarray:
    with np.errstate(invalid="ignore", over="ignore"):
        timestamps = np.asarray(timestamps, dtype=np.float64)
        values = np.asarray(values, dtype=np.float64)
    # Timeout-terminated replay logs can contain a partial final record with
    # finite but impossible float payloads.  No P1 core telemetry channel has
    # a physically meaningful magnitude near this conservative guardrail.
    valid = np.isfinite(timestamps) & np.isfinite(values) & (np.abs(values) <= 1e12)
    if valid.sum() < 2:
        return np.full(len(grid), np.nan, dtype=np.float32)
    timestamps = timestamps[valid]
    values = values[valid]
    order = np.argsort(timestamps)
    timestamps = timestamps[order]
    values = values[order]
    timestamps, first = np.unique(timestamps, return_index=True)
    values = values[first]
    if len(timestamps) < 2:
        return np.full(len(grid), np.nan, dtype=np.float32)
    return np.interp(grid.astype(np.float64), timestamps, values).astype(np.float32)


def _ulog_time_bounds(ulog: Any) -> tuple[int, int]:
    """Return sane ULog bounds, tolerating timeout-corrupted metadata.

    Some PX4 replay logs end with an unsigned timestamp underflow in the ULog
    metadata when the process is stopped by ``timeout``.  Normal logs retain
    their original metadata bounds; only invalid or excessive ranges fall back
    to the timestamps carried by the parsed telemetry datasets.
    """
    start = int(ulog.start_timestamp)
    stop = int(ulog.last_timestamp)
    if stop > start and (stop - start) / 1_000_000 <= 7200:
        return start, stop

    timestamp_parts = []
    for dataset in ulog.data_list:
        if "timestamp" not in dataset.data:
            continue
        timestamps = np.asarray(dataset.data["timestamp"])
        valid = np.isfinite(timestamps) & (timestamps >= 0) & (timestamps < 2**63)
        if valid.any():
            timestamp_parts.append(timestamps[valid].astype(np.int64, copy=False))
    if not timestamp_parts:
        raise ValueError("invalid ULog time range and no valid topic timestamps")
    derived_start = min(int(values.min()) for values in timestamp_parts)
    derived_stop = max(int(values.max()) for values in timestamp_parts)
    if derived_stop <= derived_start or (derived_stop - derived_start) / 1_000_000 > 7200:
        raise ValueError("invalid or excessive ULog time range")
    return derived_start, derived_stop


def align_log_arrays(ulog_path: Path, channels: list[str], entry: dict[str, Any], frequency_hz: float) -> tuple[np.ndarray, np.ndarray, np.ndarray, int, int]:
    ulog = ULog(str(ulog_path), message_name_filter_list=list(TOPIC_FIELDS))
    start, stop = _ulog_time_bounds(ulog)
    step = max(1, int(round(1_000_000 / frequency_hz)))
    rows = int(np.floor((stop - start) / step)) + 1
    grid = start + np.arange(rows, dtype=np.int64) * step

    wanted = set(channels)
    series: dict[str, np.ndarray] = {}
    seen_topics: set[str] = set()
    for dataset in ulog.data_list:
        if dataset.name in seen_topics or dataset.name not in TOPIC_FIELDS or "timestamp" not in dataset.data:
            continue
        seen_topics.add(dataset.name)
        timestamps = dataset.data["timestamp"]
        for field in TOPIC_FIELDS[dataset.name]:
            name = f"{dataset.name}.{field}"
            if name in wanted and field in dataset.data:
                series[name] = _interpolate(grid, timestamps, dataset.data[field])

    x = np.zeros((rows, len(channels)), dtype=np.float32)
    for index, channel in enumerate(channels):
        if channel not in series:
            continue
        values = series[channel]
        finite = np.isfinite(values)
        if finite.any():
            first, last = np.flatnonzero(finite)[[0, -1]]
            values[:first] = values[first]
            values[last + 1 :] = values[last]
            if not finite.all():
                positions = np.arange(rows)
                values[~finite] = np.interp(positions[~finite], positions[finite], values[finite])
            x[:, index] = np.nan_to_num(values, nan=0.0, posinf=0.0, neginf=0.0)

    labels = np.zeros(rows, dtype=np.int8)
    anomaly_types = np.zeros(rows, dtype=np.int16)
    for interval in annotation_intervals(entry):
        mask = (grid >= interval["start_us"]) & (grid <= interval["end_us"])
        labels[mask] = 1
        anomaly_types[mask] = CLASS_TO_ID.get(interval["class"], CLASS_TO_ID["Uncategorized"])
    return x, labels, anomaly_types, start, step


def _prepare_one(args: tuple[str, str, str, list[str], dict[str, Any], float, int]) -> dict[str, Any]:
    log_key, ulog_name, output_name, channels, entry, frequency_hz, expected_rows = args
    output = Path(output_name)
    if output.exists():
        try:
            with np.load(output, allow_pickle=False) as cached:
                if cached["x"].shape == (expected_rows, len(channels)):
                    return {"log_key": log_key, "status": "cached", "path": str(output), "rows": expected_rows,
                            "positive_rows": int(cached["labels"].sum())}
        except Exception:
            pass
    try:
        x, labels, types, start, step = align_log_arrays(Path(ulog_name), channels, entry, frequency_hz)
        if len(x) != expected_rows:
            raise ValueError(f"row mismatch: expected {expected_rows}, got {len(x)}")
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_suffix(".tmp.npz")
        np.savez_compressed(temporary, x=x, labels=labels, anomaly_types=types,
                            start_timestamp_us=np.int64(start), step_us=np.int64(step))
        temporary.replace(output)
        return {"log_key": log_key, "status": "ok", "path": str(output), "rows": len(x),
                "positive_rows": int(labels.sum())}
    except Exception as exc:
        return {"log_key": log_key, "status": "error", "path": str(output), "rows": 0,
                "positive_rows": 0, "error": f"{type(exc).__name__}: {exc}"}


def _write_csv(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    rows = list(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def prepare_aligned(config: dict[str, Any], root: Path, workers: int) -> dict[str, Any]:
    paths, data = config["paths"], config["data"]
    data_root = _resolve(root, paths["data_root"])
    inventory = pd.read_csv(_resolve(root, paths["inventory"]))
    inventory = inventory.loc[inventory["status"].eq("usable")].sort_values("log_key")
    channels = [line.strip() for line in _resolve(root, paths["channels"]).read_text(encoding="utf-8").splitlines() if line.strip()]
    mapping = load_mapping(data_root / "mapping.json")
    aligned_dir = _resolve(root, paths["aligned_dir"])
    tasks = []
    for row in inventory.itertuples(index=False):
        output = aligned_dir / f"{safe_log_name(row.log_key)}.npz"
        tasks.append((row.log_key, str(data_root / relative_ulog_path(row.log_key)), str(output), channels,
                      mapping[row.log_key], float(data["frequency_hz"]), int(row.aligned_rows)))

    results: list[dict[str, Any]] = []
    if workers <= 1:
        iterator = map(_prepare_one, tasks)
        for index, result in enumerate(iterator, 1):
            results.append(result)
            if index % 25 == 0:
                print(f"aligned {index}/{len(tasks)}", flush=True)
    else:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(_prepare_one, task) for task in tasks]
            for index, future in enumerate(as_completed(futures), 1):
                results.append(future.result())
                if index % 25 == 0:
                    print(f"aligned {index}/{len(tasks)}", flush=True)
    results.sort(key=lambda row: row["log_key"])
    manifest = _resolve(root, paths["report_dir"]) / "aligned_manifest.csv"
    _write_csv(manifest, results)
    statuses = pd.Series([row["status"] for row in results]).value_counts().to_dict()
    summary = {"logs": len(results), "status_counts": statuses,
               "rows": int(sum(row["rows"] for row in results if row["status"] in {"ok", "cached"})),
               "positive_rows": int(sum(row["positive_rows"] for row in results if row["status"] in {"ok", "cached"}))}
    if sum(statuses.get(name, 0) for name in ("ok", "cached")) != EXPECTED["logs"]:
        raise RuntimeError(f"aligned preparation incomplete: {summary}")
    return summary


def descriptor_batch(x: np.ndarray) -> np.ndarray:
    diff = np.diff(x, axis=1)
    quantiles = np.quantile(x, [0.1, 0.25, 0.5, 0.75, 0.9], axis=1).transpose(1, 0, 2)
    centered = x - x.mean(axis=1, keepdims=True)
    lag_num = (centered[:, 1:, :] * centered[:, :-1, :]).mean(axis=1)
    lag_den = centered[:, 1:, :].std(axis=1) * centered[:, :-1, :].std(axis=1)
    lag1 = lag_num / np.maximum(lag_den, 1e-6)
    groups = [
        x.mean(axis=1), x.std(axis=1), x.min(axis=1), x.max(axis=1), x.max(axis=1) - x.min(axis=1),
        *[quantiles[:, index, :] for index in range(5)], x[:, 0, :], x[:, -1, :],
        x[:, -1, :] - x[:, 0, :], diff.mean(axis=1), diff.std(axis=1),
        np.abs(diff).mean(axis=1), np.abs(diff).max(axis=1), lag1,
    ]
    return np.nan_to_num(np.concatenate(groups, axis=1), nan=0.0, posinf=0.0, neginf=0.0).astype(np.float32)


def _training_weights(rows: int, starts: np.ndarray, window_size: int) -> np.ndarray:
    delta = np.zeros(rows + 1, dtype=np.int32)
    np.add.at(delta, starts, 1)
    np.add.at(delta, starts + window_size, -1)
    return np.cumsum(delta[:-1])


def fit_window_standardizer(records: list[dict[str, Any]], data: dict[str, Any], llo_assignments: dict[str, str] | None = None) -> tuple[np.ndarray, np.ndarray, int]:
    channels = int(records[0]["channels"])
    sums = np.zeros(channels, dtype=np.float64)
    squares = np.zeros(channels, dtype=np.float64)
    samples = 0
    purge_n = int(math.ceil((data["window_size"] + data["horizon"]) / data["stride"])) if data["protocol"] == "purged" else 0
    for index, record in enumerate(records, 1):
        with np.load(record["path"], allow_pickle=False) as shard:
            x = shard["x"]
        n_windows = window_count(len(x), data["window_size"], data["horizon"], data["stride"])
        if llo_assignments is not None:
            split = {name: np.arange(n_windows, dtype=np.int64) if llo_assignments[record["log_key"]] == name else np.empty(0, dtype=np.int64) for name in ("train", "validation", "test")}
        else:
            split = split_window_indices(n_windows, data["train_fraction"], data["validation_fraction"], purge_n)
        starts = split["train"] * data["stride"]
        weights = _training_weights(len(x), starts, data["window_size"])
        for lo in range(0, len(x), 8192):
            hi = min(len(x), lo + 8192)
            values = np.asarray(x[lo:hi], dtype=np.float64)
            weight = weights[lo:hi].astype(np.float64)[:, None]
            sums += (values * weight).sum(axis=0)
            squares += (values * values * weight).sum(axis=0)
        samples += int(weights.sum())
        if index % 100 == 0:
            print(f"scaler {index}/{len(records)}", flush=True)
    mean = sums / max(1, samples)
    variance = np.maximum(squares / max(1, samples) - mean * mean, 0.0)
    std = np.sqrt(variance)
    std[std < 1e-6] = 1.0
    return mean.astype(np.float32), std.astype(np.float32), samples


def _create_feature_arrays(directory: Path, counts: dict[str, int], feature_count: int) -> dict[str, dict[str, np.memmap]]:
    directory.mkdir(parents=True, exist_ok=True)
    arrays: dict[str, dict[str, np.memmap]] = {}
    for split, count in counts.items():
        arrays[split] = {
            "x": open_memmap(directory / f"x_{split}.npy", mode="w+", dtype=np.float32, shape=(count, feature_count)),
            "y": open_memmap(directory / f"y_{split}.npy", mode="w+", dtype=np.int8, shape=(count,)),
            "type": open_memmap(directory / f"type_{split}.npy", mode="w+", dtype=np.int16, shape=(count,)),
            "group": open_memmap(directory / f"group_{split}.npy", mode="w+", dtype=np.int32, shape=(count,)),
            "start": open_memmap(directory / f"start_{split}.npy", mode="w+", dtype=np.int32, shape=(count,)),
        }
    return arrays


def _majority_types(types: np.ndarray) -> np.ndarray:
    counts = np.stack([(types == class_id).sum(axis=1) for class_id in range(1, 6)], axis=1)
    best = counts.argmax(axis=1) + 1
    best[counts.max(axis=1) == 0] = 0
    return best.astype(np.int16)


def build_features(config: dict[str, Any], root: Path) -> dict[str, Any]:
    paths, data = config["paths"], config["data"]
    report_dir = _resolve(root, paths["report_dir"])
    manifest_path = _resolve(root, paths.get("aligned_manifest", str(report_dir / "aligned_manifest.csv")))
    manifest = pd.read_csv(manifest_path).sort_values("log_key")
    manifest = manifest.loc[manifest["status"].isin(["ok", "cached"])]
    channels = [line.strip() for line in _resolve(root, paths["channels"]).read_text(encoding="utf-8").splitlines() if line.strip()]
    mapping = load_mapping(_resolve(root, paths["data_root"]) / "mapping.json")
    records = [{"log_key": row.log_key, "path": Path(row.path), "rows": int(row.rows), "channels": len(channels), "entry": mapping[row.log_key]}
               for row in manifest.itertuples(index=False)]
    if len(records) != EXPECTED["logs"]:
        raise RuntimeError(f"expected {EXPECTED['logs']} aligned logs, got {len(records)}")

    purge_n = int(math.ceil((data["window_size"] + data["horizon"]) / data["stride"])) if data["protocol"] == "purged" else 0
    llo_assignments = leave_log_out_assignments(records, data["train_fraction"], data["validation_fraction"], int(config["seed"])) if data["protocol"] == "leave_log_out" else None
    counts = {name: 0 for name in ("train", "validation", "test")}
    total_windows = 0
    for record in records:
        n = window_count(record["rows"], data["window_size"], data["horizon"], data["stride"])
        total_windows += n
        if llo_assignments is not None:
            counts[llo_assignments[record["log_key"]]] += n
        else:
            tr, va, te = split_counts(n, data["train_fraction"], data["validation_fraction"], purge_n)
            for name, value in zip(counts, (tr, va, te)):
                counts[name] += value

    mean, std, scaler_samples = fit_window_standardizer(records, data, llo_assignments)
    feature_dir = _resolve(root, paths["feature_dir"])
    feature_count = len(channels) * len(DESCRIPTORS)
    arrays = _create_feature_arrays(feature_dir, counts, feature_count)
    offsets = {name: 0 for name in counts}
    window_axis = np.arange(data["window_size"], dtype=np.int64)
    label_axis = np.arange(data["window_size"] + data["horizon"], dtype=np.int64)

    for group_id, record in enumerate(records):
        with np.load(record["path"], allow_pickle=False) as shard:
            x = (shard["x"].astype(np.float32) - mean) / std
            labels = shard["labels"].astype(np.int8)
            types = shard["anomaly_types"].astype(np.int16)
        n = window_count(len(x), data["window_size"], data["horizon"], data["stride"])
        if llo_assignments is not None:
            assigned = llo_assignments[record["log_key"]]
            splits = {name: np.arange(n, dtype=np.int64) if name == assigned else np.empty(0, dtype=np.int64) for name in counts}
        else:
            splits = split_window_indices(n, data["train_fraction"], data["validation_fraction"], purge_n)
        for split_name, window_indices in splits.items():
            for lo in range(0, len(window_indices), data["batch_size"]):
                indices = window_indices[lo : lo + data["batch_size"]]
                starts = indices * data["stride"]
                windows = x[starts[:, None] + window_axis[None, :]]
                label_positions = starts[:, None] + label_axis[None, :]
                out_lo = offsets[split_name]
                out_hi = out_lo + len(indices)
                arrays[split_name]["x"][out_lo:out_hi] = descriptor_batch(windows)
                label_segments = labels[label_positions]
                type_segments = types[label_positions]
                arrays[split_name]["y"][out_lo:out_hi] = label_segments.max(axis=1)
                arrays[split_name]["type"][out_lo:out_hi] = _majority_types(type_segments)
                arrays[split_name]["group"][out_lo:out_hi] = group_id
                arrays[split_name]["start"][out_lo:out_hi] = starts
                offsets[split_name] = out_hi
        if (group_id + 1) % 50 == 0:
            print(f"features {group_id + 1}/{len(records)}", flush=True)

    for split_arrays in arrays.values():
        for array in split_arrays.values():
            array.flush()
    positives = {name: int(np.asarray(arrays[name]["y"]).sum()) for name in counts}
    feature_rows = []
    for descriptor_index, descriptor in enumerate(DESCRIPTORS):
        for channel_index, channel in enumerate(channels):
            feature_rows.append({"feature_index": descriptor_index * len(channels) + channel_index,
                                 "feature": f"{descriptor}__{channel}", "descriptor": descriptor,
                                 "channel": channel, "topic": channel.split(".", 1)[0]})
    _write_csv(report_dir / "feature_dictionary.csv", feature_rows)
    _write_csv(report_dir / "group_dictionary.csv", [
        {"group": index, "log_key": record["log_key"], "aligned_path": str(record["path"])}
        for index, record in enumerate(records)
    ])
    summary = {
        "protocol": data["protocol"], "logs": len(records), "windows": total_windows,
        "positive_windows": sum(positives.values()), "channels": len(channels), "features": feature_count,
        "split_counts": counts, "split_positive_counts": positives, "scaler_window_samples": scaler_samples,
        "expected": EXPECTED if data["protocol"] == "original" else None,
    }
    if llo_assignments is not None:
        assignment_rows = [{"log_key": record["log_key"], "split": llo_assignments[record["log_key"]]} for record in records]
        _write_csv(report_dir / "leave_log_out_assignments.csv", assignment_rows)
        summary["log_split_counts"] = pd.Series(list(llo_assignments.values())).value_counts().sort_index().to_dict()
    if data["protocol"] == "original":
        actual = {"logs": len(records), "windows": total_windows, "positive_windows": sum(positives.values()),
                  "train_windows": counts["train"], "validation_windows": counts["validation"],
                  "test_windows": counts["test"], "train_positive": positives["train"],
                  "validation_positive": positives["validation"], "test_positive": positives["test"],
                  "channels": len(channels), "features": feature_count}
        summary["benchmark_matches"] = {key: actual[key] == value for key, value in EXPECTED.items()}
        if not all(summary["benchmark_matches"].values()):
            raise RuntimeError(f"P2 feature benchmark mismatch: {summary}")
    np.save(feature_dir / "scaler_mean.npy", mean)
    np.save(feature_dir / "scaler_std.npy", std)
    (report_dir / "feature_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return summary


def best_f1_threshold(labels: np.ndarray, scores: np.ndarray) -> tuple[float, float]:
    precision, recall, thresholds = precision_recall_curve(labels, scores)
    values = 2 * precision * recall / np.maximum(precision + recall, 1e-12)
    index = int(np.nanargmax(values))
    threshold = float(thresholds[min(index, len(thresholds) - 1)]) if len(thresholds) else 0.5
    return float(values[index]), threshold


def _segments(binary: np.ndarray) -> list[tuple[int, int]]:
    binary = np.asarray(binary, dtype=bool)
    starts = np.flatnonzero(binary & np.r_[True, ~binary[:-1]])
    ends = np.flatnonzero(binary & np.r_[~binary[1:], True])
    return list(zip(starts.tolist(), ends.tolist()))


def event_f1(labels: np.ndarray, scores: np.ndarray, threshold: float, groups: np.ndarray | None = None) -> dict[str, float]:
    predicted = np.asarray(scores) >= threshold
    labels = np.asarray(labels, dtype=bool)
    if groups is None:
        groups = np.zeros(len(labels), dtype=np.int32)
    matched_true = matched_pred = true_total = pred_total = 0
    for group in np.unique(groups):
        keep = groups == group
        true_events = _segments(labels[keep])
        pred_events = _segments(predicted[keep])
        true_total += len(true_events)
        pred_total += len(pred_events)
        used: set[int] = set()
        for pred in pred_events:
            for index, true in enumerate(true_events):
                if index not in used and pred[0] <= true[1] and true[0] <= pred[1]:
                    used.add(index)
                    matched_true += 1
                    matched_pred += 1
                    break
    precision = matched_pred / max(1, pred_total)
    recall = matched_true / max(1, true_total)
    return {"event_precision": precision, "event_recall": recall,
            "event_f1": 2 * precision * recall / max(precision + recall, 1e-12)}


def point_metrics(labels: np.ndarray, scores: np.ndarray, threshold: float | None = None) -> dict[str, float]:
    best_f1, best_threshold = best_f1_threshold(labels, scores)
    operating = best_threshold if threshold is None else threshold
    predictions = np.asarray(scores) >= operating
    return {"auroc": float(roc_auc_score(labels, scores)),
            "auprc": float(average_precision_score(labels, scores)), "best_f1": best_f1,
            "threshold": float(operating), "f1_at_threshold": float(f1_score(labels, predictions, zero_division=0)),
            "positive_rate": float(predictions.mean())}


def evaluate_scores(labels: np.ndarray, scores: np.ndarray, groups: np.ndarray, threshold: float | None = None) -> dict[str, float]:
    metrics = point_metrics(labels, scores, threshold)
    metrics.update(event_f1(labels, scores, metrics["threshold"]))
    aware = event_f1(labels, scores, metrics["threshold"], groups)
    metrics.update({f"log_aware_{key}": value for key, value in aware.items()})
    return metrics


def train_baseline(config: dict[str, Any], root: Path, seeds: list[int] | None = None) -> dict[str, Any]:
    paths = config["paths"]
    feature_dir = _resolve(root, paths["feature_dir"])
    report_dir = _resolve(root, paths["report_dir"])
    output_dir = report_dir / "baseline_runs"
    output_dir.mkdir(parents=True, exist_ok=True)
    x_train = np.load(feature_dir / "x_train.npy", mmap_mode="r")
    y_train = np.load(feature_dir / "y_train.npy", mmap_mode="r").astype(np.int32)
    x_val = np.load(feature_dir / "x_validation.npy", mmap_mode="r")
    y_val = np.load(feature_dir / "y_validation.npy", mmap_mode="r").astype(np.int32)
    x_test = np.load(feature_dir / "x_test.npy", mmap_mode="r")
    y_test = np.load(feature_dir / "y_test.npy", mmap_mode="r").astype(np.int32)
    val_groups = np.load(feature_dir / "group_validation.npy", mmap_mode="r")
    test_groups = np.load(feature_dir / "group_test.npy", mmap_mode="r")
    val_starts = np.load(feature_dir / "start_validation.npy", mmap_mode="r")
    test_starts = np.load(feature_dir / "start_test.npy", mmap_mode="r")
    seeds = seeds or list(config["experiment"]["seeds"])
    rows = []
    for seed in seeds:
        params = dict(config["model"])
        early_stopping = int(params.pop("early_stopping_rounds"))
        model = lgb.LGBMClassifier(objective="binary", random_state=seed,
                                   n_jobs=int(config["experiment"]["n_jobs"]), verbosity=-1, **params)
        model.fit(x_train, y_train, eval_set=[(x_val, y_val)], eval_metric="average_precision",
                  callbacks=[lgb.early_stopping(early_stopping), lgb.log_evaluation(100)])
        val_scores = model.predict_proba(x_val)[:, 1]
        test_scores = model.predict_proba(x_test)[:, 1]
        val_metrics = evaluate_scores(y_val, val_scores, val_groups)
        test_best = evaluate_scores(y_test, test_scores, test_groups)
        test_frozen = evaluate_scores(y_test, test_scores, test_groups, val_metrics["threshold"])
        row: dict[str, Any] = {"seed": seed, "best_iteration": int(model.best_iteration_ or 0)}
        row.update({f"val_{key}": value for key, value in val_metrics.items()})
        row.update({f"test_{key}": value for key, value in test_best.items()})
        row.update({f"test_at_val_threshold_{key}": value for key, value in test_frozen.items()})
        rows.append(row)
        run_dir = output_dir / f"seed{seed}"
        run_dir.mkdir(parents=True, exist_ok=True)
        joblib.dump(model, run_dir / "lightgbm.joblib")
        pd.DataFrame({"label": y_val, "group": val_groups, "start": val_starts, "score": val_scores}).to_csv(run_dir / "val_scores.csv", index=False)
        pd.DataFrame({"label": y_test, "group": test_groups, "start": test_starts, "score": test_scores}).to_csv(run_dir / "test_scores.csv", index=False)
        (run_dir / "metrics.json").write_text(json.dumps(row, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(json.dumps({"seed": seed, "test_auprc": row["test_auprc"], "test_auroc": row["test_auroc"],
                          "test_best_f1": row["test_best_f1"], "test_event_f1": row["test_event_f1"]}), flush=True)
    _write_csv(report_dir / "seed_metrics.csv", rows)
    metric_names = ["test_auroc", "test_auprc", "test_best_f1", "test_event_f1",
                    "test_at_val_threshold_f1_at_threshold", "test_at_val_threshold_log_aware_event_f1"]
    summary = {"seeds": seeds, "runs": len(rows), "metrics": {}}
    for name in metric_names:
        values = np.asarray([row[name] for row in rows], dtype=float)
        summary["metrics"][name] = {"mean": float(values.mean()), "std": float(values.std(ddof=1)) if len(values) > 1 else 0.0}
    summary["paper_reference"] = {"test_auroc_mean": 0.9516, "test_auprc_mean": 0.7516,
                                  "test_best_f1_mean": 0.6860, "test_event_f1_mean": 0.5342}
    (report_dir / "baseline_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return summary


def train_random_forest_baseline(config: dict[str, Any], root: Path, seeds: list[int] | None = None) -> dict[str, Any]:
    """Train a conventional binary RF on exactly the feature/split protocol used by LightGBM."""
    paths = config["paths"]
    feature_dir = _resolve(root, paths["feature_dir"])
    report_dir = _resolve(root, paths["report_dir"])
    rf_config = dict(config["random_forest"])
    output_dir = report_dir / "random_forest_runs"
    output_dir.mkdir(parents=True, exist_ok=True)
    x_train, y_train = np.load(feature_dir / "x_train.npy", mmap_mode="r"), np.load(feature_dir / "y_train.npy", mmap_mode="r")
    x_val, y_val = np.load(feature_dir / "x_validation.npy", mmap_mode="r"), np.load(feature_dir / "y_validation.npy", mmap_mode="r")
    x_test, y_test = np.load(feature_dir / "x_test.npy", mmap_mode="r"), np.load(feature_dir / "y_test.npy", mmap_mode="r")
    val_groups, test_groups = np.load(feature_dir / "group_validation.npy", mmap_mode="r"), np.load(feature_dir / "group_test.npy", mmap_mode="r")
    val_starts, test_starts = np.load(feature_dir / "start_validation.npy", mmap_mode="r"), np.load(feature_dir / "start_test.npy", mmap_mode="r")
    seeds = seeds or list(config["experiment"]["seeds"])
    rows = []
    for seed in seeds:
        model = RandomForestClassifier(random_state=seed, n_jobs=int(rf_config.pop("n_jobs", config["experiment"]["n_jobs"])), **rf_config)
        model.fit(x_train, y_train)
        val_scores, test_scores = model.predict_proba(x_val)[:, 1], model.predict_proba(x_test)[:, 1]
        val_metrics = evaluate_scores(y_val, val_scores, val_groups)
        test_best, test_frozen = evaluate_scores(y_test, test_scores, test_groups), evaluate_scores(y_test, test_scores, test_groups, val_metrics["threshold"])
        row = {"seed": seed, **{f"val_{key}": value for key, value in val_metrics.items()}, **{f"test_{key}": value for key, value in test_best.items()}, **{f"test_at_val_threshold_{key}": value for key, value in test_frozen.items()}}
        rows.append(row)
        run_dir = output_dir / f"seed{seed}"
        run_dir.mkdir(parents=True, exist_ok=True)
        joblib.dump(model, run_dir / "random_forest.joblib")
        pd.DataFrame({"label": y_val, "group": val_groups, "start": val_starts, "score": val_scores}).to_csv(run_dir / "val_scores.csv", index=False)
        pd.DataFrame({"label": y_test, "group": test_groups, "start": test_starts, "score": test_scores}).to_csv(run_dir / "test_scores.csv", index=False)
        (run_dir / "metrics.json").write_text(json.dumps(row, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_csv(report_dir / "random_forest_seed_metrics.csv", rows)
    metrics = {name: {"mean": float(np.mean([row[name] for row in rows])), "std": float(np.std([row[name] for row in rows], ddof=1)) if len(rows) > 1 else 0.0} for name in ("test_auroc", "test_auprc", "test_best_f1", "test_event_f1", "test_at_val_threshold_f1_at_threshold")}
    summary = {"method": "random_forest_binary", "seeds": seeds, "runs": len(rows), "protocol": config["data"]["protocol"], "metrics": metrics}
    (report_dir / "random_forest_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="configs/p2_aerotsboost.yaml")
    sub = parser.add_subparsers(dest="command", required=True)
    prepare = sub.add_parser("prepare-aligned", help="convert usable ULogs to compact aligned arrays")
    prepare.add_argument("--workers", type=int, default=max(1, min(4, os.cpu_count() or 1)))
    sub.add_parser("build-features", help="fit train-only scaler and create 1,566-D descriptor arrays")
    train = sub.add_parser("train", help="train and evaluate class-balanced LightGBM")
    train.add_argument("--seeds", type=int, nargs="*")
    random_forest = sub.add_parser("train-random-forest", help="train a conventional RF under the identical feature and split protocol")
    random_forest.add_argument("--seeds", type=int, nargs="*")
    run = sub.add_parser("run", help="run all P2 stages")
    run.add_argument("--workers", type=int, default=max(1, min(4, os.cpu_count() or 1)))
    run.add_argument("--seeds", type=int, nargs="*")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    root = Path.cwd()
    config = load_config(args.config)
    if args.command in {"prepare-aligned", "run"}:
        print(json.dumps(prepare_aligned(config, root, args.workers), indent=2, ensure_ascii=False), flush=True)
    if args.command in {"build-features", "run"}:
        print(json.dumps(build_features(config, root), indent=2, ensure_ascii=False), flush=True)
    if args.command in {"train", "run"}:
        print(json.dumps(train_baseline(config, root, args.seeds), indent=2, ensure_ascii=False), flush=True)
    if args.command == "train-random-forest":
        print(json.dumps(train_random_forest_baseline(config, root, args.seeds), indent=2, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
