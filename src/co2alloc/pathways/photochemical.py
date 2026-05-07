"""Photochemical and photoelectrochemical CO2 conversion screening models."""

from __future__ import annotations

from ..constants import kg_to_kmol, kmol_to_kg
from ..scenario import Scenario
from ..types import PathwayInventory


KJ_PER_KWH = 3600.0


def _solar_requirements(
    converted_kmol: float,
    delta_g_kj_per_mol_product: float,
    solar_to_product_efficiency: float,
    annual_insolation_kwh_m2: float,
    photoreactor_cost_usd_m2: float,
) -> tuple[float, float, float]:
    chemical_energy_kwh = (
        converted_kmol * 1000.0 * delta_g_kj_per_mol_product / KJ_PER_KWH
    )
    solar_input_kwh = chemical_energy_kwh / max(solar_to_product_efficiency, 1e-6)
    land_m2 = solar_input_kwh / max(annual_insolation_kwh_m2, 1e-6)
    capex_usd_per_tpa_co2 = land_m2 * photoreactor_cost_usd_m2
    return solar_input_kwh, land_m2, capex_usd_per_tpa_co2


def photocatalytic_co_inventory(
    scenario: Scenario,
    co2_feed_kg: float = 1000.0,
    overall_co2_conversion: float = 0.18,
    co_selectivity: float = 0.75,
    solar_to_product_efficiency: float = 0.01,
    annual_insolation_kwh_m2: float = 1700.0,
    photoreactor_cost_usd_m2: float = 180.0,
    gas_cleanup_kwh_per_tco2: float = 95.0,
) -> PathwayInventory:
    feed_kmol = kg_to_kmol(co2_feed_kg, "CO2")
    converted_kmol = feed_kmol * overall_co2_conversion
    co_kmol = converted_kmol * co_selectivity
    side_kmol = converted_kmol - co_kmol
    co_kg = kmol_to_kg(co_kmol, "CO")
    co2_to_co_kg = kmol_to_kg(co_kmol, "CO2")
    side_co2_kg = kmol_to_kg(side_kmol, "CO2")
    direct_emissions = co2_feed_kg - co2_to_co_kg - side_co2_kg + side_co2_kg
    solar_input, land_m2, capex = _solar_requirements(
        co_kmol,
        delta_g_kj_per_mol_product=257.0,
        solar_to_product_efficiency=solar_to_product_efficiency,
        annual_insolation_kwh_m2=annual_insolation_kwh_m2,
        photoreactor_cost_usd_m2=photoreactor_cost_usd_m2,
    )
    feed_t = co2_feed_kg / 1000.0

    inventory = PathwayInventory(
        pathway="photocatalytic_to_co",
        category="photochemical_utilization",
        technology_family="photochemical",
        co2_feed_kg=co2_feed_kg,
        product_name="carbon_monoxide",
        product_kg=co_kg,
        co2_utilized_kg=co2_to_co_kg,
        co2_released_end_of_life_kg=co2_to_co_kg,
        direct_co2_emissions_kg=max(direct_emissions, 0.0),
        electricity_kwh=gas_cleanup_kwh_per_tco2 * feed_t,
        solar_input_kwh=solar_input,
        land_m2=land_m2,
        cooling_gj=0.10,
        water_kg=kmol_to_kg(co_kmol, "H2O"),
        transport_tkm=feed_t * scenario.co2_transport_distance_km,
        capex_usd_per_tpa_co2=capex,
        fixed_opex_usd_per_tco2=0.04 * capex,
        variable_opex_usd_per_tco2=18.0,
        product_price_usd_per_kg=0.22,
        displaced_emissions_kgco2e_per_kg_product=1.6,
        market_capacity_mtco2_per_year=400.0,
        carbon_residence_years=0.5,
        notes="Photocatalytic CO is represented by solar-to-product efficiency and photoreactor area.",
    )
    inventory.validate()
    return inventory


def photoelectrochemical_formate_inventory(
    scenario: Scenario,
    co2_feed_kg: float = 1000.0,
    overall_co2_conversion: float = 0.22,
    formate_selectivity: float = 0.80,
    solar_to_product_efficiency: float = 0.025,
    annual_insolation_kwh_m2: float = 1700.0,
    photoreactor_cost_usd_m2: float = 260.0,
    product_recovery_kwh_per_tco2: float = 260.0,
) -> PathwayInventory:
    feed_kmol = kg_to_kmol(co2_feed_kg, "CO2")
    converted_kmol = feed_kmol * overall_co2_conversion
    formate_kmol = converted_kmol * formate_selectivity
    side_kmol = converted_kmol - formate_kmol
    product_kg = kmol_to_kg(formate_kmol, "FORMIC_ACID")
    co2_to_formate_kg = kmol_to_kg(formate_kmol, "CO2")
    side_co2_kg = kmol_to_kg(side_kmol, "CO2")
    direct_emissions = co2_feed_kg - co2_to_formate_kg - side_co2_kg + side_co2_kg
    solar_input, land_m2, capex = _solar_requirements(
        formate_kmol,
        delta_g_kj_per_mol_product=285.0,
        solar_to_product_efficiency=solar_to_product_efficiency,
        annual_insolation_kwh_m2=annual_insolation_kwh_m2,
        photoreactor_cost_usd_m2=photoreactor_cost_usd_m2,
    )
    feed_t = co2_feed_kg / 1000.0

    inventory = PathwayInventory(
        pathway="photoelectrochemical_to_formate",
        category="photochemical_utilization",
        technology_family="photochemical",
        co2_feed_kg=co2_feed_kg,
        product_name="formic_acid_equivalent",
        product_kg=product_kg,
        co2_utilized_kg=co2_to_formate_kg,
        co2_released_end_of_life_kg=co2_to_formate_kg,
        direct_co2_emissions_kg=max(direct_emissions, 0.0),
        electricity_kwh=product_recovery_kwh_per_tco2 * feed_t,
        solar_input_kwh=solar_input,
        land_m2=land_m2,
        cooling_gj=0.12,
        water_kg=kmol_to_kg(formate_kmol, "H2O"),
        transport_tkm=feed_t * scenario.co2_transport_distance_km,
        capex_usd_per_tpa_co2=capex,
        fixed_opex_usd_per_tco2=0.05 * capex,
        variable_opex_usd_per_tco2=26.0,
        product_price_usd_per_kg=0.70,
        displaced_emissions_kgco2e_per_kg_product=1.65,
        market_capacity_mtco2_per_year=80.0,
        carbon_residence_years=0.4,
        notes="PEC formate uses solar-to-product efficiency plus downstream product recovery electricity.",
    )
    inventory.validate()
    return inventory
