"""Isolated backtest: calibrate on 2024-25, predict 2025-26, evaluate once.

Rules enforced here:
  * the model and its configuration are frozen before the target season is read;
  * the 2025-26 actual outcome is used for evaluation only;
  * nothing is tuned to make the target look accurate.
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from .model import Rates, ScenarioSpec, fit_rates, simulate_seasons, summarize


def run_backtest(train_log: pd.DataFrame, target_log: pd.DataFrame,
                 target_totals: pd.Series, n_seasons: int, seed: int,
                 thresholds: list[int]) -> dict[str, Any]:
    # ---- freeze: everything below is fitted on 2024-25 only -------------------
    train_rates: Rates = fit_rates(train_log)
    spec = ScenarioSpec(
        scenario_id="BT", name="Backtest (2024-25 calibration)", family="backtest",
        lambda_gf=train_rates.lambda_gf, lambda_ga=train_rates.lambda_ga,
        details={"frozen_from": train_rates.season,
                 "lambda_gf": round(train_rates.lambda_gf, 5),
                 "lambda_ga": round(train_rates.lambda_ga, 5),
                 "p_win_if_tied": train_rates.p_win_if_tied,
                 "n_tied_training_games": train_rates.n_tied},
    )
    samples = simulate_seasons(spec, train_rates, n_seasons=n_seasons, seed=seed)
    summary = summarize(samples, thresholds)

    # ---- evaluate: read the held-out season now -------------------------------
    pts = samples["points"].astype(float)
    actual_points = int(target_totals["points"])
    actual_wins = int(target_totals["wins"])
    actual_reg_losses = int(target_totals["losses"])
    actual_otl = int(target_totals["ot_losses"])
    inside80 = bool(np.percentile(pts, 10) <= actual_points <= np.percentile(pts, 90))
    inside95 = bool(np.percentile(pts, 2.5) <= actual_points <= np.percentile(pts, 97.5))

    predicted_wins = float(samples["wins"].mean())
    predicted_reg = float(samples["regulation_losses"].mean())
    predicted_otl = float(samples["ot_losses"].mean())

    return {
        "train_season": train_rates.season,
        "target_season": str(target_log["season"].iloc[0]),
        "frozen_configuration": spec.details,
        "simulation": summary,
        "actual": {
            "points": actual_points, "wins": actual_wins,
            "regulation_losses": actual_reg_losses, "ot_losses": actual_otl,
            "gw_reg_otl": [actual_wins, actual_reg_losses, actual_otl],
        },
        "error": {
            "absolute_error_of_mean_points": round(abs(summary["mean_points"] - actual_points), 3),
            "error_of_median_points": round(abs(summary["median_points"] - actual_points), 3),
            "points_percentile_of_actual": round(float((pts <= actual_points).mean()) * 100, 2),
            "actual_inside_80pct_interval": inside80,
            "actual_inside_95pct_interval": inside95,
            "win_error": round(predicted_wins - actual_wins, 3),
            "regulation_loss_error": round(predicted_reg - actual_reg_losses, 3),
            "ot_loss_error": round(predicted_otl - actual_otl, 3),
        },
        "predicted_vs_actual_record": {
            "predicted_W_regL_OTL": [round(predicted_wins, 2), round(predicted_reg, 2),
                                     round(predicted_otl, 2)],
            "actual_W_regL_OTL": [actual_wins, actual_reg_losses, actual_otl],
        },
        "interpretation_limits": [
            "One backtest does not establish general forecasting accuracy.",
            "The target season's own totals were never used to fit or tune the model.",
            "A single season is one draw from a wide distribution; interval containment is "
            "weak evidence on its own.",
        ],
        "_samples": samples,
        "post_backtest_revisions": [],  # nothing was revised after seeing the target
        "samples_file": "outputs/tables/backtest_samples.npz",
    }
