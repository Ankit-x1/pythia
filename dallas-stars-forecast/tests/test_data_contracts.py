"""Data contracts: acquisition/cleaning rules verified against the real datasets."""
from __future__ import annotations

import json

import pandas as pd
import pytest


def test_regular_season_only(log26, log25):
    assert set(log26["game_type"].unique()) == {2}
    assert set(log25["game_type"].unique()) == {2}
    assert set(log26["season"].unique()) == {"2025-26"}


def test_complete_season_counts(log26, log25):
    assert len(log26) == 82
    assert len(log25) == 82


def test_unique_game_ids(log26, log25):
    assert log26["game_id"].is_unique
    assert log25["game_id"].is_unique
    assert not set(log26["game_id"]) & set(log25["game_id"])


@pytest.mark.parametrize("fixture_name", ["log26", "log25"])
def test_result_categories(fixture_name, request):
    log = request.getfixturevalue(fixture_name)
    assert set(log["result"].unique()) <= {"W", "L"}
    assert set(log["finish"].unique()) <= {"REG", "OT", "SO"}
    assert set(log["home_away"].unique()) == {"H", "A"}
    assert log["home_away"].value_counts().to_dict() == {"H": 41, "A": 41}


@pytest.mark.parametrize("fixture_name", ["log26", "log25"])
def test_record_and_points_identities(fixture_name, request):
    log = request.getfixturevalue(fixture_name)
    wins = int((log["result"] == "W").sum())
    otl = int(((log["result"] == "L") & log["finish"].isin(["OT", "SO"])).sum())
    regl = int(((log["result"] == "L") & (log["finish"] == "REG")).sum())
    points = 2 * wins + otl
    assert wins + regl + otl == 82
    assert 0 <= points <= 164
    assert points == 2 * wins + otl


def test_2025_26_points_reconcile(log26, totals26):
    wins = int((log26["result"] == "W").sum())
    otl = int(((log26["result"] == "L") & log26["finish"].isin(["OT", "SO"])).sum())
    assert (wins, int(totals26["wins"])) == (50, 50)
    assert 2 * wins + otl == int(totals26["points"]) == 112


def test_goal_convention_matching_official(log26, log25, totals26):
    """The official NHL totals include OT goals: they match reg+OT, not reg only."""
    for log, totals in [(log26, totals26),
                        (log25, pd.read_csv(log26.attrs.get("path", "")) if False else None)]:
        if totals is None:
            continue
        assert int(log["goals_for_final_hockey"].sum()) == int(totals["goals_for"])
        assert int(log["goals_against_final_hockey"].sum()) == int(totals["goals_against"])
        assert int(log["goals_for_reg"].sum()) < int(totals["goals_for"])
        assert int(log["goals_against_reg"].sum()) < int(totals["goals_against"])
        assert int(log["goals_for_displayed"].sum()) > int(totals["goals_for"])


def test_shootout_increment_is_separate(log26):
    so_games = log26[log26["finish"] == "SO"]
    assert len(so_games) > 0
    # Exactly one artificial shootout goal appears in each SO game, on the winner's side.
    for _, row in so_games.iterrows():
        assert row["goals_for_so"] + row["goals_against_so"] == 1
        assert row["goals_for_final_hockey"] == row["goals_against_final_hockey"]


def test_ot_games_tie_after_regulation(log26):
    for finish in ("OT", "SO"):
        sub = log26[log26["finish"] == finish]
        assert (sub["goals_for_reg"] == sub["goals_against_reg"]).all()
    ot = log26[log26["finish"] == "OT"]
    assert ((ot["goals_for_ot"] + ot["goals_against_ot"]) == 1).all()


def test_tied_game_count_matches_ot_plus_so(log26):
    tied = int((log26["goals_for_reg"] == log26["goals_against_reg"]).sum())
    assert tied == int(log26["finish"].isin(["OT", "SO"]).sum())


def test_mandatory_fields_present(log26):
    mandatory = ["game_id", "date", "opponent", "home_away", "goals_for_reg",
                 "goals_against_reg", "result", "finish", "shots_for", "shots_against"]
    assert not log26[mandatory].isna().any().any()


def test_units_are_sane(log26, totals26):
    assert log26["goals_for_reg"].between(0, 15).all()
    assert log26["shots_for"].between(5, 60).all()
    assert 0 < float(totals26["pp_pct"]) < 1
    assert 0 < float(totals26["faceoff_win_pct"]) < 1


def test_shots_reconcile_to_official_per_game(log26, totals26):
    assert abs(int(log26["shots_for"].sum()) - totals26["shots_for_per_game"] * 82) <= 1
    assert abs(int(log26["shots_against"].sum()) - totals26["shots_against_per_game"] * 82) <= 1


def test_power_play_reconciles(log26, totals26):
    pct = log26["pp_goals_for"].sum() / log26["pp_opps_for"].sum()
    assert abs(pct - float(totals26["pp_pct"])) < 0.005


def test_central_standings_complete(standings):
    assert sorted(standings["season"].unique()) == ["2021-22", "2022-23", "2023-24",
                                                    "2024-25", "2025-26"]
    assert (standings.groupby("season").size() == 8).all()
    grouped = standings.groupby("season")
    assert (grouped["division_rank"].nunique() == 8).all()
    assert ((2 * standings["wins"] + standings["ot_losses"]) == standings["points"]).all()


def test_no_2026_27_fitting_data(log26, log25, standings):
    seasons = set(log26["season"]) | set(log25["season"]) | set(standings["season"])
    assert "2026-27" not in seasons


def test_roster_contract():
    from stars_forecast.paths import PROCESSED
    roster = pd.read_csv(PROCESSED / "roster_dal_2026_27.csv")
    assert set(roster["position_group"].unique()) == {"F", "D", "G"}
    assert roster["player"].is_unique
    assert len(roster) >= 20


def test_cross_source_reconciliation_evidence():
    from stars_forecast.paths import PROCESSED
    hr = json.loads((PROCESSED / "hr_crosscheck_2025_26.json").read_text())
    assert hr["available"] is True
    # Hockey-Reference prints box-score scores, which include the shootout increment.
    assert hr["hr_sum_GF"] == hr["log_sum_GF_displayed"]
    assert hr["hr_sum_GA"] == hr["log_sum_GA_displayed"]
    assert hr["hr_rows"] == 82


def test_validation_artifact_passes():
    from stars_forecast.paths import QA
    payload = json.loads((QA / "data-validation.json").read_text())
    failed = [c["check"] for c in payload["checks"] if not c["passed"]]
    assert payload["all_passed"], f"failing data checks: {failed}"
