from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
REPORTS = ROOT / "reports"
OUT = Path(__file__).resolve().parent


def short_module(name):
    return name.replace("src/modules/", "").replace("src/", "")


def main():
    masking = pd.read_csv(REPORTS / "p4" / "masking_results.csv")
    consistency = pd.read_csv(REPORTS / "p4" / "consistency_at_k.csv")
    modules = pd.read_csv(REPORTS / "p8" / "module_suspiciousness.csv")

    shap_mask = masking[masking["mask"] == "validation_shap_top_k"].sort_values("k")
    random_mask = masking[masking["mask"] == "uniform_random_k"].sort_values("k")
    all_consistency = consistency[consistency["scope"] == "all"].sort_values("k")
    class_consistency = consistency[
        (consistency["scope"].isin([
            "External Position",
            "Global Position",
            "Altitude",
            "Mechanical/Electrical",
        ]))
        & (consistency["k"] == 1)
    ].copy()
    class_order = [
        "External Position",
        "Global Position",
        "Altitude",
        "Mechanical/Electrical",
    ]
    class_consistency["scope"] = pd.Categorical(
        class_consistency["scope"], categories=class_order, ordered=True
    )
    class_consistency = class_consistency.sort_values("scope")
    top_modules = modules[
        (modules["scope"] == "all") & (modules["mode"] == "producer_only")
    ].sort_values("rank").head(5).copy()
    top_modules["label"] = top_modules["module"].map(short_module)
    top_modules = top_modules.sort_values("shap_share")

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
        "shap": "#0072B2",
        "random": "#D55E00",
        "consistency": "#009E73",
        "baseline": "#6B7280",
        "class": "#CC79A7",
        "module": "#E69F00",
    }

    fig, axes = plt.subplots(2, 2, figsize=(7.2, 5.7), constrained_layout=True)
    ax = axes[0, 0]
    x = np.arange(len(shap_mask))
    width = 0.36
    ax.bar(
        x - width / 2,
        shap_mask["macro_f1_drop_mean"],
        width,
        yerr=shap_mask["macro_f1_drop_std"],
        label="SHAP top-k",
        color=colors["shap"],
        capsize=2,
    )
    ax.bar(
        x + width / 2,
        random_mask["macro_f1_drop_mean"],
        width,
        yerr=random_mask["macro_f1_drop_std"],
        label="Random",
        color=colors["random"],
        capsize=2,
    )
    ax.set_title("(a) Masking effect")
    ax.set_xlabel("Masked features (k)")
    ax.set_ylabel("Macro-F1 decrease")
    ax.set_xticks(x, shap_mask["k"].astype(str))
    ax.set_ylim(bottom=0)
    ax.legend(frameon=False, loc="upper left")

    ax = axes[0, 1]
    ax.errorbar(
        all_consistency["k"],
        all_consistency["consistency_mean"],
        yerr=all_consistency["consistency_std"],
        marker="o",
        linewidth=1.7,
        color=colors["consistency"],
        capsize=2,
        label="SHAP consistency",
    )
    ax.plot(
        all_consistency["k"],
        all_consistency["random_consistency"],
        marker="s",
        linestyle="--",
        linewidth=1.3,
        color=colors["baseline"],
        label="Random baseline",
    )
    ax.set_title("(b) Overall Consistency@K")
    ax.set_xlabel("K channels")
    ax.set_ylabel("Consistency")
    ax.set_xticks(all_consistency["k"])
    ax.set_ylim(0, 0.5)
    ax.legend(frameon=False, loc="upper right")

    ax = axes[1, 0]
    xpos = np.arange(len(class_consistency))
    ax.errorbar(
        xpos,
        class_consistency["consistency_mean"],
        yerr=class_consistency["consistency_std"],
        fmt="o",
        color=colors["class"],
        capsize=3,
        markersize=5,
        label="SHAP",
    )
    ax.scatter(
        xpos,
        class_consistency["random_consistency"],
        marker="_",
        s=220,
        linewidths=2,
        color=colors["baseline"],
        label="Random baseline",
    )
    ax.set_title("(c) Class Consistency@1")
    ax.set_ylabel("Consistency")
    ax.set_xticks(xpos, ["External\nPosition", "Global\nPosition", "Altitude", "Mechanical/\nElectrical"])
    ax.set_ylim(0, 1.0)
    ax.legend(frameon=False, loc="upper left")

    ax = axes[1, 1]
    ax.barh(top_modules["label"], top_modules["shap_share"], color=colors["module"])
    ax.set_title("(d) Aggregate module suspects")
    ax.set_xlabel("Allocated SHAP share")
    ax.set_xlim(0, 0.28)
    for y, value in enumerate(top_modules["shap_share"]):
        ax.text(value + 0.004, y, f"{value:.3f}", va="center", fontsize=7.5)

    for axis in axes.flat:
        axis.spines["top"].set_visible(False)
        axis.spines["right"].set_visible(False)
        axis.grid(axis="y", color="#D1D5DB", linewidth=0.5, alpha=0.55)
        axis.set_axisbelow(True)

    fig.savefig(OUT / "figure_4_shap_evidence_module_ranking.pdf", bbox_inches="tight")
    fig.savefig(OUT / "figure_4_shap_evidence_module_ranking.png", bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    main()
