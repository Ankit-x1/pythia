"""Command-line interface.

    python -m stars_forecast collect-data
    python -m stars_forecast validate-data
    python -m stars_forecast data-report
    python -m stars_forecast run-all --n-seasons 10000 --seed 3315

Imports are lazy so a missing optional dependency for one command never breaks
the others.
"""
from __future__ import annotations

import argparse
import json
import sys

from .paths import QA, rel


def _print(obj) -> None:
    print(json.dumps(obj, indent=2))


def cmd_collect_data(args: argparse.Namespace) -> int:
    from .collect import run_collect
    summary = run_collect()
    print("Collected datasets A-G")
    _print(summary)
    return 0


def cmd_validate_data(args: argparse.Namespace) -> int:
    from .validate import run_validation
    result = run_validation()
    print(f"{result['n_passed']}/{result['n_checks']} checks passed")
    for c in result["checks"]:
        if not c["passed"]:
            print(f"  FAIL  {c['check']}: {c['detail']}")
    print(f"evidence: {rel(QA / 'data-validation.json')}")
    return 0 if result["all_passed"] else 1


def cmd_data_report(args: argparse.Namespace) -> int:
    from .datareport import write_data_report
    path = write_data_report()
    print(f"wrote {rel(path)}")
    return 0


def cmd_run_all(args: argparse.Namespace) -> int:
    from .pipeline import run_all
    result = run_all(n_seasons=args.n_seasons, seed=args.seed)
    _print({k: v for k, v in result.items() if not k.startswith("_") and k != "scenarios"})
    print("\nscenario means (points):")
    for sid, row in result["scenarios"].items():
        print(f"  {sid:5s} {row['name'][:48]:48s} {row['mean_points']:6.2f}")
    return 0 if result.get("ok", True) else 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="stars-forecast", description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("collect-data", help="download and cache all source data").set_defaults(
        func=cmd_collect_data)
    sub.add_parser("validate-data", help="run automated data validation").set_defaults(
        func=cmd_validate_data)
    sub.add_parser("data-report", help="regenerate docs/data-report.md").set_defaults(
        func=cmd_data_report)

    ra = sub.add_parser("run-all", help="diagnostics, scenarios, backtest, figures, tables")
    ra.add_argument("--n-seasons", type=int, default=None)
    ra.add_argument("--seed", type=int, default=None)
    ra.set_defaults(func=cmd_run_all)

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
