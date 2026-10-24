"""Model core: score recovery, season arithmetic, reproducibility, analytic checks."""
from __future__ import annotations

import numpy as np
import pytest

from conftest import synthetic_game_log

from stars_forecast.model import (GAMES_PER_SEASON, Rates, ScenarioSpec, expected_points,
                                  fit_rates, simulate_seasons, summarize)


def _spec(lgf=3.0, lga=2.7, sid="T"):
    return ScenarioSpec(sid, "test", "test", lgf, lga, {})


def _rates(p=0.5, p_ot=0.5):
    return Rates(season="9999-00", lambda_gf=3.0, lambda_ga=2.7, p_win_if_tied=p,
                 p_ot_given_tied=p_ot, n_games=4, n_tied=2, n_tied_wins=1,
                 n_tied_losses=1, n_ot_games=1, n_so_games=1)


# ---------------------------------------------------------------- fixtures/hand math
def test_regulation_score_recovery_from_fixture():
    log = synthetic_game_log()
    r = fit_rates(log)
    # Regulation means: (3+1+2+2)/4 = 2.0 ; (1+4+2+2)/4 = 2.25
    assert r.lambda_gf == pytest.approx(2.0)
    assert r.lambda_ga == pytest.approx(2.25)


def test_final_hockey_totals_exclude_shootout():
    log = synthetic_game_log()
    assert log["goals_for_final_hockey"].sum() == 3 + 1 + 3 + 2
    assert log["goals_against_final_hockey"].sum() == 1 + 4 + 2 + 2
    # display totals add exactly one shootout goal
    assert log["goals_against_displayed"].sum() == log["goals_against_final_hockey"].sum() + 1


def test_fixture_points_and_record():
    log = synthetic_game_log()
    wins = (log["result"] == "W").sum()
    otl = ((log["result"] == "L") & log["finish"].isin(["OT", "SO"])).sum()
    regl = ((log["result"] == "L") & (log["finish"] == "REG")).sum()
    assert (wins, regl, otl) == (2, 1, 1)
    assert 2 * wins + otl == 5


def test_tied_game_probability_from_fixture():
    log = synthetic_game_log()
    r = fit_rates(log)
    # two games tied after regulation (one OT, one SO), Dallas won one of them
    assert r.p_win_if_tied == pytest.approx(0.5)
    assert r.p_ot_given_tied == pytest.approx(0.5)


def test_no_tied_games_raises():
    log = synthetic_game_log()
    log.loc[log["finish"].isin(["OT", "SO"]), "goals_for_reg"] = 9  # break the ties
    with pytest.raises(ValueError):
        fit_rates(log)


# ---------------------------------------------------------------- season arithmetic
def test_every_season_has_82_games_and_valid_points():
    s = simulate_seasons(_spec(), _rates(), n_seasons=300, seed=1)
    assert (s["wins"] + s["regulation_losses"] + s["ot_losses"] == GAMES_PER_SEASON).all()
    assert (s["points"] == 2 * s["wins"] + s["ot_losses"]).all()
    assert s["points"].max() <= 164 and s["points"].min() >= 0
    assert (s["points"] >= s["wins"]).all()


def test_goal_differential_definitions_differ_correctly():
    s = simulate_seasons(_spec(3.0, 3.0), _rates(), n_seasons=2000, seed=7)
    reg = s["regulation_goal_differential"].mean()
    final = s["final_hockey_goal_differential"].mean()
    assert reg == pytest.approx(0.0, abs=0.35)
    # An OT deciding goal moves the differential by +/-1 depending on the winner, so the
    # two definitions differ in spread but not in expectation when rates are equal.
    delta = s["final_hockey_goal_differential"].astype(float) - \
        s["regulation_goal_differential"].astype(float)
    assert abs(final - reg) < 0.35
    assert delta.std() > 0, "OT deciding goals must change per-season differentials"
    assert (np.abs(delta) <= 82).all()


def test_shootout_awards_no_goal_differential():
    # With p_ot_given_tied = 0, every tied game is a shootout: no deciding goal is added.
    rates = _rates(p=0.5, p_ot=0.0)
    s = simulate_seasons(_spec(2.8, 2.8), rates, n_seasons=1500, seed=11)
    assert np.all(s["final_hockey_goal_differential"] == s["regulation_goal_differential"])


# ---------------------------------------------------------------- reproducibility
def test_fixed_seed_reproducible():
    a = simulate_seasons(_spec(), _rates(), n_seasons=200, seed=3315)
    b = simulate_seasons(_spec(), _rates(), n_seasons=200, seed=3315)
    for key in a:
        assert np.array_equal(a[key], b[key])


def test_different_seed_differs():
    a = simulate_seasons(_spec(), _rates(), n_seasons=200, seed=3315)
    b = simulate_seasons(_spec(), _rates(), n_seasons=200, seed=3316)
    assert not np.array_equal(a["points"], b["points"])


def test_common_random_numbers_are_reusable():
    """Same seed, different rate -> same underlying draws, so differences are signal."""
    spec_a = _spec(3.0, 2.7)
    spec_b = _spec(3.3, 2.7)
    a = simulate_seasons(spec_a, _rates(), n_seasons=500, seed=42)
    b = simulate_seasons(spec_b, _rates(), n_seasons=500, seed=42)
    assert (b["points"].mean() - a["points"].mean()) > 0


# ---------------------------------------------------------------- analytic agreement
@pytest.mark.parametrize("lgf,lga", [(3.0, 2.7), (2.4, 3.1), (3.6, 3.6)])
def test_monte_carlo_matches_analytic_expectation(lgf, lga):
    rates = _rates()
    samples = simulate_seasons(_spec(lgf, lga), rates, n_seasons=6000, seed=99)
    mc = samples["points"].mean()
    analytic = expected_points(rates, lgf, lga)
    assert abs(mc - analytic) < 0.6, (mc, analytic)


def test_stronger_offense_never_lowers_expected_points():
    rates = _rates()
    analytic = [expected_points(rates, 3.0 * (1 + d), 2.7)
                for d in (-0.15, -0.05, 0.0, 0.05, 0.15)]
    assert analytic == sorted(analytic)
    mc = [simulate_seasons(_spec(3.0 * (1 + d), 2.7), rates, n_seasons=3000, seed=5)["points"].mean()
          for d in (-0.15, 0.0, 0.15)]
    assert mc[0] < mc[1] < mc[2]


def test_fewer_goals_allowed_never_lowers_expected_points():
    rates = _rates()
    analytic = [expected_points(rates, 3.0, 2.7 * (1 + d))
                for d in (0.15, 0.05, 0.0, -0.05, -0.15)]
    assert analytic == sorted(analytic)


def test_equal_rates_cancel_in_differential():
    s = simulate_seasons(_spec(2.9, 2.9), _rates(), n_seasons=3000, seed=3)
    assert abs(s["regulation_goal_differential"].mean()) < 0.3


# ---------------------------------------------------------------- summary contract
def test_summary_intervals_are_ordered_and_probabilities_valid():
    s = simulate_seasons(_spec(), _rates(), n_seasons=2000, seed=8)
    summ = summarize(s, [90, 95, 100, 105, 110])
    assert summ["interval_95"][0] <= summ["interval_80"][0] <= summ["median_points"] <= \
        summ["interval_80"][1] <= summ["interval_95"][1]
    probs = [summ[f"prob_at_least_{t}_points"] for t in (90, 95, 100, 105, 110)]
    assert probs == sorted(probs, reverse=True)
    assert all(0.0 <= p <= 1.0 for p in probs)
    assert summ["mean_wins"] + summ["mean_regulation_losses"] + summ["mean_ot_losses"] == \
        pytest.approx(82, abs=0.02)


def test_invalid_rates_rejected():
    with pytest.raises(ValueError):
        simulate_seasons(_spec(lgf=-1.0), _rates(), n_seasons=10, seed=1)
    with pytest.raises(ValueError):
        simulate_seasons(_spec(lgf=0.0), _rates(), n_seasons=10, seed=1)
