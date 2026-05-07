"""Mineralization screening model."""

from __future__ import annotations

from ..constants import kg_to_kmol, kmol_to_kg
from ..scenario import Scenario
from ..types import PathwayInventory


def mineralization_inventory(
    scenario: Scenario,
    co2_feed_kg: float = 1000.0,
    uptake_fraction: float = 0.82,
    milling_kwh_per_tco2: float = 55.0,
    handling_kwh_per_tco2: float = 18.0,
    low_grade_heat_gj_per_tco2: float = 0.10,
) -> PathwayInventory:
    stored_kg = co2_feed_kg * uptake_fraction
    unreacted_kg = co2_feed_kg - stored_kg
    carbonate_kg = kmol_to_kg(kg_to_kmol(stored_kg, "CO2"), "CACO3")
    feed_t = co2_feed_kg / 1000.0

    inventory = PathwayInventory(
        pathway="mineralization",
        category="mineral_storage",
        technology_family="mineralization",
        co2_feed_kg=co2_feed_kg,
        product_name="carbonate_product",
        product_kg=carbonate_kg,
        co2_utilized_kg=stored_kg,
        co2_stored_kg=stored_kg,
        direct_co2_emissions_kg=unreacted_kg,
        electricity_kwh=(milling_kwh_per_tco2 + handling_kwh_per_tco2) * feed_t,
        heat_gj=low_grade_heat_gj_per_tco2 * feed_t,
        cooling_gj=0.0,
        water_kg=250.0 * feed_t,
        transport_tkm=feed_t * scenario.co2_transport_distance_km,
        capex_usd_per_tpa_co2=520.0,
        fixed_opex_usd_per_tco2=12.0,
        variable_opex_usd_per_tco2=24.0,
        product_price_usd_per_kg=0.018,
        displaced_emissions_kgco2e_per_kg_product=0.015,
        market_capacity_mtco2_per_year=1800.0,
        carbon_residence_years=1000.0,
        notes="Aggregate-like mineralization represented by uptake and handling energy.",
    )
    inventory.validate()
    return inventory
