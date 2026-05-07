"""CO2 hydrogenation to methanol screening model."""

from __future__ import annotations

from ..constants import kg_to_kmol, kmol_to_kg
from ..scenario import Scenario
from ..types import PathwayInventory


def methanol_inventory(
    scenario: Scenario,
    co2_feed_kg: float = 1000.0,
    overall_co2_conversion: float = 0.88,
    methanol_selectivity: float = 0.96,
    h2_loss_fraction: float = 0.04,
    compression_kwh_per_tco2: float = 75.0,
    recycle_separation_kwh_per_tco2: float = 45.0,
    distillation_gj_per_t_methanol: float = 1.25,
) -> PathwayInventory:
    feed_kmol = kg_to_kmol(co2_feed_kg, "CO2")
    converted_kmol = feed_kmol * overall_co2_conversion
    methanol_kmol = converted_kmol * methanol_selectivity
    rwgs_byproduct_kmol = converted_kmol * (1.0 - methanol_selectivity)

    methanol_kg = kmol_to_kg(methanol_kmol, "METHANOL")
    co2_to_methanol_kg = kmol_to_kg(methanol_kmol, "CO2")
    co2_to_co_byproduct_kg = kmol_to_kg(rwgs_byproduct_kmol, "CO2")
    unconverted_co2_kg = co2_feed_kg - co2_to_methanol_kg - co2_to_co_byproduct_kg

    h2_for_methanol_kg = kmol_to_kg(3.0 * methanol_kmol, "H2")
    h2_for_rwgs_kg = kmol_to_kg(rwgs_byproduct_kmol, "H2")
    h2_kg = (h2_for_methanol_kg + h2_for_rwgs_kg) * (1.0 + h2_loss_fraction)

    feed_t = co2_feed_kg / 1000.0
    methanol_t = methanol_kg / 1000.0
    electricity = (compression_kwh_per_tco2 + recycle_separation_kwh_per_tco2) * feed_t
    heat = distillation_gj_per_t_methanol * methanol_t

    inventory = PathwayInventory(
        pathway="co2_to_methanol",
        category="chemical_utilization",
        technology_family="thermochemical",
        co2_feed_kg=co2_feed_kg,
        product_name="methanol",
        product_kg=methanol_kg,
        co2_utilized_kg=co2_to_methanol_kg,
        co2_released_end_of_life_kg=co2_to_methanol_kg,
        direct_co2_emissions_kg=max(unconverted_co2_kg, 0.0) + co2_to_co_byproduct_kg,
        h2_kg=h2_kg,
        electricity_kwh=electricity,
        heat_gj=heat,
        cooling_gj=0.4 * heat,
        water_kg=kmol_to_kg(methanol_kmol, "H2O"),
        transport_tkm=feed_t * scenario.co2_transport_distance_km,
        capex_usd_per_tpa_co2=850.0,
        fixed_opex_usd_per_tco2=18.0,
        variable_opex_usd_per_tco2=22.0,
        product_price_usd_per_kg=0.45,
        displaced_emissions_kgco2e_per_kg_product=1.45,
        market_capacity_mtco2_per_year=250.0,
        carbon_residence_years=2.0,
        notes="Stoichiometric hydrogenation with recycle represented by overall conversion.",
    )
    inventory.validate()
    return inventory
