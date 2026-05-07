"""Reverse water-gas shift to CO screening model."""

from __future__ import annotations

from ..constants import kg_to_kmol, kmol_to_kg
from ..scenario import Scenario
from ..types import PathwayInventory


def rwgs_inventory(
    scenario: Scenario,
    co2_feed_kg: float = 1000.0,
    overall_co2_conversion: float = 0.85,
    co_selectivity: float = 0.98,
    h2_loss_fraction: float = 0.03,
    compression_kwh_per_tco2: float = 70.0,
    gas_separation_kwh_per_tco2: float = 80.0,
    heat_efficiency: float = 0.75,
) -> PathwayInventory:
    feed_kmol = kg_to_kmol(co2_feed_kg, "CO2")
    converted_kmol = feed_kmol * overall_co2_conversion
    co_kmol = converted_kmol * co_selectivity
    side_kmol = converted_kmol * (1.0 - co_selectivity)

    co_kg = kmol_to_kg(co_kmol, "CO")
    co2_to_co_kg = kmol_to_kg(co_kmol, "CO2")
    co2_side_kg = kmol_to_kg(side_kmol, "CO2")
    unconverted_kg = co2_feed_kg - co2_to_co_kg - co2_side_kg

    h2_kg = kmol_to_kg(converted_kmol, "H2") * (1.0 + h2_loss_fraction)
    reaction_heat_gj = converted_kmol * 1000.0 * 41.2 / 1e6 / max(heat_efficiency, 1e-6)

    feed_t = co2_feed_kg / 1000.0
    electricity = (compression_kwh_per_tco2 + gas_separation_kwh_per_tco2) * feed_t

    inventory = PathwayInventory(
        pathway="rwgs_to_co",
        category="platform_molecule",
        technology_family="thermochemical",
        co2_feed_kg=co2_feed_kg,
        product_name="carbon_monoxide",
        product_kg=co_kg,
        co2_utilized_kg=co2_to_co_kg,
        co2_released_end_of_life_kg=co2_to_co_kg,
        direct_co2_emissions_kg=max(unconverted_kg, 0.0) + co2_side_kg,
        h2_kg=h2_kg,
        electricity_kwh=electricity,
        heat_gj=reaction_heat_gj,
        cooling_gj=0.2 * reaction_heat_gj,
        water_kg=kmol_to_kg(co_kmol, "H2O"),
        transport_tkm=feed_t * scenario.co2_transport_distance_km,
        capex_usd_per_tpa_co2=620.0,
        fixed_opex_usd_per_tco2=15.0,
        variable_opex_usd_per_tco2=18.0,
        product_price_usd_per_kg=0.22,
        displaced_emissions_kgco2e_per_kg_product=1.6,
        market_capacity_mtco2_per_year=400.0,
        carbon_residence_years=0.5,
        notes="RWGS heat demand is represented by reaction enthalpy with efficiency loss.",
    )
    inventory.validate()
    return inventory
