"""Generate dependency-free SVG figures for the manuscript draft."""

from __future__ import annotations

import csv
import math
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output"
FIGURES = ROOT / "docs" / "figures"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def num(record: dict[str, str], key: str, default: float = 0.0) -> float:
    value = record.get(key, "")
    if value in {"", "inf", "nan"}:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def write_svg(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def fig1_framework(path: Path) -> None:
    width, height = 1050, 610
    colors = {
        "capture": "#59636f",
        "storage": "#4c78a8",
        "mineral": "#59a14f",
        "thermo": "#f28e2b",
        "electro": "#b07aa1",
        "photo": "#edc948",
    }
    boxes = [
        ("Captured CO2", 45, 250, 155, 64, colors["capture"]),
        ("Geological\nstorage", 280, 70, 165, 68, colors["storage"]),
        ("Mineralization", 280, 185, 165, 68, colors["mineral"]),
        ("Thermochemical\nconversion", 280, 300, 165, 68, colors["thermo"]),
        ("Electrochemical\nconversion", 280, 415, 165, 68, colors["electro"]),
        ("Photochemical /\nPEC conversion", 280, 520, 165, 68, colors["photo"]),
        ("Durable CO2\nretention", 580, 98, 165, 68, "#3b6d8f"),
        ("Carbonate / building\nmaterials", 580, 205, 190, 68, "#4f8d4b"),
        ("CO, methanol,\nmethane", 580, 320, 165, 68, "#c96d1e"),
        ("CO, formate,\nethylene", 580, 435, 165, 68, "#84639a"),
        ("Solar-derived\nCO / formate", 580, 528, 165, 68, "#b7982f"),
        ("TEA-LCA decision map\ncost, emissions, market,\nresidence time", 820, 275, 185, 95, "#2f3b45"),
    ]
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        '<style>text{font-family:Arial,Helvetica,sans-serif;fill:#20252b}.title{font-size:20px;font-weight:700}.small{font-size:12px}.box{font-size:14px;font-weight:700;fill:#fff}.line{stroke:#6d747c;stroke-width:2.2;fill:none;marker-end:url(#arrow)}</style>',
        '<defs><marker id="arrow" markerWidth="10" markerHeight="8" refX="9" refY="4" orient="auto"><path d="M0,0 L10,4 L0,8 Z" fill="#6d747c"/></marker></defs>',
        '<text x="36" y="34" class="title">Figure 1. Captured CO2 allocation framework</text>',
        '<text x="36" y="55" class="small">The model compares storage, mineralization, thermochemical, electrochemical, and photochemical destinations on a common per-tonne CO2 basis.</text>',
    ]
    for label, x, y, w, h, color in boxes:
        parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" fill="{color}"/>')
        lines = label.split("\n")
        for i, line in enumerate(lines):
            ty = y + h / 2 - (len(lines) - 1) * 8 + i * 17 + 5
            parts.append(f'<text x="{x + w / 2}" y="{ty:.1f}" text-anchor="middle" class="box">{line}</text>')
    for y in [104, 219, 334, 449, 554]:
        parts.append(f'<path d="M200,282 C235,{y} 240,{y} 280,{y}" class="line"/>')
    for y in [104, 219, 334, 449, 562]:
        parts.append(f'<path d="M445,{y} L580,{y}" class="line"/>')
    for y in [132, 239, 354, 469, 562]:
        parts.append(f'<path d="M770,{y} C805,{y} 790,322 820,322" class="line"/>')
    parts.append("</svg>")
    write_svg(path, "\n".join(parts))


def fig2_baseline(records: list[dict[str, str]], path: Path) -> None:
    rows = [r for r in records if r.get("pathway") and r["pathway"] != "_scenario"]
    width, height = 1120, 650
    left, top, bottom = 195, 70, 80
    plot_w, plot_h = width - left - 55, height - top - bottom
    values = [num(r, "net_cost_usd_per_tco2") for r in rows]
    min_v = min(values + [0])
    max_v = max(values + [0])
    span = max_v - min_v or 1
    zero_x = left + (0 - min_v) / span * plot_w
    row_h = plot_h / len(rows)
    family_colors = {
        "storage": "#4c78a8",
        "mineralization": "#59a14f",
        "thermochemical": "#f28e2b",
        "electrochemical": "#b07aa1",
        "photochemical": "#edc948",
    }
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        '<style>text{font-family:Arial,Helvetica,sans-serif;fill:#222}.title{font-size:20px;font-weight:700}.small{font-size:12px}.label{font-size:12px}.axis{stroke:#5f6872;stroke-width:1.2}.grid{stroke:#e7eaee;stroke-width:1}</style>',
        '<text x="35" y="32" class="title">Figure 2. Baseline net cost by pathway</text>',
        '<text x="35" y="53" class="small">Net cost includes annualized CAPEX, utilities, transport, fixed/variable OPEX, product revenue, and avoided-emissions carbon credit.</text>',
    ]
    for tick in range(math.floor(min_v / 100) * 100, math.ceil(max_v / 100) * 100 + 1, 100):
        x = left + (tick - min_v) / span * plot_w
        parts.append(f'<line x1="{x:.1f}" y1="{top}" x2="{x:.1f}" y2="{top + plot_h}" class="grid"/>')
        parts.append(f'<text x="{x:.1f}" y="{top + plot_h + 20}" text-anchor="middle" class="small">{tick}</text>')
    parts.append(f'<line x1="{zero_x:.1f}" y1="{top}" x2="{zero_x:.1f}" y2="{top + plot_h}" class="axis"/>')
    for i, row in enumerate(rows):
        y = top + i * row_h + row_h * 0.18
        h = row_h * 0.62
        value = num(row, "net_cost_usd_per_tco2")
        x = left + (min(value, 0) - min_v) / span * plot_w
        w = abs(value) / span * plot_w
        color = family_colors.get(row.get("technology_family", ""), "#9aa0a6")
        parts.append(f'<text x="{left - 12}" y="{y + h * 0.68:.1f}" text-anchor="end" class="label">{row["pathway"]}</text>')
        parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{max(w, 1):.1f}" height="{h:.1f}" rx="3" fill="{color}"/>')
        tx = x + w + 5 if value >= 0 else x - 5
        anchor = "start" if value >= 0 else "end"
        parts.append(f'<text x="{tx:.1f}" y="{y + h * 0.68:.1f}" text-anchor="{anchor}" class="small">{value:.1f}</text>')
    parts.append(f'<text x="{left + plot_w / 2:.1f}" y="{height - 20}" text-anchor="middle" class="small">Net cost (USD per tonne captured CO2)</text>')
    parts.append("</svg>")
    write_svg(path, "\n".join(parts))


def fig3_family(records: list[dict[str, str]], path: Path) -> None:
    rows = [r for r in records if r.get("technology_family")]
    width, height = 900, 560
    left, right, top, bottom = 90, 45, 65, 70
    plot_w, plot_h = width - left - right, height - top - bottom
    xs = [num(r, "net_avoided_kgco2e_per_tco2") for r in rows]
    ys = [num(r, "net_cost_usd_per_tco2") for r in rows]
    min_x, max_x = 0, max(xs + [1000])
    min_y, max_y = min(ys + [0]) - 30, max(ys + [0]) + 50
    colors = {
        "storage": "#4c78a8",
        "mineralization": "#59a14f",
        "thermochemical": "#f28e2b",
        "electrochemical": "#b07aa1",
        "photochemical": "#edc948",
    }
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        '<style>text{font-family:Arial,Helvetica,sans-serif;fill:#222}.title{font-size:20px;font-weight:700}.small{font-size:12px}.label{font-size:13px;font-weight:700}.grid{stroke:#e7eaee}.axis{stroke:#5f6872;stroke-width:1.2}</style>',
        '<text x="35" y="32" class="title">Figure 3. Best representative route within each technology family</text>',
        '<text x="35" y="53" class="small">Screening-model output under the baseline scenario.</text>',
    ]
    for tick in [0, 250, 500, 750, 1000]:
        x = left + (tick - min_x) / (max_x - min_x) * plot_w
        parts.append(f'<line x1="{x:.1f}" y1="{top}" x2="{x:.1f}" y2="{top + plot_h}" class="grid"/>')
        parts.append(f'<text x="{x:.1f}" y="{top + plot_h + 20}" text-anchor="middle" class="small">{tick}</text>')
    for tick in [0, 100, 200, 300]:
        y = top + plot_h - (tick - min_y) / (max_y - min_y) * plot_h
        parts.append(f'<line x1="{left}" y1="{y:.1f}" x2="{left + plot_w}" y2="{y:.1f}" class="grid"/>')
        parts.append(f'<text x="{left - 12}" y="{y + 4:.1f}" text-anchor="end" class="small">{tick}</text>')
    parts.append(f'<line x1="{left}" y1="{top + plot_h}" x2="{left + plot_w}" y2="{top + plot_h}" class="axis"/>')
    parts.append(f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_h}" class="axis"/>')
    for row in rows:
        x = left + (num(row, "net_avoided_kgco2e_per_tco2") - min_x) / (max_x - min_x) * plot_w
        y = top + plot_h - (num(row, "net_cost_usd_per_tco2") - min_y) / (max_y - min_y) * plot_h
        fam = row["technology_family"]
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="10" fill="{colors.get(fam, "#888")}" stroke="#ffffff" stroke-width="1.5"/>')
        parts.append(f'<text x="{x + 14:.1f}" y="{y + 4:.1f}" class="label">{fam}</text>')
    parts.append(f'<text x="{left + plot_w / 2:.1f}" y="{height - 20}" text-anchor="middle" class="small">Net avoided emissions (kgCO2e per tonne captured CO2)</text>')
    parts.append(f'<text x="22" y="{top + plot_h / 2:.1f}" transform="rotate(-90 22 {top + plot_h / 2:.1f})" text-anchor="middle" class="small">Net cost (USD/tCO2)</text>')
    parts.append("</svg>")
    write_svg(path, "\n".join(parts))


def fig5_market_residence(records: list[dict[str, str]], path: Path) -> None:
    rows = [r for r in records if r.get("pathway") and r["pathway"] != "_scenario"]
    width, height = 980, 620
    left, right, top, bottom = 95, 50, 70, 85
    plot_w, plot_h = width - left - right, height - top - bottom
    colors = {
        "storage": "#4c78a8",
        "mineralization": "#59a14f",
        "thermochemical": "#f28e2b",
        "electrochemical": "#b07aa1",
        "photochemical": "#edc948",
    }

    def lx(value: float) -> float:
        return math.log10(max(value, 0.01))

    x_min, x_max = -2, 4.2
    y_min, y_max = 1, 10000
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        '<style>text{font-family:Arial,Helvetica,sans-serif;fill:#222}.title{font-size:20px;font-weight:700}.small{font-size:12px}.label{font-size:11px}.grid{stroke:#e7eaee}.axis{stroke:#5f6872;stroke-width:1.2}</style>',
        '<text x="35" y="32" class="title">Figure 5. Market capacity and carbon residence time</text>',
        '<text x="35" y="53" class="small">Bubble size scales with baseline net avoided emissions. Axes are logarithmic.</text>',
    ]
    for tick in [0.01, 0.1, 1, 10, 100, 1000, 10000]:
        x = left + (lx(tick) - x_min) / (x_max - x_min) * plot_w
        parts.append(f'<line x1="{x:.1f}" y1="{top}" x2="{x:.1f}" y2="{top + plot_h}" class="grid"/>')
        parts.append(f'<text x="{x:.1f}" y="{top + plot_h + 20}" text-anchor="middle" class="small">{tick:g}</text>')
    for tick in [1, 10, 100, 1000, 10000]:
        y = top + plot_h - (math.log10(tick) - math.log10(y_min)) / (math.log10(y_max) - math.log10(y_min)) * plot_h
        parts.append(f'<line x1="{left}" y1="{y:.1f}" x2="{left + plot_w}" y2="{y:.1f}" class="grid"/>')
        parts.append(f'<text x="{left - 12}" y="{y + 4:.1f}" text-anchor="end" class="small">{tick:g}</text>')
    parts.append(f'<line x1="{left}" y1="{top + plot_h}" x2="{left + plot_w}" y2="{top + plot_h}" class="axis"/>')
    parts.append(f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_h}" class="axis"/>')
    for row in rows:
        cap = num(row, "market_capacity_mtco2_per_year")
        residence = num(row, "carbon_residence_years")
        avoided = max(num(row, "net_avoided_kgco2e_per_tco2"), 0)
        x = left + (lx(cap) - x_min) / (x_max - x_min) * plot_w
        y = top + plot_h - (math.log10(max(residence, 1)) - math.log10(y_min)) / (math.log10(y_max) - math.log10(y_min)) * plot_h
        r = 5 + 16 * math.sqrt(avoided / 1000)
        color = colors.get(row.get("technology_family", ""), "#888")
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.1f}" fill="{color}" fill-opacity="0.78" stroke="#ffffff" stroke-width="1.5"/>')
        parts.append(f'<text x="{x + r + 3:.1f}" y="{y + 3:.1f}" class="label">{row["pathway"]}</text>')
    parts.append(f'<text x="{left + plot_w / 2:.1f}" y="{height - 28}" text-anchor="middle" class="small">Indicative market capacity (MtCO2/year)</text>')
    parts.append(f'<text x="24" y="{top + plot_h / 2:.1f}" transform="rotate(-90 24 {top + plot_h / 2:.1f})" text-anchor="middle" class="small">Carbon residence time (years)</text>')
    parts.append("</svg>")
    write_svg(path, "\n".join(parts))


def fig6_targets(path: Path) -> None:
    width, height = 1060, 610
    families = [
        (
            "Thermochemical",
            "#f28e2b",
            [
                ("Low-carbon H2 price", 0.92),
                ("Heat integration", 0.70),
                ("Recycle/separation", 0.62),
                ("Product displacement", 0.58),
            ],
            "Most sensitive to hydrogen cost and carbon intensity.",
        ),
        (
            "Electrochemical",
            "#b07aa1",
            [
                ("Cell voltage", 0.82),
                ("Faradaic efficiency", 0.78),
                ("Single-pass conversion", 0.65),
                ("Product recovery", 0.88),
            ],
            "Requires reactor and downstream separation targets together.",
        ),
        (
            "Photochemical / PEC",
            "#edc948",
            [
                ("Solar-to-product efficiency", 0.94),
                ("Area-specific CAPEX", 0.86),
                ("Durability", 0.76),
                ("Recovery electricity", 0.60),
            ],
            "Must be evaluated per illuminated area and lifetime.",
        ),
    ]
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        '<style>text{font-family:Arial,Helvetica,sans-serif;fill:#222}.title{font-size:20px;font-weight:700}.small{font-size:12px}.head{font-size:16px;font-weight:700;fill:#fff}.label{font-size:12px}.note{font-size:12px;font-style:italic}.axis{stroke:#d9dde3;stroke-width:1}</style>',
        '<text x="35" y="32" class="title">Figure 6. Route-specific research targets for CO2 conversion families</text>',
        '<text x="35" y="53" class="small">Relative target importance is a screening interpretation from the model structure and baseline outputs, not a final global sensitivity result.</text>',
    ]
    panel_w = 310
    gap = 30
    top = 85
    for idx, (family, color, targets, note) in enumerate(families):
        x0 = 35 + idx * (panel_w + gap)
        parts.append(f'<rect x="{x0}" y="{top}" width="{panel_w}" height="440" rx="6" fill="#f7f8fa" stroke="#d7dce2"/>')
        parts.append(f'<rect x="{x0}" y="{top}" width="{panel_w}" height="48" rx="6" fill="{color}"/>')
        parts.append(f'<text x="{x0 + panel_w / 2}" y="{top + 31}" text-anchor="middle" class="head">{family}</text>')
        y = top + 90
        for label, score in targets:
            parts.append(f'<text x="{x0 + 18}" y="{y}" class="label">{label}</text>')
            parts.append(f'<line x1="{x0 + 18}" y1="{y + 15}" x2="{x0 + panel_w - 20}" y2="{y + 15}" class="axis"/>')
            parts.append(f'<rect x="{x0 + 18}" y="{y + 7}" width="{(panel_w - 38) * score:.1f}" height="16" rx="3" fill="{color}"/>')
            y += 74
        note_lines = note.split(" and ")
        parts.append(f'<text x="{x0 + 18}" y="{top + 400}" class="note">{note_lines[0]}</text>')
        if len(note_lines) > 1:
            parts.append(f'<text x="{x0 + 18}" y="{top + 418}" class="note">and {note_lines[1]}</text>')
    parts.append("</svg>")
    write_svg(path, "\n".join(parts))


def fig7_spatial_network(path: Path) -> None:
    sources = read_csv(ROOT / "data" / "spatial_sources.csv")
    destinations = read_csv(ROOT / "data" / "spatial_destinations.csv")
    allocations = read_csv(OUTPUT / "spatial_allocations.csv")
    width, height = 1080, 680
    left, right, top, bottom = 70, 50, 70, 70
    lats = [num(row, "latitude") for row in sources + destinations]
    lons = [num(row, "longitude") for row in sources + destinations]
    min_lat, max_lat = min(lats) - 2, max(lats) + 2
    min_lon, max_lon = min(lons) - 3, max(lons) + 3
    plot_w, plot_h = width - left - right, height - top - bottom

    def xy(lat: float, lon: float) -> tuple[float, float]:
        x = left + (lon - min_lon) / (max_lon - min_lon) * plot_w
        y = top + plot_h - (lat - min_lat) / (max_lat - min_lat) * plot_h
        return x, y

    source_by_id = {row["source_id"]: row for row in sources}
    dest_by_id = {row["destination_id"]: row for row in destinations}
    colors = {
        "storage": "#4c78a8",
        "mineralization": "#59a14f",
        "thermochemical": "#f28e2b",
        "electrochemical": "#b07aa1",
        "photochemical": "#edc948",
    }
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        '<style>text{font-family:Arial,Helvetica,sans-serif;fill:#222}.title{font-size:20px;font-weight:700}.small{font-size:12px}.label{font-size:11px}.node{font-size:10px;font-weight:700}</style>',
        '<text x="35" y="32" class="title">Figure 7. Spatial CO2 allocation network</text>',
        '<text x="35" y="53" class="small">Line width scales with allocated CO2 flow. This is a schematic coordinate plot, not a final GIS map.</text>',
        f'<rect x="{left}" y="{top}" width="{plot_w}" height="{plot_h}" fill="#f8fafc" stroke="#d8dde5"/>',
    ]
    for allocation in allocations:
        source = source_by_id[allocation["source_id"]]
        dest = dest_by_id[allocation["destination_id"]]
        x1, y1 = xy(num(source, "latitude"), num(source, "longitude"))
        x2, y2 = xy(num(dest, "latitude"), num(dest, "longitude"))
        amount = num(allocation, "allocated_mtco2_per_year")
        family = allocation["technology_family"]
        color = colors.get(family, "#777")
        width_line = 1.5 + amount * 0.35
        parts.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{color}" stroke-width="{width_line:.1f}" stroke-opacity="0.72"/>')
    for source in sources:
        x, y = xy(num(source, "latitude"), num(source, "longitude"))
        r = 4 + num(source, "co2_available_mtpa") * 0.28
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.1f}" fill="#222" fill-opacity="0.78"/>')
        parts.append(f'<text x="{x + r + 3:.1f}" y="{y - 3:.1f}" class="label">{source["source_id"]}</text>')
    for dest in destinations:
        x, y = xy(num(dest, "latitude"), num(dest, "longitude"))
        parts.append(f'<rect x="{x - 6:.1f}" y="{y - 6:.1f}" width="12" height="12" fill="#ffffff" stroke="#222" stroke-width="1.6"/>')
        parts.append(f'<text x="{x + 9:.1f}" y="{y + 12:.1f}" class="label">{dest["destination_id"]}</text>')
    legend_y = height - 46
    parts.append(f'<text x="35" y="{legend_y}" class="small">Black circles: CO2 sources. White squares: destinations. Colors: storage, mineralization, thermochemical, electrochemical, photochemical.</text>')
    parts.append("</svg>")
    write_svg(path, "\n".join(parts))


def main() -> None:
    FIGURES.mkdir(parents=True, exist_ok=True)
    baseline = read_csv(OUTPUT / "baseline.csv")
    family = read_csv(OUTPUT / "family_best.csv")
    fig1_framework(FIGURES / "fig1_framework.svg")
    fig2_baseline(baseline, FIGURES / "fig2_baseline_net_cost.svg")
    fig3_family(family, FIGURES / "fig3_family_best.svg")
    shutil.copyfile(OUTPUT / "decision_map.svg", FIGURES / "fig4_decision_map.svg")
    fig5_market_residence(baseline, FIGURES / "fig5_market_residence.svg")
    fig6_targets(FIGURES / "fig6_research_targets.svg")
    if (OUTPUT / "spatial_allocations.csv").exists():
        fig7_spatial_network(FIGURES / "fig7_spatial_network.svg")


if __name__ == "__main__":
    main()
