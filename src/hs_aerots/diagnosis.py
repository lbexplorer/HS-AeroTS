"""P3 Stage 2 subsystem diagnosis on the fixed P2 AeroTSBoost features."""

from __future__ import annotations

import argparse
import csv
import json
import warnings
from pathlib import Path
from typing import Any, Iterable

import joblib
import lightgbm as lgb
import numpy as np
import pandas as pd
import yaml
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    balanced_accuracy_score,
    confusion_matrix,
    f1_score,
    precision_recall_fscore_support,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.preprocessing import label_binarize


SUBSYSTEM_LABELS = [1, 2, 3, 4]
LABEL_NAMES = {
    0: "Normal",
    1: "External Position",
    2: "Global Position",
    3: "Altitude",
    4: "Mechanical/Electrical",
}


def load_config(path: str | Path) -> dict[str, Any]:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def _resolve(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


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


def hierarchical_labels(binary: np.ndarray, anomaly_types: np.ndarray) -> np.ndarray:
    binary = np.asarray(binary).astype(bool)
    anomaly_types = np.asarray(anomaly_types).astype(np.int16)
    labels = np.where(binary, anomaly_types, 0).astype(np.int16)
    invalid = binary & ~np.isin(labels, SUBSYSTEM_LABELS)
    if invalid.any():
        raise ValueError(f"{int(invalid.sum())} positive windows lack one of the four subsystem labels")
    return labels


def stage2_subset(x: np.ndarray, binary: np.ndarray, anomaly_types: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    labels = hierarchical_labels(binary, anomaly_types)
    keep = np.isin(labels, SUBSYSTEM_LABELS)
    return np.asarray(x[keep], dtype=np.float32), labels[keep].astype(np.int32), np.flatnonzero(keep)


def classification_metrics(y_true: np.ndarray, y_pred: np.ndarray, labels: list[int]) -> tuple[dict[str, float], list[dict[str, Any]], np.ndarray]:
    y_true = np.asarray(y_true).astype(int)
    y_pred = np.asarray(y_pred).astype(int)
    precision, recall, f1, support = precision_recall_fscore_support(
        y_true, y_pred, labels=labels, zero_division=0
    )
    metrics = {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "macro_f1": float(f1_score(y_true, y_pred, labels=labels, average="macro", zero_division=0)),
        "balanced_accuracy": float(recall.mean()),
        "macro_precision": float(precision_score(y_true, y_pred, labels=labels, average="macro", zero_division=0)),
        "macro_recall": float(recall_score(y_true, y_pred, labels=labels, average="macro", zero_division=0)),
        "weighted_f1": float(f1_score(y_true, y_pred, labels=labels, average="weighted", zero_division=0)),
    }
    rows = [
        {
            "class_id": int(label),
            "class": LABEL_NAMES[label],
            "precision": float(precision[index]),
            "recall": float(recall[index]),
            "f1": float(f1[index]),
            "support": int(support[index]),
        }
        for index, label in enumerate(labels)
    ]
    return metrics, rows, confusion_matrix(y_true, y_pred, labels=labels)


def probability_metrics(y_true: np.ndarray, probability: np.ndarray) -> dict[str, float]:
    encoded = label_binarize(y_true, classes=SUBSYSTEM_LABELS)
    return {
        "macro_ovr_auprc": float(average_precision_score(encoded, probability, average="macro")),
        "macro_ovr_auroc": float(roc_auc_score(encoded, probability, average="macro", multi_class="ovr")),
    }


def subsystem_for_channel(channel: str) -> tuple[str, str]:
    lower = channel.lower()
    if "vehicle_vision_position" in lower:
        return "External Position", "visual-position estimate"
    if any(token in lower for token in ("distance_sensor", "hagl", "hgt", "pos_vert_accuracy", ".z", ".vz", ".az", "dist_bottom", "land_detected")):
        return "Altitude", "vertical/range state"
    if any(token in lower for token in ("pos_test_ratio", "pos_horiz_accuracy", "heading_innov", "vel_pos_innov[3]", "vel_pos_innov[4]", ".x", ".y", ".vx", ".vy", ".eph", ".epv")):
        return "Global Position", "horizontal/global state"
    if any(token in lower for token in ("actuator", "battery", "system_power", "cpuload", "vibe", "gyro", "accelerometer", "rate_ctrl", "attitude", "rates_setpoint", "sensor_preflight")):
        return "Mechanical/Electrical", "actuation/inertial/system health"
    return "Shared", "context/control state"


def build_subsystem_mapping(feature_dictionary: Path, report_dir: Path) -> dict[str, int]:
    features = pd.read_csv(feature_dictionary)
    channel_rows = []
    for channel, part in features.groupby("channel", sort=False):
        subsystem, rationale = subsystem_for_channel(channel)
        channel_rows.append({
            "channel": channel,
            "topic": str(part.iloc[0]["topic"]),
            "subsystem": subsystem,
            "rationale": rationale,
            "feature_count": int(len(part)),
        })
    _write_csv(report_dir / "channel_subsystem_mapping.csv", channel_rows)
    counts = pd.Series([row["subsystem"] for row in channel_rows]).value_counts().sort_index().to_dict()
    return {str(key): int(value) for key, value in counts.items()}


def _load_split(feature_dir: Path, split: str) -> dict[str, np.ndarray]:
    return {
        "x": np.load(feature_dir / f"x_{split}.npy", mmap_mode="r"),
        "binary": np.load(feature_dir / f"y_{split}.npy", mmap_mode="r"),
        "type": np.load(feature_dir / f"type_{split}.npy", mmap_mode="r"),
        "group": np.load(feature_dir / f"group_{split}.npy", mmap_mode="r"),
        "start": np.load(feature_dir / f"start_{split}.npy", mmap_mode="r"),
    }


def train_stage2_lgbm(x_train: np.ndarray, y_train: np.ndarray, x_val: np.ndarray, y_val: np.ndarray, config: dict[str, Any], seed: int, n_jobs: int):
    params = dict(config)
    early_stopping = int(params.pop("early_stopping_rounds"))
    model = lgb.LGBMClassifier(
        objective="multiclass", num_class=4, random_state=seed, n_jobs=n_jobs, verbosity=-1, **params
    )
    model.fit(
        x_train,
        y_train - 1,
        eval_set=[(x_val, y_val - 1)],
        eval_metric="multi_logloss",
        callbacks=[lgb.early_stopping(early_stopping), lgb.log_evaluation(100)],
    )
    return model


def train_random_forest(x_train: np.ndarray, y_train: np.ndarray, config: dict[str, Any], seed: int, n_jobs: int):
    params = dict(config)
    rf_n_jobs = int(params.pop("n_jobs", n_jobs))
    model = RandomForestClassifier(random_state=seed, n_jobs=rf_n_jobs, **params)
    model.fit(x_train, y_train)
    return model


def train_direct_five_class(x_train: np.ndarray, y_train: np.ndarray, x_val: np.ndarray, y_val: np.ndarray, config: dict[str, Any], seed: int, n_jobs: int):
    params = dict(config)
    early_stopping = int(params.pop("early_stopping_rounds"))
    model = lgb.LGBMClassifier(
        objective="multiclass", num_class=5, random_state=seed, n_jobs=n_jobs, verbosity=-1, **params
    )
    model.fit(
        x_train,
        y_train,
        eval_set=[(x_val, y_val)],
        eval_metric="multi_logloss",
        callbacks=[lgb.early_stopping(early_stopping), lgb.log_evaluation(100)],
    )
    return model


def _append_result(method: str, seed: int, y_true: np.ndarray, y_pred: np.ndarray, labels: list[int], metric_rows: list[dict[str, Any]], class_rows: list[dict[str, Any]], confusion_dir: Path, probability: np.ndarray | None = None) -> dict[str, float]:
    metrics, per_class, matrix = classification_metrics(y_true, y_pred, labels)
    if probability is not None and labels == SUBSYSTEM_LABELS:
        metrics.update(probability_metrics(y_true, probability))
    metric_rows.append({"method": method, "seed": seed, **metrics})
    for row in per_class:
        class_rows.append({"method": method, "seed": seed, **row})
    confusion_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(matrix, index=[LABEL_NAMES[x] for x in labels], columns=[LABEL_NAMES[x] for x in labels]).to_csv(
        confusion_dir / f"{method}_seed{seed}.csv", encoding="utf-8-sig"
    )
    return metrics


def summarize(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    frame = pd.DataFrame(rows)
    metric_columns = [column for column in frame.columns if column not in {"method", "seed"}]
    output = []
    for method, part in frame.groupby("method", sort=False):
        row: dict[str, Any] = {"method": method, "runs": int(len(part))}
        for metric in metric_columns:
            values = pd.to_numeric(part[metric], errors="coerce").dropna()
            if len(values):
                row[f"{metric}_mean"] = float(values.mean())
                row[f"{metric}_std"] = float(values.std(ddof=1)) if len(values) > 1 else 0.0
        output.append(row)
    return output


def run_diagnosis(config: dict[str, Any], root: Path, seeds: list[int] | None = None) -> dict[str, Any]:
    paths = config["paths"]
    feature_dir = _resolve(root, paths["feature_dir"])
    report_dir = _resolve(root, paths["report_dir"])
    model_dir = report_dir / "model_runs"
    report_dir.mkdir(parents=True, exist_ok=True)
    splits = {name: _load_split(feature_dir, name) for name in ("train", "validation", "test")}
    subset = {}
    label_summary: dict[str, Any] = {}
    for name, split in splits.items():
        x, labels, indices = stage2_subset(split["x"], split["binary"], split["type"])
        subset[name] = {"x": x, "y": labels, "indices": indices}
        label_summary[name] = {
            "windows": int(len(labels)),
            "classes": {LABEL_NAMES[label]: int((labels == label).sum()) for label in SUBSYSTEM_LABELS},
        }
    (report_dir / "label_summary.json").write_text(json.dumps(label_summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    mapping_counts = build_subsystem_mapping(_resolve(root, paths["feature_dictionary"]), report_dir)

    seeds = list(config["experiment"]["seeds"]) if seeds is None else list(seeds)
    run_stage2 = bool(config["experiment"].get("run_stage2", True))
    n_jobs = int(config["experiment"]["n_jobs"])
    metric_rows: list[dict[str, Any]] = []
    class_rows: list[dict[str, Any]] = []
    predictions_dir = report_dir / "predictions"
    confusion_dir = report_dir / "confusion_matrices"
    predictions_dir.mkdir(parents=True, exist_ok=True)
    model_dir.mkdir(parents=True, exist_ok=True)
    train_priors = np.asarray([(subset["train"]["y"] == label).mean() for label in SUBSYSTEM_LABELS])
    majority = int(SUBSYSTEM_LABELS[int(np.argmax(train_priors))])

    for seed in seeds if run_stage2 else []:
        print(f"Stage2 seed={seed}", flush=True)
        model = train_stage2_lgbm(
            subset["train"]["x"], subset["train"]["y"], subset["validation"]["x"],
            subset["validation"]["y"], config["stage2_model"], seed, n_jobs,
        )
        probability = model.predict_proba(subset["test"]["x"])
        prediction = (np.argmax(probability, axis=1) + 1).astype(int)
        metrics = _append_result(
            "stage2_lightgbm", seed, subset["test"]["y"], prediction, SUBSYSTEM_LABELS,
            metric_rows, class_rows, confusion_dir, probability,
        )

        rf = train_random_forest(subset["train"]["x"], subset["train"]["y"], config["random_forest"], seed, n_jobs)
        rf_probability = rf.predict_proba(subset["test"]["x"])
        rf_prediction = rf.predict(subset["test"]["x"])
        _append_result(
            "stage2_random_forest", seed, subset["test"]["y"], rf_prediction, SUBSYSTEM_LABELS,
            metric_rows, class_rows, confusion_dir, rf_probability,
        )

        majority_prediction = np.full(len(subset["test"]["y"]), majority, dtype=int)
        _append_result(
            "majority", seed, subset["test"]["y"], majority_prediction, SUBSYSTEM_LABELS,
            metric_rows, class_rows, confusion_dir,
        )
        random_prediction = np.random.default_rng(seed).choice(SUBSYSTEM_LABELS, size=len(subset["test"]["y"]), p=train_priors)
        _append_result(
            "stratified_random", seed, subset["test"]["y"], random_prediction, SUBSYSTEM_LABELS,
            metric_rows, class_rows, confusion_dir,
        )

        p2_run = _resolve(root, paths["p2_model_runs"]) / f"seed{seed}"
        stage1 = joblib.load(p2_run / "lightgbm.joblib")
        stage1_metrics = json.loads((p2_run / "metrics.json").read_text(encoding="utf-8"))
        threshold = float(stage1_metrics["val_threshold"])
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            anomaly_score = stage1.predict_proba(splits["test"]["x"])[:, 1]
        cascade = np.zeros(len(anomaly_score), dtype=int)
        flagged = anomaly_score >= threshold
        if flagged.any():
            cascade[flagged] = model.predict(splits["test"]["x"][flagged]).astype(int) + 1
        true_five = hierarchical_labels(splits["test"]["binary"], splits["test"]["type"])
        cascade_metrics = _append_result(
            "hs_aerots_cascade", seed, true_five, cascade, [0, 1, 2, 3, 4],
            metric_rows, class_rows, confusion_dir,
        )
        true_anomaly = true_five > 0
        cascade_subtype, _, _ = classification_metrics(true_five[true_anomaly], cascade[true_anomaly], SUBSYSTEM_LABELS)
        for key, value in cascade_subtype.items():
            cascade_metrics[f"anomaly_only_{key}"] = value
        metric_rows[-1].update({f"anomaly_only_{key}": value for key, value in cascade_subtype.items()})
        metric_rows[-1]["stage1_threshold"] = threshold
        metric_rows[-1]["stage1_flagged_windows"] = int(flagged.sum())

        run_dir = model_dir / f"seed{seed}"
        run_dir.mkdir(parents=True, exist_ok=True)
        joblib.dump(model, run_dir / "stage2_lightgbm.joblib")
        joblib.dump(rf, run_dir / "stage2_random_forest.joblib")
        pd.DataFrame({
            "window_index": subset["test"]["indices"],
            "true_class": subset["test"]["y"],
            "predicted_class": prediction,
            **{f"probability_{LABEL_NAMES[label]}": probability[:, index] for index, label in enumerate(SUBSYSTEM_LABELS)},
        }).to_csv(predictions_dir / f"stage2_seed{seed}.csv", index=False)
        pd.DataFrame({
            "true_class": true_five, "predicted_class": cascade, "stage1_score": anomaly_score,
            "stage1_flagged": flagged.astype(np.int8), "group": splits["test"]["group"], "start": splits["test"]["start"],
        }).to_csv(predictions_dir / f"cascade_seed{seed}.csv", index=False)
        print(json.dumps({"seed": seed, "macro_f1": metrics["macro_f1"],
                          "balanced_accuracy": metrics["balanced_accuracy"],
                          "cascade_macro_f1": cascade_metrics["macro_f1"]}), flush=True)

    if config.get("direct_five_class", {}).get("enabled", False):
        train_five = hierarchical_labels(splits["train"]["binary"], splits["train"]["type"])
        val_five = hierarchical_labels(splits["validation"]["binary"], splits["validation"]["type"])
        test_five = hierarchical_labels(splits["test"]["binary"], splits["test"]["type"])
        for seed in config["direct_five_class"].get("seeds", [0]):
            print(f"Direct five-class seed={seed}", flush=True)
            model = train_direct_five_class(
                splits["train"]["x"], train_five, splits["validation"]["x"], val_five,
                config["stage2_model"], int(seed), n_jobs,
            )
            prediction = model.predict(splits["test"]["x"]).astype(int)
            _append_result(
                "direct_five_class_lightgbm", int(seed), test_five, prediction, [0, 1, 2, 3, 4],
                metric_rows, class_rows, confusion_dir,
            )
            anomaly = test_five > 0
            subtype_metrics, _, _ = classification_metrics(test_five[anomaly], prediction[anomaly], SUBSYSTEM_LABELS)
            metric_rows[-1].update({f"anomaly_only_{key}": value for key, value in subtype_metrics.items()})
            run_dir = model_dir / f"direct_five_seed{seed}"
            run_dir.mkdir(parents=True, exist_ok=True)
            joblib.dump(model, run_dir / "direct_five_class_lightgbm.joblib")
            probability = model.predict_proba(splits["test"]["x"])
            pd.DataFrame({
                "true_class": test_five,
                "predicted_class": prediction,
                "group": splits["test"]["group"],
                "start": splits["test"]["start"],
                **{f"probability_{LABEL_NAMES[label]}": probability[:, label] for label in range(5)},
            }).to_csv(predictions_dir / f"direct_five_seed{seed}.csv", index=False)

    _write_csv(report_dir / "seed_metrics.csv", metric_rows)
    _write_csv(report_dir / "per_class_metrics.csv", class_rows)
    summary_rows = summarize(metric_rows)
    _write_csv(report_dir / "method_summary.csv", summary_rows)
    summaries = {row["method"]: row for row in summary_rows}
    if not run_stage2:
        direct_summary = summaries["direct_five_class_lightgbm"]
        completion = {
            "status": "complete",
            "protocol": str(config.get("protocol", "fixed P2 per-log chronological split")),
            "experiment": "direct five-class LightGBM multi-seed robustness",
            "seeds": [int(seed) for seed in config["direct_five_class"].get("seeds", [0])],
            "direct_five_class_lightgbm": direct_summary,
            "test_windows": int(len(test_five)),
        }
        (report_dir / "completion_summary.json").write_text(json.dumps(completion, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return completion
    stage2_summary = summaries["stage2_lightgbm"]
    majority_summary = summaries["majority"]
    random_summary = summaries["stratified_random"]
    completion = {
        "status": "complete",
        "protocol": str(config.get("protocol", "fixed P2 per-log chronological split")),
        "stage2_train_windows": int(len(subset["train"]["y"])),
        "stage2_validation_windows": int(len(subset["validation"]["y"])),
        "stage2_test_windows": int(len(subset["test"]["y"])),
        "stage2_lightgbm": stage2_summary,
        "majority_macro_f1": majority_summary["macro_f1_mean"],
        "stratified_random_macro_f1": random_summary["macro_f1_mean"],
        "macro_f1_gain_over_majority": stage2_summary["macro_f1_mean"] - majority_summary["macro_f1_mean"],
        "macro_f1_gain_over_random": stage2_summary["macro_f1_mean"] - random_summary["macro_f1_mean"],
        "channel_subsystem_counts": mapping_counts,
        "completion_criterion": "Macro-F1 clearly exceeds majority and stratified-random baselines",
        "criterion_passed": stage2_summary["macro_f1_mean"] > max(majority_summary["macro_f1_mean"], random_summary["macro_f1_mean"]) + 0.10,
    }
    (report_dir / "completion_summary.json").write_text(json.dumps(completion, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return completion


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="configs/p3_stage2.yaml")
    parser.add_argument("--seeds", nargs="*", type=int)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    root = Path.cwd()
    config = load_config(args.config)
    print(json.dumps(run_diagnosis(config, root, args.seeds), indent=2, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
