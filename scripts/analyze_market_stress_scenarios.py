"""Market-scale, policy-exit, shock, and neutrality buildout analysis.

This is a reduced-order post-processor over the China 2030/2060 profitability
matrix. It deliberately separates market/profit potential from durable carbon
neutrality contribution, because fuels and most chemicals recycle carbon rather
than permanently remove it.
"""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
CHINA = ROOT / "output" / "china2060_optimistic_profitability"
OUT = ROOT / "output" / "china2060_market_stress"
FIG_OUT = ROOT / "docs" / "joule_submission" / "figures_composite"


YEARS = [2030, 2035, 2040, 2045, 2050, 2055, 2060]
EPS = 1e-9


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


CATEGORY_BY_PATHWAY = {
    "geological_storage": "geological_storage",
    "mineralization": "mineral_products",
    "co2_h2_ft_saf": "synthetic_fuels",
    "co2_methanol_to_jet_saf": "synthetic_fuels",
    "rwgs_to_co": "chemicals",
    "co2_to_methanol": "chemicals",
    "co2_to_methane": "chemicals",
    "electrolysis_to_formate": "chemicals",
    "electrolysis_to_co": "chemicals",
    "electrolysis_to_ethylene": "chemicals",
    "photoelectrochemical_to_formate": "chemicals",
    "photocatalytic_to_co": "chemicals",
}


def is_eor_row(row: dict[str, str]) -> bool:
    return row.get("sink_type") == "eor_oilfield" or row.get("destination_id", "").startswith("EOR_")


CATEGORY_LABELS = {
    "geological_storage": "Geological storage",
    "mineral_products": "Mineral products",
    "synthetic_fuels": "SAF / synthetic fuels",
    "chemicals": "Chemicals",
    "eor": "CO2-EOR overlay",
}


CATEGORY_COLORS = {
    "geological_storage": "#225f74",
    "mineral_products": "#3d8f63",
    "synthetic_fuels": "#c97836",
    "chemicals": "#7d63a6",
    "eor": "#8a6b3f",
}


PLANT_SIZE_MTCO2_PER_YEAR = {
    "chemicals": 1.0,
    "synthetic_fuels": 1.0,
    "mineral_products": 2.0,
    "geological_storage": 5.0,
    "eor": 3.0,
}


H2_KG_PER_TCO2 = {
    "co2_h2_ft_saf": 165.0,
    "co2_methanol_to_jet_saf": 178.0,
    "co2_to_methanol": 140.0,
    "co2_to_methane": 185.0,
    "rwgs_to_co": 45.0,
}


@dataclass(frozen=True)
class StressScenario:
    name: str
    label: str
    policy_multiplier: float
    price_case: str
    product_price_multiplier: float = 1.0
    market_volume_multiplier: float = 1.0
    source_capacity_multiplier: float = 1.0
    destination_capacity_multiplier: float = 1.0
    transport_cost_multiplier: float = 1.0
    capture_energy_cost_multiplier: float = 1.0
    h2_price_multiplier: float = 1.0
    extra_risk_cost_usd_per_tco2: float = 0.0
    notes: str = ""


STRESS_SCENARIOS = [
    StressScenario(
        name="policy_supported_effort",
        label="Policy-supported effort",
        policy_multiplier=1.0,
        price_case="high",
        notes="China 2030/2060 optimistic effort case with policy-backed high offtake.",
    ),
    StressScenario(
        name="policy_exit_green_premium",
        label="Policy exit, green premium remains",
        policy_multiplier=0.0,
        price_case="high",
        notes="Carbon tax, carbon credit, and removal credit removed; high-product offtake retained.",
    ),
    StressScenario(
        name="commodity_only_no_support",
        label="Commodity only, no support",
        policy_multiplier=0.0,
        price_case="base",
        notes="Policy revenue removed and product prices revert to base commodity case.",
    ),
    StressScenario(
        name="war_energy_security_shock",
        label="War / energy-security shock",
        policy_multiplier=1.0,
        price_case="high",
        product_price_multiplier=1.10,
        market_volume_multiplier=0.90,
        source_capacity_multiplier=0.85,
        destination_capacity_multiplier=0.90,
        transport_cost_multiplier=1.60,
        capture_energy_cost_multiplier=1.35,
        h2_price_multiplier=1.50,
        extra_risk_cost_usd_per_tco2=10.0,
        notes="Energy and hydrogen shock; transport disruption; some product scarcity premium.",
    ),
    StressScenario(
        name="earthquake_pipeline_disruption",
        label="Earthquake / pipeline disruption",
        policy_multiplier=1.0,
        price_case="high",
        market_volume_multiplier=0.95,
        source_capacity_multiplier=0.90,
        destination_capacity_multiplier=0.75,
        transport_cost_multiplier=1.80,
        capture_energy_cost_multiplier=1.10,
        h2_price_multiplier=1.10,
        extra_risk_cost_usd_per_tco2=8.0,
        notes="Network derating and rerouting stress; strongest effect on long-distance storage.",
    ),
    StressScenario(
        name="pandemic_demand_slump",
        label="Pandemic demand slump",
        policy_multiplier=1.0,
        price_case="high",
        product_price_multiplier=0.80,
        market_volume_multiplier=0.65,
        source_capacity_multiplier=0.90,
        destination_capacity_multiplier=0.90,
        transport_cost_multiplier=1.10,
        capture_energy_cost_multiplier=1.10,
        h2_price_multiplier=1.10,
        extra_risk_cost_usd_per_tco2=15.0,
        notes="Product demand, utilization, and construction-finance stress.",
    ),
    StressScenario(
        name="compound_stress_no_support",
        label="Compound stress, no support",
        policy_multiplier=0.0,
        price_case="base",
        product_price_multiplier=0.80,
        market_volume_multiplier=0.60,
        source_capacity_multiplier=0.75,
        destination_capacity_multiplier=0.75,
        transport_cost_multiplier=1.70,
        capture_energy_cost_multiplier=1.40,
        h2_price_multiplier=1.60,
        extra_risk_cost_usd_per_tco2=30.0,
        notes="Simultaneous policy exit, demand slump, energy shock, and infrastructure derating.",
    ),
]


NEUTRALITY_DURABLE_TARGETS_MTCO2 = [500.0, 1000.0, 1500.0]
EOR_OIL_PRICE_USD_PER_BBL = [55.0, 75.0, 95.0, 120.0]


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


def f(value: Any, default: float = 0.0) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(parsed):
        return default
    return parsed


def finite(value: Any, default: float = math.inf) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(parsed):
        return default
    return parsed


def ceil_count(value: float) -> int:
    if value <= EPS:
        return 0
    return int(math.ceil(value - EPS))


def load_capacities() -> tuple[dict[str, float], dict[str, float]]:
    sources = {
        row["source_id"]: f(row["co2_available_mtpa"])
        for row in read_csv(DATA / "real_inputs_top300_with_dac" / "spatial_sources_real.csv")
    }
    destinations = {
        row["destination_id"]: f(row["capacity_mtco2_per_year"])
        for row in read_csv(DATA / "real_inputs_top300_with_dac" / "spatial_destinations_real.csv")
    }
    return sources, destinations


def load_price_table() -> dict[tuple[int, str], dict[str, float]]:
    rows = read_csv(DATA / "product_prices_china2060_optimistic.csv")
    table: dict[tuple[int, str], dict[str, float]] = {}
    for row in rows:
        key = (int(row["year"]), row["product"])
        table[key] = {
            "low": f(row["price_low_usd_per_kg"]),
            "base": f(row["price_base_usd_per_kg"]),
            "high": f(row["price_high_usd_per_kg"]),
            "volume_limit_mt_product": f(row["volume_limit_t_per_year"]) / 1_000_000.0,
        }
    return table


def target_product_price(row: dict[str, str], scenario: StressScenario, prices: dict[tuple[int, str], dict[str, float]]) -> float:
    product = row["product"]
    if product == "none":
        return 0.0
    year = int(row["year"])
    price_row = prices.get((year, product), {})
    target = price_row.get(scenario.price_case, f(row["product_price_usd_per_kg"]))
    return target * scenario.product_price_multiplier


def adjusted_margin(row: dict[str, str], scenario: StressScenario, prices: dict[tuple[int, str], dict[str, float]]) -> float:
    pathway = row["pathway"]
    h2_delta = H2_KG_PER_TCO2.get(pathway, 0.0) * f(row["h2_price_usd_per_kg"]) * (scenario.h2_price_multiplier - 1.0)
    product_delta = (
        target_product_price(row, scenario, prices) - f(row["product_price_usd_per_kg"])
    ) * f(row["marketable_product_kg_per_tco2"])
    policy_delta = (scenario.policy_multiplier - 1.0) * f(row["policy_revenue_usd_per_tco2"])
    transport_delta = -f(row["transport_cost_usd_per_tco2"]) * (scenario.transport_cost_multiplier - 1.0)
    capture_delta = -f(row["capture_energy_cost_usd_per_tco2"]) * (scenario.capture_energy_cost_multiplier - 1.0)
    risk_delta = -scenario.extra_risk_cost_usd_per_tco2
    return f(row["margin_usd_per_tco2"]) + product_delta + policy_delta + transport_delta + capture_delta - h2_delta + risk_delta


def product_remaining_capacity(
    row: dict[str, str],
    scenario: StressScenario,
    prices: dict[tuple[int, str], dict[str, float]],
    product_remaining_mt: dict[str, float],
) -> float:
    product = row["product"]
    if product == "none":
        return math.inf
    marketable = f(row["marketable_product_kg_per_tco2"])
    if marketable <= EPS:
        return math.inf
    if product not in product_remaining_mt:
        year = int(row["year"])
        volume = prices.get((year, product), {}).get("volume_limit_mt_product", math.inf)
        product_remaining_mt[product] = volume * scenario.market_volume_multiplier
    return product_remaining_mt[product] * 1000.0 / marketable


def decrement_product_capacity(row: dict[str, str], co2_mt: float, product_remaining_mt: dict[str, float]) -> float:
    product = row["product"]
    marketable = f(row["marketable_product_kg_per_tco2"])
    product_mt = co2_mt * marketable / 1000.0
    if product != "none" and product in product_remaining_mt:
        product_remaining_mt[product] = max(0.0, product_remaining_mt[product] - product_mt)
    return product_mt


def empty_summary(year: int, scenario: StressScenario, category: str, pathway: str = "all") -> dict[str, Any]:
    return {
        "year": year,
        "scenario": scenario.name,
        "scenario_label": scenario.label,
        "category": category,
        "category_label": CATEGORY_LABELS.get(category, category),
        "pathway": pathway,
        "pathway_label": PATHWAY_LABELS.get(pathway, "All pathways" if pathway == "all" else pathway),
        "allocated_mtco2_per_year": 0.0,
        "durable_allocated_mtco2_per_year": 0.0,
        "product_mt_per_year": 0.0,
        "product_market_revenue_busd_per_year": 0.0,
        "policy_revenue_busd_per_year": 0.0,
        "profit_busd_per_year": 0.0,
        "weighted_margin_usd_per_tco2": 0.0,
        "capture_factory_count": 0,
        "source_count": 0,
        "destination_count": 0,
    }


def add_allocation(
    summary: dict[str, Any],
    row: dict[str, str],
    co2_mt: float,
    margin: float,
    target_price: float,
    policy_multiplier: float,
    product_mt: float,
) -> None:
    category = summary["category"]
    summary["allocated_mtco2_per_year"] += co2_mt
    if category in {"geological_storage", "mineral_products"}:
        summary["durable_allocated_mtco2_per_year"] += co2_mt
    summary["product_mt_per_year"] += product_mt
    summary["product_market_revenue_busd_per_year"] += target_price * product_mt
    summary["policy_revenue_busd_per_year"] += policy_multiplier * f(row["policy_revenue_usd_per_tco2"]) * co2_mt / 1000.0
    summary["profit_busd_per_year"] += margin * co2_mt / 1000.0
    summary.setdefault("_margin_weighted_sum", 0.0)
    summary.setdefault("_sources", set())
    summary.setdefault("_destinations", set())
    summary["_margin_weighted_sum"] += margin * co2_mt
    summary["_sources"].add(row["source_id"])
    summary["_destinations"].add(row["destination_id"])


def finalize_summary(row: dict[str, Any]) -> dict[str, Any]:
    allocated = float(row["allocated_mtco2_per_year"])
    if allocated > EPS:
        row["weighted_margin_usd_per_tco2"] = row.pop("_margin_weighted_sum", 0.0) / allocated
    else:
        row.pop("_margin_weighted_sum", None)
    row["capture_factory_count"] = ceil_count(
        allocated / PLANT_SIZE_MTCO2_PER_YEAR.get(row["category"], 1.0)
    )
    sources = row.pop("_sources", set())
    destinations = row.pop("_destinations", set())
    row["source_count"] = len(sources)
    row["destination_count"] = len(destinations)
    return row


def allocate_year(
    year: int,
    scenario: StressScenario,
    records: list[dict[str, str]],
    source_caps: dict[str, float],
    dest_caps: dict[str, float],
    prices: dict[tuple[int, str], dict[str, float]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    source_remaining = {
        key: value * scenario.source_capacity_multiplier for key, value in source_caps.items()
    }
    dest_remaining = {
        key: value * scenario.destination_capacity_multiplier for key, value in dest_caps.items()
    }
    product_remaining_mt: dict[str, float] = {}
    transformed = []
    for row in records:
        if is_eor_row(row):
            continue
        margin = adjusted_margin(row, scenario, prices)
        if margin <= 0.0:
            continue
        transformed.append((margin, row))
    transformed.sort(key=lambda item: item[0], reverse=True)

    summaries: dict[tuple[str, str], dict[str, Any]] = {}
    allocations: list[dict[str, Any]] = []

    for margin, row in transformed:
        category = CATEGORY_BY_PATHWAY.get(row["pathway"], "other")
        source_id = row["source_id"]
        dest_id = row["destination_id"]
        candidate_cap = f(row["deployable_mtco2_per_year"])
        product_cap = product_remaining_capacity(row, scenario, prices, product_remaining_mt)
        cap = min(
            candidate_cap,
            source_remaining.get(source_id, 0.0),
            dest_remaining.get(dest_id, 0.0),
            product_cap,
        )
        if cap <= EPS:
            continue
        source_remaining[source_id] = max(0.0, source_remaining.get(source_id, 0.0) - cap)
        dest_remaining[dest_id] = max(0.0, dest_remaining.get(dest_id, 0.0) - cap)
        product_mt = decrement_product_capacity(row, cap, product_remaining_mt)
        target_price = target_product_price(row, scenario, prices)

        for key in [(category, "all"), (category, row["pathway"])]:
            if key not in summaries:
                summaries[key] = empty_summary(year, scenario, key[0], key[1])
            add_allocation(summaries[key], row, cap, margin, target_price, scenario.policy_multiplier, product_mt)

        allocations.append(
            {
                "year": year,
                "scenario": scenario.name,
                "category": category,
                "pathway": row["pathway"],
                "source_id": source_id,
                "destination_id": dest_id,
                "city_id": row["city_id"],
                "city_name": row["city_name"],
                "allocated_mtco2_per_year": cap,
                "product_mt_per_year": product_mt,
                "adjusted_margin_usd_per_tco2": margin,
                "profit_busd_per_year": margin * cap / 1000.0,
                "target_product_price_usd_per_kg": target_price,
                "base_margin_usd_per_tco2": row["margin_usd_per_tco2"],
                "base_policy_revenue_usd_per_tco2": row["policy_revenue_usd_per_tco2"],
                "transport_cost_usd_per_tco2": row["transport_cost_usd_per_tco2"],
                "capture_energy_cost_usd_per_tco2": row["capture_energy_cost_usd_per_tco2"],
            }
        )

    return [finalize_summary(row) for row in summaries.values()], allocations


def allocate_eor_overlay(
    year: int,
    scenario: StressScenario,
    records: list[dict[str, str]],
    source_caps: dict[str, float],
    dest_caps: dict[str, float],
    prices: dict[tuple[int, str], dict[str, float]],
    oil_price_usd_per_bbl: float = 75.0,
    oil_price_case: str = "central_75_usd_bbl",
) -> dict[str, Any]:
    lifting_cost_usd_per_bbl = 28.0
    netback_share = 0.45
    bbl_per_tco2_injected = 2.3
    eor_storage_capacity_fraction = 1.0
    oil_netback_usd_per_tco2 = (
        max(0.0, oil_price_usd_per_bbl - lifting_cost_usd_per_bbl)
        * netback_share
        * bbl_per_tco2_injected
    )
    oil_combustion_debit_tco2e_per_tco2 = 0.43 * bbl_per_tco2_injected

    storage_rows = [
        row
        for row in records
        if row["pathway"] == "geological_storage"
        and is_eor_row(row)
    ]
    source_remaining = {
        key: value * scenario.source_capacity_multiplier for key, value in source_caps.items()
    }
    dest_remaining = {
        key: value * scenario.destination_capacity_multiplier * eor_storage_capacity_fraction
        for key, value in dest_caps.items()
    }
    transformed = []
    for row in storage_rows:
        # EOR is reported as a private oil-production overlay, not a durable
        # removal route. Remove any storage/durable policy revenue inherited
        # from the geological-storage candidate before adding oil netback.
        inherited_policy_revenue = scenario.policy_multiplier * f(row["policy_revenue_usd_per_tco2"])
        margin = adjusted_margin(row, scenario, prices) - inherited_policy_revenue + oil_netback_usd_per_tco2
        if margin > 0:
            transformed.append((margin, row))
    transformed.sort(key=lambda item: item[0], reverse=True)

    summary = empty_summary(year, scenario, "eor", "co2_eor_overlay")
    summary["pathway_label"] = "CO2-EOR overlay"
    summary["oil_price_usd_per_bbl"] = oil_price_usd_per_bbl
    summary["oil_price_case"] = oil_price_case
    summary["oil_netback_usd_per_tco2"] = oil_netback_usd_per_tco2
    summary["oil_combustion_debit_tco2e_per_tco2"] = oil_combustion_debit_tco2e_per_tco2
    summary["net_durable_storage_after_oil_debit_tco2e_per_tco2"] = 1.0 - oil_combustion_debit_tco2e_per_tco2
    summary["eor_storage_capacity_fraction"] = eor_storage_capacity_fraction
    summary["oil_mmbbl_per_year"] = 0.0
    summary["notes"] = (
        "Reduced-order overlay only on EOR-positive oilfield destinations; non-oilfield "
        "cities are excluded and the result is not additive with saline storage capacity."
    )

    for margin, row in transformed:
        cap = min(
            f(row["deployable_mtco2_per_year"]),
            source_remaining.get(row["source_id"], 0.0),
            dest_remaining.get(row["destination_id"], 0.0),
        )
        if cap <= EPS:
            continue
        source_remaining[row["source_id"]] -= cap
        dest_remaining[row["destination_id"]] -= cap
        add_allocation(summary, row, cap, margin, 0.0, 0.0, 0.0)
        summary["product_market_revenue_busd_per_year"] += oil_netback_usd_per_tco2 * cap / 1000.0
        summary["oil_mmbbl_per_year"] += cap * bbl_per_tco2_injected

    return finalize_summary(summary)


def eor_sensitivity_rows(
    records_by_year: dict[int, list[dict[str, str]]],
    source_caps: dict[str, float],
    dest_caps: dict[str, float],
    prices: dict[tuple[int, str], dict[str, float]],
) -> list[dict[str, Any]]:
    scenario_names = {
        "policy_supported_effort",
        "policy_exit_green_premium",
        "commodity_only_no_support",
        "compound_stress_no_support",
    }
    scenarios = [scenario for scenario in STRESS_SCENARIOS if scenario.name in scenario_names]
    rows: list[dict[str, Any]] = []
    for year in YEARS:
        records = records_by_year[year]
        for scenario in scenarios:
            for oil_price in EOR_OIL_PRICE_USD_PER_BBL:
                rows.append(
                    allocate_eor_overlay(
                        year,
                        scenario,
                        records,
                        source_caps,
                        dest_caps,
                        prices,
                        oil_price_usd_per_bbl=oil_price,
                        oil_price_case=f"{oil_price:.0f}_usd_bbl",
                    )
                )
    return rows


def market_scale_rows(
    records_by_year: dict[int, list[dict[str, str]]],
    prices: dict[tuple[int, str], dict[str, float]],
) -> list[dict[str, Any]]:
    representative_yield: dict[tuple[int, str], float] = {}
    for year, records in records_by_year.items():
        by_product: dict[str, list[float]] = {}
        for row in records:
            product = row["product"]
            if product == "none":
                continue
            by_product.setdefault(product, []).append(f(row["marketable_product_kg_per_tco2"]))
        for product, values in by_product.items():
            positive = [value for value in values if value > EPS]
            representative_yield[(year, product)] = sorted(positive)[len(positive) // 2] if positive else 0.0

    rows: list[dict[str, Any]] = []
    for (year, product), price_row in sorted(prices.items()):
        if product == "none":
            continue
        yield_kg = representative_yield.get((year, product), 0.0)
        required_co2_mt = (
            price_row["volume_limit_mt_product"] * 1000.0 / yield_kg if yield_kg > EPS else math.inf
        )
        for case in ["base", "high"]:
            price = price_row[case]
            rows.append(
                {
                    "year": year,
                    "product": product,
                    "price_case": case,
                    "price_usd_per_kg": price,
                    "volume_limit_mt_product_per_year": price_row["volume_limit_mt_product"],
                    "gross_market_value_busd_per_year": price * price_row["volume_limit_mt_product"],
                    "representative_yield_kg_product_per_tco2": yield_kg,
                    "co2_required_if_full_market_mtco2_per_year": required_co2_mt,
                }
            )
    return rows


def neutrality_rows(summary_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows_2060 = [
        row
        for row in summary_rows
        if int(row["year"]) == 2060
        and row["pathway"] == "all"
        and row["scenario"] in {"policy_supported_effort", "commodity_only_no_support"}
    ]
    out: list[dict[str, Any]] = []
    for scenario_name in ["policy_supported_effort", "commodity_only_no_support"]:
        scenario_rows = [row for row in rows_2060 if row["scenario"] == scenario_name]
        all_capacity = sum(float(row["allocated_mtco2_per_year"]) for row in scenario_rows)
        durable_capacity = sum(float(row["durable_allocated_mtco2_per_year"]) for row in scenario_rows)
        all_profit = sum(float(row["profit_busd_per_year"]) for row in scenario_rows)
        durable_profit = sum(
            float(row["profit_busd_per_year"])
            for row in scenario_rows
            if row["category"] in {"geological_storage", "mineral_products"}
        )
        all_factories = sum(int(row["capture_factory_count"]) for row in scenario_rows)
        durable_factories = sum(
            int(row["capture_factory_count"])
            for row in scenario_rows
            if row["category"] in {"geological_storage", "mineral_products"}
        )
        for target in NEUTRALITY_DURABLE_TARGETS_MTCO2:
            out.append(
                {
                    "year": 2060,
                    "scenario": scenario_name,
                    "target_durable_mtco2_per_year": target,
                    "profitable_durable_capacity_mtco2_per_year": durable_capacity,
                    "durable_gap_mtco2_per_year": max(0.0, target - durable_capacity),
                    "durable_capture_factory_count": durable_factories,
                    "durable_profit_busd_per_year": durable_profit,
                    "all_profitable_managed_co2_mtco2_per_year": all_capacity,
                    "all_capture_factory_count": all_factories,
                    "all_profit_busd_per_year": all_profit,
                    "interpretation": "durable_target_met" if durable_capacity >= target else "durable_policy_or_storage_gap",
                }
            )
    return out


def factory_rows(summary_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "year": row["year"],
            "scenario": row["scenario"],
            "category": row["category"],
            "category_label": row["category_label"],
            "allocated_mtco2_per_year": row["allocated_mtco2_per_year"],
            "durable_allocated_mtco2_per_year": row["durable_allocated_mtco2_per_year"],
            "profit_busd_per_year": row["profit_busd_per_year"],
            "capture_factory_count": row["capture_factory_count"],
            "plant_size_mtco2_per_year": PLANT_SIZE_MTCO2_PER_YEAR.get(row["category"], 1.0),
            "source_count": row["source_count"],
            "destination_count": row["destination_count"],
        }
        for row in summary_rows
        if int(row["year"]) == 2060 and row["pathway"] == "all"
    ]


def shock_definition_rows() -> list[dict[str, Any]]:
    return [
        {
            "scenario": scenario.name,
            "label": scenario.label,
            "policy_multiplier": scenario.policy_multiplier,
            "price_case": scenario.price_case,
            "product_price_multiplier": scenario.product_price_multiplier,
            "market_volume_multiplier": scenario.market_volume_multiplier,
            "source_capacity_multiplier": scenario.source_capacity_multiplier,
            "destination_capacity_multiplier": scenario.destination_capacity_multiplier,
            "transport_cost_multiplier": scenario.transport_cost_multiplier,
            "capture_energy_cost_multiplier": scenario.capture_energy_cost_multiplier,
            "h2_price_multiplier": scenario.h2_price_multiplier,
            "extra_risk_cost_usd_per_tco2": scenario.extra_risk_cost_usd_per_tco2,
            "notes": scenario.notes,
        }
        for scenario in STRESS_SCENARIOS
    ]


def esc(text: Any) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def svg_text(x: float, y: float, text: Any, size: int = 12, weight: int = 400, anchor: str = "start", color: str = "#202426") -> str:
    return f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" font-weight="{weight}" text-anchor="{anchor}" fill="{color}">{esc(text)}</text>'


def rect(x: float, y: float, w: float, h: float, fill: str, stroke: str = "none", sw: float = 1.0) -> str:
    return f'<rect x="{x:.1f}" y="{y:.1f}" width="{max(0, w):.1f}" height="{max(0, h):.1f}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>'


def line(x1: float, y1: float, x2: float, y2: float, stroke: str = "#dfe6e8", sw: float = 1.0) -> str:
    return f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{stroke}" stroke-width="{sw}"/>'


def panel_label(letter: str, title: str, x: float, y: float) -> list[str]:
    return [
        svg_text(x, y, letter, 16, 700),
        svg_text(x + 24, y, title, 14, 700),
    ]


def stacked_bar_panel(rows: list[dict[str, Any]], scenario: str, x: float, y: float, w: float, h: float) -> list[str]:
    parts = panel_label("A", "Profitable deployable CO2 by market category", x, y)
    data = [row for row in rows if row["scenario"] == scenario and row["pathway"] == "all"]
    by_year: dict[int, dict[str, float]] = {year: {} for year in YEARS}
    for row in data:
        by_year[int(row["year"])][row["category"]] = float(row["allocated_mtco2_per_year"])
    max_total = max(sum(values.values()) for values in by_year.values()) or 1.0
    plot_x, plot_y = x + 42, y + 34
    plot_w, plot_h = w - 70, h - 70
    parts.append(line(plot_x, plot_y + plot_h, plot_x + plot_w, plot_y + plot_h, "#9aa6aa", 1.2))
    parts.append(line(plot_x, plot_y, plot_x, plot_y + plot_h, "#9aa6aa", 1.2))
    bar_gap = 14
    bar_w = (plot_w - bar_gap * (len(YEARS) - 1)) / len(YEARS)
    order = ["geological_storage", "mineral_products", "synthetic_fuels", "chemicals"]
    for i, year in enumerate(YEARS):
        bx = plot_x + i * (bar_w + bar_gap)
        bottom = plot_y + plot_h
        for category in order:
            value = by_year[year].get(category, 0.0)
            bh = value / max_total * plot_h
            bottom -= bh
            parts.append(rect(bx, bottom, bar_w, bh, CATEGORY_COLORS[category]))
        parts.append(svg_text(bx + bar_w / 2, plot_y + plot_h + 18, year, 10, 400, "middle", "#5f6b70"))
    for tick in [0.0, 0.5, 1.0]:
        ty = plot_y + plot_h - tick * plot_h
        parts.append(line(plot_x - 4, ty, plot_x + plot_w, ty, "#edf1f2", 1))
        parts.append(svg_text(plot_x - 8, ty + 4, f"{max_total * tick:.0f}", 10, 400, "end", "#5f6b70"))
    parts.append(svg_text(plot_x - 36, plot_y + 10, "MtCO2/yr", 10, 600, "start", "#5f6b70"))
    lx = plot_x + plot_w - 225
    ly = plot_y + 4
    for i, category in enumerate(order):
        parts.append(rect(lx, ly + i * 18, 10, 10, CATEGORY_COLORS[category]))
        parts.append(svg_text(lx + 16, ly + 9 + i * 18, CATEGORY_LABELS[category], 10, 400, "start", "#5f6b70"))
    return parts


def stress_heatmap_panel(rows: list[dict[str, Any]], x: float, y: float, w: float, h: float) -> list[str]:
    parts = panel_label("B", "2060 profit pool under policy exit and shocks", x, y)
    scenarios = [scenario.name for scenario in STRESS_SCENARIOS]
    labels = [scenario.label for scenario in STRESS_SCENARIOS]
    categories = ["geological_storage", "mineral_products", "synthetic_fuels", "chemicals"]
    lookup = {
        (row["scenario"], row["category"]): float(row["profit_busd_per_year"])
        for row in rows
        if int(row["year"]) == 2060 and row["pathway"] == "all"
    }
    values = [lookup.get((scenario, category), 0.0) for scenario in scenarios for category in categories]
    vmax = max([abs(value) for value in values] + [1.0])
    cell_w = (w - 180) / len(categories)
    cell_h = (h - 70) / len(scenarios)
    start_x, start_y = x + 150, y + 38
    for j, category in enumerate(categories):
        parts.append(svg_text(start_x + j * cell_w + cell_w / 2, y + 24, CATEGORY_LABELS[category].split()[0], 10, 600, "middle", "#5f6b70"))
    for i, scenario in enumerate(scenarios):
        parts.append(svg_text(x + 5, start_y + i * cell_h + cell_h * 0.62, labels[i], 9, 400, "start", "#5f6b70"))
        for j, category in enumerate(categories):
            value = lookup.get((scenario, category), 0.0)
            if value >= 0:
                intensity = min(1.0, value / vmax)
                color = f"rgb({int(240 - 195 * intensity)},{int(248 - 95 * intensity)},{int(244 - 118 * intensity)})"
            else:
                intensity = min(1.0, abs(value) / vmax)
                color = f"rgb({int(250 - 80 * intensity)},{int(232 - 120 * intensity)},{int(224 - 115 * intensity)})"
            parts.append(rect(start_x + j * cell_w, start_y + i * cell_h, cell_w - 2, cell_h - 2, color, "#ffffff", 0.5))
            parts.append(svg_text(start_x + j * cell_w + cell_w / 2, start_y + i * cell_h + cell_h * 0.62, f"{value:.1f}", 10, 600, "middle"))
    parts.append(svg_text(start_x, y + h - 8, "Billion USD/yr; zero means no profitable selected capacity after stress filters.", 10, 400, "start", "#5f6b70"))
    return parts


def first_year_panel(rows: list[dict[str, Any]], x: float, y: float, w: float, h: float) -> list[str]:
    parts = panel_label("C", "First profitable year with and without support", x, y)
    scenarios = ["policy_supported_effort", "commodity_only_no_support"]
    labels = ["Supported", "No support"]
    pathways = ["mineralization", "geological_storage", "co2_h2_ft_saf", "rwgs_to_co", "electrolysis_to_formate", "co2_to_methanol", "co2_methanol_to_jet_saf"]
    lookup: dict[tuple[str, str], int | None] = {}
    for scenario in scenarios:
        for pathway in pathways:
            years = [
                int(row["year"])
                for row in rows
                if row["scenario"] == scenario
                and row["pathway"] == pathway
                and float(row["allocated_mtco2_per_year"]) > EPS
            ]
            lookup[(scenario, pathway)] = min(years) if years else None
    plot_x, plot_y = x + 128, y + 34
    row_h = (h - 58) / len(pathways)
    col_w = 94
    for j, label in enumerate(labels):
        parts.append(svg_text(plot_x + j * col_w + col_w / 2, y + 24, label, 11, 700, "middle", "#5f6b70"))
    for i, pathway in enumerate(pathways):
        py = plot_y + i * row_h
        parts.append(svg_text(x + 5, py + row_h * 0.60, PATHWAY_LABELS[pathway], 10, 500, "start"))
        for j, scenario in enumerate(scenarios):
            first = lookup[(scenario, pathway)]
            fill = "#e8f0f4" if first is None else "#2f8f83"
            if first and first >= 2050:
                fill = "#b8a23a"
            parts.append(rect(plot_x + j * col_w, py + 2, col_w - 4, row_h - 4, fill, "#ffffff", 0.5))
            parts.append(svg_text(plot_x + j * col_w + col_w / 2, py + row_h * 0.62, first or "none", 10, 700, "middle", "#202426"))
    return parts


def neutrality_panel(rows: list[dict[str, Any]], x: float, y: float, w: float, h: float) -> list[str]:
    parts = panel_label("D", "2060 carbon-neutral buildout stress test", x, y)
    supported = [row for row in rows if row["scenario"] == "policy_supported_effort"]
    no_support = [row for row in rows if row["scenario"] == "commodity_only_no_support"]
    plot_x, plot_y = x + 58, y + 42
    plot_w, plot_h = w - 86, h - 82
    vmax = max([float(row["target_durable_mtco2_per_year"]) for row in rows] + [1.0])
    bar_h = 18
    groups = [("Supported", supported, "#225f74"), ("No support", no_support, "#b94d5a")]
    for gi, (label, group, color) in enumerate(groups):
        parts.append(svg_text(plot_x, plot_y + gi * 82 - 10, label, 11, 700, "start"))
        for i, row in enumerate(group):
            yy = plot_y + gi * 82 + i * 22
            target = float(row["target_durable_mtco2_per_year"])
            durable = float(row["profitable_durable_capacity_mtco2_per_year"])
            parts.append(rect(plot_x + 70, yy, plot_w * target / vmax, bar_h, "#e8edf0"))
            parts.append(rect(plot_x + 70, yy, plot_w * min(durable, target) / vmax, bar_h, color))
            parts.append(svg_text(plot_x, yy + 13, f"{target:.0f} Mt", 10, 500, "start", "#5f6b70"))
            gap = float(row["durable_gap_mtco2_per_year"])
            parts.append(svg_text(plot_x + 75 + plot_w * target / vmax, yy + 13, f"gap {gap:.0f}", 10, 500, "start", "#5f6b70"))
    parts.append(svg_text(plot_x, y + h - 12, "Bar fill = profitable durable CO2 capacity; target bars = 0.5/1.0/1.5 GtCO2/yr.", 10, 400, "start", "#5f6b70"))
    return parts


def eor_panel(rows: list[dict[str, Any]], x: float, y: float, w: float, h: float) -> list[str]:
    parts = panel_label("E", "CO2-EOR oil-price sensitivity", x, y)
    scenarios = ["policy_supported_effort", "commodity_only_no_support", "compound_stress_no_support"]
    labels = ["Supported", "No support", "Compound"]
    data = [
        row
        for row in rows
        if int(row["year"]) == 2060 and row["scenario"] in scenarios
    ]
    max_profit = max([float(row["profit_busd_per_year"]) for row in data] + [1.0])
    plot_x, plot_y = x + 58, y + 36
    plot_w, plot_h = w - 90, h - 78
    group_w = plot_w / len(EOR_OIL_PRICE_USD_PER_BBL)
    bar_w = min(24.0, (group_w - 16) / len(scenarios))
    colors = ["#8a6b3f", "#c97836", "#b94d5a"]
    lookup = {
        (row["oil_price_usd_per_bbl"], row["scenario"]): float(row["profit_busd_per_year"])
        for row in data
    }
    for i, oil_price in enumerate(EOR_OIL_PRICE_USD_PER_BBL):
        gx = plot_x + i * group_w
        for j, scenario in enumerate(scenarios):
            value = max(0.0, lookup.get((oil_price, scenario), 0.0))
            bh = value / max_profit * plot_h
            bx = gx + 8 + j * (bar_w + 3)
            parts.append(rect(bx, plot_y + plot_h - bh, bar_w, bh, colors[j]))
        parts.append(svg_text(gx + group_w / 2, plot_y + plot_h + 16, f"${oil_price:.0f}", 10, 400, "middle", "#5f6b70"))
    parts.append(line(plot_x, plot_y + plot_h, plot_x + plot_w, plot_y + plot_h, "#9aa6aa", 1))
    for j, label in enumerate(labels):
        parts.append(rect(plot_x + j * 96, y + h - 36, 10, 10, colors[j]))
        parts.append(svg_text(plot_x + 15 + j * 96, y + h - 27, label, 9, 400, "start", "#5f6b70"))
    parts.append(svg_text(plot_x, y + h - 12, "Overlay is not durable neutrality capacity; CSV reports oil-combustion debit.", 10, 400, "start", "#5f6b70"))
    return parts


def render_market_stress_figure(
    summary_rows: list[dict[str, Any]],
    neutrality: list[dict[str, Any]],
    eor_rows: list[dict[str, Any]],
    eor_sensitivity: list[dict[str, Any]],
) -> None:
    FIG_OUT.mkdir(parents=True, exist_ok=True)
    width, height = 1420, 1180
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        "<style>text{font-family:Arial,Helvetica,sans-serif;} .title{font-size:25px;font-weight:700;}</style>",
        rect(0, 0, width, height, "#ffffff"),
        '<text x="40" y="44" class="title">Market size, policy-exit resilience, and carbon-neutral buildout</text>',
        svg_text(40, 68, "Reduced-order post-processing of city-route profitability; durable neutrality counted separately from recycled-carbon products.", 13, 400, "start", "#5f6b70"),
    ]
    parts.extend(stacked_bar_panel(summary_rows, "policy_supported_effort", 40, 100, 650, 330))
    parts.extend(stress_heatmap_panel(summary_rows, 730, 100, 650, 330))
    parts.extend(first_year_panel(summary_rows, 40, 470, 420, 310))
    parts.extend(neutrality_panel(neutrality, 500, 470, 430, 310))
    parts.extend(eor_panel(eor_sensitivity, 970, 470, 380, 310))
    parts.append(svg_text(40, 830, "Key interpretation", 15, 700))
    parts.append(svg_text(40, 856, "1. Commodity-only profitability is much narrower than the policy-supported case; mineralization and selected SAF/CO routes are the main survivors.", 12, 400, "start", "#202426"))
    parts.append(svg_text(40, 878, "2. Shock scenarios change both margins and buildable volume; product-demand shocks mainly hit chemicals/fuels, while network shocks mainly hit storage.", 12, 400, "start", "#202426"))
    parts.append(svg_text(40, 900, "3. EOR is oilfield-constrained and receives no durable-removal credit in the conservative accounting.", 12, 400, "start", "#202426"))
    parts.append("</svg>")
    (FIG_OUT / "figure7_market_stress_composite.svg").write_text("\n".join(parts), encoding="utf-8")


def write_key_findings(
    summary_rows: list[dict[str, Any]],
    neutrality: list[dict[str, Any]],
    market_rows: list[dict[str, Any]],
    eor_rows: list[dict[str, Any]],
) -> None:
    def total_for(year: int, scenario: str, field: str) -> float:
        return sum(
            float(row[field])
            for row in summary_rows
            if int(row["year"]) == year and row["scenario"] == scenario and row["pathway"] == "all"
        )

    market_2060_high = sum(
        float(row["gross_market_value_busd_per_year"])
        for row in market_rows
        if int(row["year"]) == 2060 and row["price_case"] == "high"
    )
    market_2060_base = sum(
        float(row["gross_market_value_busd_per_year"])
        for row in market_rows
        if int(row["year"]) == 2060 and row["price_case"] == "base"
    )
    supported_profit = total_for(2060, "policy_supported_effort", "profit_busd_per_year")
    no_support_profit = total_for(2060, "commodity_only_no_support", "profit_busd_per_year")
    supported_capacity = total_for(2060, "policy_supported_effort", "allocated_mtco2_per_year")
    no_support_capacity = total_for(2060, "commodity_only_no_support", "allocated_mtco2_per_year")
    central_target = next(
        row
        for row in neutrality
        if row["scenario"] == "policy_supported_effort" and float(row["target_durable_mtco2_per_year"]) == 1000.0
    )
    eor_2060 = next(
        row
        for row in eor_rows
        if int(row["year"]) == 2060
        and row["scenario"] == "policy_supported_effort"
        and float(row["oil_price_usd_per_bbl"]) == 75.0
    )
    text = f"""# Market Stress Key Findings

Generated by `scripts/analyze_market_stress_scenarios.py`.

- 2060 addressable product-market value in the optimistic China effort table is {market_2060_base:.1f} billion USD/yr at base commodity prices and {market_2060_high:.1f} billion USD/yr at high policy-backed offtake prices.
- Under the policy-supported effort case, the greedy source-destination-market allocator selects {supported_capacity:.1f} MtCO2/yr of profitable managed CO2 in 2060, with an aggregate profit pool of {supported_profit:.1f} billion USD/yr.
- Under the commodity-only/no-support stress case, profitable managed CO2 falls to {no_support_capacity:.1f} MtCO2/yr and profit to {no_support_profit:.1f} billion USD/yr.
- For a 1.0 GtCO2/yr durable 2060 neutrality target, currently profitable durable capacity reaches {float(central_target['profitable_durable_capacity_mtco2_per_year']):.1f} MtCO2/yr, leaving a modeled gap of {float(central_target['durable_gap_mtco2_per_year']):.1f} MtCO2/yr. This is the storage/mineralization scale-up gap, not a chemicals-market gap.
- The reduced-order CO2-EOR overlay reaches {float(eor_2060['allocated_mtco2_per_year']):.1f} MtCO2/yr, {float(eor_2060['oil_mmbbl_per_year']):.1f} million bbl/yr of incremental oil, and {float(eor_2060['profit_busd_per_year']):.1f} billion USD/yr in 2060 at 75 USD/bbl oil. It is not counted as durable neutrality capacity because the oil-combustion debit is {float(eor_2060['oil_combustion_debit_tco2e_per_tco2']):.2f} tCO2e/tCO2 injected.

Interpretation for the manuscript: a Joule-level claim should not be "all CO2 utilization becomes profitable." The stronger and more defensible claim is that a portfolio becomes bankable only after geography, product-market limits, policy durability, and shock resilience are jointly screened; durable carbon neutrality remains a storage/mineralization buildout challenge even when fuels and chemicals create attractive private profit pools.
"""
    (OUT / "market_stress_key_findings.md").write_text(text, encoding="utf-8")


def main() -> None:
    source_caps, dest_caps = load_capacities()
    prices = load_price_table()
    OUT.mkdir(parents=True, exist_ok=True)
    records_by_year = {
        year: read_csv(CHINA / f"china2060_{year}_profit_detail.csv")
        for year in YEARS
    }

    summary_rows: list[dict[str, Any]] = []
    allocation_rows: list[dict[str, Any]] = []
    eor_rows: list[dict[str, Any]] = []
    for year in YEARS:
        records = records_by_year[year]
        for scenario in STRESS_SCENARIOS:
            summaries, allocations = allocate_year(year, scenario, records, source_caps, dest_caps, prices)
            summary_rows.extend(summaries)
            allocation_rows.extend(allocations[:250])
            eor_rows.append(allocate_eor_overlay(year, scenario, records, source_caps, dest_caps, prices))

    market_rows = market_scale_rows(records_by_year, prices)
    eor_sensitivity = eor_sensitivity_rows(records_by_year, source_caps, dest_caps, prices)
    neutrality = neutrality_rows(summary_rows)
    factories = factory_rows(summary_rows)

    write_csv(OUT / "market_stress_summary.csv", summary_rows)
    write_csv(OUT / "market_stress_top_allocations.csv", allocation_rows)
    write_csv(OUT / "market_scale_by_product.csv", market_rows)
    write_csv(OUT / "neutrality_buildout_summary.csv", neutrality)
    write_csv(OUT / "factory_buildout_by_category_2060.csv", factories)
    write_csv(OUT / "eor_overlay_summary.csv", eor_rows)
    write_csv(OUT / "eor_oil_price_sensitivity.csv", eor_sensitivity)
    write_csv(OUT / "shock_definitions.csv", shock_definition_rows())
    write_key_findings(summary_rows, neutrality, market_rows, eor_rows)
    render_market_stress_figure(summary_rows, neutrality, eor_rows, eor_sensitivity)
    print(f"Wrote market stress analysis to {OUT}")
    print(f"Wrote Figure 7 to {FIG_OUT / 'figure7_market_stress_composite.svg'}")


if __name__ == "__main__":
    main()
