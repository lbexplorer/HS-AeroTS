"""P13 low-cost, inference-only analyses for manuscript revision.

This module never fits or updates a model.  It consumes frozen predictions,
models, feature arrays, and the P8/P12 mapping artifacts to produce three
submission-facing sensitivity analyses:

1. Stage-1-gated real-flight diagnostic evidence;
2. conservative source-tree exclusion sensitivity for PX4FMU_V2/NuttX; and
3. flight/sequence-cluster bootstrap confidence intervals.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Callable

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, f1_score

from .explainability import _mapping_codes, _predict_contributions, aggregate_columns
from .software_mapping import propagate_topic_evidence
from .submission_readiness import MAJORITY_COMMIT, _degree_normalized, _group_commit_table


BOOTSTRAP_SEED = 20260825
BOOTSTRAP_REPETITIONS = 1000
PROPAGATION_MODES = ("producer_only", "consumer_only", "bidirectional")


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def _input_files(root: Path) -> list[Path]:
    files = [
        root / "data/processed/p2/features_original/x_test.npy",
        root / "data/processed/p2/features_original/y_test.npy",
        root / "data/processed/p2/features_original/type_test.npy",
        root / "data/processed/p2/features_original/group_test.npy",
        root / "data/processed/p2/features_original/start_test.npy",
        root / "reports/p8/topic_module_mapping.csv",
        root / "reports/p8/firmware_inventory.csv",
        root / "reports/p2/group_dictionary.csv",
    ]
    patterns = (
        "reports/p3/model_runs/seed*/stage2_lightgbm.joblib",
        "reports/p2/baseline_runs/seed*/test_scores.csv",
        "reports/p3/predictions/*.csv",
        "reports/p10/purged/p2/baseline_runs/seed*/test_scores.csv",
        "reports/p10/purged/p3/predictions/*.csv",
        "reports/p12/statistics/purged_direct/predictions/*.csv",
        "reports/p11/llo/p2/baseline_runs/seed*/test_scores.csv",
        "reports/p11/llo/p3/predictions/*.csv",
        "reports/p10/direct_five_seeds/predictions/*.csv",
        "reports/p6/model_runs/seed*/alfa_scores.csv",
        "reports/p7/flight_scores.csv",
    )
    for pattern in patterns:
        files.extend(root.glob(pattern))
    return sorted({path.resolve() for path in files if path.exists()})


def _hash_manifest(root: Path, files: list[Path]) -> dict[str, str]:
    return {path.relative_to(root).as_posix(): sha256_file(path) for path in files}


def _aggregate_rankings(frame: pd.DataFrame) -> pd.DataFrame:
    result = (
        frame.groupby(["scope", "mode", "module"], as_index=False)
        .agg(
            mean_abs_shap=("mean_abs_shap", "mean"),
            seed_std=("mean_abs_shap", "std"),
            seeds=("seed", "nunique"),
        )
    )
    totals = result.groupby(["scope", "mode"])["mean_abs_shap"].transform("sum")
    result["shap_share"] = np.divide(
        result["mean_abs_shap"], totals,
        out=np.zeros(len(result), dtype=float), where=totals.to_numpy() > 0,
    )
    result["rank"] = (
        result.groupby(["scope", "mode"])["mean_abs_shap"]
        .rank(method="dense", ascending=False).astype(int)
    )
    return result.sort_values(["scope", "mode", "rank", "module"]).reset_index(drop=True)


def _topic_importance(
    values: np.ndarray, topics: list[str], seed: int, scope: str,
) -> pd.DataFrame:
    means = values.mean(axis=0)
    return pd.DataFrame({
        "seed": seed,
        "scope": scope,
        "topic": topics,
        "mean_abs_shap": means,
        "scope_windows": len(values),
    })


def stage1_gated_analysis(root: Path, output: Path, seeds: list[int]) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=True)
    feature_dir = root / "data/processed/p2/features_original"
    x_test = np.load(feature_dir / "x_test.npy", mmap_mode="r")
    groups = np.load(feature_dir / "group_test.npy", mmap_mode="r")
    starts = np.load(feature_dir / "start_test.npy", mmap_mode="r")
    lookup = {(int(group), int(start)): index for index, (group, start) in enumerate(zip(groups, starts, strict=True))}

    group_commit = _group_commit_table(root).set_index("group")
    matching_groups = set(group_commit.index[group_commit["firmware_commit"].eq(MAJORITY_COMMIT)].astype(int))
    features = pd.read_csv(root / "reports/p2/feature_dictionary.csv")
    channel_map = pd.read_csv(root / "reports/p3/channel_subsystem_mapping.csv")
    mapping = _mapping_codes(features, channel_map)
    edges = pd.read_csv(root / "reports/p8/topic_module_mapping.csv")

    count_rows: list[dict[str, Any]] = []
    class_rows: list[dict[str, Any]] = []
    topic_rows: list[pd.DataFrame] = []
    ranking_rows: list[pd.DataFrame] = []

    for seed in seeds:
        cascade = pd.read_csv(root / f"reports/p3/predictions/cascade_seed{seed}.csv")
        true_anomaly = cascade["true_class"].gt(0)
        flagged = cascade["stage1_flagged"].eq(1)
        commit_match = cascade["group"].isin(matching_groups)
        categories = {
            "tp": true_anomaly & flagged,
            "fn": true_anomaly & ~flagged,
            "fp": ~true_anomaly & flagged,
            "tn": ~true_anomaly & ~flagged,
        }
        for scope_name, scope_mask in (("all_test", np.ones(len(cascade), dtype=bool)), ("matching_commit", commit_match)):
            row: dict[str, Any] = {
                "seed": seed,
                "scope": scope_name,
                "windows": int(np.asarray(scope_mask).sum()),
                "flight_logs": int(cascade.loc[scope_mask, "group"].nunique()),
            }
            for name, mask in categories.items():
                selected = np.asarray(scope_mask) & np.asarray(mask)
                row[name] = int(selected.sum())
                row[f"{name}_flight_logs"] = int(cascade.loc[selected, "group"].nunique())
            positives = row["tp"] + row["fn"]
            predicted_positives = row["tp"] + row["fp"]
            row["recall"] = row["tp"] / positives if positives else None
            row["precision"] = row["tp"] / predicted_positives if predicted_positives else None
            count_rows.append(row)

        fp = cascade.loc[commit_match & categories["fp"]]
        for predicted_class, part in fp.groupby("predicted_class"):
            class_rows.append({
                "seed": seed,
                "scope": "matching_commit_false_positive",
                "predicted_class": int(predicted_class),
                "windows": int(len(part)),
                "flight_logs": int(part["group"].nunique()),
            })

        model = joblib.load(root / f"reports/p3/model_runs/seed{seed}/stage2_lightgbm.joblib")
        for scope, mask in (
            ("detected_true_anomaly", commit_match & categories["tp"]),
            ("false_positive", commit_match & categories["fp"]),
        ):
            selected = cascade.loc[mask, ["group", "start"]]
            indices = np.asarray([lookup[(int(row.group), int(row.start))] for row in selected.itertuples(index=False)], dtype=int)
            if len(indices) == 0:
                continue
            _, signed = _predict_contributions(model, np.asarray(x_test[indices]), 256)
            absolute = np.abs(signed)
            channel_values = aggregate_columns(absolute, mapping["feature_channel_codes"], len(mapping["channels"]))
            topic_values = aggregate_columns(channel_values, mapping["channel_topic_codes"], len(mapping["topics"]))
            topic = _topic_importance(topic_values, mapping["topics"], seed, scope)
            topic_rows.append(topic)
            for mode in PROPAGATION_MODES:
                ranking, _ = propagate_topic_evidence(topic, edges, mode)
                ranking["seed"] = seed
                ranking_rows.append(ranking)

    counts = pd.DataFrame(count_rows)
    counts.to_csv(output / "stage1_gate_counts_by_seed.csv", index=False, encoding="utf-8-sig")
    class_distribution = pd.DataFrame(class_rows)
    class_distribution.to_csv(output / "false_positive_stage2_distribution.csv", index=False, encoding="utf-8-sig")
    topics = pd.concat(topic_rows, ignore_index=True)
    topics.to_csv(output / "topic_importance_by_seed.csv", index=False, encoding="utf-8-sig")
    rankings_by_seed = pd.concat(ranking_rows, ignore_index=True)
    rankings_by_seed.to_csv(output / "module_rankings_by_seed.csv", index=False, encoding="utf-8-sig")
    rankings = _aggregate_rankings(rankings_by_seed)
    rankings.to_csv(output / "module_rankings.csv", index=False, encoding="utf-8-sig")

    count_summary = (
        counts.groupby("scope", as_index=False)
        .agg({
            "windows": "first", "flight_logs": "first",
            "tp": "mean", "fn": "mean", "fp": "mean", "tn": "mean",
            "recall": ["mean", "std"], "precision": ["mean", "std"],
        })
    )
    count_summary.columns = ["_".join(column).rstrip("_") if isinstance(column, tuple) else column for column in count_summary.columns]
    count_summary.to_csv(output / "stage1_gate_summary.csv", index=False, encoding="utf-8-sig")
    summary = {
        "status": "complete",
        "analysis_type": "inference-only; no model fitting or threshold selection",
        "firmware_commit": MAJORITY_COMMIT,
        "seeds": seeds,
        "counts": count_summary.to_dict(orient="records"),
        "top_modules": rankings.groupby(["scope", "mode"], sort=False).head(5).to_dict(orient="records"),
        "boundary": "Detected-true-anomaly and false-positive rankings are Stage-1-gated, commit-matched inspection candidates; they are not causal or deployment-build localization results.",
    }
    (output / "completion_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def conservative_exclusion_reason(source_file: str) -> str | None:
    path = source_file.lower().replace("\\", "/")
    rules = (
        ("examples", "/examples/"),
        ("templates", "/templates/"),
        ("tests", "/tests/"),
        ("tests", "/test/"),
        ("posix_platform", "/platforms/posix/"),
        ("qurt_platform", "/platforms/qurt/"),
        ("bebop_specific", "bebop"),
        ("linux_specific", "linux"),
        ("snapdragon_specific", "snapdragon"),
        ("simulation_or_replay", "/simulator/"),
        ("simulation_or_replay", "/replay/"),
        ("simulation_or_replay", "_sim"),
        ("hardware_test", "hwtest"),
    )
    for reason, token in rules:
        if token in path:
            return reason
    return None


def conservative_graph_analysis(root: Path, output: Path, seeds: list[int]) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=True)
    edges = pd.read_csv(root / "reports/p8/topic_module_mapping.csv")
    reasons = edges["source_file"].map(conservative_exclusion_reason)
    excluded = edges.loc[reasons.notna()].copy()
    excluded["exclusion_reason"] = reasons[reasons.notna()].to_numpy()
    filtered = edges.loc[reasons.isna()].copy()
    if len(filtered) >= len(edges) or not set(filtered.index).issubset(set(edges.index)):
        raise RuntimeError("conservative filter did not produce a strict subset")
    excluded.to_csv(output / "excluded_edges.csv", index=False, encoding="utf-8-sig")
    filtered.to_csv(output / "filtered_topic_module_mapping.csv", index=False, encoding="utf-8-sig")

    topics_by_seed = pd.read_csv(root / "reports/p12/commit_matched/topic_importance_by_seed.csv")
    ranking_rows: list[pd.DataFrame] = []
    check_rows: list[pd.DataFrame] = []
    for seed in seeds:
        topic = topics_by_seed.loc[topics_by_seed["seed"].eq(seed)].copy()
        for mode in PROPAGATION_MODES:
            ranking, checks = propagate_topic_evidence(topic, filtered, mode)
            ranking["seed"] = seed
            checks["seed"] = seed
            ranking_rows.append(ranking)
            check_rows.append(checks)
    by_seed = pd.concat(ranking_rows, ignore_index=True)
    by_seed.to_csv(output / "module_rankings_by_seed.csv", index=False, encoding="utf-8-sig")
    ranking = _aggregate_rankings(by_seed.assign(scope="all"))
    ranking.to_csv(output / "module_rankings.csv", index=False, encoding="utf-8-sig")
    checks = pd.concat(check_rows, ignore_index=True)
    checks.to_csv(output / "conservation_checks.csv", index=False, encoding="utf-8-sig")
    conservation_passed = bool((checks.loc[checks["mapped"], "conservation_error"].abs() <= 1e-10).all())

    degree = pd.concat([
        _degree_normalized(ranking.loc[ranking["mode"].eq(mode)].copy(), filtered, mode).assign(mode=mode)
        for mode in PROPAGATION_MODES
    ], ignore_index=True)
    degree.to_csv(output / "degree_normalized_sensitivity.csv", index=False, encoding="utf-8-sig")

    original = pd.read_csv(root / "reports/p12/commit_matched/module_rankings.csv")
    comparisons: list[dict[str, Any]] = []
    rank_changes: list[pd.DataFrame] = []
    for mode in PROPAGATION_MODES:
        before = original.loc[original["mode"].eq(mode), ["module", "rank", "mean_abs_shap"]].copy()
        after = ranking.loc[ranking["mode"].eq(mode), ["module", "rank", "mean_abs_shap"]].copy()
        merged = before.merge(after, on="module", how="outer", suffixes=("_before", "_after"))
        merged.insert(0, "mode", mode)
        merged["rank_change_after_minus_before"] = merged["rank_after"] - merged["rank_before"]
        rank_changes.append(merged)
        common = merged.dropna(subset=["rank_before", "rank_after"])
        spearman = common["rank_before"].corr(common["rank_after"], method="spearman") if len(common) > 1 else float("nan")
        for k in (1, 3, 5, 10):
            before_set = set(before.nsmallest(k, "rank")["module"])
            after_set = set(after.nsmallest(k, "rank")["module"])
            union = before_set | after_set
            comparisons.append({
                "mode": mode, "k": k,
                "top_k_overlap": len(before_set & after_set),
                "top_k_jaccard": len(before_set & after_set) / len(union) if union else 1.0,
                "spearman_common_modules": spearman,
                "common_modules": len(common),
            })
    comparison = pd.DataFrame(comparisons)
    comparison.to_csv(output / "ranking_comparison.csv", index=False, encoding="utf-8-sig")
    pd.concat(rank_changes, ignore_index=True).to_csv(output / "rank_changes.csv", index=False, encoding="utf-8-sig")

    summary = {
        "status": "complete",
        "hardware_scope": "PX4FMU_V2 / NuttX",
        "filter_type": "conservative source-path exclusion sensitivity; not a compiled build-target graph",
        "original_edges": int(len(edges)),
        "filtered_edges": int(len(filtered)),
        "excluded_edges": int(len(excluded)),
        "original_modules": int(edges["module"].nunique()),
        "filtered_modules": int(filtered["module"].nunique()),
        "excluded_reason_counts": excluded["exclusion_reason"].value_counts().to_dict(),
        "topics_retained": int(filtered["topic"].nunique()),
        "contribution_conservation_passed": conservation_passed,
        "ranking_comparison": comparison.to_dict(orient="records"),
        "top_modules": ranking.groupby("mode", sort=False).head(5).to_dict(orient="records"),
        "boundary": "Filtering removes clearly incompatible source paths but does not prove that every retained module was compiled or active in the logged firmware.",
    }
    (output / "completion_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def _bootstrap_weights(groups: int, repetitions: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    weights = np.zeros((repetitions, groups), dtype=np.int16)
    for row in range(repetitions):
        weights[row] = np.bincount(rng.integers(0, groups, size=groups), minlength=groups)
    return weights


def _group_codes(groups: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    unique, codes = np.unique(np.asarray(groups), return_inverse=True)
    return unique, codes


def _weighted_average_precision_sorted(
    labels: np.ndarray, scores: np.ndarray, group_codes: np.ndarray, weights: np.ndarray,
) -> np.ndarray:
    order = np.argsort(-np.asarray(scores), kind="stable")
    labels_sorted = np.asarray(labels, dtype=int)[order]
    scores_sorted = np.asarray(scores, dtype=float)[order]
    groups_sorted = np.asarray(group_codes, dtype=int)[order]
    threshold_ends = np.r_[np.flatnonzero(scores_sorted[:-1] != scores_sorted[1:]), len(scores_sorted) - 1]
    values = np.full(len(weights), np.nan, dtype=float)
    for index, group_weight in enumerate(weights):
        row_weight = group_weight[groups_sorted]
        positive_weight = row_weight * labels_sorted
        total_positive = positive_weight.sum()
        if total_positive <= 0:
            continue
        cumulative_positive = np.cumsum(positive_weight)[threshold_ends]
        cumulative_weight = np.cumsum(row_weight)[threshold_ends]
        precision = np.divide(
            cumulative_positive, cumulative_weight,
            out=np.zeros_like(cumulative_positive, dtype=float), where=cumulative_weight > 0,
        )
        increments = np.diff(np.r_[0, cumulative_positive])
        values[index] = float(np.sum(increments * precision) / total_positive)
    return values


def _macro_f1_bootstrap(
    labels: np.ndarray, predictions: np.ndarray, group_codes: np.ndarray,
    weights: np.ndarray, classes: list[int],
) -> np.ndarray:
    confusions = np.zeros((weights.shape[1], len(classes), len(classes)), dtype=np.int64)
    class_index = {value: index for index, value in enumerate(classes)}
    for truth, guess, group in zip(labels, predictions, group_codes, strict=True):
        if int(truth) in class_index and int(guess) in class_index:
            confusions[int(group), class_index[int(truth)], class_index[int(guess)]] += 1
    combined = np.einsum("bg,gij->bij", weights, confusions, optimize=True).astype(float)
    tp = np.diagonal(combined, axis1=-2, axis2=-1)
    fp = combined.sum(axis=-2) - tp
    fn = combined.sum(axis=-1) - tp
    denominator = 2 * tp + fp + fn
    per_class = np.divide(2 * tp, denominator, out=np.zeros_like(tp), where=denominator > 0)
    return per_class.mean(axis=1)


def _seed_metric(
    frame: pd.DataFrame, metric: str, weights: np.ndarray, expected_groups: np.ndarray,
    truth_column: str, value_column: str, classes: list[int] | None = None,
) -> tuple[float, np.ndarray]:
    groups, codes = _group_codes(frame["group"].to_numpy())
    if not np.array_equal(groups, expected_groups):
        raise RuntimeError("model seeds do not share identical cluster groups")
    truth = frame[truth_column].to_numpy(dtype=int)
    values = frame[value_column].to_numpy()
    if metric == "auprc":
        point = float(average_precision_score(truth, values))
        boot = _weighted_average_precision_sorted(truth, values, codes, weights)
    elif metric == "macro_f1":
        if classes is None:
            raise ValueError("macro_f1 requires explicit classes")
        point = float(f1_score(truth, values, labels=classes, average="macro", zero_division=0))
        boot = _macro_f1_bootstrap(truth, values.astype(int), codes, weights, classes)
    else:
        raise ValueError(f"unsupported metric: {metric}")
    return point, boot


def _summarize_seed_frames(
    frames: list[pd.DataFrame], metric: str, truth_column: str, value_column: str,
    repetitions: int, unit: str, classes: list[int] | None = None,
) -> dict[str, Any]:
    groups, _ = _group_codes(frames[0]["group"].to_numpy())
    weights = _bootstrap_weights(len(groups), repetitions, BOOTSTRAP_SEED)
    points: list[float] = []
    bootstraps: list[np.ndarray] = []
    for frame in frames:
        point, boot = _seed_metric(frame, metric, weights, groups, truth_column, value_column, classes)
        points.append(point)
        bootstraps.append(boot)
    pooled = np.nanmean(np.vstack(bootstraps), axis=0)
    valid = np.isfinite(pooled)
    return {
        "seeds": len(frames),
        "point_mean": float(np.mean(points)),
        "seed_sd": float(np.std(points, ddof=1)) if len(points) > 1 else None,
        "ci_low": float(np.quantile(pooled[valid], 0.025)),
        "ci_high": float(np.quantile(pooled[valid], 0.975)),
        "clusters": int(len(groups)),
        "bootstrap_repetitions": repetitions,
        "valid_bootstrap_repetitions": int(valid.sum()),
        "bootstrap_unit": unit,
    }


def _stage2_frame(path: Path, feature_dir: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    groups = np.load(feature_dir / "group_test.npy", mmap_mode="r")
    frame["group"] = np.asarray(groups[frame["window_index"].to_numpy(dtype=int)])
    return frame


def absolute_uncertainty_analysis(
    root: Path, output: Path, seeds: list[int], repetitions: int = BOOTSTRAP_REPETITIONS,
) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=True)
    protocols = {
        "fixed_chronological": {
            "feature_dir": root / "data/processed/p2/features_original",
            "stage1": root / "reports/p2/baseline_runs",
            "cascade": root / "reports/p3/predictions",
            "direct": root / "reports/p10/direct_five_seeds/predictions",
            "stage2": root / "reports/p3/predictions",
        },
        "purged_14_windows": {
            "feature_dir": root / "data/processed/p10/features_purged",
            "stage1": root / "reports/p10/purged/p2/baseline_runs",
            "cascade": root / "reports/p10/purged/p3/predictions",
            "direct": root / "reports/p12/statistics/purged_direct/predictions",
            "stage2": root / "reports/p10/purged/p3/predictions",
        },
        "leave_log_out": {
            "feature_dir": root / "data/processed/p11/features_leave_log_out",
            "stage1": root / "reports/p11/llo/p2/baseline_runs",
            "cascade": root / "reports/p11/llo/p3/predictions",
            "direct": root / "reports/p11/llo/p3/predictions",
            "stage2": root / "reports/p11/llo/p3/predictions",
        },
    }
    rows: list[dict[str, Any]] = []
    seed_rows: list[dict[str, Any]] = []

    def add_result(protocol: str, task: str, metric: str, frames: list[pd.DataFrame], truth: str,
                   value: str, unit: str, classes: list[int] | None = None) -> None:
        summary = _summarize_seed_frames(frames, metric, truth, value, repetitions, unit, classes)
        rows.append({"protocol": protocol, "task": task, "metric": metric, **summary})
        for seed, frame in zip(seeds, frames, strict=True):
            point, _ = _seed_metric(
                frame, metric,
                _bootstrap_weights(len(np.unique(frame["group"])), 1, BOOTSTRAP_SEED),
                np.unique(frame["group"]), truth, value, classes,
            )
            seed_rows.append({"protocol": protocol, "task": task, "metric": metric, "seed": seed, "point": point})

    for protocol, paths in protocols.items():
        stage1 = [pd.read_csv(paths["stage1"] / f"seed{seed}/test_scores.csv") for seed in seeds]
        add_result(protocol, "stage1", "auprc", stage1, "label", "score", "flight_log")
        stage2 = [_stage2_frame(paths["stage2"] / f"stage2_seed{seed}.csv", paths["feature_dir"]) for seed in seeds]
        add_result(protocol, "stage2_anomaly_only", "macro_f1", stage2, "true_class", "predicted_class", "flight_log", [1, 2, 3, 4])
        cascade = [pd.read_csv(paths["cascade"] / f"cascade_seed{seed}.csv") for seed in seeds]
        add_result(protocol, "cascade_five_class", "macro_f1", cascade, "true_class", "predicted_class", "flight_log", [0, 1, 2, 3, 4])
        direct = [pd.read_csv(paths["direct"] / f"direct_five_seed{seed}.csv") for seed in seeds]
        add_result(protocol, "direct_five_class", "macro_f1", direct, "true_class", "predicted_class", "flight_log", [0, 1, 2, 3, 4])

    alfa = [pd.read_csv(root / f"reports/p6/model_runs/seed{seed}/alfa_scores.csv") for seed in seeds]
    add_result("alfa_zero_shot", "stage1", "auprc", alfa, "label", "score", "sequence")
    unknown_all = pd.read_csv(root / "reports/p7/flight_scores.csv")
    unknown = [unknown_all.loc[unknown_all["seed"].eq(seed)].copy() for seed in seeds]
    add_result("uncategorized_screening", "flight_level", "auprc", unknown, "label", "top_fraction_mean", "flight_log")

    result = pd.DataFrame(rows)
    result.to_csv(output / "absolute_metric_cluster_ci.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(seed_rows).to_csv(output / "absolute_metric_points_by_seed.csv", index=False, encoding="utf-8-sig")
    summary = {
        "status": "complete",
        "bootstrap_seed": BOOTSTRAP_SEED,
        "bootstrap_repetitions": repetitions,
        "aggregation": "cluster bootstrap within each seed; replicate metrics averaged across model seeds",
        "results": result.to_dict(orient="records"),
        "boundary": "Seed SD describes training-seed variation; cluster intervals describe sampling variation over complete flight logs or ALFA sequences.",
    }
    (output / "completion_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def run_all(root: Path, output: Path, seeds: list[int], repetitions: int) -> dict[str, Any]:
    files = _input_files(root)
    before = _hash_manifest(root, files)
    results = {
        "stage1_gated": stage1_gated_analysis(root, output / "stage1_gated", seeds),
        "conservative_graph": conservative_graph_analysis(root, output / "conservative_graph", seeds),
        "absolute_uncertainty": absolute_uncertainty_analysis(root, output / "absolute_uncertainty", seeds, repetitions),
    }
    after = _hash_manifest(root, files)
    unchanged = before == after
    integrity = {
        "status": "pass" if unchanged else "fail",
        "files_checked": len(files),
        "all_inputs_unchanged": unchanged,
        "before": before,
        "after": after,
    }
    (output / "input_integrity.json").write_text(json.dumps(integrity, indent=2) + "\n", encoding="utf-8")
    if not unchanged:
        raise RuntimeError("one or more frozen inputs changed during P13")
    completion = {
        "status": "complete",
        "training_performed": False,
        "new_data_collected": False,
        "new_baselines_added": False,
        "px4_replay_performed": False,
        "input_integrity": integrity,
        "analyses": results,
    }
    (output / "completion_summary.json").write_text(json.dumps(completion, indent=2) + "\n", encoding="utf-8")
    return completion


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("task", choices=["stage1-gated", "conservative-graph", "uncertainty", "all"])
    parser.add_argument("--output", default="reports/p13")
    parser.add_argument("--seeds", nargs="*", type=int, default=[0, 1, 2, 3, 4])
    parser.add_argument("--repetitions", type=int, default=BOOTSTRAP_REPETITIONS)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    root = Path.cwd()
    output = root / args.output
    if args.task == "all":
        result = run_all(root, output, args.seeds, args.repetitions)
    elif args.task == "stage1-gated":
        result = stage1_gated_analysis(root, output / "stage1_gated", args.seeds)
    elif args.task == "conservative-graph":
        result = conservative_graph_analysis(root, output / "conservative_graph", args.seeds)
    else:
        result = absolute_uncertainty_analysis(root, output / "absolute_uncertainty", args.seeds, args.repetitions)
    print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    main()
