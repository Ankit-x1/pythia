import pandas as pd

from stars_forecast.datareport import _md_table


def test_markdown_table_dependency_is_available():
    rendered = _md_table(pd.DataFrame({"value": [1]}))

    assert rendered.splitlines()[0].strip("| ") == "value"
