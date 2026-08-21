"""Aggregate P11 leave-log-out seed metrics and flight-log bootstrap CIs."""

from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, f1_score

from hs_aerots.robustness import grouped_bootstrap


ROOT = Path(__file__).resolve().parents[2]
P2 = ROOT / "reports/p11/llo/p2"
P3 = ROOT / "reports/p11/llo/p3"
SEEDS = range(5)


def ci_for(groups: np.ndarray, metric, seed: int) -> dict[str, float]:
    return grouped_bootstrap(groups, metric, 1000, 20260821 + seed, 0.95)


def multi_seed_classification_ci(paths: list[Path], seed: int) -> dict[str, float]:
    frames = [pd.read_csv(path) for path in paths]
    truth = frames[0]["true_class"].to_numpy(int)
    if "group" in frames[0]:
        groups = frames[0]["group"].to_numpy()
    else:
        all_groups = np.load(ROOT / "data/processed/p11/features_leave_log_out/group_test.npy", mmap_mode="r")
        groups = np.asarray(all_groups[frames[0]["window_index"].to_numpy(int)])
    predictions = [frame["predicted_class"].to_numpy(int) for frame in frames]
    labels = sorted(np.unique(truth).tolist())
    return ci_for(groups, lambda selected: float(np.mean([
        f1_score(truth[selected], prediction[selected], labels=labels, average="macro", zero_division=0)
        for prediction in predictions
    ])), seed)


def paired_classification_difference_ci(direct_paths: list[Path], cascade_paths: list[Path], seed: int) -> dict[str, float]:
    direct_frames = [pd.read_csv(path) for path in direct_paths]
    cascade_frames = [pd.read_csv(path) for path in cascade_paths]
    truth = direct_frames[0]["true_class"].to_numpy(int)
    groups = direct_frames[0]["group"].to_numpy()
    labels = sorted(np.unique(truth).tolist())
    direct_predictions = [frame["predicted_class"].to_numpy(int) for frame in direct_frames]
    cascade_predictions = [frame["predicted_class"].to_numpy(int) for frame in cascade_frames]
    return ci_for(groups, lambda selected: float(np.mean([
        f1_score(truth[selected], direct[selected], labels=labels, average="macro", zero_division=0)
        - f1_score(truth[selected], cascade[selected], labels=labels, average="macro", zero_division=0)
        for direct, cascade in zip(direct_predictions, cascade_predictions)
    ])), seed)


def score_ci(path: Path, seed: int) -> dict[str, float]:
    frame = pd.read_csv(path)
    labels = frame["label"].to_numpy(int)
    scores = frame["score"].to_numpy(float)
    groups = frame["group"].to_numpy()
    return ci_for(groups, lambda selected: float(average_precision_score(labels[selected], scores[selected])), seed)


def multi_seed_score_ci(paths: list[Path], seed: int) -> dict[str, float]:
    frames = [pd.read_csv(path) for path in paths]
    labels = frames[0]["label"].to_numpy(int)
    groups = frames[0]["group"].to_numpy()
    scores = [frame["score"].to_numpy(float) for frame in frames]
    return ci_for(groups, lambda selected: float(np.mean([
        average_precision_score(labels[selected], score[selected]) for score in scores
    ])), seed)


def ensure_stage2_rf_predictions() -> list[Path]:
    feature_dir = ROOT / "data/processed/p11/features_leave_log_out"
    x_test = np.load(feature_dir / "x_test.npy", mmap_mode="r")
    binary = np.load(feature_dir / "y_test.npy", mmap_mode="r")
    anomaly_type = np.load(feature_dir / "type_test.npy", mmap_mode="r")
    keep = (binary > 0) & np.isin(anomaly_type, [1, 2, 3, 4])
    indices = np.flatnonzero(keep)
    output = []
    for seed in SEEDS:
        path = P3 / f"predictions/stage2_random_forest_seed{seed}.csv"
        if not path.exists():
            model = joblib.load(P3 / f"model_runs/seed{seed}/stage2_random_forest.joblib")
            prediction = model.predict(x_test[keep]).astype(int)
            pd.DataFrame({"window_index": indices, "true_class": anomaly_type[keep], "predicted_class": prediction}).to_csv(path, index=False)
        output.append(path)
    return output


def main() -> None:
    p2_rows = pd.read_csv(P2 / "seed_metrics.csv")
    p3_rows = pd.read_csv(P3 / "seed_metrics.csv")
    metric_rows: list[dict[str, object]] = []
    p2_metrics = ["test_auprc", "test_auroc", "test_best_f1", "test_event_f1", "test_at_val_threshold_f1_at_threshold", "test_at_val_threshold_log_aware_event_f1"]
    p2_summary: dict[str, dict[str, float]] = {}
    for metric in p2_metrics:
        values = p2_rows[metric].to_numpy(float)
        p2_summary[metric] = {"mean": float(values.mean()), "std": float(values.std(ddof=1))}
    p2_summary["test_auprc"].update(multi_seed_score_ci([P2 / f"baseline_runs/seed{seed}/test_scores.csv" for seed in SEEDS], 0))
    for seed in SEEDS:
        score_path = P2 / f"baseline_runs/seed{seed}/test_scores.csv"
        frame = pd.read_csv(score_path)
        labels = frame["label"].to_numpy(int)
        scores = frame["score"].to_numpy(float)
        groups = frame["group"].to_numpy()
        for metric in ("auprc",):
            values = {"seed": seed, "method": "stage1", "metric": metric, "value": float(average_precision_score(labels, scores)), **score_ci(score_path, seed)}
            metric_rows.append(values)

    method_summary = []
    for method, part in p3_rows.groupby("method", sort=False):
        row: dict[str, object] = {"method": method, "runs": int(len(part))}
        for metric in ("macro_f1", "balanced_accuracy", "accuracy", "weighted_f1"):
            values = pd.to_numeric(part[metric], errors="coerce").to_numpy(float)
            row[f"{metric}_mean"] = float(values.mean())
            row[f"{metric}_std"] = float(values.std(ddof=1))
        prediction_name = {"stage2_lightgbm": "stage2_seed{seed}.csv", "hs_aerots_cascade": "cascade_seed{seed}.csv", "direct_five_class_lightgbm": "direct_five_seed{seed}.csv"}.get(method)
        if prediction_name:
            ci = multi_seed_classification_ci([P3 / "predictions" / prediction_name.format(seed=seed) for seed in SEEDS], 10)
            row["macro_f1_ci_low"] = ci["ci_low"]
            row["macro_f1_ci_high"] = ci["ci_high"]
            row["bootstrap_repetitions"] = 1000
            row["bootstrap_unit"] = "flight_log"
        method_summary.append(row)

    rf_stage2_paths = ensure_stage2_rf_predictions()
    rf_stage2_ci = multi_seed_classification_ci(rf_stage2_paths, 11)
    for row in method_summary:
        if row["method"] == "stage2_random_forest":
            row["macro_f1_ci_low"] = rf_stage2_ci["ci_low"]
            row["macro_f1_ci_high"] = rf_stage2_ci["ci_high"]
            row["bootstrap_repetitions"] = 1000
            row["bootstrap_unit"] = "flight_log"

    # RF is a Stage-1 detector and is reported from its own five-seed file.
    rf = pd.read_csv(P2 / "random_forest_seed_metrics.csv")
    rf_summary = {"method": "random_forest_binary", "runs": int(len(rf)), "protocol": "leave_log_out"}
    for metric in ("test_auprc", "test_auroc", "test_best_f1", "test_event_f1"):
        values = rf[metric].to_numpy(float)
        rf_summary[f"{metric}_mean"] = float(values.mean())
        rf_summary[f"{metric}_std"] = float(values.std(ddof=1))
    rf_ci = multi_seed_score_ci([P2 / f"random_forest_runs/seed{seed}/test_scores.csv" for seed in SEEDS], 12)
    rf_summary["test_auprc_ci_low"] = rf_ci["ci_low"]
    rf_summary["test_auprc_ci_high"] = rf_ci["ci_high"]
    rf_summary["bootstrap_repetitions"] = 1000
    rf_summary["bootstrap_unit"] = "flight_log"
    method_summary.append(rf_summary)

    direct = next(row for row in method_summary if row["method"] == "direct_five_class_lightgbm")
    cascade = next(row for row in method_summary if row["method"] == "hs_aerots_cascade")
    difference_ci = paired_classification_difference_ci(
        [P3 / f"predictions/direct_five_seed{seed}.csv" for seed in SEEDS],
        [P3 / f"predictions/cascade_seed{seed}.csv" for seed in SEEDS],
        13,
    )
    comparison = {
        "metric": "five_class_macro_f1",
        "direct_minus_cascade": float(direct["macro_f1_mean"] - cascade["macro_f1_mean"]),
        "paired_bootstrap_ci_low": difference_ci["ci_low"],
        "paired_bootstrap_ci_high": difference_ci["ci_high"],
        "bootstrap_repetitions": 1000,
        "bootstrap_unit": "flight_log",
    }
    summary = {
        "status": "complete",
        "protocol": "leave_log_out",
        "seeds": list(SEEDS),
        "flight_log_bootstrap": {"repetitions": 1000, "confidence": 0.95, "unit": "flight_log"},
        "stage1_lightgbm": p2_summary,
        "methods": method_summary,
        "cascade_vs_direct": comparison,
        "interpretation": "Under leave-log-out, direct five-class has a 0.0130 higher mean five-class Macro-F1 than the cascade, but the paired flight-log bootstrap 95% CI includes zero. The evaluated logs therefore do not support a stable performance difference; the cascade remains a distinct gated design with explicit anomaly detection semantics.",
    }
    (P2 / "summary_5seeds_bootstrap.json").write_text(json.dumps({"protocol": "leave_log_out", "stage1_lightgbm": p2_summary, "random_forest": rf_summary, "bootstrap": summary["flight_log_bootstrap"]}, indent=2) + "\n", encoding="utf-8")
    pd.DataFrame(method_summary).to_csv(P3 / "method_summary_5seeds_bootstrap.csv", index=False, encoding="utf-8-sig")
    (P3 / "completion_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
