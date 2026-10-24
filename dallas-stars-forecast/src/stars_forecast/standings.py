"""Historical Central Division translation.

This module converts a simulated Dallas point total into *historical point-level*
comparisons. It does not simulate other teams and it does not claim a 2026-27
division rank. Two statistics are produced:

1. Historical top-three point-level probability
   P(points >= third-place points in season s), averaged over the five seasons.
   Equality rule: a total equal to the threshold counts as meeting it
   ("at least", >=), which is stated wherever the number is reported.

2. Historical division-rank range
   Historical Dallas rows are removed from the competitor table (they are the team
   being replaced), and the simulated total is ranked against the remaining
   Central teams season by season. Because historical ties cannot be broken
   without inventing a tiebreaker, each simulated total yields a rank *interval*
   [best, worst] where best counts only competitors strictly above and worst
   counts competitors above or equal. The interval is averaged over seasons.
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def season_thresholds(standings: pd.DataFrame, top_rank: int = 3) -> list[dict[str, Any]]:
    rows = []
    for season, grp in standings.groupby("season", sort=True):
        grp = grp.sort_values("division_rank")
        third = grp[grp["division_rank"] == top_rank]
        first = grp[grp["division_rank"] == 1]
        rows.append({
            "season": season,
            "first_place_points": int(first["points"].iloc[0]),
            "third_place_points": int(third["points"].iloc[0]),
            "third_place_team": str(third["team"].iloc[0]),
            "mean_central_points": round(float(grp["points"].mean()), 2),
            "dallas_points": int(grp.loc[grp["is_dallas"], "points"].iloc[0]),
            "dallas_rank": int(grp.loc[grp["is_dallas"], "division_rank"].iloc[0]),
        })
    return rows


def translate(points: np.ndarray, standings: pd.DataFrame, top_rank: int = 3) -> dict[str, Any]:
    """Point-level historical comparison for one simulated point sample."""
    pts = np.asarray(points, dtype=float)
    thresholds = season_thresholds(standings, top_rank)
    per_season = []
    rank_best, rank_worst, top3_lo, top3_hi, top3_eq = [], [], [], [], []
    for t in thresholds:
        thr = t["third_place_points"]
        p_meet = float((pts >= thr).mean())
        p_equal = float((pts == thr).mean())
        # Competitors: historical Central rows excluding Dallas (Dallas is replaced).
        season_rows = standings[standings["season"] == t["season"]]
        rivals = season_rows[~season_rows["is_dallas"]]["points"].to_numpy(dtype=float)
        # Rivals strictly above the simulated total -> best possible rank.
        # Rivals at or above -> worst possible rank when ties cannot be broken.
        strictly_above = (rivals[None, :] > pts[:, None]).sum(axis=1)
        at_or_above = (rivals[None, :] >= pts[:, None]).sum(axis=1)
        best = strictly_above + 1
        worst = at_or_above + 1
        per_season.append({
            "season": t["season"],
            "third_place_points": thr,
            "third_place_team": t["third_place_team"],
            "prob_points_at_least_third_place": round(p_meet, 4),
            "prob_points_exactly_third_place": round(p_equal, 4),
            "mean_best_rank": round(float(best.mean()), 3),
            "mean_worst_rank": round(float(worst.mean()), 3),
            "prob_rank_best_at_most_3": round(float((best <= 3).mean()), 4),
            "prob_rank_worst_at_most_3": round(float((worst <= 3).mean()), 4),
        })
        rank_best.append(best)
        rank_worst.append(worst)
        top3_lo.append(float((worst <= 3).mean()))
        top3_hi.append(float((best <= 3).mean()))
        top3_eq.append(p_meet)

    all_best = np.concatenate(rank_best)
    all_worst = np.concatenate(rank_worst)
    return {
        "statistic": "historical top-three Central point-level probability",
        "definition": ("average over the five historical Central seasons of "
                       "P(simulated Dallas points >= that season's third-place point total); "
                       ">= means the threshold is met when points equal it"),
        "prob_meets_third_place_points": round(float(np.mean(top3_eq)), 4),
        "prob_top3_rank_range": [round(float(np.mean(top3_lo)), 4),
                                 round(float(np.mean(top3_hi)), 4)],
        "mean_division_rank_range": [round(float(all_best.mean()), 2),
                                     round(float(all_worst.mean()), 2)],
        "rank_p10_p90_best_case": [int(np.percentile(all_best, 10)),
                                   int(np.percentile(all_best, 90))],
        "prob_rank_1": round(float((all_best <= 1).mean()), 4),
        "prob_rank_worst_at_most_4": round(float((all_worst <= 4).mean()), 4),
        "per_season": per_season,
        "caveats": [
            "Historical Dallas rows are excluded from the competitors.",
            "Ties are reported as a rank interval, not resolved with an invented tiebreaker.",
            "This is not a playoff-qualification probability and not an exact 2026-27 rank.",
            "Five Central seasons are a small sample of competitor behaviour.",
        ],
    }


def points_rank_table(standings: pd.DataFrame) -> pd.DataFrame:
    """Tidy points-vs-rank table used by the figure and the report."""
    return standings.sort_values(["season", "division_rank"])[
        ["season", "team", "points", "point_pct", "gp", "division_rank", "made_playoffs",
         "is_dallas"]
    ].reset_index(drop=True)
