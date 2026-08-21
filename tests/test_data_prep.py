from __future__ import annotations

from hs_aerots.data_prep import annotation_intervals, relative_ulog_path


def test_relative_ulog_path_preserves_hierarchy() -> None:
    assert relative_ulog_path("2018-05-24/19_06_07") == "ulg_files/2018-05-24/19_06_07.ulg"


def test_annotation_intervals_flattens_and_orders_bounds() -> None:
    entry = {
        "annotations": [
            {
                "class": "Altitude",
                "ranges": [["Position.Z", [[20, 10], [30, 40]]]],
            }
        ]
    }
    assert annotation_intervals(entry) == [
        {"class": "Altitude", "signal": "Position.Z", "start_us": 10, "end_us": 20},
        {"class": "Altitude", "signal": "Position.Z", "start_us": 30, "end_us": 40},
    ]


def test_annotation_intervals_ignores_malformed_ranges() -> None:
    entry = {"annotations": [{"class": "Mechanical", "ranges": [None, ["x"], ["x", [1]]]}]}
    assert annotation_intervals(entry) == []

