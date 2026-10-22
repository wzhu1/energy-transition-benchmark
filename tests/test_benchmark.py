import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from benchmark import decoupling, latest_and_base, scorecard  # noqa: E402


def toy():
    rows = []
    # A: clean and improving, B: dirty and worsening, C: in between.
    spec = {
        "A": dict(renewable_share=(20, 40), renewable_electricity=(30, 60), energy_intensity=(5, 3), co2_per_capita=(8, 4), gdp_per_capita=(100, 120)),
        "B": dict(renewable_share=(5, 4), renewable_electricity=(10, 9), energy_intensity=(8, 9), co2_per_capita=(10, 12), gdp_per_capita=(100, 110)),
        "C": dict(renewable_share=(10, 15), renewable_electricity=(20, 25), energy_intensity=(6, 5), co2_per_capita=(9, 8), gdp_per_capita=(100, 95)),
    }
    for iso, inds in spec.items():
        for ind, (base, latest) in inds.items():
            rows += [{"iso3": iso, "country": iso, "year": 2010, "indicator": ind, "value": base},
                     {"iso3": iso, "country": iso, "year": 2021, "indicator": ind, "value": latest}]
    return pd.DataFrame(rows)


def test_latest_and_base_picks_correct_years():
    lb = latest_and_base(toy())
    row = lb[(lb.iso3 == "A") & (lb.indicator == "co2_per_capita")].iloc[0]
    assert (row.base, row.latest, row.latest_year) == (8, 4, 2021)


def test_scorecard_orders_countries_sensibly():
    card = scorecard(latest_and_base(toy()))
    assert list(card.index) == ["A", "C", "B"]
    assert card.loc["A", "progress_score"] > 0 > card.loc["B", "progress_score"]


def test_decoupling_classification():
    dec = decoupling(latest_and_base(toy()))
    assert dec.loc["A", "status"] == "absolute decoupling"
    assert dec.loc["B", "status"] == "coupled"  # CO2 +20% outpaces GDP +10%
    assert dec.loc["C", "status"] == "no income growth"
