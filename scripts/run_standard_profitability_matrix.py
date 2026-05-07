"""Run standard city-level profitability scenarios with DAC included."""

from __future__ import annotations

import csv
import math
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from co2alloc.cli import _apply_policy_source  # noqa: E402
from co2alloc.hourly import load_hourly_profiles  # noqa: E402
from co2alloc.learning import load_learning_rows  # noqa: E402
from co2alloc.profitability import (  # noqa: E402
    city_profit_recommendations,
    load_profitability_assumptions,
    profit_scan,
)
from co2alloc.realdata import build_real_inputs  # noqa: E402
from co2alloc.scenario import Scenario  # noqa: E402
from co2alloc.spatial import (  # noqa: E402
    Destination,
    generate_spatial_candidates,
    load_destinations,
    load_hubs,
    load_sources,
    load_transport_modes,
)


DATA_DIR = ROOT / "data"
INPUT_DIR = DATA_DIR / "real_inputs_top300_with_dac"
OUTPUT_DIR = ROOT / "output"
SCENARIO_DIR = OUTPUT_DIR / "standard_profitability_matrix"
SOURCE_CALIBRATION = DATA_DIR / "processed" / "co2_sources" / "source_inventory_calibration_ceads_2022.csv"
EXTRA_SOURCES = DATA_DIR / "dac_sources.csv"
PRODUCT_PRICES = DATA_DIR / "product_prices_evidence_upgraded.csv"
RELIABILITY = DATA_DIR / "technology_reliability_evidence_upgraded.csv"


DestinationModifier = Callable[[list[Destination]], list[Destination]]
INCLUDE_ALL_LCA = -1_000_000.0


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


def replace_destination(destination: Destination, **updates: Any) -> Destination:
    values = asdict(destination)
    values.update(updates)
    return Destination(**values)


def identity(destinations: list[Destination]) -> list[Destination]:
    return destinations


def low_green_h2(destinations: list[Destination]) -> list[Destination]:
    return [
        replace_destination(
            destination,
            h2_price_usd_per_kg=1.2,
            h2_emissions_kgco2e_per_kg=0.4,
            electricity_price_usd_per_mwh=min(destination.electricity_price_usd_per_mwh, 28.0),
            grid_emissions_kgco2e_per_mwh=min(destination.grid_emissions_kgco2e_per_mwh, 80.0),
        )
        if destination.sink_type != "provincial_storage"
        else destination
        for destination in destinations
    ]


def ultra_low_power(destinations: list[Destination]) -> list[Destination]:
    return [
        replace_destination(
            destination,
            electricity_price_usd_per_mwh=min(destination.electricity_price_usd_per_mwh, 18.0),
            grid_emissions_kgco2e_per_mwh=min(destination.grid_emissions_kgco2e_per_mwh, 40.0),
        )
        if destination.sink_type != "provincial_storage"
        else destination
        for destination in destinations
    ]


def breakthrough_utilization(destinations: list[Destination]) -> list[Destination]:
    return [
        replace_destination(
            destination,
            h2_price_usd_per_kg=0.65,
            h2_emissions_kgco2e_per_kg=0.15,
            electricity_price_usd_per_mwh=min(destination.electricity_price_usd_per_mwh, 12.0),
            grid_emissions_kgco2e_per_mwh=min(destination.grid_emissions_kgco2e_per_mwh, 25.0),
            electrolyzer_capex_usd_per_kw=min(destination.electrolyzer_capex_usd_per_kw, 250.0),
            electrolyzer_kwh_per_kg_h2=min(destination.electrolyzer_kwh_per_kg_h2, 45.0),
        )
        if destination.sink_type != "provincial_storage"
        else destination
        for destination in destinations
    ]


SCENARIOS: list[dict[str, Any]] = [
    {
        "name": "china_current_2030",
        "year": 2030,
        "target_market": "china",
        "price_case": "base",
        "policy_source": "destination",
        "scenario": Scenario(min_net_avoided_kgco2e_per_tco2=INCLUDE_ALL_LCA),
        "modifier": identity,
        "notes": "Current China policy and base product prices.",
    },
    {
        "name": "china_high_policy_2040",
        "year": 2040,
        "target_market": "china",
        "price_case": "base",
        "policy_source": "cli",
        "scenario": Scenario(carbon_price_usd_per_tco2=120.0, carbon_tax_usd_per_tco2=60.0, durable_removal_credit_usd_per_tco2=120.0, min_net_avoided_kgco2e_per_tco2=INCLUDE_ALL_LCA),
        "modifier": identity,
        "notes": "High domestic carbon policy sensitivity.",
    },
    {
        "name": "low_green_h2_2040",
        "year": 2040,
        "target_market": "china",
        "price_case": "base",
        "policy_source": "cli",
        "scenario": Scenario(carbon_price_usd_per_tco2=80.0, carbon_tax_usd_per_tco2=30.0, durable_removal_credit_usd_per_tco2=80.0, min_net_avoided_kgco2e_per_tco2=INCLUDE_ALL_LCA),
        "modifier": low_green_h2,
        "notes": "Low-cost local green H2 and low-carbon electricity for utilization destinations.",
    },
    {
        "name": "ultra_low_power_product_high_2040",
        "year": 2040,
        "target_market": "china",
        "price_case": "high",
        "policy_source": "cli",
        "scenario": Scenario(carbon_price_usd_per_tco2=80.0, carbon_tax_usd_per_tco2=30.0, durable_removal_credit_usd_per_tco2=80.0, min_net_avoided_kgco2e_per_tco2=INCLUDE_ALL_LCA),
        "modifier": ultra_low_power,
        "notes": "High product prices plus very low-cost low-carbon electricity.",
    },
    {
        "name": "eu_saf_export_2040",
        "year": 2040,
        "target_market": "eu_saf",
        "price_case": "high",
        "policy_source": "cli",
        "scenario": Scenario(carbon_price_usd_per_tco2=120.0, carbon_tax_usd_per_tco2=50.0, durable_removal_credit_usd_per_tco2=0.0, min_net_avoided_kgco2e_per_tco2=INCLUDE_ALL_LCA),
        "modifier": low_green_h2,
        "notes": "Export-mandate SAF sensitivity with low-carbon H2.",
    },
    {
        "name": "dac_cdr_credit_2040",
        "year": 2040,
        "target_market": "global",
        "price_case": "base",
        "policy_source": "cli",
        "scenario": Scenario(carbon_price_usd_per_tco2=0.0, carbon_tax_usd_per_tco2=0.0, durable_removal_credit_usd_per_tco2=300.0, min_net_avoided_kgco2e_per_tco2=INCLUDE_ALL_LCA),
        "modifier": ultra_low_power,
        "notes": "High durable-removal-credit sensitivity for DAC and storage.",
    },
    {
        "name": "learning_2050_high_product",
        "year": 2050,
        "target_market": "china",
        "price_case": "high",
        "policy_source": "cli",
        "scenario": Scenario(carbon_price_usd_per_tco2=150.0, carbon_tax_usd_per_tco2=80.0, durable_removal_credit_usd_per_tco2=160.0, min_net_avoided_kgco2e_per_tco2=INCLUDE_ALL_LCA),
        "modifier": low_green_h2,
        "notes": "2050 learning, high product price, and stronger policy.",
    },
    {
        "name": "breakthrough_utilization_2050",
        "year": 2050,
        "target_market": "eu_saf",
        "price_case": "high",
        "policy_source": "cli",
        "scenario": Scenario(carbon_price_usd_per_tco2=250.0, carbon_tax_usd_per_tco2=150.0, durable_removal_credit_usd_per_tco2=250.0, min_net_avoided_kgco2e_per_tco2=INCLUDE_ALL_LCA),
        "modifier": breakthrough_utilization,
        "notes": "Boundary case: very low electricity, very low H2 cost, high carbon policy, high product premium.",
    },
]


def ensure_inputs() -> None:
    build_real_inputs(
        data_dir=DATA_DIR,
        out_dir=INPUT_DIR,
        source_year=2024,
        top_sources=300,
        capture_rate=0.90,
        exchange_rate_cny_per_usd=7.2,
        storage_horizon_years=20,
        source_calibration_path=SOURCE_CALIBRATION,
        extra_sources_path=EXTRA_SOURCES,
    )


def finite_float(value: Any, default: float = math.inf) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def summarize_profit_records(scenario: dict[str, Any], records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for record in records:
        key = (str(record["technology_family"]), str(record["pathway"]), str(record["product"]))
        groups.setdefault(key, []).append(record)
    for (family, pathway, product), group in sorted(groups.items()):
        best = max(group, key=lambda row: finite_float(row["margin_usd_per_tco2"], -math.inf))
        positives = [row for row in group if finite_float(row["margin_usd_per_tco2"], -math.inf) > 0]
        rows.append(
            {
                "scenario": scenario["name"],
                "year": scenario["year"],
                "target_market": scenario["target_market"],
                "price_case": scenario["price_case"],
                "technology_family": family,
                "pathway": pathway,
                "product": product,
                "candidate_count": len(group),
                "positive_candidate_count": len(positives),
                "best_margin_usd_per_tco2": best["margin_usd_per_tco2"],
                "best_city": best["city_name"],
                "best_source_id": best["source_id"],
                "best_source_type": best["source_type"],
                "best_destination_id": best["destination_id"],
                "best_distance_km": best["distance_km"],
                "best_break_even_product_price_usd_per_kg": best["break_even_product_price_usd_per_kg"],
                "best_break_even_policy_credit_usd_per_tco2": best["break_even_policy_credit_usd_per_tco2"],
                "best_break_even_h2_price_usd_per_kg": best["break_even_h2_price_usd_per_kg"],
                "best_break_even_electricity_price_usd_per_mwh": best["break_even_electricity_price_usd_per_mwh"],
            }
        )
    return rows


def summarize_system(scenario: dict[str, Any], records: list[dict[str, Any]]) -> dict[str, Any]:
    best = max(records, key=lambda row: finite_float(row["margin_usd_per_tco2"], -math.inf))
    positives = [row for row in records if finite_float(row["margin_usd_per_tco2"], -math.inf) > 0]
    return {
        "scenario": scenario["name"],
        "year": scenario["year"],
        "target_market": scenario["target_market"],
        "price_case": scenario["price_case"],
        "policy_source": scenario["policy_source"],
        "candidate_count": len(records),
        "positive_candidate_count": len(positives),
        "best_margin_usd_per_tco2": best["margin_usd_per_tco2"],
        "best_city": best["city_name"],
        "best_pathway": best["pathway"],
        "best_family": best["technology_family"],
        "best_product": best["product"],
        "best_source_type": best["source_type"],
        "best_distance_km": best["distance_km"],
        "notes": scenario["notes"],
    }


def run_scenario(scenario: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    sources = load_sources(INPUT_DIR / "spatial_sources_real.csv")
    destinations = load_destinations(INPUT_DIR / "spatial_destinations_real.csv")
    destinations = scenario["modifier"](destinations)
    destinations = _apply_policy_source(destinations, scenario["scenario"], scenario["policy_source"])
    modes = load_transport_modes(DATA_DIR / "transport_modes.csv")
    hubs = load_hubs(INPUT_DIR / "hubs_real.csv")
    hourly = load_hourly_profiles(INPUT_DIR / "hourly_energy_profiles_real.csv")
    learning = load_learning_rows(DATA_DIR / "technology_scenarios.csv")
    candidates = generate_spatial_candidates(
        sources,
        destinations,
        modes,
        base=scenario["scenario"],
        max_distance_km=1500.0,
        hubs=hubs,
        hourly_profiles=hourly,
        learning_rows=learning,
        technology_year=scenario["year"],
    )
    assumption_kwargs: dict[str, Path] = {}
    if PRODUCT_PRICES.exists():
        assumption_kwargs["product_prices"] = PRODUCT_PRICES
    if RELIABILITY.exists():
        assumption_kwargs["reliability"] = RELIABILITY
    join_path = DATA_DIR / "processed" / "admin" / "source_prefecture_join_top300_with_dac.csv"
    if join_path.exists():
        assumption_kwargs["source_prefecture_joins"] = join_path
    assumptions = load_profitability_assumptions(**assumption_kwargs)
    records = profit_scan(
        candidates,
        assumptions=assumptions,
        year=scenario["year"],
        target_market=scenario["target_market"],
        price_case=scenario["price_case"],
    )
    detail_path = SCENARIO_DIR / f"{scenario['name']}_profit_detail.csv"
    city_path = SCENARIO_DIR / f"{scenario['name']}_city_recommendations.csv"
    write_csv(detail_path, records)
    city_rows = city_profit_recommendations(records)
    write_csv(city_path, city_rows)
    return summarize_system(scenario, records), summarize_profit_records(scenario, records), city_rows


def main() -> None:
    ensure_inputs()
    SCENARIO_DIR.mkdir(parents=True, exist_ok=True)
    system_rows: list[dict[str, Any]] = []
    pathway_rows: list[dict[str, Any]] = []
    city_rows_all: list[dict[str, Any]] = []
    for scenario in SCENARIOS:
        system, pathway_summary, city_rows = run_scenario(scenario)
        system_rows.append(system)
        pathway_rows.extend(pathway_summary)
        for row in city_rows:
            city_rows_all.append({"scenario": scenario["name"], **row})
        print(f"Finished {scenario['name']}: {system['candidate_count']} candidates, {system['positive_candidate_count']} positive")
    write_csv(SCENARIO_DIR / "standard_scenario_system_summary.csv", system_rows)
    write_csv(SCENARIO_DIR / "standard_scenario_pathway_summary.csv", pathway_rows)
    write_csv(SCENARIO_DIR / "standard_scenario_city_recommendations.csv", city_rows_all)


if __name__ == "__main__":
    main()
