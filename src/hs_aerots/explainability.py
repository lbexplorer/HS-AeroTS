"""P4 hierarchical TreeSHAP aggregation and quantitative validation."""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

import joblib
import numpy as np
import pandas as pd
import yaml

from .diagnosis import LABEL_NAMES, SUBSYSTEM_LABELS, classification_metrics, stage2_subset


SUBSYSTEM_TO_LABEL = {LABEL_NAMES[label]: label for label in SUBSYSTEM_LABELS}


def load_config(path: str | Path) -> dict[str, Any]:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def _resolve(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def reshape_multiclass_contributions(
    contributions: np.ndarray, n_rows: int, n_classes: int, n_features: int
) -> np.ndarray:
    """Convert LightGBM's flattened multiclass contributions to row/class/term."""
    values = np.asarray(contributions)
    expected = n_classes * (n_features + 1)
    if values.shape != (n_rows, expected):
        raise ValueError(f"expected contribution shape {(n_rows, expected)}, got {values.shape}")
    return values.reshape(n_rows, n_classes, n_features + 1)


def aggregate_columns(values: np.ndarray, codes: np.ndarray, n_groups: int) -> np.ndarray:
    """Sum columns into explicit groups without assuming contiguous feature order."""
    values = np.asarray(values)
    codes = np.asarray(codes, dtype=np.int32)
    if values.ndim != 2 or values.shape[1] != len(codes):
        raise ValueError("values and grouping codes have incompatible shapes")
    result = np.zeros((values.shape[0], n_groups), dtype=np.float64)
    for group in range(n_groups):
        result[:, group] = values[:, codes == group].sum(axis=1)
    return result


def consistency_at_k(
    channel_importance: np.ndarray,
    true_labels: np.ndarray,
    channel_labels: np.ndarray,
    k: int,
    row_mask: np.ndarray | None = None,
) -> dict[str, float | int]:
    """Measure whether top-k channels belong to the ground-truth subsystem."""
    values = np.asarray(channel_importance)
    truth = np.asarray(true_labels, dtype=np.int32)
    mapping = np.asarray(channel_labels, dtype=np.int32)
    if row_mask is not None:
        mask = np.asarray(row_mask, dtype=bool)
        values, truth = values[mask], truth[mask]
    if not 1 <= k <= values.shape[1]:
        raise ValueError("k must be within the number of channels")
    if len(values) == 0:
        return {"windows": 0, "consistency": float("nan"), "hit_rate": float("nan"), "weighted_consistency": float("nan")}
    top = np.argpartition(-values, kth=k - 1, axis=1)[:, :k]
    match = mapping[top] == truth[:, None]
    denominator = values.sum(axis=1)
    true_mass = (values * (mapping[None, :] == truth[:, None])).sum(axis=1)
    weighted = np.divide(true_mass, denominator, out=np.zeros_like(true_mass), where=denominator > 0)
    return {
        "windows": int(len(values)),
        "consistency": float(match.mean()),
        "hit_rate": float(match.any(axis=1).mean()),
        "weighted_consistency": float(weighted.mean()),
    }


def random_consistency_baseline(
    true_labels: np.ndarray, channel_labels: np.ndarray, k: int
) -> dict[str, float]:
    """Exact expectation for uniformly selecting k channels without replacement."""
    truth = np.asarray(true_labels, dtype=np.int32)
    mapping = np.asarray(channel_labels, dtype=np.int32)
    n_channels = len(mapping)
    strict, hit = [], []
    for label in truth:
        matching = int((mapping == label).sum())
        strict.append(matching / n_channels)
        if n_channels - matching < k:
            hit.append(1.0)
        else:
            hit.append(1.0 - math.comb(n_channels - matching, k) / math.comb(n_channels, k))
    return {"consistency": float(np.mean(strict)), "hit_rate": float(np.mean(hit))}


def mask_columns(values: np.ndarray, columns: np.ndarray, replacement: np.ndarray) -> np.ndarray:
    masked = np.asarray(values).copy()
    masked[:, columns] = replacement[columns]
    return masked


def _load_split(feature_dir: Path, split: str) -> dict[str, np.ndarray]:
    return {
        "x": np.load(feature_dir / f"x_{split}.npy", mmap_mode="r"),
        "binary": np.load(feature_dir / f"y_{split}.npy", mmap_mode="r"),
        "type": np.load(feature_dir / f"type_{split}.npy", mmap_mode="r"),
        "group": np.load(feature_dir / f"group_{split}.npy", mmap_mode="r"),
        "start": np.load(feature_dir / f"start_{split}.npy", mmap_mode="r"),
    }


def _mapping_codes(features: pd.DataFrame, channel_map: pd.DataFrame) -> dict[str, Any]:
    if features["feature_index"].tolist() != list(range(len(features))):
        raise ValueError("feature dictionary is not in model feature order")
    channel_meta = (
        features.groupby(["channel", "topic"], sort=False, as_index=False)
        .agg(feature_count=("feature", "size"))
    )
    channel_meta = channel_meta.merge(
        channel_map[["channel", "subsystem"]], on="channel", how="left", validate="one_to_one"
    )
    if channel_meta["subsystem"].isna().any():
        missing = channel_meta.loc[channel_meta["subsystem"].isna(), "channel"].tolist()
        raise ValueError(f"channels lack subsystem mappings: {missing[:5]}")
    channels = channel_meta["channel"].tolist()
    topics = list(dict.fromkeys(channel_meta["topic"].tolist()))
    subsystems = list(dict.fromkeys(channel_meta["subsystem"].tolist()))
    channel_index = {value: index for index, value in enumerate(channels)}
    topic_index = {value: index for index, value in enumerate(topics)}
    subsystem_index = {value: index for index, value in enumerate(subsystems)}
    return {
        "feature_channel_codes": features["channel"].map(channel_index).to_numpy(np.int32),
        "channel_topic_codes": channel_meta["topic"].map(topic_index).to_numpy(np.int32),
        "channel_subsystem_codes": channel_meta["subsystem"].map(subsystem_index).to_numpy(np.int32),
        "channel_labels": channel_meta["subsystem"].map(SUBSYSTEM_TO_LABEL).fillna(0).to_numpy(np.int32),
        "channel_meta": channel_meta,
        "channels": channels,
        "topics": topics,
        "subsystems": subsystems,
    }


def _predict_contributions(model: Any, x: np.ndarray, batch_size: int) -> tuple[np.ndarray, np.ndarray]:
    """Return predicted classes and predicted-class signed TreeSHAP values."""
    n_rows, n_features = x.shape
    n_classes = len(model.classes_)
    prediction = np.empty(n_rows, dtype=np.int32)
    selected = np.empty((n_rows, n_features), dtype=np.float64)
    for start in range(0, n_rows, batch_size):
        stop = min(start + batch_size, n_rows)
        part = np.asarray(x[start:stop], dtype=np.float32)
        probability = model.booster_.predict(part, num_iteration=model.best_iteration_)
        predicted = np.argmax(probability, axis=1).astype(np.int32)
        flat = model.booster_.predict(part, pred_contrib=True, num_iteration=model.best_iteration_)
        shaped = reshape_multiclass_contributions(flat, len(part), n_classes, n_features)
        selected[start:stop] = shaped[np.arange(len(part)), predicted, :-1]
        prediction[start:stop] = predicted + 1
    return prediction, selected


def _booster_predict_labels(model: Any, values: np.ndarray) -> np.ndarray:
    probability = model.booster_.predict(values, num_iteration=model.best_iteration_)
    return np.argmax(probability, axis=1).astype(np.int32) + 1


def _importance_rows(
    seed: int,
    level: str,
    names: list[str],
    values: np.ndarray,
    true_labels: np.ndarray,
    meta: pd.DataFrame | None = None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    scopes: list[tuple[str, np.ndarray]] = [("all", np.ones(len(true_labels), dtype=bool))]
    scopes.extend((LABEL_NAMES[label], true_labels == label) for label in SUBSYSTEM_LABELS)
    for scope, mask in scopes:
        mean_values = values[mask].mean(axis=0)
        order = np.argsort(-mean_values, kind="stable")
        for rank, index in enumerate(order, start=1):
            row: dict[str, Any] = {
                "seed": seed,
                "scope": scope,
                "level": level,
                "rank": rank,
                "name": names[index],
                "mean_abs_shap": float(mean_values[index]),
                "scope_windows": int(mask.sum()),
            }
            if meta is not None:
                for column in meta.columns:
                    row[column] = meta.iloc[index][column]
            rows.append(row)
    return rows


def _summarize_importance(rows: list[dict[str, Any]]) -> pd.DataFrame:
    frame = pd.DataFrame(rows)
    keys = ["scope", "level", "name"]
    extra = [column for column in ("descriptor", "channel", "topic", "subsystem", "feature_count") if column in frame]
    summary = frame.groupby(keys, sort=False, as_index=False).agg(
        mean_abs_shap=("mean_abs_shap", "mean"),
        std_abs_shap=("mean_abs_shap", "std"),
        seeds=("seed", "nunique"),
        scope_windows=("scope_windows", "first"),
    )
    if extra:
        metadata = frame[keys + extra].drop_duplicates(keys)
        summary = summary.merge(metadata, on=keys, how="left", validate="one_to_one")
    if "feature_count" in summary:
        summary["mean_abs_shap_per_feature"] = summary["mean_abs_shap"] / summary["feature_count"]
    summary["shap_share"] = summary["mean_abs_shap"] / summary.groupby("scope")["mean_abs_shap"].transform("sum")
    summary["rank"] = summary.groupby("scope")["mean_abs_shap"].rank(method="first", ascending=False).astype(int)
    return summary.sort_values(["scope", "rank"], kind="stable")


def _train_reference(x_train: np.ndarray, sample_size: int, seed: int) -> tuple[np.ndarray, np.ndarray]:
    count = min(sample_size, len(x_train))
    indices = np.sort(np.random.default_rng(seed).choice(len(x_train), size=count, replace=False))
    reference = np.nanmedian(np.asarray(x_train[indices], dtype=np.float32), axis=0)
    reference = np.nan_to_num(reference, nan=0.0, posinf=0.0, neginf=0.0).astype(np.float32)
    return reference, indices


def _metric_pair(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    metrics, _, _ = classification_metrics(y_true, y_pred, SUBSYSTEM_LABELS)
    return {"macro_f1": metrics["macro_f1"], "balanced_accuracy": metrics["balanced_accuracy"]}


def _masking_rows(
    model: Any,
    seed: int,
    x_test: np.ndarray,
    y_test: np.ndarray,
    ranking: np.ndarray,
    reference: np.ndarray,
    k_values: Iterable[int],
    random_repeats: int,
) -> list[dict[str, Any]]:
    baseline_pred = _booster_predict_labels(model, x_test)
    baseline = _metric_pair(y_test, baseline_pred)
    rows: list[dict[str, Any]] = []
    work = np.asarray(x_test, dtype=np.float32).copy()
    rng = np.random.default_rng(seed + 41027)
    for k in k_values:
        top = np.asarray(ranking[:k], dtype=np.int32)
        work[:, top] = reference[top]
        metrics = _metric_pair(y_test, _booster_predict_labels(model, work))
        work[:, top] = x_test[:, top]
        rows.append({
            "seed": seed, "k": int(k), "mask": "validation_shap_top_k", "repeat": -1,
            "baseline_macro_f1": baseline["macro_f1"], "masked_macro_f1": metrics["macro_f1"],
            "macro_f1_drop": baseline["macro_f1"] - metrics["macro_f1"],
            "baseline_balanced_accuracy": baseline["balanced_accuracy"],
            "masked_balanced_accuracy": metrics["balanced_accuracy"],
            "balanced_accuracy_drop": baseline["balanced_accuracy"] - metrics["balanced_accuracy"],
        })
        for repeat in range(random_repeats):
            chosen = np.sort(rng.choice(x_test.shape[1], size=k, replace=False))
            work[:, chosen] = reference[chosen]
            metrics = _metric_pair(y_test, _booster_predict_labels(model, work))
            work[:, chosen] = x_test[:, chosen]
            rows.append({
                "seed": seed, "k": int(k), "mask": "uniform_random_k", "repeat": repeat,
                "baseline_macro_f1": baseline["macro_f1"], "masked_macro_f1": metrics["macro_f1"],
                "macro_f1_drop": baseline["macro_f1"] - metrics["macro_f1"],
                "baseline_balanced_accuracy": baseline["balanced_accuracy"],
                "masked_balanced_accuracy": metrics["balanced_accuracy"],
                "balanced_accuracy_drop": baseline["balanced_accuracy"] - metrics["balanced_accuracy"],
            })
    return rows


def _evidence_rows(
    seed: int,
    channel_values: np.ndarray,
    true_labels: np.ndarray,
    predicted_labels: np.ndarray,
    indices: np.ndarray,
    groups: np.ndarray,
    starts: np.ndarray,
    channel_meta: pd.DataFrame,
    top_k: int,
) -> list[dict[str, Any]]:
    if seed != 0:
        return []
    top = np.argpartition(-channel_values, kth=top_k - 1, axis=1)[:, :top_k]
    rows: list[dict[str, Any]] = []
    for row_index in range(len(channel_values)):
        ordered = top[row_index][np.argsort(-channel_values[row_index, top[row_index]], kind="stable")]
        for rank, channel_index in enumerate(ordered, start=1):
            meta = channel_meta.iloc[channel_index]
            rows.append({
                "seed": seed,
                "window_index": int(indices[row_index]),
                "group": str(groups[indices[row_index]]),
                "start": float(starts[indices[row_index]]),
                "true_class": LABEL_NAMES[int(true_labels[row_index])],
                "predicted_class": LABEL_NAMES[int(predicted_labels[row_index])],
                "rank": rank,
                "channel": meta["channel"],
                "topic": meta["topic"],
                "subsystem": meta["subsystem"],
                "abs_shap": float(channel_values[row_index, channel_index]),
            })
    return rows


def run_explainability(config: dict[str, Any], root: Path, seeds: list[int] | None = None) -> dict[str, Any]:
    paths = config["paths"]
    feature_dir = _resolve(root, paths["feature_dir"])
    report_dir = _resolve(root, paths["report_dir"])
    report_dir.mkdir(parents=True, exist_ok=True)
    features = pd.read_csv(_resolve(root, paths["feature_dictionary"]))
    channel_map = pd.read_csv(_resolve(root, paths["channel_mapping"]))
    mapping = _mapping_codes(features, channel_map)
    splits = {name: _load_split(feature_dir, name) for name in ("train", "validation", "test")}
    subset: dict[str, dict[str, np.ndarray]] = {}
    for name in ("validation", "test"):
        x, labels, indices = stage2_subset(splits[name]["x"], splits[name]["binary"], splits[name]["type"])
        subset[name] = {"x": x, "y": labels, "indices": indices}

    settings = config["explanation"]
    seeds = seeds or list(config["experiment"]["seeds"])
    reference, reference_indices = _train_reference(
        splits["train"]["x"], int(settings["reference_sample_size"]), int(settings["reference_seed"])
    )
    all_importance: dict[str, list[dict[str, Any]]] = defaultdict(list)
    masking_rows: list[dict[str, Any]] = []
    consistency_rows: list[dict[str, Any]] = []
    evidence_rows: list[dict[str, Any]] = []
    conservation_errors: list[float] = []

    feature_meta = features[["descriptor", "channel", "topic"]].copy()
    feature_meta["feature_count"] = 1
    channel_meta = mapping["channel_meta"][["channel", "topic", "subsystem", "feature_count"]].copy()
    topic_meta = (
        mapping["channel_meta"].groupby("topic", sort=False, as_index=False)
        .agg(feature_count=("feature_count", "sum"))
    )
    subsystem_meta = (
        mapping["channel_meta"].groupby("subsystem", sort=False, as_index=False)
        .agg(feature_count=("feature_count", "sum"))
    )

    for seed in seeds:
        print(f"P4 TreeSHAP seed={seed}", flush=True)
        model_path = _resolve(root, paths["p3_model_runs"]) / f"seed{seed}" / "stage2_lightgbm.joblib"
        model = joblib.load(model_path)
        val_prediction, val_signed = _predict_contributions(model, subset["validation"]["x"], int(settings["batch_size"]))
        test_prediction, test_signed = _predict_contributions(model, subset["test"]["x"], int(settings["batch_size"]))
        val_abs, test_abs = np.abs(val_signed), np.abs(test_signed)
        val_ranking = np.argsort(-val_abs.mean(axis=0), kind="stable")

        channel_values = aggregate_columns(
            test_abs, mapping["feature_channel_codes"], len(mapping["channels"])
        )
        topic_values = aggregate_columns(
            channel_values, mapping["channel_topic_codes"], len(mapping["topics"])
        )
        subsystem_values = aggregate_columns(
            channel_values, mapping["channel_subsystem_codes"], len(mapping["subsystems"])
        )
        totals = np.column_stack((test_abs.sum(axis=1), channel_values.sum(axis=1), topic_values.sum(axis=1), subsystem_values.sum(axis=1)))
        conservation_errors.append(float(np.max(np.abs(totals - totals[:, [0]]))))

        all_importance["feature"].extend(_importance_rows(
            seed, "feature", features["feature"].tolist(), test_abs, subset["test"]["y"], feature_meta
        ))
        all_importance["channel"].extend(_importance_rows(
            seed, "channel", mapping["channels"], channel_values, subset["test"]["y"], channel_meta
        ))
        all_importance["topic"].extend(_importance_rows(
            seed, "topic", mapping["topics"], topic_values, subset["test"]["y"], topic_meta
        ))
        all_importance["subsystem"].extend(_importance_rows(
            seed, "subsystem", mapping["subsystems"], subsystem_values, subset["test"]["y"], subsystem_meta
        ))

        masking_rows.extend(_masking_rows(
            model, seed, subset["test"]["x"], subset["test"]["y"], val_ranking, reference,
            settings["masking_k"], int(settings["random_mask_repeats"]),
        ))
        correct = test_prediction == subset["test"]["y"]
        for k in settings["consistency_k"]:
            scopes: list[tuple[str, np.ndarray | None]] = [("all", None), ("correct_predictions", correct)]
            scopes.extend((LABEL_NAMES[label], subset["test"]["y"] == label) for label in SUBSYSTEM_LABELS)
            for scope, row_mask in scopes:
                observed = consistency_at_k(
                    channel_values, subset["test"]["y"], mapping["channel_labels"], int(k), row_mask
                )
                truth = subset["test"]["y"] if row_mask is None else subset["test"]["y"][row_mask]
                random = random_consistency_baseline(truth, mapping["channel_labels"], int(k))
                consistency_rows.append({
                    "seed": seed, "scope": scope, "k": int(k), **observed,
                    "random_consistency": random["consistency"],
                    "random_hit_rate": random["hit_rate"],
                    "consistency_lift": observed["consistency"] - random["consistency"],
                    "hit_rate_lift": observed["hit_rate"] - random["hit_rate"],
                })
        evidence_rows.extend(_evidence_rows(
            seed, channel_values, subset["test"]["y"], test_prediction,
            subset["test"]["indices"], splits["test"]["group"], splits["test"]["start"],
            mapping["channel_meta"], int(settings["evidence_top_k"]),
        ))
        print(json.dumps({
            "seed": seed,
            "top_feature": features.iloc[int(val_ranking[0])]["feature"],
            "max_conservation_error": conservation_errors[-1],
        }, ensure_ascii=False), flush=True)

    for level, rows in all_importance.items():
        pd.DataFrame(rows).to_csv(report_dir / f"shap_{level}_importance_by_seed.csv", index=False, encoding="utf-8-sig")
        _summarize_importance(rows).to_csv(report_dir / f"shap_{level}_importance.csv", index=False, encoding="utf-8-sig")
    masking = pd.DataFrame(masking_rows)
    masking.to_csv(report_dir / "masking_results_by_repeat.csv", index=False, encoding="utf-8-sig")
    masking_summary = masking.groupby(["mask", "k"], as_index=False).agg(
        runs=("macro_f1_drop", "size"),
        macro_f1_drop_mean=("macro_f1_drop", "mean"),
        macro_f1_drop_std=("macro_f1_drop", "std"),
        balanced_accuracy_drop_mean=("balanced_accuracy_drop", "mean"),
        balanced_accuracy_drop_std=("balanced_accuracy_drop", "std"),
    )
    masking_summary.to_csv(report_dir / "masking_results.csv", index=False, encoding="utf-8-sig")
    consistency = pd.DataFrame(consistency_rows)
    consistency.to_csv(report_dir / "consistency_at_k_by_seed.csv", index=False, encoding="utf-8-sig")
    consistency_summary = consistency.groupby(["scope", "k"], as_index=False).agg(
        seeds=("seed", "nunique"),
        windows=("windows", "first"),
        consistency_mean=("consistency", "mean"),
        consistency_std=("consistency", "std"),
        hit_rate_mean=("hit_rate", "mean"),
        hit_rate_std=("hit_rate", "std"),
        weighted_consistency_mean=("weighted_consistency", "mean"),
        weighted_consistency_std=("weighted_consistency", "std"),
        random_consistency=("random_consistency", "first"),
        random_hit_rate=("random_hit_rate", "first"),
        consistency_lift_mean=("consistency_lift", "mean"),
        hit_rate_lift_mean=("hit_rate_lift", "mean"),
    )
    consistency_summary.to_csv(report_dir / "consistency_at_k.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(evidence_rows).to_csv(report_dir / "window_evidence_seed0.csv", index=False, encoding="utf-8-sig")

    top_mask = masking_summary[masking_summary["mask"] == "validation_shap_top_k"].set_index("k")
    random_mask = masking_summary[masking_summary["mask"] == "uniform_random_k"].set_index("k")
    mask_advantages = {
        str(k): float(top_mask.loc[k, "macro_f1_drop_mean"] - random_mask.loc[k, "macro_f1_drop_mean"])
        for k in settings["masking_k"]
    }
    all_consistency = consistency_summary[consistency_summary["scope"] == "all"]
    protocol = {
        "tree_shap_target": "predicted Stage 2 class raw score",
        "aggregation": "absolute feature contributions are summed feature -> channel -> PX4 topic -> subsystem",
        "class_conditional_scope": "rows are grouped by ground-truth anomaly class; explained output remains each row's predicted class",
        "masking_ranking": "mean absolute predicted-class TreeSHAP on validation anomaly windows only",
        "masking_replacement": "per-feature median from a deterministic sample of training windows only",
        "consistency": "fraction of top-k channels mapped to the ground-truth subsystem; Shared is a non-match",
        "weighted_consistency": "ground-truth subsystem absolute SHAP mass divided by total channel absolute SHAP mass",
        "random_consistency": "exact uniform-without-replacement channel baseline",
        "lightgbm_extra_term": "the final contribution term is the expected value and is excluded from feature aggregation",
        "seeds": seeds,
        "reference_sample_size": int(len(reference_indices)),
        "reference_seed": int(settings["reference_seed"]),
    }
    (report_dir / "explanation_protocol.json").write_text(
        json.dumps(protocol, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    completion = {
        "status": "complete",
        "protocol": "fixed P2 per-log chronological split; validation-only ranking; training-only masking reference",
        "seeds": seeds,
        "validation_stage2_windows": int(len(subset["validation"]["y"])),
        "test_stage2_windows": int(len(subset["test"]["y"])),
        "features": int(len(features)),
        "channels": int(len(mapping["channels"])),
        "topics": int(len(mapping["topics"])),
        "subsystems_including_shared": int(len(mapping["subsystems"])),
        "max_aggregation_conservation_error": float(max(conservation_errors)),
        "masking_macro_f1_drop_advantage_over_random": mask_advantages,
        "consistency": all_consistency.to_dict(orient="records"),
        "completion_criterion": "hierarchical conservation holds; top-k masking is more damaging than random at >=1 k; Consistency@K exceeds exact random baseline at >=1 k",
        "criterion_passed": bool(
            max(conservation_errors) < 1e-8
            and any(value > 0 for value in mask_advantages.values())
            and (all_consistency["consistency_lift_mean"] > 0).any()
        ),
    }
    (report_dir / "completion_summary.json").write_text(
        json.dumps(completion, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return completion


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="configs/p4_explainability.yaml")
    parser.add_argument("--seeds", nargs="*", type=int)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    config = load_config(args.config)
    print(json.dumps(run_explainability(config, Path.cwd(), args.seeds), ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
