# Model decisions and change log

Every entry records a decision, its justification, and whether instructor review is needed.
Formulas use `lambda_GF` (Dallas goals per game) and `lambda_GA` (goals allowed per game).

---

## 1. Regulation-based rates (needs instructor review)

The proposal defines `lambda_GF = 273/82 = 3.329` and `lambda_GA = 222/82 = 2.707` from official
season totals, but calls the simulated goal counts *regulation* goals. Official season totals include
overtime goals, so totals/82 is a **final-hockey** rate, not a 60-minute rate.

Verified conventions for 2025-26 (all from the cleaned game log, reconciled in
`outputs/qa/data-validation.json`):

| Quantity                             | Goals for | Goals against |
| ------------------------------------ | --------- | ------------- |
| Regulation only (60 min)             | 267       | 214           |
| Final hockey (reg + OT)              | 273       | 222           |
| Displayed (incl. shootout increment) | 279       | 226           |

The official NHL totals (273/222) match the **final hockey** row exactly, so the shootout
increment is excluded from official totals.

**Decision.** The simulation is regulation-based, so the final run uses

```
lambda_GF = mean(regulation goals for per game)  = 3.2561
lambda_GA = mean(regulation goals against per game) = 2.6098
```

and the tied-game mechanism then adds overtime/shootout resolution. This is the internally
consistent choice: a Poisson draw represents 60 minutes, so its mean must be the 60-minute mean.
Using 3.329 as a 60-minute mean would double-count overtime scoring.

Both rate sets are reported side by side (`outputs/tables/diagnostics.json → proposal_rate_comparison`). 

## 2. Three goal definitions are preserved, never merged

`game_log_dal_*.csv` keeps `goals_for_reg` / `goals_against_reg`, `..._final_hockey` and
`..._displayed`, plus `goals_for_ot`, `goals_against_ot` and the shootout columns. Cleaning never
"fixes" one convention into another. Overtime vs shootout classification comes from the period type
in the period-by-period linescore, and is cross-checked against the game outcome period type.

## 3. Tied-game resolution is empirical

For each tied-after-regulation game the model needs `p = P(Dallas wins | tied after 60 minutes)`.
From 2025-26: 24 tied games, Dallas won 12 → `p = 0.500`; 14 of the 24 went to overtime
(`p_ot_given_tied = 0.583`). This is a single-season estimate with wide sampling error and is
reported as such. A season with zero tied games raises an error rather than defaulting to 0.5.

Points: 2 for any win, 1 for an OT/SO loss, 0 for a regulation loss. A season is 82 games.

## 4. Independent Poisson is retained

Diagnostics for 2025-26 regulation goals:

|               | variance/mean | overdispersion test p | chi-square GOF p (pooled bins) | NB better by AIC?                  |
| ------------- | ------------- | --------------------- | ------------------------------ | ---------------------------------- |
| Goals for     | 1.015         | 0.442                 | 0.682                          | no (Poisson AIC 326.7 vs NB 328.7) |
| Goals against | 0.944         | 0.622                 | 0.950                          | no (Poisson 301.7 vs NB 303.7)     |

No material overdispersion. The Poisson benchmark therefore stands and no negative-binomial or
segmented model is adopted; the NB comparison is recorded as a diagnostic only. Chi-square bins are
pooled from the right so that every expected count is at least 5, and the degrees of freedom account
for the estimated mean.

*Acknowledged approximation:* goals for and against are treated as independent draws even though
game state couples them.

## 5. Scenario definitions

- **S0 Baseline:** the two fitted regulation rates, unchanged.
- **S1 Offense:** `lambda_GF(s) = lambda_GF0 (1 + s)` for `s ∈ {-15, -10, -5, +5, +10, +15}%`,
  `lambda_GA` fixed.
- **S2 Defense:** `lambda_GA(d) = lambda_GA0 (1 + d)` for the same grid, `lambda_GF` fixed.
  A negative `d` means *fewer* goals allowed.
- **S3 personnel** uses one documented normalization:

  ```
  projected_goals = prior_goals / prior_gp * assumed_gp * role_factor
  per_team_game   = projected_goals / 82
  lambda_GF_new   = lambda_GF0 + Σ(incoming) - Σ(outgoing)
  ```

  Bases: `prior_goals` and `prior_gp` are verified 2025-26 figures (Dallas-attributed for returning
  players, full-season for arrivals). Assists are never counted as goals; a defenseman's offensive
  points are never treated as defensive value. Every number is reproduced in each scenario JSON
  under `details.components`.
- **S3a — availability (a distinct mechanism).** Rantanen is already *inside* the 2025-26 baseline,
  so crediting all 22 of his goals would double count. Availability adds only the missing games:

  ```
  delta_per_game = prior_goals / prior_gp * (assumed_gp - prior_gp) * role_factor / 82
                 = 22/64 * 18 * 1.0 / 82 = +0.0754 goals per game
  ```

  *Defect found and fixed during development:* the first implementation used
  `rate × assumed_gp`, which credited 28 goals instead of 6 and overstated the effect
  (107.2 → 112.8 points). The corrected version gives +1.7 points. Recorded here rather than
  quietly deleted.
- **S3b — depth turnover.** Five depth skaters leave, two arrive (Kiviranta, Perron). Both arrivals
  carry a 0.9 role factor (fourth-line role; Perron is entering his age-38 season). Net effect
  −0.29 points.
- **S3c/S3d — goaltending.** Team save percentage shifts by ±0.010, converted through shots
  against:

  ```
  delta_GA_per_game = delta_SV% * SA_per_game = 0.010 * 26.1585 = 0.2616
  lambda_GA_new = lambda_GA0 - delta_GA_per_game
  ```

  Noted limitation: empty-net goals are not shots on goal, so this is a *lower bound* on the true
  effect of a save-percentage change.
- **S4 combined:** `S3a + S3c`, applied in a stated order — roster/offense first, then goaltending.
  Labelled conditional, not a proven best prediction. Cross-effects between the two are not modelled.

## 6. Standings translation is point-level, not a rank forecast

The model does **not** simulate other teams. For each historical Central season, the third-place point
total is the threshold; the reported statistic is the average over five seasons of
`P(simulated points >= that season's third-place total)`. Equality counts as meeting the threshold
(`>=`) and this is stated wherever the number appears.

Rank information is reported as an **interval**: historical Dallas rows are removed from the
competitor set (Dallas is the team being replaced), and a simulated total is ranked as
`[rivals strictly above + 1, rivals at or above + 1]`. The interval exists because historical ties
have no recorded tiebreaker and none is invented. This is not a playoff-qualification probability.

## 7. Backtest protocol

Fit rates and `p` on 2024-25 only → freeze → simulate 2025-26 → open the actual result once.
No parameter was revised afterwards (`post_backtest_revisions: []` in `outputs/tables/backtest.json`).
An automated test corrupts the target total and asserts that the forecast distribution is unchanged,
which demonstrates the separation mechanically rather than by assertion.

## 8. Simulation and reproducibility

10,000 seasons per scenario, `seed = 3315`, `games_per_season = 82`, one RNG stream per scenario so
runs are comparable (common random numbers). Determinism is checked by re-running with the same seed.
`outputs/tables/run_manifest.json` records the seed, sample size, rates, scenario settings, config
version, model version, package versions and input checksums; run timestamps are kept in a separate
`run_metadata.json` so they never affect a numerical comparison.

Independent numerical check: an analytic expected-points calculation (truncated bivariate Poisson
with the tied-game adjustment) is stored next to every Monte Carlo mean
(`analytic_expected_points`, `mc_minus_analytic`); all 18 scenarios agree within 1.2 points and are
tested.
