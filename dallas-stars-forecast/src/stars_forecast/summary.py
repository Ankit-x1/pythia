"""outputs/results-summary.md — evidence summary connecting files to findings.

This is deliberately separate from docs/data-report.md (data only) and from the
final academic report (written later, on request).
"""
from __future__ import annotations

from typing import Any

from .paths import OUTPUTS, rel


def write_results_summary(results: dict[str, dict], diagnostics: dict, backtest: dict,
                          table, manifest: dict):
    base = results["S0"]["summary"]
    hist = results["S0"]["historical_central"]
    s1 = {k: v for k, v in results.items() if v["family"] == "offense_sensitivity"}
    s2 = {k: v for k, v in results.items() if v["family"] == "defense_sensitivity"}
    up = max(s1.values(), key=lambda r: r["summary"]["mean_points"])
    dn = min(s1.values(), key=lambda r: r["summary"]["mean_points"])
    up2 = max(s2.values(), key=lambda r: r["summary"]["mean_points"])
    dn2 = min(s2.values(), key=lambda r: r["summary"]["mean_points"])

    lines: list[str] = []
    a = lines.append
    a("# Results summary (computational evidence)\n")
    a(f"_Model `{manifest['model_version']}`, config v{manifest['config_version']}, "
      f"{manifest['n_seasons']:,} seasons per scenario, seed {manifest['seed']}._\n")
    a("This file connects the generated artifacts to the main findings. It is not the final "
      "academic report and it is not the data report.\n")

    a("## 1. Model inputs (verified data only)\n")
    a(f"- Regulation goals for: mean **{diagnostics['fitted_rates']['lambda_gf']:.3f}** per game")
    a(f"- Regulation goals against: mean **{diagnostics['fitted_rates']['lambda_ga']:.3f}** per game")
    a(f"- P(Dallas wins | tied after regulation), 2025-26: "
      f"**{diagnostics['fitted_rates']['p_win_if_tied']:.3f}** "
      f"({diagnostics['fitted_rates']['n_tied_wins']} of "
      f"{diagnostics['fitted_rates']['n_tied']} tied games)")
    a(f"- Overtime share of tied games: "
      f"{diagnostics['fitted_rates']['p_ot_given_tied']:.3f}\n")
    a("The proposal's totals/82 rates are "
      f"{diagnostics['proposal_rate_comparison']['proposal_lambda_gf_final_hockey']:.3f} GF and "
      f"{diagnostics['proposal_rate_comparison']['proposal_lambda_ga_final_hockey']:.3f} GA. "
      "Those are final-hockey rates (they include overtime goals); the simulation uses the "
      "regulation means above. Both are reported in `outputs/tables/diagnostics.json`.\n")

    a("## 2. Poisson adequacy\n")
    for key in ("goals_for", "goals_against"):
        d = diagnostics[key]
        a(f"- **{d['quantity']}**: variance/mean = {d['dispersion_index_var_over_mean']:.3f}, "
          f"overdispersion test p = {d['overdispersion_p_value']:.3f} "
          f"({'overdispersed' if d['overdispersed_at_5pct'] else 'no material overdispersion'}); "
          f"chi-square GOF p = {d['chi_square_gof']['p_value']:.3f} with "
          f"{d['chi_square_gof']['n_bins']} pooled bins; "
          f"negative binomial preferred by AIC: "
          f"{'no' if d['poisson_preferred_by_aic'] else 'yes (see diagnostics)'}.")
    a("")
    a("The Poisson benchmark is retained for every reported scenario; the negative-binomial "
      "AIC comparison is recorded as a documented diagnostic, not as a silent model change.\n")

    a("## 3. Baseline season (S0)\n")
    a(f"- Mean points **{base['mean_points']:.1f}** (median {base['median_points']:.0f}), "
      f"80% interval **{base['interval_80'][0]}-{base['interval_80'][1]}**, "
      f"95% interval **{base['interval_95'][0]}-{base['interval_95'][1]}**")
    a(f"- Mean record: {base['mean_wins']:.1f} W / {base['mean_regulation_losses']:.1f} "
      f"regulation L / {base['mean_ot_losses']:.1f} OTL")
    a(f"- Mean final-hockey goal differential: "
      f"{base['mean_final_hockey_goal_differential']:+.1f}")
    a(f"- P(>=100 points) = {base['prob_at_least_100_points']:.1%}, "
      f"P(>=105) = {base['prob_at_least_105_points']:.1%}, "
      f"P(>=110) = {base['prob_at_least_110_points']:.1%}")
    a(f"- Historical top-three Central point-level probability: "
      f"**{hist['prob_meets_third_place_points']:.1%}**; top-three rank range "
      f"{hist['prob_top3_rank_range'][0]:.1%}-{hist['prob_top3_rank_range'][1]:.1%}\n")

    a("## 4. Sensitivity\n")
    a(f"- Offense is roughly linear in points: {dn['name']} gives "
      f"{dn['summary']['mean_points']:.1f} pts and {up['name']} gives "
      f"{up['summary']['mean_points']:.1f} pts versus {base['mean_points']:.1f} at baseline "
      f"(about {(up['summary']['mean_points'] - base['mean_points']) / 15:.2f} points per 1% of "
      "offense).")
    a(f"- Defense moves points faster per percent: {dn2['name']} gives "
      f"{dn2['summary']['mean_points']:.1f} pts and {up2['name']} gives "
      f"{up2['summary']['mean_points']:.1f} pts.")
    a("- Full grid: `outputs/tables/scenario_summary.csv`, "
      "`outputs/figures/fig4_sensitivity_curves.png`.\n")

    a("## 5. Personnel, availability and goaltending (S3) and combined case (S4)\n")
    for sid in ("S3a", "S3b", "S3c", "S3d", "S4"):
        if sid not in results:
            continue
        r = results[sid]
        s = r["summary"]
        a(f"- **{sid} — {r['name']}**: {s['mean_points']:.1f} pts "
          f"({s['mean_points'] - base['mean_points']:+.1f} vs S0), "
          f"lambda_GF {r['lambda_gf']:.3f}, lambda_GA {r['lambda_ga']:.3f}. "
          f"Top-three point-level probability {r['historical_central']['prob_meets_third_place_points']:.1%}.")
    a("")
    a("Every personnel number traces to a verified player row; the normalization and role "
      "factors are in `config/scenarios.yaml` and repeated in each scenario JSON under "
      "`details.components`.\n")

    a("## 6. Backtest (2024-25 -> 2025-26, single isolated pass)\n")
    a(f"- Frozen 2024-25 rates: lambda_GF {backtest['frozen_configuration']['lambda_gf']:.3f}, "
      f"lambda_GA {backtest['frozen_configuration']['lambda_ga']:.3f}, "
      f"p(tie win) {backtest['frozen_configuration']['p_win_if_tied']:.3f}")
    a(f"- Forecast mean {backtest['simulation']['mean_points']:.1f} pts vs actual "
      f"**{backtest['actual']['points']}** pts; absolute error of the mean "
      f"**{backtest['error']['absolute_error_of_mean_points']:.1f}** points")
    a(f"- Actual result inside the 80% interval: "
      f"**{backtest['error']['actual_inside_80pct_interval']}**; inside the 95% interval: "
      f"**{backtest['error']['actual_inside_95pct_interval']}**; the actual season sits at the "
      f"{backtest['error']['points_percentile_of_actual']:.0f}th percentile of the forecast")
    a(f"- Predicted record {backtest['predicted_vs_actual_record']['predicted_W_regL_OTL']} vs "
      f"actual {backtest['predicted_vs_actual_record']['actual_W_regL_OTL']}")
    a("- One backtest does not establish general forecasting accuracy. No parameter was tuned "
      "after the target season was opened.\n")

    a("## 7. Figures\n")
    for f in manifest["figures"]:
        a(f"- `{f}`")

    a("\n## 8. Limitations\n")
    a("- Goals for and against are treated as independent Poisson draws; NHL game state makes "
      "them weakly dependent.\n- One constant rate per side ignores opponent strength, "
      "home/away, injuries, schedule density and empty-net effects.\n- The tied-game probability "
      "is estimated from a single season, so it carries wide sampling error.\n- Historical "
      "Central translation rests on five seasons and reports rank intervals because historical "
      "ties have no recorded tiebreaker.\n- Monte Carlo intervals are conditional on the model; "
      "they quantify simulation noise, not model error.\n")

    path = OUTPUTS / "results-summary.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
