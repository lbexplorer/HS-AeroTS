"""P7 weakly supervised flight-level screening of Uncategorized logs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import lightgbm as lgb
import numpy as np
import pandas as pd
import yaml
from sklearn.metrics import average_precision_score, f1_score, roc_auc_score

from .baseline import evaluate_scores


def aggregate_flights(scores: np.ndarray, groups: np.ndarray, fraction: float) -> pd.DataFrame:
    rows = []
    for group in np.unique(groups):
        values = np.asarray(scores[groups == group], dtype=float)
        count = max(1, int(np.ceil(len(values) * fraction)))
        rows.append({"group": int(group), "windows": len(values),
                     "top_fraction_mean": float(np.partition(values, -count)[-count:].mean()),
                     "mean_score": float(values.mean()), "max_score": float(values.max())})
    return pd.DataFrame(rows)


def _resolve(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def _load_split(feature_dir: Path, split: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    return (np.load(feature_dir / f"x_{split}.npy", mmap_mode="r"),
            np.load(feature_dir / f"y_{split}.npy", mmap_mode="r").astype(np.int32),
            np.load(feature_dir / f"group_{split}.npy", mmap_mode="r").astype(np.int32))


def run(config: dict[str, Any], root: Path) -> dict[str, Any]:
    paths = config["paths"]
    feature_dir = _resolve(root, paths["feature_dir"])
    report_dir = _resolve(root, paths["report_dir"])
    report_dir.mkdir(parents=True, exist_ok=True)
    groups_df = pd.read_csv(_resolve(root, paths["group_dictionary"]))
    annotations = pd.read_csv(_resolve(root, paths["annotations"]))
    classes = annotations.groupby("log_key")["class"].agg(lambda x: set(x.dropna()))
    unknown_keys = {key for key, values in classes.items() if "Uncategorized" in values}
    normal_keys = {key for key, values in classes.items() if values == {"Normal"}}
    unknown_groups = set(groups_df.loc[groups_df.log_key.isin(unknown_keys), "group"].astype(int))
    normal_groups = set(groups_df.loc[groups_df.log_key.isin(normal_keys), "group"].astype(int))

    x_train, y_train, g_train = _load_split(feature_dir, "train")
    x_val, y_val, g_val = _load_split(feature_dir, "validation")
    x_test, _, g_test = _load_split(feature_dir, "test")
    train_keep = ~np.isin(g_train, list(unknown_groups))
    val_known = ~np.isin(g_val, list(unknown_groups))
    eval_groups = unknown_groups | normal_groups
    test_keep = np.isin(g_test, list(eval_groups))
    val_normal_keep = np.isin(g_val, list(normal_groups))
    if not val_normal_keep.any() or not test_keep.any():
        raise RuntimeError("no eligible validation/test groups for P7")

    seed_rows, flight_rows = [], []
    for seed in config["experiment"]["seeds"]:
        params = dict(config["model"])
        stopping = int(params.pop("early_stopping_rounds"))
        model = lgb.LGBMClassifier(objective="binary", random_state=int(seed),
                                   n_jobs=int(config["experiment"]["n_jobs"]), verbosity=-1, **params)
        model.fit(x_train[train_keep], y_train[train_keep],
                  eval_set=[(x_val[val_known], y_val[val_known])], eval_metric="average_precision",
                  callbacks=[lgb.early_stopping(stopping, verbose=False)])
        val_scores = model.predict_proba(x_val)[:, 1]
        known_metrics = evaluate_scores(y_val[val_known], val_scores[val_known], g_val[val_known])
        test_scores = model.predict_proba(x_test[test_keep])[:, 1]
        test_groups = g_test[test_keep]
        aggregated = aggregate_flights(test_scores, test_groups, float(config["experiment"]["top_fraction"]))
        val_aggregated = aggregate_flights(val_scores[val_normal_keep], g_val[val_normal_keep],
                                           float(config["experiment"]["top_fraction"]))
        threshold = float(np.quantile(val_aggregated.top_fraction_mean,
                                      1.0 - float(config["experiment"]["normal_fpr"]), method="higher"))
        aggregated["label"] = aggregated.group.isin(unknown_groups).astype(int)
        aggregated["seed"] = int(seed)
        aggregated["prediction"] = (aggregated.top_fraction_mean >= threshold).astype(int)
        aggregated = aggregated.merge(groups_df[["group", "log_key"]], on="group", how="left")
        flight_rows.extend(aggregated.to_dict("records"))
        labels = aggregated.label.to_numpy()
        scores = aggregated.top_fraction_mean.to_numpy()
        seed_rows.append({"seed": int(seed), "known_validation_window_threshold": known_metrics["threshold"],
                          "flight_threshold": threshold, "flight_auprc": float(average_precision_score(labels, scores)),
                          "flight_auroc": float(roc_auc_score(labels, scores)),
                          "flight_f1": float(f1_score(labels, aggregated.prediction)),
                          "unknown_recall": float(aggregated.loc[aggregated.label.eq(1), "prediction"].mean()),
                          "normal_specificity": float(1.0 - aggregated.loc[aggregated.label.eq(0), "prediction"].mean()),
                          "train_windows": int(train_keep.sum()), "excluded_unknown_train_windows": int((~train_keep).sum())})
        print(json.dumps(seed_rows[-1]), flush=True)

    metrics = pd.DataFrame(seed_rows)
    metrics.to_csv(report_dir / "seed_metrics.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(flight_rows).to_csv(report_dir / "flight_scores.csv", index=False, encoding="utf-8-sig")
    summary_metrics = {name: {"mean": float(metrics[name].mean()), "std": float(metrics[name].std(ddof=1))}
                       for name in ["flight_auprc", "flight_auroc", "flight_f1", "unknown_recall", "normal_specificity"]}
    summary = {"status": "complete", "scope": "flight-level weak-label screening only",
               "unknown_logs": len(unknown_groups), "pure_normal_logs": len(normal_groups),
               "protocol": "P2 fixed chronological test slice; Uncategorized groups excluded from retraining",
               "threshold_policy": "95th percentile of pure-Normal validation-flight top-10%-mean score",
               "metrics": summary_metrics,
               "limitation": "Uncategorized annotations have no temporal ranges; point-wise and Event-F1 claims are unsupported."}
    (report_dir / "completion_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="configs/p7_unknown_fault.yaml")
    args = parser.parse_args()
    config = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    print(json.dumps(run(config, Path.cwd()), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
