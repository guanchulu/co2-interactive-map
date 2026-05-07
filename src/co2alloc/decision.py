"""Pathway evaluation and decision-map utilities."""

from __future__ import annotations

import math
from html import escape
from collections.abc import Callable, Iterable

from .lca import evaluate_lca
from .pathways import PATHWAY_BUILDERS
from .scenario import Scenario
from .tea import evaluate_economics
from .types import Evaluation, PathwayInventory

PathwayBuilder = Callable[[Scenario], PathwayInventory]


def evaluate_pathway(builder: PathwayBuilder, scenario: Scenario) -> Evaluation:
    inventory = builder(scenario)
    lca = evaluate_lca(inventory, scenario)
    economics = evaluate_economics(inventory, scenario)
    return Evaluation(inventory=inventory, lca=lca, economics=economics)


def evaluate_all(
    scenario: Scenario,
    builders: Iterable[PathwayBuilder] | None = None,
) -> list[Evaluation]:
    selected = list(builders or PATHWAY_BUILDERS)
    return [evaluate_pathway(builder, scenario) for builder in selected]


def choose_best(
    evaluations: Iterable[Evaluation],
    metric: str = "net_cost",
    min_net_avoided_kgco2e: float = 0.0,
) -> Evaluation | None:
    candidates = [
        ev
        for ev in evaluations
        if ev.lca.net_avoided_kgco2e >= min_net_avoided_kgco2e
    ]
    if not candidates:
        return None

    if metric == "net_cost":
        key = lambda ev: ev.economics.net_cost_usd_per_tco2
    elif metric == "gross_cost":
        key = lambda ev: ev.economics.gross_cost_usd_per_tco2
    elif metric == "abatement_cost":
        key = lambda ev: ev.economics.abatement_cost_usd_per_tco2_avoided
    elif metric == "removal_cost":
        key = lambda ev: ev.economics.removal_cost_usd_per_tco2_retained
    else:
        raise ValueError(f"Unknown decision metric: {metric}")

    finite = [ev for ev in candidates if math.isfinite(key(ev))]
    return min(finite or candidates, key=key)


def decision_grid(
    base: Scenario,
    electricity_prices: Iterable[float],
    h2_prices: Iterable[float],
    carbon_price: float | None = None,
    metric: str = "net_cost",
) -> list[dict[str, float | str]]:
    records: list[dict[str, float | str]] = []
    for h2_price in h2_prices:
        for electricity_price in electricity_prices:
            scenario = base.with_updates(
                electricity_price_usd_per_mwh=electricity_price,
                h2_price_usd_per_kg=h2_price,
                carbon_price_usd_per_tco2=(
                    base.carbon_price_usd_per_tco2
                    if carbon_price is None
                    else carbon_price
                ),
            )
            evaluations = evaluate_all(scenario)
            winner = choose_best(
                evaluations,
                metric=metric,
                min_net_avoided_kgco2e=scenario.min_net_avoided_kgco2e_per_tco2,
            )
            if winner is None:
                records.append(
                    {
                        "electricity_price_usd_per_mwh": electricity_price,
                        "h2_price_usd_per_kg": h2_price,
                        "winner": "none",
                    }
                )
                continue
            records.append(
                    {
                        "electricity_price_usd_per_mwh": electricity_price,
                        "h2_price_usd_per_kg": h2_price,
                        "winner": winner.inventory.pathway,
                        "winner_category": winner.inventory.category,
                        "winner_technology_family": winner.inventory.technology_family,
                        "winner_net_cost_usd_per_tco2": winner.economics.net_cost_usd_per_tco2,
                        "winner_net_avoided_kgco2e_per_tco2": winner.lca.net_avoided_kgco2e,
                        "winner_durable_retained_kgco2_per_tco2": winner.lca.durable_retained_kgco2,
                }
            )
    return records


def ascii_decision_map(records: list[dict[str, float | str]]) -> str:
    if not records:
        return ""
    abbrev = {
        "geological_storage": "STO",
        "mineralization": "MIN",
        "co2_to_methanol": "MEO",
        "rwgs_to_co": "RWG",
        "electrolysis_to_co": "ECO",
        "electrolysis_to_formate": "EFO",
        "electrolysis_to_ethylene": "EET",
        "photocatalytic_to_co": "PCO",
        "photoelectrochemical_to_formate": "PFO",
        "co2_to_methane": "CH4",
        "co2_h2_ft_saf": "SAF",
        "co2_methanol_to_jet_saf": "MTJ",
        "none": "---",
    }
    xs = sorted({float(r["electricity_price_usd_per_mwh"]) for r in records})
    ys = sorted({float(r["h2_price_usd_per_kg"]) for r in records}, reverse=True)
    by_point = {
        (float(r["electricity_price_usd_per_mwh"]), float(r["h2_price_usd_per_kg"])): str(
            r["winner"]
        )
        for r in records
    }
    lines = ["h2\\elec | " + " ".join(f"{x:>5.0f}" for x in xs)]
    lines.append("-" * len(lines[0]))
    for y in ys:
        row = [f"{y:>7.2f} |"]
        for x in xs:
            row.append(f"{abbrev.get(by_point[(x, y)], '???'):>5}")
        lines.append(" ".join(row))
    lines.append("")
    lines.append("Legend: STO storage; MIN mineralization; MEO methanol; RWG RWGS-CO; ECO electrolysis-CO; EFO electrolysis-formate; EET electrolysis-ethylene; PCO photocatalytic-CO; PFO PEC-formate; CH4 e-methane.")
    return "\n".join(lines)


def svg_decision_map(records: list[dict[str, float | str]]) -> str:
    if not records:
        return '<svg xmlns="http://www.w3.org/2000/svg"></svg>'
    abbrev = {
        "geological_storage": "STO",
        "mineralization": "MIN",
        "co2_to_methanol": "MEO",
        "rwgs_to_co": "RWG",
        "electrolysis_to_co": "ECO",
        "electrolysis_to_formate": "EFO",
        "electrolysis_to_ethylene": "EET",
        "photocatalytic_to_co": "PCO",
        "photoelectrochemical_to_formate": "PFO",
        "co2_to_methane": "CH4",
        "co2_h2_ft_saf": "SAF",
        "co2_methanol_to_jet_saf": "MTJ",
        "none": "---",
    }
    colors = {
        "geological_storage": "#4c78a8",
        "mineralization": "#59a14f",
        "co2_to_methanol": "#f28e2b",
        "rwgs_to_co": "#e15759",
        "electrolysis_to_co": "#b07aa1",
        "electrolysis_to_formate": "#9c755f",
        "electrolysis_to_ethylene": "#d37295",
        "photocatalytic_to_co": "#edc948",
        "photoelectrochemical_to_formate": "#8cd17d",
        "co2_to_methane": "#76b7b2",
        "co2_h2_ft_saf": "#2f4b7c",
        "co2_methanol_to_jet_saf": "#665191",
        "none": "#d9d9d9",
    }
    labels = {
        "geological_storage": "Storage",
        "mineralization": "Mineralization",
        "co2_to_methanol": "Methanol",
        "rwgs_to_co": "RWGS-CO",
        "electrolysis_to_co": "Electrolysis-CO",
        "electrolysis_to_formate": "Electrolysis-formate",
        "electrolysis_to_ethylene": "Electrolysis-ethylene",
        "photocatalytic_to_co": "Photocatalytic-CO",
        "photoelectrochemical_to_formate": "PEC-formate",
        "co2_to_methane": "e-Methane",
        "co2_h2_ft_saf": "FT-SAF",
        "co2_methanol_to_jet_saf": "MTJ-SAF",
        "none": "No feasible winner",
    }
    xs = sorted({float(r["electricity_price_usd_per_mwh"]) for r in records})
    ys = sorted({float(r["h2_price_usd_per_kg"]) for r in records}, reverse=True)
    by_point = {
        (float(r["electricity_price_usd_per_mwh"]), float(r["h2_price_usd_per_kg"])): str(
            r["winner"]
        )
        for r in records
    }

    left = 72
    top = 50
    cell_w = 54
    cell_h = 30
    legend_top = top + len(ys) * cell_h + 55
    width = left + len(xs) * cell_w + 40
    height = legend_top + 110
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        '<style>text{font-family:Arial,Helvetica,sans-serif;fill:#222} .small{font-size:11px}.axis{font-size:12px;font-weight:600}.cell{font-size:11px;font-weight:700;fill:#fff}</style>',
        '<text x="20" y="24" font-size="16" font-weight="700">CO2 pathway decision map</text>',
        '<text x="20" y="42" class="small">Winner minimizes net cost subject to net avoided emissions constraint</text>',
    ]
    for i, x in enumerate(xs):
        px = left + i * cell_w + cell_w / 2
        parts.append(f'<text x="{px:.1f}" y="{top - 10}" text-anchor="middle" class="small">{x:.0f}</text>')
    for j, y in enumerate(ys):
        py = top + j * cell_h + cell_h / 2 + 4
        parts.append(f'<text x="{left - 10}" y="{py:.1f}" text-anchor="end" class="small">{y:.2f}</text>')
    parts.append(
        f'<text x="{left + len(xs) * cell_w / 2:.1f}" y="{top + len(ys) * cell_h + 34}" text-anchor="middle" class="axis">Electricity price (USD/MWh)</text>'
    )
    parts.append(
        f'<text x="18" y="{top + len(ys) * cell_h / 2:.1f}" transform="rotate(-90 18 {top + len(ys) * cell_h / 2:.1f})" text-anchor="middle" class="axis">H2 price (USD/kg)</text>'
    )

    for j, y in enumerate(ys):
        for i, x in enumerate(xs):
            winner = by_point[(x, y)]
            px = left + i * cell_w
            py = top + j * cell_h
            color = colors.get(winner, "#999999")
            text = escape(abbrev.get(winner, "???"))
            parts.append(f'<rect x="{px}" y="{py}" width="{cell_w}" height="{cell_h}" fill="{color}" stroke="#ffffff" stroke-width="1"/>')
            parts.append(f'<text x="{px + cell_w / 2:.1f}" y="{py + cell_h / 2 + 4:.1f}" text-anchor="middle" class="cell">{text}</text>')

    legend_items = [winner for winner in colors if any(str(r["winner"]) == winner for r in records)]
    parts.append(f'<text x="20" y="{legend_top}" class="axis">Legend</text>')
    for idx, winner in enumerate(legend_items):
        lx = 20 + (idx % 3) * 190
        ly = legend_top + 22 + (idx // 3) * 24
        parts.append(f'<rect x="{lx}" y="{ly - 12}" width="14" height="14" fill="{colors[winner]}"/>')
        parts.append(f'<text x="{lx + 22}" y="{ly}" class="small">{escape(labels[winner])} ({escape(abbrev[winner])})</text>')
    parts.append("</svg>")
    return "\n".join(parts)


def best_by_technology_family(
    scenario: Scenario,
    metric: str = "net_cost",
) -> list[dict[str, float | str]]:
    evaluations = evaluate_all(scenario)
    families = sorted({ev.inventory.technology_family for ev in evaluations})
    records: list[dict[str, float | str]] = []
    for family in families:
        family_evaluations = [
            ev for ev in evaluations if ev.inventory.technology_family == family
        ]
        winner = choose_best(
            family_evaluations,
            metric=metric,
            min_net_avoided_kgco2e=scenario.min_net_avoided_kgco2e_per_tco2,
        )
        if winner is None:
            continue
        records.append(
            {
                "technology_family": family,
                "best_pathway": winner.inventory.pathway,
                "category": winner.inventory.category,
                "product": winner.inventory.product_name,
                "net_cost_usd_per_tco2": winner.economics.net_cost_usd_per_tco2,
                "abatement_cost_usd_per_tco2_avoided": winner.economics.abatement_cost_usd_per_tco2_avoided,
                "net_avoided_kgco2e_per_tco2": winner.lca.net_avoided_kgco2e,
                "durable_retained_kgco2_per_tco2": winner.lca.durable_retained_kgco2,
                "market_capacity_mtco2_per_year": winner.inventory.market_capacity_mtco2_per_year,
                "carbon_residence_years": winner.inventory.carbon_residence_years,
            }
        )
    return records
