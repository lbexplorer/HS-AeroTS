import numpy as np
import pandas as pd

from hs_aerots.baseline import DESCRIPTORS
from hs_aerots.external_validation import selected_feature_indices, window_binary_labels


def test_selected_feature_indices_are_descriptor_major():
    rows = []
    index = 0
    for descriptor in DESCRIPTORS:
        for channel in ["a", "b", "c"]:
            rows.append({"feature_index": index, "descriptor": descriptor, "channel": channel})
            index += 1
    selected = selected_feature_indices(pd.DataFrame(rows), ["c", "a"])
    assert selected[:4].tolist() == [2, 0, 5, 3]
    assert len(selected) == len(DESCRIPTORS) * 2


def test_window_binary_labels_include_horizon():
    labels = np.zeros(12, dtype=np.int8)
    labels[7] = 1
    output, starts = window_binary_labels(labels, window_size=4, horizon=2, stride=2)
    assert starts.tolist() == [0, 2, 4, 6]
    assert output.tolist() == [0, 1, 1, 1]
