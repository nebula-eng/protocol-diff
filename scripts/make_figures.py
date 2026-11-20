"""Figures for the differential-learning benchmark."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "results" / "results.json"

plt.rcParams.update(
    {
        "font.family": "DejaVu Sans",
        "font.size": 10,
        "axes.edgecolor": "#444444",
        "axes.linewidth": 0.8,
        "axes.grid": True,
        "grid.color": "#e8e8e8",
        "grid.linewidth": 0.6,
        "figure.facecolor": "white",
    }
)

NAMES = ["clearance_persist", "admin_persist", "auth_inverted", "close_ignored", "pub_leak_closed"]
SHORT = ["clearance", "admin", "auth\nbypass", "close\nignored", "public\nleak"]
SIZES = {"core": 6, "mid": 8, "full": 10}
LABEL = {"core": "core (6)", "mid": "mid (8)", "full": "full (10)"}


def main() -> None:
    payload = json.loads(DATA.read_text(encoding="utf-8"))
    blocks = payload["variants"]
    order = ["core", "mid", "full"]

    fig, axes = plt.subplots(1, 2, figsize=(16, 5), gridspec_kw={"width_ratios": [1, 1.5]})

    # Panel 1: cost and visibility as the alphabet grows.
    ax = axes[0]
    xs = np.arange(len(order))
    queries = [blocks[name]["reference_table_queries"] for name in order]
    detections = [blocks[name]["detections"] for name in order]
    bars = ax.bar(xs, queries, width=0.55, color="#2c7fb8")
    for bar, value, hits in zip(bars, queries, detections):
        ax.text(bar.get_x() + bar.get_width() / 2, value + 40, f"{value:,}",
                ha="center", fontsize=9, color="#1b4f72")
        ax.text(bar.get_x() + bar.get_width() / 2, value * 0.5, f"{int(hits)}/5\nfound",
                ha="center", va="center", fontsize=9, color="white", weight="bold")
    ax.set_xticks(xs)
    ax.set_xticklabels([LABEL[name].replace(" ", "\n") for name in order], fontsize=9)
    ax.set_ylabel("membership queries")
    ax.set_ylim(0, max(queries) * 1.24)
    ax.set_xlabel("alphabet")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.set_title("Cost and visibility as the alphabet grows", fontsize=12, loc="left", weight="bold")

    # Panel 2: per-defect detection matrix.
    ax = axes[1]
    matrix = np.zeros((len(order), len(NAMES)))
    for i, name in enumerate(order):
        for j, variant in enumerate(NAMES):
            matrix[i, j] = 1.0 if blocks[name]["rows"][variant]["verified"] else 0.0
    ax.imshow(matrix, cmap="RdYlGn", vmin=0, vmax=1, aspect="auto")
    ax.set_xticks(range(len(NAMES)))
    ax.set_xticklabels(SHORT, fontsize=8)
    ax.set_yticks(range(len(order)))
    ax.set_yticklabels([LABEL[name] for name in order], fontsize=9)
    for i in range(len(order)):
        for j in range(len(NAMES)):
            ax.text(j, i, "found" if matrix[i, j] else "missed", ha="center", va="center", fontsize=8)
    ax.set_title("Verified detections by alphabet", fontsize=12, loc="left", weight="bold")
    ax.grid(False)

    fig.suptitle(
        "Differential automata learning: each alphabet symbol buys visibility, not just cost",
        fontsize=13,
        weight="bold",
    )
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    fig.savefig(ROOT / "results" / "fig_detection.png", dpi=200)
    plt.close(fig)

    # Witness lengths at the full alphabet.
    full = blocks["full"]["rows"]
    fig, ax = plt.subplots(figsize=(10, 5))
    lengths = [full[n]["witness_length"] for n in NAMES]
    bars = ax.bar(np.arange(len(NAMES)), lengths, color="#2c7fb8", width=0.55)
    for bar, value in zip(bars, lengths):
        ax.text(bar.get_x() + bar.get_width() / 2, value + 0.08, str(value), ha="center", fontsize=9)
    ax.set_xticks(np.arange(len(NAMES)))
    ax.set_xticklabels(SHORT)
    ax.set_ylabel("witness length (symbols)")
    ax.set_ylim(0, max(lengths) + 1.2)
    ax.set_title("Shortest distinguishing sequence per defect (full alphabet)",
                 fontsize=12, loc="left", weight="bold")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout()
    fig.savefig(ROOT / "results" / "fig_witness.png", dpi=200)
    plt.close(fig)
    print("wrote fig_detection.png fig_witness.png")


if __name__ == "__main__":
    main()
