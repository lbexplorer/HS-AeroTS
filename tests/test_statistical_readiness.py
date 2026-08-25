import numpy as np

from hs_aerots.statistical_readiness import _confusions_by_group, _macro_f1_from_confusions


def test_group_confusions_reproduce_perfect_macro_f1():
    truth = np.array([0, 1, 0, 1])
    pred = truth.copy()
    groups = np.array([10, 10, 20, 20])
    order, matrices = _confusions_by_group(truth, pred, groups, [0, 1])
    assert order.tolist() == [10, 20]
    assert _macro_f1_from_confusions(matrices.sum(axis=0)) == 1.0


def test_macro_f1_handles_missing_predictions():
    confusion = np.array([[2, 0], [2, 0]])
    value = _macro_f1_from_confusions(confusion)
    assert np.isclose(value, 1 / 3)
