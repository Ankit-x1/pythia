"""Figures for the diagnostics, scenarios, standings translation and backtest.

Every figure carries a source/model context line so it can be lifted into the
report or slides without losing provenance.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from scipy import stats  # noqa: E402

from .paths import FIGURES  # noqa: E402

NAVY = "#0b1f3a"
GREEN = "#00936c"
SILVER = "#8b949e"
ACCENT = "#b8621b"
DAL_GREEN = "#006847"

plt.rcParams.update({
    "figure.dpi": 130,
    "savefig.dpi": 130,
    "font.size": 9.5,
    "axes.titlesize": 10.5,
    "axes.titleweight": "bold",
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.alpha": 0.25,
    "grid.linewidth": 0.6,
    "figure.facecolor": "white",
})


def _caption(fig: plt.Figure, text: str) -> None:
    fig.text(0.01, 0.005, text, fontsize=7.2, color=SILVER, ha="left", va="bottom")


def _save(fig: plt.Figure, name: str, caption: str) -> Path:
    _caption(fig, caption)
    path = FIGURES / name
    fig.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return path


# --------------------------------------------------------------------------- 1
def fig_goal_frequencies(log26: pd.DataFrame, rates: Any) -> Path:
    fig, axes = plt.subplots(1, 2, figsize=(10.2, 3.9))
    for ax, col, lam, title, colour in [
        (axes[0], "goals_for_reg", rates.lambda_gf, "Dallas regulation goals for", DAL_GREEN),
        (axes[1], "goals_against_reg", rates.lambda_ga, "Regulation goals against", ACCENT),
    ]:
        values = log26[col].to_numpy()
        kmax = int(values.max())
        ks = np.arange(0, kmax + 1)
        obs = np.array([(values == k).sum() for k in ks]) / len(values)
        exp = stats.poisson.pmf(ks, lam)
        width = 0.4
        ax.bar(ks - width / 2, obs, width=width, color=colour, label="Observed frequency")
        ax.bar(ks + width / 2, exp, width=width, color=SILVER, alpha=0.85,
               label=f"Poisson($\\lambda$={lam:.3f})")
        ax.set_xlabel("Goals in a game")
        ax.set_ylabel("Proportion of the 82 games")
        ax.set_title(title)
        ax.legend(frameon=False, fontsize=8)
    fig.suptitle("Observed goal frequencies vs fitted Poisson models — Dallas 2025-26", y=1.02)
    fig.tight_layout()
    return _save(fig, "fig1_goal_frequencies.png",
                 "Source: NHL gamecenter linescores (regulation goals only), 82 Dallas games. "
                 "Model: independent Poisson with lambda = mean regulation goals.")


# --------------------------------------------------------------------------- 2/3
def fig_point_distributions(results: dict[str, dict], subset: list[str], title: str,
                            name: str, caption: str) -> Path:
    fig, ax = plt.subplots(figsize=(8.4, 4.5))
    colours = plt.cm.viridis(np.linspace(0.05, 0.85, len(subset)))
    bins = np.arange(55, 145)
    for colour, sid in zip(colours, subset):
        pts = results[sid]["samples"]["points"]
        ax.hist(pts, bins=bins, density=True, histtype="step", linewidth=1.6,
                color=colour, label=f"{sid}  ({results[sid]['summary']['mean_points']:.1f} pts)")
    ax.set_xlabel("Simulated regular-season points")
    ax.set_ylabel("Density")
    ax.set_title(title)
    ax.legend(frameon=False, fontsize=8, ncol=2)
    fig.tight_layout()
    return _save(fig, name, caption)


# --------------------------------------------------------------------------- 4
def fig_sensitivity_curves(results: dict[str, dict], cfg: dict) -> Path:
    pcts = sorted([0.0] + list(cfg["sensitivity"]["percentages"]))
    fig, axes = plt.subplots(1, 2, figsize=(10.2, 4.0), sharey=True)
    for ax, prefix, colour, title in [
        (axes[0], "S1", DAL_GREEN, "S1: offense only (defense fixed)"),
        (axes[1], "S2", ACCENT, "S2: goals allowed only (offense fixed)"),
    ]:
        means, lo, hi = [], [], []
        for p in pcts:
            sid = "S0" if p == 0.0 else _pct_id(prefix, p)
            s = results[sid]["summary"]
            means.append(s["mean_points"])
            lo.append(s["interval_80"][0])
            hi.append(s["interval_80"][1])
        x = np.array(pcts) * 100
        ax.fill_between(x, lo, hi, color=colour, alpha=0.16, label="80% simulation interval")
        ax.plot(x, means, "o-", color=colour, linewidth=2, markersize=5, label="Mean points")
        ax.axvline(0, color=SILVER, linewidth=1, linestyle="--")
        ax.set_xlabel("Change in the rate (%)")
        ax.set_title(title)
        ax.legend(frameon=False, fontsize=8, loc="best")
    axes[0].set_ylabel("Standings points (82 games)")
    fig.suptitle("Offense and defense sensitivity of projected standings points", y=1.02)
    fig.tight_layout()
    return _save(fig, "fig4_sensitivity_curves.png",
                 "S0 baseline is 2025-26 regulation rates (lambda_GF, lambda_GA). Each point is "
                 "10,000 simulated seasons with common random numbers.")


def _pct_id(prefix: str, pct: float) -> str:
    return f"{prefix}_{pct:+.0%}".replace("+", "plus").replace("-", "minus")


# --------------------------------------------------------------------------- 5
def fig_personnel(results: dict[str, dict]) -> Path:
    ids = ["S0", "S3a", "S3b", "S3c", "S3d", "S4"]
    ids = [i for i in ids if i in results]
    fig, ax = plt.subplots(figsize=(9.2, 4.3))
    base = results["S0"]["summary"]["mean_points"]
    means = [results[i]["summary"]["mean_points"] for i in ids]
    colours = [SILVER if i == "S0" else (NAVY if i == "S4" else DAL_GREEN) for i in ids]
    y = np.arange(len(ids))[::-1]
    ax.barh(y, [m - base for m in means], left=base, color=colours, height=0.6)
    for yy, m, i in zip(y, means, ids):
        right = max(m, base) + 0.45
        ax.text(right, yy, f"{m:.1f} pts ({m - base:+.1f})", va="center", ha="left",
                fontsize=8.5, color=NAVY)
    ax.set_yticks(y)
    ax.set_yticklabels([f"{i}  {results[i]['name'][:44]}" for i in ids], fontsize=8.5)
    ax.axvline(base, color=SILVER, linestyle="--", linewidth=1)
    ax.set_xlabel("Mean simulated points (bars start at the S0 baseline)")
    ax.set_title("Personnel, availability, goaltending and combined scenarios vs baseline")
    ax.set_xlim(min(min(means), base) - 2.0, max(means) + 8.5)
    fig.tight_layout()
    return _save(fig, "fig5_personnel_comparison.png",
                 "Player inputs: NHL 2025-26 Dallas skater statistics and 2025-26 full-season "
                 "production for arrivals on the initial 2026-27 roster. Rate effects use the "
                 "documented per-team-game normalization.")


# --------------------------------------------------------------------------- 6
def fig_central(standings: pd.DataFrame, thresholds: list[dict], base_mean: float) -> Path:
    fig, ax = plt.subplots(figsize=(8.8, 4.4))
    seasons = sorted(standings["season"].unique())
    cmap = plt.cm.Blues(np.linspace(0.35, 0.9, len(seasons)))
    for colour, season in zip(cmap, seasons):
        grp = standings[standings["season"] == season].sort_values("division_rank")
        ax.plot(grp["division_rank"], grp["points"], "o-", color=colour, linewidth=1.5,
                markersize=5, label=season)
        dal = grp[grp["is_dallas"]]
        ax.scatter(dal["division_rank"], dal["points"], s=110, facecolors="none",
                   edgecolors=DAL_GREEN, linewidths=2, zorder=5)
    ax.axhline(base_mean, color=ACCENT, linestyle="--", linewidth=1.4,
               label=f"Baseline (S0) simulated mean: {base_mean:.1f} pts")
    for t in thresholds:
        ax.axhline(t["third_place_points"], color=SILVER, linewidth=0.7, linestyle=":", alpha=0.8)
    ax.set_xlabel("Central Division rank")
    ax.set_ylabel("Standings points (82-game season)")
    ax.set_xticks(range(1, 9))
    ax.set_title("Central Division points by rank, 2021-22 to 2025-26")
    ax.legend(frameon=False, fontsize=7.6, ncol=2, loc="lower left")
    fig.tight_layout()
    return _save(fig, "fig6_central_points_vs_rank.png",
                 "Source: NHL standings on each season's final regular-season date. Green rings "
                 "mark Dallas. Dotted lines are each season's third-place point total.")


# --------------------------------------------------------------------------- 7
def fig_backtest(backtest: dict) -> Path:
    pts = backtest["_samples"]["points"]
    actual = backtest["actual"]["points"]
    fig, ax = plt.subplots(figsize=(8.2, 4.1))
    ax.hist(pts, bins=np.arange(pts.min() - 0.5, pts.max() + 1.5), color=NAVY,
            alpha=0.75, density=True)
    for q, style in [(10, ":"), (90, ":"), (2.5, "-."), (97.5, "-.")]:
        ax.axvline(np.percentile(pts, q), color=SILVER, linestyle=style, linewidth=1)
    ax.axvline(actual, color=ACCENT, linewidth=2.2,
               label=f"Actual 2025-26: {actual} pts")
    ax.axvline(backtest["simulation"]["mean_points"], color=DAL_GREEN, linewidth=1.8,
               linestyle="--",
               label=f"Forecast mean: {backtest['simulation']['mean_points']:.1f} pts")
    ax.set_xlabel("Simulated 2025-26 points (model frozen on 2024-25 only)")
    ax.set_ylabel("Density")
    ax.set_title("Backtest: 2025-26 point distribution from a 2024-25-calibrated model")
    ax.legend(frameon=False, fontsize=8.5)
    fig.tight_layout()
    return _save(fig, "fig7_backtest.png",
                 "Training data: 2024-25 Dallas game log only. The 2025-26 result was opened "
                 "once, for evaluation. Dotted and dash-dot lines are the 80% and 95% bounds.")


# --------------------------------------------------------------------------- 8
def fig_data_overview(log26: pd.DataFrame, log25: pd.DataFrame) -> Path:
    fig, axes = plt.subplots(1, 2, figsize=(10.4, 3.9))
    ax = axes[0]
    for log, label, colour in [(log25, "2024-25", SILVER), (log26, "2025-26", DAL_GREEN)]:
        gf = log["goals_for_reg"].rolling(10).mean()
        ga = log["goals_against_reg"].rolling(10).mean()
        x = np.arange(1, len(log) + 1)
        ax.plot(x, gf, color=colour, linewidth=1.7, label=f"{label} GF (10-game avg)")
        ax.plot(x, ga, color=colour, linewidth=1.3, linestyle="--",
                label=f"{label} GA (10-game avg)")
    ax.set_xlabel("Dallas game number")
    ax.set_ylabel("Regulation goals per game")
    ax.set_title("Rolling 10-game regulation scoring")
    ax.legend(frameon=False, fontsize=7.4, ncol=2)

    ax = axes[1]
    counts = log26["finish"].value_counts().reindex(["REG", "OT", "SO"]).fillna(0)
    bars = ax.bar(counts.index, counts.values,
                  color=[NAVY, DAL_GREEN, ACCENT], width=0.55)
    for bar, v in zip(bars, counts.values):
        ax.text(bar.get_x() + bar.get_width() / 2, v + 0.6, f"{int(v)}",
                ha="center", fontsize=9)
    ax.set_ylabel("Games")
    ax.set_title("How 2025-26 games finished")
    ax.set_ylim(0, counts.max() * 1.18)
    fig.suptitle("Descriptive view of the 2025-26 Dallas regular season", y=1.02)
    fig.tight_layout()
    return _save(fig, "fig8_data_overview.png",
                 "Source: NHL gamecenter linescores, 82 regular-season games per season. "
                 "Finishing type comes from the game outcome period type (REG/OT/SO).")
