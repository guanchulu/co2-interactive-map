"""Electrochemical CO2 conversion screening models."""

from __future__ import annotations

from ..constants import FARADAY_C_PER_MOL, J_PER_KWH, kg_to_kmol, kmol_to_kg
from ..scenario import Scenario
from ..types import PathwayInventory


def electrolysis_co_inventory(
    scenario: Scenario,
    co2_feed_kg: float = 1000.0,
    single_pass_conversion: float = 0.45,
    overall_capture_recycle_efficiency: float = 0.90,
    faradaic_efficiency: float = 0.86,
    cell_voltage_v: float = 3.0,
    separation_kwh_per_tco2: float = 130.0,
    balance_of_plant_kwh_per_tco2: float = 90.0,
) -> PathwayInventory:
    feed_kmol = kg_to_kmol(co2_feed_kg, "CO2")
    converted_kmol = feed_kmol * single_pass_conversion * overall_capture_recycle_efficiency
    co_kg = kmol_to_kg(converted_kmol, "CO")
    co2_utilized_kg = kmol_to_kg(converted_kmol, "CO2")
    direct_emissions = co2_feed_kg - co2_utilized_kg

    electrolysis_kwh = (
        converted_kmol
        * 1000.0
        * 2.0
        * FARADAY_C_PER_MOL
        * cell_voltage_v
        / J_PER_KWH
        / max(faradaic_efficiency, 1e-6)
    )
    feed_t = co2_feed_kg / 1000.0
    electricity = electrolysis_kwh + (
        separation_kwh_per_tco2 + balance_of_plant_kwh_per_tco2
    ) * feed_t

    inventory = PathwayInventory(
        pathway="electrolysis_to_co",
        category="electrochemical_utilization",
        technology_family="electrochemical",
        co2_feed_kg=co2_feed_kg,
        product_name="carbon_monoxide",
        product_kg=co_kg,
        co2_utilized_kg=co2_utilized_kg,
        co2_released_end_of_life_kg=co2_utilized_kg,
        direct_co2_emissions_kg=max(direct_emissions, 0.0),
        h2_kg=0.0,
        electricity_kwh=electricity,
        heat_gj=0.0,
        cooling_gj=0.25,
        water_kg=kmol_to_kg(converted_kmol, "H2O"),
        transport_tkm=feed_t * scenario.co2_transport_distance_km,
        capex_usd_per_tpa_co2=1450.0,
        fixed_opex_usd_per_tco2=35.0,
        variable_opex_usd_per_tco2=28.0,
        product_price_usd_per_kg=0.22,
        displaced_emissions_kgco2e_per_kg_product=1.6,
        market_capacity_mtco2_per_year=400.0,
        carbon_residence_years=0.5,
        notes="Electrolysis electricity calculated from cell voltage and Faradaic efficiency.",
    )
    inventory.validate()
    return inventory


def electrolysis_formate_inventory(
    scenario: Scenario,
    co2_feed_kg: float = 1000.0,
    single_pass_conversion: float = 0.40,
    overall_capture_recycle_efficiency: float = 0.88,
    faradaic_efficiency: float = 0.82,
    cell_voltage_v: float = 3.2,
    product_recovery_kwh_per_tco2: float = 420.0,
    balance_of_plant_kwh_per_tco2: float = 110.0,
) -> PathwayInventory:
    feed_kmol = kg_to_kmol(co2_feed_kg, "CO2")
    converted_kmol = feed_kmol * single_pass_conversion * overall_capture_recycle_efficiency
    product_kg = kmol_to_kg(converted_kmol, "FORMIC_ACID")
    co2_utilized_kg = kmol_to_kg(converted_kmol, "CO2")
    direct_emissions = co2_feed_kg - co2_utilized_kg

    electrolysis_kwh = (
        converted_kmol
        * 1000.0
        * 2.0
        * FARADAY_C_PER_MOL
        * cell_voltage_v
        / J_PER_KWH
        / max(faradaic_efficiency, 1e-6)
    )
    feed_t = co2_feed_kg / 1000.0
    electricity = electrolysis_kwh + (
        product_recovery_kwh_per_tco2 + balance_of_plant_kwh_per_tco2
    ) * feed_t

    inventory = PathwayInventory(
        pathway="electrolysis_to_formate",
        category="electrochemical_utilization",
        technology_family="electrochemical",
        co2_feed_kg=co2_feed_kg,
        product_name="formic_acid_equivalent",
        product_kg=product_kg,
        co2_utilized_kg=co2_utilized_kg,
        co2_released_end_of_life_kg=co2_utilized_kg,
        direct_co2_emissions_kg=max(direct_emissions, 0.0),
        electricity_kwh=electricity,
        heat_gj=0.0,
        cooling_gj=0.35,
        water_kg=kmol_to_kg(converted_kmol, "H2O"),
        transport_tkm=feed_t * scenario.co2_transport_distance_km,
        capex_usd_per_tpa_co2=1700.0,
        fixed_opex_usd_per_tco2=40.0,
        variable_opex_usd_per_tco2=34.0,
        product_price_usd_per_kg=0.70,
        displaced_emissions_kgco2e_per_kg_product=1.65,
        market_capacity_mtco2_per_year=80.0,
        carbon_residence_years=0.4,
        notes="Electrochemical formate represented as formic-acid equivalent product.",
    )
    inventory.validate()
    return inventory


def electrolysis_ethylene_inventory(
    scenario: Scenario,
    co2_feed_kg: float = 1000.0,
    single_pass_conversion: float = 0.25,
    overall_capture_recycle_efficiency: float = 0.82,
    faradaic_efficiency: float = 0.45,
    cell_voltage_v: float = 3.6,
    product_recovery_kwh_per_tco2: float = 520.0,
    balance_of_plant_kwh_per_tco2: float = 180.0,
) -> PathwayInventory:
    feed_kmol = kg_to_kmol(co2_feed_kg, "CO2")
    converted_co2_kmol = feed_kmol * single_pass_conversion * overall_capture_recycle_efficiency
    ethylene_kmol = converted_co2_kmol / 2.0
    product_kg = kmol_to_kg(ethylene_kmol, "ETHYLENE")
    co2_utilized_kg = kmol_to_kg(converted_co2_kmol, "CO2")
    direct_emissions = co2_feed_kg - co2_utilized_kg

    electrolysis_kwh = (
        ethylene_kmol
        * 1000.0
        * 12.0
        * FARADAY_C_PER_MOL
        * cell_voltage_v
        / J_PER_KWH
        / max(faradaic_efficiency, 1e-6)
    )
    feed_t = co2_feed_kg / 1000.0
    electricity = electrolysis_kwh + (
        product_recovery_kwh_per_tco2 + balance_of_plant_kwh_per_tco2
    ) * feed_t

    inventory = PathwayInventory(
        pathway="electrolysis_to_ethylene",
        category="electrochemical_utilization",
        technology_family="electrochemical",
        co2_feed_kg=co2_feed_kg,
        product_name="ethylene",
        product_kg=product_kg,
        co2_utilized_kg=co2_utilized_kg,
        co2_released_end_of_life_kg=co2_utilized_kg,
        direct_co2_emissions_kg=max(direct_emissions, 0.0),
        electricity_kwh=electricity,
        heat_gj=0.0,
        cooling_gj=0.60,
        water_kg=kmol_to_kg(2.0 * ethylene_kmol, "H2O"),
        transport_tkm=feed_t * scenario.co2_transport_distance_km,
        capex_usd_per_tpa_co2=2600.0,
        fixed_opex_usd_per_tco2=62.0,
        variable_opex_usd_per_tco2=45.0,
        product_price_usd_per_kg=1.05,
        displaced_emissions_kgco2e_per_kg_product=1.85,
        market_capacity_mtco2_per_year=350.0,
        carbon_residence_years=0.8,
        notes="C2 electrolysis represented by ethylene stoichiometry and literature-like FE constraints.",
    )
    inventory.validate()
    return inventory
