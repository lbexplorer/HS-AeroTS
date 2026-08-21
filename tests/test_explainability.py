import numpy as np

from hs_aerots.explainability import (
    aggregate_columns,
    consistency_at_k,
    mask_columns,
    random_consistency_baseline,
    reshape_multiclass_contributions,
)


def test_multiclass_contribution_reshape_preserves_additivity():
    shaped = np.arange(2 * 3 * 5, dtype=float).reshape(2, 3, 5)
    restored = reshape_multiclass_contributions(shaped.reshape(2, -1), 2, 3, 4)
    assert np.array_equal(restored, shaped)
    assert np.array_equal(restored.sum(axis=2), shaped.sum(axis=2))


def test_hierarchical_aggregation_conserves_absolute_mass():
    features = np.array([[1.0, 2.0, 3.0, 4.0], [4.0, 3.0, 2.0, 1.0]])
    channels = aggregate_columns(features, np.array([0, 0, 1, 2]), 3)
    topics = aggregate_columns(channels, np.array([0, 0, 1]), 2)
    subsystems = aggregate_columns(channels, np.array([0, 1, 1]), 2)
    assert np.allclose(features.sum(axis=1), channels.sum(axis=1))
    assert np.allclose(features.sum(axis=1), topics.sum(axis=1))
    assert np.allclose(features.sum(axis=1), subsystems.sum(axis=1))


def test_consistency_and_random_baseline_are_exact():
    importance = np.array([[9.0, 1.0, 0.0, 0.0], [0.0, 1.0, 8.0, 0.0]])
    truth = np.array([1, 2])
    mapping = np.array([1, 1, 2, 0])
    observed = consistency_at_k(importance, truth, mapping, 1)
    random = random_consistency_baseline(truth, mapping, 1)
    assert observed["consistency"] == 1.0
    assert observed["hit_rate"] == 1.0
    assert np.isclose(observed["weighted_consistency"], (1.0 + 8 / 9) / 2)
    assert random["consistency"] == (2 / 4 + 1 / 4) / 2
    assert random["hit_rate"] == random["consistency"]


def test_mask_columns_does_not_mutate_input():
    x = np.arange(12, dtype=np.float32).reshape(3, 4)
    replacement = np.array([-1.0, -2.0, -3.0, -4.0])
    masked = mask_columns(x, np.array([1, 3]), replacement)
    assert np.array_equal(x, np.arange(12, dtype=np.float32).reshape(3, 4))
    assert np.all(masked[:, 1] == -2.0)
    assert np.all(masked[:, 3] == -4.0)
