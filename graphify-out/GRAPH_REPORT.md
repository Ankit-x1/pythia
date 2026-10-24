# Graph Report - fin_1  (2026-10-23)

## Corpus Check
- 82 files · ~63,255 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 32 file(s) not represented in the graph (top: .npz 19, .csv 11, (none) 1)

## Summary
- 425 nodes · 897 edges · 21 communities (14 shown, 7 thin omitted)
- Extraction: 96% EXTRACTED · 4% INFERRED · 0% AMBIGUOUS · INFERRED: 35 edges (avg confidence: 0.89)
- Token cost: 195,684 input · 16,375 output

## Community Hubs (Navigation)
- CLI and Report Orchestration
- Data Collection Pipeline
- Forecast Model and Scenarios
- Chart Generation
- Scenario Configuration
- Backtesting and Calibration
- Game Schedule and Venues
- League Game Logs
- Configuration Validation
- Standings and Ranking Analysis
- Data Contract Tests
- Simulation Model Tests
- Scraped Page Boilerplate
- Forecast Results and Charts
- Data Dictionary
- Model Decisions and Rationale
- Project Progress Tracking
- Project Packaging
- Hockey Reference Source

## God Nodes (most connected - your core abstractions)
1. `run_all()` - 32 edges
2. `2025-26 Regular Season Gamelog` - 31 edges
3. `2025-26 Dallas Stars` - 30 edges
4. `simulate_seasons()` - 22 edges
5. `fit_rates()` - 20 edges
6. `build_scenarios()` - 20 edges
7. `run_validation()` - 20 edges
8. `Manifest` - 18 edges
9. `run_collect()` - 17 edges
10. `rel()` - 16 edges

## Surprising Connections (you probably didn't know these)
- `Results Summary` --references--> `Goal Frequencies Chart`  [EXTRACTED]
  dallas-stars-forecast/outputs/results-summary.md → dallas-stars-forecast/outputs/figures/fig1_goal_frequencies.png
- `Results Summary` --references--> `Offense Point Distributions Chart`  [EXTRACTED]
  dallas-stars-forecast/outputs/results-summary.md → dallas-stars-forecast/outputs/figures/fig2_offense_point_distributions.png
- `Results Summary` --references--> `Defense Point Distributions Chart`  [EXTRACTED]
  dallas-stars-forecast/outputs/results-summary.md → dallas-stars-forecast/outputs/figures/fig3_defense_point_distributions.png
- `Results Summary` --references--> `Sensitivity Curves Chart`  [EXTRACTED]
  dallas-stars-forecast/outputs/results-summary.md → dallas-stars-forecast/outputs/figures/fig4_sensitivity_curves.png
- `Results Summary` --references--> `Personnel Comparison Chart`  [EXTRACTED]
  dallas-stars-forecast/outputs/results-summary.md → dallas-stars-forecast/outputs/figures/fig5_personnel_comparison.png

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Forecasting Pipeline Flow** — dallas_stars_forecast_src_stars_forecast_collect, dallas_stars_forecast_src_stars_forecast_validate, dallas_stars_forecast_src_stars_forecast_model, dallas_stars_forecast_src_stars_forecast_scenarios, dallas_stars_forecast_src_stars_forecast_pipeline [EXTRACTED 1.00]
- **Scenario Family Definitions** — dallas_stars_forecast_src_stars_forecast_scenarios, dallas_stars_forecast_config_scenarios, dallas_stars_forecast_docs_model_decisions [EXTRACTED 0.95]
- **2025-26 Dallas Stars Schedule** — probe_hr_event_202602250dal, probe_hr_event_202602280dal, probe_hr_event_202603020van, probe_hr_event_202603030cgy, probe_hr_event_202603060dal, probe_hr_event_202603080dal, probe_hr_event_202603100dal, probe_hr_event_202603120dal, probe_hr_event_202603140dal, probe_hr_event_202603160dal, probe_hr_event_202603180col, probe_hr_event_202603210min, probe_hr_event_202603220dal, probe_hr_event_202603240dal, probe_hr_event_202603260nyi, probe_hr_event_202603280pit, probe_hr_event_202603290phi, probe_hr_event_202603310bos, probe_hr_event_202604020dal, probe_hr_event_202604040dal, probe_hr_event_202604070dal, probe_hr_event_202604090dal, probe_hr_event_202604110dal, probe_hr_event_202604130tor, probe_hr_event_202604150buf [EXTRACTED 1.00]
- **Dallas Stars 2025-26 Season Data** — probe_hr_dallas_stars_2026, probe_hr_team_games, probe_hr_team_games_post [EXTRACTED 1.00]
- **Sports Reference Network Sites** — sports_reference_hub, baseball_reference, pro_football_reference, basketball_reference, probe_hr_html, fbref, stathead [EXTRACTED 1.00]

## Communities (21 total, 7 thin omitted)

### Community 0 - "CLI and Report Orchestration"
Cohesion: 0.07
Nodes (16): Data Report, QA Results, build_parser(), cmd_collect_data(), cmd_data_report(), cmd_run_all(), cmd_validate_data(), main() (+8 more)

### Community 1 - "Data Collection Pipeline"
Cohesion: 0.11
Nodes (21): collect_arrivals_prior(), collect_central_standings(), collect_game_log(), collect_goalies(), collect_hr_crosscheck(), collect_roster(), collect_skaters(), collect_team_totals() (+13 more)

### Community 2 - "Forecast Model and Scenarios"
Cohesion: 0.10
Nodes (23): fit_rates(), _availability_delta(), build_scenarios(), _personnel_delta(), synthetic_game_log(), test_final_hockey_totals_exclude_shootout(), test_fixture_points_and_record(), test_no_tied_games_raises() (+15 more)

### Community 3 - "Chart Generation"
Cohesion: 0.13
Nodes (19): _caption(), fig_backtest(), fig_central(), fig_data_overview(), fig_goal_frequencies(), fig_personnel(), fig_point_distributions(), fig_sensitivity_curves() (+11 more)

### Community 4 - "Scenario Configuration"
Cohesion: 0.06
Nodes (32): assumed_gp, delta_team_save_pct, direction, note, player, prior_goals, prior_gp, role_factor (+24 more)

### Community 5 - "Backtesting and Calibration"
Cohesion: 0.10
Nodes (8): run_backtest(), _chi2_gof(), dispersion_report(), _nb_aic(), Rates, ScenarioSpec, summarize(), test_backtest_records_target_outcome_separately()

### Community 6 - "Game Schedule and Venues"
Cohesion: 0.06
Nodes (31): American Airlines Center, 2025-26 Dallas Stars, Seattle Kraken @ Dallas Stars, Nashville Predators @ Dallas Stars, Dallas Stars @ Vancouver Canucks, Dallas Stars @ Calgary Flames, Colorado Avalanche @ Dallas Stars, Chicago Blackhawks @ Dallas Stars (+23 more)

### Community 7 - "League Game Logs"
Cohesion: 0.07
Nodes (30): 2025-26 Regular Season Gamelog, Anaheim Ducks (2026), Boston Bruins (2026), Buffalo Sabres (2026), Carolina Hurricanes (2026), Columbus Blue Jackets (2026), Calgary Flames (2026), Chicago Blackhawks (2026) (+22 more)

### Community 8 - "Configuration Validation"
Cohesion: 0.11
Nodes (10): ConfigError, load_config(), Scenario, missing_check(), config(), log25(), log26(), processed_dir() (+2 more)

### Community 9 - "Standings and Ranking Analysis"
Cohesion: 0.14
Nodes (12): points_rank_table(), season_thresholds(), translate(), test_analytic_check_recorded_for_every_scenario(), test_backtest_does_not_read_target_rates(), test_historical_dallas_excluded_from_competitors(), test_pipeline_outputs_exist_and_are_consistent(), test_scenario_samples_reproduce_summaries() (+4 more)

### Community 10 - "Data Contract Tests"
Cohesion: 0.09
Nodes (6): test_cross_source_reconciliation_evidence(), test_goal_convention_matching_official(), test_record_and_points_identities(), test_result_categories(), test_roster_contract(), test_validation_artifact_passes()

### Community 11 - "Simulation Model Tests"
Cohesion: 0.24
Nodes (16): expected_points(), simulate_seasons(), _rates(), _spec(), test_common_random_numbers_are_reusable(), test_different_seed_differs(), test_equal_rates_cancel_in_differential(), test_every_season_has_82_games_and_valid_points() (+8 more)

### Community 12 - "Scraped Page Boilerplate"
Cohesion: 0.18
Nodes (11): Baseball-Reference.com, Basketball-Reference.com, FBref.com (Soccer), Freestar Ad Engine, Google Tag Manager, HubSpot Embed Code, Immaculate Grid, Pro-Football-Reference.com (+3 more)

### Community 13 - "Forecast Results and Charts"
Cohesion: 0.22
Nodes (9): Results Summary, Goal Frequencies Chart, Offense Point Distributions Chart, Defense Point Distributions Chart, Sensitivity Curves Chart, Personnel Comparison Chart, Central Points vs Rank Chart, Backtest Chart (+1 more)

## Knowledge Gaps
- **82 isolated node(s):** `stars-forecast`, `Data Dictionary`, `Data Report`, `Model Decisions and Change Log`, `Progress Tracker` (+77 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 219 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **7 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `run_all()` connect `Chart Generation` to `CLI and Report Orchestration`, `Forecast Model and Scenarios`, `Backtesting and Calibration`, `Configuration Validation`, `Standings and Ranking Analysis`, `Simulation Model Tests`?**
  _High betweenness centrality (0.062) - this node is a cross-community bridge._
- **What connects `stars-forecast`, `Data Dictionary`, `Data Report` to the rest of the system?**
  _82 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `CLI and Report Orchestration` be split into smaller, more focused modules?**
  _Cohesion score 0.0663265306122449 - nodes in this community are weakly interconnected._
- **Should `Data Collection Pipeline` be split into smaller, more focused modules?**
  _Cohesion score 0.10821256038647344 - nodes in this community are weakly interconnected._
- **Should `Forecast Model and Scenarios` be split into smaller, more focused modules?**
  _Cohesion score 0.10104529616724739 - nodes in this community are weakly interconnected._
- **Should `Chart Generation` be split into smaller, more focused modules?**
  _Cohesion score 0.1282051282051282 - nodes in this community are weakly interconnected._
- **Should `Scenario Configuration` be split into smaller, more focused modules?**
  _Cohesion score 0.06060606060606061 - nodes in this community are weakly interconnected._