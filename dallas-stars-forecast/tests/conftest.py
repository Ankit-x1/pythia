"""Shared fixtures.

Real processed CSVs are used where the contract is about the actual data. Small
SYNTHETIC fixtures are used only inside tests that need hand-computable cases;
they never enter data/, outputs/ or the reports.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

PROCESSED = ROOT / "data" / "processed"


@pytest.fixture(scope="session")
def processed_dir() -> Path:
    return PROCESSED


@pytest.fixture(scope="session")
def log26() -> pd.DataFrame:
    return pd.read_csv(PROCESSED / "game_log_dal_2025_26.csv")


@pytest.fixture(scope="session")
def log25() -> pd.DataFrame:
    return pd.read_csv(PROCESSED / "game_log_dal_2024_25.csv")


@pytest.fixture(scope="session")
def totals26() -> pd.Series:
    return pd.read_csv(PROCESSED / "team_totals_dal_2025_26.csv").iloc[0]


@pytest.fixture(scope="session")
def standings() -> pd.DataFrame:
    return pd.read_csv(PROCESSED / "central_standings_2021_2026.csv")


@pytest.fixture(scope="session")
def config() -> dict:
    from stars_forecast.config import load_config
    return load_config()


# ---------------------------------------------------------------- synthetic helpers
SYNTHETIC_FINISHES = ["REG", "REG", "OT", "SO"]


def synthetic_game_log() -> pd.DataFrame:
    """Hand-built 4-game log: REG win, REG loss, OT win, SO loss.

    Regulation scores are chosen so final, displayed and regulation totals all
    differ in a way a test can assert exactly.
    """
    rows = [
        # REG win 3-1
        dict(game_id=1, date="2025-10-01", season="9999-00", game_type=2, opponent="AAA",
             home_away="H", goals_for_reg=3, goals_against_reg=1, goals_for_ot=0,
             goals_against_ot=0, goals_for_so=0, goals_against_so=0, result="W", finish="REG"),
        # REG loss 1-4
        dict(game_id=2, date="2025-10-03", season="9999-00", game_type=2, opponent="BBB",
             home_away="A", goals_for_reg=1, goals_against_reg=4, goals_for_ot=0,
             goals_against_ot=0, goals_for_so=0, goals_against_so=0, result="L", finish="REG"),
        # OT win: 2-2 after regulation, 3-2 final hockey
        dict(game_id=3, date="2025-10-05", season="9999-00", game_type=2, opponent="CCC",
             home_away="H", goals_for_reg=2, goals_against_reg=2, goals_for_ot=1,
             goals_against_ot=0, goals_for_so=0, goals_against_so=0, result="W", finish="OT"),
        # SO loss: 2-2 after regulation and after OT, shootout decides it
        dict(game_id=4, date="2025-10-07", season="9999-00", game_type=2, opponent="DDD",
             home_away="A", goals_for_reg=2, goals_against_reg=2, goals_for_ot=0,
             goals_against_ot=0, goals_for_so=0, goals_against_so=1, result="L", finish="SO"),
    ]
    df = pd.DataFrame(rows)
    df["goals_for_final_hockey"] = df["goals_for_reg"] + df["goals_for_ot"]
    df["goals_against_final_hockey"] = df["goals_against_reg"] + df["goals_against_ot"]
    df["goals_for_displayed"] = df["goals_for_final_hockey"] + df["goals_for_so"]
    df["goals_against_displayed"] = df["goals_against_final_hockey"] + df["goals_against_so"]
    return df
