# Results summary (computational evidence)

_Model `poisson-mc-v1`, config v3, 10,000 seasons per scenario, seed 3315._

This file connects the generated artifacts to the main findings. It is not the final academic report and it is not the data report.

## 1. Model inputs (verified data only)

- Regulation goals for: mean **3.256** per game
- Regulation goals against: mean **2.610** per game
- P(Dallas wins | tied after regulation), 2025-26: **0.500** (12 of 24 tied games)
- Overtime share of tied games: 0.583

The proposal's totals/82 rates are 3.329 GF and 2.707 GA. Those are final-hockey rates (they include overtime goals); the simulation uses the regulation means above. Both are reported in `outputs/tables/diagnostics.json`.

## 2. Poisson adequacy

- **regulation goals for**: variance/mean = 1.015, overdispersion test p = 0.442 (no material overdispersion); chi-square GOF p = 0.682 with 6 pooled bins; negative binomial preferred by AIC: no.
- **regulation goals against**: variance/mean = 0.944, overdispersion test p = 0.622 (no material overdispersion); chi-square GOF p = 0.950 with 6 pooled bins; negative binomial preferred by AIC: no.

The Poisson benchmark is retained for every reported scenario; the negative-binomial AIC comparison is recorded as a documented diagnostic, not as a silent model change.

## 3. Baseline season (S0)

- Mean points **105.7** (median 106), 80% interval **95-116**, 95% interval **89-122**
- Mean record: 49.5 W / 25.8 regulation L / 6.7 OTL
- Mean final-hockey goal differential: +53.1
- P(>=100 points) = 77.7%, P(>=105) = 55.9%, P(>=110) = 32.0%
- Historical top-three Central point-level probability: **57.7%**; top-three rank range 75.4%-78.1%

## 4. Sensitivity

- Offense is roughly linear in points: Offense -15%, defense fixed gives 93.5 pts and Offense +15%, defense fixed gives 116.2 pts versus 105.7 at baseline (about 0.70 points per 1% of offense).
- Defense moves points faster per percent: Goals allowed +15%, offense fixed gives 95.2 pts and Goals allowed -15%, offense fixed gives 116.3 pts.
- Full grid: `outputs/tables/scenario_summary.csv`, `outputs/figures/fig4_sensitivity_curves.png`.

## 5. Personnel, availability and goaltending (S3) and combined case (S4)

- **S3a — Rantanen full-season availability**: 107.4 pts (+1.7 vs S0), lambda_GF 3.332, lambda_GA 2.610. Top-three point-level probability 64.8%.
- **S3b — Fourth-line / depth turnover**: 105.4 pts (-0.3 vs S0), lambda_GF 3.242, lambda_GA 2.610. Top-three point-level probability 56.3%.
- **S3c — Goaltending save-percentage shift**: 112.7 pts (+7.1 vs S0), lambda_GF 3.256, lambda_GA 2.348. Top-three point-level probability 84.8%.
- **S3d — Goaltending regression**: 98.8 pts (-6.9 vs S0), lambda_GF 3.256, lambda_GA 2.871. Top-three point-level probability 27.6%.
- **S4 — Combined case: Rantanen full season + 0.010 save-pct gain**: 114.3 pts (+8.7 vs S0), lambda_GF 3.332, lambda_GA 2.348. Top-three point-level probability 88.8%.

Every personnel number traces to a verified player row; the normalization and role factors are in `config/scenarios.yaml` and repeated in each scenario JSON under `details.components`.

## 6. Backtest (2024-25 -> 2025-26, single isolated pass)

- Frozen 2024-25 rates: lambda_GF 3.268, lambda_GA 2.659, p(tie win) 0.600
- Forecast mean 105.9 pts vs actual **112** pts; absolute error of the mean **6.1** points
- Actual result inside the 80% interval: **True**; inside the 95% interval: **True**; the actual season sits at the 78th percentile of the forecast
- Predicted record [50.29, 26.37, 5.34] vs actual [50, 20, 12]
- One backtest does not establish general forecasting accuracy. No parameter was tuned after the target season was opened.

## 7. Figures

- `outputs\figures\fig1_goal_frequencies.png`
- `outputs\figures\fig2_offense_point_distributions.png`
- `outputs\figures\fig3_defense_point_distributions.png`
- `outputs\figures\fig4_sensitivity_curves.png`
- `outputs\figures\fig5_personnel_comparison.png`
- `outputs\figures\fig6_central_points_vs_rank.png`
- `outputs\figures\fig7_backtest.png`
- `outputs\figures\fig8_data_overview.png`

## 8. Limitations

- Goals for and against are treated as independent Poisson draws; NHL game state makes them weakly dependent.
- One constant rate per side ignores opponent strength, home/away, injuries, schedule density and empty-net effects.
- The tied-game probability is estimated from a single season, so it carries wide sampling error.
- Historical Central translation rests on five seasons and reports rank intervals because historical ties have no recorded tiebreaker.
- Monte Carlo intervals are conditional on the model; they quantify simulation noise, not model error.
