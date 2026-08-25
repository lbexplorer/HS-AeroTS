import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
REPORTS = ROOT / "reports"
OUT = Path(__file__).resolve().parent


def load_protocol_values():
    fixed_p2 = json.loads((REPORTS / "p2" / "completion_summary.json").read_text())
    fixed_p3 = json.loads((REPORTS / "p3" / "completion_summary.json").read_text())
    fixed_p3_methods = pd.read_csv(REPORTS / "p3" / "method_summary.csv").set_index("method")
    purged = json.loads((REPORTS / "p10" / "completion_summary.json").read_text())
    fixed_direct = pd.read_csv(REPORTS / "p10" / "direct_five_seeds" / "method_summary.csv").set_index("method")
    llo = json.loads((REPORTS / "p11" / "llo" / "p3" / "completion_summary.json").read_text())
    return {
        "protocol": ["Fixed chronological", "Purged", "Leave-log-out"],
        "stage1_auprc": [
            fixed_p2["lightgbm_five_seed"]["auprc_mean"],
            purged["purged_stage1_auprc"],
            llo["stage1_lightgbm"]["test_auprc"]["mean"],
        ],
        "stage2_macro_f1": [
            fixed_p3["stage2_lightgbm"]["macro_f1_mean"],
            purged["purged_stage2_macro_f1"],
            llo["methods"][0]["macro_f1_mean"],
        ],
        "cascade_macro_f1": [
            fixed_p3_methods.loc["hs_aerots_cascade", "macro_f1_mean"],
            purged["purged_cascade_macro_f1"],
            next(item["macro_f1_mean"] for item in llo["methods"] if item["method"] == "hs_aerots_cascade"),
        ],
        "direct_macro_f1": [
            fixed_direct.loc["direct_five_class_lightgbm", "macro_f1_mean"],
            purged["purged_direct_five_macro_f1"],
            next(item["macro_f1_mean"] for item in llo["methods"] if item["method"] == "direct_five_class_lightgbm"),
        ],
    }


def main():
    protocol = load_protocol_values()
    replay = json.loads((REPORTS / "p9" / "localization_metrics.json").read_text())

    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 8.5,
            "axes.titlesize": 9.5,
            "axes.labelsize": 8.5,
            "xtick.labelsize": 8,
            "ytick.labelsize": 8,
            "legend.fontsize": 7.5,
            "figure.dpi": 150,
            "savefig.dpi": 300,
        }
    )
    colors = {
        "stage1": "#0072B2",
        "stage2": "#009E73",
        "cascade": "#D55E00",
        "direct": "#CC79A7",
        "onset": "#0072B2",
        "gated": "#6B7280",
    }

    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.45), constrained_layout=True)
    ax = axes[0]
    x = np.arange(3)
    ax.bar(x, protocol["stage1_auprc"], color=colors["stage1"], width=0.56)
    ax.set_title("(a) Stage 1 AUPRC")
    ax.set_ylabel("AUPRC")
    ax.set_xticks(x, ["Fixed\nchrono.", "Purged", "Leave-log-\nout"])
    ax.set_ylim(0, 0.85)
    for idx, value in enumerate(protocol["stage1_auprc"]):
        ax.text(idx, value + 0.025, f"{value:.3f}", ha="center", fontsize=7.5)

    ax = axes[1]
    width = 0.19
    for offset, key, label, color in [
        (-1.5, "stage2_macro_f1", "Stage 2", colors["stage2"]),
        (-0.5, "cascade_macro_f1", "Cascade", colors["cascade"]),
        (0.5, "direct_macro_f1", "Direct Five-Class", colors["direct"]),
    ]:
        values = protocol[key]
        ax.bar(x + offset * width, values, width=width, label=label, color=color)
    ax.set_title("(b) Diagnostic Macro-F1")
    ax.set_ylabel("Macro-F1")
    ax.set_xticks(x, ["Fixed\nchrono.", "Purged", "Leave-log-\nout"])
    ax.set_ylim(0, 1.0)
    ax.legend(
        frameon=False,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.19),
        ncol=3,
        columnspacing=1.0,
        handletextpad=0.4,
    )

    for axis in axes:
        axis.spines["top"].set_visible(False)
        axis.spines["right"].set_visible(False)
        axis.grid(axis="y", color="#D1D5DB", linewidth=0.5, alpha=0.55)
        axis.set_axisbelow(True)
    fig.savefig(OUT / "figure_3_protocol_robustness.pdf", bbox_inches="tight")
    fig.savefig(OUT / "figure_3_protocol_robustness.png", bbox_inches="tight")
    plt.close(fig)

    labels = ["Top-1", "Top-3", "Top-5", "MRR"]
    onset = [replay["top1_recall"], replay["top3_recall"], replay["top5_recall"], replay["mrr"]]
    gated = [
        replay["detector_gated_top1_recall"],
        replay["detector_gated_top3_recall"],
        replay["detector_gated_top5_recall"],
        replay["detector_gated_mrr"],
    ]
    fig, ax = plt.subplots(figsize=(6.2, 3.8), constrained_layout=True)
    x = np.arange(len(labels))
    width = 0.34
    ax.bar(x - width / 2, onset, width, color=colors["onset"], label="Onset-conditioned")
    ax.bar(x + width / 2, gated, width, color=colors["gated"], label="Detector-gated")
    ax.set_title("Onset-conditioned versus detector-gated replay ranking")
    ax.set_ylabel("Recall / MRR")
    ax.set_xticks(x, labels)
    ax.set_ylim(0, 0.4)
    ax.text(0.5, 0.355, "Detector recall: 0/12 mutation runs", ha="center", fontsize=8.5)
    ax.legend(frameon=False, loc="upper right")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis="y", color="#D1D5DB", linewidth=0.5, alpha=0.55)
    ax.set_axisbelow(True)
    fig.savefig(OUT / "figure_5_replay_onset_vs_detector_gated.pdf", bbox_inches="tight")
    fig.savefig(OUT / "figure_5_replay_onset_vs_detector_gated.png", bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    main()
