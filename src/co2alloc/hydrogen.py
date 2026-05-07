"""Hydrogen supply model for spatial CO2 allocation."""

from __future__ import annotations

from dataclasses import dataclass

from .constants import capital_recovery_factor


@dataclass(frozen=True, slots=True)
class HydrogenSupply:
    mode: str
    price_usd_per_kg: float
    emissions_kgco2e_per_kg: float
    electricity_kwh_per_kg: float = 0.0
    water_l_per_kg: float = 0.0


def market_hydrogen(
    price_usd_per_kg: float,
    emissions_kgco2e_per_kg: float,
) -> HydrogenSupply:
    return HydrogenSupply(
        mode="market",
        price_usd_per_kg=price_usd_per_kg,
        emissions_kgco2e_per_kg=emissions_kgco2e_per_kg,
    )


def electrolytic_hydrogen(
    electricity_price_usd_per_mwh: float,
    grid_emissions_kgco2e_per_mwh: float,
    electrolyzer_capex_usd_per_kw: float,
    electrolyzer_kwh_per_kg: float,
    electrolyzer_capacity_factor: float,
    electrolyzer_lifetime_years: int,
    discount_rate: float,
    fixed_om_fraction_of_capex_per_year: float,
    water_l_per_kg: float,
    water_price_usd_per_m3: float,
    water_emissions_kgco2e_per_m3: float,
    compression_storage_cost_usd_per_kg: float,
) -> HydrogenSupply:
    if electrolyzer_kwh_per_kg <= 0:
        raise ValueError("electrolyzer_kwh_per_kg must be positive")
    if electrolyzer_capacity_factor <= 0:
        raise ValueError("electrolyzer_capacity_factor must be positive")
    crf = capital_recovery_factor(discount_rate, electrolyzer_lifetime_years)
    annual_kg_per_kw = electrolyzer_capacity_factor * 8760.0 / electrolyzer_kwh_per_kg
    capex_cost = electrolyzer_capex_usd_per_kw * crf / annual_kg_per_kw
    fixed_om_cost = (
        electrolyzer_capex_usd_per_kw
        * fixed_om_fraction_of_capex_per_year
        / annual_kg_per_kw
    )
    electricity_cost = electrolyzer_kwh_per_kg / 1000.0 * electricity_price_usd_per_mwh
    water_m3_per_kg = water_l_per_kg / 1000.0
    water_cost = water_m3_per_kg * water_price_usd_per_m3
    price = capex_cost + fixed_om_cost + electricity_cost + water_cost + compression_storage_cost_usd_per_kg

    emissions = (
        electrolyzer_kwh_per_kg / 1000.0 * grid_emissions_kgco2e_per_mwh
        + water_m3_per_kg * water_emissions_kgco2e_per_m3
    )
    return HydrogenSupply(
        mode="electrolysis",
        price_usd_per_kg=price,
        emissions_kgco2e_per_kg=emissions,
        electricity_kwh_per_kg=electrolyzer_kwh_per_kg,
        water_l_per_kg=water_l_per_kg,
    )

