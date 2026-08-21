import numpy as np

from hs_aerots.unknown_validation import aggregate_flights


def test_aggregate_flights_uses_top_fraction():
    frame = aggregate_flights(np.array([0.1, 0.2, 0.9, 0.3, 0.4]), np.array([1, 1, 1, 2, 2]), 0.34)
    assert np.isclose(frame.loc[frame.group.eq(1), "top_fraction_mean"].iloc[0], 0.55)
    assert np.isclose(frame.loc[frame.group.eq(2), "top_fraction_mean"].iloc[0], 0.4)
