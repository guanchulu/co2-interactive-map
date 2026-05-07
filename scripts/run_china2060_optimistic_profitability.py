"""Run China 2030/2060 optimistic-effort profitability time series."""

from __future__ import annotations

import csv
import math
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any


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
OUTPUT_DIR = ROOT / "output" / "china2060_optimistic_profitability"
SOURCE_CALIBRATION = DATA_DIR / "processed" / "co2_sources" / "source_inventory_calibration_ceads_2022.csv"
EXTRA_SOURCES = DATA_DIR / "dac_sources.csv"
EFFORT_FILE = DATA_DIR / "china2060_optimistic_effort_scenario.csv"
PRODUCT_PRICES = DATA_DIR / "product_prices_china2060_optimistic.csv"
POLICY_RULES = DATA_DIR / "policy_eligibility_rules_china2060_optimistic.csv"
LEARNING = DATA_DIR / "technology_scenarios_china2060_optimistic.csv"
RELIABILITY = DATA_DIR / "technology_reliability_china2060_optimistic.csv"
SOURCE_JOIN = DATA_DIR / "processed" / "admin" / "source_prefecture_join_top300_with_dac.csv"
INCLUDE_ALL_LCA = -1_000_000.0


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


def finite_float(value: Any, default: float = math.inf) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


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


def replace_destination(destination: Destination, **updates: Any) -> Destination:
    values = asdict(destination)
    values.update(updates)
    return Destination(**values)


def effort_rows() -> list[dict[str, Any]]:
    rows = []
    for row in read_csv(EFFORT_FILE):
        rows.append(
            {
                "year": int(row["year"]),
                "electricity_price_usd_per_mwh": float(row["electricity_price_usd_per_mwh"]),
                "grid_emissions_kgco2e_per_mwh": float(row["grid_emissions_kgco2e_per_mwh"]),
                "h2_price_usd_per_kg": float(row["h2_price_usd_per_kg"]),
                "h2_emissions_kgco2e_per_kg": float(row["h2_emissions_kgco2e_per_kg"]),
                "carbon_price_usd_per_tco2": float(row["carbon_price_usd_per_tco2"]),
                "carbon_tax_usd_per_tco2": float(row["carbon_tax_usd_per_tco2"]),
                "durable_removal_credit_usd_per_tco2": float(row["durable_removal_credit_usd_per_tco2"]),
                "discount_rate": float(row["discount_rate"]),
            }
        )
    return rows


def optimistic_destinations(destinations: list[Destination], effort: dict[str, Any]) -> list[Destination]:
    updated = []
    for destination in destinations:
        updates = {
            "electricity_price_usd_per_mwh": min(destination.electricity_price_usd_per_mwh, effort["electricity_price_usd_per_mwh"]),
            "grid_emissions_kgco2e_per_mwh": min(destination.grid_emissions_kgco2e_per_mwh, effort["grid_emissions_kgco2e_per_mwh"]),
            "h2_price_usd_per_kg": min(destination.h2_price_usd_per_kg, effort["h2_price_usd_per_kg"]),
            "h2_emissions_kgco2e_per_kg": min(destination.h2_emissions_kgco2e_per_kg, effort["h2_emissions_kgco2e_per_kg"]),
            "electrolyzer_capex_usd_per_kw": min(destination.electrolyzer_capex_usd_per_kw, 900.0 - (effort["year"] - 2030) * 18.0),
            "electrolyzer_kwh_per_kg_h2": min(destination.electrolyzer_kwh_per_kg_h2, 52.0 - (effort["year"] - 2030) * 0.18),
        }
        if destination.sink_type == "provincial_storage":
            updates = {
                key: value
                for key, value in updates.items()
                if key in {"electricity_price_usd_per_mwh", "grid_emissions_kgco2e_per_mwh"}
            }
        updated.append(replace_destination(destination, **updates))
    return updated


def scenario_for_effort(effort: dict[str, Any]) -> Scenario:
    return Scenario(
        electricity_price_usd_per_mwh=effort["electricity_price_usd_per_mwh"],
        h2_price_usd_per_kg=effort["h2_price_usd_per_kg"],
        grid_emissions_kgco2e_per_mwh=effort["grid_emissions_kgco2e_per_mwh"],
        h2_emissions_kgco2e_per_kg=effort["h2_emissions_kgco2e_per_kg"],
        carbon_price_usd_per_tco2=effort["carbon_price_usd_per_tco2"],
        carbon_tax_usd_per_tco2=effort["carbon_tax_usd_per_tco2"],
        durable_removal_credit_usd_per_tco2=effort["durable_removal_credit_usd_per_tco2"],
        discount_rate=effort["discount_rate"],
        min_net_avoided_kgco2e_per_tco2=INCLUDE_ALL_LCA,
    )


def summarize_pathways(year: int, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for record in records:
        groups.setdefault((str(record["technology_family"]), str(record["pathway"]), str(record["product"])), []).append(record)
    rows: list[dict[str, Any]] = []
    for (family, pathway, product), group in sorted(groups.items()):
        best = max(group, key=lambda item: finite_float(item["margin_usd_per_tco2"], -math.inf))
        positives = [item for item in group if finite_float(item["margin_usd_per_tco2"], -math.inf) > 0]
        rows.append(
            {
                "year": year,
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
                "best_product_price_usd_per_kg": best["product_price_usd_per_kg"],
                "best_break_even_product_price_usd_per_kg": best["break_even_product_price_usd_per_kg"],
                "best_break_even_policy_credit_usd_per_tco2": best["break_even_policy_credit_usd_per_tco2"],
                "best_policy_revenue_usd_per_tco2": best["policy_revenue_usd_per_tco2"],
                "best_product_revenue_usd_per_tco2": best["product_revenue_usd_per_tco2"],
                "best_risk_adjusted_gross_cost_usd_per_tco2": best["risk_adjusted_gross_cost_usd_per_tco2"],
            }
        )
    return rows


def summarize_year(year: int, records: list[dict[str, Any]]) -> dict[str, Any]:
    best = max(records, key=lambda item: finite_float(item["margin_usd_per_tco2"], -math.inf))
    positives = [item for item in records if finite_float(item["margin_usd_per_tco2"], -math.inf) > 0]
    nonstorage = [item for item in records if item["pathway"] != "geological_storage"]
    best_nonstorage = max(nonstorage, key=lambda item: finite_float(item["margin_usd_per_tco2"], -math.inf))
    return {
        "year": year,
        "candidate_count": len(records),
        "positive_candidate_count": len(positives),
        "positive_pathway_count": len({item["pathway"] for item in positives}),
        "best_margin_usd_per_tco2": best["margin_usd_per_tco2"],
        "best_city": best["city_name"],
        "best_pathway": best["pathway"],
        "best_family": best["technology_family"],
        "best_product": best["product"],
        "best_nonstorage_margin_usd_per_tco2": best_nonstorage["margin_usd_per_tco2"],
        "best_nonstorage_city": best_nonstorage["city_name"],
        "best_nonstorage_pathway": best_nonstorage["pathway"],
        "best_nonstorage_product": best_nonstorage["product"],
    }


def earliest_windows(pathway_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_pathway: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for row in pathway_rows:
        by_pathway.setdefault((row["technology_family"], row["pathway"], row["product"]), []).append(row)
    out = []
    for (family, pathway, product), rows in sorted(by_pathway.items()):
        rows_sorted = sorted(rows, key=lambda item: int(item["year"]))
        positives = [row for row in rows_sorted if finite_float(row["best_margin_usd_per_tco2"], -math.inf) > 0]
        first = positives[0] if positives else None
        best = max(rows_sorted, key=lambda item: finite_float(item["best_margin_usd_per_tco2"], -math.inf))
        out.append(
            {
                "technology_family": family,
                "pathway": pathway,
                "product": product,
                "first_profitable_year": first["year"] if first else "",
                "first_profitable_margin_usd_per_tco2": first["best_margin_usd_per_tco2"] if first else "",
                "first_profitable_city": first["best_city"] if first else "",
                "best_year": best["year"],
                "best_margin_usd_per_tco2": best["best_margin_usd_per_tco2"],
                "best_city": best["best_city"],
                "best_product_price_usd_per_kg": best["best_product_price_usd_per_kg"],
                "best_break_even_product_price_usd_per_kg": best["best_break_even_product_price_usd_per_kg"],
                "interpretation": "profitable_in_effort_case" if first else "not_profitable_even_by_2060_effort_case",
            }
        )
    return out


def main() -> None:
    ensure_inputs()
    sources = load_sources(INPUT_DIR / "spatial_sources_real.csv")
    base_destinations = load_destinations(INPUT_DIR / "spatial_destinations_real.csv")
    modes = load_transport_modes(DATA_DIR / "transport_modes.csv")
    hubs = load_hubs(INPUT_DIR / "hubs_real.csv")
    hourly = load_hourly_profiles(INPUT_DIR / "hourly_energy_profiles_real.csv")
    learning = load_learning_rows(LEARNING)
    assumption_kwargs: dict[str, Path] = {
        "product_prices": PRODUCT_PRICES,
        "policy_rules": POLICY_RULES,
        "reliability": RELIABILITY,
    }
    if SOURCE_JOIN.exists():
        assumption_kwargs["source_prefecture_joins"] = SOURCE_JOIN
    assumptions = load_profitability_assumptions(**assumption_kwargs)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    system_rows: list[dict[str, Any]] = []
    pathway_rows: list[dict[str, Any]] = []
    city_rows_all: list[dict[str, Any]] = []
    for effort in effort_rows():
        year = int(effort["year"])
        base = scenario_for_effort(effort)
        destinations = optimistic_destinations(base_destinations, effort)
        destinations = _apply_policy_source(destinations, base, "cli")
        candidates = generate_spatial_candidates(
            sources,
            destinations,
            modes,
            base=base,
            max_distance_km=1500.0,
            hubs=hubs,
            hourly_profiles=hourly,
            learning_rows=learning,
            technology_year=year,
        )
        records = profit_scan(
            candidates,
            assumptions=assumptions,
            year=year,
            target_market="china",
            price_case="high",
        )
        write_csv(OUTPUT_DIR / f"china2060_{year}_profit_detail.csv", records)
        city_rows = city_profit_recommendations(records)
        write_csv(OUTPUT_DIR / f"china2060_{year}_city_recommendations.csv", city_rows)
        system_rows.append(summarize_year(year, records))
        pathway_summary = summarize_pathways(year, records)
        pathway_rows.extend(pathway_summary)
        for row in city_rows:
            city_rows_all.append({"year": year, **row})
        print(f"Finished China 2060 effort {year}: {len(records)} candidates, {system_rows[-1]['positive_candidate_count']} positive")

    write_csv(OUTPUT_DIR / "china2060_system_summary.csv", system_rows)
    write_csv(OUTPUT_DIR / "china2060_pathway_summary.csv", pathway_rows)
    write_csv(OUTPUT_DIR / "china2060_city_recommendations.csv", city_rows_all)
    write_csv(OUTPUT_DIR / "china2060_earliest_profit_windows.csv", earliest_windows(pathway_rows))


if __name__ == "__main__":
    main()
