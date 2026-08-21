"""Retrain only the P11 Stage-2 Random Forest under the fixed LLO protocol."""

from __future__ import annotations

from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import yaml

from hs_aerots.diagnosis import (
    SUBSYSTEM_LABELS,
    _load_split,
    classification_metrics,
    probability_metrics,
    summarize,
    train_random_forest,
)


ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "configs/p11_leave_log_out_p3.yaml"


def main() -> None:
    config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    feature_dir = ROOT / config["paths"]["feature_dir"]
    report_dir = ROOT / config["paths"]["report_dir"]
    split = _load_split(feature_dir, "test")
    train = _load_split(feature_dir, "train")
    train_keep = (train["binary"] > 0) & np.isin(train["type"], SUBSYSTEM_LABELS)
    test_keep = (split["binary"] > 0) & np.isin(split["type"], SUBSYSTEM_LABELS)
    test_indices = np.flatnonzero(test_keep)

    metrics_path = report_dir / "seed_metrics.csv"
    class_path = report_dir / "per_class_metrics.csv"
    metric_frame = pd.read_csv(metrics_path)
    class_frame = pd.read_csv(class_path)
    metric_frame = metric_frame.loc[~metric_frame["method"].eq("stage2_random_forest")]
    class_frame = class_frame.loc[~class_frame["method"].eq("stage2_random_forest")]
    metric_rows = metric_frame.to_dict("records")
    class_rows = class_frame.to_dict("records")

    for seed in range(5):
        model = train_random_forest(
            train["x"][train_keep], train["type"][train_keep],
            config["random_forest"], seed, int(config["experiment"]["n_jobs"]),
        )
        probability = model.predict_proba(split["x"][test_keep])
        prediction = model.predict(split["x"][test_keep]).astype(int)
        metrics, per_class, matrix = classification_metrics(split["type"][test_keep], prediction, SUBSYSTEM_LABELS)
        metrics.update(probability_metrics(split["type"][test_keep], probability))
        metric_rows.append({"method": "stage2_random_forest", "seed": seed, **metrics})
        class_rows.extend({"method": "stage2_random_forest", "seed": seed, **row} for row in per_class)
        run_dir = report_dir / f"model_runs/seed{seed}"
        run_dir.mkdir(parents=True, exist_ok=True)
        joblib.dump(model, run_dir / "stage2_random_forest.joblib")
        pd.DataFrame({"window_index": test_indices, "true_class": split["type"][test_keep], "predicted_class": prediction}).to_csv(
            report_dir / f"predictions/stage2_random_forest_seed{seed}.csv", index=False,
        )
        pd.DataFrame(matrix).to_csv(report_dir / f"confusion_matrices/stage2_random_forest_seed{seed}.csv", index=False)

    pd.DataFrame(metric_rows).to_csv(metrics_path, index=False, encoding="utf-8-sig")
    pd.DataFrame(class_rows).to_csv(class_path, index=False, encoding="utf-8-sig")
    pd.DataFrame(summarize(metric_rows)).to_csv(report_dir / "method_summary.csv", index=False, encoding="utf-8-sig")


if __name__ == "__main__":
    main()
