"""Submission-readiness analyses for firmware-coherent mapping and semantic audits."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

from .diagnosis import LABEL_NAMES, SUBSYSTEM_LABELS, stage2_subset
from .explainability import (
    _importance_rows,
    _mapping_codes,
    _predict_contributions,
    _summarize_importance,
    aggregate_columns,
    consistency_at_k,
    random_consistency_baseline,
)
from .software_mapping import (
    ORB_ID_PATTERN,
    PUBLISH_HINTS,
    SUBSCRIBE_HINTS,
    _role_for_context,
    module_from_path,
    propagate_topic_evidence,
)


MAJORITY_COMMIT = "82aa24adfca29321cfd1209e287eab6c2b16780e"


def document_subsystem_for_channel(channel: str, topic: str) -> tuple[str, str]:
    """Map channels by PX4 message-field semantics without using SHAP values."""
    field = channel.split(".", 1)[1] if "." in channel else channel
    if topic == "vehicle_vision_position":
        return "External Position", "external-vision position field"

    altitude_fields = {
        ("distance_sensor", "current_distance"),
        ("ekf2_innovations", "hagl_innov"),
        ("ekf2_innovations", "vel_pos_innov[5]"),
        ("estimator_status", "hagl_test_ratio"),
        ("estimator_status", "hgt_test_ratio"),
        ("estimator_status", "pos_vert_accuracy"),
        ("vehicle_local_position", "z"),
        ("vehicle_local_position", "vz"),
        ("vehicle_local_position", "az"),
        ("vehicle_local_position", "epv"),
        ("vehicle_local_position", "dist_bottom"),
        ("vehicle_local_position", "dist_bottom_rate"),
    }
    if (topic, field) in altitude_fields or topic == "vehicle_land_detected":
        return "Altitude", "vertical position/range/landing-state field"

    global_fields = {
        ("ekf2_innovations", "heading_innov"),
        ("ekf2_innovations", "vel_pos_innov[3]"),
        ("ekf2_innovations", "vel_pos_innov[4]"),
        ("estimator_status", "pos_horiz_accuracy"),
        ("estimator_status", "pos_test_ratio"),
        ("vehicle_local_position", "x"),
        ("vehicle_local_position", "y"),
        ("vehicle_local_position", "vx"),
        ("vehicle_local_position", "vy"),
        ("vehicle_local_position", "ax"),
        ("vehicle_local_position", "ay"),
        ("vehicle_local_position", "eph"),
    }
    if (topic, field) in global_fields:
        return "Global Position", "horizontal position/velocity/accuracy field"

    mechanical_topics = {
        "actuator_controls_0",
        "actuator_outputs",
        "battery_status",
        "cpuload",
        "rate_ctrl_status",
        "sensor_combined",
        "sensor_preflight",
        "vehicle_attitude",
        "vehicle_attitude_setpoint",
        "vehicle_rates_setpoint",
    }
    if topic in mechanical_topics or (topic == "estimator_status" and field.startswith("vibe[")):
        return "Mechanical/Electrical", "actuation/power/inertial/control-health field"
    return "Shared", "control/context or cross-domain estimator field"


def build_document_mapping(features: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for channel, part in features.groupby("channel", sort=False):
        topic = str(part.iloc[0]["topic"])
        subsystem, rationale = document_subsystem_for_channel(str(channel), topic)
        rows.append({
            "channel": str(channel),
            "topic": topic,
            "subsystem": subsystem,
            "rationale": rationale,
            "feature_count": int(len(part)),
        })
    return pd.DataFrame(rows)


def _split(feature_dir: Path, name: str) -> dict[str, np.ndarray]:
    return {
        "x": np.load(feature_dir / f"x_{name}.npy", mmap_mode="r"),
        "binary": np.load(feature_dir / f"y_{name}.npy", mmap_mode="r"),
        "type": np.load(feature_dir / f"type_{name}.npy", mmap_mode="r"),
        "group": np.load(feature_dir / f"group_{name}.npy", mmap_mode="r"),
    }


def _group_commit_table(root: Path) -> pd.DataFrame:
    groups = pd.read_csv(root / "reports/p2/group_dictionary.csv")[["group", "log_key"]]
    firmware = pd.read_csv(root / "reports/p8/firmware_inventory.csv")[["log_key", "firmware_commit"]]
    groups["log_key"] = groups["log_key"].astype(str)
    firmware["log_key"] = firmware["log_key"].astype(str)
    return groups.merge(firmware, on="log_key", how="left", validate="one_to_one")


def _aggregate_module_seeds(rankings: pd.DataFrame) -> pd.DataFrame:
    result = (
        rankings.groupby(["mode", "module"], as_index=False)
        .agg(mean_abs_shap=("mean_abs_shap", "mean"), seed_std=("mean_abs_shap", "std"), seeds=("seed", "nunique"))
    )
    result["shap_share"] = result["mean_abs_shap"] / result.groupby("mode")["mean_abs_shap"].transform("sum")
    result["rank"] = result.groupby("mode")["mean_abs_shap"].rank(method="dense", ascending=False).astype(int)
    return result.sort_values(["mode", "rank", "module"]).reset_index(drop=True)


def _degree_normalized(ranking: pd.DataFrame, edges: pd.DataFrame, mode: str) -> pd.DataFrame:
    selected = edges.copy()
    if mode == "producer_only":
        selected = selected[selected["role"].eq("publisher")]
    elif mode == "consumer_only":
        selected = selected[selected["role"].eq("subscriber")]
    degree = selected.groupby("module")["topic"].nunique().rename("mapped_topic_degree")
    out = ranking.merge(degree, on="module", how="left")
    out["mapped_topic_degree"] = out["mapped_topic_degree"].fillna(1).astype(int)
    out["degree_normalized_score"] = out["mean_abs_shap"] / out["mapped_topic_degree"]
    out["degree_normalized_share"] = out["degree_normalized_score"] / out["degree_normalized_score"].sum()
    out["degree_normalized_rank"] = out["degree_normalized_score"].rank(method="dense", ascending=False).astype(int)
    return out.sort_values(["degree_normalized_rank", "module"]).reset_index(drop=True)


def recompute_commit_matched(root: Path, output: Path, seeds: list[int]) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=True)
    feature_dir = root / "data/processed/p2/features_original"
    features = pd.read_csv(root / "reports/p2/feature_dictionary.csv")
    original_map = pd.read_csv(root / "reports/p3/channel_subsystem_mapping.csv")
    mapping = _mapping_codes(features, original_map)
    test = _split(feature_dir, "test")
    x_stage2, y_stage2, stage2_indices = stage2_subset(test["x"], test["binary"], test["type"])
    group_commit = _group_commit_table(root).set_index("group")
    matching_groups = set(group_commit.index[group_commit["firmware_commit"].eq(MAJORITY_COMMIT)].astype(int))
    matched = np.isin(test["group"][stage2_indices], np.fromiter(matching_groups, dtype=int))
    matched_indices = stage2_indices[matched]
    x_matched = np.asarray(x_stage2[matched])
    y_matched = np.asarray(y_stage2[matched])

    topic_meta = (
        mapping["channel_meta"].groupby("topic", sort=False, as_index=False)
        .agg(feature_count=("feature_count", "sum"))
    )
    topic_seed_rows: list[dict[str, Any]] = []
    ranking_seeds: list[pd.DataFrame] = []
    edges = pd.read_csv(root / "reports/p8/topic_module_mapping.csv")
    for seed in seeds:
        print(f"commit-matched TreeSHAP seed={seed}", flush=True)
        model = joblib.load(root / f"reports/p3/model_runs/seed{seed}/stage2_lightgbm.joblib")
        _, signed = _predict_contributions(model, x_matched, 256)
        absolute = np.abs(signed)
        channel_values = aggregate_columns(absolute, mapping["feature_channel_codes"], len(mapping["channels"]))
        topic_values = aggregate_columns(channel_values, mapping["channel_topic_codes"], len(mapping["topics"]))
        rows = _importance_rows(seed, "topic", mapping["topics"], topic_values, y_matched, topic_meta)
        rows = [row for row in rows if row["scope"] == "all"]
        topic_seed_rows.extend(rows)
        topic_seed = pd.DataFrame(rows)
        for mode in ("producer_only", "consumer_only", "bidirectional"):
            ranking, _ = propagate_topic_evidence(topic_seed, edges, mode)
            ranking["seed"] = seed
            ranking_seeds.append(ranking)

    topic_by_seed = pd.DataFrame(topic_seed_rows)
    topic_by_seed.to_csv(output / "topic_importance_by_seed.csv", index=False, encoding="utf-8-sig")
    topic_summary = _summarize_importance(topic_seed_rows)
    topic_summary.to_csv(output / "topic_importance.csv", index=False, encoding="utf-8-sig")
    ranking_by_seed = pd.concat(ranking_seeds, ignore_index=True)
    ranking_by_seed.to_csv(output / "module_rankings_by_seed.csv", index=False, encoding="utf-8-sig")
    ranking = _aggregate_module_seeds(ranking_by_seed)
    ranking.to_csv(output / "module_rankings.csv", index=False, encoding="utf-8-sig")
    sensitivity = pd.concat(
        [_degree_normalized(ranking[ranking["mode"].eq(mode)].copy(), edges, mode).assign(mode=mode)
         for mode in ("producer_only", "consumer_only", "bidirectional")],
        ignore_index=True,
    )
    sensitivity.to_csv(output / "degree_normalized_sensitivity.csv", index=False, encoding="utf-8-sig")

    total_test = int(len(test["binary"]))
    matched_test = int(np.isin(test["group"], np.fromiter(matching_groups, dtype=int)).sum())
    summary = {
        "status": "complete",
        "firmware_commit": MAJORITY_COMMIT,
        "matching_logs_in_corpus": int(len(matching_groups)),
        "fixed_test_windows": total_test,
        "matching_fixed_test_windows": matched_test,
        "matching_fixed_test_fraction": matched_test / total_test,
        "stage2_anomaly_test_windows": int(len(stage2_indices)),
        "matching_stage2_anomaly_test_windows": int(len(matched_indices)),
        "matching_stage2_anomaly_fraction": float(len(matched_indices) / len(stage2_indices)),
        "seeds": seeds,
        "top_producer_modules": ranking[ranking["mode"].eq("producer_only")].head(10).to_dict(orient="records"),
        "boundary": "All SHAP windows in this report originate from logs whose firmware commit matches the static PX4 graph.",
    }
    (output / "completion_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def recompute_document_mapping_consistency(root: Path, output: Path, seeds: list[int]) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=True)
    features = pd.read_csv(root / "reports/p2/feature_dictionary.csv")
    original = pd.read_csv(root / "reports/p3/channel_subsystem_mapping.csv")
    reference = build_document_mapping(features)
    reference.to_csv(output / "document_derived_channel_mapping.csv", index=False, encoding="utf-8-sig")
    comparison = original.merge(reference, on=["channel", "topic"], suffixes=("_original", "_document"))
    comparison["agreement"] = comparison["subsystem_original"].eq(comparison["subsystem_document"])
    comparison.to_csv(output / "mapping_comparison.csv", index=False, encoding="utf-8-sig")

    mapping = _mapping_codes(features, reference)
    test = _split(root / "data/processed/p2/features_original", "test")
    x, y, _ = stage2_subset(test["x"], test["binary"], test["type"])
    rows: list[dict[str, Any]] = []
    for seed in seeds:
        print(f"document-mapping consistency seed={seed}", flush=True)
        model = joblib.load(root / f"reports/p3/model_runs/seed{seed}/stage2_lightgbm.joblib")
        prediction, signed = _predict_contributions(model, np.asarray(x), 256)
        absolute = np.abs(signed)
        channel_values = aggregate_columns(absolute, mapping["feature_channel_codes"], len(mapping["channels"]))
        correct = prediction == y
        for k in (1, 3, 5, 10):
            scopes: list[tuple[str, np.ndarray | None]] = [("all", None), ("correct_predictions", correct)]
            scopes.extend((LABEL_NAMES[label], y == label) for label in SUBSYSTEM_LABELS)
            for scope, mask in scopes:
                observed = consistency_at_k(channel_values, y, mapping["channel_labels"], k, mask)
                truth = y if mask is None else y[mask]
                random = random_consistency_baseline(truth, mapping["channel_labels"], k)
                rows.append({"seed": seed, "scope": scope, "k": k, **observed,
                             "random_consistency": random["consistency"], "random_hit_rate": random["hit_rate"]})
    by_seed = pd.DataFrame(rows)
    by_seed.to_csv(output / "consistency_by_seed.csv", index=False, encoding="utf-8-sig")
    summary_frame = by_seed.groupby(["scope", "k"], as_index=False).agg(
        seeds=("seed", "nunique"), windows=("windows", "first"),
        consistency_mean=("consistency", "mean"), consistency_std=("consistency", "std"),
        hit_rate_mean=("hit_rate", "mean"), hit_rate_std=("hit_rate", "std"),
        random_consistency=("random_consistency", "first"), random_hit_rate=("random_hit_rate", "first"),
    )
    summary_frame.to_csv(output / "consistency_summary.csv", index=False, encoding="utf-8-sig")
    summary = {
        "status": "complete",
        "channels": int(len(comparison)),
        "mapping_agreement_channels": int(comparison["agreement"].sum()),
        "mapping_agreement_fraction": float(comparison["agreement"].mean()),
        "changed_channels": int((~comparison["agreement"]).sum()),
        "document_mapping_counts": reference["subsystem"].value_counts().to_dict(),
        "consistency_at_1": summary_frame[(summary_frame["scope"].eq("all")) & (summary_frame["k"].eq(1))].to_dict(orient="records"),
        "boundary": "The reference mapping is derived from PX4 message-field semantics and is independent of SHAP values; it is not a substitute for external human-expert adjudication.",
    }
    (output / "completion_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def _logical_statement(text: str, start: int, end: int) -> str:
    left = max(text.rfind(";", max(0, start - 600), start), text.rfind("{", max(0, start - 600), start),
               text.rfind("}", max(0, start - 600), start))
    right = text.find(";", end, min(len(text), end + 600))
    return text[left + 1:right + 1 if right >= 0 else min(len(text), end + 300)]


def audit_uorb_parser(root: Path, output: Path) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=True)
    source_root = root / "third_party/PX4-Autopilot"
    topics = set(pd.read_csv(root / "reports/p8/topic_mapping_coverage.csv")["topic"].astype(str))
    rows: list[dict[str, Any]] = []
    files: set[Path] = set()
    for pattern in ("src/**/*.cpp", "src/**/*.c", "src/**/*.hpp", "src/**/*.h"):
        files.update(source_root.glob(pattern))
    for path in sorted(files):
        text = path.read_text(encoding="utf-8", errors="ignore")
        for match in ORB_ID_PATTERN.finditer(text):
            topic = match.group(1)
            if topic not in topics:
                continue
            statement = _logical_statement(text, match.start(), match.end())
            has_publish = any(hint in statement for hint in PUBLISH_HINTS)
            has_subscribe = any(hint in statement for hint in SUBSCRIBE_HINTS)
            if has_publish == has_subscribe:
                continue
            reference_role = "publisher" if has_publish else "subscriber"
            current = _role_for_context(text, match.start(), match.end())
            current_role = next(iter(current)) if len(current) == 1 else "unclassified"
            rows.append({
                "topic": topic,
                "source_file": path.relative_to(source_root).as_posix(),
                "line": text.count("\n", 0, match.start()) + 1,
                "module": module_from_path(path.relative_to(source_root)),
                "reference_role": reference_role,
                "parser_role": current_role,
                "role_agreement": current_role == reference_role,
                "statement": re.sub(r"\s+", " ", statement).strip()[:500],
            })
    audit = pd.DataFrame(rows).drop_duplicates(["topic", "source_file", "line", "reference_role"])
    audit.to_csv(output / "explicit_declaration_audit.csv", index=False, encoding="utf-8-sig")
    current_edges = pd.read_csv(root / "reports/p8/topic_module_mapping.csv")
    explicit_edges = audit[["topic", "reference_role", "module"]].drop_duplicates().rename(columns={"reference_role": "role"})
    merged = explicit_edges.merge(current_edges[["topic", "role", "module"]].drop_duplicates(),
                                  on=["topic", "role", "module"], how="left", indicator=True)
    edge_recall = float(merged["_merge"].eq("both").mean()) if len(merged) else float("nan")
    summary = {
        "status": "complete",
        "audit_scope": "all unambiguous same-statement uORB declarations/calls for the 18 evaluated topics",
        "audited_occurrences": int(len(audit)),
        "topics_audited": int(audit["topic"].nunique()),
        "publisher_occurrences": int(audit["reference_role"].eq("publisher").sum()),
        "subscriber_occurrences": int(audit["reference_role"].eq("subscriber").sum()),
        "role_agreement": float(audit["role_agreement"].mean()) if len(audit) else float("nan"),
        "explicit_edge_recall": edge_recall,
        "boundary": "This source-grounded audit measures agreement and recall on explicit unambiguous declarations; it does not estimate recall for macro-generated or runtime-created relations.",
    }
    (output / "completion_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("task", choices=["commit-mapping", "semantic-mapping", "uorb-audit", "all"])
    parser.add_argument("--output", default="reports/p12")
    parser.add_argument("--seeds", nargs="*", type=int, default=[0, 1, 2, 3, 4])
    args = parser.parse_args()
    root = Path.cwd()
    output = root / args.output
    results: dict[str, Any] = {}
    if args.task in {"commit-mapping", "all"}:
        results["commit_mapping"] = recompute_commit_matched(root, output / "commit_matched", args.seeds)
    if args.task in {"semantic-mapping", "all"}:
        results["semantic_mapping"] = recompute_document_mapping_consistency(root, output / "semantic_mapping", args.seeds)
    if args.task in {"uorb-audit", "all"}:
        results["uorb_audit"] = audit_uorb_parser(root, output / "uorb_audit")
    print(json.dumps(results, indent=2), flush=True)


if __name__ == "__main__":
    main()
