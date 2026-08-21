"""P6 zero-shot ALFA external validation with semantically shared telemetry."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import joblib
import lightgbm as lgb
import numpy as np
import pandas as pd
import yaml

from .baseline import DESCRIPTORS, descriptor_batch, evaluate_scores


def load_config(path: str | Path) -> dict[str, Any]:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def _resolve(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def selected_feature_indices(feature_dictionary: pd.DataFrame, channels: list[str]) -> np.ndarray:
    """Return descriptor-major columns matching a fixed semantic channel order."""
    lookup = {
        (row.descriptor, row.channel): int(row.feature_index)
        for row in feature_dictionary.itertuples(index=False)
    }
    missing = [(descriptor, channel) for descriptor in DESCRIPTORS for channel in channels
               if (descriptor, channel) not in lookup]
    if missing:
        raise ValueError(f"missing mapped features: {missing[:5]}")
    return np.asarray([lookup[(descriptor, channel)] for descriptor in DESCRIPTORS for channel in channels], dtype=np.int32)


def window_binary_labels(labels: np.ndarray, window_size: int, horizon: int, stride: int) -> tuple[np.ndarray, np.ndarray]:
    limit = len(labels) - window_size - horizon + 1
    if limit <= 0:
        return np.empty(0, dtype=np.int8), np.empty(0, dtype=np.int32)
    starts = np.arange(0, limit, stride, dtype=np.int32)
    axis = np.arange(window_size + horizon, dtype=np.int32)
    output = np.asarray(labels)[starts[:, None] + axis[None, :]].max(axis=1).astype(np.int8)
    return output, starts


def _read_numeric_series(path: Path, field: str) -> tuple[np.ndarray, np.ndarray]:
    frame = pd.read_csv(path, usecols=["%time", field])
    time = pd.to_numeric(frame["%time"], errors="coerce").to_numpy(np.float64) / 1e9
    value = pd.to_numeric(frame[field], errors="coerce").to_numpy(np.float64)
    keep = np.isfinite(time) & np.isfinite(value)
    time, value = time[keep], value[keep]
    if len(time) == 0:
        raise ValueError(f"no finite values in {path.name}:{field}")
    unique, indices = np.unique(time, return_index=True)
    return unique, value[indices]


def align_alfa_sequence(sequence_dir: Path, mapping: list[dict[str, str]], frequency_hz: float) -> tuple[np.ndarray, np.ndarray, float | None]:
    series: list[tuple[np.ndarray, np.ndarray]] = []
    for item in mapping:
        path = sequence_dir / f"{sequence_dir.name}-{item['file_suffix']}.csv"
        series.append(_read_numeric_series(path, item["field"]))
    start = max(values[0][0] for values in series)
    end = min(values[0][-1] for values in series)
    if end <= start:
        raise ValueError(f"mapped ALFA topics do not overlap in {sequence_dir.name}")
    step = 1.0 / frequency_hz
    grid = np.arange(start, end + step * 0.25, step, dtype=np.float64)
    aligned = np.column_stack([np.interp(grid, time, value) for time, value in series]).astype(np.float32)
    failure_files = sorted(sequence_dir.glob(f"{sequence_dir.name}-failure_status-*.csv"))
    onset: float | None = None
    for path in failure_files:
        frame = pd.read_csv(path, usecols=["%time"])
        values = pd.to_numeric(frame["%time"], errors="coerce").dropna()
        if len(values):
            candidate = float(values.iloc[0]) / 1e9
            onset = candidate if onset is None else min(onset, candidate)
    return aligned, grid, onset


def _failure_family(sequence_dir: Path) -> str:
    files = sorted(sequence_dir.glob(f"{sequence_dir.name}-failure_status-*.csv"))
    if not files:
        return "No Failure"
    return files[0].stem.rsplit("failure_status-", 1)[-1].title()


def build_alfa_features(config: dict[str, Any], root: Path) -> dict[str, Any]:
    paths, data = config["paths"], config["data"]
    alfa_root = _resolve(root, paths["alfa_processed_dir"])
    output_dir = _resolve(root, paths["alfa_feature_dir"])
    report_dir = _resolve(root, paths["report_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)
    mapping = list(config["semantic_channels"])
    channels = [item["uav_sead_channel"] for item in mapping]
    p2_channels = [line.strip() for line in _resolve(root, paths["p2_channels"]).read_text(encoding="utf-8").splitlines() if line.strip()]
    channel_indices = np.asarray([p2_channels.index(channel) for channel in channels], dtype=np.int32)
    scaler_mean = np.load(_resolve(root, paths["p2_feature_dir"]) / "scaler_mean.npy")[channel_indices]
    scaler_std = np.load(_resolve(root, paths["p2_feature_dir"]) / "scaler_std.npy")[channel_indices]

    feature_parts, label_parts, group_parts, time_parts = [], [], [], []
    inventory: list[dict[str, Any]] = []
    sequence_dirs = sorted(path for path in alfa_root.iterdir() if path.is_dir() and "no_ground_truth" not in path.name)
    for group, sequence_dir in enumerate(sequence_dirs):
        aligned, grid, onset = align_alfa_sequence(sequence_dir, mapping, float(data["frequency_hz"]))
        standardized = (aligned - scaler_mean) / scaler_std
        point_labels = np.zeros(len(grid), dtype=np.int8) if onset is None else (grid >= onset).astype(np.int8)
        labels, starts = window_binary_labels(point_labels, int(data["window_size"]), int(data["horizon"]), int(data["stride"]))
        if len(starts) == 0:
            continue
        window_axis = np.arange(int(data["window_size"]), dtype=np.int32)
        for lo in range(0, len(starts), int(data["batch_size"])):
            batch_starts = starts[lo: lo + int(data["batch_size"])]
            windows = standardized[batch_starts[:, None] + window_axis[None, :]]
            feature_parts.append(descriptor_batch(windows))
        label_parts.append(labels)
        group_parts.append(np.full(len(labels), group, dtype=np.int32))
        decision_index = np.minimum(starts + int(data["window_size"]) - 1, len(grid) - 1)
        time_parts.append(grid[decision_index])
        inventory.append({
            "group": group, "sequence": sequence_dir.name, "failure_family": _failure_family(sequence_dir),
            "failure_onset_s": onset, "aligned_rows": len(grid), "windows": len(labels),
            "positive_windows": int(labels.sum()), "duration_s": float(grid[-1] - grid[0]),
        })
        print(f"ALFA features {len(inventory)}/{len(sequence_dirs)} {sequence_dir.name}", flush=True)
    x = np.concatenate(feature_parts).astype(np.float32)
    y = np.concatenate(label_parts).astype(np.int8)
    groups = np.concatenate(group_parts).astype(np.int32)
    times = np.concatenate(time_parts).astype(np.float64)
    np.save(output_dir / "x.npy", x)
    np.save(output_dir / "y.npy", y)
    np.save(output_dir / "group.npy", groups)
    np.save(output_dir / "decision_time_s.npy", times)
    pd.DataFrame(inventory).to_csv(report_dir / "alfa_inventory.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(mapping).to_csv(report_dir / "semantic_channel_mapping.csv", index=False, encoding="utf-8-sig")
    summary = {
        "source": config["source"],
        "excluded": ["carbonZ_2018-07-18-12-10-11_no_ground_truth"],
        "sequences": len(inventory), "channels": len(channels), "features": x.shape[1],
        "windows": len(y), "positive_windows": int(y.sum()), "negative_windows": int((y == 0).sum()),
        "frequency_hz": float(data["frequency_hz"]), "window_size": int(data["window_size"]),
        "stride": int(data["stride"]), "horizon": int(data["horizon"]),
    }
    (report_dir / "alfa_feature_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return summary


def _summary(rows: list[dict[str, Any]], metrics: list[str]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for metric in metrics:
        values = np.asarray([row[metric] for row in rows], dtype=float)
        result[metric] = {"mean": float(values.mean()), "std": float(values.std(ddof=1)) if len(values) > 1 else 0.0}
    return result


def run_external_validation(config: dict[str, Any], root: Path, seeds: list[int] | None = None) -> dict[str, Any]:
    paths = config["paths"]
    report_dir = _resolve(root, paths["report_dir"])
    model_dir = report_dir / "model_runs"
    model_dir.mkdir(parents=True, exist_ok=True)
    feature_dictionary = pd.read_csv(_resolve(root, paths["p2_feature_dictionary"]))
    channels = [item["uav_sead_channel"] for item in config["semantic_channels"]]
    columns = selected_feature_indices(feature_dictionary, channels)
    p2_dir = _resolve(root, paths["p2_feature_dir"])
    x_train = np.asarray(np.load(p2_dir / "x_train.npy", mmap_mode="r")[:, columns], dtype=np.float32)
    y_train = np.load(p2_dir / "y_train.npy", mmap_mode="r").astype(np.int32)
    x_val = np.asarray(np.load(p2_dir / "x_validation.npy", mmap_mode="r")[:, columns], dtype=np.float32)
    y_val = np.load(p2_dir / "y_validation.npy", mmap_mode="r").astype(np.int32)
    val_groups = np.load(p2_dir / "group_validation.npy", mmap_mode="r")
    x_test = np.asarray(np.load(p2_dir / "x_test.npy", mmap_mode="r")[:, columns], dtype=np.float32)
    y_test = np.load(p2_dir / "y_test.npy", mmap_mode="r").astype(np.int32)
    test_groups = np.load(p2_dir / "group_test.npy", mmap_mode="r")
    alfa_dir = _resolve(root, paths["alfa_feature_dir"])
    x_alfa = np.load(alfa_dir / "x.npy", mmap_mode="r")
    y_alfa = np.load(alfa_dir / "y.npy", mmap_mode="r").astype(np.int32)
    alfa_groups = np.load(alfa_dir / "group.npy", mmap_mode="r")
    inventory = pd.read_csv(report_dir / "alfa_inventory.csv")
    seeds = seeds or list(config["experiment"]["seeds"])
    rows: list[dict[str, Any]] = []
    family_rows: list[dict[str, Any]] = []
    for seed in seeds:
        params = dict(config["lightgbm"])
        early_stopping = int(params.pop("early_stopping_rounds"))
        model = lgb.LGBMClassifier(objective="binary", random_state=seed, n_jobs=int(config["experiment"]["n_jobs"]), verbosity=-1, **params)
        model.fit(x_train, y_train, eval_set=[(x_val, y_val)], eval_metric="average_precision",
                  callbacks=[lgb.early_stopping(early_stopping), lgb.log_evaluation(100)])
        val_scores = model.predict_proba(x_val)[:, 1]
        val_metrics = evaluate_scores(y_val, val_scores, val_groups)
        internal_scores = model.predict_proba(x_test)[:, 1]
        internal = evaluate_scores(y_test, internal_scores, test_groups, val_metrics["threshold"])
        alfa_scores = model.predict_proba(x_alfa)[:, 1]
        external = evaluate_scores(y_alfa, alfa_scores, alfa_groups, val_metrics["threshold"])
        row = {"method": "shared_channel_lightgbm", "seed": seed, "mapped_channels": len(channels),
               "best_iteration": int(model.best_iteration_ or 0), "uav_validation_threshold": val_metrics["threshold"]}
        row.update({f"uav_test_{key}": value for key, value in internal.items()})
        row.update({f"alfa_{key}": value for key, value in external.items()})
        rows.append(row)
        for family in sorted(inventory["failure_family"].unique()):
            family_groups = inventory.loc[inventory["failure_family"].isin([family, "No Failure"]), "group"].to_numpy()
            keep = np.isin(alfa_groups, family_groups)
            if y_alfa[keep].min() == y_alfa[keep].max():
                continue
            metrics = evaluate_scores(y_alfa[keep], alfa_scores[keep], alfa_groups[keep], val_metrics["threshold"])
            family_rows.append({"seed": seed, "failure_family": family, "windows": int(keep.sum()), **metrics})
        run_dir = model_dir / f"seed{seed}"
        run_dir.mkdir(parents=True, exist_ok=True)
        joblib.dump(model, run_dir / "shared_channel_lightgbm.joblib")
        pd.DataFrame({"group": alfa_groups, "label": y_alfa, "score": alfa_scores}).to_csv(
            run_dir / "alfa_scores.csv", index=False
        )
        print(json.dumps({"seed": seed, "alfa_auprc": external["auprc"], "alfa_auroc": external["auroc"],
                          "alfa_fixed_f1": external["f1_at_threshold"]}), flush=True)

    pd.DataFrame(rows).to_csv(report_dir / "seed_metrics.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(family_rows).to_csv(report_dir / "per_failure_family_metrics.csv", index=False, encoding="utf-8-sig")
    metrics = ["uav_test_auprc", "uav_test_auroc", "uav_test_f1_at_threshold", "alfa_auprc", "alfa_auroc",
               "alfa_f1_at_threshold", "alfa_log_aware_event_f1"]
    completion = {
        "status": "complete", "protocol": "zero-shot UAV-SEAD -> ALFA using 16 semantically shared physical channels",
        "seeds": seeds, "mapped_channels": len(channels), "alfa_sequences": int(len(inventory)),
        "alfa_windows": int(len(y_alfa)), "metrics": _summary(rows, metrics),
        "threshold_policy": "fixed exclusively on UAV-SEAD validation windows",
        "label_scope": "binary anomaly detection only; ALFA faults are not mapped to UAV-SEAD subsystem classes",
    }
    (report_dir / "completion_summary.json").write_text(json.dumps(completion, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return completion


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="configs/p6_alfa.yaml")
    parser.add_argument("--seeds", nargs="*", type=int)
    parser.add_argument("command", choices=["build-features", "evaluate", "run"])
    return parser


def main() -> None:
    args = build_parser().parse_args()
    config = load_config(args.config)
    root = Path.cwd()
    if args.command in {"build-features", "run"}:
        print(json.dumps(build_alfa_features(config, root), indent=2, ensure_ascii=False), flush=True)
    if args.command in {"evaluate", "run"}:
        print(json.dumps(run_external_validation(config, root, args.seeds), indent=2, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
