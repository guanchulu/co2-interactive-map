"""CO2-derived sustainable aviation fuel screening models."""

from __future__ import annotations

from ..scenario import Scenario
from ..types import PathwayInventory


def ft_saf_inventory(
    scenario: Scenario,
    co2_feed_kg: float = 1000.0,
    co2_to_hydrocarbon_fraction: float = 0.88,
    saf_selectivity_fraction: float = 0.58,
    h2_kg_per_tco2: float = 165.0,
    synthesis_kwh_per_tco2: float = 260.0,
    upgrading_kwh_per_tco2: float = 120.0,
    heat_gj_per_tco2: float = 0.45,
) -> PathwayInventory:
    feed_t = co2_feed_kg / 1000.0
    co2_utilized = co2_feed_kg * co2_to_hydrocarbon_fraction
    co2_released = co2_utilized
    direct = max(0.0, co2_feed_kg - co2_utilized)

    # Approximate CH2 product from CO2 + 3H2 -> CH2 + 2H2O, then SAF-range cut.
    hydrocarbon_kg = co2_utilized * (14.027 / 44.0095)
    saf_kg = hydrocarbon_kg * saf_selectivity_fraction
    coproduct_kg = hydrocarbon_kg - saf_kg

    inventory = PathwayInventory(
        pathway="co2_h2_ft_saf",
        category="fuel_recycling",
        technology_family="thermochemical",
        co2_feed_kg=co2_feed_kg,
        product_name="sustainable_aviation_fuel",
        product_kg=saf_kg,
        co2_utilized_kg=co2_utilized,
        co2_released_end_of_life_kg=co2_released,
        direct_co2_emissions_kg=direct,
        h2_kg=h2_kg_per_tco2 * feed_t,
        electricity_kwh=(synthesis_kwh_per_tco2 + upgrading_kwh_per_tco2) * feed_t,
        heat_gj=heat_gj_per_tco2 * feed_t,
        cooling_gj=0.25 * heat_gj_per_tco2 * feed_t,
        water_kg=2.1 * h2_kg_per_tco2 * feed_t,
        transport_tkm=feed_t * scenario.co2_transport_distance_km,
        capex_usd_per_tpa_co2=1900.0,
        fixed_opex_usd_per_tco2=55.0,
        variable_opex_usd_per_tco2=85.0,
        product_price_usd_per_kg=1.55,
        displaced_emissions_kgco2e_per_kg_product=3.15,
        market_capacity_mtco2_per_year=1000.0,
        carbon_residence_years=0.02,
        notes=(
            "Reduced-order CO2+H2 Fischer-Tropsch SAF model; coproduct "
            f"hydrocarbon not credited directly ({coproduct_kg:.1f} kg/tCO2)."
        ),
    )
    inventory.validate()
    return inventory


def methanol_to_jet_saf_inventory(
    scenario: Scenario,
    co2_feed_kg: float = 1000.0,
    methanol_intermediate_fraction: float = 0.84,
    saf_selectivity_fraction: float = 0.46,
    h2_kg_per_tco2: float = 178.0,
    synthesis_kwh_per_tco2: float = 180.0,
    upgrading_kwh_per_tco2: float = 320.0,
    heat_gj_per_tco2: float = 0.85,
) -> PathwayInventory:
    feed_t = co2_feed_kg / 1000.0
    co2_utilized = co2_feed_kg * methanol_intermediate_fraction
    co2_released = co2_utilized
    direct = max(0.0, co2_feed_kg - co2_utilized)
    hydrocarbon_kg = co2_utilized * (14.027 / 44.0095)
    saf_kg = hydrocarbon_kg * saf_selectivity_fraction

    inventory = PathwayInventory(
        pathway="co2_methanol_to_jet_saf",
        category="fuel_recycling",
        technology_family="thermochemical",
        co2_feed_kg=co2_feed_kg,
        product_name="sustainable_aviation_fuel",
        product_kg=saf_kg,
        co2_utilized_kg=co2_utilized,
        co2_released_end_of_life_kg=co2_released,
        direct_co2_emissions_kg=direct,
        h2_kg=h2_kg_per_tco2 * feed_t,
        electricity_kwh=(synthesis_kwh_per_tco2 + upgrading_kwh_per_tco2) * feed_t,
        heat_gj=heat_gj_per_tco2 * feed_t,
        cooling_gj=0.30 * heat_gj_per_tco2 * feed_t,
        water_kg=2.4 * h2_kg_per_tco2 * feed_t,
        transport_tkm=feed_t * scenario.co2_transport_distance_km,
        capex_usd_per_tpa_co2=2300.0,
        fixed_opex_usd_per_tco2=70.0,
        variable_opex_usd_per_tco2=105.0,
        product_price_usd_per_kg=1.55,
        displaced_emissions_kgco2e_per_kg_product=3.15,
        market_capacity_mtco2_per_year=650.0,
        carbon_residence_years=0.02,
        notes="Reduced-order CO2-to-methanol-to-jet SAF model.",
    )
    inventory.validate()
    return inventory
