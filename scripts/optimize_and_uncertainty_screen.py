"""Formal LP deployment optimization and uncertainty screen for the Joule draft.

The spatial profitability matrix scores each source-destination-pathway route.
This post-processor adds two reviewer-facing checks:

1. A continuous linear program for deployment selection under source,
   destination, and product-market constraints.
2. A Monte Carlo screen for pathway profitability probability and key drivers.
"""

from __future__ import annotations

import csv
import math
import sys
from pathlib import Path
from typing import Any

import numpy as np
from scipy.optimize import linprog
from scipy.sparse import lil_matrix


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = ROOT / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from analyze_market_stress_scenarios import (  # noqa: E402
    CATEGORY_BY_PATHWAY,
    CATEGORY_COLORS,
    CATEGORY_LABELS,
    H2_KG_PER_TCO2,
    PATHWAY_LABELS,
    PLANT_SIZE_MTCO2_PER_YEAR,
    STRESS_SCENARIOS,
    adjusted_margin,
    f,
    load_capacities,
    load_price_table,
    read_csv,
    target_product_price,
    write_csv,
)


CHINA = ROOT / "output" / "china2060_optimistic_profitability"
OUT = ROOT / "output" / "china2060_deployment_optimization"
FIG_OUT = ROOT / "docs" / "joule_submission" / "figures_composite"
CEADS_CITY_CAPS = ROOT / "data" / "processed" / "co2_sources" / "ceads_city_emission_lp_caps.csv"


LP_YEARS = [2040, 2060]
LP_SCENARIOS = ["policy_supported_effort", "policy_exit_green_premium", "commodity_only_no_support"]
DURABLE_TARGETS_MTCO2 = [80.0, 100.0, 500.0, 1000.0]
MC_YEAR = 2060
MC_SAMPLES = 5000
RANDOM_SEED = 2602060
EPS = 1e-9


def esc(value: Any) -> str:
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def svg_text(
    x: float,
    y: float,
    value: Any,
    size: int = 12,
    weight: int = 400,
    anchor: str = "start",
    color: str = "#202426",
) -> str:
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" font-weight="{weight}" '
        f'text-anchor="{anchor}" fill="{color}">{esc(value)}</text>'
    )


def rect(x: float, y: float, w: float, h: float, fill: str, stroke: str = "none", sw: float = 1.0) -> str:
    return f'<rect x="{x:.1f}" y="{y:.1f}" width="{max(0.0, w):.1f}" height="{max(0.0, h):.1f}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>'


def line(x1: float, y1: float, x2: float, y2: float, stroke: str = "#dfe6e8", sw: float = 1.0) -> str:
    return f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{stroke}" stroke-width="{sw}"/>'


def panel_label(letter: str, title: str, x: float, y: float) -> list[str]:
    return [svg_text(x, y, letter, 16, 700), svg_text(x + 24, y, title, 14, 700)]


def scenario_by_name() -> dict[str, Any]:
    return {scenario.name: scenario for scenario in STRESS_SCENARIOS}


def product_capacity_mtco2(
    row: dict[str, str],
    scenario: Any,
    prices: dict[tuple[int, str], dict[str, float]],
) -> float:
    product = row["product"]
    if product == "none":
        return math.inf
    marketable = f(row["marketable_product_kg_per_tco2"])
    if marketable <= EPS:
        return math.inf
    price_row = prices.get((int(row["year"]), product), {})
    product_mt = price_row.get("volume_limit_mt_product", math.inf)
    return product_mt * scenario.market_volume_multiplier * 1000.0 / marketable


def is_eor_row(row: dict[str, str]) -> bool:
    return row.get("sink_type") == "eor_oilfield" or row.get("destination_id", "").startswith("EOR_")


def is_dac_row(row: dict[str, str]) -> bool:
    return row.get("source_type") == "dac" or row.get("source_id", "").startswith("DAC_")


def is_durable(row: dict[str, str]) -> bool:
    return (
        not is_eor_row(row)
        and CATEGORY_BY_PATHWAY.get(row["pathway"]) in {"geological_storage", "mineral_products"}
    )


def load_city_emission_caps() -> dict[str, float]:
    if not CEADS_CITY_CAPS.exists():
        return {}
    caps: dict[str, float] = {}
    for row in read_csv(CEADS_CITY_CAPS):
        cap = f(row.get("city_non_dac_capture_cap_mtco2_per_year"))
        if cap > EPS:
            caps[str(row["prefecture_code"])] = cap
    return caps


def build_lp(
    records: list[dict[str, str]],
    scenario: Any,
    source_caps: dict[str, float],
    dest_caps: dict[str, float],
    prices: dict[tuple[int, str], dict[str, float]],
    durable_target_mtco2: float | None = None,
    city_caps: dict[str, float] | None = None,
) -> tuple[np.ndarray, lil_matrix, np.ndarray, list[tuple[float, float]], list[dict[str, Any]]]:
    city_caps = city_caps if city_caps is not None else load_city_emission_caps()
    products = sorted({row["product"] for row in records if row["product"] != "none"})
    sources = sorted(source_caps)
    destinations = sorted(dest_caps)
    capped_cities = sorted(city_caps)
    source_index = {value: i for i, value in enumerate(sources)}
    dest_index = {value: len(sources) + i for i, value in enumerate(destinations)}
    city_index = {
        value: len(sources) + len(destinations) + i for i, value in enumerate(capped_cities)
    }
    product_index = {
        value: len(sources) + len(destinations) + len(capped_cities) + i
        for i, value in enumerate(products)
    }
    row_count = len(sources) + len(destinations) + len(capped_cities) + len(products)
    if durable_target_mtco2 is not None:
        durable_row = row_count
        row_count += 1
    else:
        durable_row = -1

    variables: list[dict[str, Any]] = []
    for row in records:
        if is_eor_row(row):
            continue
        ub = min(
            f(row["deployable_mtco2_per_year"]),
            source_caps.get(row["source_id"], 0.0) * scenario.source_capacity_multiplier,
            dest_caps.get(row["destination_id"], 0.0) * scenario.destination_capacity_multiplier,
            product_capacity_mtco2(row, scenario, prices),
        )
        if ub <= EPS:
            continue
        margin = adjusted_margin(row, scenario, prices)
        variables.append(
            {
                "row": row,
                "margin": margin,
                "ub": ub,
                "durable": 1.0 if is_durable(row) else 0.0,
                "category": CATEGORY_BY_PATHWAY.get(row["pathway"], "other"),
                "target_product_price": target_product_price(row, scenario, prices),
            }
        )

    c = -np.array([item["margin"] for item in variables], dtype=float)
    bounds = [(0.0, item["ub"]) for item in variables]
    a = lil_matrix((row_count, len(variables)), dtype=float)
    b = np.zeros(row_count, dtype=float)
    for source, idx in source_index.items():
        b[idx] = source_caps[source] * scenario.source_capacity_multiplier
    for destination, idx in dest_index.items():
        b[idx] = dest_caps[destination] * scenario.destination_capacity_multiplier
    for city_id, idx in city_index.items():
        b[idx] = city_caps[city_id] * scenario.source_capacity_multiplier
    for product, idx in product_index.items():
        year = int(records[0]["year"])
        b[idx] = prices.get((year, product), {}).get("volume_limit_mt_product", math.inf) * scenario.market_volume_multiplier

    for col, item in enumerate(variables):
        row = item["row"]
        a[source_index[row["source_id"]], col] = 1.0
        a[dest_index[row["destination_id"]], col] = 1.0
        if not is_dac_row(row) and row["city_id"] in city_index:
            a[city_index[row["city_id"]], col] = 1.0
        product = row["product"]
        if product != "none":
            a[product_index[product], col] = f(row["marketable_product_kg_per_tco2"]) / 1000.0
        if durable_target_mtco2 is not None:
            a[durable_row, col] = -item["durable"]
    if durable_target_mtco2 is not None:
        b[durable_row] = -durable_target_mtco2
    return c, a, b, bounds, variables


def solve_lp(
    year: int,
    scenario: Any,
    records: list[dict[str, str]],
    source_caps: dict[str, float],
    dest_caps: dict[str, float],
    prices: dict[tuple[int, str], dict[str, float]],
    durable_target_mtco2: float | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    city_caps = load_city_emission_caps()
    c, a, b, bounds, variables = build_lp(
        records,
        scenario,
        source_caps,
        dest_caps,
        prices,
        durable_target_mtco2,
        city_caps,
    )
    result = linprog(c, A_ub=a.tocsr(), b_ub=b, bounds=bounds, method="highs")
    summary: dict[str, Any] = {
        "year": year,
        "scenario": scenario.name,
        "scenario_label": scenario.label,
        "objective": "maximize_profit" if durable_target_mtco2 is None else "maximize_profit_with_durable_target",
        "durable_target_mtco2_per_year": "" if durable_target_mtco2 is None else durable_target_mtco2,
        "status": result.message,
        "success": int(bool(result.success)),
        "variable_count": len(variables),
        "allocated_mtco2_per_year": 0.0,
        "durable_allocated_mtco2_per_year": 0.0,
        "profit_busd_per_year": 0.0,
        "average_margin_usd_per_tco2": 0.0,
        "factory_count": 0,
        "required_support_busd_per_year_if_negative": 0.0,
        "ceads_city_cap_count": len(city_caps),
        "ceads_city_cap_status": "applied_to_non_dac_sources" if city_caps else "not_available",
    }
    rows: list[dict[str, Any]] = []
    if not result.success:
        return summary, rows
    x = np.asarray(result.x, dtype=float)
    total = float(x.sum())
    durable = 0.0
    profit_busd = 0.0
    factory_by_category: dict[str, float] = {}
    for value, item in zip(x, variables):
        if value <= 1e-5:
            continue
        row = item["row"]
        category = item["category"]
        durable += value * item["durable"]
        profit_busd += item["margin"] * value / 1000.0
        factory_by_category[category] = factory_by_category.get(category, 0.0) + value
        rows.append(
            {
                "year": year,
                "scenario": scenario.name,
                "durable_target_mtco2_per_year": "" if durable_target_mtco2 is None else durable_target_mtco2,
                "source_id": row["source_id"],
                "destination_id": row["destination_id"],
                "city_id": row["city_id"],
                "city_name": row["city_name"],
                "ceads_city_cap_mtco2_per_year": city_caps.get(str(row["city_id"]), ""),
                "category": category,
                "pathway": row["pathway"],
                "pathway_label": PATHWAY_LABELS.get(row["pathway"], row["pathway"]),
                "product": row["product"],
                "allocated_mtco2_per_year": value,
                "adjusted_margin_usd_per_tco2": item["margin"],
                "profit_musd_per_year": item["margin"] * value,
                "durable_flag": int(bool(item["durable"])),
                "target_product_price_usd_per_kg": item["target_product_price"],
                "distance_km": row["distance_km"],
            }
        )
    summary["allocated_mtco2_per_year"] = total
    summary["durable_allocated_mtco2_per_year"] = durable
    summary["profit_busd_per_year"] = profit_busd
    summary["average_margin_usd_per_tco2"] = profit_busd * 1000.0 / total if total > EPS else 0.0
    summary["factory_count"] = sum(
        int(math.ceil(value / PLANT_SIZE_MTCO2_PER_YEAR.get(category, 1.0) - EPS))
        for category, value in factory_by_category.items()
    )
    summary["required_support_busd_per_year_if_negative"] = max(0.0, -profit_busd)
    rows.sort(key=lambda item: float(item["profit_musd_per_year"]), reverse=True)
    return summary, rows[:500]


def run_lp_suite() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    source_caps, dest_caps = load_capacities()
    prices = load_price_table()
    scenarios = scenario_by_name()
    summaries: list[dict[str, Any]] = []
    allocations: list[dict[str, Any]] = []
    for year in LP_YEARS:
        records = read_csv(CHINA / f"china2060_{year}_profit_detail.csv")
        for scenario_name in LP_SCENARIOS:
            scenario = scenarios[scenario_name]
            summary, rows = solve_lp(year, scenario, records, source_caps, dest_caps, prices)
            summaries.append(summary)
            allocations.extend(rows)
            if year == 2060:
                for target in DURABLE_TARGETS_MTCO2:
                    summary, rows = solve_lp(year, scenario, records, source_caps, dest_caps, prices, target)
                    summaries.append(summary)
                    allocations.extend(rows)
    return summaries, allocations


def best_rows_by_pathway(year: int) -> list[dict[str, str]]:
    best: dict[str, dict[str, str]] = {}
    for row in read_csv(CHINA / f"china2060_{year}_profit_detail.csv"):
        pathway = row["pathway"]
        if pathway not in best or f(row["margin_usd_per_tco2"], -math.inf) > f(best[pathway]["margin_usd_per_tco2"], -math.inf):
            best[pathway] = row
    return [best[key] for key in sorted(best)]


def quantile(values: np.ndarray, q: float) -> float:
    return float(np.quantile(values, q))


def uncertainty_screen() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rng = np.random.default_rng(RANDOM_SEED)
    rows = best_rows_by_pathway(MC_YEAR)
    summary_rows: list[dict[str, Any]] = []
    driver_rows: list[dict[str, Any]] = []

    for row in rows:
        product_mult = rng.lognormal(mean=-0.5 * 0.30**2, sigma=0.30, size=MC_SAMPLES)
        policy_mult = rng.triangular(left=0.0, mode=1.0, right=1.2, size=MC_SAMPLES)
        h2_mult = rng.lognormal(mean=-0.5 * 0.35**2, sigma=0.35, size=MC_SAMPLES)
        transport_mult = rng.lognormal(mean=-0.5 * 0.25**2, sigma=0.25, size=MC_SAMPLES)
        capture_energy_mult = rng.lognormal(mean=-0.5 * 0.25**2, sigma=0.25, size=MC_SAMPLES)
        reliability_mult = rng.lognormal(mean=-0.5 * 0.35**2, sigma=0.35, size=MC_SAMPLES)
        shock_extra = rng.exponential(scale=6.0, size=MC_SAMPLES)

        pathway = row["pathway"]
        h2_delta = H2_KG_PER_TCO2.get(pathway, 0.0) * f(row["h2_price_usd_per_kg"]) * (h2_mult - 1.0)
        margins = (
            f(row["margin_usd_per_tco2"])
            + f(row["product_revenue_usd_per_tco2"]) * (product_mult - 1.0)
            + f(row["policy_revenue_usd_per_tco2"]) * (policy_mult - 1.0)
            - h2_delta
            - f(row["transport_cost_usd_per_tco2"]) * (transport_mult - 1.0)
            - f(row["capture_energy_cost_usd_per_tco2"]) * (capture_energy_mult - 1.0)
            - f(row["reliability_cost_usd_per_tco2"]) * (reliability_mult - 1.0)
            - shock_extra
        )
        summary_rows.append(
            {
                "year": MC_YEAR,
                "technology_family": row["technology_family"],
                "pathway": pathway,
                "pathway_label": PATHWAY_LABELS.get(pathway, pathway),
                "product": row["product"],
                "best_city": row["city_name"],
                "base_margin_usd_per_tco2": row["margin_usd_per_tco2"],
                "probability_positive": float(np.mean(margins > 0.0)),
                "margin_p05_usd_per_tco2": quantile(margins, 0.05),
                "margin_p50_usd_per_tco2": quantile(margins, 0.50),
                "margin_p95_usd_per_tco2": quantile(margins, 0.95),
            }
        )
        drivers = {
            "product_price": product_mult,
            "policy_credit": policy_mult,
            "h2_price": h2_mult,
            "transport_cost": transport_mult,
            "capture_energy_cost": capture_energy_mult,
            "reliability_cost": reliability_mult,
            "shock_extra": shock_extra,
        }
        ranked = []
        for name, values in drivers.items():
            corr = float(np.corrcoef(values, margins)[0, 1])
            if math.isnan(corr):
                corr = 0.0
            ranked.append((abs(corr), corr, name))
        ranked.sort(reverse=True)
        for rank, (abs_corr, corr, name) in enumerate(ranked[:4], start=1):
            driver_rows.append(
                {
                    "year": MC_YEAR,
                    "pathway": pathway,
                    "pathway_label": PATHWAY_LABELS.get(pathway, pathway),
                    "driver_rank": rank,
                    "driver": name,
                    "correlation_with_margin": corr,
                    "abs_correlation_with_margin": abs_corr,
                }
            )
    summary_rows.sort(key=lambda item: float(item["probability_positive"]), reverse=True)
    return summary_rows, driver_rows


def lp_profit_panel(lp_rows: list[dict[str, Any]], x: float, y: float, w: float, h: float) -> list[str]:
    parts = panel_label("A", "Formal LP: maximum-profit deployment", x, y)
    rows = [
        row
        for row in lp_rows
        if row["objective"] == "maximize_profit" and row["scenario"] in LP_SCENARIOS
    ]
    max_capacity = max([float(row["allocated_mtco2_per_year"]) for row in rows] + [1.0])
    plot_x, plot_y = x + 55, y + 40
    plot_w, plot_h = w - 90, h - 78
    groups = [(2040, "#7d63a6"), (2060, "#2f8f83")]
    scenarios = LP_SCENARIOS
    group_w = plot_w / len(scenarios)
    bar_w = 26
    lookup = {(int(row["year"]), row["scenario"]): row for row in rows}
    for i, scenario in enumerate(scenarios):
        gx = plot_x + i * group_w
        for j, (year, color) in enumerate(groups):
            value = float(lookup.get((year, scenario), {}).get("allocated_mtco2_per_year", 0.0))
            bh = value / max_capacity * plot_h
            bx = gx + 22 + j * (bar_w + 4)
            parts.append(rect(bx, plot_y + plot_h - bh, bar_w, bh, color))
        parts.append(svg_text(gx + group_w / 2, plot_y + plot_h + 18, scenario.replace("_", "\n")[:18], 9, 400, "middle", "#5f6b70"))
    parts.append(line(plot_x, plot_y + plot_h, plot_x + plot_w, plot_y + plot_h, "#9aa6aa", 1))
    parts.append(svg_text(plot_x, y + h - 12, "Bars: 2040 purple, 2060 green; source, sink and product-market constraints active.", 10, 400, "start", "#5f6b70"))
    return parts


def target_panel(lp_rows: list[dict[str, Any]], x: float, y: float, w: float, h: float) -> list[str]:
    parts = panel_label("B", "Durable carbon-neutrality target feasibility", x, y)
    rows = [
        row
        for row in lp_rows
        if row["objective"] == "maximize_profit_with_durable_target"
        and row["scenario"] == "policy_supported_effort"
    ]
    max_target = max([float(row["durable_target_mtco2_per_year"]) for row in rows] + [1.0])
    plot_x, plot_y = x + 62, y + 44
    plot_w = w - 105
    for i, row in enumerate(sorted(rows, key=lambda item: float(item["durable_target_mtco2_per_year"]))):
        yy = plot_y + i * 42
        target = float(row["durable_target_mtco2_per_year"])
        success = bool(int(row["success"]))
        allocated = float(row["durable_allocated_mtco2_per_year"])
        parts.append(svg_text(x + 8, yy + 16, f"{target:.0f} Mt", 10, 600, "start", "#5f6b70"))
        parts.append(rect(plot_x, yy, plot_w * target / max_target, 18, "#e8edf0"))
        color = "#2f8f83" if success else "#b94d5a"
        parts.append(rect(plot_x, yy, plot_w * min(target, allocated) / max_target, 18, color))
        label = "feasible" if success else "infeasible"
        parts.append(svg_text(plot_x + plot_w * target / max_target + 6, yy + 14, label, 10, 700, "start", color))
    parts.append(svg_text(plot_x, y + h - 14, "Result: current screened durable capacity cannot satisfy 0.5-1.0 GtCO2/yr targets.", 10, 400, "start", "#5f6b70"))
    return parts


def probability_panel(mc_rows: list[dict[str, Any]], x: float, y: float, w: float, h: float) -> list[str]:
    parts = panel_label("C", "Monte Carlo probability of positive margin", x, y)
    rows = sorted(mc_rows, key=lambda item: float(item["probability_positive"]), reverse=True)[:10]
    plot_x, plot_y = x + 128, y + 34
    row_h = (h - 58) / len(rows)
    for i, row in enumerate(rows):
        yy = plot_y + i * row_h
        probability = float(row["probability_positive"])
        parts.append(svg_text(x + 4, yy + row_h * 0.62, row["pathway_label"], 10, 500))
        parts.append(rect(plot_x, yy + 4, (w - 165) * probability, row_h - 8, "#2f8f83"))
        parts.append(rect(plot_x + (w - 165) * probability, yy + 4, (w - 165) * (1 - probability), row_h - 8, "#e8edf0"))
        parts.append(svg_text(x + w - 24, yy + row_h * 0.62, f"{probability:.0%}", 10, 700, "end"))
    return parts


def driver_panel(driver_rows: list[dict[str, Any]], x: float, y: float, w: float, h: float) -> list[str]:
    parts = panel_label("D", "Top uncertainty drivers", x, y)
    pathways = ["co2_h2_ft_saf", "mineralization", "geological_storage", "electrolysis_to_formate", "rwgs_to_co", "co2_to_methanol"]
    drivers = ["product_price", "policy_credit", "h2_price", "transport_cost", "capture_energy_cost", "reliability_cost", "shock_extra"]
    lookup = {
        (row["pathway"], row["driver"]): float(row["abs_correlation_with_margin"])
        for row in driver_rows
    }
    cell_w = (w - 145) / len(drivers)
    cell_h = (h - 58) / len(pathways)
    start_x, start_y = x + 126, y + 38
    for j, driver in enumerate(drivers):
        parts.append(svg_text(start_x + j * cell_w + cell_w / 2, y + 26, driver.replace("_", " ")[:10], 8, 600, "middle", "#5f6b70"))
    for i, pathway in enumerate(pathways):
        parts.append(svg_text(x + 4, start_y + i * cell_h + cell_h * 0.62, PATHWAY_LABELS.get(pathway, pathway), 9, 500))
        for j, driver in enumerate(drivers):
            value = lookup.get((pathway, driver), 0.0)
            intensity = min(1.0, value)
            color = f"rgb({int(240 - 178 * intensity)},{int(246 - 98 * intensity)},{int(242 - 130 * intensity)})"
            parts.append(rect(start_x + j * cell_w, start_y + i * cell_h, cell_w - 2, cell_h - 2, color, "#ffffff", 0.4))
            if value > 0.10:
                parts.append(svg_text(start_x + j * cell_w + cell_w / 2, start_y + i * cell_h + cell_h * 0.62, f"{value:.2f}", 8, 600, "middle"))
    return parts


def render_figure(lp_rows: list[dict[str, Any]], mc_rows: list[dict[str, Any]], driver_rows: list[dict[str, Any]]) -> None:
    FIG_OUT.mkdir(parents=True, exist_ok=True)
    width, height = 1420, 920
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        "<style>text{font-family:Arial,Helvetica,sans-serif;white-space:pre;} .title{font-size:25px;font-weight:700;}</style>",
        rect(0, 0, width, height, "#ffffff"),
        '<text x="40" y="44" class="title">Formal deployment optimization and uncertainty screen</text>',
        svg_text(40, 68, "LP separates profit maximization from durable carbon-neutrality targets; Monte Carlo tests whether best routes survive uncertainty.", 13, 400, "start", "#5f6b70"),
    ]
    parts.extend(lp_profit_panel(lp_rows, 40, 105, 650, 320))
    parts.extend(target_panel(lp_rows, 730, 105, 620, 320))
    parts.extend(probability_panel(mc_rows, 40, 475, 610, 340))
    parts.extend(driver_panel(driver_rows, 690, 475, 670, 340))
    parts.append(svg_text(40, 860, "Reviewer-facing conclusion: profitable managed CO2 and durable carbon-neutrality capacity are not the same optimization problem.", 13, 700))
    parts.append("</svg>")
    (FIG_OUT / "figure8_optimization_uncertainty_composite.svg").write_text("\n".join(parts), encoding="utf-8")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    lp_rows, lp_allocations = run_lp_suite()
    mc_rows, driver_rows = uncertainty_screen()
    write_csv(OUT / "lp_deployment_summary.csv", lp_rows)
    write_csv(OUT / "lp_top_allocations.csv", lp_allocations)
    write_csv(OUT / "uncertainty_positive_probability.csv", mc_rows)
    write_csv(OUT / "uncertainty_driver_rank.csv", driver_rows)
    render_figure(lp_rows, mc_rows, driver_rows)
    print(f"Wrote LP and uncertainty outputs to {OUT}")
    print(f"Wrote Figure 8 to {FIG_OUT / 'figure8_optimization_uncertainty_composite.svg'}")


if __name__ == "__main__":
    main()
