"""P8 firmware provenance, PX4 uORB architecture mapping, and SHAP propagation."""

from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

import pandas as pd
import yaml
from pyulog import ULog


ORB_ID_PATTERN = re.compile(r"ORB_ID\s*\(\s*([A-Za-z0-9_]+)\s*\)")
PUBLISH_HINTS = (
    "uORB::Publication", "uORB::PublicationMulti", "uORB::PublicationQueued",
    "orb_advertise", "orb_publish",
)
SUBSCRIBE_HINTS = (
    "uORB::Subscription", "uORB::SubscriptionData", "uORB::SubscriptionInterval",
    "uORB::SubscriptionCallback", "orb_subscribe",
)


def load_config(path: str | Path) -> dict[str, Any]:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def _resolve(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def _write_csv(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    rows = list(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def extract_firmware_inventory(dataset_inventory: Path, raw_root: Path, usable_status: str) -> pd.DataFrame:
    """Read only ULog headers and return one provenance row per usable P1 log."""
    inventory = pd.read_csv(dataset_inventory)
    inventory = inventory.loc[inventory["status"].eq(usable_status)].copy()
    rows: list[dict[str, Any]] = []
    for index, row in enumerate(inventory.itertuples(index=False), start=1):
        path = raw_root / str(row.relative_path)
        record: dict[str, Any] = {
            "log_key": str(row.log_key),
            "relative_path": str(row.relative_path),
            "firmware_commit": "",
            "hardware": "",
            "hardware_subtype": "",
            "system_name": "",
            "os_name": "",
            "parse_status": "ok",
            "parse_error": "",
        }
        try:
            info = ULog(str(path), parse_header_only=True).msg_info_dict
            record.update({
                "firmware_commit": str(info.get("ver_sw", "")),
                "hardware": str(info.get("ver_hw", "")),
                "hardware_subtype": str(info.get("ver_hw_subtype", "")),
                "system_name": str(info.get("sys_name", "")),
                "os_name": str(info.get("sys_os_name", "")),
            })
        except Exception as exc:  # preserve a complete, auditable inventory
            record["parse_status"] = "error"
            record["parse_error"] = f"{type(exc).__name__}: {exc}"
        rows.append(record)
        if index % 100 == 0:
            print(f"firmware headers: {index}/{len(inventory)}", flush=True)
    return pd.DataFrame(rows)


def source_commit(source_root: Path) -> str:
    try:
        return subprocess.run(
            ["git", "-C", str(source_root), "rev-parse", "HEAD"],
            check=True, capture_output=True, text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def module_from_path(relative_path: Path) -> str:
    parts = relative_path.parts
    if len(parts) >= 3 and parts[0] == "src" and parts[1] in {"modules", "drivers", "examples", "systemcmds"}:
        return "/".join(parts[:3])
    if len(parts) >= 3 and parts[0] == "src" and parts[1] == "lib":
        return "/".join(parts[:3])
    return "/".join(parts[:-1]) or "."


def _role_for_context(text: str, start: int, end: int) -> set[str]:
    # PX4 declarations sometimes span lines.  Associate an ORB_ID with the
    # closest preceding API/type hint, instead of allowing a neighbouring
    # declaration to leak its role into this occurrence.
    context = text[max(0, start - 500):end]
    publish_pos = max((context.rfind(hint) for hint in PUBLISH_HINTS), default=-1)
    subscribe_pos = max((context.rfind(hint) for hint in SUBSCRIBE_HINTS), default=-1)
    if publish_pos < 0 and subscribe_pos < 0:
        return set()
    return {"publisher"} if publish_pos > subscribe_pos else {"subscriber"}


def parse_uorb_source(source_root: Path, globs: list[str], topics: set[str] | None = None) -> pd.DataFrame:
    """Statically extract topic/role/module edges from a checked-out PX4 tree."""
    edges: set[tuple[str, str, str, str]] = set()
    files: set[Path] = set()
    for pattern in globs:
        files.update(source_root.glob(pattern))
    for path in sorted(files):
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        relative = path.relative_to(source_root)
        module = module_from_path(relative)
        for match in ORB_ID_PATTERN.finditer(text):
            topic = match.group(1)
            if topics is not None and topic not in topics:
                continue
            for role in _role_for_context(text, match.start(), match.end()):
                edges.add((topic, role, module, relative.as_posix()))
    return pd.DataFrame(sorted(edges), columns=["topic", "role", "module", "source_file"])


def propagate_topic_evidence(topic_importance: pd.DataFrame, edges: pd.DataFrame, mode: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Distribute each mapped topic's absolute SHAP mass uniformly over selected modules."""
    if mode not in {"producer_only", "consumer_only", "bidirectional"}:
        raise ValueError(f"unknown propagation mode: {mode}")
    rows: list[dict[str, Any]] = []
    checks: list[dict[str, Any]] = []
    for item in topic_importance.itertuples(index=False):
        candidates = edges.loc[edges["topic"].eq(str(item.topic))].copy()
        if mode == "producer_only":
            candidates = candidates.loc[candidates["role"].eq("publisher")]
        elif mode == "consumer_only":
            candidates = candidates.loc[candidates["role"].eq("subscriber")]
        modules = sorted(candidates["module"].unique())
        incoming = float(item.mean_abs_shap)
        if modules:
            share = incoming / len(modules)
            for module in modules:
                roles = ";".join(sorted(candidates.loc[candidates["module"].eq(module), "role"].unique()))
                rows.append({
                    "scope": item.scope, "mode": mode, "topic": item.topic,
                    "module": module, "roles": roles, "topic_mean_abs_shap": incoming,
                    "allocated_mean_abs_shap": share, "module_count_for_topic": len(modules),
                })
        outgoing = incoming if modules else 0.0
        checks.append({
            "scope": item.scope, "mode": mode, "topic": item.topic,
            "mapped": bool(modules), "module_count": len(modules),
            "input_mean_abs_shap": incoming, "allocated_mean_abs_shap": outgoing,
            "conservation_error": outgoing - incoming if modules else 0.0,
        })
    allocation = pd.DataFrame(rows)
    if allocation.empty:
        ranking = pd.DataFrame(columns=["scope", "mode", "module", "mean_abs_shap", "shap_share", "rank"])
    else:
        ranking = allocation.groupby(["scope", "mode", "module"], as_index=False)["allocated_mean_abs_shap"].sum()
        ranking = ranking.rename(columns={"allocated_mean_abs_shap": "mean_abs_shap"})
        ranking["shap_share"] = ranking["mean_abs_shap"] / ranking.groupby(["scope", "mode"])["mean_abs_shap"].transform("sum")
        ranking["rank"] = ranking.groupby(["scope", "mode"])["mean_abs_shap"].rank(method="dense", ascending=False).astype(int)
        ranking = ranking.sort_values(["scope", "mode", "rank", "module"]).reset_index(drop=True)
    return ranking, pd.DataFrame(checks)


def run_mapping(config: dict[str, Any], root: Path) -> dict[str, Any]:
    paths = config["paths"]
    report_dir = _resolve(root, paths["report_dir"])
    report_dir.mkdir(parents=True, exist_ok=True)
    firmware = extract_firmware_inventory(
        _resolve(root, paths["dataset_inventory"]), _resolve(root, paths["raw_root"]),
        str(config["firmware"]["usable_status"]),
    )
    firmware.to_csv(report_dir / "firmware_inventory.csv", index=False, encoding="utf-8-sig")
    commit_counts = Counter(x for x in firmware["firmware_commit"].astype(str) if x and x != "nan")
    source_root = _resolve(root, paths["px4_source_root"])
    checked_out_commit = source_commit(source_root)
    topic_importance = pd.read_csv(_resolve(root, paths["shap_topic_importance"]))
    topics = set(topic_importance["topic"].astype(str))
    edges = parse_uorb_source(source_root, list(config["mapping"]["source_globs"]), topics)
    edges.insert(0, "source_commit", checked_out_commit)
    edges.to_csv(report_dir / "topic_module_mapping.csv", index=False, encoding="utf-8-sig")

    coverage_rows = []
    for topic in sorted(topics):
        part = edges.loc[edges["topic"].eq(topic)]
        coverage_rows.append({
            "topic": topic, "has_publisher": bool(part["role"].eq("publisher").any()) if len(part) else False,
            "has_subscriber": bool(part["role"].eq("subscriber").any()) if len(part) else False,
            "publisher_modules": int(part.loc[part["role"].eq("publisher"), "module"].nunique()) if len(part) else 0,
            "subscriber_modules": int(part.loc[part["role"].eq("subscriber"), "module"].nunique()) if len(part) else 0,
            "mapped_modules": int(part["module"].nunique()) if len(part) else 0,
        })
    coverage = pd.DataFrame(coverage_rows)
    coverage.to_csv(report_dir / "topic_mapping_coverage.csv", index=False, encoding="utf-8-sig")

    rankings = []
    checks = []
    for mode in config["mapping"]["propagation_modes"]:
        ranking, check = propagate_topic_evidence(topic_importance, edges, str(mode))
        rankings.append(ranking)
        checks.append(check)
    ranking_frame = pd.concat(rankings, ignore_index=True)
    check_frame = pd.concat(checks, ignore_index=True)
    ranking_frame.to_csv(report_dir / "module_suspiciousness.csv", index=False, encoding="utf-8-sig")
    check_frame.to_csv(report_dir / "conservation_checks.csv", index=False, encoding="utf-8-sig")
    tolerance = float(config["mapping"]["conservation_tolerance"])
    conservation_ok = bool((check_frame.loc[check_frame["mapped"], "conservation_error"].abs() <= tolerance).all())
    if bool(config["mapping"].get("fail_on_conservation_error", True)) and not conservation_ok:
        raise RuntimeError("topic-to-module propagation failed contribution conservation")

    majority_commit, majority_count = commit_counts.most_common(1)[0] if commit_counts else ("", 0)
    summary = {
        "status": "complete",
        "usable_logs": int(len(firmware)),
        "firmware_parse_errors": int(firmware["parse_status"].ne("ok").sum()),
        "unique_firmware_commits": int(len(commit_counts)),
        "majority_firmware_commit": majority_commit,
        "majority_firmware_logs": int(majority_count),
        "source_commit": checked_out_commit,
        "source_matches_majority_firmware": bool(checked_out_commit and checked_out_commit == majority_commit),
        "shap_topics": int(len(topics)),
        "topics_with_any_mapping": int(coverage["mapped_modules"].gt(0).sum()),
        "topics_with_publishers": int(coverage["has_publisher"].sum()),
        "topics_with_subscribers": int(coverage["has_subscriber"].sum()),
        "mapping_edges": int(len(edges)),
        "mapped_modules": int(edges["module"].nunique()) if len(edges) else 0,
        "contribution_conservation_passed": conservation_ok,
        "boundary": "Static uORB dependencies rank runtime software-module suspects; only controlled SITL injections establish module-level ground truth.",
    }
    (report_dir / "completion_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (report_dir / "firmware_commit_counts.json").write_text(
        json.dumps(dict(commit_counts.most_common()), indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="configs/p8_software_mapping.yaml")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    result = run_mapping(load_config(args.config), Path.cwd())
    print(json.dumps(result, indent=2, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
