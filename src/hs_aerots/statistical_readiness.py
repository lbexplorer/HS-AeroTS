"""Cluster-aware statistics and masking sensitivity for submission readiness."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, f1_score

from .diagnosis import SUBSYSTEM_LABELS, stage2_subset
from .explainability import _booster_predict_labels, _predict_contributions, _train_reference


def _split(feature_dir: Path, name: str) -> dict[str, np.ndarray]:
    return {
        "x": np.load(feature_dir / f"x_{name}.npy", mmap_mode="r"),
        "binary": np.load(feature_dir / f"y_{name}.npy", mmap_mode="r"),
        "type": np.load(feature_dir / f"type_{name}.npy", mmap_mode="r"),
        "group": np.load(feature_dir / f"group_{name}.npy", mmap_mode="r"),
    }


def _confusions_by_group(y: np.ndarray, pred: np.ndarray, groups: np.ndarray, labels: list[int]) -> tuple[np.ndarray, np.ndarray]:
    unique = np.unique(groups)
    index = {group: i for i, group in enumerate(unique)}
    matrix = np.zeros((len(unique), len(labels), len(labels)), dtype=np.int64)
    label_index = {label: i for i, label in enumerate(labels)}
    for truth, guess, group in zip(y, pred, groups, strict=True):
        if int(truth) in label_index and int(guess) in label_index:
            matrix[index[group], label_index[int(truth)], label_index[int(guess)]] += 1
    return unique, matrix


def _macro_f1_from_confusions(confusions: np.ndarray) -> np.ndarray:
    confusions = np.asarray(confusions, dtype=float)
    tp = np.diagonal(confusions, axis1=-2, axis2=-1)
    fp = confusions.sum(axis=-2) - tp
    fn = confusions.sum(axis=-1) - tp
    denominator = 2 * tp + fp + fn
    per_class = np.divide(2 * tp, denominator, out=np.zeros_like(tp), where=denominator > 0)
    return per_class.mean(axis=-1)


def _bootstrap_weights(groups: int, repetitions: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    weights = np.zeros((repetitions, groups), dtype=np.int16)
    for row in range(repetitions):
        weights[row] = np.bincount(rng.integers(0, groups, size=groups), minlength=groups)
    return weights


def _bootstrap_f1(confusions: np.ndarray, weights: np.ndarray) -> np.ndarray:
    combined = np.einsum("bg,gij->bij", weights, confusions, optimize=True)
    return _macro_f1_from_confusions(combined)


def masking_paired_analysis(root: Path, output: Path, seeds: list[int], repetitions: int = 1000) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=True)
    feature_dir = root / "data/processed/p2/features_original"
    train = _split(feature_dir, "train")
    validation = _split(feature_dir, "validation")
    test = _split(feature_dir, "test")
    val_x, _, _ = stage2_subset(validation["x"], validation["binary"], validation["type"])
    test_x, test_y, test_indices = stage2_subset(test["x"], test["binary"], test["type"])
    test_x = np.asarray(test_x, dtype=np.float32)
    test_y = np.asarray(test_y, dtype=int)
    test_groups = np.asarray(test["group"][test_indices])
    reference, reference_indices = _train_reference(train["x"], 20000, 20260820)
    donor_pool = np.asarray(train["x"][reference_indices], dtype=np.float32)
    unique_groups = np.unique(test_groups)
    weights = _bootstrap_weights(len(unique_groups), repetitions, 20260825)
    k_values = [10, 25, 50, 100]
    random_repeats = 20
    point_rows: list[dict[str, Any]] = []
    seed_bootstrap: dict[int, dict[int, dict[str, np.ndarray]]] = {}

    for seed in seeds:
        print(f"paired masking seed={seed}", flush=True)
        model = joblib.load(root / f"reports/p3/model_runs/seed{seed}/stage2_lightgbm.joblib")
        _, val_signed = _predict_contributions(model, np.asarray(val_x), 256)
        ranking = np.argsort(-np.abs(val_signed).mean(axis=0), kind="stable")
        baseline = _booster_predict_labels(model, test_x)
        group_order, baseline_conf = _confusions_by_group(test_y, baseline, test_groups, SUBSYSTEM_LABELS)
        if not np.array_equal(group_order, unique_groups):
            raise RuntimeError("group ordering mismatch")
        baseline_boot = _bootstrap_f1(baseline_conf, weights)
        baseline_point = float(_macro_f1_from_confusions(baseline_conf.sum(axis=0)))
        work = test_x.copy()
        rng = np.random.default_rng(seed + 41027)
        donor_rng = np.random.default_rng(seed + 91027)
        seed_bootstrap[seed] = {}
        for k in k_values:
            top = np.asarray(ranking[:k], dtype=np.int32)
            work[:, top] = reference[top]
            shap_pred = _booster_predict_labels(model, work)
            work[:, top] = test_x[:, top]
            _, shap_conf = _confusions_by_group(test_y, shap_pred, test_groups, SUBSYSTEM_LABELS)
            shap_boot = _bootstrap_f1(shap_conf, weights)
            shap_point = float(_macro_f1_from_confusions(shap_conf.sum(axis=0)))

            donor_indices = donor_rng.integers(0, len(donor_pool), size=len(test_x))
            work[:, top] = donor_pool[donor_indices][:, top]
            donor_pred = _booster_predict_labels(model, work)
            work[:, top] = test_x[:, top]
            _, donor_conf = _confusions_by_group(test_y, donor_pred, test_groups, SUBSYSTEM_LABELS)
            donor_boot = _bootstrap_f1(donor_conf, weights)
            donor_point = float(_macro_f1_from_confusions(donor_conf.sum(axis=0)))

            random_boots: list[np.ndarray] = []
            random_points: list[float] = []
            for repeat in range(random_repeats):
                chosen = np.sort(rng.choice(test_x.shape[1], size=k, replace=False))
                work[:, chosen] = reference[chosen]
                random_pred = _booster_predict_labels(model, work)
                work[:, chosen] = test_x[:, chosen]
                _, random_conf = _confusions_by_group(test_y, random_pred, test_groups, SUBSYSTEM_LABELS)
                random_boots.append(_bootstrap_f1(random_conf, weights))
                random_points.append(float(_macro_f1_from_confusions(random_conf.sum(axis=0))))
            random_boot = np.vstack(random_boots).mean(axis=0)
            random_point = float(np.mean(random_points))
            seed_bootstrap[seed][k] = {
                "shap_advantage": random_boot - shap_boot,
                "median_drop": baseline_boot - shap_boot,
                "donor_drop": baseline_boot - donor_boot,
            }
            point_rows.extend([
                {"seed": seed, "k": k, "condition": "baseline", "macro_f1": baseline_point, "macro_f1_drop": 0.0},
                {"seed": seed, "k": k, "condition": "shap_median", "macro_f1": shap_point, "macro_f1_drop": baseline_point - shap_point},
                {"seed": seed, "k": k, "condition": "shap_training_row_donor", "macro_f1": donor_point, "macro_f1_drop": baseline_point - donor_point},
                {"seed": seed, "k": k, "condition": "random_median_mean20", "macro_f1": random_point, "macro_f1_drop": baseline_point - random_point},
            ])
    points = pd.DataFrame(point_rows)
    points.to_csv(output / "masking_point_estimates.csv", index=False, encoding="utf-8-sig")
    ci_rows: list[dict[str, Any]] = []
    alpha = 0.025
    for k in k_values:
        for metric in ("shap_advantage", "median_drop", "donor_drop"):
            values = np.vstack([seed_bootstrap[seed][k][metric] for seed in seeds]).mean(axis=0)
            point = {
                "shap_advantage": points[(points["k"].eq(k)) & (points["condition"].eq("random_median_mean20"))]["macro_f1"].mean()
                                  - points[(points["k"].eq(k)) & (points["condition"].eq("shap_median"))]["macro_f1"].mean(),
                "median_drop": points[(points["k"].eq(k)) & (points["condition"].eq("shap_median"))]["macro_f1_drop"].mean(),
                "donor_drop": points[(points["k"].eq(k)) & (points["condition"].eq("shap_training_row_donor"))]["macro_f1_drop"].mean(),
            }[metric]
            ci_rows.append({"k": k, "metric": metric, "estimate": float(point),
                            "ci_low": float(np.quantile(values, alpha)), "ci_high": float(np.quantile(values, 1 - alpha)),
                            "bootstrap_unit": "flight_log", "bootstrap_repetitions": repetitions, "seeds": len(seeds)})
    ci = pd.DataFrame(ci_rows)
    ci.to_csv(output / "masking_paired_flight_log_ci.csv", index=False, encoding="utf-8-sig")
    summary = {
        "status": "complete",
        "test_stage2_windows": int(len(test_y)),
        "test_flight_logs": int(len(unique_groups)),
        "seeds": seeds,
        "random_repeats_nested_within_seed": random_repeats,
        "bootstrap_repetitions": repetitions,
        "results": ci.to_dict(orient="records"),
        "boundary": "Training-row donor replacement preserves the joint distribution among replaced features but can still create cross-block combinations with unreplaced features.",
    }
    (output / "completion_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def _paired_method_ci(first: pd.DataFrame, second: pd.DataFrame, repetitions: int, seed: int) -> dict[str, float]:
    keys = ["group", "start"]
    merged = first.merge(second, on=keys, suffixes=("_first", "_second"), validate="one_to_one")
    if not np.array_equal(merged["true_class_first"], merged["true_class_second"]):
        raise ValueError("truth labels differ between paired methods")
    truth = merged["true_class_first"].to_numpy(dtype=int)
    pred_first = merged["predicted_class_first"].to_numpy(dtype=int)
    pred_second = merged["predicted_class_second"].to_numpy(dtype=int)
    groups = merged["group"].to_numpy()
    unique = np.unique(groups)
    weights = _bootstrap_weights(len(unique), repetitions, seed)
    order, first_conf = _confusions_by_group(truth, pred_first, groups, [0, 1, 2, 3, 4])
    order2, second_conf = _confusions_by_group(truth, pred_second, groups, [0, 1, 2, 3, 4])
    if not np.array_equal(order, order2):
        raise RuntimeError("paired group ordering mismatch")
    values = _bootstrap_f1(first_conf, weights) - _bootstrap_f1(second_conf, weights)
    estimate = float(f1_score(truth, pred_first, labels=[0, 1, 2, 3, 4], average="macro", zero_division=0)
                     - f1_score(truth, pred_second, labels=[0, 1, 2, 3, 4], average="macro", zero_division=0))
    return {"estimate": estimate, "ci_low": float(np.quantile(values, 0.025)),
            "ci_high": float(np.quantile(values, 0.975)), "flight_logs": int(len(unique))}


def model_comparison_analysis(root: Path, output: Path, seeds: list[int], repetitions: int = 1000) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    protocols = {
        "fixed_chronological": (root / "reports/p3/predictions", root / "reports/p10/direct_five_seeds/predictions"),
        "purged": (root / "reports/p10/purged/p3/predictions", root / "reports/p12/statistics/purged_direct/predictions"),
    }
    for protocol, (cascade_dir, direct_dir) in protocols.items():
        for model_seed in seeds:
            cascade_path = cascade_dir / f"cascade_seed{model_seed}.csv"
            direct_path = direct_dir / f"direct_five_seed{model_seed}.csv"
            if not cascade_path.exists() or not direct_path.exists():
                continue
            result = _paired_method_ci(pd.read_csv(direct_path), pd.read_csv(cascade_path), repetitions, 20260825 + model_seed)
            rows.append({"protocol": protocol, "seed": model_seed, "contrast": "direct_minus_cascade_macro_f1", **result})
    frame = pd.DataFrame(rows)
    frame.to_csv(output / "paired_method_ci_by_seed.csv", index=False, encoding="utf-8-sig")
    aggregated: list[dict[str, Any]] = []
    for protocol, (cascade_dir, direct_dir) in protocols.items():
        available = [model_seed for model_seed in seeds
                     if (cascade_dir / f"cascade_seed{model_seed}.csv").exists()
                     and (direct_dir / f"direct_five_seed{model_seed}.csv").exists()]
        if not available:
            continue
        bootstrap_values: list[np.ndarray] = []
        estimates: list[float] = []
        common_weights: np.ndarray | None = None
        common_groups: np.ndarray | None = None
        for model_seed in available:
            first = pd.read_csv(direct_dir / f"direct_five_seed{model_seed}.csv")
            second = pd.read_csv(cascade_dir / f"cascade_seed{model_seed}.csv")
            merged = first.merge(second, on=["group", "start"], suffixes=("_first", "_second"), validate="one_to_one")
            truth = merged["true_class_first"].to_numpy(dtype=int)
            groups = merged["group"].to_numpy()
            order, first_conf = _confusions_by_group(truth, merged["predicted_class_first"].to_numpy(dtype=int), groups, [0, 1, 2, 3, 4])
            order2, second_conf = _confusions_by_group(truth, merged["predicted_class_second"].to_numpy(dtype=int), groups, [0, 1, 2, 3, 4])
            if common_groups is None:
                common_groups = order
                common_weights = _bootstrap_weights(len(order), repetitions, 20260825)
            if not np.array_equal(order, common_groups) or not np.array_equal(order2, common_groups):
                raise RuntimeError("model seeds do not share the same flight-log groups")
            bootstrap_values.append(_bootstrap_f1(first_conf, common_weights) - _bootstrap_f1(second_conf, common_weights))
            estimates.append(float(f1_score(truth, merged["predicted_class_first"], labels=[0, 1, 2, 3, 4], average="macro", zero_division=0)
                                   - f1_score(truth, merged["predicted_class_second"], labels=[0, 1, 2, 3, 4], average="macro", zero_division=0)))
        pooled = np.vstack(bootstrap_values).mean(axis=0)
        aggregated.append({
            "protocol": protocol,
            "seeds": int(len(available)),
            "estimate_mean": float(np.mean(estimates)),
            "seed_sd": float(np.std(estimates, ddof=1)) if len(estimates) > 1 else None,
            "paired_flight_log_ci_low": float(np.quantile(pooled, 0.025)),
            "paired_flight_log_ci_high": float(np.quantile(pooled, 0.975)),
            "flight_logs": int(len(common_groups)),
            "interpretation": "flight logs are paired within each seed; bootstrap contrasts are averaged across model seeds",
        })
    pd.DataFrame(aggregated).to_csv(output / "paired_method_summary.csv", index=False, encoding="utf-8-sig")
    summary = {"status": "complete", "comparisons": rows, "aggregate": aggregated}
    (output / "completion_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def replay_two_way_bootstrap(root: Path, output: Path, repetitions: int = 5000) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=True)
    frame = pd.read_csv(root / "reports/p9/mapping_ablation_by_run.csv")
    frame["source_log"] = frame.apply(
        lambda row: str(row.run_id)[len(str(row.mutation_id)) + 2:].removesuffix("__fault"), axis=1
    )
    rng = np.random.default_rng(20260825)
    rows: list[dict[str, Any]] = []
    for mode, part in frame.groupby("mode"):
        logs = sorted(part["source_log"].unique())
        mutations = sorted(part["mutation_id"].unique())
        for metric in ("top1", "top3", "top5", "mrr", "exam"):
            matrix = (
                part.pivot(index="source_log", columns="mutation_id", values=metric)
                .reindex(index=logs, columns=mutations)
                .to_numpy(dtype=float)
            )
            if np.isnan(matrix).any():
                raise ValueError(f"missing replay cell for {mode}/{metric}")
            values = np.empty(repetitions, dtype=float)
            for rep in range(repetitions):
                sampled_logs = rng.integers(0, len(logs), size=len(logs))
                sampled_mutations = rng.integers(0, len(mutations), size=len(mutations))
                values[rep] = float(matrix[np.ix_(sampled_logs, sampled_mutations)].mean())
            rows.append({"mode": mode, "metric": metric, "estimate": float(part[metric].mean()),
                         "ci_low": float(np.quantile(values, 0.025)), "ci_high": float(np.quantile(values, 0.975)),
                         "source_logs": len(logs), "mutation_types": len(mutations), "repetitions": repetitions})
    result = pd.DataFrame(rows)
    result.to_csv(output / "two_way_cluster_bootstrap.csv", index=False, encoding="utf-8-sig")
    by_log = frame.groupby(["mode", "source_log"], as_index=False).agg(
        runs=("run_id", "size"), top1=("top1", "mean"), top3=("top3", "mean"), top5=("top5", "mean"),
        mrr=("mrr", "mean"), exam=("exam", "mean"))
    by_log.to_csv(output / "metrics_by_source_log.csv", index=False, encoding="utf-8-sig")
    by_mutation = frame.groupby(["mode", "mutation_id"], as_index=False).agg(
        runs=("run_id", "size"), top1=("top1", "mean"), top3=("top3", "mean"), top5=("top5", "mean"),
        mrr=("mrr", "mean"), exam=("exam", "mean"))
    by_mutation.to_csv(output / "metrics_by_mutation.csv", index=False, encoding="utf-8-sig")
    summary = {"status": "complete", "results": result.to_dict(orient="records"),
               "boundary": "Two-way cluster bootstrap resamples three source logs and four mutation types independently; intervals remain low-resolution because both cluster counts are small."}
    (output / "completion_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("task", choices=["masking", "models", "replay", "all"])
    parser.add_argument("--output", default="reports/p12/statistics")
    parser.add_argument("--seeds", nargs="*", type=int, default=[0, 1, 2, 3, 4])
    args = parser.parse_args()
    root = Path.cwd()
    output = root / args.output
    results: dict[str, Any] = {}
    if args.task in {"masking", "all"}:
        results["masking"] = masking_paired_analysis(root, output / "masking", args.seeds)
    if args.task in {"models", "all"}:
        results["models"] = model_comparison_analysis(root, output / "models", args.seeds)
    if args.task in {"replay", "all"}:
        results["replay"] = replay_two_way_bootstrap(root, output / "replay")
    print(json.dumps(results, indent=2), flush=True)


if __name__ == "__main__":
    main()
