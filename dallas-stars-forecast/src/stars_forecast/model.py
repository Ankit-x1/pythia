"""Poisson goal models, distribution diagnostics and the Monte Carlo season engine.

Mathematical content (see docs/model-decisions.md for the full derivation):

    X_i ~ Poisson(lambda_GF)        Dallas regulation goals in game i
    Y_i ~ Poisson(lambda_GA)        opponent regulation goals in game i
    lambda_GF = mean(regulation goals for),  lambda_GA = mean(regulation goals against)

A tie after 60 minutes is resolved by an empirically estimated Dallas win
probability p from the training season's tied games, with the overtime/shootout
split taken from the same games.

Points: 2 for a win (regulation, OT or SO), 1 for an OT/SO loss, 0 for a
regulation loss. A season is 82 games.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

GAMES_PER_SEASON = 82


# --------------------------------------------------------------------------- rates
@dataclass
class Rates:
    """Baseline rates for one calibration season."""

    season: str
    lambda_gf: float           # regulation goals for per game
    lambda_ga: float           # regulation goals against per game
    p_win_if_tied: float       # P(Dallas wins | tied after regulation)
    p_ot_given_tied: float     # P(game decided in OT rather than SO | tied)
    n_games: int
    n_tied: int
    n_tied_wins: int
    n_tied_losses: int
    n_ot_games: int
    n_so_games: int

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def fit_rates(game_log: pd.DataFrame) -> Rates:
    """Fit baseline rates from a cleaned game log (regulation convention)."""
    reg_gf = game_log["goals_for_reg"].to_numpy(dtype=float)
    reg_ga = game_log["goals_against_reg"].to_numpy(dtype=float)
    tied = game_log[game_log["goals_for_reg"] == game_log["goals_against_reg"]]
    n_tied = int(len(tied))
    if n_tied == 0:
        raise ValueError("no games were tied after regulation: cannot estimate OT/SO behaviour")

    tied_wins = int((tied["result"] == "W").sum())
    n_ot = int((game_log["finish"] == "OT").sum())
    n_so = int((game_log["finish"] == "SO").sum())
    if n_ot + n_so != n_tied:
        raise ValueError(
            f"internal inconsistency: {n_ot}+{n_so} OT/SO games but {n_tied} games tied "
            "after regulation"
        )
    return Rates(
        season=str(game_log["season"].iloc[0]),
        lambda_gf=float(reg_gf.mean()),
        lambda_ga=float(reg_ga.mean()),
        p_win_if_tied=tied_wins / n_tied,
        p_ot_given_tied=n_ot / n_tied,
        n_games=int(len(game_log)),
        n_tied=n_tied,
        n_tied_wins=tied_wins,
        n_tied_losses=n_tied - tied_wins,
        n_ot_games=n_ot,
        n_so_games=n_so,
    )


def proposal_rates(team_totals: pd.Series) -> dict[str, float]:
    """The proposal's totals/82 rates, kept for comparison only.

    The proposal divides season totals by 82 and calls the result a regulation
    rate. The official totals include overtime goals, so these are final-hockey
    rates, not 60-minute rates.
    """
    return {
        "proposal_lambda_gf_final_hockey": float(team_totals["goals_for"] / team_totals["gp"]),
        "proposal_lambda_ga_final_hockey": float(team_totals["goals_against"] / team_totals["gp"]),
    }


# --------------------------------------------------------------------------- diagnostics
def _chi2_gof(values: np.ndarray, lam: float, min_expected: float = 5.0) -> dict[str, Any]:
    """Chi-square goodness-of-fit with pooled tail bins (expected >= 5)."""
    counts = pd.Series(values).value_counts().sort_index()
    ks = np.arange(0, int(values.max()) + 1)
    observed = np.array([counts.get(k, 0) for k in ks], dtype=float)
    expected = stats.poisson.pmf(ks, lam) * len(values)

    # Pool from the right until every bin has enough expected counts.
    bins_o, bins_e = [], []
    acc_o = acc_e = 0.0
    for o, e in zip(observed[::-1], expected[::-1]):
        acc_o += o
        acc_e += e
        if acc_e >= min_expected:
            bins_o.append(acc_o)
            bins_e.append(acc_e)
            acc_o = acc_e = 0.0
    if acc_e > 0:  # leftover tail
        if bins_e:
            bins_o[-1] += acc_o
            bins_e[-1] += acc_e
        else:
            bins_o.append(acc_o)
            bins_e.append(acc_e)
    bins_o, bins_e = np.array(bins_o[::-1]), np.array(bins_e[::-1])

    stat = float(((bins_o - bins_e) ** 2 / bins_e).sum())
    df = len(bins_o) - 1 - 1  # bins - 1 - estimated parameter
    p = float(stats.chi2.sf(stat, df)) if df > 0 else float("nan")
    return {
        "chi2_statistic": round(stat, 3),
        "df": int(df),
        "p_value": round(p, 4),
        "n_bins": int(len(bins_o)),
        "min_expected_count": round(float(bins_e.min()), 2),
        "observed_bins": [int(x) for x in bins_o],
        "expected_bins": [round(float(x), 2) for x in bins_e],
    }


def _nb_aic(values: np.ndarray) -> dict[str, float]:
    """Method-of-moments negative binomial fit, for AIC comparison only."""
    mean = float(values.mean())
    var = float(values.var(ddof=1))
    if var <= mean:  # no overdispersion -> NB reduces to Poisson
        nll_nb = float(-stats.poisson.logpmf(values, mean).sum())
        return {"nb_mean": round(mean, 4), "nb_size": float("inf"),
                "poisson_nll": round(nll_nb, 3), "nb_nll": round(nll_nb, 3),
                "poisson_aic": round(2 * 1 + 2 * nll_nb, 3),
                "nb_aic": round(2 * 2 + 2 * nll_nb, 3)}
    size = mean ** 2 / (var - mean)
    prob = size / (size + mean)
    nll_nb = float(-stats.nbinom.logpmf(values, size, prob).sum())
    nll_p = float(-stats.poisson.logpmf(values, mean).sum())
    return {
        "nb_mean": round(mean, 4), "nb_size": round(size, 3),
        "poisson_nll": round(nll_p, 3), "nb_nll": round(nll_nb, 3),
        "poisson_aic": round(2 * 1 + 2 * nll_p, 3),
        "nb_aic": round(2 * 2 + 2 * nll_nb, 3),
    }


def dispersion_report(values: np.ndarray, label: str) -> dict[str, Any]:
    """Mean/variance behaviour, overdispersion test and goodness of fit."""
    n = len(values)
    mean = float(values.mean())
    var = float(values.var(ddof=1))
    # Variance test: (n-1) s^2 / mean ~ chi-square(n-1) under Poisson.
    test_stat = (n - 1) * var / mean
    p_disp = float(stats.chi2.sf(test_stat, n - 1))
    gof = _chi2_gof(values, mean)
    nb = _nb_aic(values)
    return {
        "quantity": label,
        "n": n,
        "mean": round(mean, 4),
        "variance": round(var, 4),
        "dispersion_index_var_over_mean": round(var / mean, 4),
        "overdispersion_test_statistic": round(test_stat, 3),
        "overdispersion_p_value": round(p_disp, 4),
        "overdispersed_at_5pct": bool(p_disp < 0.05),
        "chi_square_gof": gof,
        "negative_binomial_comparison": nb,
        "poisson_preferred_by_aic": bool(nb["poisson_aic"] <= nb["nb_aic"]),
        "note": ("Chi-square bins are pooled from the right so every expected count is at "
                 "least 5; df accounts for one estimated parameter (the mean)."),
    }


def run_diagnostics(game_log: pd.DataFrame) -> dict[str, Any]:
    gf = game_log["goals_for_reg"].to_numpy(dtype=float)
    ga = game_log["goals_against_reg"].to_numpy(dtype=float)
    return {
        "season": str(game_log["season"].iloc[0]),
        "goals_for": dispersion_report(gf, "regulation goals for"),
        "goals_against": dispersion_report(ga, "regulation goals against"),
        "independence_caveat": ("Goals for and goals against in the same game are not "
                                "independent in reality; the model treats them as independent "
                                "Poisson draws, which is a documented approximation."),
    }


# --------------------------------------------------------------------------- simulation
@dataclass
class ScenarioSpec:
    """A fully resolved scenario: rates plus provenance."""

    scenario_id: str
    name: str
    family: str
    lambda_gf: float
    lambda_ga: float
    details: dict[str, Any]

    def validate(self) -> None:
        if not (self.lambda_gf > 0 and self.lambda_ga > 0):
            raise ValueError(f"{self.scenario_id}: goal rates must be positive")


def expected_points(rates: Rates, lambda_gf: float, lambda_ga: float) -> float:
    """Analytic expected points, used as an independent check on the Monte Carlo."""
    grid = np.arange(0, 25)
    px = stats.poisson.pmf(grid, lambda_gf)     # Dallas goals
    py = stats.poisson.pmf(grid, lambda_ga)     # opponent goals
    joint = np.outer(px, py)
    win = float(np.tril(joint, -1).sum())       # X > Y
    loss = float(np.triu(joint, 1).sum())       # X < Y
    tie = float(np.trace(joint))                # X == Y
    p = rates.p_win_if_tied
    return GAMES_PER_SEASON * (2.0 * win + tie * (2.0 * p + 1.0 * (1.0 - p)) + 0.0 * loss)


def simulate_seasons(spec: ScenarioSpec, rates: Rates, n_seasons: int, seed: int,
                     n_games: int = GAMES_PER_SEASON) -> dict[str, np.ndarray]:
    """Vectorised Monte Carlo of complete regular seasons.

    Returns season-level arrays. Goal differential is stored twice:
    regulation differential (audit) and final hockey differential (adds the OT
    winner's deciding goal, never a shootout goal).
    """
    spec.validate()
    if n_seasons < 1:
        raise ValueError("n_seasons must be >= 1")
    rng = np.random.default_rng(seed)
    gf = rng.poisson(spec.lambda_gf, size=(n_seasons, n_games))
    ga = rng.poisson(spec.lambda_ga, size=(n_seasons, n_games))

    tied = gf == ga
    n_tied = tied.sum(axis=1)
    # Which tied games does Dallas win, and which of those go to overtime?
    tie_win = (rng.random((n_seasons, n_games)) < rates.p_win_if_tied) & tied
    tie_loss = tied & ~tie_win
    in_ot = rng.random((n_seasons, n_games)) < rates.p_ot_given_tied

    wins = (gf > ga).sum(axis=1) + tie_win.sum(axis=1)
    otl = tie_loss.sum(axis=1)
    reg_losses = (gf < ga).sum(axis=1)

    reg_diff = (gf - ga).sum(axis=1)
    ot_decider = ((tie_win & in_ot).sum(axis=1) - (tie_loss & in_ot).sum(axis=1))
    final_diff = reg_diff + ot_decider
    points = 2 * wins + otl

    # Invariants: checked here as well as in the test suite.
    assert np.all(wins + reg_losses + otl == n_games)
    assert np.all(points == 2 * wins + otl)

    return {
        "points": points.astype(np.int16),
        "wins": wins.astype(np.int16),
        "regulation_losses": reg_losses.astype(np.int16),
        "ot_losses": otl.astype(np.int16),
        "regulation_goal_differential": reg_diff.astype(np.int16),
        "final_hockey_goal_differential": final_diff.astype(np.int16),
    }


def summarize(samples: dict[str, np.ndarray], thresholds: list[int]) -> dict[str, Any]:
    """Distribution summary. Intervals are simulation intervals, not CIs."""
    pts = samples["points"].astype(float)
    out: dict[str, Any] = {
        "mean_points": round(float(pts.mean()), 3),
        "median_points": round(float(np.median(pts)), 3),
        "sd_points": round(float(pts.std(ddof=1)), 3),
        "points_p10": int(np.percentile(pts, 10)),
        "points_p90": int(np.percentile(pts, 90)),
        "points_p2_5": int(np.percentile(pts, 2.5)),
        "points_p97_5": int(np.percentile(pts, 97.5)),
        "interval_80": [int(np.percentile(pts, 10)), int(np.percentile(pts, 90))],
        "interval_95": [int(np.percentile(pts, 2.5)), int(np.percentile(pts, 97.5))],
        "mean_wins": round(float(samples["wins"].mean()), 3),
        "mean_regulation_losses": round(float(samples["regulation_losses"].mean()), 3),
        "mean_ot_losses": round(float(samples["ot_losses"].mean()), 3),
        "mean_regulation_goal_differential": round(
            float(samples["regulation_goal_differential"].mean()), 3),
        "mean_final_hockey_goal_differential": round(
            float(samples["final_hockey_goal_differential"].mean()), 3),
        "n_seasons": int(len(pts)),
        "interval_label": ("80%/95% simulation (prediction) intervals conditional on the model; "
                           "not confidence intervals for an estimated mean"),
    }
    for t in thresholds:
        out[f"prob_at_least_{t}_points"] = round(float((pts >= t).mean()), 4)
    return out
