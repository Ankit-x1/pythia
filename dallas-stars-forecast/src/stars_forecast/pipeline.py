"""End-to-end computational pipeline: diagnostics -> scenarios -> backtest -> figures.

`run_all` reads only local validated inputs; it never needs network access.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd

from . import MODEL_VERSION, __version__
from .backtest import run_backtest
from .config import load_config
from .figures import (fig_backtest, fig_central, fig_data_overview, fig_goal_frequencies,
                      fig_personnel, fig_point_distributions, fig_sensitivity_curves)
from .model import (ScenarioSpec, expected_points, fit_rates, proposal_rates,
                    run_diagnostics, simulate_seasons, summarize)
from .paths import PROCESSED, QA, TABLES, rel
from .scenarios import build_scenarios
from .standings import points_rank_table, season_thresholds, translate
from .validate import load_validation


class InputError(RuntimeError):
    """Raised when the validated scientific inputs are not usable."""


def _sha256(path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_inputs() -> dict[str, Any]:
    """Load validated processed inputs or fail loudly."""
    validation = load_validation()
    if not validation.get("all_passed"):
        failed = [c["check"] for c in validation["checks"] if not c["passed"]]
        raise InputError(f"data validation failed, refusing to run the analysis: {failed}")

    required = [
        "game_log_dal_2025_26.csv", "game_log_dal_2024_25.csv",
        "team_totals_dal_2025_26.csv", "team_totals_dal_2024_25.csv",
        "central_standings_2021_2026.csv", "skaters_dal_2025_26.csv",
        "goalies_dal_2025_26.csv", "roster_dal_2026_27.csv",
        "arrivals_dal_2026_27_prior_season.csv",
    ]
    missing = [f for f in required if not (PROCESSED / f).exists()]
    if missing:
        raise InputError(f"missing processed inputs: {missing}. Run collect-data first.")

    return {
        "validation": validation,
        "log26": pd.read_csv(PROCESSED / "game_log_dal_2025_26.csv"),
        "log25": pd.read_csv(PROCESSED / "game_log_dal_2024_25.csv"),
        "totals26": pd.read_csv(PROCESSED / "team_totals_dal_2025_26.csv").iloc[0],
        "totals25": pd.read_csv(PROCESSED / "team_totals_dal_2024_25.csv").iloc[0],
        "standings": pd.read_csv(PROCESSED / "central_standings_2021_2026.csv"),
        "skaters": pd.read_csv(PROCESSED / "skaters_dal_2025_26.csv"),
        "goalies": pd.read_csv(PROCESSED / "goalies_dal_2025_26.csv"),
        "roster": pd.read_csv(PROCESSED / "roster_dal_2026_27.csv"),
        "arrivals": pd.read_csv(PROCESSED / "arrivals_dal_2026_27_prior_season.csv"),
    }


def run_all(n_seasons: int | None = None, seed: int | None = None) -> dict[str, Any]:
    cfg = load_config()
    n_seasons = int(n_seasons or cfg["simulation"]["n_seasons"])
    seed = int(seed if seed is not None else cfg["simulation"]["seed"])
    thresholds = [int(t) for t in cfg["simulation"]["point_thresholds"]]
    top_rank = int(cfg["simulation"]["top_rank_threshold"])
    if n_seasons < 1000:
        raise InputError("n_seasons must be >= 1000 for a usable distribution")

    data = load_inputs()
    log26, totals26 = data["log26"], data["totals26"]

    # ---------------------------------------------------------------- diagnostics
    base = fit_rates(log26)
    diagnostics = run_diagnostics(log26)
    diagnostics["fitted_rates"] = base.as_dict()
    diagnostics["proposal_rate_comparison"] = {
        **proposal_rates(totals26),
        "regulation_based_lambda_gf": round(base.lambda_gf, 5),
        "regulation_based_lambda_ga": round(base.lambda_ga, 5),
        "difference_gf": round(proposal_rates(totals26)["proposal_lambda_gf_final_hockey"]
                               - base.lambda_gf, 5),
        "difference_ga": round(proposal_rates(totals26)["proposal_lambda_ga_final_hockey"]
                               - base.lambda_ga, 5),
        "explanation": ("The proposal divides official season totals (which include overtime "
                        "goals) by 82. The simulation is regulation-based, so it uses the mean "
                        "of 60-minute goals. Both are reported; the regulation version is used "
                        "for the final run."),
    }
    (TABLES / "diagnostics.json").write_text(json.dumps(diagnostics, indent=2) + "\n",
                                             encoding="utf-8")

    # ---------------------------------------------------------------- scenarios
    specs = build_scenarios(cfg, base, totals26, data["roster"])
    standings = data["standings"]
    thresholds_hist = season_thresholds(standings, top_rank)
    results: dict[str, dict[str, Any]] = {}

    for spec in specs:
        samples = simulate_seasons(spec, base, n_seasons=n_seasons, seed=seed)
        summary = summarize(samples, thresholds)
        hist = translate(samples["points"], standings, top_rank)
        analytic = expected_points(base, spec.lambda_gf, spec.lambda_ga)
        payload = {
            "scenario_id": spec.scenario_id,
            "name": spec.name,
            "family": spec.family,
            "lambda_gf": round(spec.lambda_gf, 5),
            "lambda_ga": round(spec.lambda_ga, 5),
            "details": spec.details,
            "summary": summary,
            "historical_central": hist,
            "analytic_expected_points": round(analytic, 3),
            "mc_minus_analytic": round(summary["mean_points"] - analytic, 4),
            "n_seasons": n_seasons,
            "seed": seed,
        }
        results[spec.scenario_id] = {**payload, "samples": samples}
        (TABLES / f"scenario_{spec.scenario_id}.json").write_text(
            json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        np.savez_compressed(TABLES / f"samples_{spec.scenario_id}.npz", **samples)

    # ---------------------------------------------------------------- deltas
    base_summary = results["S0"]["summary"]
    for sid, res in results.items():
        s = res["summary"]
        res["difference_from_baseline"] = {
            "delta_mean_points": round(s["mean_points"] - base_summary["mean_points"], 3),
            "delta_median_points": round(s["median_points"] - base_summary["median_points"], 3),
            "delta_mean_wins": round(s["mean_wins"] - base_summary["mean_wins"], 3),
            "delta_mean_ot_losses": round(s["mean_ot_losses"] - base_summary["mean_ot_losses"], 3),
            "delta_prob_top3_point_level": round(
                res["historical_central"]["prob_meets_third_place_points"]
                - results["S0"]["historical_central"]["prob_meets_third_place_points"], 4),
            "delta_threshold_probs": {
                str(t): round(s[f"prob_at_least_{t}_points"]
                              - base_summary[f"prob_at_least_{t}_points"], 4)
                for t in thresholds},
        }

    # ---------------------------------------------------------------- summary table
    rows = []
    for sid, res in results.items():
        s, h = res["summary"], res["historical_central"]
        rows.append({
            "scenario_id": sid, "name": res["name"], "family": res["family"],
            "lambda_gf": res["lambda_gf"], "lambda_ga": res["lambda_ga"],
            "mean_points": s["mean_points"], "median_points": s["median_points"],
            "sd_points": s["sd_points"],
            "interval_80_low": s["interval_80"][0], "interval_80_high": s["interval_80"][1],
            "interval_95_low": s["interval_95"][0], "interval_95_high": s["interval_95"][1],
            "mean_wins": s["mean_wins"], "mean_regulation_losses": s["mean_regulation_losses"],
            "mean_ot_losses": s["mean_ot_losses"],
            "mean_goal_differential": s["mean_final_hockey_goal_differential"],
            **{f"prob_{t}": s[f"prob_at_least_{t}_points"] for t in thresholds},
            "prob_top3_point_level": h["prob_meets_third_place_points"],
            "prob_top3_rank_low": h["prob_top3_rank_range"][0],
            "prob_top3_rank_high": h["prob_top3_rank_range"][1],
            "mean_division_rank_low": h["mean_division_rank_range"][0],
            "mean_division_rank_high": h["mean_division_rank_range"][1],
            "delta_mean_points_vs_baseline": res["difference_from_baseline"]["delta_mean_points"],
        })
    table = pd.DataFrame(rows)
    table.to_csv(TABLES / "scenario_summary.csv", index=False)

    # ---------------------------------------------------------------- backtest
    backtest = run_backtest(data["log25"], log26, totals26, n_seasons, seed, thresholds)
    bt_samples = backtest["_samples"]
    np.savez_compressed(TABLES / "backtest_samples.npz", **bt_samples)
    backtest_out = {k: v for k, v in backtest.items() if k != "_samples"}
    (TABLES / "backtest.json").write_text(json.dumps(backtest_out, indent=2) + "\n",
                                          encoding="utf-8")

    # ---------------------------------------------------------------- figures
    figs = [
        fig_goal_frequencies(log26, base),
        fig_point_distributions(results, ["S0"] + [s.scenario_id for s in specs if s.family ==
                                                   "offense_sensitivity"],
                                "S1 offense sensitivity: simulated point distributions",
                                "fig2_offense_point_distributions.png",
                                "10,000 simulated 82-game seasons per scenario, common random "
                                "numbers. Source: 2025-26 regulation rates."),
        fig_point_distributions(results, ["S0"] + [s.scenario_id for s in specs if s.family ==
                                                   "defense_sensitivity"],
                                "S2 goals-allowed sensitivity: simulated point distributions",
                                "fig3_defense_point_distributions.png",
                                "10,000 simulated 82-game seasons per scenario, common random "
                                "numbers. A negative change means fewer goals allowed."),
        fig_sensitivity_curves(results, cfg),
        fig_personnel(results),
        fig_central(standings, thresholds_hist, base_summary["mean_points"]),
        fig_backtest({**backtest, "_samples": bt_samples}),
        fig_data_overview(log26, data["log25"]),
    ]
    (TABLES / "points_rank_table.csv").write_text(
        points_rank_table(standings).to_csv(index=False), encoding="utf-8")
    (TABLES / "central_thresholds.json").write_text(
        json.dumps(thresholds_hist, indent=2) + "\n", encoding="utf-8")

    # ---------------------------------------------------------------- run manifest
    inputs = ["game_log_dal_2025_26.csv", "game_log_dal_2024_25.csv",
              "team_totals_dal_2025_26.csv", "team_totals_dal_2024_25.csv",
              "central_standings_2021_2026.csv", "skaters_dal_2025_26.csv",
              "goalies_dal_2025_26.csv", "roster_dal_2026_27.csv",
              "arrivals_dal_2026_27_prior_season.csv"]
    manifest = {
        "model_version": MODEL_VERSION,
        "package_version": __version__,
        "config_version": cfg["version"],
        "n_seasons": n_seasons,
        "seed": seed,
        "games_per_season": cfg["simulation"]["games_per_season"],
        "baseline_rates": base.as_dict(),
        "scenarios": {s.scenario_id: {"lambda_gf": round(s.lambda_gf, 5),
                                      "lambda_ga": round(s.lambda_ga, 5),
                                      "family": s.family} for s in specs},
        "data_checksums": {f: _sha256(PROCESSED / f) for f in inputs},
        "validation": {"all_passed": data["validation"]["all_passed"],
                       "n_checks": data["validation"]["n_checks"]},
        "figures": [rel(p) for p in figs],
        "tables": sorted(rel(p) for p in TABLES.glob("*.csv"))
                  + sorted(rel(p) for p in TABLES.glob("*.json")),
        "reproducibility_note": ("Numerical outputs depend on seed, n_seasons, config version, "
                                 "model version and the input checksums above. Run timestamps "
                                 "are metadata only and are not part of the numerical check."),
    }
    (TABLES / "run_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n",
                                             encoding="utf-8")
    (TABLES / "run_metadata.json").write_text(json.dumps({
        "run_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "python": sys.version.split()[0],
        "packages": _versions(),
    }, indent=2) + "\n", encoding="utf-8")

    from .summary import write_results_summary
    write_results_summary(results, diagnostics, backtest_out, table, manifest)

    return {
        "ok": True,
        "n_seasons": n_seasons,
        "seed": seed,
        "baseline_lambda_gf": round(base.lambda_gf, 4),
        "baseline_lambda_ga": round(base.lambda_ga, 4),
        "p_win_if_tied": round(base.p_win_if_tied, 4),
        "diagnostics_overdispersed_gf": diagnostics["goals_for"]["overdispersed_at_5pct"],
        "diagnostics_overdispersed_ga": diagnostics["goals_against"]["overdispersed_at_5pct"],
        "backtest_abs_error": backtest_out["error"]["absolute_error_of_mean_points"],
        "figures": [rel(p) for p in figs],
        "summary_table": rel(TABLES / "scenario_summary.csv"),
        "scenarios": {sid: {"name": r["name"], "mean_points": r["summary"]["mean_points"]}
                      for sid, r in results.items()},
        "_results": results,
        "_backtest": backtest_out,
    }


def _versions() -> dict[str, str]:
    import matplotlib
    import scipy
    return {"numpy": np.__version__, "pandas": pd.__version__,
            "scipy": scipy.__version__, "matplotlib": matplotlib.__version__}
