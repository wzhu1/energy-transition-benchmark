"""Download energy and emissions indicators for G20 economies from the World Bank
World Development Indicators API (public, no key required) and cache them as a
tidy CSV in data/wdi_g20.csv."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
API = "https://api.worldbank.org/v2/country/{countries}/indicator/{indicator}"

# EG.USE.COMM.FO.ZS (fossil fuel share) is deliberately excluded: the WDI series
# stops in 2015 and later years are filled with 0.0 placeholders.

# G20 member economies (the EU and African Union are blocs, not countries, so they are left out).
COUNTRIES = ["ARG", "AUS", "BRA", "CAN", "CHN", "DEU", "FRA", "GBR", "IDN", "IND",
             "ITA", "JPN", "KOR", "MEX", "RUS", "SAU", "TUR", "USA", "ZAF"]

INDICATORS = {
    "EG.FEC.RNEW.ZS": "renewable_share",        # % of final energy consumption
    "EG.ELC.RNEW.ZS": "renewable_electricity",  # % of electricity output
    "EG.EGY.PRIM.PP.KD": "energy_intensity",    # MJ per $2021 PPP of GDP
    "EN.GHG.CO2.PC.CE.AR5": "co2_per_capita",   # t CO2e per person, excl. LULUCF
    "NY.GDP.PCAP.PP.KD": "gdp_per_capita",      # constant 2021 PPP $
}


def fetch_indicator(code: str, start: int = 2000, end: int = 2024) -> pd.DataFrame:
    url = API.format(countries=";".join(COUNTRIES), indicator=code)
    resp = requests.get(url, params={"format": "json", "date": f"{start}:{end}", "per_page": 2000}, timeout=60)
    resp.raise_for_status()
    meta, rows = resp.json()
    assert meta["pages"] == 1, "increase per_page"
    return pd.DataFrame(
        {"iso3": r["countryiso3code"], "country": r["country"]["value"], "year": int(r["date"]),
         "indicator": INDICATORS[code], "value": r["value"]}
        for r in rows
    )


def main() -> None:
    frames = [fetch_indicator(code) for code in INDICATORS]
    tidy = pd.concat(frames).dropna(subset=["value"]).sort_values(["iso3", "indicator", "year"])
    out = ROOT / "data"
    out.mkdir(exist_ok=True)
    tidy.to_csv(out / "wdi_g20.csv", index=False)
    print(f"wrote {len(tidy):,} observations for {tidy.iso3.nunique()} countries to {out / 'wdi_g20.csv'}")
    print(tidy.groupby("indicator").year.max().rename("latest_year").to_string())


if __name__ == "__main__":
    main()
