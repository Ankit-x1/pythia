# Pythia — Dallas Stars 2026–27 Season Forecast

A simple, honest forecast of how many standings points the **Dallas Stars** are likely to earn in the 2026–27 NHL season, built entirely from real, checked NHL data.

**Headline result:** ~**106 points** if Dallas repeat last season's form (likely range **95–116**), with a **78% chance of 100+ points**. The biggest lever is goaltending: stopping 1% more shots is worth about **+7 points**.

> Full project, source code and documentation: **[`dallas-stars-forecast/`](dallas-stars-forecast/)**

## What's in this repo

| Folder                                              | Contents                                                                            |
| --------------------------------------------------- | ----------------------------------------------------------------------------------- |
| [`dallas-stars-forecast/`](dallas-stars-forecast/) | The complete project — source code, data, model outputs, figures, tests and docs   |
| [`graphify-out/`](graphify-out/)                   | Interactive graph of the codebase — open `graph.html` in a browser to explore it |

## Detail

- **Method in plain words:** last season's scoring rates (3.26 scored / 2.61 allowed per 60 min) are used to play the 82-game season 10,000 times per case across 18 scenarios — see [`dallas-stars-forecast/README.md`](dallas-stars-forecast/README.md) and `dallas-stars-forecast/docs/`.
- **Verified:** All data checks, all tests passing, and a frozen backtest (forecast 106 vs actual 112 for 2025–26) with no re-tuning.
- **Data sources:** NHL official stats/API and Hockey-Reference cross-checks, all cited in the project docs.
