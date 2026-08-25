import pandas as pd

from hs_aerots.submission_readiness import build_document_mapping, document_subsystem_for_channel


def test_document_mapping_avoids_generic_axis_token_leakage():
    assert document_subsystem_for_channel("vehicle_attitude.yawspeed", "vehicle_attitude")[0] == "Mechanical/Electrical"
    assert document_subsystem_for_channel("manual_control_setpoint.x", "manual_control_setpoint")[0] == "Shared"
    assert document_subsystem_for_channel("vehicle_local_position.epv", "vehicle_local_position")[0] == "Altitude"


def test_document_mapping_covers_all_feature_channels():
    features = pd.DataFrame({
        "channel": ["vehicle_vision_position.x", "vehicle_local_position.z", "battery_status.voltage_v"],
        "topic": ["vehicle_vision_position", "vehicle_local_position", "battery_status"],
    })
    mapping = build_document_mapping(features)
    assert mapping["subsystem"].tolist() == ["External Position", "Altitude", "Mechanical/Electrical"]
