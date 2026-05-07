"""Generate multi-panel Joule-style composite figures.

The output is pure SVG so the figures remain editable without extra plotting
dependencies. The design goal is closer to Nature Energy/Joule systems papers:
each main figure carries several linked panels rather than one isolated chart.
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
STD = ROOT / "output" / "standard_profitability_matrix"
CHINA = ROOT / "output" / "china2060_optimistic_profitability"
OUT = ROOT / "docs" / "joule_submission" / "figures_composite"


COLORS = {
    "ink": "#202426",
    "muted": "#5f6b70",
    "grid": "#dfe6e8",
    "panel": "#f7f9f9",
    "grey": "#c8d0d3",
    "neg": "#b94d5a",
    "neg2": "#df8b5f",
    "mid": "#f3f4ee",
    "pos": "#2f8f83",
    "pos2": "#225f74",
    "storage": "#225f74",
    "mineralization": "#3d8f63",
    "thermochemical": "#c97836",
    "electrochemical": "#7d63a6",
    "photochemical": "#b8a23a",
    "policy": "#4d4d4d",
    "water": "#e8f0f4",
}


PATHWAY_LABELS = {
    "geological_storage": "Storage",
    "mineralization": "Mineralization",
    "co2_h2_ft_saf": "FT-SAF",
    "co2_methanol_to_jet_saf": "MTJ-SAF",
    "rwgs_to_co": "RWGS-CO",
    "co2_to_methanol": "Methanol",
    "co2_to_methane": "Methane",
    "electrolysis_to_formate": "E-formate",
    "electrolysis_to_co": "E-CO",
    "electrolysis_to_ethylene": "E-ethylene",
    "photoelectrochemical_to_formate": "PEC-formate",
    "photocatalytic_to_co": "PCO",
}


FAMILY_COLOR = {
    "storage": COLORS["storage"],
    "mineralization": COLORS["mineralization"],
    "thermochemical": COLORS["thermochemical"],
    "electrochemical": COLORS["electrochemical"],
    "photochemical": COLORS["photochemical"],
}


def esc(text: Any) -> str:
    value = str(text)
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def f(row: dict[str, Any], key: str, default: float = 0.0) -> float:
    try:
        value = row.get(key, "")
        if value in {"", "inf", "Infinity"}:
            return math.inf if value else default
        return float(value)
    except (TypeError, ValueError):
        return default


def rgb(hex_color: str) -> tuple[int, int, int]:
    color = hex_color.lstrip("#")
    return int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)


def hex_rgb(values: tuple[int, int, int]) -> str:
    return "#" + "".join(f"{max(0, min(255, v)):02x}" for v in values)


def blend(a: str, b: str, t: float) -> str:
    t = max(0.0, min(1.0, t))
    ar, ag, ab = rgb(a)
    br, bg, bb = rgb(b)
    return hex_rgb((round(ar + (br - ar) * t), round(ag + (bg - ag) * t), round(ab + (bb - ab) * t)))


def diverging(value: float, vmin: float = -500.0, vmax: float = 500.0) -> str:
    if not math.isfinite(value):
        return "#eef1f2"
    if value < 0:
        return blend(COLORS["neg"], COLORS["mid"], (value - vmin) / max(1e-9, -vmin))
    return blend(COLORS["mid"], COLORS["pos2"], value / max(1e-9, vmax))


def sequential(value: float, vmin: float, vmax: float, lo: str = "#edf3f0", hi: str = "#155f6b") -> str:
    if not math.isfinite(value):
        return "#eef1f2"
    return blend(lo, hi, (value - vmin) / max(1e-9, vmax - vmin))


def svg_start(width: int, height: int, title: str, subtitle: str = "") -> list[str]:
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        "<style>",
        "text{font-family:Arial,Helvetica,sans-serif;fill:#202426}",
        ".title{font-size:26px;font-weight:700}.subtitle{font-size:13px;fill:#5f6b70}",
        ".paneltitle{font-size:14px;font-weight:700}.small{font-size:10.5px;fill:#5f6b70}",
        ".axis{font-size:11px;fill:#5f6b70}.label{font-size:12px;fill:#202426}",
        ".panelletter{font-size:17px;font-weight:700;fill:#202426}",
        "</style>",
        f'<text x="36" y="34" class="title">{esc(title)}</text>',
    ]
    if subtitle:
        parts.append(f'<text x="36" y="56" class="subtitle">{esc(subtitle)}</text>')
    return parts


def svg_end(parts: list[str]) -> str:
    parts.append("</svg>")
    return "\n".join(parts)


def panel(parts: list[str], letter: str, x: float, y: float, w: float, h: float, title: str) -> None:
    parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" fill="{COLORS["panel"]}" stroke="#d6dedf"/>')
    parts.append(f'<text x="{x + 12}" y="{y + 22}" class="panelletter">{letter}</text>')
    parts.append(f'<text x="{x + 38}" y="{y + 21}" class="paneltitle">{esc(title)}</text>')


def text(parts: list[str], x: float, y: float, value: Any, cls: str = "small", anchor: str = "start", color: str | None = None) -> None:
    style = f' fill="{color}"' if color else ""
    parts.append(f'<text x="{x}" y="{y}" text-anchor="{anchor}" class="{cls}"{style}>{esc(value)}</text>')


def line(parts: list[str], x1: float, y1: float, x2: float, y2: float, color: str = "#202426", width: float = 1.0, dash: str = "") -> None:
    d = f' stroke-dasharray="{dash}"' if dash else ""
    parts.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="{width}"{d}/>')


def rect(parts: list[str], x: float, y: float, w: float, h: float, fill: str, stroke: str = "none", rx: float = 0, opacity: float = 1.0) -> None:
    parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" stroke="{stroke}" opacity="{opacity}"/>')


def circle(parts: list[str], x: float, y: float, r: float, fill: str, stroke: str = "#ffffff", opacity: float = 1.0) -> None:
    parts.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{fill}" stroke="{stroke}" stroke-width="0.7" opacity="{opacity}"/>')


def polyline(parts: list[str], pts: list[tuple[float, float]], color: str, width: float = 2.0) -> None:
    if not pts:
        return
    d = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    parts.append(f'<polyline points="{d}" fill="none" stroke="{color}" stroke-width="{width}" stroke-linejoin="round" stroke-linecap="round"/>')


def arrow_defs(parts: list[str]) -> None:
    parts.append('<defs><marker id="arrow2" markerWidth="10" markerHeight="8" refX="9" refY="4" orient="auto"><path d="M0,0 L10,4 L0,8 z" fill="#202426"/></marker></defs>')


def bar_chart(
    parts: list[str],
    x: float,
    y: float,
    w: float,
    h: float,
    labels: list[str],
    values: list[float],
    colors: list[str] | None = None,
    x_label: str = "",
    value_fmt: str = "{:.0f}",
) -> None:
    if not values:
        return
    vmin = min(0.0, min(values))
    vmax = max(values)
    scale = w / max(1e-9, vmax - vmin)
    zero_x = x + (0 - vmin) * scale
    line(parts, zero_x, y, zero_x, y + h, "#8b969a", 1)
    row_h = h / len(values)
    for i, (label, value) in enumerate(zip(labels, values)):
        yy = y + i * row_h + row_h * 0.18
        bw = abs(value) * scale
        bx = zero_x if value >= 0 else zero_x - bw
        color = colors[i] if colors else (COLORS["pos2"] if value >= 0 else COLORS["neg"])
        rect(parts, bx, yy, bw, row_h * 0.55, color, rx=3)
        text(parts, x - 6, yy + row_h * 0.40, label, "axis", "end")
        text(parts, bx + (bw + 4 if value >= 0 else -4), yy + row_h * 0.40, value_fmt.format(value), "axis", "start" if value >= 0 else "end")
    line(parts, x, y + h, x + w, y + h, "#8b969a", 1)
    if x_label:
        text(parts, x + w / 2, y + h + 20, x_label, "axis", "middle")


def heatmap(
    parts: list[str],
    x: float,
    y: float,
    w: float,
    h: float,
    rows: list[str],
    cols: list[str],
    values: dict[tuple[str, str], float],
    color_fn: Callable[[float], str],
    fmt: str = "{:.0f}",
    show_values: bool = True,
) -> None:
    if not rows or not cols:
        return
    cell_w = w / len(cols)
    cell_h = h / len(rows)
    for j, col in enumerate(cols):
        text(parts, x + j * cell_w + cell_w / 2, y - 8, col, "axis", "middle")
    for i, row in enumerate(rows):
        yy = y + i * cell_h
        text(parts, x - 8, yy + cell_h * 0.58, row, "axis", "end")
        for j, col in enumerate(cols):
            value = values.get((row, col), math.nan)
            rect(parts, x + j * cell_w, yy, cell_w - 1, cell_h - 1, color_fn(value), stroke="#ffffff")
            if show_values and math.isfinite(value):
                color = "#ffffff" if abs(value) > 350 else COLORS["ink"]
                text(parts, x + j * cell_w + cell_w / 2, yy + cell_h * 0.60, fmt.format(value), "small", "middle", color=color)


def coords_iter(geometry: dict[str, Any]) -> list[list[tuple[float, float]]]:
    rings: list[list[tuple[float, float]]] = []
    if geometry["type"] == "Polygon":
        polygons = [geometry["coordinates"]]
    elif geometry["type"] == "MultiPolygon":
        polygons = geometry["coordinates"]
    else:
        return rings
    for polygon in polygons:
        if not polygon:
            continue
        ring = polygon[0]
        pts = [(float(lon), float(lat)) for lon, lat in ring]
        rings.append(pts)
    return rings


def draw_china_map(
    parts: list[str],
    x: float,
    y: float,
    w: float,
    h: float,
    metric_by_code: dict[str, float],
    color_fn: Callable[[float], str],
    legend_label: str,
    points: list[dict[str, Any]] | None = None,
    point_color: str = "#202426",
) -> None:
    geo_path = DATA / "admin" / "prefecture_boundaries.geojson"
    geo = json.loads(geo_path.read_text(encoding="utf-8"))
    min_lon, max_lon, min_lat, max_lat = 73.0, 136.0, 18.0, 54.0

    def project(lon: float, lat: float) -> tuple[float, float]:
        px = x + (lon - min_lon) / (max_lon - min_lon) * w
        py = y + h - (lat - min_lat) / (max_lat - min_lat) * h
        return px, py

    rect(parts, x, y, w, h, COLORS["water"], stroke="#d6dedf", rx=5)
    for feature in geo["features"]:
        code = str(feature["properties"].get("prefecture_code", ""))
        value = metric_by_code.get(code, math.nan)
        fill = color_fn(value) if math.isfinite(value) else "#edf0f1"
        for ring in coords_iter(feature["geometry"]):
            pts = []
            step = max(1, math.ceil(len(ring) / 90))
            for lon, lat in ring[::step]:
                if min_lon <= lon <= max_lon and min_lat <= lat <= max_lat:
                    pts.append(project(lon, lat))
            if len(pts) < 3:
                continue
            d = " ".join(f"{px:.1f},{py:.1f}" for px, py in pts)
            parts.append(f'<polygon points="{d}" fill="{fill}" stroke="#ffffff" stroke-width="0.25"/>')
    if points:
        for point in points:
            lon, lat = float(point["longitude"]), float(point["latitude"])
            if not (min_lon <= lon <= max_lon and min_lat <= lat <= max_lat):
                continue
            px, py = project(lon, lat)
            radius = float(point.get("radius", 3.0))
            circle(parts, px, py, radius, point.get("fill", point_color), stroke="#ffffff", opacity=float(point.get("opacity", 0.75)))
    # Legend
    lx, ly = x + 10, y + h - 24
    for i in range(9):
        t = i / 8
        value = -500 + t * 1000
        rect(parts, lx + i * 18, ly, 18, 8, color_fn(value), stroke="none")
    text(parts, lx, ly - 5, legend_label, "small")
    text(parts, lx, ly + 22, "low", "small")
    text(parts, lx + 162, ly + 22, "high", "small", "end")


def source_points() -> list[dict[str, Any]]:
    rows = read_csv(DATA / "real_inputs_top300_with_dac" / "spatial_sources_real.csv")
    points = []
    for row in rows:
        mtpa = f(row, "co2_available_mtpa")
        radius = 1.4 + min(7.0, math.sqrt(max(mtpa, 0.0)) * 0.75)
        color = {
            "dac": "#202426",
            "chemicals": "#c97836",
            "cement": "#7d63a6",
            "steel": "#b94d5a",
            "power": "#225f74",
        }.get(row.get("source_type", ""), "#5f6b70")
        points.append({"longitude": row["longitude"], "latitude": row["latitude"], "radius": radius, "fill": color, "opacity": 0.64})
    return points


def figure1_model_composite() -> None:
    parts = svg_start(1600, 1050, "Figure 1. Model architecture and evidence upgrade", "Functional unit, data layers, technology families, and evidence status.")
    arrow_defs(parts)
    panel(parts, "a", 40, 82, 740, 360, "Allocation workflow")
    x0, y0 = 85, 180
    nodes = [
        ("CO2 sources", "purity / pressure / capture cost", x0, y0, "#edf2f2"),
        ("Transport + hubs", "pipeline / rail / truck / ship", x0 + 150, y0, "#edf2f2"),
        ("Pathway module", "storage / minerals / fuels / chemicals", x0 + 315, y0, "#edf2f2"),
        ("Markets + policy", "price / capacity / credits / MRV", x0 + 500, y0, "#edf2f2"),
    ]
    for label, note, nx, ny, fill in nodes:
        rect(parts, nx, ny, 130, 76, fill, stroke="#9aa6aa", rx=8)
        text(parts, nx + 65, ny + 30, label, "label", "middle")
        text(parts, nx + 65, ny + 52, note, "small", "middle")
    for nx in [x0 + 130, x0 + 280, x0 + 445]:
        line(parts, nx, y0 + 38, nx + 20, y0 + 38, COLORS["ink"], 1.8)
    text(parts, x0 + 315, y0 + 125, "Output: margin, NPV proxy, net avoided emissions, permanence, first profitable year", "label", "middle")

    panel(parts, "b", 820, 82, 720, 360, "Evidence ladder")
    ledger = read_csv(DATA / "evidence_upgrade_ledger.csv")
    grades = {"B": 0, "C": 0, "D": 0, "mixed": 0}
    for row in ledger:
        grade = row.get("current_grade", "")
        if "B" in grade and "C" not in grade and "D" not in grade:
            grades["B"] += 1
        elif "D" in grade:
            grades["D"] += 1
        elif "mixed" in grade or "/" in grade:
            grades["mixed"] += 1
        else:
            grades["C"] += 1
    bar_chart(
        parts,
        940,
        160,
        420,
        190,
        ["B", "B/C mixed", "C", "D"],
        [grades["B"], grades["mixed"], grades["C"], grades["D"]],
        ["#225f74", "#7d63a6", "#c97836", "#b94d5a"],
        "parameter groups",
        "{:.0f}",
    )
    text(parts, 860, 385, "Ledger separates measured data, literature calibration, and unresolved scenario inputs.", "small")

    panel(parts, "c", 40, 480, 460, 500, "Pathway portfolio")
    windows = read_csv(CHINA / "china2060_earliest_profit_windows.csv")
    rows = sorted(windows, key=lambda r: (9999 if not r["first_profitable_year"] else int(r["first_profitable_year"]), r["pathway"]))
    for i, row in enumerate(rows[:12]):
        y = 540 + i * 33
        color = FAMILY_COLOR.get(row["technology_family"], "#888")
        rect(parts, 75, y - 16, 20, 20, color, rx=4)
        text(parts, 105, y, PATHWAY_LABELS.get(row["pathway"], row["pathway"]), "small")
        year = row["first_profitable_year"] or "not by 2060"
        text(parts, 410, y, year, "small", "end")

    panel(parts, "d", 535, 480, 480, 500, "Profit equation")
    eqs = [
        "margin = product revenue + policy revenue - risk-adjusted cost",
        "risk-adjusted cost = process + capture + transport + MRV + finance + reliability",
        "policy revenue = avoided-carbon credit + durable-removal credit + fuel/product premiums",
        "profitability window = first year with margin > 0 for at least one city-route pair",
    ]
    for i, eq in enumerate(eqs):
        rect(parts, 575, 560 + i * 82, 390, 52, "#ffffff", stroke="#d6dedf", rx=6)
        text(parts, 595, 592 + i * 82, eq, "small")

    panel(parts, "e", 1050, 480, 490, 500, "China dual-carbon time axis")
    effort = read_csv(DATA / "china2060_optimistic_effort_scenario.csv")
    years = [r["year"] for r in effort]
    h2 = [f(r, "h2_price_usd_per_kg") for r in effort]
    elec = [f(r, "electricity_price_usd_per_mwh") for r in effort]
    carbon = [f(r, "carbon_price_usd_per_tco2") for r in effort]
    plot_x, plot_y, plot_w, plot_h = 1110, 585, 360, 250
    line(parts, plot_x, plot_y + plot_h, plot_x + plot_w, plot_y + plot_h, "#8b969a")
    line(parts, plot_x, plot_y, plot_x, plot_y + plot_h, "#8b969a")
    for series, color, label, max_v in [
        (h2, "#7d63a6", "H2 price (inverse)", 2.2),
        (elec, "#225f74", "Power price (inverse)", 28.0),
        (carbon, "#3d8f63", "Carbon value", 360.0),
    ]:
        pts = []
        for i, value in enumerate(series):
            px = plot_x + i * plot_w / (len(series) - 1)
            norm = (max_v - value) / max_v if "inverse" in label else value / max_v
            py = plot_y + plot_h - norm * plot_h
            pts.append((px, py))
        polyline(parts, pts, color, 2.5)
        text(parts, plot_x + plot_w + 8, pts[-1][1] + 4, label, "small", color=color)
    for i, year in enumerate(years):
        px = plot_x + i * plot_w / (len(years) - 1)
        text(parts, px, plot_y + plot_h + 18, year, "axis", "middle")
    text(parts, 1110, 880, "Official framing: peak before 2030, carbon neutrality before 2060.", "small")
    (OUT / "figure1_model_composite.svg").write_text(svg_end(parts), encoding="utf-8")


def figure2_spatial_heatmap() -> None:
    parts = svg_start(1600, 1180, "Figure 2. National spatial heat maps for the 2040 effort window", "Prefecture-level margin, positive-candidate density, storage distance, and CO2 source distribution.")
    city = read_csv(CHINA / "china2060_2040_city_recommendations.csv")
    detail = read_csv(CHINA / "china2060_2040_profit_detail.csv")
    margin_by_city = {row["city_id"]: f(row, "best_margin_usd_per_tco2", -math.inf) for row in city}
    distance_by_city = {row["city_id"]: f(row, "nearest_storage_distance_km", math.inf) for row in city}
    positive_count: dict[str, float] = {}
    best_family: dict[str, str] = {}
    for row in detail:
        cid = row["city_id"]
        if f(row, "margin_usd_per_tco2", -math.inf) > 0:
            positive_count[cid] = positive_count.get(cid, 0.0) + 1
        incumbent = margin_by_city.get(cid, -math.inf)
        if f(row, "margin_usd_per_tco2", -math.inf) >= incumbent:
            best_family[cid] = row["technology_family"]

    panel(parts, "a", 40, 82, 700, 430, "Best margin by prefecture (USD/tCO2)")
    draw_china_map(parts, 65, 122, 650, 350, margin_by_city, lambda v: diverging(v, -250, 450), "margin")

    panel(parts, "b", 780, 82, 760, 430, "Positive route density")
    draw_china_map(parts, 805, 122, 650, 350, positive_count, lambda v: sequential(v, 0, max(1, max(positive_count.values() or [1])), "#edf3f0", "#1f6f78"), "positive candidates")

    panel(parts, "c", 40, 550, 700, 520, "CO2 source intensity")
    draw_china_map(parts, 65, 590, 650, 405, {}, lambda v: "#edf0f1", "source size = MtCO2/y", points=source_points())
    text(parts, 80, 1030, "Circle size scales with source CO2 availability; color encodes source sector/DAC.", "small")

    panel(parts, "d", 780, 550, 360, 520, "Storage distance distribution")
    bands = {"0-150 km": 0, "150-350 km": 0, "350-800 km": 0, ">800 km": 0}
    for value in distance_by_city.values():
        if value <= 150:
            bands["0-150 km"] += 1
        elif value <= 350:
            bands["150-350 km"] += 1
        elif value <= 800:
            bands["350-800 km"] += 1
        else:
            bands[">800 km"] += 1
    bar_chart(parts, 895, 640, 190, 260, list(bands), list(bands.values()), ["#225f74", "#3d8f63", "#c97836", "#b94d5a"], "prefectures")

    panel(parts, "e", 1180, 550, 360, 520, "Top positive city-route windows")
    top = sorted(city, key=lambda r: f(r, "best_margin_usd_per_tco2", -math.inf), reverse=True)[:10]
    labels = [f"{row['city_id']} {PATHWAY_LABELS.get(row['best_pathway'], row['best_pathway'])}" for row in top]
    values = [f(row, "best_margin_usd_per_tco2") for row in top]
    colors = [FAMILY_COLOR.get(row["best_family"], "#888") for row in top]
    bar_chart(parts, 1290, 625, 200, 330, labels, values, colors, "USD/tCO2", "{:.0f}")
    (OUT / "figure2_spatial_heatmap_composite.svg").write_text(svg_end(parts), encoding="utf-8")


def figure3_time_heatmaps() -> None:
    parts = svg_start(1600, 1120, "Figure 3. 2030-2060 profitability windows", "Time-pathway heat maps show when China's dual-carbon effort case becomes investable.")
    summary = read_csv(CHINA / "china2060_pathway_summary.csv")
    system = read_csv(CHINA / "china2060_system_summary.csv")
    windows = read_csv(CHINA / "china2060_earliest_profit_windows.csv")
    years = ["2030", "2035", "2040", "2045", "2050", "2055", "2060"]
    order = [
        "mineralization",
        "geological_storage",
        "co2_h2_ft_saf",
        "rwgs_to_co",
        "electrolysis_to_formate",
        "co2_methanol_to_jet_saf",
        "co2_to_methanol",
        "co2_to_methane",
        "photoelectrochemical_to_formate",
        "electrolysis_to_co",
        "photocatalytic_to_co",
        "electrolysis_to_ethylene",
    ]
    margin_values = {(PATHWAY_LABELS.get(r["pathway"], r["pathway"]), r["year"]): f(r, "best_margin_usd_per_tco2", math.nan) for r in summary}
    count_values = {(PATHWAY_LABELS.get(r["pathway"], r["pathway"]), r["year"]): f(r, "positive_candidate_count", 0.0) for r in summary}
    labels = [PATHWAY_LABELS[p] for p in order]

    panel(parts, "a", 40, 82, 930, 430, "Best margin heat map (USD/tCO2)")
    heatmap(parts, 235, 145, 680, 300, labels, years, margin_values, lambda v: diverging(v, -700, 700), "{:.0f}")

    panel(parts, "b", 1010, 82, 530, 430, "Positive candidates by year")
    vals = [f(r, "positive_candidate_count") for r in system]
    max_v = max(vals)
    px, py, pw, ph = 1080, 170, 390, 240
    pts = []
    for i, value in enumerate(vals):
        x = px + i * pw / (len(vals) - 1)
        y = py + ph - value / max_v * ph
        pts.append((x, y))
    polyline(parts, pts, COLORS["pos2"], 3)
    for point, value, year in zip(pts, vals, years):
        circle(parts, point[0], point[1], 5, COLORS["pos2"])
        text(parts, point[0], point[1] - 10, f"{value:.0f}", "small", "middle")
        text(parts, point[0], py + ph + 18, year, "axis", "middle")
    line(parts, px, py + ph, px + pw, py + ph, "#8b969a")
    line(parts, px, py, px, py + ph, "#8b969a")

    panel(parts, "c", 40, 552, 780, 450, "Positive candidate density heat map")
    heatmap(parts, 235, 615, 530, 300, labels, years, count_values, lambda v: sequential(v, 0, 1500, "#f4f6f6", "#225f74"), "{:.0f}")

    panel(parts, "d", 860, 552, 340, 450, "Earliest profitable year")
    for i, row in enumerate(windows):
        y = 620 + i * 28
        p = row["pathway"]
        color = FAMILY_COLOR.get(row["technology_family"], "#888")
        rect(parts, 900, y - 14, 18, 18, color, rx=3)
        text(parts, 925, y, PATHWAY_LABELS.get(p, p), "small")
        text(parts, 1160, y, row["first_profitable_year"] or "not by 2060", "small", "end")

    panel(parts, "e", 1230, 552, 310, 450, "Policy/technology effort")
    effort = read_csv(DATA / "china2060_optimistic_effort_scenario.csv")
    curves = [
        ("H2 $/kg", [f(r, "h2_price_usd_per_kg") for r in effort], "#7d63a6", True),
        ("Power $/MWh", [f(r, "electricity_price_usd_per_mwh") for r in effort], "#225f74", True),
        ("Carbon $/t", [f(r, "carbon_price_usd_per_tco2") for r in effort], "#3d8f63", False),
        ("CDR $/t", [f(r, "durable_removal_credit_usd_per_tco2") for r in effort], "#c97836", False),
    ]
    px, py, pw, ph = 1275, 645, 210, 260
    for label, series, color, inverse in curves:
        max_s, min_s = max(series), min(series)
        pts = []
        for i, value in enumerate(series):
            norm = (max_s - value) / max(1e-9, max_s - min_s) if inverse else (value - min_s) / max(1e-9, max_s - min_s)
            pts.append((px + i * pw / (len(series) - 1), py + ph - norm * ph))
        polyline(parts, pts, color, 2.4)
        text(parts, px + pw + 8, pts[-1][1] + 3, label, "small", color=color)
    text(parts, px, py + ph + 22, "2030", "axis")
    text(parts, px + pw, py + ph + 22, "2060", "axis", "end")
    (OUT / "figure3_time_heatmaps_composite.svg").write_text(svg_end(parts), encoding="utf-8")


def best_record(year: int, pathway: str) -> dict[str, str]:
    rows = read_csv(CHINA / f"china2060_{year}_profit_detail.csv")
    selected = [r for r in rows if r["pathway"] == pathway]
    return max(selected, key=lambda r: f(r, "margin_usd_per_tco2", -math.inf))


def cost_components(row: dict[str, str]) -> dict[str, float]:
    capture = f(row, "capture_cost_usd_per_tco2") + f(row, "capture_energy_cost_usd_per_tco2")
    transport = f(row, "spec_cost_usd_per_tco2") + f(row, "transport_cost_usd_per_tco2") + f(row, "land_cost_usd_per_tco2") + f(row, "spatial_risk_cost_usd_per_tco2")
    adders = (
        f(row, "quality_upgrade_cost_usd_per_tco2")
        + f(row, "mrv_cost_usd_per_tco2")
        + f(row, "finance_cost_adjustment_usd_per_tco2")
        + f(row, "capex_risk_cost_usd_per_tco2")
        + f(row, "reliability_cost_usd_per_tco2")
        + f(row, "scale_penalty_usd_per_tco2")
    )
    process = max(0.0, f(row, "risk_adjusted_gross_cost_usd_per_tco2") - capture - transport - adders)
    return {"capture": capture, "transport/spec": transport, "process": process, "risk/MRV": adders}


def stacked_profit_panel(parts: list[str], x: float, y: float, w: float, h: float, row: dict[str, str], title: str) -> None:
    comps = cost_components(row)
    revenue = {"product": f(row, "product_revenue_usd_per_tco2"), "policy": f(row, "policy_revenue_usd_per_tco2")}
    total = max(sum(comps.values()), sum(revenue.values()), 1.0)
    base_y = y + h - 55
    scale = (h - 95) / total
    bar_w = 62
    colors = ["#9fb6bd", "#70a3a2", "#c97836", "#7d63a6"]
    yy = base_y
    for (name, value), color in zip(comps.items(), colors):
        hh = value * scale
        yy -= hh
        rect(parts, x + 60, yy, bar_w, hh, color, stroke="#ffffff")
    yy = base_y
    for name, value in revenue.items():
        hh = value * scale
        yy -= hh
        rect(parts, x + 170, yy, bar_w, hh, COLORS["pos2"] if name == "product" else COLORS["mineralization"], stroke="#ffffff")
    margin = f(row, "margin_usd_per_tco2")
    text(parts, x + 20, y + 28, title, "label")
    text(parts, x + 91, base_y + 18, "cost", "axis", "middle")
    text(parts, x + 201, base_y + 18, "revenue", "axis", "middle")
    text(parts, x + w - 12, y + 30, f"margin {margin:.0f}", "small", "end", COLORS["pos"] if margin > 0 else COLORS["neg"])
    text(parts, x + 20, y + h - 15, f"{row['year']} | {row['source_id']} -> {row['destination_id']}", "small")


def figure4_cost_stacks() -> None:
    parts = svg_start(1600, 1080, "Figure 4. Why routes become profitable", "Cost-revenue stacks for first profitable windows under the China 2060 effort case.")
    selected = [
        (2035, "mineralization", "Mineralization"),
        (2040, "geological_storage", "Storage"),
        (2040, "co2_h2_ft_saf", "FT-SAF"),
        (2040, "rwgs_to_co", "RWGS-CO"),
        (2040, "electrolysis_to_formate", "E-formate"),
    ]
    positions = [(40, 82), (560, 82), (1080, 82), (300, 575), (820, 575)]
    for idx, ((year, pathway, title), (x, y)) in enumerate(zip(selected, positions)):
        panel(parts, chr(ord("a") + idx), x, y, 480, 410, f"{title}: first positive case")
        row = best_record(year, pathway)
        stacked_profit_panel(parts, x + 20, y + 52, 420, 300, row, f"{title} ({year})")
    panel(parts, "f", 40, 990, 1500, 60, "Reading the stacks")
    text(parts, 75, 1025, "Each panel compares risk-adjusted cost against product and policy revenue. Positive margin appears only when both revenue columns exceed the full system cost stack.", "label")
    (OUT / "figure4_cost_stacks_composite.svg").write_text(svg_end(parts), encoding="utf-8")


def sensitivity_grid(
    row: dict[str, str],
    product_prices: list[float],
    other_values: list[float],
    other_name: str,
) -> dict[tuple[str, str], float]:
    product_kg = f(row, "marketable_product_kg_per_tco2")
    base_product_price = f(row, "product_price_usd_per_kg")
    base_margin = f(row, "margin_usd_per_tco2")
    if other_name == "H2":
        base_other = f(row, "h2_price_usd_per_kg")
        be = f(row, "break_even_h2_price_usd_per_kg")
        driver = base_margin / max(1e-9, be - base_other) if math.isfinite(be) else 165.0
    else:
        base_other = f(row, "electricity_price_usd_per_mwh")
        be = f(row, "break_even_electricity_price_usd_per_mwh")
        driver = base_margin / max(1e-9, be - base_other) if math.isfinite(be) else 1.0
    values = {}
    for p in product_prices:
        for other in other_values:
            margin = base_margin + product_kg * (p - base_product_price) + driver * (base_other - other)
            values[(f"{other:.1f}", f"{p:.1f}")] = margin
    return values


def figure5_sensitivity() -> None:
    parts = svg_start(1600, 1100, "Figure 5. Break-even and sensitivity surfaces", "Two-dimensional heat maps show why product price, H2, and power must improve together.")
    thresholds = read_csv(STD / "technology_profitability_thresholds.csv")
    top = sorted(thresholds, key=lambda r: f(r, "profitability_gap_usd_per_tco2"))[:10]
    panel(parts, "a", 40, 82, 700, 430, "Standard-scenario break-even thresholds")
    labels = [PATHWAY_LABELS.get(r["pathway"], r["pathway"]) for r in top]
    values = [f(r, "profitability_gap_usd_per_tco2") for r in top]
    colors = [FAMILY_COLOR.get(r["technology_family"], "#888") for r in top]
    bar_chart(parts, 235, 150, 420, 270, labels, values, colors, "remaining gap, USD/tCO2")

    panel(parts, "b", 780, 82, 760, 430, "Margin improvement from 2030 to 2060")
    summary = read_csv(CHINA / "china2060_pathway_summary.csv")
    margins_by_pathway: dict[str, dict[str, float]] = {}
    for row in summary:
        margins_by_pathway.setdefault(row["pathway"], {})[row["year"]] = f(row, "best_margin_usd_per_tco2")
    gain_rows = []
    for pathway, by_year in margins_by_pathway.items():
        if "2030" in by_year and "2060" in by_year:
            gain_rows.append((pathway, by_year["2060"] - by_year["2030"]))
    gain_rows = sorted(gain_rows, key=lambda item: item[1], reverse=True)[:10]
    bar_chart(parts, 950, 150, 430, 270, [PATHWAY_LABELS.get(p, p) for p, _ in gain_rows], [v for _, v in gain_rows], None, "USD/tCO2")

    ft = best_record(2040, "co2_h2_ft_saf")
    formate = best_record(2040, "electrolysis_to_formate")
    panel(parts, "c", 40, 552, 700, 450, "FT-SAF surface: SAF price vs H2 price")
    saf_prices = [4, 6, 8, 10, 12, 14]
    h2_prices = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0]
    vals = sensitivity_grid(ft, saf_prices, h2_prices, "H2")
    heatmap(parts, 160, 635, 500, 250, [f"{v:.1f}" for v in h2_prices], [f"{v:.1f}" for v in saf_prices], vals, lambda v: diverging(v, -700, 700), "{:.0f}")
    text(parts, 410, 930, "SAF price (USD/kg)", "axis", "middle")
    text(parts, 95, 765, "H2 price", "axis", "middle")

    panel(parts, "d", 780, 552, 760, 450, "Electro-formate surface: product price vs power price")
    formate_prices = [1.5, 2.0, 2.5, 3.0, 3.5, 4.0]
    power_prices = [10, 25, 50, 75, 100, 125]
    vals2 = sensitivity_grid(formate, formate_prices, power_prices, "electricity")
    heatmap(parts, 945, 635, 500, 250, [f"{v:.1f}" for v in power_prices], [f"{v:.1f}" for v in formate_prices], vals2, lambda v: diverging(v, -500, 500), "{:.0f}")
    text(parts, 1195, 930, "formate price (USD/kg)", "axis", "middle")
    text(parts, 860, 765, "power price", "axis", "middle")
    (OUT / "figure5_sensitivity_composite.svg").write_text(svg_end(parts), encoding="utf-8")


def figure6_self_review() -> None:
    parts = svg_start(1600, 980, "Figure 6. Author-editor self-review map", "What the current model supports, what remains a scenario, and what must be upgraded before submission.")
    panel(parts, "a", 40, 82, 500, 360, "Supported by upgraded evidence")
    supported = [
        "2030 baseline: no positive route",
        "2035 mineralization opens first in effort case",
        "2040 storage / FT-SAF / RWGS / formate windows",
        "SAF requires policy-backed premium, not fossil parity",
        "Photochemical routes remain late-stage or unresolved",
    ]
    for i, item in enumerate(supported):
        circle(parts, 80, 150 + i * 50, 6, COLORS["pos"])
        text(parts, 100, 154 + i * 50, item, "label")

    panel(parts, "b", 580, 82, 460, 360, "Still scenario-driven")
    scenario = [
        "CO / formic acid / carbonate price premiums",
        "City-level product offtake capacity",
        "China SAF mandate and certificate value",
        "2060 carbon/removal credit trajectory",
        "Photochemical module lifetime",
    ]
    for i, item in enumerate(scenario):
        circle(parts, 620, 150 + i * 50, 6, COLORS["thermochemical"])
        text(parts, 640, 154 + i * 50, item, "label")

    panel(parts, "c", 1080, 82, 460, 360, "Must upgrade for submission")
    must = [
        "Reservoir pressure simulation",
        "SAF Aspen/IDAES process package",
        "Audited city product markets",
        "Legal policy eligibility audit",
        "Monte Carlo uncertainty figures",
    ]
    for i, item in enumerate(must):
        circle(parts, 1120, 150 + i * 50, 6, COLORS["neg"])
        text(parts, 1140, 154 + i * 50, item, "label")

    panel(parts, "d", 40, 500, 720, 360, "Claim strength")
    claims = [
        ("Strong", 4, "#225f74"),
        ("Moderate", 6, "#c97836"),
        ("Weak until upgraded", 5, "#b94d5a"),
    ]
    bar_chart(parts, 210, 585, 420, 170, [c[0] for c in claims], [c[1] for c in claims], [c[2] for c in claims], "claim count")

    panel(parts, "e", 820, 500, 720, 360, "Editorial rule for revisions")
    rules = [
        "Every figure must answer one decision question.",
        "Every heat map must state the scenario and unit.",
        "Every optimistic claim must list its enabling conditions.",
        "Every C/D input must stay visible in SI.",
        "No route is called profitable outside the simulated window.",
    ]
    for i, item in enumerate(rules):
        rect(parts, 860, 565 + i * 48, 610, 34, "#ffffff", stroke="#d6dedf", rx=5)
        text(parts, 880, 588 + i * 48, item, "label")
    (OUT / "figure6_self_review_composite.svg").write_text(svg_end(parts), encoding="utf-8")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    figure1_model_composite()
    figure2_spatial_heatmap()
    figure3_time_heatmaps()
    figure4_cost_stacks()
    figure5_sensitivity()
    figure6_self_review()
    print(f"Wrote composite figures to {OUT}")


if __name__ == "__main__":
    main()
