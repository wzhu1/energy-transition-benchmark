"""Benchmark G20 economies on where they stand and how fast they are moving on the
energy transition, and test for decoupling of growth from emissions."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

ROOT = Path(__file__).resolve().parents[1]
BASE_YEAR = 2010

# +1 means higher is better for the transition, -1 means lower is better.
DIRECTION = {
    "renewable_share": 1,
    "renewable_electricity": 1,
    "energy_intensity": -1,
    "co2_per_capita": -1,
}


def load(path: Path = ROOT / "data" / "wdi_g20.csv") -> pd.DataFrame:
    return pd.read_csv(path)


def latest_and_base(tidy: pd.DataFrame, base_year: int = BASE_YEAR) -> pd.DataFrame:
    """One row per country x indicator: base-year value, latest value and latest year."""
    latest = tidy.sort_values("year").groupby(["iso3", "indicator"]).tail(1)
    base = tidy[tidy.year == base_year][["iso3", "indicator", "value"]].rename(columns={"value": "base"})
    out = latest.rename(columns={"value": "latest", "year": "latest_year"}).merge(base, on=["iso3", "indicator"], how="left")
    return out[["iso3", "country", "indicator", "base", "latest", "latest_year"]]


def zscore(s: pd.Series) -> pd.Series:
    return (s - s.mean()) / s.std(ddof=0)


def scorecard(lb: pd.DataFrame) -> pd.DataFrame:
    """Level score = mean direction-adjusted z-score of latest values.
    Progress score = mean direction-adjusted z-score of change since the base year
    (percentage-point change for shares, % change for intensity and CO2)."""
    lb = lb[lb.indicator.isin(DIRECTION)].copy()
    shares = lb.indicator.isin(["renewable_share", "renewable_electricity"])
    lb["change"] = np.where(shares, lb.latest - lb.base, 100 * (lb.latest / lb.base - 1))
    level = lb.pivot(index="iso3", columns="indicator", values="latest")
    change = lb.pivot(index="iso3", columns="indicator", values="change")
    sign = pd.Series(DIRECTION)
    level_z = level.apply(zscore).mul(sign, axis=1)
    change_z = change.apply(zscore).mul(sign, axis=1)
    names = lb.drop_duplicates("iso3").set_index("iso3").country
    card = pd.DataFrame({
        "country": names,
        "level_score": level_z.mean(axis=1),
        "progress_score": change_z.mean(axis=1),
    }).join(level.add_suffix("_latest")).join(change.add_suffix("_chg"))
    return card.sort_values("level_score", ascending=False)


def decoupling(lb: pd.DataFrame) -> pd.DataFrame:
    wide = lb.pivot(index="iso3", columns="indicator", values=["base", "latest"])
    gdp = 100 * (wide[("latest", "gdp_per_capita")] / wide[("base", "gdp_per_capita")] - 1)
    co2 = 100 * (wide[("latest", "co2_per_capita")] / wide[("base", "co2_per_capita")] - 1)
    out = pd.DataFrame({"gdp_pc_growth_pct": gdp, "co2_pc_change_pct": co2})
    out["status"] = np.select(
        [gdp <= 0, co2 < 0, co2 < gdp],
        ["no income growth", "absolute decoupling", "relative decoupling"],
        default="coupled",
    )
    return out.sort_values("co2_pc_change_pct")


def emissions_model(lb: pd.DataFrame):
    """Cross-section: log CO2 per capita on log income, renewable share and energy intensity."""
    wide = lb.pivot(index="iso3", columns="indicator", values="latest")
    return smf.ols("np.log(co2_per_capita) ~ np.log(gdp_per_capita) + renewable_share + np.log(energy_intensity)", wide).fit(cov_type="HC1")


def plot(tidy: pd.DataFrame, card: pd.DataFrame, dec: pd.DataFrame) -> None:
    out = ROOT / "figures"
    out.mkdir(exist_ok=True)

    fig, ax = plt.subplots(figsize=(9, 7))
    ax.axhline(0, color="gray", lw=0.8)
    ax.axvline(0, color="gray", lw=0.8)
    ax.scatter(card.level_score, card.progress_score, s=50)
    for iso, r in card.iterrows():
        ax.annotate(iso, (r.level_score, r.progress_score), xytext=(4, 3), textcoords="offset points", fontsize=9)
    ax.set_xlabel("Level score (where they are now, z)")
    ax.set_ylabel(f"Progress score (change since {BASE_YEAR}, z)")
    ax.set_title("G20 energy-transition benchmark")
    for x, y, label in [(0.98, 0.98, "Leaders"), (0.02, 0.98, "Fast movers"), (0.02, 0.02, "Laggards"), (0.98, 0.02, "Stalling")]:
        ax.text(x, y, label, transform=ax.transAxes, ha="right" if x > 0.5 else "left",
                va="top" if y > 0.5 else "bottom", color="gray", fontsize=11, style="italic")
    fig.tight_layout()
    fig.savefig(out / "level_vs_progress.png", dpi=150)
    plt.close(fig)

    colors = {"absolute decoupling": "tab:green", "relative decoupling": "tab:orange", "coupled": "tab:red", "no income growth": "tab:gray"}
    fig, ax = plt.subplots(figsize=(9, 6))
    for status, g in dec.groupby("status"):
        ax.scatter(g.gdp_pc_growth_pct, g.co2_pc_change_pct, label=status, color=colors[status], s=50)
        for iso, r in g.iterrows():
            ax.annotate(iso, (r.gdp_pc_growth_pct, r.co2_pc_change_pct), xytext=(4, 3), textcoords="offset points", fontsize=9)
    num = dec[["gdp_pc_growth_pct", "co2_pc_change_pct"]]
    lim = [num.min().min() - 5, num.max().max() + 5]
    ax.plot(lim, lim, ls="--", color="gray", lw=0.8, label="CO2 grows as fast as GDP")
    ax.axhline(0, color="gray", lw=0.8)
    ax.set_xlabel(f"GDP per capita growth since {BASE_YEAR} (%)")
    ax.set_ylabel(f"CO2 per capita change since {BASE_YEAR} (%)")
    ax.set_title("Is growth decoupling from emissions?")
    ax.legend(fontsize=9)
    fig.tight_layout()
    fig.savefig(out / "decoupling.png", dpi=150)
    plt.close(fig)

    rs = tidy[tidy.indicator == "renewable_share"].pivot(index="year", columns="iso3", values="value")
    fig, ax = plt.subplots(figsize=(9, 5))
    for iso in ["BRA", "CAN", "CHN", "DEU", "GBR", "IND", "USA", "SAU"]:
        ax.plot(rs.index, rs[iso], label=iso, lw=1.8)
    ax.set_ylabel("Renewables, % of final energy consumption")
    ax.set_title("Renewable share of final energy, selected G20 economies")
    ax.legend(ncol=4, fontsize=9)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(out / "renewable_share_trend.png", dpi=150)
    plt.close(fig)


def main() -> None:
    tidy = load()
    lb = latest_and_base(tidy)
    card = scorecard(lb)
    dec = decoupling(lb)
    model = emissions_model(lb)
    plot(tidy, card, dec)

    reports = ROOT / "reports"
    reports.mkdir(exist_ok=True)
    card.round(3).to_csv(reports / "scorecard.csv")
    dec.round(2).to_csv(reports / "decoupling.csv")
    (reports / "emissions_model.txt").write_text(str(model.summary()))

    print("Latest year per indicator:\n", lb.groupby("indicator").latest_year.max().to_string())
    print("\nScorecard\n", card[["country", "level_score", "progress_score"]].round(2).to_string())
    print("\nDecoupling\n", dec.round(1).to_string())
    print("\nEmissions model\n", model.params.round(3).to_string(), "\nR2 =", round(model.rsquared, 3))


if __name__ == "__main__":
    main()
