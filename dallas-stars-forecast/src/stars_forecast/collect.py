"""Acquisition and cleaning of datasets A-G.

Every processed CSV written here is derived from a cached raw response stored
under data/raw/. Nothing is hand-entered; nothing is synthetic.

Goal conventions (see docs/model-decisions.md):
  * ``*_reg``   goals scored at 60 minutes only.
  * ``*_ot``    goals scored in the 5-minute overtime period.
  * ``*_so``    the artificial shootout decision increment (never a hockey goal).
  * ``*_final_hockey``  regulation + overtime goals (the convention used to fit rates).
  * ``*_displayed``     what the scoreboard / box score shows (includes the SO increment).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import pandas as pd

from .fetch import FetchError, Manifest, fetch_json, fetch_text
from .paths import PROCESSED, RAW, rel

NHL_WEB = "https://api-web.nhle.com/v1"
NHL_STATS = "https://api.nhle.com/stats/rest/en"
DAL_TEAM_ID = 25
HISTORY_SEASONS = ["20212022", "20222023", "20232024", "20242025", "20252026"]
SEASON_LABEL = {"20212022": "2021-22", "20222023": "2022-23", "20232024": "2023-24",
                "20242025": "2024-25", "20252026": "2025-26", "20262027": "2026-27"}


def _stats_url(path: str, cayenne: str, limit: int = 200) -> str:
    from urllib.parse import quote
    return (f"{NHL_STATS}/{path}?isAggregate=false&isGame=false&start=0&limit={limit}"
            f"&cayenneExp={quote(cayenne)}")


# --------------------------------------------------------------------------- A/E
def collect_team_totals(season: str, manifest: Manifest) -> pd.DataFrame:
    """Team-level season totals for Dallas (dataset A: 2025-26, dataset E: 2024-25)."""
    url = _stats_url("team/summary", f"seasonId={season} and gameTypeId=2", limit=50)
    data = fetch_json(url, "nhl/team_summary", f"team_summary_{season}.json", manifest,
                      dataset="A" if season == "20252026" else "E", season=SEASON_LABEL[season],
                      filters="regular season, all teams (Dallas row retained)")
    rows = [r for r in data["data"] if r.get("teamId") == DAL_TEAM_ID]
    if len(rows) != 1:
        raise FetchError(f"expected exactly one Dallas row in team summary {season}")
    r = rows[0]
    df = pd.DataFrame([{
        "season": SEASON_LABEL[season],
        "team": r["teamFullName"],
        "team_id": r["teamId"],
        "gp": r["gamesPlayed"],
        "wins": r["wins"],
        "losses": r["losses"],
        "ot_losses": r["otLosses"],
        "points": r["points"],
        "point_pct": r["pointPct"],
        "goals_for": r["goalsFor"],
        "goals_against": r["goalsAgainst"],
        "gf_per_game": r["goalsForPerGame"],
        "ga_per_game": r["goalsAgainstPerGame"],
        "pp_pct": r["powerPlayPct"],
        "pp_net_pct": r["powerPlayNetPct"],
        "pk_pct": r["penaltyKillPct"],
        "pk_net_pct": r["penaltyKillNetPct"],
        "shots_for_per_game": r["shotsForPerGame"],
        "shots_against_per_game": r["shotsAgainstPerGame"],
        "faceoff_win_pct": r["faceoffWinPct"],
        "wins_in_regulation": r["winsInRegulation"],
        "wins_in_shootout": r["winsInShootout"],
        "regulation_and_ot_wins": r["regulationAndOtWins"],
        "team_shutouts": r["teamShutouts"],
        "source_url": url,
    }])
    out = PROCESSED / f"team_totals_dal_{SEASON_LABEL[season].replace('-', '_')}.csv"
    df.to_csv(out, index=False)
    return df


# --------------------------------------------------------------------------- B/E
def _period_goals(linescore: dict, team_side: str) -> dict[str, int]:
    """Sum goals by period type for one side ('away'/'home')."""
    totals = {"REG": 0, "OT": 0, "SO": 0}
    for period in linescore.get("byPeriod", []):
        ptype = period["periodDescriptor"]["periodType"]
        if ptype in totals:
            totals[ptype] += int(period[team_side])
    return totals


def _team_stat(team_stats: list[dict], category: str, side: str) -> Any:
    for row in team_stats:
        if row.get("category") == category:
            return row.get(f"{side}Value")
    return None


def _parse_pp(value: str | None) -> tuple[int | None, int | None]:
    if not value or "/" not in str(value):
        return None, None
    made, _, opps = str(value).partition("/")
    try:
        return int(made), int(opps)
    except ValueError:
        return None, None


def collect_game_log(season: str, manifest: Manifest) -> pd.DataFrame:
    """Regular-season game log with overtime/shootout accounting (dataset B/E)."""
    sched = fetch_json(f"{NHL_WEB}/club-schedule-season/DAL/{season}", "nhl/schedule",
                       f"dal_schedule_{season}.json", manifest,
                       dataset="B" if season == "20252026" else "E",
                       season=SEASON_LABEL[season], filters="all game types; regular season kept")
    games = [g for g in sched["games"] if g["gameType"] == 2]
    rows: list[dict[str, Any]] = []
    for g in games:
        gid = g["id"]
        rr_url = f"{NHL_WEB}/gamecenter/{gid}/right-rail"
        rr = fetch_json(rr_url, "nhl/right_rail", f"{gid}.json", manifest,
                        dataset="B" if season == "20252026" else "E",
                        season=SEASON_LABEL[season], game_id=gid,
                        filters="linescore by period + team game stats")
        home = g["homeTeam"]["abbrev"] == "DAL"
        side, opp_side = ("home", "away") if home else ("away", "home")
        gf = _period_goals(rr["linescore"], side)
        ga = _period_goals(rr["linescore"], opp_side)
        ts = rr.get("teamGameStats") or []
        ppg_for, ppo_for = _parse_pp(_team_stat(ts, "powerPlay", side))
        ppg_ag, ppo_ag = _parse_pp(_team_stat(ts, "powerPlay", opp_side))
        gf_disp = gf["REG"] + gf["OT"] + gf["SO"]
        ga_disp = ga["REG"] + ga["OT"] + ga["SO"]
        finish = (g.get("gameOutcome") or {}).get("lastPeriodType")
        if finish not in ("REG", "OT", "SO"):
            raise FetchError(f"unexpected finish type {finish!r} in game {gid}")
        rows.append({
            "game_id": gid,
            "date": g["gameDate"],
            "season": SEASON_LABEL[season],
            "game_type": g["gameType"],
            "game_state": g.get("gameState"),
            "opponent": g[opp_side + "Team"]["abbrev"],
            "home_away": "H" if home else "A",
            "goals_for_reg": gf["REG"], "goals_against_reg": ga["REG"],
            "goals_for_ot": gf["OT"], "goals_against_ot": ga["OT"],
            "goals_for_so": gf["SO"], "goals_against_so": ga["SO"],
            "goals_for_final_hockey": gf["REG"] + gf["OT"],
            "goals_against_final_hockey": ga["REG"] + ga["OT"],
            "goals_for_displayed": gf_disp,
            "goals_against_displayed": ga_disp,
            "result": "W" if gf_disp > ga_disp else "L",
            "finish": finish,
            "shots_for": _team_stat(ts, "sog", side),
            "shots_against": _team_stat(ts, "sog", opp_side),
            "pp_goals_for": ppg_for, "pp_opps_for": ppo_for,
            "pp_goals_against": ppg_ag, "pp_opps_against": ppo_ag,
            "faceoff_win_pct": _team_stat(ts, "faceoffWinningPctg", side),
            "pim_for": _team_stat(ts, "pim", side),
            "hits_for": _team_stat(ts, "hits", side),
            "blocked_for": _team_stat(ts, "blockedShots", side),
            "source_url": rr_url,
        })
    df = pd.DataFrame(rows).sort_values(["date", "game_id"]).reset_index(drop=True)
    out = PROCESSED / f"game_log_dal_{SEASON_LABEL[season].replace('-', '_')}.csv"
    df.to_csv(out, index=False)
    return df


# --------------------------------------------------------------------------- C/D
def collect_skaters(season: str, manifest: Manifest) -> pd.DataFrame:
    url = _stats_url("skater/summary", f'seasonId={season} and gameTypeId=2 and teamAbbrevs="DAL"')
    data = fetch_json(url, "nhl/skaters", f"skaters_dal_{season}.json", manifest,
                      dataset="C" if season == "20252026" else "E",
                      season=SEASON_LABEL[season],
                      filters="regular season, Dallas-only attribution for traded players")
    rows = [{
        "player_id": r["playerId"],
        "player": r["skaterFullName"],
        "position": r["positionCode"],
        "team_attribution": r["teamAbbrevs"],
        "gp": r["gamesPlayed"],
        "goals": r["goals"],
        "assists": r["assists"],
        "points": r["points"],
        "shots": r["shots"],
        "shooting_pct": r["shootingPct"],
        "pp_goals": r["ppGoals"],
        "pp_points": r["ppPoints"],
        "ev_goals": r["evGoals"],
        "ot_goals": r["otGoals"],
        "game_winning_goals": r["gameWinningGoals"],
        "toi_per_gp_sec": r["timeOnIcePerGame"],
        "toi_per_gp_min": round(r["timeOnIcePerGame"] / 60.0, 1),
        "faceoff_win_pct": r.get("faceoffWinPct"),
        "plus_minus": r.get("plusMinus"),
        "season": SEASON_LABEL[season],
        "source_url": url,
    } for r in data["data"]]
    df = pd.DataFrame(rows).sort_values("points", ascending=False).reset_index(drop=True)
    out = PROCESSED / f"skaters_dal_{SEASON_LABEL[season].replace('-', '_')}.csv"
    df.to_csv(out, index=False)
    return df


def collect_goalies(season: str, manifest: Manifest) -> pd.DataFrame:
    url = _stats_url("goalie/summary", f'seasonId={season} and gameTypeId=2 and teamAbbrevs="DAL"', limit=50)
    data = fetch_json(url, "nhl/goalies", f"goalies_dal_{season}.json", manifest,
                      dataset="D" if season == "20252026" else "E",
                      season=SEASON_LABEL[season],
                      filters="regular season, Dallas-only attribution")
    rows = [{
        "player_id": r["playerId"],
        "player": r["goalieFullName"],
        "gp": r["gamesPlayed"],
        "games_started": r["gamesStarted"],
        "wins": r["wins"],
        "losses": r["losses"],
        "ot_losses": r["otLosses"],
        "shots_against": r["shotsAgainst"],
        "saves": r["saves"],
        "goals_against": r["goalsAgainst"],
        "save_pct": r["savePct"],
        "gaa": r["goalsAgainstAverage"],
        "shutouts": r["shutouts"],
        "season": SEASON_LABEL[season],
        "source_url": url,
    } for r in data["data"]]
    df = pd.DataFrame(rows).sort_values("gp", ascending=False).reset_index(drop=True)
    out = PROCESSED / f"goalies_dal_{SEASON_LABEL[season].replace('-', '_')}.csv"
    df.to_csv(out, index=False)
    return df


# --------------------------------------------------------------------------- F
def collect_central_standings(manifest: Manifest) -> pd.DataFrame:
    """Central Division standings for the five completed seasons (dataset F)."""
    frames = []
    for season in HISTORY_SEASONS:
        sched = fetch_json(f"{NHL_WEB}/club-schedule-season/DAL/{season}", "nhl/schedule",
                           f"dal_schedule_{season}.json", manifest,
                           dataset="F", season=SEASON_LABEL[season],
                           filters="used only to locate the final regular-season date")
        last_date = max(g["gameDate"] for g in sched["games"] if g["gameType"] == 2)
        url = f"{NHL_WEB}/standings/{last_date}"
        data = fetch_json(url, "nhl/standings", f"standings_{season}_{last_date}.json", manifest,
                          dataset="F", season=SEASON_LABEL[season],
                          filters=f"standings on final regular-season date {last_date}")
        rows = [{
            "season": SEASON_LABEL[season],
            "as_of_date": last_date,
            "team": s["teamAbbrev"]["default"],
            "team_name": s["teamName"]["default"],
            "division": s["divisionName"],
            "conference": s["conferenceName"],
            "gp": s["gamesPlayed"],
            "wins": s["wins"],
            "losses": s["losses"],
            "ot_losses": s["otLosses"],
            "points": s["points"],
            "point_pct": s["pointPctg"],
            "goals_for": s["goalFor"],
            "goals_against": s["goalAgainst"],
            "division_rank": s["divisionSequence"],
            "conference_rank": s["conferenceSequence"],
            "league_rank": s["leagueSequence"],
            "clinch_indicator": s.get("clinchIndicator"),
            "source_url": url,
        } for s in data["standings"] if s["divisionName"] == "Central"]
        frames.append(pd.DataFrame(rows))
    df = pd.concat(frames, ignore_index=True)
    df["made_playoffs"] = df["clinch_indicator"].isin(["x", "y", "z", "p"])
    df["is_dallas"] = df["team"] == "DAL"
    df = df.sort_values(["season", "division_rank"]).reset_index(drop=True)
    df.to_csv(PROCESSED / "central_standings_2021_2026.csv", index=False)
    return df


# --------------------------------------------------------------------------- G
def collect_roster(manifest: Manifest) -> pd.DataFrame:
    """Initial 2026-27 Dallas roster (dataset G). Scenario context only."""
    url = f"{NHL_WEB}/roster/DAL/20262027"
    data = fetch_json(url, "nhl/roster", "dal_roster_20262027.json", manifest,
                      dataset="G", season="2026-27",
                      filters="initial/current NHL roster snapshot; no game results")
    snapshot = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    pos_group = {"forwards": "F", "defensemen": "D", "goalies": "G"}
    rows = []
    for group, label in pos_group.items():
        for p in data.get(group, []):
            rows.append({
                "player_id": p["id"],
                "player": f"{p['firstName']['default']} {p['lastName']['default']}",
                "position_group": label,
                "position_code": p.get("positionCode"),
                "sweater_number": p.get("sweaterNumber"),
                "shoots_catches": p.get("shootsCatches"),
                "height_in": p.get("heightInInches"),
                "weight_lb": p.get("weightInPounds"),
                "birth_date": p.get("birthDate"),
                "roster_snapshot_utc": snapshot,
                "source_url": url,
            })
    df = pd.DataFrame(rows)
    df.to_csv(PROCESSED / "roster_dal_2026_27.csv", index=False)

    # Official announcement cited by the proposal: attempt it, record the outcome.
    announce = ("https://www.nhl.com/stars/news/"
                "dallas-stars-announce-initial-roster-for-2026-27-season-092826")
    status = _probe_url(announce, manifest)
    (PROCESSED / "roster_announcement_probe.json").write_text(
        json.dumps({"url": announce, "result": status,
                    "note": "Recorded verbatim; roster CSV comes from the official NHL roster API."},
                   indent=2) + "\n", encoding="utf-8")
    return df


def _probe_url(url: str, manifest: Manifest) -> str:
    try:
        text = fetch_text(url, "nhl/news", "stars_roster_announcement_2026_27.html",
                          manifest, dataset="G", season="2026-27", filters="announcement probe")
    except FetchError as exc:
        return f"unavailable: {exc}"
    return f"ok ({len(text)} bytes)"


def collect_arrivals_prior(roster: pd.DataFrame, season: str, manifest: Manifest) -> pd.DataFrame:
    """2025-26 production for 2026-27 arrivals that were not Dallas skaters that season."""
    dal25 = pd.read_csv(PROCESSED / "skaters_dal_2025_26.csv")
    known = set(dal25["player_id"])
    rows = []
    for _, p in roster.iterrows():
        if p["player_id"] in known or p["position_group"] == "G":
            continue
        url = _stats_url("skater/summary",
                         f"seasonId={season} and gameTypeId=2 and playerId={p['player_id']}")
        data = fetch_json(url, "nhl/arrivals", f"arrival_{p['player_id']}_{season}.json",
                          manifest, dataset="G", season="2025-26",
                          filters=f"all-team full-season production for arrival {p['player']}")
        for r in data["data"]:
            rows.append({
                "player_id": r["playerId"], "player": r["skaterFullName"],
                "position": r["positionCode"], "team_attribution": r["teamAbbrevs"],
                "gp": r["gamesPlayed"], "goals": r["goals"], "assists": r["assists"],
                "points": r["points"], "shots": r["shots"], "shooting_pct": r["shootingPct"],
                "toi_per_gp_min": round(r["timeOnIcePerGame"] / 60.0, 1),
                "season": "2025-26", "source_url": url,
            })
        if not data["data"]:
            rows.append({
                "player_id": p["player_id"], "player": p["player"], "position": p["position_code"],
                "team_attribution": None, "gp": 0, "goals": 0, "assists": 0, "points": 0,
                "shots": 0, "shooting_pct": None, "toi_per_gp_min": None,
                "season": "2025-26", "source_url": url,
            })
    df = pd.DataFrame(rows)
    df.to_csv(PROCESSED / "arrivals_dal_2026_27_prior_season.csv", index=False)
    return df


def collect_hr_crosscheck(game_log: pd.DataFrame, season: str, manifest: Manifest) -> dict:
    """Hockey-Reference cross-check of the Dallas game log (independent source)."""
    year = SEASON_LABEL[season].split("-")[0]
    url = f"https://www.hockey-reference.com/teams/DAL/{int(year) + 1}_gamelog.html"
    try:
        html = fetch_text(url, "hockey-reference", f"dal_gamelog_{season}.html", manifest,
                          dataset="cross-check", season=SEASON_LABEL[season],
                          filters="team game log page")
    except FetchError as exc:
        return {"available": False, "reason": f"{exc}", "url": url}

    # Hockey-Reference wraps its data tables in HTML comments; strip the markers
    # so the parser can see them. This does not modify the cached raw file.
    import re
    from io import StringIO

    visible = re.sub(r"<!--|-->", "", html)
    tables = pd.read_html(StringIO(visible))
    gm = None
    for t in tables:
        flat = t.copy()
        if isinstance(flat.columns, pd.MultiIndex):
            flat.columns = [c[1] if c[1] else c[0] for c in flat.columns]
        if {"GF", "GA"} <= set(flat.columns):
            gm = flat
            break
    if gm is None:
        return {"available": False, "reason": "no game-log table parsed", "url": url}
    date_col = next((c for c in gm.columns if "Date" in str(c)), gm.columns[1])
    mask = gm[date_col].astype(str).str.match(r"^\d{4}-\d{2}-\d{2}$")
    gm = gm[mask].copy()
    for col in ("GF", "GA"):
        gm[col] = pd.to_numeric(gm[col], errors="coerce")
    out = {
        "available": True,
        "url": url,
        "hr_rows": int(len(gm)),
        "hr_sum_GF": float(gm["GF"].sum()),
        "hr_sum_GA": float(gm["GA"].sum()),
        "log_sum_GF_final_hockey": float(game_log["goals_for_final_hockey"].sum()),
        "log_sum_GA_final_hockey": float(game_log["goals_against_final_hockey"].sum()),
        "log_sum_GF_displayed": float(game_log["goals_for_displayed"].sum()),
        "log_sum_GA_displayed": float(game_log["goals_against_displayed"].sum()),
    }
    out["note"] = ("Hockey-Reference game logs report final hockey scores; their GF/GA totals "
                   "exclude the shootout decision increment.")
    (PROCESSED / f"hr_crosscheck_{SEASON_LABEL[season].replace('-', '_')}.json").write_text(
        json.dumps(out, indent=2) + "\n", encoding="utf-8")
    return out


def run_collect() -> dict[str, Any]:
    """Collect every dataset A-G plus the cross-check. Cached and resumable."""
    manifest = Manifest()
    summary: dict[str, Any] = {}

    totals26 = collect_team_totals("20252026", manifest)          # A
    log26 = collect_game_log("20252026", manifest)                # B
    skaters26 = collect_skaters("20252026", manifest)             # C
    goalies26 = collect_goalies("20252026", manifest)             # D
    totals25 = collect_team_totals("20242025", manifest)          # E
    log25 = collect_game_log("20242025", manifest)                # E
    standings = collect_central_standings(manifest)               # F
    roster = collect_roster(manifest)                             # G
    arrivals = collect_arrivals_prior(roster, "20252026", manifest)
    hr26 = collect_hr_crosscheck(log26, "20252026", manifest)
    hr25 = collect_hr_crosscheck(log25, "20242025", manifest)

    manifest.save()
    summary.update({
        "team_totals_2025_26": int(len(totals26)),
        "game_log_2025_26": int(len(log26)),
        "skaters_2025_26": int(len(skaters26)),
        "goalies_2025_26": int(len(goalies26)),
        "team_totals_2024_25": int(len(totals25)),
        "game_log_2024_25": int(len(log25)),
        "central_standings_rows": int(len(standings)),
        "roster_2026_27": int(len(roster)),
        "arrivals_rows": int(len(arrivals)),
        "hr_crosscheck_2025_26": hr26.get("available"),
        "hr_crosscheck_2024_25": hr25.get("available"),
        "raw_files": len(manifest.entries),
        "source_manifest": rel(manifest.path),
    })
    (PROCESSED / "collect_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary
