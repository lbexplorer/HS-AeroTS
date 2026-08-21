import pandas as pd
import numpy as np

from hs_aerots.baseline import _interpolate, _ulog_time_bounds
from hs_aerots.sitl_injection import localization_metrics


def test_localization_metrics_single_fault_ranks():
    rankings = pd.DataFrame([
        {"run_id": "a", "ground_truth_module": "m2", "module": "m1", "rank": 1},
        {"run_id": "a", "ground_truth_module": "m2", "module": "m2", "rank": 2},
        {"run_id": "b", "ground_truth_module": "m1", "module": "m1", "rank": 1},
        {"run_id": "b", "ground_truth_module": "m1", "module": "m2", "rank": 2},
    ])
    metrics = localization_metrics(rankings)
    assert metrics["top1_recall"] == 0.5
    assert metrics["top3_recall"] == 1.0
    assert metrics["mrr"] == 0.75
    assert metrics["mean_exam"] == 0.75


def test_ulog_time_bounds_falls_back_from_unsigned_metadata_overflow():
    class Dataset:
        data = {"timestamp": np.array([84_000_000, 90_000_000, 115_000_000], dtype=np.uint64)}

    class Log:
        start_timestamp = 84_000_000
        last_timestamp = 18_446_744_073_709_551_000
        data_list = [Dataset()]

    assert _ulog_time_bounds(Log()) == (84_000_000, 115_000_000)


def test_ulog_time_bounds_preserves_valid_metadata():
    class Log:
        start_timestamp = 10_000_000
        last_timestamp = 20_000_000
        data_list = []

    assert _ulog_time_bounds(Log()) == (10_000_000, 20_000_000)


def test_interpolate_rejects_impossible_partial_record_payload():
    grid = np.array([0, 1, 2], dtype=np.int64)
    result = _interpolate(grid, np.array([0, 1, 2]), np.array([1.0, 1e300, 3.0]))
    np.testing.assert_allclose(result, [1.0, 2.0, 3.0])
