# Dallas Stars 2026-27 Season Performance Forecasting Model

A probabilistic forecast of the Dallas Stars' 2026-27 regular season, built from completed NHL data
through the end of 2025-26. Poisson goal models feed a Monte Carlo season simulator; scenarios test
offense, defense/goaltending and roster changes; a frozen 2024-25 model is backtested against the
known 2025-26 season.

---

## Headline result (10,000 simulated seasons, seed 3315)

|                                                      | Value                                                                              |
| ---------------------------------------------------- | ---------------------------------------------------------------------------------- |
| Baseline rates (2025-26 regulation)                  | 3.256 goals for, 2.610 goals against per game                                      |
| Mean projected points                                | **105.7** (median 106)                                                       |
| 80 % / 95 % simulation intervals                     | 95–116 / 89–122                                                                  |
| Mean record                                          | 49.5 W – 25.8 regulation L – 6.7 OTL                                             |
| P(≥ 100 pts) / P(≥ 110 pts)                        | 77.7 % / 32.0 %                                                                    |
| Historical top-three Central point-level probability | **57.7 %**                                                                   |
| Backtest (2024-25 → 2025-26)                        | forecast 105.9 vs actual 112, error 6.1 pts, actual inside 80 % and 95 % intervals |

Read `outputs/results-summary.md` for the full evidence summary, `docs/data-report.md` for the data
report, and `docs/model-decisions.md` for every modelling choice (including one item awaiting
instructor review).

## Install

```bash
git clone https://github.com/Ankit-x1/pythia.git
cd pythia/dallas-stars-forecast

uv sync --extra dev
```

Requires Python 3.10+ (developed on 3.13). Dependencies: pandas, NumPy, SciPy, Matplotlib, requests,
PyYAML, pytest, tabulate.

## Commands

```bash
# 1. Acquire and clean all source data (network; cached and resumable, safe to re-run)
python -m stars_forecast collect-data

# 2. Validate the datasets (exits nonzero if any check fails)
python -m stars_forecast validate-data

# 3. Regenerate the data report
python -m stars_forecast data-report

# 4. Run the full analysis: diagnostics, 18 scenarios, backtest, tables, figures
python -m stars_forecast run-all --n-seasons 10000 --seed 3315

# 5. Tests
python -m pytest --junitxml=outputs/qa/test-results.xml
```

`run-all` reads only local validated inputs — no network needed once `collect-data` has run. It
refuses to run if validation fails or an input file is missing.

### Rerun from local inputs only

```bash
python -m stars_forecast validate-data && python -m stars_forecast run-all --n-seasons 10000 --seed 3315
```

### Use a different project root

```bash
STARS_ROOT=/path/to/project python -m stars_forecast run-all
```

## What the model does

```
Regulation goals for      X_i ~ Poisson(lambda_GF)      lambda_GF = mean(60-min goals for)
Regulation goals against  Y_i ~ Poisson(lambda_GA)      lambda_GA = mean(60-min goals against)
Tie after 60 minutes      Dallas wins with p = 0.500    (12 of 24 tied games in 2025-26)
Points                    2 win, 1 OT/SO loss, 0 regulation loss; 82 games per season
```

### Scenario families

| Family                 | What changes                                                                                                                                                              |
| ---------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **S0** Baseline  | 2025-26 regulation rates, unchanged                                                                                                                                       |
| **S1** Offense   | `lambda_GF` × (1 ± 5 %, 10 %, 15 %), defense fixed                                                                                                                    |
| **S2** Defense   | `lambda_GA` × (1 ± 5 %, 10 %, 15 %), offense fixed                                                                                                                    |
| **S3** Personnel | S3a Rantanen full-season availability, S3b depth turnover, S3c/S3d goaltending save-% shifts, all from verified player data with a documented per-team-game normalization |
| **S4** Combined  | S3a + S3c, order of application stated, labelled conditional                                                                                                              |

Scenario parameters live in `config/scenarios.yaml` (versioned).

## Repository layout

```
src/stars_forecast/
  fetch.py        cached, throttled, bounded-retry HTTP + SHA-256 source manifest
  collect.py      datasets A-G acquisition and cleaning (pure code, no hand-built CSVs)
  validate.py     30 automated data checks -> outputs/qa/data-validation.json
  model.py        Poisson fits, dispersion/GOF diagnostics, Monte Carlo engine, analytic check
  scenarios.py    S0-S4 construction from config + verified data
  standings.py    historical Central point-level translation and rank intervals
  backtest.py     frozen 2024-25 -> 2025-26 out-of-sample pass
  figures.py      8 figures
  pipeline.py     orchestration + run manifest
  summary.py      outputs/results-summary.md
  datareport.py   docs/data-report.md
  cli.py          command line
tests/            64 tests: data contracts, model core, scenarios, pipeline/backtest
config/           scenarios.yaml
data/raw/         cached source responses (regenerable)
data/processed/   cleaned CSVs + validation evidence
docs/             data report, model decisions, QA results, progress, data dictionary
outputs/          figures/, tables/, qa/, results-summary.md
```

## Data sources

Official NHL data endpoints (team totals, per-game period scoring, skaters, goalies, standings,
roster) with Hockey-Reference as an independent game-log cross-check. Every file's URL, timestamp and
SHA-256 is in `data/raw/source_manifest.json`. Full provenance and reconciliation are in
`docs/data-report.md`.

**Goal conventions** are kept separate and never merged: regulation (60 min), final hockey (reg + OT)
and displayed (includes the shootout decision increment). Official NHL season totals match the final
hockey convention; the simulation is regulation-based and uses the 60-minute means.

## Data licensing

Raw responses from NHL.com and Hockey-Reference are cached locally so results are reproducible. Both
are third-party content — do not republish the cached snapshots without checking each source's terms.
`data/raw/` is excluded from the repository for that reason and can be regenerated
with `python -m stars_forecast collect-data`.

## Status

Complete: data collection, validation, model, all four scenario families, 10,000-season runs,
figures, backtest, QA suite, CLI, data report.

## Limitations

Goals for and against are modelled as independent Poisson draws. One constant rate per side ignores
opponent strength, home/away, rest, injuries and game state. The tied-game probability and the
five-season Central sample are small. Simulation intervals quantify noise conditional on the model,
not model error. One backtest does not establish general forecasting accuracy. "Top-three Central
point-level probability" is not a playoff-qualification probability. See
`docs/model-decisions.md` and `outputs/results-summary.md` §8.
