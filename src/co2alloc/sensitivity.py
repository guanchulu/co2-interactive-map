"""Simple one-at-a-time sensitivity utilities."""

from __future__ import annotations

from dataclasses import asdict

from .decision import choose_best, evaluate_all
from .scenario import Scenario


def one_at_a_time(
    base: Scenario,
    parameters: list[str] | None = None,
    perturbation: float = 0.25,
    metric: str = "net_cost",
) -> list[dict[str, float | str]]:
    params = parameters or [
        "electricity_price_usd_per_mwh",
        "h2_price_usd_per_kg",
        "carbon_price_usd_per_tco2",
        "co2_transport_distance_km",
        "grid_emissions_kgco2e_per_mwh",
        "h2_emissions_kgco2e_per_kg",
    ]
    base_dict = asdict(base)
    records: list[dict[str, float | str]] = []
    for param in params:
        value = base_dict[param]
        if not isinstance(value, (int, float)):
            continue
        for label, multiplier in [("low", 1.0 - perturbation), ("high", 1.0 + perturbation)]:
            scenario = base.with_updates(**{param: value * multiplier})
            winner = choose_best(
                evaluate_all(scenario),
                metric=metric,
                min_net_avoided_kgco2e=scenario.min_net_avoided_kgco2e_per_tco2,
            )
            if winner is None:
                records.append(
                    {
                        "parameter": param,
                        "case": label,
                        "value": value * multiplier,
                        "winner": "none",
                    }
                )
            else:
                records.append(
                    {
                        "parameter": param,
                        "case": label,
                        "value": value * multiplier,
                        "winner": winner.inventory.pathway,
                        "net_cost_usd_per_tco2": winner.economics.net_cost_usd_per_tco2,
                        "net_avoided_kgco2e_per_tco2": winner.lca.net_avoided_kgco2e,
                    }
                )
    return records

