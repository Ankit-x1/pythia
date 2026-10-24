"""Standings translation, backtest isolation and the end-to-end pipeline contract."""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from stars_forecast.backtest import run_backtest
from stars_forecast.model import fit_rates
from stars_forecast.paths import PROCESSED, QA, TABLES
from stars_forecast.standings import season_thresholds, translate


# ---------------------------------------------------------------- standings translation
def test_thresholds_match_historical_third_place(standings):
    th = season_thresholds(standings, 3)
    assert len(th) == 5
    for t in th:
        third = standings[(standings.season == t["season"]) & (standings.division_rank == 3)]
        assert t["third_place_points"] == int(third["points"].iloc[0])


def test_translation_probabilities_are_monotone_in_points(standings):
    low = np.full(500, 85)
    high = np.full(500, 120)
    p_low = translate(low, standings)["prob_meets_third_place_points"]
    p_high = translate(high, standings)["prob_meets_third_place_points"]
    assert p_low == 0.0
    assert p_high == 1.0


def test_translation_rank_interval_is_ordered(standings):
    rng = np.random.default_rng(0)
    pts = rng.integers(75, 130, size=2000)
    out = translate(pts, standings)
    best, worst = out["mean_division_rank_range"]
    assert 1 <= best <= worst <= 8
    lo, hi = out["prob_top3_rank_range"]
    assert 0.0 <= lo <= hi <= 1.0
    for row in out["per_season"]:
        assert row["mean_best_rank"] <= row["mean_worst_rank"]


def test_historical_dallas_excluded_from_competitors(standings):
    # A total equal to a season's 1st-place points must be at worst rank 1 among
    # the seven rivals, never 2.
    first = int(standings[standings.division_rank == 1]["points"].max())
    out = translate(np.array([first + 40]), standings)
    assert out["prob_rank_1"] == 1.0


def test_tie_rule_is_at_least(standings):
    thr = season_thresholds(standings)[0]["third_place_points"]
    out = translate(np.array([thr]), standings)
    assert out["per_season"][0]["prob_points_at_least_third_place"] == 1.0
    assert out["per_season"][0]["prob_points_exactly_third_place"] == 1.0


# ---------------------------------------------------------------- backtest isolation
def test_backtest_uses_only_training_season(log25, log26, totals26):
    bt = run_backtest(log25, log26, totals26, n_seasons=1500, seed=3315,
                      thresholds=[90, 100, 110])
    # Frozen rates must equal the 2024-25 fit exactly.
    train = fit_rates(log25)
    assert bt["frozen_configuration"]["lambda_gf"] == pytest.approx(train.lambda_gf, abs=1e-4)
    assert bt["frozen_configuration"]["lambda_ga"] == pytest.approx(train.lambda_ga, abs=1e-4)
    assert bt["frozen_configuration"]["frozen_from"] == "2024-25"
    assert bt["post_backtest_revisions"] == []


def test_backtest_records_target_outcome_separately(log25, log26, totals26):
    bt = run_backtest(log25, log26, totals26, n_seasons=1500, seed=3315, thresholds=[100])
    assert bt["actual"]["points"] == int(totals26["points"])
    assert bt["target_season"] == "2025-26"
    err = bt["error"]
    assert err["absolute_error_of_mean_points"] == pytest.approx(
        abs(bt["simulation"]["mean_points"] - bt["actual"]["points"]), abs=1e-6)
    assert isinstance(err["actual_inside_80pct_interval"], bool)
    assert err["points_percentile_of_actual"] >= 0


def test_backtest_does_not_read_target_rates(log25, log26, totals26):
    """Corrupting the target total must change only the evaluation, never the forecast."""
    bt_a = run_backtest(log25, log26, totals26, n_seasons=800, seed=3315, thresholds=[100])
    mutated = totals26.copy()
    mutated["points"] = 60
    bt_b = run_backtest(log25, log26, mutated, n_seasons=800, seed=3315, thresholds=[100])
    assert bt_a["simulation"]["mean_points"] == bt_b["simulation"]["mean_points"]
    assert bt_a["actual"]["points"] != bt_b["actual"]["points"]


# ---------------------------------------------------------------- pipeline artifacts
def test_pipeline_outputs_exist_and_are_consistent():
    required = [
        TABLES / "scenario_summary.csv", TABLES / "diagnostics.json",
        TABLES / "backtest.json", TABLES / "run_manifest.json",
        TABLES / "central_thresholds.json", QA / "data-validation.json",
    ]
    for path in required:
        assert path.exists(), f"missing artifact {path}"

    table = pd.read_csv(TABLES / "scenario_summary.csv")
    assert {"S0", "S3a", "S3b", "S3c", "S3d", "S4"} <= set(table["scenario_id"])
    assert (table["interval_80_low"] <= table["median_points"]).all()
    assert (table["median_points"] <= table["interval_80_high"]).all()
    assert (table["interval_95_low"] <= table["interval_80_low"]).all()
    assert (table["interval_80_high"] <= table["interval_95_high"]).all()
    for col in [c for c in table.columns if c.startswith("prob_")]:
        assert table[col].between(0, 1).all(), col

    manifest = json.loads((TABLES / "run_manifest.json").read_text())
    assert manifest["n_seasons"] >= 1000
    assert manifest["data_checksums"]
    assert all(len(v) == 64 for v in manifest["data_checksums"].values())

    # Stronger offense / fewer goals allowed must not lower mean points.
    s1 = table[table.family == "offense_sensitivity"].sort_values("lambda_gf")
    assert s1["mean_points"].is_monotonic_increasing
    # For defense, a higher lambda_GA means more goals allowed, so points must fall.
    s2 = table[table.family == "defense_sensitivity"].sort_values("lambda_ga")
    assert s2["mean_points"].is_monotonic_decreasing


def test_analytic_check_recorded_for_every_scenario():
    for path in sorted(TABLES.glob("scenario_S*.json")):
        payload = json.loads(path.read_text())
        assert abs(payload["mc_minus_analytic"]) < 1.2, path.name


def test_scenario_samples_reproduce_summaries():
    payload = json.loads((TABLES / "scenario_S0.json").read_text())
    samples = np.load(TABLES / "samples_S0.npz")
    assert samples["points"].mean() == pytest.approx(payload["summary"]["mean_points"], abs=0.01)
    assert len(samples["points"]) == payload["n_seasons"]
