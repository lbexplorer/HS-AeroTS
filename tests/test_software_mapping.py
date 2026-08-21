from pathlib import Path

import pandas as pd

from hs_aerots.software_mapping import parse_uorb_source, propagate_topic_evidence


def test_parse_uorb_source_roles(tmp_path: Path):
    source = tmp_path / "src" / "modules" / "demo" / "demo.cpp"
    source.parent.mkdir(parents=True)
    source.write_text(
        "uORB::Publication<msg_s> pub{ORB_ID(vehicle_status)};\n"
        "uORB::Subscription sub{ORB_ID(sensor_combined)};\n",
        encoding="utf-8",
    )
    edges = parse_uorb_source(tmp_path, ["src/**/*.cpp"], {"vehicle_status", "sensor_combined"})
    assert set(map(tuple, edges[["topic", "role"]].to_numpy())) == {
        ("vehicle_status", "publisher"), ("sensor_combined", "subscriber")
    }
    assert set(edges["module"]) == {"src/modules/demo"}


def test_propagation_conserves_mapped_topic_mass():
    importance = pd.DataFrame([
        {"scope": "Altitude", "topic": "vehicle_status", "mean_abs_shap": 3.0},
    ])
    edges = pd.DataFrame([
        {"topic": "vehicle_status", "role": "publisher", "module": "src/modules/a", "source_file": "a.cpp"},
        {"topic": "vehicle_status", "role": "subscriber", "module": "src/modules/b", "source_file": "b.cpp"},
    ])
    ranking, checks = propagate_topic_evidence(importance, edges, "bidirectional")
    assert ranking["mean_abs_shap"].sum() == 3.0
    assert set(ranking["mean_abs_shap"]) == {1.5}
    assert checks.iloc[0]["conservation_error"] == 0.0

