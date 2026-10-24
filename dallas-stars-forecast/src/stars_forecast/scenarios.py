"""Scenario families S0-S4 built from verified data and config/scenarios.yaml.

S0  Baseline                       2025-26 regulation rates, unchanged
S1  Offense sensitivity            lambda_GF x (1 + s), lambda_GA fixed
S2  Defense sensitivity            lambda_GA x (1 + d), lambda_GF fixed
S3  Personnel / availability /
    goaltending                    transparent normalization of verified player or
                                   save-percentage data into a rate change
S4  Combined case                  effects evaluated separately, then applied in a
                                   documented order
"""
from __future__ import annotations

from typing import Any

import pandas as pd

from .model import Rates, ScenarioSpec

GAMES_PER_SEASON = 82


def _personnel_delta(components: list[dict[str, Any]]) -> tuple[float, list[dict[str, Any]]]:
    """Net per-team-game scoring change from roster components.

    projected_goals = prior_goals / prior_gp * assumed_gp * role_factor
    contribution    = projected_goals / 82   (per Dallas team game)
    """
    trace: list[dict[str, Any]] = []
    net = 0.0
    for c in components:
        prior_gp = int(c["prior_gp"])
        assumed_gp = int(c["assumed_gp"])
        if prior_gp <= 0 or assumed_gp < 0 or assumed_gp > GAMES_PER_SEASON:
            raise ValueError(f"invalid games-played assumption for {c['player']}: "
                             f"prior_gp={prior_gp}, assumed_gp={assumed_gp}")
        role = float(c.get("role_factor", 1.0))
        if not 0.0 < role <= 2.0:
            raise ValueError(f"role factor out of range for {c['player']}: {role}")
        projected = int(c["prior_goals"]) / prior_gp * assumed_gp * role
        contrib = projected / GAMES_PER_SEASON
        signed = contrib if c["direction"] == "in" else -contrib
        net += signed
        trace.append({
            "player": c["player"], "direction": c["direction"],
            "prior_goals": int(c["prior_goals"]), "prior_gp": prior_gp,
            "assumed_gp": assumed_gp, "role_factor": role,
            "projected_goals": round(projected, 3),
            "per_team_game": round(contrib, 5),
            "signed_effect": round(signed, 5),
            "note": c.get("note", ""),
        })
    return net, trace


def _availability_delta(components: list[dict[str, Any]]) -> tuple[float, list[dict[str, Any]]]:
    """Extra goals from extra games for a player already counted in the baseline.

    delta_per_game = prior_goals / prior_gp * (assumed_gp - prior_gp) * role_factor / 82
    """
    trace: list[dict[str, Any]] = []
    net = 0.0
    for c in components:
        prior_gp, assumed_gp = int(c["prior_gp"]), int(c["assumed_gp"])
        if prior_gp <= 0 or not 0 <= assumed_gp <= GAMES_PER_SEASON:
            raise ValueError(f"invalid games-played assumption for {c['player']}")
        role = float(c.get("role_factor", 1.0))
        if not 0.0 < role <= 2.0:
            raise ValueError(f"role factor out of range for {c['player']}: {role}")
        rate = int(c["prior_goals"]) / prior_gp
        extra_goals = rate * (assumed_gp - prior_gp) * role
        contrib = extra_goals / GAMES_PER_SEASON if extra_goals >= 0 else -abs(extra_goals) / GAMES_PER_SEASON
        net += contrib
        trace.append({
            "player": c["player"], "mode": "availability",
            "prior_goals": int(c["prior_goals"]), "prior_gp": prior_gp,
            "assumed_gp": assumed_gp, "role_factor": role,
            "goals_per_game_rate": round(rate, 5),
            "extra_games": assumed_gp - prior_gp,
            "extra_goals": round(extra_goals, 3),
            "per_team_game": round(contrib, 5),
            "note": c.get("note", ""),
        })
    return net, trace


def build_scenarios(cfg: dict[str, Any], base: Rates, team_totals: pd.Series,
                    roster: pd.DataFrame) -> list[ScenarioSpec]:
    """Resolve every scenario into explicit goal rates. Baseline stays untouched."""
    lgf0, lga0 = base.lambda_gf, base.lambda_ga
    shots_against_per_game = float(team_totals["shots_against_per_game"])
    scenarios: list[ScenarioSpec] = []

    scenarios.append(ScenarioSpec(
        scenario_id="S0", name="Baseline (2025-26 regulation rates)", family="baseline",
        lambda_gf=lgf0, lambda_ga=lga0,
        details={"lambda_gf": round(lgf0, 5), "lambda_ga": round(lga0, 5),
                 "convention": "regulation (60-minute) goals",
                 "p_win_if_tied": base.p_win_if_tied,
                 "tied_games_2025_26": base.n_tied}))

    # ------------------------------------------------------------------ S1 offense
    for pct in cfg["sensitivity"]["percentages"]:
        scenarios.append(ScenarioSpec(
            scenario_id=f"S1_{pct:+.0%}".replace("+", "plus").replace("-", "minus"),
            name=f"Offense {pct:+.0%}, defense fixed", family="offense_sensitivity",
            lambda_gf=lgf0 * (1 + pct), lambda_ga=lga0,
            details={"offense_pct_change": pct, "defense_pct_change": 0.0,
                     "formula": "lambda_GF = lambda_GF0 * (1 + s), lambda_GA fixed"}))

    # ------------------------------------------------------------------ S2 defense
    for pct in cfg["sensitivity"]["percentages"]:
        scenarios.append(ScenarioSpec(
            scenario_id=f"S2_{pct:+.0%}".replace("+", "plus").replace("-", "minus"),
            name=f"Goals allowed {pct:+.0%}, offense fixed", family="defense_sensitivity",
            lambda_gf=lgf0, lambda_ga=lga0 * (1 + pct),
            details={"offense_pct_change": 0.0, "defense_pct_change": pct,
                     "formula": ("lambda_GA = lambda_GA0 * (1 + d); a negative change means "
                                 "fewer goals allowed (better defense)")}))

    # ------------------------------------------------------------------ S3 personnel
    by_id: dict[str, ScenarioSpec] = {}
    for sc in cfg["roster"]["scenarios"]:
        if sc.get("combines"):
            continue
        comps = sc["components"]
        if sc["type"] == "availability":
            net, trace = _availability_delta(comps)
            spec = ScenarioSpec(
                scenario_id=sc["id"], name=sc["name"], family=sc["family"],
                lambda_gf=lgf0 + net, lambda_ga=lga0,
                details={"type": "availability", "net_goals_per_game": round(net, 5),
                         "formula": ("lambda_GF = lambda_GF0 + prior_goals/prior_gp x "
                                     "(assumed_gp - prior_gp) x role_factor / 82"),
                         "components": trace,
                         "rationale": sc.get("rationale", "").strip(),
                         "roster_players_checked": int(len(roster))})
        elif sc["type"] == "offense":
            net, trace = _personnel_delta(comps)
            spec = ScenarioSpec(
                scenario_id=sc["id"], name=sc["name"], family=sc["family"],
                lambda_gf=lgf0 + net, lambda_ga=lga0,
                details={"type": "offense", "net_goals_per_game": round(net, 5),
                         "formula": ("lambda_GF = lambda_GF0 + (sum of incoming - outgoing "
                                     "per-team-game contributions)"),
                         "components": trace, "rationale": sc.get("rationale", "").strip(),
                         "roster_players_checked": int(len(roster))})
        else:  # goaltending / defense
            delta_sv = float(comps[0]["delta_team_save_pct"])
            delta_ga = delta_sv * shots_against_per_game
            spec = ScenarioSpec(
                scenario_id=sc["id"], name=sc["name"], family=sc["family"],
                lambda_gf=lgf0, lambda_ga=lga0 - delta_ga,
                details={"type": "defense", "delta_team_save_pct": delta_sv,
                         "shots_against_per_game": round(shots_against_per_game, 4),
                         "delta_goals_allowed_per_game": round(-delta_ga, 5),
                         "formula": ("delta_GA_per_game = delta_SV% x SA_per_game; "
                                     "lambda_GA = lambda_GA0 - delta_GA_per_game"),
                         "rationale": sc.get("rationale", "").strip()})
        spec.validate()
        by_id[spec.scenario_id] = spec
        scenarios.extend([spec])

    # ------------------------------------------------------------------ S4 combined
    for sc in cfg["roster"]["scenarios"]:
        if not sc.get("combines"):
            continue
        missing = [p for p in sc["combines"] if p not in by_id]
        if missing:
            raise ValueError(f"{sc['id']} combines unknown scenario ids: {missing}")
        parts = [by_id[p] for p in sc["combines"]]
        d_gf = sum(p.lambda_gf - lgf0 for p in parts)
        d_ga = sum(p.lambda_ga - lga0 for p in parts)
        spec = ScenarioSpec(
            scenario_id=sc["id"], name=sc["name"], family=sc["family"],
            lambda_gf=lgf0 + d_gf, lambda_ga=lga0 + d_ga,
            details={
                "combined_from": sc["combines"],
                "order_of_application": [
                    "1. Apply roster/offense terms to lambda_GF (lambda_GF0 + sum of changes)",
                    "2. Apply goaltending/defense terms to lambda_GA (lambda_GA0 + sum of changes)",
                ],
                "delta_gf_per_game": round(d_gf, 5),
                "delta_ga_per_game": round(d_ga, 5),
                "components": [{"scenario_id": p.scenario_id,
                                "lambda_gf": round(p.lambda_gf, 5),
                                "lambda_ga": round(p.lambda_ga, 5),
                                "delta_gf": round(p.lambda_gf - lgf0, 5),
                                "delta_ga": round(p.lambda_ga - lga0, 5)} for p in parts],
                "label": ("conditional scenario built from separately evaluated effects; "
                          "not a proven best prediction"),
            })
        spec.validate()
        scenarios.append(spec)

    return scenarios
