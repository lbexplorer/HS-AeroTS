import numpy as np

from hs_aerots.baseline import (
    DESCRIPTORS,
    _training_weights,
    descriptor_batch,
    event_f1,
    leave_log_out_assignments,
    split_counts,
    window_count,
)


def test_window_and_split_counts_match_short_log_behavior():
    assert window_count(108, 96, 12, 8) == 1
    assert window_count(107, 96, 12, 8) == 0
    assert split_counts(1, 0.7, 0.15) == (1, 0, 0)
    assert split_counts(100, 0.7, 0.15) == (70, 15, 15)


def test_descriptor_dimension_and_finiteness():
    rng = np.random.default_rng(7)
    x = rng.normal(size=(3, 96, 5)).astype(np.float32)
    x[:, :, 0] = 1.0
    features = descriptor_batch(x)
    assert features.shape == (3, len(DESCRIPTORS) * 5)
    assert np.isfinite(features).all()


def test_training_weights_match_explicit_windows():
    x = np.arange(30, dtype=np.float64)[:, None]
    starts = np.array([0, 4, 8])
    weights = _training_weights(len(x), starts, 8)
    weighted = (x[:, 0] * weights).sum()
    explicit = sum(x[start : start + 8, 0].sum() for start in starts)
    assert weighted == explicit
    assert weights.sum() == len(starts) * 8


def test_log_aware_event_metric_does_not_merge_boundaries():
    labels = np.array([0, 1, 1, 1])
    scores = np.array([0.1, 0.9, 0.9, 0.9])
    groups = np.array([0, 0, 1, 1])
    metrics = event_f1(labels, scores, 0.5, groups)
    assert metrics["event_precision"] == 1.0
    assert metrics["event_recall"] == 1.0


def test_leave_log_out_assignments_are_deterministic_and_keep_logs_intact():
    records = [
        {"log_key": f"normal-{index}", "entry": {"annotations": []}}
        for index in range(10)
    ] + [
        {"log_key": f"altitude-{index}", "entry": {"annotations": [{"class": "Altitude"}]}}
        for index in range(10)
    ]
    first = leave_log_out_assignments(records, 0.7, 0.15, 42)
    second = leave_log_out_assignments(records, 0.7, 0.15, 42)
    assert first == second
    assert set(first) == {record["log_key"] for record in records}
    assert set(first.values()) == {"train", "validation", "test"}
