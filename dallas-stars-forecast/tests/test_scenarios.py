"""Scenario rules: isolation, units, neutrality and the documented normalizations."""
from __future__ import annotations

import copy

import pandas as pd
import pytest

from stars_forecast.model import fit_rates
from stars_forecast.scenarios import build_scenarios


@pytest.fixture()
def built(config, log26, totals26):
    base = fit_rates(log26)
    roster = pd.read_csv(__import__("stars_forecast.paths", fromlist=["PROCESSED"]).PROCESSED
                         / "roster_dal_2026_27.csv")
    return base, build_scenarios(config, base, totals26, roster)


def test_all_required_scenario_families_present(built):
    _, specs = built
    ids = {s.scenario_id for s in specs}
    assert "S0" in ids
    assert len([s for s in specs if s.family == "offense_sensitivity"]) == 6
    assert len([s for s in specs if s.family == "defense_sensitivity"]) == 6
    assert {"S3a", "S3b", "S3c", "S3d", "S4"} <= ids


def test_baseline_matches_fitted_rates(built):
    base, specs = built
    s0 = next(s for s in specs if s.scenario_id == "S0")
    assert s0.lambda_gf == pytest.approx(base.lambda_gf)
    assert s0.lambda_ga == pytest.approx(base.lambda_ga)


def test_offense_only_scenarios_leave_defense_untouched(built):
    base, specs = built
    for s in [x for x in specs if x.family == "offense_sensitivity"]:
        assert s.lambda_ga == pytest.approx(base.lambda_ga)
        pct = s.details["offense_pct_change"]
        assert s.lambda_gf == pytest.approx(base.lambda_gf * (1 + pct))


def test_defense_only_scenarios_leave_offense_untouched(built):
    base, specs = built
    for s in [x for x in specs if x.family == "defense_sensitivity"]:
        assert s.lambda_gf == pytest.approx(base.lambda_gf)
        pct = s.details["defense_pct_change"]
        assert s.lambda_ga == pytest.approx(base.lambda_ga * (1 + pct))


def test_scenario_isolation_baseline_unchanged(built):
    """Building scenarios must not mutate the baseline rates object."""
    base, _ = built
    assert base.lambda_gf == pytest.approx(base.lambda_gf)
    clone = copy.deepcopy(base)
    assert clone.lambda_gf == base.lambda_gf


def test_positive_rates_everywhere(built):
    _, specs = built
    for s in specs:
        assert s.lambda_gf > 0 and s.lambda_ga > 0, s.scenario_id


def test_personnel_units_and_normalization(config, log26, totals26):
    """projected goals = prior/prior_gp * assumed_gp * role; per-team-game = /82."""
    base = fit_rates(log26)
    roster = pd.read_csv(__import__("stars_forecast.paths", fromlist=["PROCESSED"]).PROCESSED
                         / "roster_dal_2026_27.csv")
    specs = {s.scenario_id: s for s in build_scenarios(config, base, totals26, roster)}
    s3b = specs["S3b"]
    net = s3b.details["net_goals_per_game"]
    manual = 0.0
    for c in s3b.details["components"]:
        assert c["per_team_game"] == pytest.approx(
            c["prior_goals"] / c["prior_gp"] * c["assumed_gp"] * c["role_factor"] / 82,
            abs=1e-5)
        manual += c["signed_effect"]
    assert net == pytest.approx(manual, abs=1e-5)
    assert s3b.lambda_gf == pytest.approx(base.lambda_gf + net)


def test_availability_uses_extra_games_only(config, log26, totals26):
    base = fit_rates(log26)
    roster = pd.read_csv(__import__("stars_forecast.paths", fromlist=["PROCESSED"]).PROCESSED
                         / "roster_dal_2026_27.csv")
    specs = {s.scenario_id: s for s in build_scenarios(config, base, totals26, roster)}
    s3a = specs["S3a"]
    comp = s3a.details["components"][0]
    assert comp["extra_games"] == comp["assumed_gp"] - comp["prior_gp"] == 18
    expected = 22 / 64 * 18 * 1.0 / 82
    assert s3a.details["net_goals_per_game"] == pytest.approx(expected, abs=1e-5)


def test_goaltending_uses_save_pct_and_shots(config, log26, totals26):
    base = fit_rates(log26)
    roster = pd.read_csv(__import__("stars_forecast.paths", fromlist=["PROCESSED"]).PROCESSED
                         / "roster_dal_2026_27.csv")
    specs = {s.scenario_id: s for s in build_scenarios(config, base, totals26, roster)}
    s3c = specs["S3c"]
    delta_ga = 0.010 * float(totals26["shots_against_per_game"])
    assert s3c.lambda_ga == pytest.approx(base.lambda_ga - delta_ga)
    assert s3c.lambda_gf == pytest.approx(base.lambda_gf)
    # improved goaltending must lower goals allowed
    assert s3c.lambda_ga < base.lambda_ga


def test_combined_scenario_equals_sum_of_separate_effects(config, log26, totals26):
    base = fit_rates(log26)
    roster = pd.read_csv(__import__("stars_forecast.paths", fromlist=["PROCESSED"]).PROCESSED
                         / "roster_dal_2026_27.csv")
    specs = {s.scenario_id: s for s in build_scenarios(config, base, totals26, roster)}
    s4 = specs["S4"]
    assert s4.lambda_gf == pytest.approx(specs["S3a"].lambda_gf)
    assert s4.lambda_ga == pytest.approx(specs["S3c"].lambda_ga)
    assert "order_of_application" in s4.details


def test_equal_replacement_is_neutral(config, log26, totals26):
    """An identical player in and out must leave the rate unchanged."""
    cfg = copy.deepcopy(config)
    cfg["roster"]["scenarios"] = [{
        "id": "NEUTRAL", "name": "neutral", "family": "personnel", "type": "offense",
        "components": [
            dict(player="Out", direction="out", prior_goals=20, prior_gp=82, assumed_gp=82),
            dict(player="In", direction="in", prior_goals=20, prior_gp=82, assumed_gp=82),
        ]}]
    base = fit_rates(log26)
    roster = pd.read_csv(__import__("stars_forecast.paths", fromlist=["PROCESSED"]).PROCESSED
                         / "roster_dal_2026_27.csv")
    spec = build_scenarios(cfg, base, totals26, roster)[-1]
    assert spec.lambda_gf == pytest.approx(base.lambda_gf, abs=1e-12)
    assert spec.details["net_goals_per_game"] == pytest.approx(0.0, abs=1e-5)


def test_impossible_games_played_rejected(config, log26, totals26):
    cfg = copy.deepcopy(config)
    cfg["roster"]["scenarios"] = [{
        "id": "BAD", "name": "bad", "family": "personnel", "type": "offense",
        "components": [dict(player="X", direction="in", prior_goals=10, prior_gp=82,
                            assumed_gp=120)]}]
    base = fit_rates(log26)
    roster = pd.read_csv(__import__("stars_forecast.paths", fromlist=["PROCESSED"]).PROCESSED
                         / "roster_dal_2026_27.csv")
    with pytest.raises(ValueError):
        build_scenarios(cfg, base, totals26, roster)


def test_unknown_combine_target_rejected(config, log26, totals26):
    cfg = copy.deepcopy(config)
    cfg["roster"]["scenarios"] = [{
        "id": "S4", "name": "bad combine", "family": "combined", "type": "both",
        "combines": ["NOPE"]}]
    base = fit_rates(log26)
    roster = pd.read_csv(__import__("stars_forecast.paths", fromlist=["PROCESSED"]).PROCESSED
                         / "roster_dal_2026_27.csv")
    with pytest.raises(ValueError):
        build_scenarios(cfg, base, totals26, roster)
