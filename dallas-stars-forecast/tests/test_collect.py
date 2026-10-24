import pandas as pd

from stars_forecast.collect import collect_hr_crosscheck
from stars_forecast.fetch import Manifest


def test_hockey_reference_crosscheck_parses_cached_html(monkeypatch, tmp_path):
    html = """
    <table>
      <thead><tr><th>Date</th><th>Opponent</th><th>GF</th><th>GA</th></tr></thead>
      <tbody><tr><td>2025-10-01</td><td>AAA</td><td>4</td><td>2</td></tr></tbody>
    </table>
    """
    monkeypatch.setattr("stars_forecast.collect.fetch_text", lambda *args, **kwargs: html)
    monkeypatch.setattr("stars_forecast.collect.PROCESSED", tmp_path)
    game_log = pd.DataFrame([{
        "goals_for_final_hockey": 4,
        "goals_against_final_hockey": 2,
        "goals_for_displayed": 4,
        "goals_against_displayed": 2,
    }])

    result = collect_hr_crosscheck(game_log, "20252026", Manifest())

    assert result["available"]
    assert result["hr_rows"] == 1
    assert result["hr_sum_GF"] == 4
    assert result["hr_sum_GA"] == 2
    assert (tmp_path / "hr_crosscheck_2025_26.json").is_file()
