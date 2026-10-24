# Data dictionary (processed CSVs)

All files live in `data/processed/`. Every value is derived from a cached raw response in
`data/raw/` by `python -m stars_forecast collect-data`. Seasons use the NHL "YYYY-YY" label.

## team_totals_dal_2025_26.csv / team_totals_dal_2024_25.csv  (1 row each)
| Column | Definition |
|---|---|
| `season`, `team`, `team_id` | season label, club name, NHL team id (Dallas = 25) |
| `gp`, `wins`, `losses`, `ot_losses`, `points`, `point_pct` | standings record as published; `losses` = regulation losses |
| `goals_for`, `goals_against` | official season totals, **final-hockey convention** (include overtime goals) |
| `gf_per_game`, `ga_per_game` | official per-game rates (same convention) |
| `pp_pct`, `pp_net_pct`, `pk_pct`, `pk_net_pct` | special teams as decimals (0.2863 = 28.63 %) |
| `shots_for_per_game`, `shots_against_per_game` | team shots on goal per game |
| `faceoff_win_pct` | share of faceoffs won |
| `wins_in_regulation`, `wins_in_shootout`, `regulation_and_ot_wins` | win breakdown |
| `team_shutouts` | shutouts recorded by the team's goalies |
| `source_url` | exact endpoint used |

## game_log_dal_2025_26.csv / game_log_dal_2024_25.csv  (82 rows each)
| Column | Definition |
|---|---|
| `game_id` | NHL game id (unique; encodes season/type/game number) |
| `date`, `season`, `game_type` | game date, season label, 2 = regular season |
| `game_state` | terminal game state reported by the API (`OFF` in this endpoint version) |
| `opponent`, `home_away` | opponent abbreviation; `H`/`A` from Dallas's perspective |
| `goals_for_reg`, `goals_against_reg` | goals at 60 minutes only |
| `goals_for_ot`, `goals_against_ot` | overtime-period goals |
| `goals_for_so`, `goals_against_so` | shootout decision increment (never a hockey goal; exactly 1 per SO game, on the winner's side) |
| `goals_for_final_hockey`, `goals_against_final_hockey` | reg + OT; matches official NHL season totals |
| `goals_for_displayed`, `goals_against_displayed` | what the box score shows (reg + OT + SO increment) |
| `result` | `W` / `L` |
| `finish` | `REG`, `OT` or `SO` (deciding period type) |
| `shots_for`, `shots_against` | shots on goal |
| `pp_goals_for`, `pp_opps_for`, `pp_goals_against`, `pp_opps_against` | power play goals / opportunities |
| `faceoff_win_pct`, `pim_for`, `hits_for`, `blocked_for` | supporting per-game fields |
| `source_url` | exact gamecenter endpoint used |

## skaters_dal_2025_26.csv (25 rows)
`player_id`, `player`, `position`, `team_attribution` (always contains DAL → Dallas-only
contribution), `gp`, `goals`, `assists`, `points`, `shots`, `shooting_pct`, `pp_goals`,
`pp_points`, `ev_goals`, `ot_goals`, `game_winning_goals`, `toi_per_gp_sec`, `toi_per_gp_min`,
`faceoff_win_pct`, `plus_minus`, `season`, `source_url`.

## arrivals_dal_2026_27_prior_season.csv (4 rows)
2026-27 roster players who were not Dallas skaters in 2025-26. Same statistical fields as above but
**full-season, all-team** production (`team_attribution` lists every club), used only to build roster
scenarios.

## goalies_dal_2025_26.csv (2 rows)
`player_id`, `player`, `gp` (appearances, not starts), `games_started`, `wins`, `losses`,
`ot_losses`, `shots_against`, `saves`, `goals_against` (goalie-attributed), `save_pct`, `gaa`,
`shutouts`, `season`, `source_url`.
Note: goalie `gp` totals exceed 82 because appearances are not team games, and goalie `goals_against`
is lower than team goals against because empty-net goals beat no goalie.

## central_standings_2021_2026.csv (40 rows = 8 teams x 5 seasons)
| Column | Definition |
|---|---|
| `season`, `as_of_date` | season label; the final regular-season date the snapshot was taken on |
| `team`, `team_name`, `division`, `conference` | club identity; only Central Division rows are kept |
| `gp`, `wins`, `losses`, `ot_losses`, `points`, `point_pct` | standings fields as published |
| `goals_for`, `goals_against` | official season totals (final-hockey convention) |
| `division_rank`, `conference_rank`, `league_rank` | published sequences |
| `clinch_indicator` | raw NHL indicator (`x`, `y`, `z`, `p` or empty) |
| `made_playoffs` | derived flag: clinch indicator in {x, y, z, p} |
| `is_dallas` | Dallas row flag; used to exclude Dallas from competitor comparisons |
| `source_url` | standings endpoint for that date |

## roster_dal_2026_27.csv (25 rows)
`player_id`, `player`, `position_group` (F/D/G), `position_code`, `sweater_number`,
`shoots_catches`, `height_in`, `weight_lb`, `birth_date`, `roster_snapshot_utc` (the date the
snapshot was captured — not an opening-night roster claim), `source_url`.

## JSON evidence files
| File | Contents |
|---|---|
| `outputs/qa/data-validation.json` | every validation check with compared numbers and pass/fail |
| `data/processed/hr_crosscheck_*.json` | Hockey-Reference vs cleaned-log totals |
| `data/processed/roster_announcement_probe.json` | outcome of fetching the proposal's roster announcement URL |
| `data/raw/source_manifest.json` | dataset, file, URL, timestamp, size, SHA-256 per source file |
