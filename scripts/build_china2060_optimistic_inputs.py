"""Build a China 2030/2060 optimistic-effort scenario package.

This is not a forecast. It is a policy-and-technology effort case aligned with
China's dual-carbon framing: CO2 emissions peak before 2030 and carbon
neutrality before 2060. The tables define what must improve for profitability,
then the scan determines when each pathway becomes positive under those efforts.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
PROCESSED = DATA / "processed"


DUAL_CARBON_URL = "https://en.ndrc.gov.cn/policies/202110/t20211024_1300725.html"
IRENA_H2_URL = "https://www.irena.org/Energy-Transition/Technology/Hydrogen/Electrolyser-costs"
CDR_FYI_URL = "https://www.cdr.fyi/blog/2024-year-in-review"
EIA_JET_URL = "https://www.eia.gov/dnav/pet/hist/LeafHandler.ashx?f=w&n=pet&s=eer_epjk_pf4_rgc_dpg"
SAF_EKEROSENE_URL = "https://www.sciencedirect.com/science/article/pii/S0196890425008787"


YEARS = [2030, 2035, 2040, 2045, 2050, 2055, 2060]


EFFORTS = {
    2030: {
        "electricity_price_usd_per_mwh": 28.0,
        "grid_emissions_kgco2e_per_mwh": 120.0,
        "h2_price_usd_per_kg": 2.20,
        "h2_emissions_kgco2e_per_kg": 1.20,
        "carbon_price_usd_per_tco2": 60.0,
        "carbon_tax_usd_per_tco2": 20.0,
        "durable_removal_credit_usd_per_tco2": 120.0,
        "discount_rate": 0.075,
    },
    2035: {
        "electricity_price_usd_per_mwh": 22.0,
        "grid_emissions_kgco2e_per_mwh": 70.0,
        "h2_price_usd_per_kg": 1.50,
        "h2_emissions_kgco2e_per_kg": 0.55,
        "carbon_price_usd_per_tco2": 130.0,
        "carbon_tax_usd_per_tco2": 45.0,
        "durable_removal_credit_usd_per_tco2": 220.0,
        "discount_rate": 0.070,
    },
    2040: {
        "electricity_price_usd_per_mwh": 18.0,
        "grid_emissions_kgco2e_per_mwh": 45.0,
        "h2_price_usd_per_kg": 0.95,
        "h2_emissions_kgco2e_per_kg": 0.30,
        "carbon_price_usd_per_tco2": 190.0,
        "carbon_tax_usd_per_tco2": 75.0,
        "durable_removal_credit_usd_per_tco2": 290.0,
        "discount_rate": 0.065,
    },
    2045: {
        "electricity_price_usd_per_mwh": 14.0,
        "grid_emissions_kgco2e_per_mwh": 25.0,
        "h2_price_usd_per_kg": 0.78,
        "h2_emissions_kgco2e_per_kg": 0.18,
        "carbon_price_usd_per_tco2": 240.0,
        "carbon_tax_usd_per_tco2": 100.0,
        "durable_removal_credit_usd_per_tco2": 340.0,
        "discount_rate": 0.060,
    },
    2050: {
        "electricity_price_usd_per_mwh": 11.0,
        "grid_emissions_kgco2e_per_mwh": 15.0,
        "h2_price_usd_per_kg": 0.65,
        "h2_emissions_kgco2e_per_kg": 0.10,
        "carbon_price_usd_per_tco2": 280.0,
        "carbon_tax_usd_per_tco2": 125.0,
        "durable_removal_credit_usd_per_tco2": 380.0,
        "discount_rate": 0.058,
    },
    2055: {
        "electricity_price_usd_per_mwh": 9.0,
        "grid_emissions_kgco2e_per_mwh": 8.0,
        "h2_price_usd_per_kg": 0.58,
        "h2_emissions_kgco2e_per_kg": 0.07,
        "carbon_price_usd_per_tco2": 320.0,
        "carbon_tax_usd_per_tco2": 145.0,
        "durable_removal_credit_usd_per_tco2": 430.0,
        "discount_rate": 0.055,
    },
    2060: {
        "electricity_price_usd_per_mwh": 8.0,
        "grid_emissions_kgco2e_per_mwh": 5.0,
        "h2_price_usd_per_kg": 0.52,
        "h2_emissions_kgco2e_per_kg": 0.05,
        "carbon_price_usd_per_tco2": 360.0,
        "carbon_tax_usd_per_tco2": 165.0,
        "durable_removal_credit_usd_per_tco2": 480.0,
        "discount_rate": 0.055,
    },
}


PRODUCT_BASE = {
    "none": {"grade": "none", "market": "none", "volume": 0},
    "carbonate_product": {"grade": "aggregate", "market": "china", "volume": 700_000_000},
    "carbon_monoxide": {"grade": "chemical_grade", "market": "china", "volume": 35_000_000},
    "methanol": {"grade": "chemical_grade", "market": "china", "volume": 180_000_000},
    "formic_acid_equivalent": {"grade": "industrial_grade", "market": "china", "volume": 18_000_000},
    "ethylene": {"grade": "polymer_grade", "market": "china", "volume": 45_000_000},
    "methane": {"grade": "grid_grade", "market": "china", "volume": 350_000_000},
    "sustainable_aviation_fuel": {"grade": "astm_blending_component", "market": "china", "volume": 80_000_000},
}


PRICE_CURVES = {
    "none": {year: (0.0, 0.0, 0.0) for year in YEARS},
    "carbonate_product": {
        2030: (0.010, 0.025, 0.060),
        2035: (0.012, 0.035, 0.080),
        2040: (0.014, 0.045, 0.100),
        2045: (0.016, 0.055, 0.120),
        2050: (0.018, 0.065, 0.135),
        2055: (0.020, 0.075, 0.150),
        2060: (0.022, 0.085, 0.165),
    },
    "carbon_monoxide": {
        2030: (0.20, 0.45, 0.90),
        2035: (0.24, 0.65, 1.20),
        2040: (0.28, 0.85, 1.60),
        2045: (0.32, 1.00, 1.90),
        2050: (0.35, 1.10, 2.20),
        2055: (0.38, 1.20, 2.40),
        2060: (0.40, 1.30, 2.60),
    },
    "methanol": {
        2030: (0.32, 0.65, 1.05),
        2035: (0.34, 0.75, 1.20),
        2040: (0.36, 0.85, 1.40),
        2045: (0.38, 0.95, 1.60),
        2050: (0.40, 1.05, 1.80),
        2055: (0.42, 1.12, 1.95),
        2060: (0.45, 1.20, 2.10),
    },
    "formic_acid_equivalent": {
        2030: (0.55, 0.95, 1.80),
        2035: (0.65, 1.25, 2.30),
        2040: (0.75, 1.60, 2.90),
        2045: (0.85, 1.90, 3.40),
        2050: (0.95, 2.20, 3.90),
        2055: (1.05, 2.45, 4.30),
        2060: (1.10, 2.70, 4.70),
    },
    "ethylene": {
        2030: (0.80, 1.15, 2.00),
        2035: (0.85, 1.30, 2.30),
        2040: (0.90, 1.50, 2.80),
        2045: (0.95, 1.70, 3.20),
        2050: (1.00, 1.90, 3.60),
        2055: (1.05, 2.10, 4.00),
        2060: (1.10, 2.30, 4.50),
    },
    "methane": {
        2030: (0.40, 0.85, 1.80),
        2035: (0.45, 1.05, 2.20),
        2040: (0.50, 1.25, 2.70),
        2045: (0.55, 1.45, 3.10),
        2050: (0.60, 1.60, 3.50),
        2055: (0.65, 1.75, 3.80),
        2060: (0.70, 1.90, 4.10),
    },
    "sustainable_aviation_fuel": {
        2030: (1.25, 2.10, 4.00),
        2035: (1.50, 3.20, 6.00),
        2040: (1.75, 4.40, 8.50),
        2045: (2.00, 5.40, 10.50),
        2050: (2.20, 6.30, 12.00),
        2055: (2.30, 6.80, 13.00),
        2060: (2.40, 7.20, 14.00),
    },
}


LEARNING = {
    2030: {"all": (0.92, 0.95, 0.97), "storage": (0.90, 0.94, 0.96), "mineralization": (0.88, 0.92, 0.95), "thermochemical": (0.86, 0.90, 0.94), "electrochemical": (0.70, 0.80, 0.88), "photochemical": (0.70, 0.82, 0.90)},
    2035: {"all": (0.85, 0.90, 0.94), "storage": (0.82, 0.88, 0.93), "mineralization": (0.76, 0.84, 0.91), "thermochemical": (0.72, 0.82, 0.90), "electrochemical": (0.52, 0.68, 0.80), "photochemical": (0.50, 0.68, 0.80)},
    2040: {"all": (0.78, 0.86, 0.92), "storage": (0.75, 0.85, 0.90), "mineralization": (0.66, 0.78, 0.88), "thermochemical": (0.60, 0.74, 0.86), "electrochemical": (0.38, 0.56, 0.72), "photochemical": (0.34, 0.52, 0.70)},
    2045: {"all": (0.72, 0.82, 0.90), "storage": (0.70, 0.82, 0.88), "mineralization": (0.58, 0.72, 0.85), "thermochemical": (0.50, 0.66, 0.80), "electrochemical": (0.28, 0.46, 0.64), "photochemical": (0.24, 0.40, 0.60)},
    2050: {"all": (0.66, 0.78, 0.88), "storage": (0.66, 0.80, 0.86), "mineralization": (0.50, 0.66, 0.82), "thermochemical": (0.42, 0.58, 0.74), "electrochemical": (0.21, 0.36, 0.56), "photochemical": (0.18, 0.32, 0.52)},
    2055: {"all": (0.60, 0.75, 0.86), "storage": (0.62, 0.78, 0.85), "mineralization": (0.44, 0.60, 0.78), "thermochemical": (0.36, 0.52, 0.70), "electrochemical": (0.17, 0.30, 0.50), "photochemical": (0.14, 0.26, 0.46)},
    2060: {"all": (0.56, 0.72, 0.84), "storage": (0.60, 0.76, 0.84), "mineralization": (0.40, 0.56, 0.74), "thermochemical": (0.32, 0.46, 0.66), "electrochemical": (0.14, 0.25, 0.44), "photochemical": (0.12, 0.22, 0.40)},
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        extra = row.pop(None, None)
        if extra:
            row["notes"] = (row.get("notes", "") + "," + ",".join(value for value in extra if value)).strip(",")
    return rows


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def build_effort_table() -> None:
    rows = []
    for year, values in EFFORTS.items():
        rows.append(
            {
                "year": year,
                **values,
                "evidence_basis": (
                    "dual-carbon target from China State Council; H2/electrolyser effort from IRENA; "
                    "durable CDR credit anchored to current durable CDR market observations; SAF price effort from e-fuel TEA literature"
                ),
                "source_url": f"{DUAL_CARBON_URL}; {IRENA_H2_URL}; {CDR_FYI_URL}; {SAF_EKEROSENE_URL}",
                "scenario_type": "optimistic_effort_not_forecast",
            }
        )
    write_csv(DATA / "china2060_optimistic_effort_scenario.csv", rows)


def build_product_prices() -> None:
    rows = []
    for year in YEARS:
        for product, meta in PRODUCT_BASE.items():
            low, base, high = PRICE_CURVES[product][year]
            volume = meta["volume"]
            if product == "sustainable_aviation_fuel":
                volume = int(volume * (0.25 + 0.75 * (year - 2030) / 30))
            rows.append(
                {
                    "year": year,
                    "region": "all",
                    "product": product,
                    "grade": meta["grade"],
                    "market_type": meta["market"],
                    "price_low_usd_per_kg": low,
                    "price_base_usd_per_kg": base,
                    "price_high_usd_per_kg": high,
                    "price_distribution": "triangular",
                    "price_driver": "china_2060_policy_backed_offtake",
                    "volume_limit_t_per_year": volume,
                    "source": "china2060_optimistic_effort",
                    "notes": "Optimistic policy-backed offtake scenario; not a commodity-price forecast.",
                    "evidence_grade": "C_scenario",
                    "source_url": f"{EIA_JET_URL}; {SAF_EKEROSENE_URL}",
                }
            )
    write_csv(DATA / "product_prices_china2060_optimistic.csv", rows)


def build_policy_rules() -> None:
    rows = []
    for start, end, saf_premium, clean_fuel_credit, eligibility in [
        (2030, 2034, 0.60, 0.20, 0.50),
        (2035, 2039, 1.20, 0.35, 0.60),
        (2040, 2044, 1.80, 0.50, 0.70),
        (2045, 2049, 2.20, 0.65, 0.78),
        (2050, 2054, 2.50, 0.80, 0.82),
        (2055, 2060, 2.80, 0.90, 0.85),
    ]:
        rows.append(
            {
                "policy_id": f"china_saf_dual_carbon_{start}_{end}",
                "jurisdiction": "China",
                "target_market": "china",
                "product": "sustainable_aviation_fuel",
                "pathway": "all",
                "start_year": start,
                "end_year": end,
                "credit_usd_per_tco2_avoided": 0,
                "durable_credit_usd_per_tco2": 0,
                "carbon_tax_usd_per_tco2": 0,
                "saf_premium_usd_per_kg": saf_premium,
                "clean_fuel_credit_usd_per_kg": clean_fuel_credit,
                "eligibility_fraction": eligibility,
                "stacking_allowed": "true",
                "certificate_transfer_allowed": "true",
                "notes": "Optimistic China SAF/RFNBO-style mandate proxy for dual-carbon aviation decarbonization.",
            }
        )
    write_csv(DATA / "policy_eligibility_rules_china2060_optimistic.csv", rows)


def build_learning_rows() -> None:
    rows = []
    for year, selectors in LEARNING.items():
        for selector, values in selectors.items():
            selector_type = "all" if selector == "all" else "technology_family"
            capex, fixed, variable = values
            rows.append(
                {
                    "year": year,
                    "selector_type": selector_type,
                    "selector": selector,
                    "capex_multiplier": capex,
                    "fixed_opex_multiplier": fixed,
                    "variable_opex_multiplier": variable,
                    "notes": "Optimistic learning effort scenario. Electrochemical reduction is directionally supported by electrolyser cost-learning evidence but remains a CO2-electrolyzer extrapolation.",
                }
            )
    write_csv(DATA / "technology_scenarios_china2060_optimistic.csv", rows)


def build_reliability_rows() -> None:
    base_rows = read_csv(DATA / "technology_reliability_evidence_upgraded.csv")
    rows: list[dict[str, Any]] = []
    future_adjustments = {
        "electrolysis_to_co": {
            2040: (0.84, 12000, 0.16, 0.018, 0.22),
            2050: (0.88, 30000, 0.10, 0.010, 0.16),
            2060: (0.90, 50000, 0.08, 0.007, 0.12),
        },
        "electrolysis_to_formate": {
            2040: (0.86, 20000, 0.14, 0.012, 0.20),
            2050: (0.90, 40000, 0.09, 0.008, 0.14),
            2060: (0.92, 60000, 0.07, 0.006, 0.11),
        },
        "electrolysis_to_ethylene": {
            2040: (0.76, 6000, 0.25, 0.030, 0.34),
            2050: (0.82, 16000, 0.18, 0.020, 0.25),
            2060: (0.86, 30000, 0.13, 0.014, 0.20),
        },
        "photocatalytic_to_co": {
            2040: (0.68, 0, 0.30, 0.045, 0.42),
            2050: (0.76, 0, 0.22, 0.028, 0.30),
            2060: (0.82, 0, 0.16, 0.020, 0.24),
        },
        "photoelectrochemical_to_formate": {
            2040: (0.70, 0, 0.28, 0.040, 0.40),
            2050: (0.78, 0, 0.20, 0.026, 0.29),
            2060: (0.84, 0, 0.15, 0.018, 0.23),
        },
    }
    for row in base_rows:
        rows.append(row)
        pathway = row["pathway"]
        if pathway not in future_adjustments:
            continue
        for year, values in future_adjustments[pathway].items():
            availability, stack_life, replacement, degradation, contingency = values
            future = dict(row)
            future.update(
                {
                    "year": year,
                    "availability_fraction": availability,
                    "stack_lifetime_hours": stack_life,
                    "replacement_cost_fraction": replacement,
                    "performance_degradation_per_year": degradation,
                    "contingency_fraction": contingency,
                    "notes": "Optimistic reliability effort case for China 2060; requires demonstrated stack lifetime and manufacturable replacement cost.",
                    "evidence_grade": "D_scenario_target",
                }
            )
            rows.append(future)
    write_csv(DATA / "technology_reliability_china2060_optimistic.csv", rows)


def build_source_notes() -> None:
    rows = [
        {
            "source_id": "china_dual_carbon_policy",
            "claim": "China policy framing is CO2 emissions peak before 2030 and carbon neutrality before 2060.",
            "source_url": DUAL_CARBON_URL,
            "model_use": "sets 2030-2060 time axis",
        },
        {
            "source_id": "irena_h2_cost_effort",
            "claim": "Electrolyser cost reductions and low-cost renewable power can push green hydrogen toward low-cost ranges in best locations.",
            "source_url": IRENA_H2_URL,
            "model_use": "supports optimistic H2 cost effort curve",
        },
        {
            "source_id": "cdr_fyi_durable_credit_anchor",
            "claim": "CDR.fyi reports publicly disclosed durable CDR order pricing falling from about 490 USD/t in 2023 to about 320 USD/t in 2024.",
            "source_url": CDR_FYI_URL,
            "model_use": "supports high-credit CDR sensitivity, not a China policy forecast",
        },
        {
            "source_id": "e_saf_literature_cost_anchor",
            "claim": "Recent e-kerosene literature reports multi-USD/kg costs and high sensitivity to electricity and hydrogen.",
            "source_url": SAF_EKEROSENE_URL,
            "model_use": "supports high SAF offtake/mandate price sensitivity",
        },
    ]
    write_csv(PROCESSED / "policy" / "china2060_optimistic_source_notes.csv", rows)


def main() -> None:
    build_effort_table()
    build_product_prices()
    build_policy_rules()
    build_learning_rows()
    build_reliability_rows()
    build_source_notes()
    print("Wrote China 2030/2060 optimistic-effort input tables.")


if __name__ == "__main__":
    main()
