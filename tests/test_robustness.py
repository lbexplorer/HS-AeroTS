import numpy as np

from hs_aerots.robustness import grouped_bootstrap


def test_grouped_bootstrap_is_deterministic_and_group_based():
    groups = np.array([0, 0, 1, 1, 1])
    values = np.array([1.0, 1.0, 3.0, 3.0, 3.0])
    first = grouped_bootstrap(groups, lambda idx: float(values[idx].mean()), 50, 7, 0.95)
    second = grouped_bootstrap(groups, lambda idx: float(values[idx].mean()), 50, 7, 0.95)
    assert first == second
    assert first["bootstrap_unit_count"] == 2

