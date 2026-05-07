"""CO2 methanation to e-methane screening model."""

from __future__ import annotations

from ..constants import kg_to_kmol, kmol_to_kg
from ..scenario import Scenario
from ..types import PathwayInventory


def methane_inventory(
    scenario: Scenario,
    co2_feed_kg: float = 1000.0,
    overall_co2_conversion: float = 0.92,
    methane_selectivity: float = 0.98,
    h2_loss_fraction: float = 0.035,
    compression_kwh_per_tco2: float = 70.0,
    gas_cleanup_kwh_per_tco2: float = 35.0,
) -> PathwayInventory:
    feed_kmol = kg_to_kmol(co2_feed_kg, "CO2")
    converted_kmol = feed_kmol * overall_co2_conversion
    methane_kmol = converted_kmol * methane_selectivity
    side_kmol = converted_kmol * (1.0 - methane_selectivity)

    methane_kg = kmol_to_kg(methane_kmol, "CH4")
    co2_to_methane_kg = kmol_to_kg(methane_kmol, "CO2")
    co2_side_kg = kmol_to_kg(side_kmol, "CO2")
    unconverted_kg = co2_feed_kg - co2_to_methane_kg - co2_side_kg
    h2_kg = kmol_to_kg(4.0 * methane_kmol, "H2") * (1.0 + h2_loss_fraction)
    feed_t = co2_feed_kg / 1000.0

    inventory = PathwayInventory(
        pathway="co2_to_methane",
        category="fuel_recycling",
        technology_family="thermochemical",
        co2_feed_kg=co2_feed_kg,
        product_name="methane",
        product_kg=methane_kg,
        co2_utilized_kg=co2_to_methane_kg,
        co2_released_end_of_life_kg=co2_to_methane_kg,
        direct_co2_emissions_kg=max(unconverted_kg, 0.0) + co2_side_kg,
        h2_kg=h2_kg,
        electricity_kwh=(compression_kwh_per_tco2 + gas_cleanup_kwh_per_tco2) * feed_t,
        heat_gj=0.0,
        cooling_gj=0.55,
        water_kg=kmol_to_kg(2.0 * methane_kmol, "H2O"),
        transport_tkm=feed_t * scenario.co2_transport_distance_km,
        capex_usd_per_tpa_co2=700.0,
        fixed_opex_usd_per_tco2=16.0,
        variable_opex_usd_per_tco2=18.0,
        product_price_usd_per_kg=0.60,
        displaced_emissions_kgco2e_per_kg_product=2.75,
        market_capacity_mtco2_per_year=2500.0,
        carbon_residence_years=0.02,
        notes="Sabatier methanation treated as carbon recycling with short residence time.",
    )
    inventory.validate()
    return inventory
