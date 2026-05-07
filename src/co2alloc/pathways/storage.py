"""Geological storage screening model."""

from __future__ import annotations

from ..scenario import Scenario
from ..types import PathwayInventory


def storage_inventory(
    scenario: Scenario,
    co2_feed_kg: float = 1000.0,
    compression_kwh_per_tco2: float = 95.0,
    injection_kwh_per_tco2: float = 8.0,
    retention_fraction: float = 0.995,
) -> PathwayInventory:
    feed_t = co2_feed_kg / 1000.0
    stored = co2_feed_kg * retention_fraction
    leaked_or_lost = co2_feed_kg - stored
    electricity = (compression_kwh_per_tco2 + injection_kwh_per_tco2) * feed_t
    transport_tkm = feed_t * scenario.co2_transport_distance_km

    inventory = PathwayInventory(
        pathway="geological_storage",
        category="durable_storage",
        technology_family="storage",
        co2_feed_kg=co2_feed_kg,
        co2_stored_kg=stored,
        direct_co2_emissions_kg=leaked_or_lost,
        electricity_kwh=electricity,
        transport_tkm=transport_tkm,
        capex_usd_per_tpa_co2=320.0,
        fixed_opex_usd_per_tco2=6.0,
        variable_opex_usd_per_tco2=14.0,
        market_capacity_mtco2_per_year=10000.0,
        carbon_residence_years=10000.0,
        notes="Compression, transport, injection, and monitoring screening model.",
    )
    inventory.validate()
    return inventory
