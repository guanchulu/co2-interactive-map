"""Techno-economic accounting for pathway inventories."""

from __future__ import annotations

import math

from .constants import capital_recovery_factor
from .lca import evaluate_lca
from .scenario import Scenario
from .types import EconomicSummary, PathwayInventory


def evaluate_economics(
    inventory: PathwayInventory,
    scenario: Scenario,
) -> EconomicSummary:
    lca = evaluate_lca(inventory, scenario)
    feed_t = inventory.co2_feed_tonnes
    crf = capital_recovery_factor(scenario.discount_rate, scenario.plant_lifetime_years)

    annualized_capex_per_tco2 = (
        inventory.capex_usd_per_tpa_co2 * crf / max(scenario.capacity_factor, 1e-6)
    )
    electricity_cost = (
        inventory.electricity_kwh / 1000.0 * scenario.electricity_price_usd_per_mwh
    )
    h2_cost = inventory.h2_kg * scenario.h2_price_usd_per_kg
    heat_cost = inventory.heat_gj * scenario.heat_price_usd_per_gj
    cooling_cost = inventory.cooling_gj * scenario.cooling_price_usd_per_gj
    transport_cost = inventory.transport_tkm * scenario.co2_transport_cost_usd_per_tkm
    variable_cost = inventory.variable_opex_usd_per_tco2 * feed_t
    fixed_cost = inventory.fixed_opex_usd_per_tco2 * feed_t

    gross_cost_total = (
        annualized_capex_per_tco2 * feed_t
        + electricity_cost
        + h2_cost
        + heat_cost
        + cooling_cost
        + transport_cost
        + variable_cost
        + fixed_cost
    )
    gross_cost_per_t = gross_cost_total / feed_t
    product_revenue_per_t = inventory.product_revenue_usd / feed_t

    avoided_t = lca.net_avoided_kgco2e / 1000.0
    if scenario.include_carbon_credit:
        creditable_avoided_t = avoided_t
        if not scenario.credit_negative_avoided_as_penalty:
            creditable_avoided_t = max(0.0, creditable_avoided_t)
        carbon_credit_per_t = creditable_avoided_t * scenario.carbon_price_usd_per_tco2 / feed_t
    else:
        carbon_credit_per_t = 0.0

    durable_credit_per_t = (
        lca.removal_credit_kgco2 / 1000.0
        * scenario.durable_removal_credit_usd_per_tco2
        / feed_t
    )
    taxable_emissions_t = max(
        0.0,
        (lca.induced_emissions_kgco2e + inventory.co2_released_end_of_life_kg)
        / 1000.0,
    )
    carbon_tax_per_t = taxable_emissions_t * scenario.carbon_tax_usd_per_tco2 / feed_t

    net_cost_per_t = (
        gross_cost_per_t
        - product_revenue_per_t
        - carbon_credit_per_t
        - durable_credit_per_t
        + carbon_tax_per_t
    )

    cost_before_credit = gross_cost_per_t - product_revenue_per_t
    if avoided_t > 0:
        abatement_cost = cost_before_credit / avoided_t
    else:
        abatement_cost = math.inf

    retained_t = lca.durable_retained_kgco2 / 1000.0
    if retained_t > 0:
        removal_cost = cost_before_credit / retained_t
    else:
        removal_cost = math.inf

    return EconomicSummary(
        pathway=inventory.pathway,
        gross_cost_usd_per_tco2=gross_cost_per_t,
        product_revenue_usd_per_tco2=product_revenue_per_t,
        carbon_credit_usd_per_tco2=carbon_credit_per_t,
        durable_removal_credit_usd_per_tco2=durable_credit_per_t,
        carbon_tax_usd_per_tco2=carbon_tax_per_t,
        net_cost_usd_per_tco2=net_cost_per_t,
        abatement_cost_usd_per_tco2_avoided=abatement_cost,
        removal_cost_usd_per_tco2_retained=removal_cost,
    )
