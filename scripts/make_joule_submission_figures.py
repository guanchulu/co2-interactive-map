"""Generate draft figures for the Joule submission package.

The figures are dependency-free SVGs. They are intended as manuscript-quality
drafts whose underlying data are traceable to the CSV outputs in
``output/standard_profitability_matrix``.
"""

from __future__ import annotations

import csv
import math
from html import escape
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "output" / "standard_profitability_matrix"
CHINA2060 = ROOT / "output" / "china2060_optimistic_profitability"
OUT = ROOT / "docs" / "joule_submission" / "figures"


COLORS = {
    "storage": "#2f6f9f",
    "mineralization": "#5a8f59",
    "thermochemical": "#c86b34",
    "electrochemical": "#8b6aa8",
    "photochemical": "#bca43a",
    "policy": "#4d4d4d",
    "grid": "#e6e6e6",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def write_svg(path: Path, parts: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(parts), encoding="utf-8")


def f(row: dict[str, str], key: str, default: float = 0.0) -> float:
    try:
        return float(row.get(key, ""))
    except ValueError:
        return default


def base_svg(width: int, height: int, title: str, subtitle: str = "") -> list[str]:
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        '<style>text{font-family:Arial,Helvetica,sans-serif;fill:#222} .title{font-size:24px;font-weight:700} .subtitle{font-size:13px;fill:#555} .label{font-size:13px} .small{font-size:11px;fill:#555} .axis{stroke:#333;stroke-width:1} .grid{stroke:#e6e6e6;stroke-width:1}</style>',
        f'<text x="34" y="36" class="title">{escape(title)}</text>',
    ]
    if subtitle:
        parts.append(f'<text x="34" y="60" class="subtitle">{escape(subtitle)}</text>')
    return parts


def finish(parts: list[str]) -> list[str]:
    parts.append("</svg>")
    return parts


def figure1_framework() -> None:
    width, height = 1120, 660
    parts = base_svg(
        width,
        height,
        "Figure 1. Spatial-temporal CO2 allocation framework",
        "Captured CO2 is matched to storage, utilization, markets, policies, and time-varying energy conditions.",
    )
    x0, y0 = 55, 120
    w, h = 190, 74
    nodes = [
        ("CO2 sources", x0, y0, "purity, pressure, capture cost, DAC"),
        ("Transport network", x0 + 250, y0, "pipeline, truck, rail, ship, hubs"),
        ("Destination candidates", x0 + 500, y0, "storage, mineralization, conversion"),
        ("Hourly energy", x0 + 250, y0 + 160, "electricity price, grid carbon, green H2"),
        ("Policy and markets", x0 + 500, y0 + 160, "carbon price, credits, product demand"),
        ("Profitability allocation", x0 + 750, y0 + 80, "margin, NPV proxy, break-even thresholds"),
    ]
    for title, x, y, note in nodes:
        parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" fill="#f7f8f8" stroke="#333"/>')
        parts.append(f'<text x="{x + w / 2}" y="{y + 30}" text-anchor="middle" class="label">{escape(title)}</text>')
        words = note.split(", ")
        parts.append(f'<text x="{x + w / 2}" y="{y + 52}" text-anchor="middle" class="small">{escape(words[0])}</text>')
        if len(words) > 1:
            parts.append(f'<text x="{x + w / 2}" y="{y + 66}" text-anchor="middle" class="small">{escape(", ".join(words[1:]))}</text>')
    arrows = [
        (x0 + w, y0 + h / 2, x0 + 250, y0 + h / 2),
        (x0 + 250 + w, y0 + h / 2, x0 + 500, y0 + h / 2),
        (x0 + 500 + w, y0 + h / 2, x0 + 750, y0 + 80 + h / 2),
        (x0 + 250 + w / 2, y0 + 160, x0 + 750, y0 + 80 + h / 2),
        (x0 + 500 + w, y0 + 160 + h / 2, x0 + 750, y0 + 80 + h / 2),
    ]
    parts.append('<defs><marker id="arrow" markerWidth="10" markerHeight="8" refX="9" refY="4" orient="auto"><path d="M0,0 L10,4 L0,8 z" fill="#333"/></marker></defs>')
    for x1, y1, x2, y2 in arrows:
        parts.append(f'<line x1="{x1}" y1="{y1}" x2="{x2 - 10}" y2="{y2}" stroke="#333" stroke-width="1.6" marker-end="url(#arrow)"/>')
    families = [
        ("Geological storage", COLORS["storage"]),
        ("Mineralization", COLORS["mineralization"]),
        ("Thermochemical", COLORS["thermochemical"]),
        ("Electrochemical", COLORS["electrochemical"]),
        ("Photochemical", COLORS["photochemical"]),
    ]
    parts.append('<text x="55" y="440" class="label">Compared technology families</text>')
    for idx, (label, color) in enumerate(families):
        x = 55 + idx * 205
        parts.append(f'<rect x="{x}" y="465" width="170" height="48" rx="8" fill="{color}" opacity="0.88"/>')
        parts.append(f'<text x="{x + 85}" y="494" text-anchor="middle" class="label" fill="#fff">{escape(label)}</text>')
    parts.append('<text x="55" y="575" class="small">Functional unit: one tonne of captured CO2 entering each route; output metrics include cost, net avoided emissions, durability, market capacity, and city-level assignment.</text>')
    write_svg(OUT / "figure1_framework.svg", finish(parts))


def figure2_national_screen() -> None:
    rows = read_csv(MATRIX / "china_current_2030_profit_detail.csv")
    best_by_city: dict[str, dict[str, str]] = {}
    for row in rows:
        city = row["city_id"]
        incumbent = best_by_city.get(city)
        if incumbent is None or f(row, "margin_usd_per_tco2", -math.inf) > f(incumbent, "margin_usd_per_tco2", -math.inf):
            best_by_city[city] = row
    selected = sorted(best_by_city.values(), key=lambda row: f(row, "margin_usd_per_tco2", -math.inf), reverse=True)[:50]
    width, height = 1120, 720
    parts = base_svg(
        width,
        height,
        "Figure 2. Prefecture-level national screening",
        "Top candidate cities in the 2030 China baseline; city attribution uses polygon boundary joins.",
    )
    lats = [f(row, "latitude") for row in read_csv(ROOT / "data" / "processed" / "admin" / "source_prefecture_join_top300_with_dac.csv")]
    lons = [f(row, "longitude") for row in read_csv(ROOT / "data" / "processed" / "admin" / "source_prefecture_join_top300_with_dac.csv")]
    min_lat, max_lat = min(lats) - 2, max(lats) + 2
    min_lon, max_lon = min(lons) - 3, max(lons) + 3
    left, top, plot_w, plot_h = 75, 95, 820, 540

    def xy(row: dict[str, str]) -> tuple[float, float]:
        lon, lat = f(row, "longitude"), f(row, "latitude")
        x = left + (lon - min_lon) / (max_lon - min_lon) * plot_w
        y = top + plot_h - (lat - min_lat) / (max_lat - min_lat) * plot_h
        return x, y

    for i in range(7):
        x = left + plot_w * i / 6
        y = top + plot_h * i / 6
        parts.append(f'<line x1="{x:.1f}" y1="{top}" x2="{x:.1f}" y2="{top + plot_h}" class="grid"/>')
        parts.append(f'<line x1="{left}" y1="{y:.1f}" x2="{left + plot_w}" y2="{y:.1f}" class="grid"/>')
    source_join = {
        row["entity_id"]: row for row in read_csv(ROOT / "data" / "processed" / "admin" / "source_prefecture_join_top300_with_dac.csv")
    }
    for row in selected:
        join = source_join.get(row["source_id"])
        if not join:
            continue
        x, y = xy(join)
        family = row["technology_family"]
        margin = f(row, "margin_usd_per_tco2")
        radius = 4 + min(14, abs(margin) / 35)
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{radius:.1f}" fill="{COLORS.get(family, "#777")}" opacity="0.76" stroke="#222" stroke-width="0.4"/>')
    legend_x = 930
    parts.append(f'<text x="{legend_x}" y="130" class="label">Technology family</text>')
    for idx, family in enumerate(["storage", "mineralization", "thermochemical", "electrochemical", "photochemical"]):
        y = 160 + idx * 28
        parts.append(f'<circle cx="{legend_x + 8}" cy="{y - 4}" r="7" fill="{COLORS[family]}"/>')
        parts.append(f'<text x="{legend_x + 24}" y="{y}" class="small">{escape(family)}</text>')
    parts.append(f'<text x="{legend_x}" y="335" class="label">Baseline result</text>')
    parts.append(f'<text x="{legend_x}" y="360" class="small">No positive-margin routes</text>')
    parts.append(f'<text x="{legend_x}" y="380" class="small">Best route remains storage</text>')
    parts.append(f'<text x="75" y="675" class="small">Bubble size scales with absolute profitability gap. This is a screening map, not a legal boundary map.</text>')
    write_svg(OUT / "figure2_prefecture_screen.svg", finish(parts))


def figure3_thresholds() -> None:
    rows = read_csv(MATRIX / "technology_profitability_thresholds.csv")
    rows = sorted(rows, key=lambda row: f(row, "profitability_gap_usd_per_tco2"))[:12]
    width, height = 1120, 760
    parts = base_svg(
        width,
        height,
        "Figure 3. Break-even thresholds by pathway",
        "Current screening parameters identify the product-price or policy-credit gap required for profitability.",
    )
    left, top, plot_w, row_h = 330, 95, 650, 44
    max_gap = max(f(row, "profitability_gap_usd_per_tco2") for row in rows) * 1.05
    for idx, row in enumerate(rows):
        y = top + idx * row_h
        gap = f(row, "profitability_gap_usd_per_tco2")
        bw = gap / max_gap * plot_w
        family = row["technology_family"]
        label = f"{row['pathway']} ({row['product']})"
        parts.append(f'<text x="40" y="{y + 25}" class="small">{escape(label[:42])}</text>')
        parts.append(f'<rect x="{left}" y="{y + 6}" width="{bw:.1f}" height="24" rx="6" fill="{COLORS.get(family, "#777")}" opacity="0.9"/>')
        parts.append(f'<text x="{left + bw + 8:.1f}" y="{y + 24}" class="small">{gap:.0f} USD/tCO2 gap</text>')
    parts.append('<text x="40" y="700" class="small">Reading: the shorter the bar, the closer the pathway is to break-even under its best tested scenario.</text>')
    write_svg(OUT / "figure3_profitability_thresholds.svg", finish(parts))


def figure4_scenarios() -> None:
    rows = read_csv(MATRIX / "standard_scenario_system_summary.csv")
    width, height = 1120, 640
    parts = base_svg(
        width,
        height,
        "Figure 4. Scenario matrix",
        "Best route margin across policy, energy, product-premium, DAC, and learning scenarios.",
    )
    left, top, plot_w, plot_h = 140, 105, 820, 380
    values = [f(row, "best_margin_usd_per_tco2") for row in rows]
    min_v, max_v = min(values), max(values)
    y0 = top + plot_h
    parts.append(f'<line x1="{left}" y1="{y0}" x2="{left + plot_w}" y2="{y0}" class="axis"/>')
    for idx, row in enumerate(rows):
        x = left + (idx + 0.5) * plot_w / len(rows)
        value = f(row, "best_margin_usd_per_tco2")
        h = (value - min_v) / max(max_v - min_v, 1e-9) * (plot_h - 25) + 8
        y = y0 - h
        parts.append(f'<rect x="{x - 32:.1f}" y="{y:.1f}" width="64" height="{h:.1f}" rx="6" fill="#2f6f9f" opacity="0.86"/>')
        parts.append(f'<text x="{x:.1f}" y="{y - 8:.1f}" text-anchor="middle" class="small">{value:.1f}</text>')
        label = row["scenario"].replace("_", " ")
        parts.append(f'<text x="{x:.1f}" y="{y0 + 24}" text-anchor="end" transform="rotate(-35 {x:.1f} {y0 + 24})" class="small">{escape(label)}</text>')
    parts.append(f'<text x="36" y="{top + 35}" class="small">Best margin, USD/tCO2</text>')
    parts.append(f'<text x="36" y="{top + 55}" class="small">All tested scenarios remain below zero.</text>')
    write_svg(OUT / "figure4_scenario_matrix.svg", finish(parts))


def figure5_china2060_windows() -> None:
    system_path = CHINA2060 / "china2060_system_summary.csv"
    windows_path = CHINA2060 / "china2060_earliest_profit_windows.csv"
    if not system_path.exists() or not windows_path.exists():
        return
    system_rows = read_csv(system_path)
    window_rows = read_csv(windows_path)
    width, height = 1120, 720
    parts = base_svg(
        width,
        height,
        "Figure 5. China 2030-2060 optimistic profitability windows",
        "Under a dual-carbon effort case, positive margins first appear after 2030 and broaden toward 2060.",
    )
    left, top, plot_w, plot_h = 90, 100, 620, 310
    max_count = max(f(row, "positive_candidate_count") for row in system_rows)
    for idx, row in enumerate(system_rows):
        x = left + idx * plot_w / (len(system_rows) - 1)
        count = f(row, "positive_candidate_count")
        y = top + plot_h - count / max(max_count, 1) * plot_h
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="7" fill="#2f6f9f"/>')
        if idx:
            prev = system_rows[idx - 1]
            px = left + (idx - 1) * plot_w / (len(system_rows) - 1)
            py = top + plot_h - f(prev, "positive_candidate_count") / max(max_count, 1) * plot_h
            parts.append(f'<line x1="{px:.1f}" y1="{py:.1f}" x2="{x:.1f}" y2="{y:.1f}" stroke="#2f6f9f" stroke-width="3"/>')
        parts.append(f'<text x="{x:.1f}" y="{top + plot_h + 26}" text-anchor="middle" class="small">{row["year"]}</text>')
        parts.append(f'<text x="{x:.1f}" y="{y - 12:.1f}" text-anchor="middle" class="small">{int(count)}</text>')
    parts.append(f'<line x1="{left}" y1="{top + plot_h}" x2="{left + plot_w}" y2="{top + plot_h}" class="axis"/>')
    parts.append(f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_h}" class="axis"/>')
    parts.append(f'<text x="{left + plot_w / 2}" y="{top + plot_h + 58}" text-anchor="middle" class="label">Year in China dual-carbon effort scenario</text>')
    parts.append(f'<text x="30" y="{top + 25}" class="small">Positive candidates</text>')

    x0, y0 = 760, 108
    parts.append(f'<text x="{x0}" y="{y0}" class="label">First profitable year</text>')
    selected = [
        ("mineralization", "Mineralization", COLORS["mineralization"]),
        ("geological_storage", "Storage", COLORS["storage"]),
        ("co2_h2_ft_saf", "FT-SAF", COLORS["thermochemical"]),
        ("rwgs_to_co", "RWGS-CO", COLORS["thermochemical"]),
        ("electrolysis_to_formate", "Electro-formate", COLORS["electrochemical"]),
        ("photoelectrochemical_to_formate", "PEC-formate", COLORS["photochemical"]),
    ]
    by_pathway = {row["pathway"]: row for row in window_rows}
    for idx, (pathway, label, color) in enumerate(selected):
        row = by_pathway.get(pathway)
        year = row.get("first_profitable_year", "") if row else ""
        y = y0 + 42 + idx * 54
        parts.append(f'<rect x="{x0}" y="{y - 22}" width="22" height="22" rx="4" fill="{color}"/>')
        parts.append(f'<text x="{x0 + 34}" y="{y - 5}" class="small">{escape(label)}</text>')
        text = f"{year}" if year else "not by 2060"
        parts.append(f'<text x="{x0 + 230}" y="{y - 5}" class="small">{escape(text)}</text>')
    parts.append(f'<text x="{left}" y="655" class="small">Interpretation: 2035 mineralization opens first; 2040 storage, FT-SAF, RWGS-CO, and electro-formate become positive only under strong price, policy, H2, power, and learning efforts.</text>')
    write_svg(OUT / "figure5_china2060_profit_windows.svg", finish(parts))


def graphical_abstract() -> None:
    width = height = 1650
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        '<style>text{font-family:Arial,Helvetica,sans-serif;fill:#222}.title{font-size:58px;font-weight:700}.label{font-size:36px}.small{font-size:28px;fill:#555}</style>',
        '<text x="825" y="115" text-anchor="middle" class="title">Where should captured CO2 go?</text>',
        '<text x="825" y="170" text-anchor="middle" class="small">A spatial-temporal allocation model for storage, utilization, DAC, markets, and policy</text>',
    ]
    parts.append('<defs><marker id="ga_arrow" markerWidth="14" markerHeight="12" refX="13" refY="6" orient="auto"><path d="M0,0 L14,6 L0,12 z" fill="#333"/></marker></defs>')
    center_x, center_y = 825, 760
    parts.append(f'<circle cx="{center_x}" cy="{center_y}" r="150" fill="#f2f5f5" stroke="#333" stroke-width="4"/>')
    parts.append(f'<text x="{center_x}" y="{center_y - 10}" text-anchor="middle" class="label">Captured CO2</text>')
    parts.append(f'<text x="{center_x}" y="{center_y + 42}" text-anchor="middle" class="small">purity, pressure, cost</text>')
    targets = [
        ("Storage", 360, 430, COLORS["storage"]),
        ("Minerals", 1290, 430, COLORS["mineralization"]),
        ("CO / methanol", 350, 1110, COLORS["thermochemical"]),
        ("Formate / CO", 825, 1260, COLORS["electrochemical"]),
        ("SAF / fuels", 1300, 1110, COLORS["thermochemical"]),
    ]
    for label, x, y, color in targets:
        parts.append(f'<line x1="{center_x}" y1="{center_y}" x2="{x}" y2="{y}" stroke="#333" stroke-width="4" marker-end="url(#ga_arrow)"/>')
        parts.append(f'<rect x="{x - 170}" y="{y - 65}" width="340" height="130" rx="8" fill="{color}" opacity="0.9"/>')
        parts.append(f'<text x="{x}" y="{y + 12}" text-anchor="middle" class="label" fill="#fff">{escape(label)}</text>')
    parts.append('<text x="825" y="1500" text-anchor="middle" class="small">The best route depends on city, transport distance, hourly power, H2, product demand, and credit eligibility.</text>')
    write_svg(OUT / "graphical_abstract_draft.svg", finish(parts))


def main() -> None:
    figure1_framework()
    figure2_national_screen()
    figure3_thresholds()
    figure4_scenarios()
    figure5_china2060_windows()
    graphical_abstract()
    print(f"Wrote figures to {OUT}")


if __name__ == "__main__":
    main()
