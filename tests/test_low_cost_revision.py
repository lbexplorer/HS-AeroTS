import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, f1_score
from pathlib import Path

from hs_aerots.low_cost_revision import (
    _bootstrap_weights,
    _group_codes,
    _macro_f1_bootstrap,
    _weighted_average_precision_sorted,
    conservative_exclusion_reason,
)


ROOT = Path(__file__).resolve().parents[1]


def test_conservative_filter_rules_cover_incompatible_paths():
    assert conservative_exclusion_reason("src/examples/hwtest/hwtest.c") == "examples"
    assert conservative_exclusion_reason("src/platforms/posix/drivers/df_bebop.cpp") == "posix_platform"
    assert conservative_exclusion_reason("src/platforms/qurt/tests/muorb.cpp") == "tests"
    assert conservative_exclusion_reason("src/modules/ekf2/EKF2.cpp") is None


def test_weighted_average_precision_matches_unweighted_point_without_ties():
    labels = np.array([0, 1, 0, 1, 1])
    scores = np.array([0.1, 0.9, 0.2, 0.8, 0.7])
    groups, codes = _group_codes(np.array([10, 10, 20, 20, 30]))
    weights = np.ones((1, len(groups)), dtype=np.int16)
    observed = _weighted_average_precision_sorted(labels, scores, codes, weights)[0]
    assert np.isclose(observed, average_precision_score(labels, scores))


def test_macro_f1_bootstrap_matches_unweighted_point():
    labels = np.array([0, 1, 2, 0, 1, 2])
    predictions = np.array([0, 1, 1, 0, 2, 2])
    groups, codes = _group_codes(np.array([10, 10, 20, 20, 30, 30]))
    weights = np.ones((1, len(groups)), dtype=np.int16)
    observed = _macro_f1_bootstrap(labels, predictions, codes, weights, [0, 1, 2])[0]
    expected = f1_score(labels, predictions, labels=[0, 1, 2], average="macro", zero_division=0)
    assert np.isclose(observed, expected)


def test_bootstrap_weights_are_reproducible_and_preserve_cluster_count():
    first = _bootstrap_weights(7, 25, 20260825)
    second = _bootstrap_weights(7, 25, 20260825)
    assert np.array_equal(first, second)
    assert np.all(first.sum(axis=1) == 7)


def test_p13_stage1_counts_partition_every_test_window():
    frame = pd.read_csv(ROOT / "reports/p13/stage1_gated/stage1_gate_counts_by_seed.csv")
    for row in frame.itertuples(index=False):
        assert row.tp + row.fn + row.fp + row.tn == row.windows


def test_p13_matching_commit_subset_matches_firmware_inventory():
    counts = pd.read_csv(ROOT / "reports/p13/stage1_gated/stage1_gate_counts_by_seed.csv")
    expected = int(counts.loc[(counts.seed == 0) & (counts.scope == "matching_commit"), "windows"].iloc[0])
    cascade = pd.read_csv(ROOT / "reports/p3/predictions/cascade_seed0.csv")
    groups = pd.read_csv(ROOT / "reports/p2/group_dictionary.csv")[["group", "log_key"]]
    firmware = pd.read_csv(ROOT / "reports/p8/firmware_inventory.csv")[["log_key", "firmware_commit"]]
    matched_groups = set(
        groups.merge(firmware, on="log_key", validate="one_to_one")
        .loc[lambda x: x.firmware_commit.eq("82aa24adfca29321cfd1209e287eab6c2b16780e"), "group"]
    )
    selected = cascade.loc[cascade.group.isin(matched_groups)]
    assert len(selected) == expected
    assert set(selected.group).issubset(matched_groups)


def test_p13_filtered_edges_are_strict_subset_and_conserve_evidence():
    original = pd.read_csv(ROOT / "reports/p8/topic_module_mapping.csv")
    filtered = pd.read_csv(ROOT / "reports/p13/conservative_graph/filtered_topic_module_mapping.csv")
    keys = ["source_commit", "topic", "role", "module", "source_file"]
    original_rows = set(map(tuple, original[keys].itertuples(index=False, name=None)))
    filtered_rows = set(map(tuple, filtered[keys].itertuples(index=False, name=None)))
    assert filtered_rows < original_rows
    checks = pd.read_csv(ROOT / "reports/p13/conservative_graph/conservation_checks.csv")
    assert (checks.loc[checks.mapped, "conservation_error"].abs() <= 1e-10).all()


def test_p13_ci_point_means_match_per_seed_records():
    summary = pd.read_csv(ROOT / "reports/p13/absolute_uncertainty/absolute_metric_cluster_ci.csv")
    points = pd.read_csv(ROOT / "reports/p13/absolute_uncertainty/absolute_metric_points_by_seed.csv")
    observed = points.groupby(["protocol", "task", "metric"], as_index=False).point.mean()
    merged = summary.merge(observed, on=["protocol", "task", "metric"], validate="one_to_one")
    assert np.allclose(merged.point_mean, merged.point)
