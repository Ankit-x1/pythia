"""Config loading with validation. Invalid rates never reach the simulator."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .paths import CONFIG


class ConfigError(ValueError):
    """Raised when a scenario or simulation setting is scientifically invalid."""


@dataclass
class Scenario:
    scenario_id: str
    name: str
    family: str
    offense_multiplier: float = 1.0
    defense_multiplier: float = 1.0
    offense_delta_per_game: float = 0.0
    defense_delta_per_game: float = 0.0
    details: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        if self.offense_multiplier <= 0 or self.defense_multiplier <= 0:
            raise ConfigError(f"{self.scenario_id}: multipliers must be positive")
        if not 0.5 <= self.offense_multiplier <= 3.0:
            raise ConfigError(f"{self.scenario_id}: offense multiplier outside sane range")
        if not 0.5 <= self.defense_multiplier <= 3.0:
            raise ConfigError(f"{self.scenario_id}: defense multiplier outside sane range")


def load_config(path: Path | None = None) -> dict[str, Any]:
    path = path or (CONFIG / "scenarios.yaml")
    with open(path, encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    for key in ("seasons", "simulation", "sensitivity", "roster", "version"):
        if key not in cfg:
            raise ConfigError(f"config missing required key: {key}")
    sim = cfg["simulation"]
    if int(sim["n_seasons"]) < 1000:
        raise ConfigError("n_seasons must be at least 1000")
    if int(sim["games_per_season"]) != 82:
        raise ConfigError("NHL regular season must be 82 games")
    return cfg
