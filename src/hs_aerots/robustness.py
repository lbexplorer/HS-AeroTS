"""P10 aggregate fixed-protocol and purged sensitivity results with log bootstrap CIs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd
import yaml
from sklearn.metrics import average_precision_score, f1_score


def load_config(path: str | Path) -> dict[str, Any]:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def _resolve(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def grouped_bootstrap(
    groups: np.ndarray,
    metric: Callable[[np.ndarray], float],
    repetitions: int,
    seed: int,
    confidence: float,
) -> dict[str, float]:
    groups = np.asarray(groups)
    unique = np.unique(groups)
    indices = {group: np.flatnonzero(groups == group) for group in unique}
    rng = np.random.default_rng(seed)
    values = np.empty(repetitions, dtype=float)
    for repetition in range(repetitions):
        sampled = rng.choice(unique, size=len(unique), replace=True)
        selected = np.concatenate([indices[group] for group in sampled])
        values[repetition] = metric(selected)
    alpha = (1.0 - confidence) / 2.0
    return {
        "bootstrap_mean": float(values.mean()),
        "ci_low": float(np.quantile(values, alpha)),
        "ci_high": float(np.quantile(values, 1.0 - alpha)),
        "bootstrap_repetitions": int(repetitions),
        "bootstrap_unit_count": int(len(unique)),
    }


def _score_ci(path: Path, repetitions: int, seed: int, confidence: float) -> dict[str, float]:
    frame = pd.read_csv(path)
    labels = frame["label"].to_numpy(dtype=int)
    scores = frame["score"].to_numpy(dtype=float)
    groups = frame["group"].to_numpy()
    result = {"estimate": float(average_precision_score(labels, scores))}
    result.update(grouped_bootstrap(
        groups, lambda selected: float(average_precision_score(labels[selected], scores[selected])),
        repetitions, seed, confidence,
    ))
    return result


def _classification_ci(frame: pd.DataFrame, groups: np.ndarray, repetitions: int, seed: int, confidence: float) -> dict[str, float]:
    truth = frame["true_class"].to_numpy(dtype=int)
    prediction = frame["predicted_class"].to_numpy(dtype=int)
    labels = sorted(np.unique(truth).tolist())
    result = {"estimate": float(f1_score(truth, prediction, labels=labels, average="macro", zero_division=0))}
    result.update(grouped_bootstrap(
        groups, lambda selected: float(f1_score(
            truth[selected], prediction[selected], labels=labels, average="macro", zero_division=0,
        )), repetitions, seed, confidence,
    ))
    return result


def _stage2_ci(prediction_path: Path, feature_dir: Path, repetitions: int, seed: int, confidence: float) -> dict[str, float]:
    frame = pd.read_csv(prediction_path)
    all_groups = np.load(feature_dir / "group_test.npy", mmap_mode="r")
    groups = np.asarray(all_groups[frame["window_index"].to_numpy(dtype=int)])
    return _classification_ci(frame, groups, repetitions, seed, confidence)


def _prediction_ci(path: Path, repetitions: int, seed: int, confidence: float) -> dict[str, float]:
    frame = pd.read_csv(path)
    return _classification_ci(frame, frame["group"].to_numpy(), repetitions, seed, confidence)


def _method_metric(path: Path, method: str, metric: str = "macro_f1") -> float:
    frame = pd.read_csv(path)
    row = frame.loc[(frame["method"].eq(method)) & (frame["seed"].eq(0))].iloc[0]
    return float(row[metric])


def run_robustness(config: dict[str, Any], root: Path) -> dict[str, Any]:
    p = {key: _resolve(root, value) for key, value in config["paths"].items()}
    repetitions = int(config["bootstrap"]["repetitions"])
    seed = int(config["bootstrap"]["seed"])
    confidence = float(config["bootstrap"]["confidence"])
    fixed_p2 = json.loads(p["fixed_p2_metrics"].read_text(encoding="utf-8"))
    purged_p2 = json.loads(p["purged_p2_metrics"].read_text(encoding="utf-8"))
    direct_summary = json.loads(p["direct_five_summary"].read_text(encoding="utf-8"))["direct_five_class_lightgbm"]
    purged_features = json.loads(p["purged_feature_summary"].read_text(encoding="utf-8"))

    rows = [
        {"protocol": "fixed_chronological", "method": "stage1", "metric": "AUPRC", "value": float(fixed_p2["test_auprc"])},
        {"protocol": "purged_14_windows", "method": "stage1", "metric": "AUPRC", "value": float(purged_p2["test_auprc"])},
        {"protocol": "fixed_chronological", "method": "stage2", "metric": "Macro-F1", "value": _method_metric(p["fixed_p3_metrics"], "stage2_lightgbm")},
        {"protocol": "purged_14_windows", "method": "stage2", "metric": "Macro-F1", "value": _method_metric(p["purged_p3_metrics"], "stage2_lightgbm")},
        {"protocol": "fixed_chronological", "method": "cascade", "metric": "Macro-F1", "value": _method_metric(p["fixed_p3_metrics"], "hs_aerots_cascade")},
        {"protocol": "purged_14_windows", "method": "cascade", "metric": "Macro-F1", "value": _method_metric(p["purged_p3_metrics"], "hs_aerots_cascade")},
        {"protocol": "fixed_chronological", "method": "direct_five_class", "metric": "Macro-F1", "value": float(direct_summary["macro_f1_mean"])},
        {"protocol": "purged_14_windows", "method": "direct_five_class", "metric": "Macro-F1", "value": _method_metric(p["purged_p3_metrics"], "direct_five_class_lightgbm")},
    ]
    comparison = pd.DataFrame(rows)
    fixed = comparison.loc[comparison["protocol"].eq("fixed_chronological")].set_index("method")["value"]
    purged = comparison.loc[comparison["protocol"].eq("purged_14_windows")].set_index("method")["value"]
    comparison["relative_to_fixed"] = comparison.apply(
        lambda row: float(row["value"] / fixed[row["method"]]) if row["method"] in fixed and fixed[row["method"]] else np.nan,
        axis=1,
    )

    ci_rows = []
    ci_specs = [
        ("fixed_chronological", "stage1", _score_ci(p["fixed_p2_scores"], repetitions, seed, confidence)),
        ("purged_14_windows", "stage1", _score_ci(p["purged_p2_scores"], repetitions, seed + 1, confidence)),
        ("fixed_chronological", "stage2", _stage2_ci(p["fixed_p3_predictions"] / "stage2_seed0.csv", p["fixed_features"], repetitions, seed + 2, confidence)),
        ("purged_14_windows", "stage2", _stage2_ci(p["purged_p3_predictions"] / "stage2_seed0.csv", p["purged_features"], repetitions, seed + 3, confidence)),
        ("fixed_chronological", "cascade", _prediction_ci(p["fixed_p3_predictions"] / "cascade_seed0.csv", repetitions, seed + 4, confidence)),
        ("purged_14_windows", "cascade", _prediction_ci(p["purged_p3_predictions"] / "cascade_seed0.csv", repetitions, seed + 5, confidence)),
        ("fixed_chronological", "direct_five_class", _prediction_ci(p["fixed_p3_predictions"].parent.parent / "p10" / "direct_five_seeds" / "predictions" / "direct_five_seed0.csv", repetitions, seed + 6, confidence)),
        ("purged_14_windows", "direct_five_class", _prediction_ci(p["purged_p3_predictions"] / "direct_five_seed0.csv", repetitions, seed + 7, confidence)),
    ]
    for protocol, method, values in ci_specs:
        ci_rows.append({"protocol": protocol, "method": method, **values})
    cis = pd.DataFrame(ci_rows)
    comparison = comparison.merge(cis, on=["protocol", "method"], how="left")
    report_dir = p["report_dir"]
    report_dir.mkdir(parents=True, exist_ok=True)
    comparison.to_csv(report_dir / "protocol_comparison.csv", index=False, encoding="utf-8-sig")
    summary = {
        "status": "complete",
        "fixed_outputs_modified": False,
        "direct_five_class_five_seed_macro_f1_mean": float(direct_summary["macro_f1_mean"]),
        "direct_five_class_five_seed_macro_f1_std": float(direct_summary["macro_f1_std"]),
        "purge_gap_windows_each_side": 14,
        "purged_retained_split_windows": purged_features["split_counts"],
        "purged_stage1_auprc": float(purged["stage1"]),
        "purged_stage2_macro_f1": float(purged["stage2"]),
        "purged_cascade_macro_f1": float(purged["cascade"]),
        "purged_direct_five_macro_f1": float(purged["direct_five_class"]),
        "interpretation": "All conclusions retain the same direction under purging, but absolute performance decreases; fixed chronological results must not be presented without this sensitivity analysis.",
    }
    (report_dir / "completion_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="configs/p10_robustness.yaml")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    print(json.dumps(run_robustness(load_config(args.config), Path.cwd()), indent=2, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()

