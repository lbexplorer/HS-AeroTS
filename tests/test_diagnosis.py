import numpy as np

from hs_aerots.diagnosis import (
    SUBSYSTEM_LABELS,
    classification_metrics,
    hierarchical_labels,
    stage2_subset,
    subsystem_for_channel,
)


def test_hierarchical_labels_and_stage2_subset():
    x = np.arange(20, dtype=np.float32).reshape(5, 4)
    binary = np.array([0, 1, 1, 0, 1])
    types = np.array([0, 1, 4, 0, 3])
    labels = hierarchical_labels(binary, types)
    assert labels.tolist() == [0, 1, 4, 0, 3]
    sx, sy, indices = stage2_subset(x, binary, types)
    assert sx.shape == (3, 4)
    assert sy.tolist() == [1, 4, 3]
    assert indices.tolist() == [1, 2, 4]


def test_missing_subsystem_label_is_rejected():
    with np.testing.assert_raises(ValueError):
        hierarchical_labels(np.array([1]), np.array([0]))


def test_classification_metrics_perfect_predictions():
    truth = np.array([1, 2, 3, 4, 1, 2])
    metrics, rows, matrix = classification_metrics(truth, truth, SUBSYSTEM_LABELS)
    assert metrics["macro_f1"] == 1.0
    assert metrics["balanced_accuracy"] == 1.0
    assert len(rows) == 4
    assert np.trace(matrix) == len(truth)


def test_channel_mapping_has_expected_semantics():
    assert subsystem_for_channel("vehicle_vision_position.x")[0] == "External Position"
    assert subsystem_for_channel("distance_sensor.current_distance")[0] == "Altitude"
    assert subsystem_for_channel("vehicle_local_position.x")[0] == "Global Position"
    assert subsystem_for_channel("battery_status.voltage_v")[0] == "Mechanical/Electrical"
