# QA results — Dallas Stars 2026-27 forecasting model

Owner: Ankit Karki . Evidence in `outputs/qa/`. This document reports what was actually run
and what it showed. The team must review and sign off separately.

## 1. Commands run, and results

| Command                                                            | Result                                                                 | Evidence                                                                   |
| ------------------------------------------------------------------ | ---------------------------------------------------------------------- | -------------------------------------------------------------------------- |
| `python -m stars_forecast collect-data`                          | 188 raw source files cached; datasets A–G written                     | `data/raw/source_manifest.json`, `data/processed/collect_summary.json` |
| `python -m stars_forecast validate-data`                         | **30/30 checks passed** (exit 0)                                 | `outputs/qa/data-validation.json`                                        |
| `python -m stars_forecast data-report`                           | `docs/data-report.md` regenerated                                    | `docs/data-report.md`                                                    |
| `python -m stars_forecast run-all --n-seasons 10000 --seed 3315` | 18 scenarios x 10,000 seasons, 8 figures, 20 tables, backtest (exit 0) | `outputs/tables/`, `outputs/figures/`                                  |
| `python -m pytest --junitxml=outputs/qa/test-results.xml`        | **64 passed**, 0 failed, 0 skipped                               | `outputs/qa/test-results.xml`                                            |

## 2. Data QA (automated, `validate-data`)

30 checks across datasets A–G plus the cross-source check. The ones that carry scientific weight:

1. **Season completeness** — 82 games in 2025-26, 82 in 2024-25, unique game IDs, all regular season.
2. **Record arithmetic** — W + regulation L + OTL = 82 and points = 2W + OTL for both seasons, and the
   result equals the official total (112 for 2025-26, 106 for 2024-25).
3. **Goal convention** — regulation-only, final-hockey and displayed sums are all computed and only
   one matches the official NHL totals: **final hockey (273/222)**. This is the check that prevents a
   silent shootout-goal contamination of the Poisson fit.
4. **Shots and special teams** — per-game x 82 reproduces the game log exactly; 71/248 power-play
   goals reproduces the published 28.63 %.
5. **Goalie vs team totals** — goalie goals against are 13 lower than team goals against, and goalie
   shots against are 13 lower than team shots against. The two gaps agree, which is the signature of
   empty-net goals; the check requires agreement instead of forcing equality.
6. **Historical standings** — 5 seasons x 8 Central teams, unique ranks 1–8, points = 2W + OTL.
7. **Leakage guard** — no 2026-27 game result exists in any processed dataset or standings table.
8. **Cross-source reconciliation** — Hockey-Reference game logs (82 games each season) reproduce our
   displayed sums exactly for both seasons.

## 3. Model QA (pytest, 64 tests)

| Group                           | Tests                | What they prove                                                                                                                                                   |
| ------------------------------- | -------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Data contracts                  | 19                   | Regular-season filtering, season counts, unique IDs, result categories, points identities, convention reconciliation, no leakage                                  |
| Model core                      | 17                   | Score recovery from hand-built fixtures, 82-game arithmetic, points = 2W + OTL, OT/SO goal-differential rules, seed reproducibility                               |
| Scenarios                       | 11                   | Family coverage, isolation of offense vs defense, normalization units, availability mechanism, neutrality of an equal replacement, rejection of impossible inputs |
| Standings + backtest + pipeline | 9                    | Threshold arithmetic, `>=` tie rule, exclusion of historical Dallas, train/evaluation separation, artifact consistency                                          |
| Numerical spot checks           | 8 (inside the above) | Monte Carlo vs analytic expectation, monotonic sensitivity                                                                                                        |

### 3.1 Independent numerical checks (not just internal consistency)

- **Analytic vs Monte Carlo.** An analytic expected-points calculation (truncated bivariate Poisson
  plus the tied-game adjustment) is compared to the simulated mean for all 18 scenarios:
  `mc_minus_analytic` is within ±0.35 points for every scenario (asserted at < 1.2 in tests), e.g.
  S0 analytic 105.60 vs simulated 105.65.
- **Seed reproducibility.** Two runs with seed 3315 produce bit-identical season arrays; seed 3316
  produces different ones.
- **Monotonicity with common random numbers.** Points increase with offense in the S1 grid and
  decrease as goals allowed rise in the S2 grid. Because the same random stream is reused, the
  ordering is not a Monte Carlo artifact.
- **Hand-checked fixture.** A 4-game synthetic log (REG win, REG loss, OT win, SO loss) recovers
  regulation means 2.00 / 2.25, final-hockey totals that exclude the shootout goal, and 5 points.
  Synthetic data appears only here, in tests.

## 4. Defects found and fixed (error log)

| # | Defect                                                                                                        | Detection                                                               | Fix                                                                                    | Effect                                                                      |
| - | ------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------- | -------------------------------------------------------------------------------------- | --------------------------------------------------------------------------- |
| 1 | Standings rank logic counted rivals *below* the simulated total, so a good team was ranked 8th              | Inspecting the first scenario JSON (mean rank 6.3 for a 105-point team) | Compare rivals *above* the total; best = strictly above + 1, worst = at-or-above + 1 | Mean rank interval corrected to 2.53–2.65; top-three rank range 0.75–0.78 |
| 2 | Availability scenario credited Rantanen's full 22 goals although he is already in the baseline (double count) | Reviewing `details.components` after the first run                    | Availability now adds `rate x (assumed_gp - prior_gp)`, i.e. the 18 missing games    | S3a fell from +7.1 to +1.7 points, which is the defensible value            |
| 3 | Goalie reconciliation demanded goalie GA equal team GA                                                        | A false-fail in `validate-data`                                       | Require the GA gap to equal the shots-against gap instead                              | Check now verifies the empty-net explanation rather than forbidding it      |
| 4 | Hockey-Reference comparison expected official (final-hockey) totals                                           | Cross-check returned 279/226 vs 273/222                                 | Compare HR's box-score sums to our *displayed* sums, and say so                      | Cross-check passes on like-for-like conventions                             |
| 5 | Hockey-Reference tables sit inside HTML comments, so parsing returned nothing                                 | `available: false` in the first cross-check attempt                   | Strip comment markers before parsing (raw file untouched)                              | Cross-check available for both seasons                                      |
| 6 | Sensitivity figure plotted the 0 % point last, drawing a kink                                                 | Visual inspection of fig4                                               | Sort the percentage grid before plotting                                               | Curve is monotone as intended                                               |

Defects 1 and 2 changed reported numbers. They were found and both are recorded in `docs/model-decisions.md`.

## 5. Independent spot checks performed by hand

- 2 x 50 wins + 12 OTL = 112 points — matches the official table.
- 267 regulation GF + 6 overtime goals = 273 final-hockey GF — matches both the official total and the
  Hockey-Reference sum minus its shootout increment.
- 22/64 x 18 / 82 = 0.0754 goals per game for the availability scenario; +0.0754 goals per game maps
  to roughly +1.7 simulated points, consistent with the S1 grid's ~+0.73 points per 1 % of offense.
- 0.010 x 26.1585 = 0.2616 goals allowed per game for the goaltending scenario.

## 6. Remaining limitations (not defects)

- One backtest is not evidence of general forecasting accuracy.
- The tied-game probability and the five-season Central sample are both small.
- Independence of goals for and against is an explicit approximation.
- The goaltending scenario treats empty-net goals as unaffected by save percentage, which biases it
  toward zero.
- Monte Carlo intervals describe simulation noise conditional on the model; model error is larger.
