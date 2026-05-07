"""Summarize and plot the real-data spatial allocation run."""

from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output"
REAL_INPUTS = ROOT / "data" / "real_inputs"
FIGURES = ROOT / "docs" / "figures_real"
DEFAULT_ALLOCATION = OUTPUT / "real_allocations_2024_top120_target550_fixed.csv"
LEGACY_ALLOCATION = OUTPUT / "real_allocations_2024_top120.csv"


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


def group_sum(rows: list[dict[str, str]], group_key: str, value_key: str) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = row.get(group_key, "")
        bucket = grouped.setdefault(key, {group_key: key, value_key: 0.0, "count": 0})
        bucket[value_key] += num(row, value_key)
        bucket["count"] += 1
    return sorted(grouped.values(), key=lambda item: item[value_key], reverse=True)


def source_mix(sources: list[dict[str, str]]) -> list[dict[str, Any]]:
    rows = group_sum(sources, "source_type", "co2_available_mtpa")
    total = sum(row["co2_available_mtpa"] for row in rows)
    for row in rows:
        row["share_percent"] = row["co2_available_mtpa"] / total * 100 if total else 0.0
    return rows


def destination_mix(allocations: list[dict[str, str]]) -> list[dict[str, Any]]:
    rows = group_sum(allocations, "destination_id", "allocated_mtco2_per_year")
    cost_by_dest: dict[str, float] = {}
    avoided_by_dest: dict[str, float] = {}
    for row in allocations:
        dest = row["destination_id"]
        cost_by_dest[dest] = cost_by_dest.get(dest, 0.0) + num(row, "annual_net_cost_musd_per_year")
        avoided_by_dest[dest] = avoided_by_dest.get(dest, 0.0) + num(row, "annual_net_avoided_mtco2e_per_year")
    for row in rows:
        amount = row["allocated_mtco2_per_year"]
        dest = row["destination_id"]
        row["annual_net_cost_musd_per_year"] = cost_by_dest.get(dest, 0.0)
        row["annual_net_avoided_mtco2e_per_year"] = avoided_by_dest.get(dest, 0.0)
        row["weighted_net_cost_usd_per_tco2"] = cost_by_dest.get(dest, 0.0) / amount if amount else math.inf
    return rows


def top_routes(allocations: list[dict[str, str]], limit: int = 30) -> list[dict[str, Any]]:
    sorted_rows = sorted(allocations, key=lambda row: num(row, "allocated_mtco2_per_year"), reverse=True)
    output: list[dict[str, Any]] = []
    for row in sorted_rows[:limit]:
        output.append(
            {
                "source_id": row["source_id"],
                "source_region": row["source_region"],
                "source_type": row["source_type"],
                "destination_id": row["destination_id"],
                "destination_region": row["destination_region"],
                "pathway": row["pathway"],
                "technology_family": row["technology_family"],
                "transport_mode": row["transport_mode"],
                "allocated_mtco2_per_year": num(row, "allocated_mtco2_per_year"),
                "distance_km": num(row, "distance_km"),
                "adjusted_net_cost_usd_per_tco2": num(row, "adjusted_net_cost_usd_per_tco2"),
                "adjusted_net_avoided_kgco2e_per_tco2": num(row, "adjusted_net_avoided_kgco2e_per_tco2"),
            }
        )
    return output


def bar_svg(
    path: Path,
    rows: list[dict[str, Any]],
    label_key: str,
    value_key: str,
    title: str,
    subtitle: str,
    color: str,
    max_rows: int = 12,
) -> None:
    rows = rows[:max_rows]
    width, height = 980, 560
    left, right, top, bottom = 230, 50, 78, 55
    plot_w = width - left - right
    plot_h = height - top - bottom
    max_v = max([float(row[value_key]) for row in rows] + [1.0])
    row_h = plot_h / max(len(rows), 1)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        '<style>text{font-family:Arial,Helvetica,sans-serif;fill:#222}.title{font-size:20px;font-weight:700}.small{font-size:12px}.label{font-size:12px}.grid{stroke:#e6e9ee}</style>',
        f'<text x="35" y="32" class="title">{title}</text>',
        f'<text x="35" y="54" class="small">{subtitle}</text>',
    ]
    for i, row in enumerate(rows):
        y = top + i * row_h + row_h * 0.18
        h = row_h * 0.62
        value = float(row[value_key])
        bar_w = value / max_v * plot_w
        parts.append(f'<text x="{left - 12}" y="{y + h * 0.68:.1f}" text-anchor="end" class="label">{row[label_key]}</text>')
        parts.append(f'<rect x="{left}" y="{y:.1f}" width="{bar_w:.1f}" height="{h:.1f}" rx="4" fill="{color}"/>')
        parts.append(f'<text x="{left + bar_w + 6:.1f}" y="{y + h * 0.68:.1f}" class="small">{value:.2f}</text>')
    parts.append(f'<text x="{left + plot_w / 2:.1f}" y="{height - 18}" text-anchor="middle" class="small">{value_key}</text>')
    parts.append("</svg>")
    write_svg(path, "\n".join(parts))


def network_svg(
    path: Path,
    sources: list[dict[str, str]],
    destinations: list[dict[str, str]],
    allocations: list[dict[str, str]],
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

    colors = {
        "storage": "#4c78a8",
        "mineralization": "#59a14f",
        "thermochemical": "#f28e2b",
        "electrochemical": "#b07aa1",
        "photochemical": "#edc948",
    }
    max_flow = max([num(row, "allocated_mtco2_per_year") for row in plotted_allocations] + [1.0])
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        '<style>text{font-family:Arial,Helvetica,sans-serif;fill:#222}.title{font-size:20px;font-weight:700}.small{font-size:12px}.label{font-size:9px}</style>',
        '<text x="35" y="32" class="title">Real-data CO2 source-destination allocation network</text>',
        '<text x="35" y="54" class="small">Schematic coordinate plot from Climate TRACE point sources, Figshare storage capacity, UN/LOCODE ports, and MEE/NBS grid factors.</text>',
        f'<rect x="{left}" y="{top}" width="{plot_w}" height="{plot_h}" fill="#f8fafc" stroke="#d8dde5"/>',
    ]
    for row in plotted_allocations:
        source = source_by_id[row["source_id"]]
        dest = dest_by_id[row["destination_id"]]
        x1, y1 = xy(source)
        x2, y2 = xy(dest)
        family = row["technology_family"]
        flow = num(row, "allocated_mtco2_per_year")
        stroke_w = 0.6 + 6.0 * math.sqrt(flow / max_flow)
        parts.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{colors.get(family, "#777")}" stroke-width="{stroke_w:.2f}" stroke-opacity="0.45"/>')
    for source in sources:
        x, y = xy(source)
        r = 2.0 + 5.0 * math.sqrt(num(source, "co2_available_mtpa") / 30.0)
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.1f}" fill="#222" fill-opacity="0.72"/>')
    for dest in destinations:
        x, y = xy(dest)
        parts.append(f'<rect x="{x - 4:.1f}" y="{y - 4:.1f}" width="8" height="8" fill="#ffffff" stroke="#222" stroke-width="1.2"/>')
    parts.append(f'<text x="35" y="{height - 28}" class="small">Black circles: CO2 sources. White squares: destinations. Blue lines: storage. Green lines: mineralization.</text>')
    parts.append("</svg>")
    write_svg(path, "\n".join(parts))


def main() -> None:
    sources = read_csv(REAL_INPUTS / "spatial_sources_real.csv")
    destinations = read_csv(REAL_INPUTS / "spatial_destinations_real.csv")
    allocation_path = DEFAULT_ALLOCATION if DEFAULT_ALLOCATION.exists() else LEGACY_ALLOCATION
    allocations = read_csv(allocation_path)
    mix = source_mix(sources)
    dest_mix = destination_mix(allocations)
    routes = top_routes(allocations)
    source_regions = group_sum(allocations, "source_region", "allocated_mtco2_per_year")
    families = group_sum(allocations, "technology_family", "allocated_mtco2_per_year")

    write_csv(OUTPUT / "real_source_mix.csv", mix)
    write_csv(OUTPUT / "real_allocation_by_destination.csv", dest_mix)
    write_csv(OUTPUT / "real_top_routes.csv", routes)
    write_csv(OUTPUT / "real_allocation_by_source_region.csv", source_regions)
    write_csv(OUTPUT / "real_allocation_by_family.csv", families)

    bar_svg(
        FIGURES / "real_source_mix.svg",
        mix,
        "source_type",
        "co2_available_mtpa",
        "Real-data source mix",
        "Top 120 Climate TRACE China point sources, 2024, with 90% capture-rate assumption.",
        "#59636f",
    )
    bar_svg(
        FIGURES / "real_allocation_by_destination.svg",
        dest_mix,
        "destination_id",
        "allocated_mtco2_per_year",
        "Allocated CO2 by destination",
        "LP allocation with current China CEA/CCER price snapshot and 20-year storage-potential constraint.",
        "#4c78a8",
    )
    bar_svg(
        FIGURES / "real_allocation_by_source_region.svg",
        source_regions,
        "source_region",
        "allocated_mtco2_per_year",
        "Allocated CO2 by source province",
        "Regional contribution among selected top point sources.",
        "#59a14f",
    )
    network_svg(FIGURES / "real_allocation_network.svg", sources, destinations, allocations)


if __name__ == "__main__":
    main()
