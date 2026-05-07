"""Generate redesigned storyline figures for the Joule CO2 manuscript.

These figures are intentionally less like diagnostic plots and more like main
paper figures: each figure answers one reviewer-facing question.
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "joule_submission" / "figures_storyline"
STD = ROOT / "output" / "standard_profitability_matrix"
CHINA = ROOT / "output" / "china2060_optimistic_profitability"
CITY = ROOT / "output" / "china2060_city_archetypes"
FRONTIER = ROOT / "output" / "china2060_frontier_upgrade"
STRESS = ROOT / "output" / "china2060_market_stress"
OPT = ROOT / "output" / "china2060_deployment_optimization"
DATA = ROOT / "data"


YEARS = [2030, 2035, 2040, 2045, 2050, 2055, 2060]


COLORS = {
    "ink": "#243033",
    "muted": "#627176",
    "grid": "#dce6e8",
    "panel": "#f6f8f8",
    "water": "#e8f0f4",
    "neg": "#b9525f",
    "near": "#d9a441",
    "pos": "#2f8f83",
    "storage": "#225f74",
    "mineralization": "#3d8f63",
    "thermochemical": "#c97836",
    "electrochemical": "#7d63a6",
    "photochemical": "#a79b37",
    "policy": "#4e5557",
    "wait": "#aab4b8",
}


ARCHETYPE_COLORS = {
    "storage_first": COLORS["storage"],
    "mineralization_base": COLORS["mineralization"],
    "coastal_saf_export_hub": COLORS["thermochemical"],
    "northwest_h2_chemical_hub": "#b9842f",
    "electrochemical_formate_hub": COLORS["electrochemical"],
    "policy_backed_chemical_hub": "#8a6b3f",
    "wait_or_aggregate": COLORS["wait"],
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


PATHWAY_ORDER = [
    "geological_storage",
    "mineralization",
    "co2_h2_ft_saf",
    "co2_methanol_to_jet_saf",
    "rwgs_to_co",
    "co2_to_methanol",
    "co2_to_methane",
    "electrolysis_to_formate",
    "electrolysis_to_co",
    "electrolysis_to_ethylene",
    "photoelectrochemical_to_formate",
    "photocatalytic_to_co",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def f(value: Any, default: float = 0.0) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(parsed):
        return default
    return parsed


def esc(value: Any) -> str:
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def text(x: float, y: float, value: Any, size: int = 12, weight: int = 400, anchor: str = "start", color: str = COLORS["ink"]) -> str:
    return f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" font-weight="{weight}" text-anchor="{anchor}" fill="{color}">{esc(value)}</text>'


def rect(x: float, y: float, w: float, h: float, fill: str, stroke: str = "none", sw: float = 1.0, rx: float = 0.0) -> str:
    return f'<rect x="{x:.1f}" y="{y:.1f}" width="{max(0.0, w):.1f}" height="{max(0.0, h):.1f}" rx="{rx:.1f}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>'


def line(x1: float, y1: float, x2: float, y2: float, stroke: str = COLORS["grid"], sw: float = 1.0) -> str:
    return f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{stroke}" stroke-width="{sw}"/>'


def line_o(x1: float, y1: float, x2: float, y2: float, stroke: str = COLORS["grid"], sw: float = 1.0, opacity: float = 1.0) -> str:
    return f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{stroke}" stroke-width="{sw}" opacity="{opacity:.2f}" stroke-linecap="round"/>'


def circle(cx: float, cy: float, r: float, fill: str, stroke: str = "#ffffff", sw: float = 1.0, opacity: float = 1.0) -> str:
    return f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" opacity="{opacity:.2f}"/>'


def path_elem(d: str, fill: str, stroke: str = "#ffffff", sw: float = 0.35, opacity: float = 1.0) -> str:
    return f'<path d="{d}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" opacity="{opacity:.2f}" vector-effect="non-scaling-stroke"/>'


def title_block(title: str, subtitle: str) -> list[str]:
    return [
        rect(0, 0, 1420, 92, "#ffffff"),
        text(42, 42, title, 25, 700),
        text(42, 68, subtitle, 13, 400, "start", COLORS["muted"]),
    ]


def svg_start(title: str, subtitle: str, width: int = 1420, height: int = 980) -> list[str]:
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        "<style>text{font-family:Arial,Helvetica,sans-serif;} .mono{font-family:Consolas,monospace;}</style>",
        rect(0, 0, width, height, "#ffffff"),
        *title_block(title, subtitle),
    ]


def panel(letter: str, title: str, x: float, y: float, w: float, h: float) -> list[str]:
    return [
        rect(x, y, w, h, "#ffffff", "#dfe6e8", 1.0, 6),
        text(x + 16, y + 28, letter, 16, 700),
        text(x + 42, y + 28, title, 14, 700),
    ]


def save(name: str, parts: list[str]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    parts.append("</svg>")
    (OUT / name).write_text("\n".join(parts), encoding="utf-8")


def color_for_margin(value: float, vmin: float = -500, vmax: float = 500) -> str:
    if value >= 0:
        t = min(1.0, value / vmax)
        return f"rgb({int(235 - 188*t)},{int(247 - 100*t)},{int(242 - 118*t)})"
    t = min(1.0, abs(value) / abs(vmin))
    return f"rgb({int(250 - 70*t)},{int(232 - 120*t)},{int(224 - 110*t)})"


def impact_margin_color(value: float, vmin: float = -500, vmax: float = 1500) -> str:
    """Stronger diverging color for main-map heat panels."""
    if value >= 0:
        t = min(1.0, value / vmax)
        return f"rgb({int(232 - 196*t)},{int(246 - 128*t)},{int(235 - 158*t)})"
    t = min(1.0, abs(value) / abs(vmin))
    return f"rgb({int(252 - 122*t)},{int(230 - 145*t)},{int(214 - 111*t)})"


def bar_chart(rows: list[tuple[str, float, str]], x: float, y: float, w: float, h: float, unit: str = "") -> list[str]:
    parts = []
    max_value = max([abs(value) for _, value, _ in rows] + [1.0])
    zero_x = x + w * 0.42
    parts.append(line(zero_x, y, zero_x, y + h, "#9aa6aa", 1))
    row_h = h / max(1, len(rows))
    for i, (label, value, color) in enumerate(rows):
        cy = y + i * row_h + row_h * 0.55
        parts.append(text(x, cy + 4, label, 10, 500, "start", COLORS["ink"]))
        bw = abs(value) / max_value * (w * 0.52)
        if value >= 0:
            parts.append(rect(zero_x, cy - 8, bw, 15, color))
            parts.append(text(zero_x + bw + 5, cy + 4, f"{value:.1f}{unit}", 9, 600, "start", COLORS["muted"]))
        else:
            parts.append(rect(zero_x - bw, cy - 8, bw, 15, color))
            parts.append(text(zero_x - bw - 5, cy + 4, f"{value:.1f}{unit}", 9, 600, "end", COLORS["muted"]))
    return parts


def figure1() -> None:
    parts = svg_start(
        "Figure 1. The captured-CO2 allocation decision",
        "A tonne of captured CO2 is routed through geography, energy, market and policy gates before it becomes investable.",
    )
    parts.extend(panel("A", "One tonne enters the allocator", 40, 120, 360, 300))
    parts.append(rect(95, 205, 250, 74, "#e8f0f4", "#b8c9d1", 1, 6))
    parts.append(text(220, 235, "1 t captured CO2", 20, 700, "middle"))
    parts.append(text(220, 262, "quality, pressure, impurities, capture cost", 11, 400, "middle", COLORS["muted"]))
    parts.extend(panel("B", "Gates that decide route value", 430, 120, 500, 300))
    gates = [
        ("source quality", COLORS["storage"]),
        ("transport + hubs", "#5b8fa8"),
        ("clean electricity", COLORS["electrochemical"]),
        ("green H2", "#7aa45f"),
        ("product offtake", COLORS["thermochemical"]),
        ("policy + MRV", COLORS["policy"]),
    ]
    for i, (gate, color) in enumerate(gates):
        gx = 470 + (i % 3) * 145
        gy = 185 + (i // 3) * 92
        parts.append(rect(gx, gy, 120, 46, color, "none", 1, 6))
        parts.append(text(gx + 60, gy + 29, gate, 12, 700, "middle", "#ffffff"))
    parts.extend(panel("C", "Competing route families", 960, 120, 380, 300))
    routes = [
        ("Storage", COLORS["storage"]),
        ("Mineralization", COLORS["mineralization"]),
        ("SAF/fuels", COLORS["thermochemical"]),
        ("Chemicals", "#8a6b3f"),
        ("Electro/formate", COLORS["electrochemical"]),
        ("Photo routes", COLORS["photochemical"]),
        ("EOR overlay", "#7b6b55"),
    ]
    for i, (route, color) in enumerate(routes):
        parts.append(rect(1005, 168 + i * 31, 210, 22, color, "none", 1, 4))
        parts.append(text(1110, 184 + i * 31, route, 11, 700, "middle", "#ffffff"))
    parts.extend(panel("D", "Main output metrics", 40, 460, 1300, 330))
    metrics = [
        ("margin", "USD/tCO2"),
        ("annual profit", "billion USD/yr"),
        ("durable CO2", "MtCO2/yr"),
        ("net avoided emissions", "tCO2e/tCO2"),
        ("break-even thresholds", "price, H2, policy"),
        ("policy survival", "capacity after support"),
        ("robustness", "profit-at-risk"),
    ]
    for i, (m, u) in enumerate(metrics):
        mx = 85 + i * 178
        parts.append(rect(mx, 555, 138, 76, "#f6f8f8", "#dce6e8", 1, 6))
        parts.append(text(mx + 69, 584, m, 13, 700, "middle"))
        parts.append(text(mx + 69, 609, u, 10, 400, "middle", COLORS["muted"]))
    parts.append(text(690, 704, "Paper question: where, when and under what policy does each CO2 route become investable?", 20, 700, "middle"))
    save("figure1_decision_problem.svg", parts)


def figure1_decision_baseline() -> None:
    parts = svg_start(
        "Figure 1. Decision problem and current baseline failure",
        "The paper starts from a hard constraint: captured CO2 has many possible destinations, but current conditions do not make them broadly profitable.",
    )
    system = read_csv(STD / "standard_scenario_system_summary.csv")
    thresholds = read_csv(STD / "technology_profitability_thresholds.csv")
    source_balance = read_csv(ROOT / "output" / "submission_upgrade_v2" / "industrial_source_balance_v2.csv")
    source_values = sorted(
        [(row["sector"], f(row["current_model_available_mtco2_per_year"])) for row in source_balance],
        key=lambda item: item[1],
        reverse=True,
    )
    source_total = sum(value for _, value in source_values) or 1.0
    source_groups = source_values[:2] + [("other screened sources", sum(value for _, value in source_values[2:]))]
    source_colors = {
        "coal_power": COLORS["storage"],
        "steel": "#6e8086",
        "other screened sources": "#aebbbf",
    }

    parts.extend(panel("A", "What happens to one captured tonne?", 40, 120, 420, 300))
    parts.append(text(72, 176, "One captured tonne is tested against feasible routes.", 9, 800, "start", COLORS["ink"]))
    parts.append(text(72, 192, f"Modelled large point-source pool: {source_total / 1000:.1f} GtCO2/yr.", 8, 600, "start", COLORS["muted"]))
    parts.append(text(72, 207, "Not total China emissions.", 7, 500, "start", COLORS["muted"]))

    # Step 1: a captured tonne with source-specific properties.
    parts.append(rect(72, 222, 96, 86, "#e9f2f5", "#b9ced7", 1.1, 7))
    parts.append(text(120, 247, "1 t CO2", 17, 800, "middle", COLORS["ink"]))
    parts.append(text(120, 267, "from a source", 8, 700, "middle", COLORS["muted"]))
    parts.append(text(120, 283, "quality + cost", 8, 700, "middle", COLORS["muted"]))
    source_note = ", ".join(f"{label.replace('_', ' ')[:5]} {value / 1000:.1f}" for label, value in source_groups[:2])
    parts.append(text(120, 325, source_note + " Gt/yr", 7, 600, "middle", COLORS["muted"]))

    # Step 2: the same tonne is tested against feasible route families.
    parts.append(line_o(168, 258, 205, 258, COLORS["grid"], 2.4, 1.0))
    parts.append(text(186, 249, "test", 7, 700, "middle", COLORS["muted"]))
    parts.append(rect(205, 195, 110, 146, "#ffffff", "#d5e0e2", 1.0, 7))
    parts.append(text(260, 214, "route candidates", 9, 800, "middle", COLORS["ink"]))
    route_nodes = [
        ("storage", COLORS["storage"]),
        ("mineral", COLORS["mineralization"]),
        ("SAF", COLORS["thermochemical"]),
        ("chemical", COLORS["electrochemical"]),
        ("defer", COLORS["wait"]),
        ("CO2 hub", "#6f7c80"),
    ]
    for i, (label, color) in enumerate(route_nodes):
        y = 224 + i * 18
        parts.append(rect(222, y, 76, 14, color, "none", 1, 4))
        parts.append(text(260, y + 10, label, 6, 800, "middle", "#ffffff"))

    # Step 3: the optimizer selects the best feasible route or no-build.
    parts.append(line_o(315, 258, 348, 258, COLORS["grid"], 2.4, 1.0))
    parts.append(text(332, 249, "score", 7, 700, "middle", COLORS["muted"]))
    parts.append(rect(348, 215, 82, 86, "#f4f7f7", "#d5e0e2", 1.0, 7))
    parts.append(text(389, 236, "LP selects", 10, 800, "middle", COLORS["ink"]))
    for i, label in enumerate(["margin", "capacity", "city cap", "durable"]):
        parts.append(rect(360, 249 + i * 13, 58, 10, "#e2ece8", "none", 1, 3))
        parts.append(text(389, 257 + i * 13, label, 6, 800, "middle", COLORS["muted"]))

    parts.append(text(72, 366, "Output: selected route, hub aggregation, or defer/no-build.", 9, 800, "start", COLORS["ink"]))
    parts.append(text(72, 384, "This is the allocation unit used in every city-year.", 8, 500, "start", COLORS["muted"]))
    parts.extend(panel("B", "Current scenario best margin", 500, 120, 420, 300))
    label_map = {
        "china_current_2030": "China 2030",
        "china_high_policy_2040": "high policy",
        "low_green_h2_2040": "low H2",
        "ultra_low_power_product_high_2040": "cheap power + product",
        "eu_saf_export_2040": "SAF export",
        "dac_cdr_credit_2040": "DAC credit",
        "learning_2050_high_product": "2050 learning",
        "breakthrough_utilization_2050": "breakthrough",
    }
    ranked = sorted(system, key=lambda row: f(row["best_margin_usd_per_tco2"]))[:8]
    max_gap = max(abs(f(row["best_margin_usd_per_tco2"])) for row in ranked) or 1.0
    for i, row in enumerate(ranked):
        y = 168 + i * 24
        value = f(row["best_margin_usd_per_tco2"])
        parts.append(text(525, y + 14, label_map.get(row["scenario"], row["scenario"]), 9, 600, "start", COLORS["muted"]))
        bw = abs(value) / max_gap * 150
        parts.append(rect(705 - bw, y, bw, 15, COLORS["neg"], "none", 1, 2))
        parts.append(text(715, y + 12, f"{value:.1f}", 9, 700, "start", COLORS["ink"]))
    parts.append(line(705, 162, 705, 365, "#9aa6aa", 1))
    parts.extend(panel("C", "Closest break-even routes", 960, 120, 380, 300))
    top = sorted(thresholds, key=lambda row: f(row["profitability_gap_usd_per_tco2"]))[:5]
    rows2 = [(PATHWAY_LABELS.get(row["pathway"], row["pathway"]), f(row["profitability_gap_usd_per_tco2"]), COLORS["near"]) for row in top]
    parts.extend(bar_chart(rows2, 985, 165, 320, 210, ""))
    parts.extend(panel("D", "Current-to-2060 evidence matrix", 40, 470, 1300, 300))
    city2060 = [row for row in read_csv(CITY / "city_archetypes_by_year.csv") if int(row["year"]) == 2060]
    values = [f(row["best_margin_usd_per_tco2"]) for row in city2060]
    positive = sum(1 for value in values if value > 0)
    max_value = max(values) if values else 0.0
    frontier2060 = [
        row
        for row in read_csv(FRONTIER / "buildout_frontier.csv")
        if int(row["year"]) == 2060 and row["scenario"] == "policy_supported_effort" and row["frontier_target_label"] == "max_profit"
    ]
    max_profit = frontier2060[0] if frontier2060 else {}
    current_positive = sum(1 for row in system if f(row["best_margin_usd_per_tco2"]) > 0)
    current_best = max([f(row["best_margin_usd_per_tco2"]) for row in system] or [0.0])

    table_x, table_y = 70, 525
    col_w, row_h = 130, 32
    columns = ["metric", "current screen", "2060 city screen", "2060 LP"]
    metrics = [
        ("positive units", f"{current_positive}/{len(system)} scen.", f"{positive}/{len(values)} cities", f"{f(max_profit.get('allocated_mtco2_per_year')):.0f} Mt managed"),
        ("best margin", f"{current_best:.1f} USD/t", f"{max_value:.0f} USD/t", f"{f(max_profit.get('average_margin_usd_per_tco2')):.0f} USD/t"),
        ("durable CO2", "0 Mt/yr", "city potential", f"{f(max_profit.get('durable_allocated_mtco2_per_year')):.0f} Mt/yr"),
        ("profit pool", "0 BUSD/yr", "screening", f"{f(max_profit.get('profit_busd_per_year')):.1f} BUSD/yr"),
    ]
    for j, column in enumerate(columns):
        parts.append(rect(table_x + j * col_w, table_y, col_w - 4, 24, "#eef4f3", "#ffffff", 0.5, 2))
        parts.append(text(table_x + j * col_w + 8, table_y + 16, column, 8, 800, "start", COLORS["muted"]))
    for i, row_values in enumerate(metrics):
        for j, value in enumerate(row_values):
            fill = "#ffffff" if j == 0 else color_for_margin(-30 if "current" in columns[j] else 30, -100, 100)
            if j == 3 and i in (0, 1, 2, 3):
                fill = "#d9ece3"
            parts.append(rect(table_x + j * col_w, table_y + 28 + i * row_h, col_w - 4, row_h - 4, fill, "#ffffff", 0.5, 2))
            parts.append(text(table_x + j * col_w + 8, table_y + 49 + i * row_h, value, 8, 700 if j > 0 else 600, "start", COLORS["ink"]))

    bins = [-600, -300, -100, 0, 100, 300, 600, 900, 1200, 1600]
    counts = [0 for _ in range(len(bins) - 1)]
    for value in values:
        for i in range(len(bins) - 1):
            if bins[i] <= value < bins[i + 1] or (i == len(bins) - 2 and value >= bins[i + 1]):
                counts[i] += 1
                break
    chart_x, chart_y, chart_w, chart_h = 610, 548, 430, 115
    max_count = max(counts + [1])
    parts.append(line(chart_x, chart_y + chart_h, chart_x + chart_w, chart_y + chart_h, "#93a0a4", 1))
    zero_pos = chart_x + (0 - bins[0]) / (bins[-1] - bins[0]) * chart_w
    parts.append(line(zero_pos, chart_y - 8, zero_pos, chart_y + chart_h + 8, COLORS["ink"], 1.5))
    parts.append(text(zero_pos, chart_y + chart_h + 23, "0", 8, 700, "middle", COLORS["ink"]))
    for i, count in enumerate(counts):
        x = chart_x + (bins[i] - bins[0]) / (bins[-1] - bins[0]) * chart_w
        bw = (bins[i + 1] - bins[i]) / (bins[-1] - bins[0]) * chart_w - 4
        bh = count / max_count * chart_h
        mid = (bins[i] + bins[i + 1]) / 2
        parts.append(rect(x + 2, chart_y + chart_h - bh, bw, bh, impact_margin_color(mid), "#ffffff", 0.5, 2))
        if count:
            parts.append(text(x + bw / 2 + 2, chart_y + chart_h - bh - 5, count, 8, 700, "middle", COLORS["muted"]))
    for tick in [-600, 0, 600, 1200, 1600]:
        tx = chart_x + (tick - bins[0]) / (bins[-1] - bins[0]) * chart_w
        parts.append(text(tx, chart_y + chart_h + 38, tick, 7, 600, "middle", COLORS["muted"]))
    parts.append(text(chart_x + chart_w / 2, chart_y - 14, "2060 city margin distribution", 10, 800, "middle", COLORS["ink"]))

    family_counts: dict[str, int] = {}
    for row in city2060:
        family = row["best_family"] or row["archetype"]
        family_counts[family] = family_counts.get(family, 0) + 1
    fx, fy = 1090, 525
    parts.append(text(fx, fy + 16, "2060 best-family count", 10, 800))
    for i, (family, count) in enumerate(sorted(family_counts.items(), key=lambda item: item[1], reverse=True)[:5]):
        y = fy + 36 + i * 30
        color = COLORS.get(family, ARCHETYPE_COLORS.get(family, COLORS["policy"]))
        parts.append(rect(fx, y, min(185, count / max(family_counts.values()) * 185), 15, color, "none", 1, 2))
        parts.append(text(fx + 195, y + 12, f"{family[:18]} {count}", 8, 700, "start", COLORS["ink"]))
    save("figure1_decision_baseline.svg", parts)


def figure2() -> None:
    parts = svg_start(
        "Figure 2. Current conditions fail the broad-profitability test",
        "The baseline result is a disciplined negative result: no current route is broadly profitable.",
    )
    system = read_csv(STD / "standard_scenario_system_summary.csv")
    thresholds = read_csv(STD / "technology_profitability_thresholds.csv")
    parts.extend(panel("A", "Best margin across standard scenarios", 40, 120, 620, 330))
    rows = [(row["scenario"], f(row["best_margin_usd_per_tco2"]), COLORS["neg"]) for row in system]
    parts.extend(bar_chart(rows, 65, 165, 560, 245, ""))
    parts.extend(panel("B", "Break-even product/policy thresholds", 700, 120, 640, 330))
    top = sorted(thresholds, key=lambda row: f(row["profitability_gap_usd_per_tco2"]))[:8]
    rows2 = [(PATHWAY_LABELS.get(row["pathway"], row["pathway"]), f(row["profitability_gap_usd_per_tco2"]), COLORS["near"]) for row in top]
    parts.extend(bar_chart(rows2, 725, 165, 570, 245, ""))
    parts.extend(panel("C", "Why this matters", 40, 490, 620, 300))
    points = [
        "Storage is closest, but still needs stronger carbon value or lower delivered cost.",
        "Mineralization is the nearest utilization route.",
        "SAF and electrochemical routes need product premiums plus low-carbon inputs.",
        "The model prevents a generic 'CO2 utilization is profitable' overclaim.",
    ]
    for i, point in enumerate(points):
        parts.append(circle(75, 555 + i * 48, 5, COLORS["ink"]))
        parts.append(text(95, 560 + i * 48, point, 13, 500))
    parts.extend(panel("D", "Takeaway", 700, 490, 640, 300))
    parts.append(text(1020, 585, "Current baseline:", 18, 700, "middle"))
    parts.append(text(1020, 625, "0 positive routes", 34, 700, "middle", COLORS["neg"]))
    parts.append(text(1020, 664, "This is the anchor for a credible conditional-optimism story.", 13, 500, "middle", COLORS["muted"]))
    save("figure2_current_conditions_fail.svg", parts)


def load_geo_centers() -> dict[str, tuple[float, float]]:
    path = DATA / "admin" / "prefecture_boundaries.geojson"
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    centers = {}
    for feature in data.get("features", []):
        props = feature.get("properties", {})
        code = str(props.get("prefecture_code", ""))
        center = props.get("center") or props.get("centroid")
        if code and center:
            centers[code] = (float(center[0]), float(center[1]))
    return centers


def project(lon: float, lat: float, x: float, y: float, w: float, h: float) -> tuple[float, float]:
    lon_min, lon_max = 73.0, 135.5
    lat_min, lat_max = 18.0, 53.5
    px = x + (lon - lon_min) / (lon_max - lon_min) * w
    py = y + h - (lat - lat_min) / (lat_max - lat_min) * h
    return px, py


def load_prefecture_features() -> list[dict[str, Any]]:
    path = DATA / "admin" / "prefecture_boundaries.geojson"
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("features", [])


def geometry_to_path(geometry: dict[str, Any], x: float, y: float, w: float, h: float, max_points_per_ring: int = 110) -> str:
    if geometry.get("type") == "Polygon":
        polygons = [geometry.get("coordinates", [])]
    elif geometry.get("type") == "MultiPolygon":
        polygons = geometry.get("coordinates", [])
    else:
        polygons = []
    commands: list[str] = []
    for polygon in polygons:
        for ring in polygon:
            if len(ring) < 3:
                continue
            step = max(1, len(ring) // max_points_per_ring)
            sampled = ring[::step]
            if sampled[-1] != ring[-1]:
                sampled.append(ring[-1])
            first = sampled[0]
            px, py = project(float(first[0]), float(first[1]), x, y, w, h)
            commands.append(f"M{px:.1f},{py:.1f}")
            for lon, lat in sampled[1:]:
                px, py = project(float(lon), float(lat), x, y, w, h)
                commands.append(f"L{px:.1f},{py:.1f}")
            commands.append("Z")
    return " ".join(commands)


def load_optimized_city_allocations() -> dict[str, dict[str, Any]]:
    allocations: dict[str, dict[str, Any]] = {}
    path = FRONTIER / "frontier_top_allocations.csv"
    if not path.exists():
        return allocations
    for row in read_csv(path):
        if row["frontier_target_label"] != "max_profit" or int(row["year"]) != 2060:
            continue
        city_id = str(row["city_id"])
        record = allocations.setdefault(city_id, {"mt": 0.0, "profit": 0.0, "categories": {}})
        mt = f(row["allocated_mtco2_per_year"])
        record["mt"] += mt
        record["profit"] += f(row["profit_musd_per_year"])
        cats = record["categories"]
        cats[row["category"]] = cats.get(row["category"], 0.0) + mt
    return allocations


def category_color(category: str) -> str:
    if category == "geological_storage":
        return COLORS["storage"]
    if category == "mineral_products":
        return COLORS["mineralization"]
    if category == "synthetic_fuels":
        return COLORS["thermochemical"]
    if category == "chemicals":
        return "#8a6b3f"
    return COLORS["policy"]


def load_point_table(path: Path, id_col: str) -> dict[str, tuple[float, float]]:
    if not path.exists():
        return {}
    out: dict[str, tuple[float, float]] = {}
    for row in read_csv(path):
        if id_col in row and "longitude" in row and "latitude" in row:
            out[str(row[id_col])] = (f(row["longitude"]), f(row["latitude"]))
    return out


def draw_route_network(x: float, y: float, w: float, h: float, allocation_rows: list[dict[str, str]]) -> list[str]:
    sources = load_point_table(DATA / "real_inputs_top300_with_dac" / "spatial_sources_real.csv", "source_id")
    destinations = load_point_table(DATA / "real_inputs_top300_with_dac" / "spatial_destinations_real.csv", "destination_id")
    parts: list[str] = []
    top = sorted(allocation_rows, key=lambda row: f(row["allocated_mtco2_per_year"]), reverse=True)[:42]
    max_mt = max([f(row["allocated_mtco2_per_year"]) for row in top] + [1.0])
    for row in top:
        src = sources.get(row["source_id"])
        dst = destinations.get(row["destination_id"])
        if not src or not dst:
            continue
        sx, sy = project(src[0], src[1], x, y, w, h)
        dx, dy = project(dst[0], dst[1], x, y, w, h)
        mt = f(row["allocated_mtco2_per_year"])
        color = category_color(row["category"])
        parts.append(line_o(sx, sy, dx, dy, color, 0.7 + 3.8 * mt / max_mt, 0.34))
    for row in top:
        src = sources.get(row["source_id"])
        dst = destinations.get(row["destination_id"])
        if not src or not dst:
            continue
        sx, sy = project(src[0], src[1], x, y, w, h)
        dx, dy = project(dst[0], dst[1], x, y, w, h)
        mt = f(row["allocated_mtco2_per_year"])
        color = category_color(row["category"])
        parts.append(circle(sx, sy, 1.8 + math.sqrt(mt) * 0.9, color, "#ffffff", 0.35, 0.85))
        parts.append(circle(dx, dy, 2.4 + math.sqrt(mt) * 1.1, "#ffffff", color, 1.1, 0.88))
    return parts


def draw_margin_heatmap(x: float, y: float, w: float, h: float, rows: list[dict[str, str]], show_allocations: bool = True) -> list[str]:
    parts: list[str] = [rect(x, y, w, h, COLORS["water"], "#d3dde0", 1, 6)]
    features = load_prefecture_features()
    margins = {str(row["city_id"]): f(row["best_margin_usd_per_tco2"]) for row in rows}
    allocations = load_optimized_city_allocations() if show_allocations else {}
    centers = load_geo_centers()

    for feature in features:
        props = feature.get("properties", {})
        code = str(props.get("prefecture_code", ""))
        d = geometry_to_path(feature.get("geometry", {}), x + 8, y + 10, w - 16, h - 20)
        if not d:
            continue
        value = margins.get(code)
        if value is None:
            fill = "#d4dcdf"
            stroke = "#aebcc1"
            stroke_width = 0.34
            opacity = 0.88
        else:
            fill = impact_margin_color(value)
            stroke = "#ffffff"
            stroke_width = 0.28
            opacity = 0.94
        parts.append(path_elem(d, fill, stroke, stroke_width, opacity))

    if show_allocations:
        for city_id, record in sorted(allocations.items(), key=lambda item: item[1]["mt"], reverse=True)[:55]:
            center = centers.get(city_id)
            if not center:
                continue
            px, py = project(center[0], center[1], x + 8, y + 10, w - 16, h - 20)
            dominant = max(record["categories"].items(), key=lambda item: item[1])[0]
            radius = 2.2 + math.sqrt(max(0.0, record["mt"])) * 1.85
            parts.append(circle(px, py, radius + 1.3, "#ffffff", "#ffffff", 0.4, 0.74))
            parts.append(circle(px, py, radius, category_color(dominant), "#243033", 0.35, 0.90))

    legend_x, legend_y = x + 26, y + h - 46
    legend_values = [(-500, "< -500"), (-100, "-100"), (0, "0"), (500, "+500"), (1200, "> +1200")]
    for i, (value, label) in enumerate(legend_values):
        parts.append(rect(legend_x + i * 64, legend_y, 52, 12, impact_margin_color(value), "#ffffff", 0.4, 2))
        parts.append(text(legend_x + i * 64 + 26, legend_y + 29, label, 8, 600, "middle", COLORS["muted"]))
    nodata_x = legend_x + len(legend_values) * 64
    parts.append(rect(nodata_x, legend_y, 52, 12, "#d4dcdf", "#aebcc1", 0.4, 2))
    parts.append(text(nodata_x + 26, legend_y + 29, "no data", 8, 600, "middle", COLORS["muted"]))
    parts.append(text(legend_x, legend_y - 7, "prefecture fill = best 2060 margin (USD/tCO2)", 8, 600, "start", COLORS["muted"]))
    if show_allocations:
        bx = x + w - 228
        parts.append(text(bx, legend_y - 7, "circles = optimized allocation", 8, 600, "start", COLORS["muted"]))
        for i, (mt, label) in enumerate([(2, "2"), (10, "10"), (25, "25 Mt/yr")]):
            r = 2.2 + math.sqrt(mt) * 1.85
            cx = bx + 18 + i * 60
            parts.append(circle(cx, legend_y + 9, r, COLORS["storage"], "#243033", 0.35, 0.85))
            parts.append(text(cx, legend_y + 31, label, 8, 600, "middle", COLORS["muted"]))
    return parts


def figure3() -> None:
    parts = svg_start(
        "Figure 2. National opportunity heatmap: where different CO2 bases should be built",
        "Prefecture fill shows best 2060 route margin; circles show optimized max-profit CO2 allocation.",
    )
    rows = [row for row in read_csv(CITY / "city_archetypes_by_year.csv") if int(row["year"]) == 2060]
    summary = [row for row in read_csv(CITY / "city_archetype_summary.csv") if int(row["year"]) == 2060]
    allocations = load_optimized_city_allocations()
    parts.extend(panel("A", "2060 national heatmap with optimized allocation bubbles", 40, 120, 880, 650))
    parts.extend(draw_margin_heatmap(62, 165, 835, 560, rows, True))

    parts.extend(panel("B", "City archetype count", 950, 120, 390, 235))
    count_rows = [(row["archetype_label"][:26], f(row["city_count"]), ARCHETYPE_COLORS.get(row["archetype"], COLORS["wait"])) for row in summary]
    parts.extend(bar_chart(count_rows, 965, 165, 345, 150, ""))

    parts.extend(panel("C", "Largest optimized city allocations", 950, 385, 390, 280))
    city_lookup = {str(row["city_id"]): row for row in rows}
    for i, (city_id, record) in enumerate(sorted(allocations.items(), key=lambda item: item[1]["mt"], reverse=True)[:7]):
        row = city_lookup.get(city_id, {})
        dominant = max(record["categories"].items(), key=lambda item: item[1])[0]
        y = 430 + i * 31
        parts.append(rect(980, y, 18, 18, category_color(dominant), "none", 1, 3))
        label = f"{city_id}  {record['mt']:.1f} Mt/yr  {record['profit']/1000:.1f} BUSD"
        parts.append(text(1008, y + 14, label, 10, 700))
        parts.append(text(1008, y + 28, f"{dominant.replace('_', ' ')}; {row.get('best_pathway', 'mixed')}", 8, 500, "start", COLORS["muted"]))

    parts.extend(panel("D", "Map interpretation", 950, 695, 390, 150))
    parts.append(text(1145, 745, "The map should not read as", 13, 700, "middle", COLORS["ink"]))
    parts.append(text(1145, 772, "'build utilization everywhere'.", 18, 700, "middle", COLORS["neg"]))
    parts.append(text(1145, 806, "It says: build hubs only where margin, scale and logistics co-locate.", 10, 600, "middle", COLORS["muted"]))
    save("figure2_where_to_build.svg", parts)


def figure4() -> None:
    parts = svg_start(
        "Figure 4. When routes become investable on the 2030-2060 timeline",
        "The dual-carbon pathway is a sequence, not a single date.",
    )
    pathway_rows = read_csv(CHINA / "china2060_pathway_summary.csv")
    earliest = read_csv(CHINA / "china2060_earliest_profit_windows.csv")
    lookup = {(row["pathway"], int(row["year"])): f(row["best_margin_usd_per_tco2"]) for row in pathway_rows}
    parts.extend(panel("A", "Best margin heatmap", 40, 120, 850, 540))
    x0, y0 = 205, 170
    cell_w, cell_h = 84, 31
    for j, year in enumerate(YEARS):
        parts.append(text(x0 + j * cell_w + cell_w / 2, y0 - 14, year, 10, 700, "middle", COLORS["muted"]))
    for i, pathway in enumerate(PATHWAY_ORDER):
        parts.append(text(70, y0 + i * cell_h + 20, PATHWAY_LABELS[pathway], 10, 600))
        for j, year in enumerate(YEARS):
            value = lookup.get((pathway, year), -1000.0)
            parts.append(rect(x0 + j * cell_w, y0 + i * cell_h, cell_w - 3, cell_h - 3, color_for_margin(value), "#ffffff", 0.5, 2))
            if value > 0:
                parts.append(text(x0 + j * cell_w + cell_w / 2, y0 + i * cell_h + 20, f"{value:.0f}", 9, 700, "middle"))
    parts.extend(panel("B", "First profitable year", 930, 120, 410, 540))
    first_rows = []
    for row in earliest:
        first = row["first_profitable_year"] or "none"
        first_rows.append((PATHWAY_LABELS.get(row["pathway"], row["pathway"]), first, f(row["best_margin_usd_per_tco2"])))
    for i, (label, first, margin) in enumerate(first_rows):
        y = 165 + i * 35
        color = COLORS["pos"] if first != "none" else COLORS["wait"]
        parts.append(rect(960, y, 110, 22, color, "none", 1, 4))
        parts.append(text(1015, y + 15, first, 10, 700, "middle", "#ffffff"))
        parts.append(text(1085, y + 15, label, 10, 600))
    parts.extend(panel("C", "Takeaway", 40, 700, 1300, 160))
    parts.append(text(690, 765, "Mineralization opens first; storage, SAF, RWGS-CO and formate follow under coordinated dual-carbon effort.", 19, 700, "middle"))
    save("figure4_when_profitable.svg", parts)


def figure3_timing_switches() -> None:
    parts = svg_start(
        "Figure 3. When routes turn profitable and what flips them",
        "The 2030-2060 sequence is governed by product value, policy value, H2, electricity, transport and reliability.",
    )
    pathway_rows = read_csv(CHINA / "china2060_pathway_summary.csv")
    drivers = read_csv(OPT / "uncertainty_driver_rank.csv")
    lookup = {(row["pathway"], int(row["year"])): f(row["best_margin_usd_per_tco2"]) for row in pathway_rows}
    parts.extend(panel("A", "2030-2060 margin heatmap", 40, 120, 820, 500))
    x0, y0 = 205, 170
    cell_w, cell_h = 82, 30
    for j, year in enumerate(YEARS):
        parts.append(text(x0 + j * cell_w + cell_w / 2, y0 - 14, year, 10, 700, "middle", COLORS["muted"]))
    for i, pathway in enumerate(PATHWAY_ORDER):
        parts.append(text(70, y0 + i * cell_h + 19, PATHWAY_LABELS[pathway], 10, 600))
        for j, year in enumerate(YEARS):
            value = lookup.get((pathway, year), -1000.0)
            parts.append(rect(x0 + j * cell_w, y0 + i * cell_h, cell_w - 3, cell_h - 3, color_for_margin(value), "#ffffff", 0.5, 2))
            if value > 0:
                parts.append(text(x0 + j * cell_w + cell_w / 2, y0 + i * cell_h + 19, f"{value:.0f}", 9, 700, "middle"))
    parts.extend(panel("B", "Dominant uncertainty drivers", 900, 120, 440, 500))
    pathways = ["co2_h2_ft_saf", "mineralization", "geological_storage", "electrolysis_to_formate", "rwgs_to_co", "co2_to_methanol"]
    driver_names = ["product_price", "policy_credit", "h2_price", "transport_cost", "capture_energy_cost", "reliability_cost"]
    dlookup = {(row["pathway"], row["driver"]): f(row["abs_correlation_with_margin"]) for row in drivers}
    hx, hy, cw, ch = 1045, 180, 46, 43
    for j, driver in enumerate(driver_names):
        parts.append(text(hx + j * cw + cw / 2, 162, driver.split("_")[0][:6], 8, 600, "middle", COLORS["muted"]))
    for i, pathway in enumerate(pathways):
        parts.append(text(925, hy + i * ch + 27, PATHWAY_LABELS[pathway], 9, 600))
        for j, driver in enumerate(driver_names):
            val = dlookup.get((pathway, driver), 0.0)
            color = f"rgb({int(242 - 175*val)},{int(248 - 100*val)},{int(244 - 130*val)})"
            parts.append(rect(hx + j * cw, hy + i * ch, cw - 3, ch - 3, color, "#ffffff", 0.4, 2))
            if val > 0.15:
                parts.append(text(hx + j * cw + cw / 2, hy + i * ch + 27, f"{val:.2f}", 8, 700, "middle"))
    parts.extend(panel("C", "Takeaway", 40, 665, 1300, 165))
    parts.append(text(690, 735, "Mineralization opens first; SAF, storage, RWGS-CO and formate require combined policy, product and clean-energy progress.", 18, 700, "middle"))
    save("figure3_when_and_switches.svg", parts)


def figure5() -> None:
    parts = svg_start(
        "Figure 5. What flips profitability",
        "Break-even thresholds identify the variables worth changing, not just the routes worth naming.",
    )
    thresholds = read_csv(STD / "technology_profitability_thresholds.csv")
    drivers = read_csv(OPT / "uncertainty_driver_rank.csv")
    parts.extend(panel("A", "Break-even gap by route", 40, 120, 620, 360))
    rows = [(PATHWAY_LABELS.get(row["pathway"], row["pathway"]), f(row["profitability_gap_usd_per_tco2"]), COLORS["near"]) for row in sorted(thresholds, key=lambda r: f(r["profitability_gap_usd_per_tco2"]))[:10]]
    parts.extend(bar_chart(rows, 65, 165, 560, 260, ""))
    parts.extend(panel("B", "Dominant uncertainty drivers", 700, 120, 640, 360))
    pathways = ["co2_h2_ft_saf", "mineralization", "geological_storage", "electrolysis_to_formate", "rwgs_to_co", "co2_to_methanol"]
    driver_names = ["product_price", "policy_credit", "h2_price", "transport_cost", "capture_energy_cost", "reliability_cost"]
    lookup = {(row["pathway"], row["driver"]): f(row["abs_correlation_with_margin"]) for row in drivers}
    x0, y0 = 865, 175
    cw, ch = 70, 35
    for j, driver in enumerate(driver_names):
        parts.append(text(x0 + j * cw + cw / 2, 158, driver.split("_")[0], 9, 600, "middle", COLORS["muted"]))
    for i, pathway in enumerate(pathways):
        parts.append(text(730, y0 + i * ch + 22, PATHWAY_LABELS[pathway], 10, 600))
        for j, driver in enumerate(driver_names):
            val = lookup.get((pathway, driver), 0.0)
            color = f"rgb({int(242 - 175*val)},{int(248 - 100*val)},{int(244 - 130*val)})"
            parts.append(rect(x0 + j * cw, y0 + i * ch, cw - 3, ch - 3, color, "#ffffff", 0.4, 2))
            if val > 0.1:
                parts.append(text(x0 + j * cw + cw / 2, y0 + i * ch + 22, f"{val:.2f}", 9, 700, "middle"))
    parts.extend(panel("C", "Interpretation", 40, 520, 1300, 230))
    statements = [
        "Product price dominates fuels and chemicals.",
        "Policy credit dominates storage.",
        "Mineralization needs both product standards and carbon value.",
        "Cheap electricity or hydrogen alone rarely solves the full cost stack.",
    ]
    for i, s in enumerate(statements):
        parts.append(rect(95 + i * 305, 600, 250, 58, "#f6f8f8", "#dce6e8", 1, 6))
        parts.append(text(220 + i * 305, 633, s, 12, 700, "middle"))
    save("figure5_profitability_switches.svg", parts)


def figure6() -> None:
    parts = svg_start(
        "Figure 4. Market size is not carbon neutrality",
        "Product value can be large while durable CO2 capacity remains limited.",
    )
    market = [row for row in read_csv(STRESS / "market_scale_by_product.csv") if int(row["year"]) == 2060 and row["price_case"] == "high"]
    factories = [row for row in read_csv(STRESS / "factory_buildout_by_category_2060.csv") if row["scenario"] == "policy_supported_effort"]
    frontier = [row for row in read_csv(FRONTIER / "buildout_frontier.csv") if int(row["year"]) == 2060 and row["scenario"] == "policy_supported_effort"]
    parts.extend(panel("A", "Addressable product-market value", 40, 120, 620, 330))
    rows = [(row["product"], f(row["gross_market_value_busd_per_year"]), COLORS["thermochemical"]) for row in sorted(market, key=lambda r: f(r["gross_market_value_busd_per_year"]), reverse=True)[:8]]
    parts.extend(bar_chart(rows, 65, 165, 560, 245, ""))
    parts.extend(panel("B", "2060 factory count by category", 700, 120, 640, 330))
    rows2 = [(row["category_label"], f(row["capture_factory_count"]), COLORS["storage"] if row["category"] == "geological_storage" else COLORS["mineralization"] if row["category"] == "mineral_products" else COLORS["thermochemical"]) for row in factories]
    parts.extend(bar_chart(rows2, 725, 165, 570, 245, ""))
    parts.extend(panel("C", "Durable target frontier", 40, 490, 1300, 300))
    feasible = [row for row in frontier if int(row["success"]) == 1]
    x0, y0, w, h = 115, 565, 1080, 160
    max_target = max([f(row["target_durable_mtco2_per_year"]) for row in frontier] + [1000.0])
    max_profit = max([f(row["profit_busd_per_year"]) for row in feasible] + [1.0])
    parts.append(line(x0, y0 + h, x0 + w, y0 + h, "#9aa6aa", 1))
    parts.append(line(x0, y0, x0, y0 + h, "#9aa6aa", 1))
    for row in feasible:
        tx = x0 + f(row["target_durable_mtco2_per_year"]) / max_target * w
        py = y0 + h - f(row["profit_busd_per_year"]) / max_profit * h
        parts.append(circle(tx, py, 6, COLORS["pos"]))
    parts.append(text(x0 + w / 2, y0 + h + 32, "Durable target (MtCO2/yr)", 11, 600, "middle", COLORS["muted"]))
    parts.append(text(x0 + 20, y0 - 16, "Profit frontier", 11, 600, "start", COLORS["muted"]))
    parts.append(text(1020, 600, "1 Gt durable target is infeasible in screened network", 14, 700, "middle", COLORS["neg"]))
    save("figure4_market_vs_neutrality.svg", parts)


def figure7() -> None:
    parts = svg_start(
        "Figure 5. Policy exit and disruption reshape the portfolio",
        "A resilient CO2 strategy is not the same as the highest-margin strategy.",
    )
    stress = [row for row in read_csv(STRESS / "market_stress_summary.csv") if int(row["year"]) == 2060 and row["pathway"] == "all"]
    robust = [row for row in read_csv(FRONTIER / "robust_portfolio_scores.csv") if int(row["year"]) == 2060 and row["pathway"] == "all"]
    eor = [row for row in read_csv(STRESS / "eor_oil_price_sensitivity.csv") if int(row["year"]) == 2060 and row["scenario"] == "policy_supported_effort"]
    parts.extend(panel("A", "Profit under shock cases", 40, 120, 760, 380))
    scenarios = ["policy_supported_effort", "policy_exit_green_premium", "commodity_only_no_support", "war_energy_security_shock", "earthquake_pipeline_disruption", "pandemic_demand_slump", "compound_stress_no_support"]
    cats = ["geological_storage", "mineral_products", "synthetic_fuels", "chemicals"]
    lookup = {(row["scenario"], row["category"]): f(row["profit_busd_per_year"]) for row in stress}
    x0, y0, cw, ch = 285, 175, 110, 37
    for j, cat in enumerate(cats):
        parts.append(text(x0 + j * cw + cw / 2, 158, cat.split("_")[0], 9, 700, "middle", COLORS["muted"]))
    for i, scenario in enumerate(scenarios):
        parts.append(text(70, y0 + i * ch + 23, scenario.replace("_", " ")[:25], 9, 600))
        for j, cat in enumerate(cats):
            val = lookup.get((scenario, cat), 0.0)
            parts.append(rect(x0 + j * cw, y0 + i * ch, cw - 3, ch - 3, color_for_margin(val, -50, 50), "#ffffff", 0.4, 2))
            parts.append(text(x0 + j * cw + cw / 2, y0 + i * ch + 23, f"{val:.1f}", 9, 700, "middle"))
    parts.extend(panel("B", "Robust portfolio roles", 840, 120, 500, 380))
    for i, row in enumerate(sorted(robust, key=lambda r: f(r["expected_profit_busd_per_year"]), reverse=True)):
        parts.append(rect(870, 175 + i * 48, 20, 20, COLORS["pos"] if f(row["expected_profit_busd_per_year"]) > 0 else COLORS["wait"], "none", 1, 3))
        parts.append(text(900, 190 + i * 48, f"{row['category']}  EV {f(row['expected_profit_busd_per_year']):.1f} BUSD/yr", 11, 700))
        parts.append(text(900, 207 + i * 48, row["portfolio_role"], 9, 400, "start", COLORS["muted"]))
    parts.extend(panel("C", "EOR oil-price sensitivity outside durable accounting", 40, 540, 1300, 260))
    rows = [(f"${f(row['oil_price_usd_per_bbl']):.0f}/bbl", f(row["profit_busd_per_year"]), "#8a6b3f") for row in eor]
    parts.extend(bar_chart(rows, 130, 600, 1050, 130, ""))
    parts.append(text(690, 770, "Oilfield-constrained EOR receives no durable-removal credit in conservative accounting.", 15, 700, "middle", COLORS["muted"]))
    save("figure5_policy_exit_resilience.svg", parts)


def figure8() -> None:
    parts = svg_start(
        "Figure 6. Spatial network, route portfolio, stress, and evidence quality",
        "A decision-grade composite links where CO2 moves, which routes scale, what survives pressure, and how strong the evidence is.",
        height=1080,
    )
    frontier_all = read_csv(FRONTIER / "buildout_frontier.csv")
    frontier = [row for row in frontier_all if int(row["year"]) == 2060 and row["scenario"] == "policy_supported_effort"]
    alloc_all = read_csv(FRONTIER / "frontier_top_allocations.csv")
    alloc2060 = [
        row
        for row in alloc_all
        if int(row["year"]) == 2060
        and row["scenario"] == "policy_supported_effort"
        and row["frontier_target_label"] == "max_profit"
    ]
    mc = read_csv(OPT / "uncertainty_positive_probability.csv")
    selected_labels = ["max_profit", "durable_150_mt", "durable_250_mt", "durable_500_mt", "durable_750_mt", "durable_1000_mt"]
    by_label = {row["frontier_target_label"]: row for row in frontier}
    categories = ["geological_storage", "mineral_products", "synthetic_fuels", "chemicals"]
    category_labels = {
        "geological_storage": "storage",
        "mineral_products": "minerals",
        "synthetic_fuels": "fuels",
        "chemicals": "chemicals",
    }

    city2060 = [row for row in read_csv(CITY / "city_archetypes_by_year.csv") if int(row["year"]) == 2060]
    parts.extend(panel("A", "Spatial network: heatmap + top source-destination routes", 40, 120, 650, 430))
    parts.extend(draw_margin_heatmap(62, 165, 600, 335, city2060, False))
    parts.extend(draw_route_network(70, 174, 584, 315, alloc2060))
    route_mt = sum(f(row["allocated_mtco2_per_year"]) for row in alloc2060)
    durable = sum(f(row["allocated_mtco2_per_year"]) for row in alloc2060 if int(row["durable_flag"]) == 1)
    parts.append(text(88, 528, f"{len(alloc2060)} links; {route_mt:.0f} MtCO2/yr managed; {durable:.0f} MtCO2/yr durable", 10, 800, "start", COLORS["ink"]))
    lx, ly = 420, 520
    for i, cat in enumerate(categories):
        parts.append(line_o(lx + i * 62, ly, lx + i * 62 + 30, ly, category_color(cat), 4, 0.8))
        parts.append(text(lx + i * 62 + 15, ly + 18, category_labels[cat], 7, 700, "middle", COLORS["muted"]))

    parts.extend(panel("B", "Route portfolio under durable-target constraints", 730, 120, 610, 430))
    composition: dict[str, dict[str, float]] = {label: {cat: 0.0 for cat in categories} for label in selected_labels}
    for row in alloc_all:
        if int(row["year"]) == 2060 and row["scenario"] == "policy_supported_effort" and row["frontier_target_label"] in composition and row["category"] in categories:
            composition[row["frontier_target_label"]][row["category"]] += f(row["allocated_mtco2_per_year"])
    max_total = max([sum(values.values()) for values in composition.values()] + [1.0])
    target_labels = ["max profit", "150 Mt", "250 Mt", "500 Mt", "750 Mt", "1000 Mt"]
    bx, by, bw, row_h = 850, 176, 350, 38
    for i, label in enumerate(selected_labels):
        row = by_label.get(label, {})
        y = by + i * row_h
        if int(row.get("success", "0")) == 0:
            parts.append(text(770, y + 21, target_labels[i], 9, 800, "start", COLORS["neg"]))
            parts.append(rect(bx, y + 5, bw, 18, "#f4dedd", "#ffffff", 0.5, 2))
            parts.append(text(bx + 16, y + 19, "infeasible in screened network", 8, 800, "start", COLORS["neg"]))
            continue
        parts.append(text(770, y + 21, target_labels[i], 9, 800, "start", COLORS["ink"]))
        x = bx
        total = sum(composition[label].values())
        for cat in categories:
            width = composition[label][cat] / max_total * bw
            if width > 0:
                parts.append(rect(x, y + 5, width, 18, category_color(cat), "#ffffff", 0.5, 2))
                x += width
        parts.append(text(bx + bw + 12, y + 19, f"{total:.0f} Mt; {f(row.get('profit_busd_per_year')):.1f} BUSD", 8, 800, "start", COLORS["ink"]))
    for i, cat in enumerate(categories):
        x = 845 + i * 115
        parts.append(rect(x, 430, 16, 10, category_color(cat), "none", 1, 2))
        parts.append(text(x + 22, 439, category_labels[cat], 8, 700, "start", COLORS["muted"]))

    parts.extend(panel("C", "Policy and pressure: 2060 profit stress matrix", 40, 590, 650, 360))
    stress_rows = [row for row in read_csv(STRESS / "market_stress_summary.csv") if int(row["year"]) == 2060 and row["pathway"] == "all"]
    stress_scenarios = [
        ("policy_supported_effort", "support"),
        ("policy_exit_green_premium", "policy exit"),
        ("commodity_only_no_support", "no support"),
        ("war_energy_security_shock", "war/energy"),
        ("earthquake_pipeline_disruption", "quake/pipe"),
        ("pandemic_demand_slump", "pandemic"),
        ("compound_stress_no_support", "compound"),
    ]
    lookup = {(row["scenario"], row["category"]): f(row["profit_busd_per_year"]) for row in stress_rows}
    sx, sy, cw, ch = 255, 645, 86, 32
    for j, cat in enumerate(categories):
        parts.append(text(sx + j * cw + cw / 2, sy - 14, category_labels[cat], 8, 800, "middle", COLORS["muted"]))
    for i, (scenario, label) in enumerate(stress_scenarios):
        y = sy + i * ch
        parts.append(text(72, y + 20, label, 9, 800, "start", COLORS["ink"] if i == 0 else COLORS["muted"]))
        for j, cat in enumerate(categories):
            val = lookup.get((scenario, cat), 0.0)
            parts.append(rect(sx + j * cw, y, cw - 3, ch - 3, color_for_margin(val, -80, 80), "#ffffff", 0.4, 2))
            parts.append(text(sx + j * cw + cw / 2, y + 21, f"{val:.1f}", 8, 800, "middle", COLORS["ink"]))
    for i, value in enumerate([-80, -20, 0, 20, 80]):
        parts.append(rect(252 + i * 66, 890, 48, 12, color_for_margin(value, -80, 80), "#ffffff", 0.4, 2))
        parts.append(text(276 + i * 66, 918, f"{value}", 8, 600, "middle", COLORS["muted"]))
    parts.append(text(408, 940, "BUSD/yr", 8, 700, "middle", COLORS["muted"]))

    parts.extend(panel("D", "Uncertainty and evidence quality", 730, 590, 610, 360))
    prob_rows = sorted(mc, key=lambda row: f(row["probability_positive"]), reverse=True)[:7]
    ux, uy = 765, 650
    for i, row in enumerate(prob_rows):
        y = uy + i * 25
        p = f(row["probability_positive"]) * 100
        parts.append(text(765, y + 15, PATHWAY_LABELS.get(row["pathway"], row["pathway"]), 8, 700, "start", COLORS["ink"]))
        parts.append(rect(890, y + 4, p / 100 * 145, 13, COLORS["pos"] if p > 70 else COLORS["near"], "none", 1, 2))
        parts.append(text(1042, y + 15, f"{p:.0f}%", 8, 800, "start", COLORS["muted"]))
    manifest_path = ROOT / "output" / "multimodal_evidence_layer" / "modality_manifest.csv"
    manifest = read_csv(manifest_path) if manifest_path.exists() else []
    grade_score = {"A": 1.0, "B": 0.78, "B/C": 0.66, "C": 0.50, "C/D": 0.36, "D": 0.20}
    mx, my = 1105, 650
    parts.append(text(1178, 628, "evidence grade", 9, 800, "middle", COLORS["muted"]))
    for i, row in enumerate(manifest[:7]):
        y = my + i * 25
        score = grade_score.get(row["evidence_grade_now"], 0.45)
        color = f"rgb({int(244 - 165*score)},{int(240 - 92*score)},{int(230 - 105*score)})"
        parts.append(text(mx, y + 15, row["modality"].replace("_", " ")[:18], 8, 700, "start", COLORS["ink"]))
        parts.append(rect(mx + 145, y + 3, 46, 15, color, "#ffffff", 0.4, 2))
        parts.append(text(mx + 168, y + 15, row["evidence_grade_now"], 8, 800, "middle", COLORS["ink"]))
    if (ROOT / "output" / "multimodal_evidence_layer" / "multimodal_evidence_key_findings.md").exists():
        parts.append(text(1038, 868, "multimodal evidence layer generated", 10, 800, "middle", COLORS["pos"]))
    parts.append(text(1038, 904, "left: Monte Carlo confidence; right: modality evidence quality", 8, 700, "middle", COLORS["muted"]))
    save("figure6_optimized_buildout_gap.svg", parts)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for path in OUT.glob("figure*.svg"):
        path.unlink()
    figure1_decision_baseline()
    figure3()
    figure3_timing_switches()
    figure6()
    figure7()
    figure8()
    print(f"Wrote redesigned storyline figures to {OUT}")


if __name__ == "__main__":
    main()
