"""Evaluate P9 topic-to-module propagation alternatives on existing replay logs."""

from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from hs_aerots.baseline import align_log_arrays, descriptor_batch, window_count
from hs_aerots.explainability import _predict_contributions
from hs_aerots.sitl_injection import _resolve, _windows_path
from hs_aerots.robustness import grouped_bootstrap


ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "configs" / "p9_sitl_injection.yaml"


def windows(path: Path, channels: list[str], mean: np.ndarray, std: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    aligned, _, _, _, _ = align_log_arrays(path, channels, {"annotations": []}, 10.0)
    normalized = (aligned.astype(np.float32) - mean) / std
    count = window_count(len(normalized), 96, 12, 8)
    starts = np.arange(count, dtype=np.int64) * 8
    axis = np.arange(96, dtype=np.int64)
    features = [descriptor_batch(normalized[part[:, None] + axis[None, :]]) for part in (starts[i:i + 256] for i in range(0, count, 256))]
    return np.concatenate(features, axis=0), (starts + 96) / 10.0


def allocation(feature_dictionary: pd.DataFrame, edges: pd.DataFrame, mode: str, seed: int = 20260821) -> tuple[list[str], np.ndarray, np.ndarray]:
    topics = list(dict.fromkeys(feature_dictionary["topic"].astype(str).tolist()))
    modules = sorted(edges["module"].astype(str).unique().tolist())
    topic_index = {topic: i for i, topic in enumerate(topics)}
    module_index = {module: i for i, module in enumerate(modules)}
    selected = edges
    if mode in {"producer_only", "consumer_only"}:
        role = "publisher" if mode == "producer_only" else "subscriber"
        selected = edges.loc[edges["role"].eq(role)]
    matrix = np.zeros((len(topics), len(modules)), dtype=np.float64)
    if mode == "topic_only":
        return topics, feature_dictionary["topic"].astype(str).map(topic_index).to_numpy(np.int32), np.eye(len(topics), dtype=np.float64)
    rng = np.random.default_rng(seed)
    for topic in topics:
        mapped = sorted(selected.loc[selected["topic"].eq(topic), "module"].astype(str).unique())
        if mode == "random_mapping":
            mapped = rng.choice(modules, size=max(1, len(mapped)), replace=False).tolist()
        if mapped:
            for module in mapped:
                matrix[topic_index[topic], module_index[module]] = 1.0 / len(mapped)
    codes = feature_dictionary["topic"].astype(str).map(topic_index).to_numpy(np.int32)
    return modules, codes, matrix


def ranks(scores: np.ndarray, truth: str, modules: list[str]) -> tuple[float, float, float, float, float]:
    if truth not in modules:
        return 0.0, 0.0, 0.0, 0.0, 1.0
    order = np.argsort(-scores, kind="stable")
    rank = int(np.flatnonzero(np.asarray(modules, dtype=object)[order] == truth)[0]) + 1
    return float(rank <= 1), float(rank <= 3), float(rank <= 5), 1.0 / rank, rank / len(modules)


def main() -> None:
    import yaml

    config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    paths = config["paths"]
    report = _resolve(ROOT, paths["report_dir"])
    manifest = pd.read_csv(_resolve(ROOT, paths["run_manifest"]), sep="\t")
    mutation_manifest = pd.read_csv(report / "mutation_manifest.csv")
    mutation_topics = mutation_manifest.set_index("mutation_id")["affected_topic"].to_dict()
    channels = [line.strip() for line in _resolve(ROOT, paths["core_channels"]).read_text(encoding="utf-8").splitlines() if line.strip()]
    dictionary = pd.read_csv(_resolve(ROOT, paths["feature_dictionary"]))
    edges = pd.read_csv(_resolve(ROOT, paths["topic_module_mapping"]))
    mean, std = np.load(_resolve(ROOT, paths["scaler_mean"])), np.load(_resolve(ROOT, paths["scaler_std"])),
    stage1 = joblib.load(_resolve(ROOT, paths["stage1_model"]))
    stage2 = joblib.load(_resolve(ROOT, paths["stage2_model"]))
    threshold = json.loads(_resolve(ROOT, paths["stage1_metrics"]).read_text(encoding="utf-8"))["val_threshold"]
    inferred: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]] = {}
    for row in manifest.itertuples(index=False):
        features, times = windows(_windows_path(ROOT, str(row.output_ulog)), channels, mean, std)
        _, signed = _predict_contributions(stage2, features, 256)
        topic_values = np.zeros((len(features), len(set(dictionary["topic"]))), dtype=np.float64)
        topic_codes = dictionary["topic"].astype(str).map({topic: i for i, topic in enumerate(dict.fromkeys(dictionary["topic"].astype(str)))})
        for feature_index, topic_code in enumerate(topic_codes):
            topic_values[:, int(topic_code)] += np.abs(signed[:, feature_index])
        scores = stage1.predict_proba(features)[:, 1]
        inferred[str(row.run_id)] = times, scores, topic_values

    modes = ["bidirectional", "producer_only", "consumer_only", "topic_only", "random_mapping"]
    rows: list[dict[str, object]] = []
    for mode in modes:
        modules, codes, matrix = allocation(dictionary, edges, mode)
        for fault in manifest.loc[manifest["condition"].eq("fault")].itertuples(index=False):
            baseline_id = str(fault.run_id).rsplit("__", 1)[0] + "__baseline"
            ft, fs, fv = inferred[str(fault.run_id)]
            bt, bs, bv = inferred[baseline_id]
            count = min(len(ft), len(bt))
            post = ft[:count] >= float(config["experiment"]["injection_start_s"])
            detected = post & (fs[:count] >= threshold)
            fault_modules = fv[:count] @ matrix
            baseline_modules = bv[:count] @ matrix
            delta = np.maximum(fault_modules - baseline_modules, 0.0)
            aggregate = delta[post].mean(axis=0)
            truth = mutation_topics[str(fault.mutation_id)] if mode == "topic_only" else str(fault.ground_truth_module)
            top1, top3, top5, rr, exam = ranks(aggregate, truth, modules)
            rows.append({"mode": mode, "run_id": str(fault.run_id), "mutation_id": str(fault.mutation_id), "topic": mutation_topics[str(fault.mutation_id)], "detected": bool(detected.any()), "top1": top1, "top3": top3, "top5": top5, "mrr": rr, "exam": exam})

    frame = pd.DataFrame(rows)
    summary = []
    for mode, part in frame.groupby("mode", sort=False):
        result = {"mode": mode, "runs": int(len(part))}
        for metric in ("top1", "top3", "top5", "mrr", "exam"):
            values = part[metric].to_numpy(float)
            boot = grouped_bootstrap(part["run_id"].to_numpy(), lambda selected: float(values[selected].mean()), 1000, 20260821 + len(summary), 0.95)
            result[metric] = float(values.mean())
            result[f"{metric}_ci_low"] = boot["ci_low"]
            result[f"{metric}_ci_high"] = boot["ci_high"]
        result["detection_recall"] = float(part["detected"].mean())
        summary.append(result)
    frame.to_csv(report / "mapping_ablation_by_run.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(summary).to_csv(report / "mapping_ablation_summary.csv", index=False, encoding="utf-8-sig")
    (report / "mapping_ablation_summary.json").write_text(json.dumps({"status": "complete", "experiment_name": "Controlled PX4 ULog Replay with Source-Level Mutations", "modes": summary, "bootstrap_unit": "controlled mutation replay fault run", "bootstrap_repetitions": 1000}, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
