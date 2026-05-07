"""Scenario assumptions shared across pathway evaluations."""

from __future__ import annotations

from dataclasses import dataclass, replace


@dataclass(frozen=True, slots=True)
class Scenario:
    electricity_price_usd_per_mwh: float = 45.0
    h2_price_usd_per_kg: float = 2.5
    heat_price_usd_per_gj: float = 6.0
    cooling_price_usd_per_gj: float = 0.6
    carbon_price_usd_per_tco2: float = 80.0
    carbon_tax_usd_per_tco2: float = 0.0
    durable_removal_credit_usd_per_tco2: float = 0.0
    co2_transport_distance_km: float = 100.0
    co2_transport_cost_usd_per_tkm: float = 0.025
    co2_transport_emissions_kgco2e_per_tkm: float = 0.006
    grid_emissions_kgco2e_per_mwh: float = 80.0
    h2_emissions_kgco2e_per_kg: float = 1.0
    heat_emissions_kgco2e_per_gj: float = 6.0
    cooling_emissions_kgco2e_per_gj: float = 0.2
    discount_rate: float = 0.08
    plant_lifetime_years: int = 20
    capacity_factor: float = 0.9
    include_carbon_credit: bool = True
    credit_negative_avoided_as_penalty: bool = False
    min_net_avoided_kgco2e_per_tco2: float = 0.0

    def with_updates(self, **kwargs: float | bool | int | str) -> "Scenario":
        return replace(self, **kwargs)
