"""Summarize and plot expanded real-data spatial scenarios."""

from __future__ import annotations

import csv
import math
from html import escape
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output"
REAL_INPUTS = ROOT / "data" / "real_inputs_top300"
FIGURES = ROOT / "docs" / "figures_real"


SCENARIO_ORDER = [
    "current_2030",
    "current_2040",
    "current_2050",
    "mid_policy_2040",
    "high_policy_2050",
]

FAMILY_COLORS = {
    "storage": "#4c78a8",
    "mineralization": "#59a14f",
    "thermochemical": "#f28e2b",
    "electrochemical": "#b07aa1",
    "photochemical": "#edc948",
}

MONTE_CARLO_OUTPUT = OUTPUT / "expanded_monte_carlo_top300_target450.csv"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_svg(path: Path, svg: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(svg, encoding="utf-8")


def num(row: dict[str, str], key: str, default: float = 0.0) -> float:
    value = row.get(key, "")
    try:
        return float(value)
    except ValueError:
        return default


def scenario_sort_key(row: dict[str, Any]) -> int:
    scenario = str(row.get("scenario", ""))
    return SCENARIO_ORDER.index(scenario) if scenario in SCENARIO_ORDER else len(SCENARIO_ORDER)


def system_rows(summary: list[dict[str, str]]) -> list[dict[str, Any]]:
    rows = []
    for row in summary:
        if row["scope"] != "system_total":
            continue
        rows.append(
            {
                "scenario": row["scenario"],
                "technology_year": int(float(row["technology_year"])),
                "policy_source": row["policy_source"],
                "allocated_mtco2_per_year": num(row, "allocated_mtco2_per_year"),
                "annual_net_cost_musd_per_year": num(row, "annual_net_cost_musd_per_year"),
                "annual_net_avoided_mtco2e_per_year": num(row, "annual_net_avoided_mtco2e_per_year"),
                "weighted_net_cost_usd_per_tco2": num(row, "weighted_net_cost_usd_per_tco2"),
                "weighted_net_avoided_tco2e_per_tco2": num(row, "weighted_net_avoided_tco2e_per_tco2"),
                "carbon_price_usd_per_tco2": num(row, "carbon_price_usd_per_tco2"),
                "carbon_tax_usd_per_tco2": num(row, "carbon_tax_usd_per_tco2"),
                "durable_removal_credit_usd_per_tco2": num(row, "durable_removal_credit_usd_per_tco2"),
            }
        )
    return sorted(rows, key=scenario_sort_key)


def transport_mix(allocations: list[dict[str, str]], scenario: str) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, float]] = {}
    for row in allocations:
        mode = row["transport_mode"]
        bucket = grouped.setdefault(mode, {"allocated": 0.0, "distance_weighted": 0.0, "cost": 0.0})
        allocated = num(row, "allocated_mtco2_per_year")
        bucket["allocated"] += allocated
        bucket["distance_weighted"] += allocated * num(row, "routed_distance_km")
        bucket["cost"] += num(row, "annual_net_cost_musd_per_year")
    rows = []
    for mode, bucket in sorted(grouped.items()):
        allocated = bucket["allocated"]
        rows.append(
            {
                "scenario": scenario,
                "transport_mode": mode,
                "allocated_mtco2_per_year": allocated,
                "weighted_routed_distance_km": bucket["distance_weighted"] / allocated if allocated else 0.0,
                "annual_net_cost_musd_per_year": bucket["cost"],
            }
        )
    return rows


def top_routes(allocations: list[dict[str, str]], scenario: str, limit: int = 40) -> list[dict[str, Any]]:
    sorted_rows = sorted(allocations, key=lambda row: num(row, "allocated_mtco2_per_year"), reverse=True)
    output: list[dict[str, Any]] = []
    for row in sorted_rows[:limit]:
        output.append(
            {
                "scenario": scenario,
                "source_id": row["source_id"],
                "source_region": row["source_region"],
                "source_type": row["source_type"],
                "destination_id": row["destination_id"],
                "destination_region": row["destination_region"],
                "pathway": row["pathway"],
                "technology_family": row["technology_family"],
                "transport_mode": row["transport_mode"],
                "allocated_mtco2_per_year": num(row, "allocated_mtco2_per_year"),
                "routed_distance_km": num(row, "routed_distance_km"),
                "adjusted_net_cost_usd_per_tco2": num(row, "adjusted_net_cost_usd_per_tco2"),
                "adjusted_net_avoided_kgco2e_per_tco2": num(row, "adjusted_net_avoided_kgco2e_per_tco2"),
            }
        )
    return output


def grouped_bar_svg(path: Path, rows: list[dict[str, Any]]) -> None:
    width, height = 980, 580
    left, right, top, bottom = 110, 60, 88, 92
    plot_w = width - left - right
    plot_h = height - top - bottom
    max_cost = max(float(row["weighted_net_cost_usd_per_tco2"]) for row in rows) * 1.1
    max_avoided = max(float(row["weighted_net_avoided_tco2e_per_tco2"]) for row in rows) * 1.2
    group_w = plot_w / max(len(rows), 1)
    cost_w = group_w * 0.28
    avoided_w = group_w * 0.28
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        '<style>text{font-family:Arial,Helvetica,sans-serif;fill:#222}.title{font-size:20px;font-weight:700}.small{font-size:12px}.axis{stroke:#333}.grid{stroke:#e6e9ee}</style>',
        '<text x="35" y="32" class="title">Expanded scenario system performance</text>',
        '<text x="35" y="56" class="small">Top 300 China CO2 sources, 575 MtCO2/yr equality target, routed transport counted once.</text>',
    ]
    for i in range(6):
        y = top + plot_h - plot_h * i / 5
        parts.append(f'<line x1="{left}" y1="{y:.1f}" x2="{width - right}" y2="{y:.1f}" class="grid"/>')
        parts.append(f'<text x="{left - 8}" y="{y + 4:.1f}" text-anchor="end" class="small">{max_cost * i / 5:.0f}</text>')
    parts.append(f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_h}" class="axis"/>')
    parts.append(f'<line x1="{left}" y1="{top + plot_h}" x2="{width - right}" y2="{top + plot_h}" class="axis"/>')
    for idx, row in enumerate(rows):
        x0 = left + idx * group_w + group_w * 0.18
        cost = float(row["weighted_net_cost_usd_per_tco2"])
        avoided = float(row["weighted_net_avoided_tco2e_per_tco2"])
        cost_h = cost / max_cost * plot_h
        avoided_h = avoided / max_avoided * plot_h
        parts.append(f'<rect x="{x0:.1f}" y="{top + plot_h - cost_h:.1f}" width="{cost_w:.1f}" height="{cost_h:.1f}" rx="4" fill="#4c78a8"/>')
        parts.append(f'<rect x="{x0 + cost_w + 8:.1f}" y="{top + plot_h - avoided_h:.1f}" width="{avoided_w:.1f}" height="{avoided_h:.1f}" rx="4" fill="#59a14f"/>')
        parts.append(f'<text x="{x0 + cost_w / 2:.1f}" y="{top + plot_h - cost_h - 6:.1f}" text-anchor="middle" class="small">{cost:.0f}</text>')
        parts.append(f'<text x="{x0 + cost_w + 8 + avoided_w / 2:.1f}" y="{top + plot_h - avoided_h - 6:.1f}" text-anchor="middle" class="small">{avoided:.3f}</text>')
        label = escape(str(row["scenario"]).replace("_", " "))
        parts.append(f'<text x="{x0 + cost_w:.1f}" y="{top + plot_h + 22:.1f}" text-anchor="middle" class="small">{label}</text>')
    parts.append(f'<text x="{left}" y="{height - 24}" class="small" fill="#4c78a8">Blue: weighted net cost, USD/tCO2</text>')
    parts.append(f'<text x="{left + 280}" y="{height - 24}" class="small" fill="#59a14f">Green: weighted net avoided, tCO2e/tCO2, scaled to right axis</text>')
    parts.append("</svg>")
    write_svg(path, "\n".join(parts))


def stacked_family_svg(path: Path, family_rows: list[dict[str, str]]) -> None:
    scenarios = SCENARIO_ORDER
    families = sorted({row["technology_family"] for row in family_rows})
    by_key = {(row["scenario"], row["technology_family"]): num(row, "allocated_mtco2_per_year") for row in family_rows}
    width, height = 980, 560
    left, right, top, bottom = 90, 210, 78, 82
    plot_w = width - left - right
    plot_h = height - top - bottom
    max_total = max(sum(by_key.get((scenario, family), 0.0) for family in families) for scenario in scenarios) * 1.05
    bar_w = plot_w / max(len(scenarios), 1) * 0.58
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        '<style>text{font-family:Arial,Helvetica,sans-serif;fill:#222}.title{font-size:20px;font-weight:700}.small{font-size:12px}.axis{stroke:#333}.grid{stroke:#e6e9ee}</style>',
        '<text x="35" y="32" class="title">Allocation by technology family</text>',
        '<text x="35" y="56" class="small">LP solution under destination capacities, pathway market ceilings, water, land, and hub constraints.</text>',
    ]
    for i in range(6):
        y = top + plot_h - plot_h * i / 5
        parts.append(f'<line x1="{left}" y1="{y:.1f}" x2="{width - right}" y2="{y:.1f}" class="grid"/>')
        parts.append(f'<text x="{left - 8}" y="{y + 4:.1f}" text-anchor="end" class="small">{max_total * i / 5:.0f}</text>')
    parts.append(f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_h}" class="axis"/>')
    parts.append(f'<line x1="{left}" y1="{top + plot_h}" x2="{width - right}" y2="{top + plot_h}" class="axis"/>')
    for idx, scenario in enumerate(scenarios):
        x = left + (idx + 0.5) * plot_w / len(scenarios) - bar_w / 2
        y_base = top + plot_h
        for family in families:
            value = by_key.get((scenario, family), 0.0)
            h = value / max_total * plot_h
            y_base -= h
            parts.append(f'<rect x="{x:.1f}" y="{y_base:.1f}" width="{bar_w:.1f}" height="{h:.1f}" fill="{FAMILY_COLORS.get(family, "#777")}"/>')
        label = escape(scenario.replace("_", " "))
        parts.append(f'<text x="{x + bar_w / 2:.1f}" y="{top + plot_h + 22:.1f}" text-anchor="middle" class="small">{label}</text>')
    legend_x, legend_y = width - right + 35, top + 22
    for idx, family in enumerate(families):
        y = legend_y + idx * 24
        parts.append(f'<rect x="{legend_x}" y="{y - 11}" width="14" height="14" fill="{FAMILY_COLORS.get(family, "#777")}"/>')
        parts.append(f'<text x="{legend_x + 22}" y="{y}" class="small">{escape(family)}</text>')
    parts.append(f'<text x="{left + plot_w / 2:.1f}" y="{height - 22}" text-anchor="middle" class="small">Allocated CO2, MtCO2/yr</text>')
    parts.append("</svg>")
    write_svg(path, "\n".join(parts))


def network_svg(
    path: Path,
    sources: list[dict[str, str]],
    destinations: list[dict[str, str]],
    allocations: list[dict[str, str]],
    scenario: str,
) -> None:
    source_by_id = {row["source_id"]: row for row in sources}
    dest_by_id = {row["destination_id"]: row for row in destinations}
    plotted_allocations = [
        row for row in allocations
        if row["source_id"] in source_by_id and row["destination_id"] in dest_by_id
    ]
    lats = [num(row, "latitude") for row in sources + destinations]
    lons = [num(row, "longitude") for row in sources + destinations]
    min_lat, max_lat = min(lats) - 2, max(lats) + 2
    min_lon, max_lon = min(lons) - 3, max(lons) + 3
    width, height = 1120, 720
    left, right, top, bottom = 80, 60, 72, 68
    plot_w = width - left - right
    plot_h = height - top - bottom

    def xy(row: dict[str, str]) -> tuple[float, float]:
        lon = num(row, "longitude")
        lat = num(row, "latitude")
        x = left + (lon - min_lon) / (max_lon - min_lon) * plot_w
        y = top + plot_h - (lat - min_lat) / (max_lat - min_lat) * plot_h
        return x, y

    max_flow = max([num(row, "allocated_mtco2_per_year") for row in plotted_allocations] + [1.0])
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        '<style>text{font-family:Arial,Helvetica,sans-serif;fill:#222}.title{font-size:20px;font-weight:700}.small{font-size:12px}.label{font-size:9px}</style>',
        f'<text x="35" y="32" class="title">Expanded allocation network: {escape(scenario)}</text>',
        '<text x="35" y="54" class="small">Line width scales with allocated MtCO2/yr; color indicates pathway family.</text>',
        f'<rect x="{left}" y="{top}" width="{plot_w}" height="{plot_h}" fill="#f8fafc" stroke="#d8dde5"/>',
    ]
    for row in plotted_allocations:
        source = source_by_id[row["source_id"]]
        dest = dest_by_id[row["destination_id"]]
        x1, y1 = xy(source)
        x2, y2 = xy(dest)
        family = row["technology_family"]
        flow = num(row, "allocated_mtco2_per_year")
        stroke_w = 0.6 + 7.0 * math.sqrt(flow / max_flow)
        parts.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{FAMILY_COLORS.get(family, "#777")}" stroke-width="{stroke_w:.2f}" stroke-opacity="0.42"/>')
    source_sample = sorted(sources, key=lambda row: num(row, "co2_available_mtpa"), reverse=True)[:300]
    for source in source_sample:
        x, y = xy(source)
        r = 1.6 + 4.2 * math.sqrt(num(source, "co2_available_mtpa") / 30.0)
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.1f}" fill="#222" fill-opacity="0.62"/>')
    for dest in destinations:
        x, y = xy(dest)
        parts.append(f'<rect x="{x - 4:.1f}" y="{y - 4:.1f}" width="8" height="8" fill="#ffffff" stroke="#222" stroke-width="1.2"/>')
    parts.append(f'<text x="35" y="{height - 28}" class="small">Black circles: CO2 sources. White squares: destinations.</text>')
    parts.append("</svg>")
    write_svg(path, "\n".join(parts))


def quantile(values: list[float], q: float) -> float:
    if not values:
        return math.nan
    ordered = sorted(values)
    pos = (len(ordered) - 1) * q
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return ordered[lo]
    return ordered[lo] * (hi - pos) + ordered[hi] * (pos - lo)


def monte_carlo_quantiles(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    system = [row for row in rows if row["scope"] == "system_total"]
    metrics = [
        "weighted_net_cost_usd_per_tco2",
        "weighted_net_avoided_tco2e_per_tco2",
        "annual_net_cost_musd_per_year",
        "annual_net_avoided_mtco2e_per_year",
    ]
    output: list[dict[str, Any]] = []
    for metric in metrics:
        values = [num(row, metric) for row in system]
        output.append(
            {
                "metric": metric,
                "runs": len(values),
                "min": min(values) if values else math.nan,
                "p05": quantile(values, 0.05),
                "p25": quantile(values, 0.25),
                "p50": quantile(values, 0.50),
                "p75": quantile(values, 0.75),
                "p95": quantile(values, 0.95),
                "max": max(values) if values else math.nan,
            }
        )
    return output


def monte_carlo_distribution_svg(path: Path, rows: list[dict[str, str]]) -> None:
    system = [row for row in rows if row["scope"] == "system_total"]
    costs = [num(row, "weighted_net_cost_usd_per_tco2") for row in system]
    avoided = [num(row, "weighted_net_avoided_tco2e_per_tco2") for row in system]
    width, height = 980, 540
    left, right, top, bottom = 86, 60, 76, 72
    plot_w = width - left - right
    plot_h = height - top - bottom
    cost_min, cost_max = min(costs), max(costs)
    avoided_min, avoided_max = min(avoided), max(avoided)
    cost_span = max(cost_max - cost_min, 1e-9)
    avoided_span = max(avoided_max - avoided_min, 1e-9)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        '<style>text{font-family:Arial,Helvetica,sans-serif;fill:#222}.title{font-size:20px;font-weight:700}.small{font-size:12px}.axis{stroke:#333}.grid{stroke:#e6e9ee}</style>',
        '<text x="35" y="32" class="title">Monte Carlo system outcomes</text>',
        '<text x="35" y="56" class="small">Top 300, 2040 mid-policy, 450 MtCO2/yr target, 30 uncertain parameters.</text>',
        f'<rect x="{left}" y="{top}" width="{plot_w}" height="{plot_h}" fill="#f8fafc" stroke="#d8dde5"/>',
    ]
    for i in range(5):
        y = top + plot_h - plot_h * i / 4
        parts.append(f'<line x1="{left}" y1="{y:.1f}" x2="{width - right}" y2="{y:.1f}" class="grid"/>')
        parts.append(f'<text x="{left - 8}" y="{y + 4:.1f}" text-anchor="end" class="small">{avoided_min + avoided_span * i / 4:.3f}</text>')
    for cost, avoid in zip(costs, avoided):
        x = left + (cost - cost_min) / cost_span * plot_w
        y = top + plot_h - (avoid - avoided_min) / avoided_span * plot_h
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="#4c78a8" fill-opacity="0.72"/>')
    parts.append(f'<text x="{left + plot_w / 2:.1f}" y="{height - 24}" text-anchor="middle" class="small">Weighted net cost, USD/tCO2</text>')
    parts.append(f'<text x="22" y="{top + plot_h / 2:.1f}" text-anchor="middle" class="small" transform="rotate(-90 22 {top + plot_h / 2:.1f})">Weighted net avoided, tCO2e/tCO2</text>')
    parts.append(f'<text x="{left}" y="{height - 48}" class="small">Cost range: {cost_min:.1f}-{cost_max:.1f} USD/tCO2; avoided range: {avoided_min:.3f}-{avoided_max:.3f} tCO2e/tCO2.</text>')
    parts.append("</svg>")
    write_svg(path, "\n".join(parts))


def main() -> None:
    summary = read_csv(OUTPUT / "expanded_scenario_summary.csv")
    family_rows = read_csv(OUTPUT / "expanded_scenario_family_mix.csv")
    systems = system_rows(summary)
    write_csv(OUTPUT / "expanded_system_summary.csv", systems)

    all_transport_rows: list[dict[str, Any]] = []
    all_top_routes: list[dict[str, Any]] = []
    allocation_by_scenario: dict[str, list[dict[str, str]]] = {}
    for scenario in SCENARIO_ORDER:
        path = OUTPUT / f"expanded_{scenario}_allocations.csv"
        if not path.exists():
            continue
        allocations = read_csv(path)
        allocation_by_scenario[scenario] = allocations
        all_transport_rows.extend(transport_mix(allocations, scenario))
        all_top_routes.extend(top_routes(allocations, scenario))
    write_csv(OUTPUT / "expanded_transport_mix.csv", all_transport_rows)
    write_csv(OUTPUT / "expanded_top_routes.csv", all_top_routes)

    grouped_bar_svg(FIGURES / "expanded_system_performance.svg", systems)
    stacked_family_svg(FIGURES / "expanded_family_mix.svg", family_rows)
    if "current_2030" in allocation_by_scenario:
        sources = read_csv(REAL_INPUTS / "spatial_sources_real.csv")
        destinations = read_csv(REAL_INPUTS / "spatial_destinations_real.csv")
        network_svg(
            FIGURES / "expanded_current_2030_network.svg",
            sources,
            destinations,
            allocation_by_scenario["current_2030"],
            "current_2030",
        )
    if MONTE_CARLO_OUTPUT.exists():
        monte_carlo_rows = read_csv(MONTE_CARLO_OUTPUT)
        write_csv(OUTPUT / "expanded_monte_carlo_quantiles.csv", monte_carlo_quantiles(monte_carlo_rows))
        monte_carlo_distribution_svg(FIGURES / "expanded_monte_carlo_target450.svg", monte_carlo_rows)


if __name__ == "__main__":
    main()
