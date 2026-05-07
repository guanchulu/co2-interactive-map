"""Life-cycle accounting for pathway inventories."""

from __future__ import annotations

from .scenario import Scenario
from .types import LcaSummary, PathwayInventory


def evaluate_lca(inventory: PathwayInventory, scenario: Scenario) -> LcaSummary:
    electricity_emissions = (
        inventory.electricity_kwh / 1000.0 * scenario.grid_emissions_kgco2e_per_mwh
    )
    h2_emissions = inventory.h2_kg * scenario.h2_emissions_kgco2e_per_kg
    heat_emissions = inventory.heat_gj * scenario.heat_emissions_kgco2e_per_gj
    cooling_emissions = inventory.cooling_gj * scenario.cooling_emissions_kgco2e_per_gj
    transport_emissions = (
        inventory.transport_tkm * scenario.co2_transport_emissions_kgco2e_per_tkm
    )

    induced = (
        electricity_emissions
        + h2_emissions
        + heat_emissions
        + cooling_emissions
        + transport_emissions
        + inventory.direct_co2_emissions_kg
    )
    displaced = inventory.displaced_emissions_kgco2e

    net_lifecycle = (
        induced + inventory.co2_released_end_of_life_kg - displaced
    )

    # Functional unit: one tonne captured CO2 entering the pathway.
    # Baseline: that CO2 would be emitted and the displaced product would be
    # made conventionally. Short-lived fuels therefore do not receive permanent
    # storage credit; their feed CO2 is canceled by end-of-life release.
    net_avoided = inventory.co2_feed_kg - net_lifecycle
    durable_retained = inventory.co2_stored_kg
    removal_credit = max(0.0, durable_retained - induced)

    return LcaSummary(
        pathway=inventory.pathway,
        induced_emissions_kgco2e=induced,
        displaced_emissions_kgco2e=displaced,
        net_lifecycle_emissions_kgco2e=net_lifecycle,
        net_avoided_kgco2e=net_avoided,
        durable_retained_kgco2=durable_retained,
        removal_credit_kgco2=removal_credit,
    )

