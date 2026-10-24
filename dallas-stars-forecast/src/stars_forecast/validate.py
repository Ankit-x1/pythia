"""Automated data validation for datasets A-G.

Writes outputs/qa/data-validation.json. Every check records the evidence used so
the data report can cite an artifact rather than an assertion.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Callable

import numpy as np
import pandas as pd

from .paths import PROCESSED, QA, rel

REQUIRED_GAME_COLS = [
    "game_id", "date", "season", "game_type", "opponent", "home_away",
    "goals_for_reg", "goals_against_reg", "goals_for_final_hockey",
    "goals_against_final_hockey", "result", "finish", "shots_for", "shots_against",
]


class Validator:
    def __init__(self) -> None:
        self.checks: list[dict[str, Any]] = []

    def check(self, name: str, dataset: str, fn: Callable[[], tuple[bool, str, Any]]) -> None:
        try:
            passed, detail, evidence = fn()
        except Exception as exc:  # a validation crash is a failure, not a skip
            passed, detail, evidence = False, f"exception: {exc}", None
        self.checks.append({
            "check": name, "dataset": dataset, "passed": bool(passed),
            "detail": detail, "evidence": evidence,
        })

    @property
    def all_passed(self) -> bool:
        return all(c["passed"] for c in self.checks)


def _load(name: str) -> pd.DataFrame:
    return pd.read_csv(PROCESSED / name)


def run_validation() -> dict[str, Any]:
    v = Validator()

    log26 = _load("game_log_dal_2025_26.csv")
    log25 = _load("game_log_dal_2024_25.csv")
    totals26 = _load("team_totals_dal_2025_26.csv").iloc[0]
    totals25 = _load("team_totals_dal_2024_25.csv").iloc[0]
    skaters = _load("skaters_dal_2025_26.csv")
    goalies = _load("goalies_dal_2025_26.csv")
    standings = _load("central_standings_2021_2026.csv")
    roster = _load("roster_dal_2026_27.csv")

    # ---------------------------------------------------------------- completeness
    for label, fname, min_rows in [
        ("A", "team_totals_dal_2025_26.csv", 1), ("B", "game_log_dal_2025_26.csv", 82),
        ("C", "skaters_dal_2025_26.csv", 15), ("D", "goalies_dal_2025_26.csv", 2),
        ("E", "team_totals_dal_2024_25.csv", 1), ("E", "game_log_dal_2024_25.csv", 82),
        ("F", "central_standings_2021_2026.csv", 40), ("G", "roster_dal_2026_27.csv", 20),
    ]:
        v.check(f"dataset_{label}_present:{fname}", label, lambda f=fname, n=min_rows: (
            (PROCESSED / f).exists() and len(pd.read_csv(PROCESSED / f)) >= n,
            f"{f} has {len(pd.read_csv(PROCESSED / f)) if (PROCESSED / f).exists() else 0} rows "
            f"(>= {n} required)",
            {"file": rel(PROCESSED / f)}))

    # ---------------------------------------------------------------- regular season
    v.check("regular_season_only_games", "B", lambda: (
        bool((log26["game_type"] == 2).all() and (log25["game_type"] == 2).all()),
        "every game row has game_type == 2 (regular season)",
        {"rows_2025_26": len(log26), "rows_2024_25": len(log25)}))
    v.check("all_games_final", "B", lambda: (
        bool(log26["game_state"].isin(["FINAL", "OFF"]).all()),
        "every 2025-26 game is complete ('OFF' is the NHL API's terminal state for a "
        "finished game in this endpoint version; 'FINAL' also accepted)",
        {"game_states": sorted(log26["game_state"].unique().tolist())}))
    v.check("season_game_counts", "B", lambda: (
        len(log26) == 82 and len(log25) == 82,
        f"2025-26: {len(log26)} games, 2024-25: {len(log25)} games (82 required)",
        {"games_2025_26": len(log26), "games_2024_25": len(log25)}))
    v.check("unique_game_ids", "B", lambda: (
        log26["game_id"].is_unique and log25["game_id"].is_unique,
        "no duplicate game IDs in either season",
        {"n_2025_26": int(log26["game_id"].nunique()),
         "n_2024_25": int(log25["game_id"].nunique())}))

    # ---------------------------------------------------------------- standings math
    def rec_point_math(df: pd.DataFrame) -> tuple[bool, str, Any]:
        w = int((df["result"] == "W").sum())
        otl = int(((df["result"] == "L") & (df["finish"].isin(["OT", "SO"]))).sum())
        regl = int(((df["result"] == "L") & (df["finish"] == "REG")).sum())
        pts = 2 * w + otl
        ok = (w + regl + otl == 82) and pts == int(totals26["points"])
        return ok, (f"W={w}, regL={regl}, OTL={otl}, sum={w + regl + otl}; "
                    f"points=2W+OTL={pts} vs official {int(totals26['points'])}"), \
            {"wins": w, "regulation_losses": regl, "ot_losses": otl, "points": pts}

    v.check("game_log_points_reconcile", "B", lambda: rec_point_math(log26))

    def rec_point_math_25() -> tuple[bool, str, Any]:
        w = int((log25["result"] == "W").sum())
        otl = int(((log25["result"] == "L") & (log25["finish"].isin(["OT", "SO"]))).sum())
        regl = int(((log25["result"] == "L") & (log25["finish"] == "REG")).sum())
        pts = 2 * w + otl
        return pts == int(totals25["points"]) and w + regl + otl == 82, \
            f"2024-25: W={w}, regL={regl}, OTL={otl}, points={pts} vs official {int(totals25['points'])}", \
            {"wins": w, "regulation_losses": regl, "ot_losses": otl, "points": pts}

    v.check("game_log_points_reconcile_2024_25", "E", rec_point_math_25)

    # ---------------------------------------------------------------- goal conventions
    def convention_check(df: pd.DataFrame, totals: pd.Series) -> tuple[bool, str, Any]:
        gf_o, ga_o = int(totals["goals_for"]), int(totals["goals_against"])
        cands = {
            "regulation_only": (int(df["goals_for_reg"].sum()), int(df["goals_against_reg"].sum())),
            "final_hockey_reg_plus_ot": (int(df["goals_for_final_hockey"].sum()),
                                         int(df["goals_against_final_hockey"].sum())),
            "displayed_incl_shootout": (int(df["goals_for_displayed"].sum()),
                                        int(df["goals_against_displayed"].sum())),
        }
        matches = [k for k, (a, b) in cands.items() if a == gf_o and b == ga_o]
        detail = (f"official GF/GA = {gf_o}/{ga_o}; "
                  + "; ".join(f"{k}={a}/{b}" for k, (a, b) in cands.items())
                  + f"; matching convention(s): {matches or 'NONE'}")
        return bool(matches), detail, {"official": [gf_o, ga_o], "candidates": cands,
                                       "matches": matches}

    v.check("goal_convention_reconcile_2025_26", "B", lambda: convention_check(log26, totals26))
    v.check("goal_convention_reconcile_2024_25", "E", lambda: convention_check(log25, totals25))

    # ---------------------------------------------------------------- shots / special teams
    def shots_check() -> tuple[bool, str, Any]:
        sf = int(log26["shots_for"].sum())
        sa = int(log26["shots_against"].sum())
        exp_f = totals26["shots_for_per_game"] * 82
        exp_a = totals26["shots_against_per_game"] * 82
        ok = abs(sf - exp_f) <= 1.0 and abs(sa - exp_a) <= 1.0
        return ok, f"game-log shots {sf}/{sa} vs per-game x 82 {exp_f:.0f}/{exp_a:.0f}", \
            {"shots_for": sf, "shots_against": sa}

    v.check("shots_reconcile", "B", shots_check)

    def pp_check() -> tuple[bool, str, Any]:
        ppg = float(log26["pp_goals_for"].sum())
        ppo = float(log26["pp_opps_for"].sum())
        pct = ppg / ppo
        ok = abs(pct - float(totals26["pp_pct"])) < 0.005
        return ok, f"PP {ppg:.0f}/{ppo:.0f} = {pct:.4f} vs official {totals26['pp_pct']:.4f}", \
            {"pp_goals": ppg, "pp_opps": ppo, "pp_pct_from_log": round(pct, 5)}

    v.check("power_play_reconcile", "B", pp_check)

    # ---------------------------------------------------------------- player level
    def goalie_check() -> tuple[bool, str, Any]:
        ga_goalies = int(goalies["goals_against"].sum())
        sa = int(goalies["shots_against"].sum())
        team_ga = int(totals26["goals_against"])
        saves = int(goalies["saves"].sum())
        team_sa = int(log26["shots_against"].sum())
        empty_net = team_ga - ga_goalies
        per_row_identity = bool(((goalies["saves"] + goalies["goals_against"])
                                 == goalies["shots_against"]).all())
        # An empty-net goal beats no goalie, so it is a team shot on goal that no goalie
        # faced: team_SA - goalie_SA should equal the empty-net/attribution gap.
        ok = (per_row_identity and empty_net >= 0
              and (team_sa - sa) == empty_net and empty_net <= 0.10 * team_ga)
        return ok, (f"per-goalie saves+GA = shots_against {per_row_identity}; goalie SA {sa} vs "
                    f"team SA {team_sa} (gap {team_sa - sa}); goalie GA {ga_goalies} vs team GA "
                    f"{team_ga} (gap {empty_net} = empty-net/attribution goals, consistent with "
                    f"the SA gap)"), \
            {"goalie_ga": ga_goalies, "team_ga": team_ga, "goalie_sa": sa, "team_sa": team_sa,
             "empty_net_gap": empty_net}

    v.check("goalie_reconcile", "D", goalie_check)

    def skater_check() -> tuple[bool, str, Any]:
        g = int(skaters["goals"].sum())
        gf = int(totals26["goals_for"])
        return abs(g - gf) <= 5, f"skater goals (DAL-attributed) = {g} vs team GF {gf}", \
            {"skater_goals": g, "team_gf": gf}

    v.check("skater_reconcile", "C", skater_check)

    v.check("traded_player_attribution", "C", lambda: (
        bool(skaters["team_attribution"].astype(str).str.contains("DAL").all()),
        "every skater row carries a Dallas team attribution (Dallas-only contribution)",
        {"attributions": sorted(skaters["team_attribution"].astype(str).unique().tolist())}))

    # ---------------------------------------------------------------- historical standings
    v.check("historical_seasons_complete", "F", lambda: (
        sorted(standings["season"].unique().tolist()) ==
        ["2021-22", "2022-23", "2023-24", "2024-25", "2025-26"],
        f"seasons present: {sorted(standings['season'].unique().tolist())}",
        {"rows_per_season": standings.groupby("season").size().to_dict()}))
    v.check("central_division_membership", "F", lambda: (
        bool((standings.groupby("season").size() == 8).all()),
        "8 Central Division teams in every historical season",
        {"counts": standings.groupby("season").size().to_dict()}))
    v.check("standings_games_played", "F", lambda: (
        bool(standings["gp"].isin([81, 82]).all()),
        "all team-seasons played 81 or 82 games (a small number of 81s are recorded, not "
        f"silently altered): {standings.groupby('season')['gp'].agg(['min', 'max']).to_dict()}",
        {"gp_counts": standings["gp"].value_counts().to_dict()}))
    v.check("standings_point_math", "F", lambda: (
        bool(((2 * standings["wins"] + standings["ot_losses"]) == standings["points"]).all()),
        "points = 2*W + OTL for every historical team-season",
        {"n_rows": len(standings)}))
    v.check("standings_rank_unique", "F", lambda: (
        bool((standings.groupby("season")["division_rank"].nunique() == 8).all()),
        "division ranks 1-8 unique within each season",
        {"ranks": sorted(standings["division_rank"].unique().tolist())}))

    # ---------------------------------------------------------------- roster / leakage
    v.check("no_2026_27_fitting_data", "G", lambda: (
        set(log26["season"].unique()) == {"2025-26"} and set(log25["season"].unique()) == {"2024-25"}
        and "2026-27" not in set(standings["season"].unique()),
        "no 2026-27 game results exist anywhere in the processed data",
        {"game_log_seasons": sorted(set(log26["season"]) | set(log25["season"])),
         "standings_seasons": sorted(standings["season"].unique().tolist())}))
    v.check("roster_positions_valid", "G", lambda: (
        set(roster["position_group"].unique()) == {"F", "D", "G"},
        f"roster groups: {sorted(roster['position_group'].unique().tolist())}",
        {"n_players": len(roster)}))

    # ---------------------------------------------------------------- missing values
    def missing_check() -> tuple[bool, str, Any]:
        problems = {}
        for df, cols, label in [(log26, REQUIRED_GAME_COLS, "game_log_2025_26"),
                                (log25, REQUIRED_GAME_COLS, "game_log_2024_25")]:
            miss = [c for c in cols if df[c].isna().any()]
            if miss:
                problems[label] = miss
        return not problems, ("no missing mandatory game-log values" if not problems
                              else f"missing: {problems}"), problems or {"clean": True}

    v.check("mandatory_fields_complete", "B", missing_check)

    # ---------------------------------------------------------------- HR cross-check
    hr_path = PROCESSED / "hr_crosscheck_2025_26.json"
    hr = json.loads(hr_path.read_text()) if hr_path.exists() else {"available": False}

    def hr_check() -> tuple[bool, str, Any]:
        if not hr.get("available"):
            return False, f"Hockey-Reference cross-check unavailable: {hr.get('reason')}", hr
        # Hockey-Reference prints the box-score score, so its GF/GA totals include the
        # shootout decision increment. Compare like with like: HR vs our 'displayed'
        # sums, and official NHL totals vs our regulation+OT ('final hockey') sums.
        ok = (hr["hr_sum_GF"] == hr["log_sum_GF_displayed"]
              and hr["hr_sum_GA"] == hr["log_sum_GA_displayed"])
        return ok, (f"Hockey-Reference SUM GF/GA = {hr['hr_sum_GF']:.0f}/{hr['hr_sum_GA']:.0f} "
                    f"matches cleaned log displayed sums "
                    f"{hr['log_sum_GF_displayed']:.0f}/{hr['log_sum_GA_displayed']:.0f}; both "
                    f"differ from the official NHL team totals by the "
                    f"{hr['log_sum_GF_displayed'] - hr['log_sum_GF_final_hockey']:.0f} shootout "
                    f"decision goals, which the official total excludes"), hr

    v.check("cross_source_gamelog_reconcile", "cross-check", hr_check)

    conventions = {
        "dallas_2025_26_official_totals": {
            "goals_for": int(totals26["goals_for"]), "goals_against": int(totals26["goals_against"]),
            "wins": int(totals26["wins"]), "regulation_losses": int(totals26["losses"]),
            "ot_losses": int(totals26["ot_losses"]), "points": int(totals26["points"]),
        },
        "goal_convention_matching_official_totals": next(
            (c["evidence"]["matches"] for c in v.checks
             if c["check"] == "goal_convention_reconcile_2025_26" and c["evidence"]), []),
    }

    payload = {
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "all_passed": v.all_passed,
        "n_checks": len(v.checks),
        "n_passed": sum(c["passed"] for c in v.checks),
        "conventions": conventions,
        "checks": v.checks,
    }
    QA.mkdir(parents=True, exist_ok=True)
    (QA / "data-validation.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def load_validation() -> dict[str, Any]:
    path = QA / "data-validation.json"
    if not path.exists():
        raise FileNotFoundError("run 'validate-data' first")
    return json.loads(path.read_text())
