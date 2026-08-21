"""P9 controlled PX4 SITL mutation preparation and localization evaluation."""

from __future__ import annotations

import argparse
import difflib
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
import yaml

from .baseline import align_log_arrays, descriptor_batch, window_count
from .explainability import _predict_contributions


def load_config(path: str | Path) -> dict[str, Any]:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def _resolve(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def _command_path(name: str) -> str:
    return shutil.which(name) or ""


def check_environment(config: dict[str, Any], root: Path) -> dict[str, Any]:
    source_root = _resolve(root, config["paths"]["px4_source_root"])
    try:
        commit = subprocess.run(
            ["git", "-C", str(source_root), "rev-parse", "HEAD"], check=True,
            capture_output=True, text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        commit = ""
    tools = {name: _command_path(name) for name in ("wsl", "docker", "bash", "make", "cmake", "ninja", "gz", "gazebo")}
    wsl_distributions: list[str] = []
    if tools["wsl"]:
        try:
            result = subprocess.run([tools["wsl"], "-l", "-q"], capture_output=True, timeout=10)
            if result.returncode == 0:
                decoded = result.stdout.decode("utf-16-le", errors="ignore")
                wsl_distributions = [line.strip() for line in decoded.splitlines() if line.strip()]
        except (OSError, subprocess.SubprocessError):
            pass
    docker_ready = False
    if tools["docker"]:
        try:
            docker_ready = subprocess.run(
                [tools["docker"], "info"], capture_output=True, timeout=10
            ).returncode == 0
        except (OSError, subprocess.SubprocessError):
            pass
    requested_distribution = str(config["experiment"].get("wsl_distribution", ""))
    wsl_ready = requested_distribution in wsl_distributions if requested_distribution else bool(wsl_distributions)
    linux_runtime = bool(wsl_ready or docker_ready)
    simulator = bool(tools["gz"] or tools["gazebo"])
    wsl_tools: dict[str, str] = {}
    if wsl_ready:
        for name in ("git", "cmake", "ninja", "make", "g++", "python3"):
            try:
                probe = subprocess.run(
                    [tools["wsl"], "-d", requested_distribution, "--", "bash", "-lc", f"command -v {name}"],
                    capture_output=True, timeout=10,
                )
                wsl_tools[name] = probe.stdout.decode("utf-8", errors="ignore").strip() if probe.returncode == 0 else ""
            except (OSError, subprocess.SubprocessError):
                wsl_tools[name] = ""
    source_ok = commit == str(config["experiment"]["source_commit"])
    toolchain_ready = bool(wsl_tools and all(wsl_tools.values()))
    runnable = bool(source_ok and linux_runtime and toolchain_ready)
    return {
        "status": "ready" if runnable else "blocked",
        "source_commit": commit,
        "expected_source_commit": str(config["experiment"]["source_commit"]),
        "source_commit_matches": source_ok,
        "tools": tools,
        "wsl_distributions": wsl_distributions,
        "requested_wsl_distribution": requested_distribution,
        "wsl_tools": wsl_tools,
        "docker_daemon_ready": docker_ready,
        "linux_runtime_available": linux_runtime,
        "external_simulator_available": simulator,
        "external_simulator_required": False,
        "minimal_posix_toolchain_ready": toolchain_ready,
        "runnable": runnable,
        "blocker": "" if runnable else "The requested WSL distribution and minimal PX4 POSIX build tools are not ready; Gazebo/ROS/QGC/NuttX are intentionally not required.",
    }


def prepare_mutations(config: dict[str, Any], root: Path) -> dict[str, Any]:
    source_root = _resolve(root, config["paths"]["px4_source_root"])
    report_dir = _resolve(root, config["paths"]["report_dir"])
    patch_dir = _resolve(root, config["paths"]["patch_dir"])
    replay_script_dir = _resolve(root, config["paths"]["replay_script_dir"])
    report_dir.mkdir(parents=True, exist_ok=True)
    patch_dir.mkdir(parents=True, exist_ok=True)
    replay_script_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for mutation in config["mutations"]:
        relative = Path(str(mutation["source_file"]))
        source = source_root / relative
        original = source.read_text(encoding="utf-8")
        anchor = str(mutation["anchor"])
        count = original.count(anchor)
        if count != 1:
            raise ValueError(f"{mutation['id']}: expected one anchor in {relative}, found {count}")
        if "replacement" in mutation:
            modified = original.replace(anchor, str(mutation["replacement"]), 1)
        else:
            injected = str(mutation["injected_line"])
            modified = original.replace(anchor, injected + "\n" + anchor, 1)
        diff = "".join(difflib.unified_diff(
            original.splitlines(keepends=True), modified.splitlines(keepends=True),
            fromfile=f"a/{relative.as_posix()}", tofile=f"b/{relative.as_posix()}",
        ))
        patch_path = patch_dir / f"{mutation['id']}.patch"
        patch_path.write_text(diff, encoding="utf-8", newline="\n")
        rc_path = replay_script_dir / f"{mutation['id']}.rcS"
        rc_path.write_text(
            "uorb start\n"
            "param set SDLOG_DIRS_MAX 100\n"
            f"{mutation['startup_command']}\n"
            "logger start -f -t -b 1000\n"
            "sleep 0.5\n"
            "replay start\n",
            encoding="utf-8", newline="\n",
        )
        rules_path = replay_script_dir / f"{mutation['id']}.orb_publisher.rules"
        publisher_task = str(mutation.get("publisher_task", str(mutation["module"]).split("/")[-1]))
        rules_path.write_text(
            f"restrict_topics: {', '.join(mutation['restricted_topics'])}\n"
            f"module: {publisher_task}\n"
            "ignore_others: false\n",
            encoding="utf-8", newline="\n",
        )
        rows.append({
            "mutation_id": mutation["id"], "mutation_class": mutation["class"],
            "ground_truth_module": mutation["module"], "affected_topic": mutation["topic"],
            "source_file": relative.as_posix(), "anchor_occurrences": count,
            "injection_start_s": int(config["experiment"]["injection_start_s"]),
            "patch_file": patch_path.relative_to(root).as_posix(), "patch_bytes": patch_path.stat().st_size,
            "startup_command": mutation["startup_command"], "replay_mode": mutation["replay_mode"],
            "restricted_topics": ";".join(mutation["restricted_topics"]),
            "publisher_task": publisher_task,
            "rc_file": rc_path.relative_to(root).as_posix(),
            "publisher_rules_file": rules_path.relative_to(root).as_posix(),
            "status": "prepared",
        })
    manifest = pd.DataFrame(rows)
    manifest.to_csv(report_dir / "mutation_manifest.csv", index=False, encoding="utf-8-sig")
    environment = check_environment(config, root)
    (report_dir / "environment_check.json").write_text(json.dumps(environment, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    summary = {
        "status": "prepared" if environment["runnable"] else "blocked_environment",
        "mutations_prepared": int(len(manifest)),
        "modules": int(manifest["ground_truth_module"].nunique()),
        "mutation_classes": int(manifest["mutation_class"].nunique()),
        "anchors_validated": bool(manifest["anchor_occurrences"].eq(1).all()),
        "environment": environment,
        "replay_logs": list(config["experiment"]["replay_logs"]),
        "next_command_after_runtime_install": "bash scripts/p9/run_replay_pipeline.sh",
    }
    (report_dir / "completion_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return summary


def localization_metrics(rankings: pd.DataFrame) -> dict[str, float]:
    required = {"run_id", "ground_truth_module", "module", "rank"}
    missing = required - set(rankings.columns)
    if missing:
        raise ValueError(f"module rankings missing columns: {sorted(missing)}")
    run_rows = []
    for run_id, part in rankings.groupby("run_id", sort=False):
        truth = str(part.iloc[0]["ground_truth_module"])
        detected = bool(part.iloc[0].get("ranking_available", part.iloc[0].get("detected", True)))
        match = part.loc[part["module"].astype(str).eq(truth), "rank"] if detected else pd.Series(dtype=float)
        rank = float(match.min()) if len(match) else float("inf")
        module_count = max(1, int(part["module"].nunique()))
        run_rows.append({
            "run_id": run_id, "rank": rank, "rr": 0.0 if not np.isfinite(rank) else 1.0 / rank,
            "top1": float(rank <= 1), "top3": float(rank <= 3), "top5": float(rank <= 5),
            "exam": 1.0 if not np.isfinite(rank) else rank / module_count,
        })
    frame = pd.DataFrame(run_rows)
    return {
        "runs": int(len(frame)), "top1_recall": float(frame["top1"].mean()),
        "top3_recall": float(frame["top3"].mean()), "top5_recall": float(frame["top5"].mean()),
        "mrr": float(frame["rr"].mean()), "map_single_fault": float(frame["rr"].mean()),
        "mean_exam": float(frame["exam"].mean()),
    }


def _windows_from_ulog(
    path: Path,
    channels: list[str],
    mean: np.ndarray,
    std: np.ndarray,
    frequency_hz: float = 10.0,
    window_size: int = 96,
    stride: int = 8,
    horizon: int = 12,
) -> tuple[np.ndarray, np.ndarray]:
    aligned, _, _, _, _ = align_log_arrays(path, channels, {"annotations": []}, frequency_hz)
    normalized = (aligned.astype(np.float32) - mean) / std
    count = window_count(len(normalized), window_size, horizon, stride)
    starts = np.arange(count, dtype=np.int64) * stride
    if not count:
        return np.empty((0, len(channels) * 18), dtype=np.float32), np.empty(0, dtype=float)
    axis = np.arange(window_size, dtype=np.int64)
    features = []
    for lo in range(0, count, 256):
        part = starts[lo:lo + 256]
        features.append(descriptor_batch(normalized[part[:, None] + axis[None, :]]))
    end_seconds = (starts + window_size) / frequency_hz
    return np.concatenate(features, axis=0), end_seconds


def _allocation_matrix(feature_dictionary: pd.DataFrame, edges: pd.DataFrame) -> tuple[list[str], list[str], np.ndarray, np.ndarray]:
    topics = list(dict.fromkeys(feature_dictionary["topic"].astype(str).tolist()))
    modules = sorted(edges["module"].astype(str).unique().tolist())
    topic_index = {topic: index for index, topic in enumerate(topics)}
    module_index = {module: index for index, module in enumerate(modules)}
    feature_topic_codes = feature_dictionary["topic"].astype(str).map(topic_index).to_numpy(np.int32)
    allocation = np.zeros((len(topics), len(modules)), dtype=np.float64)
    for topic in topics:
        mapped = sorted(edges.loc[edges["topic"].eq(topic), "module"].astype(str).unique())
        if mapped:
            weight = 1.0 / len(mapped)
            for module in mapped:
                allocation[topic_index[topic], module_index[module]] = weight
    return topics, modules, feature_topic_codes, allocation


def _windows_to_modules(
    features: np.ndarray,
    stage2: Any,
    feature_topic_codes: np.ndarray,
    allocation: np.ndarray,
) -> np.ndarray:
    if not len(features):
        return np.empty((0, allocation.shape[1]), dtype=np.float64)
    _, signed = _predict_contributions(stage2, features, 256)
    topic_values = np.zeros((len(features), allocation.shape[0]), dtype=np.float64)
    for feature_index, topic_code in enumerate(feature_topic_codes):
        topic_values[:, topic_code] += np.abs(signed[:, feature_index])
    return topic_values @ allocation


def _windows_path(root: Path, value: str) -> Path:
    normalized = str(value).replace("\\", "/")
    prefix = "/mnt/d/UAV/"
    if normalized.lower().startswith(prefix.lower()):
        return root / normalized[len(prefix):]
    return Path(value)


def analyze_replay_runs(config: dict[str, Any], root: Path) -> dict[str, Any]:
    paths = config["paths"]
    report_dir = _resolve(root, paths["report_dir"])
    manifest_path = _resolve(root, paths["run_manifest"])
    manifest = pd.read_csv(manifest_path, sep="\t")
    channels = [line.strip() for line in _resolve(root, paths["core_channels"]).read_text(encoding="utf-8").splitlines() if line.strip()]
    feature_dictionary = pd.read_csv(_resolve(root, paths["feature_dictionary"]))
    edges = pd.read_csv(_resolve(root, paths["topic_module_mapping"]))
    _, modules, feature_topic_codes, allocation = _allocation_matrix(feature_dictionary, edges)
    mean = np.load(_resolve(root, paths["scaler_mean"]))
    std = np.load(_resolve(root, paths["scaler_std"]))
    stage1 = joblib.load(_resolve(root, paths["stage1_model"]))
    stage2 = joblib.load(_resolve(root, paths["stage2_model"]))
    stage1_metrics = json.loads(_resolve(root, paths["stage1_metrics"]).read_text(encoding="utf-8"))
    threshold = float(stage1_metrics["val_threshold"])
    injection_s = float(config["experiment"]["injection_start_s"])

    inferred: dict[str, dict[str, Any]] = {}
    errors: list[dict[str, str]] = []
    for row in manifest.itertuples(index=False):
        output = _windows_path(root, str(row.output_ulog))
        if not output.exists():
            errors.append({"run_id": str(row.run_id), "error": "output ULog missing"})
            continue
        try:
            features, times = _windows_from_ulog(output, channels, mean, std)
            scores = stage1.predict_proba(features)[:, 1] if len(features) else np.empty(0)
            module_values = _windows_to_modules(features, stage2, feature_topic_codes, allocation)
            inferred[str(row.run_id)] = {"times": times, "scores": scores, "modules": module_values}
        except Exception as exc:
            errors.append({"run_id": str(row.run_id), "error": f"{type(exc).__name__}: {exc}"})

    ranking_rows: list[dict[str, Any]] = []
    run_rows: list[dict[str, Any]] = []
    fault_rows = manifest.loc[manifest["condition"].eq("fault")]
    for fault in fault_rows.itertuples(index=False):
        baseline_id = str(fault.run_id).rsplit("__", 1)[0] + "__baseline"
        fault_id = str(fault.run_id)
        if fault_id not in inferred or baseline_id not in inferred:
            continue
        fault_data, baseline_data = inferred[fault_id], inferred[baseline_id]
        count = min(len(fault_data["times"]), len(baseline_data["times"]))
        times = fault_data["times"][:count]
        post = times >= injection_s
        detected_windows = post & (fault_data["scores"][:count] >= threshold)
        delta = np.maximum(fault_data["modules"][:count] - baseline_data["modules"][:count], 0.0)
        aggregate = delta[post].mean(axis=0) if post.any() else np.zeros(len(modules))
        gated_aggregate = delta[detected_windows].mean(axis=0) if detected_windows.any() else np.zeros(len(modules))
        order = np.argsort(-aggregate, kind="stable")
        ranks = np.empty(len(modules), dtype=int)
        ranks[order] = np.arange(1, len(modules) + 1)
        gated_order = np.argsort(-gated_aggregate, kind="stable")
        gated_ranks = np.empty(len(modules), dtype=int)
        gated_ranks[gated_order] = np.arange(1, len(modules) + 1)
        truth = str(fault.ground_truth_module)
        truth_index = modules.index(truth) if truth in modules else -1
        detected = bool(detected_windows.any())
        for module_index in order:
            ranking_rows.append({
                "run_id": fault_id, "mutation_id": fault.mutation_id,
                "ground_truth_module": truth, "module": modules[module_index],
                "score": float(aggregate[module_index]), "rank": int(ranks[module_index]),
                "detected": detected, "ranking_available": bool(post.any()),
                "ranking_protocol": "onset_conditioned",
            })

        detection_delay = float(times[np.flatnonzero(detected_windows)[0]] - injection_s) if detected else np.nan
        window_ranks = np.full((count, len(modules)), len(modules) + 1, dtype=int)
        for index in np.flatnonzero(post):
            window_order = np.argsort(-delta[index], kind="stable")
            window_ranks[index, window_order] = np.arange(1, len(modules) + 1)
        delays: dict[str, float] = {}
        gated_delays: dict[str, float] = {}
        for k in (1, 3, 5):
            hit = post & (window_ranks[:, truth_index] <= k) if truth_index >= 0 else np.zeros(count, dtype=bool)
            delays[f"top{k}_delay_s"] = float(times[np.flatnonzero(hit)[0]] - injection_s) if hit.any() else np.nan
            gated_hit = detected_windows & (window_ranks[:, truth_index] <= k) if truth_index >= 0 else np.zeros(count, dtype=bool)
            gated_delays[f"detector_gated_top{k}_delay_s"] = float(times[np.flatnonzero(gated_hit)[0]] - injection_s) if gated_hit.any() else np.nan
        run_rows.append({
            "run_id": fault_id, "mutation_id": fault.mutation_id, "ground_truth_module": truth,
            "detected": detected, "detection_delay_s": detection_delay,
            "ground_truth_rank": int(ranks[truth_index]) if truth_index >= 0 and post.any() else np.nan,
            "detector_gated_ground_truth_rank": int(gated_ranks[truth_index]) if truth_index >= 0 and detected else np.nan,
            "module_count": len(modules), **delays, **gated_delays,
        })

    rankings = pd.DataFrame(ranking_rows)
    runs = pd.DataFrame(run_rows)
    rankings.to_csv(_resolve(root, paths["module_rankings"]), index=False, encoding="utf-8-sig")
    runs.to_csv(report_dir / "replay_run_metrics.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(errors).to_csv(report_dir / "replay_analysis_errors.csv", index=False, encoding="utf-8-sig")
    metrics = localization_metrics(rankings) if len(rankings) else {
        "runs": 0, "top1_recall": 0.0, "top3_recall": 0.0, "top5_recall": 0.0,
        "mrr": 0.0, "map_single_fault": 0.0, "mean_exam": 1.0,
    }
    gated_metrics = localization_metrics(rankings.assign(ranking_available=rankings["detected"])) if len(rankings) else {
        "top1_recall": 0.0, "top3_recall": 0.0, "top5_recall": 0.0,
        "mrr": 0.0, "map_single_fault": 0.0, "mean_exam": 1.0,
    }
    metrics.update({
        "detection_recall": float(runs["detected"].mean()) if len(runs) else 0.0,
        "detector_gated_top1_recall": gated_metrics["top1_recall"],
        "detector_gated_top3_recall": gated_metrics["top3_recall"],
        "detector_gated_top5_recall": gated_metrics["top5_recall"],
        "detector_gated_mrr": gated_metrics["mrr"],
        "detector_gated_mean_exam": gated_metrics["mean_exam"],
        "median_detection_delay_s": float(runs["detection_delay_s"].median()) if len(runs) else np.nan,
        "median_top1_delay_s": float(runs["top1_delay_s"].median()) if len(runs) else np.nan,
        "median_top3_delay_s": float(runs["top3_delay_s"].median()) if len(runs) else np.nan,
        "median_top5_delay_s": float(runs["top5_delay_s"].median()) if len(runs) else np.nan,
        "top1_delay_observed_runs": int(runs["top1_delay_s"].notna().sum()) if len(runs) else 0,
        "top3_delay_observed_runs": int(runs["top3_delay_s"].notna().sum()) if len(runs) else 0,
        "top5_delay_observed_runs": int(runs["top5_delay_s"].notna().sum()) if len(runs) else 0,
        "analysis_errors": int(len(errors)), "stage1_threshold": threshold,
        "ranking_protocol": "onset-conditioned fault-minus-matched-baseline absolute predicted-class TreeSHAP propagated over bidirectional uORB edges",
        "detector_gated_protocol": "same ranking restricted to post-onset windows exceeding the unchanged P2 Stage 1 threshold",
    })
    module_rows = []
    for mutation_id, part in runs.groupby("mutation_id", sort=False):
        ranks_part = pd.to_numeric(part["ground_truth_rank"], errors="coerce")
        finite_ranks = ranks_part[np.isfinite(ranks_part)]
        module_rows.append({
            "mutation_id": mutation_id,
            "ground_truth_module": str(part.iloc[0]["ground_truth_module"]),
            "runs": int(len(part)),
            "top1_recall": float((finite_ranks <= 1).sum() / len(part)),
            "top3_recall": float((finite_ranks <= 3).sum() / len(part)),
            "top5_recall": float((finite_ranks <= 5).sum() / len(part)),
            "mrr": float(np.where(np.isfinite(ranks_part), 1.0 / ranks_part, 0.0).mean()),
            "mean_exam": float(np.where(np.isfinite(ranks_part), ranks_part / part["module_count"], 1.0).mean()),
            "ranks": ";".join(str(int(value)) for value in finite_ranks),
        })
    module_summary = pd.DataFrame(module_rows)
    module_summary.to_csv(report_dir / "localization_by_mutation.csv", index=False, encoding="utf-8-sig")
    (report_dir / "localization_metrics.json").write_text(json.dumps(metrics, indent=2, ensure_ascii=False, allow_nan=True) + "\n", encoding="utf-8")
    completion = {
        "status": "complete",
        "runs": int(len(manifest)),
        "fault_runs": int(len(runs)),
        "mutations": int(manifest["mutation_id"].nunique()),
        "source_logs": int(manifest["replay_log"].nunique()),
        "output_ulogs_present": int(sum(_windows_path(root, str(value)).exists() for value in manifest["output_ulog"])),
        "analysis_errors": int(len(errors)),
        "onset_conditioned_metrics": metrics,
        "primary_limitation": "The unchanged P2 Stage 1 threshold detected 0/12 controlled source-mutation runs; onset-conditioned localization is reported separately and must not be described as end-to-end localization.",
        "legacy_replay_adapter": "The three source ULogs lack ekf2_timestamps. Generic replay therefore uses a matched EKF publication adapter in both conditions; only HS_P9_EKF_FAULT activation differs.",
        "artifacts": [
            "reports/p9/run_manifest.tsv", "reports/p9/replay_logs/",
            "reports/p9/localization_metrics.json", "reports/p9/replay_run_metrics.csv",
            "reports/p9/localization_by_mutation.csv", "reports/p9/module_rankings.csv",
        ],
    }
    (report_dir / "completion_summary.json").write_text(json.dumps(completion, indent=2, ensure_ascii=False, allow_nan=True) + "\n", encoding="utf-8")
    return metrics


def evaluate(config: dict[str, Any], root: Path) -> dict[str, Any]:
    report_dir = _resolve(root, config["paths"]["report_dir"])
    rankings_path = _resolve(root, config["paths"]["module_rankings"])
    runs_path = _resolve(root, config["paths"]["run_manifest"])
    if not runs_path.exists():
        environment = check_environment(config, root)
        raise RuntimeError(
            f"SITL run artifacts are absent ({runs_path}, {rankings_path}). {environment['blocker']}"
        )
    return analyze_replay_runs(config, root)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "check", "evaluate"))
    parser.add_argument("--config", default="configs/p9_sitl_injection.yaml")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    config = load_config(args.config)
    if args.command == "prepare":
        result = prepare_mutations(config, Path.cwd())
    elif args.command == "check":
        result = check_environment(config, Path.cwd())
    else:
        result = evaluate(config, Path.cwd())
    print(json.dumps(result, indent=2, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
