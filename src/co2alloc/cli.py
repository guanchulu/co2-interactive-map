"""Command-line interface for baseline tables and decision grids."""

from __future__ import annotations

import argparse
from dataclasses import asdict

from .decision import (
    ascii_decision_map,
    best_by_technology_family,
    decision_grid,
    evaluate_all,
    svg_decision_map,
)
from .io import write_csv, write_text
from .hourly import load_hourly_profiles
from .learning import load_learning_rows
from .monte_carlo import load_uncertainty_parameters, sample_parameters
from .profitability import (
    city_profit_recommendations,
    load_profitability_assumptions,
    profit_scan,
)
from .realdata import build_real_inputs
from .scenario import Scenario
from .sensitivity import one_at_a_time
from .spatial import (
    generate_spatial_candidates,
    greedy_allocate,
    load_destinations,
    load_hubs,
    load_sources,
    load_transport_modes,
    optimize_allocate,
    summarize_allocations,
)

import random


def _float_range(start: float, stop: float, steps: int) -> list[float]:
    if steps <= 1:
        return [start]
    delta = (stop - start) / (steps - 1)
    return [start + i * delta for i in range(steps)]


def _scenario_from_args(args: argparse.Namespace) -> Scenario:
    return Scenario(
        electricity_price_usd_per_mwh=args.electricity_price,
        h2_price_usd_per_kg=args.h2_price,
        carbon_price_usd_per_tco2=args.carbon_price,
        carbon_tax_usd_per_tco2=args.carbon_tax,
        durable_removal_credit_usd_per_tco2=args.durable_removal_credit,
        co2_transport_distance_km=args.transport_distance,
        grid_emissions_kgco2e_per_mwh=args.grid_intensity,
        h2_emissions_kgco2e_per_kg=args.h2_intensity,
        min_net_avoided_kgco2e_per_tco2=args.min_net_avoided,
    )


def _apply_policy_source(destinations, scenario: Scenario, policy_source: str):
    if policy_source == "destination":
        return destinations
    if policy_source != "cli":
        raise ValueError(f"Unknown policy source: {policy_source}")
    return [
        destination.__class__(
            **{
                **{field: getattr(destination, field) for field in destination.__dataclass_fields__},
                "carbon_price_usd_per_tco2": 0.0
                if destination.sink_type == "eor_oilfield"
                else scenario.carbon_price_usd_per_tco2,
                "carbon_tax_usd_per_tco2": scenario.carbon_tax_usd_per_tco2,
                "durable_removal_credit_usd_per_tco2": 0.0
                if destination.sink_type == "eor_oilfield"
                else scenario.durable_removal_credit_usd_per_tco2,
            }
        )
        for destination in destinations
    ]


def add_scenario_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--electricity-price", type=float, default=45.0)
    parser.add_argument("--h2-price", type=float, default=2.5)
    parser.add_argument("--carbon-price", type=float, default=80.0)
    parser.add_argument("--carbon-tax", type=float, default=0.0)
    parser.add_argument("--durable-removal-credit", type=float, default=0.0)
    parser.add_argument("--transport-distance", type=float, default=100.0)
    parser.add_argument("--grid-intensity", type=float, default=80.0)
    parser.add_argument("--h2-intensity", type=float, default=1.0)
    parser.add_argument("--min-net-avoided", type=float, default=0.0)


def run_baseline(args: argparse.Namespace) -> None:
    scenario = _scenario_from_args(args)
    records = [ev.flat_record() for ev in evaluate_all(scenario)]
    records.insert(0, {"pathway": "_scenario", **asdict(scenario)})
    write_csv(args.out, records)


def run_grid(args: argparse.Namespace) -> None:
    scenario = _scenario_from_args(args)
    electricity_prices = _float_range(args.elec_min, args.elec_max, args.elec_steps)
    h2_prices = _float_range(args.h2_min, args.h2_max, args.h2_steps)
    records = decision_grid(
        scenario,
        electricity_prices=electricity_prices,
        h2_prices=h2_prices,
        carbon_price=args.carbon_price,
        metric=args.metric,
    )
    write_csv(args.out, records)
    if args.ascii_out:
        write_text(args.ascii_out, ascii_decision_map(records))
    if args.svg_out:
        write_text(args.svg_out, svg_decision_map(records))


def run_sensitivity(args: argparse.Namespace) -> None:
    scenario = _scenario_from_args(args)
    records = one_at_a_time(
        scenario,
        perturbation=args.perturbation,
        metric=args.metric,
    )
    write_csv(args.out, records)


def run_family(args: argparse.Namespace) -> None:
    scenario = _scenario_from_args(args)
    records = best_by_technology_family(scenario, metric=args.metric)
    write_csv(args.out, records)


def _spatial_candidates_from_args(args: argparse.Namespace):
    sources = load_sources(args.sources)
    scenario = _scenario_from_args(args)
    destinations = _apply_policy_source(
        load_destinations(args.destinations),
        scenario,
        getattr(args, "policy_source", "destination"),
    )
    modes = load_transport_modes(args.transport_modes)
    hubs = load_hubs(args.hubs)
    hourly_profiles = load_hourly_profiles(args.hourly_profiles) if args.hourly_profiles else None
    learning_rows = load_learning_rows(args.learning) if args.learning else None
    return generate_spatial_candidates(
        sources,
        destinations,
        modes,
        base=scenario,
        max_distance_km=args.max_distance,
        hubs=hubs,
        hourly_profiles=hourly_profiles,
        learning_rows=learning_rows,
        technology_year=args.year,
    )


def run_spatial_candidates(args: argparse.Namespace) -> None:
    candidates = _spatial_candidates_from_args(args)
    records = [
        candidate.flat_record()
        for candidate in sorted(
            candidates,
            key=lambda candidate: candidate.adjusted_net_cost_usd_per_tco2,
        )
    ]
    write_csv(args.out, records)


def run_spatial_allocate(args: argparse.Namespace) -> None:
    candidates = _spatial_candidates_from_args(args)
    if args.optimizer == "lp":
        allocations = optimize_allocate(
            candidates,
            metric=args.metric,
            minimum_source_fraction=args.minimum_source_fraction,
            target_total_mtco2_per_year=args.target_total_mtco2,
            target_source_fraction=args.target_source_fraction,
        )
    else:
        allocations = greedy_allocate(candidates, metric=args.metric)
    write_csv(args.out, allocations)
    write_csv(args.summary_out, summarize_allocations(allocations))


def run_monte_carlo(args: argparse.Namespace) -> None:
    base_sources = load_sources(args.sources)
    scenario = _scenario_from_args(args)
    base_destinations = _apply_policy_source(
        load_destinations(args.destinations),
        scenario,
        getattr(args, "policy_source", "destination"),
    )
    modes = load_transport_modes(args.transport_modes)
    hubs = load_hubs(args.hubs)
    hourly_profiles = load_hourly_profiles(args.hourly_profiles) if args.hourly_profiles else None
    learning_rows = load_learning_rows(args.learning) if args.learning else None
    params = load_uncertainty_parameters(args.uncertainty)
    rng = random.Random(args.seed)
    records = []

    def clamp(value: float, low: float, high: float) -> float:
        return max(low, min(high, value))

    for run_id in range(args.runs):
        sample = sample_parameters(params, rng)
        sources = [
            source.__class__(
                **{
                    **{field: getattr(source, field) for field in source.__dataclass_fields__},
                    "co2_available_mtpa": source.co2_available_mtpa * sample.get("source_available_multiplier", 1.0),
                    "capture_cost_usd_per_tco2": source.capture_cost_usd_per_tco2 * sample.get("capture_cost_multiplier", 1.0),
                    "capture_emissions_kgco2e_per_tco2": source.capture_emissions_kgco2e_per_tco2 * sample.get("capture_emissions_multiplier", 1.0),
                    "capture_energy_kwh_per_tco2": source.capture_energy_kwh_per_tco2 * sample.get("capture_energy_multiplier", 1.0),
                    "co2_purity_fraction": clamp(
                        source.co2_purity_fraction + sample.get("source_purity_absolute_delta", 0.0),
                        0.01,
                        0.999,
                    ),
                    "capture_pressure_bar": max(
                        0.1,
                        source.capture_pressure_bar * sample.get("source_pressure_multiplier", 1.0),
                    ),
                }
            )
            for source in base_sources
        ]
        destinations = [
            destination.__class__(
                **{
                    **{field: getattr(destination, field) for field in destination.__dataclass_fields__},
                    "capacity_mtco2_per_year": destination.capacity_mtco2_per_year * sample.get("destination_capacity_multiplier", 1.0),
                    "electricity_price_usd_per_mwh": destination.electricity_price_usd_per_mwh * sample.get("electricity_price_multiplier", 1.0),
                    "grid_emissions_kgco2e_per_mwh": destination.grid_emissions_kgco2e_per_mwh * sample.get("grid_emissions_multiplier", 1.0),
                    "h2_price_usd_per_kg": destination.h2_price_usd_per_kg * sample.get("h2_price_multiplier", 1.0),
                    "h2_emissions_kgco2e_per_kg": destination.h2_emissions_kgco2e_per_kg * sample.get("h2_emissions_multiplier", 1.0),
                    "carbon_price_usd_per_tco2": destination.carbon_price_usd_per_tco2 * sample.get("carbon_credit_multiplier", 1.0),
                    "carbon_tax_usd_per_tco2": destination.carbon_tax_usd_per_tco2 * sample.get("carbon_tax_multiplier", 1.0),
                    "durable_removal_credit_usd_per_tco2": destination.durable_removal_credit_usd_per_tco2 * sample.get("durable_credit_multiplier", 1.0),
                    "purification_cost_usd_per_tco2_per_fraction": destination.purification_cost_usd_per_tco2_per_fraction * sample.get("purification_cost_multiplier", 1.0),
                    "purification_emissions_kgco2e_per_tco2_per_fraction": destination.purification_emissions_kgco2e_per_tco2_per_fraction * sample.get("purification_emissions_multiplier", 1.0),
                    "impurity_removal_cost_usd_per_tco2_per_index": destination.impurity_removal_cost_usd_per_tco2_per_index * sample.get("impurity_removal_cost_multiplier", 1.0),
                    "impurity_removal_emissions_kgco2e_per_tco2_per_index": destination.impurity_removal_emissions_kgco2e_per_tco2_per_index * sample.get("impurity_removal_emissions_multiplier", 1.0),
                    "pressure_boost_kwh_per_tco2_per_ln_ratio": destination.pressure_boost_kwh_per_tco2_per_ln_ratio * sample.get("pressure_energy_multiplier", 1.0),
                    "electrolyzer_capex_usd_per_kw": destination.electrolyzer_capex_usd_per_kw * sample.get("electrolyzer_capex_multiplier", 1.0),
                    "electrolyzer_kwh_per_kg_h2": destination.electrolyzer_kwh_per_kg_h2 * sample.get("electrolyzer_efficiency_multiplier", 1.0),
                    "water_available_m3_per_year": destination.water_available_m3_per_year * sample.get("water_availability_multiplier", 1.0),
                    "water_price_usd_per_m3": destination.water_price_usd_per_m3 * sample.get("water_price_multiplier", 1.0),
                    "land_available_km2": destination.land_available_km2 * sample.get("land_availability_multiplier", 1.0),
                    "land_cost_usd_per_m2_year": destination.land_cost_usd_per_m2_year * sample.get("land_cost_multiplier", 1.0),
                    "permit_risk_cost_usd_per_tco2": destination.permit_risk_cost_usd_per_tco2 * sample.get("permit_risk_multiplier", 1.0),
                }
            )
            for destination in base_destinations
        ]
        sampled_modes = [
            mode.__class__(
                **{
                    **{field: getattr(mode, field) for field in mode.__dataclass_fields__},
                    "fixed_cost_usd_per_tco2": mode.fixed_cost_usd_per_tco2 * sample.get("transport_cost_multiplier", 1.0),
                    "cost_usd_per_tkm": mode.cost_usd_per_tkm * sample.get("transport_cost_multiplier", 1.0),
                    "emissions_kgco2e_per_tkm": mode.emissions_kgco2e_per_tkm * sample.get("transport_emissions_multiplier", 1.0),
                }
            )
            for mode in modes
        ]
        sampled_hubs = [
            hub.__class__(
                **{
                    **{field: getattr(hub, field) for field in hub.__dataclass_fields__},
                    "capacity_mtco2_per_year": hub.capacity_mtco2_per_year * sample.get("hub_capacity_multiplier", 1.0),
                    "compression_cost_usd_per_tco2": hub.compression_cost_usd_per_tco2 * sample.get("hub_compression_cost_multiplier", 1.0),
                    "compression_emissions_kgco2e_per_tco2": hub.compression_emissions_kgco2e_per_tco2 * sample.get("hub_compression_emissions_multiplier", 1.0),
                }
            )
            for hub in hubs
        ]
        candidates = generate_spatial_candidates(
            sources,
            destinations,
            sampled_modes,
            base=scenario,
            max_distance_km=args.max_distance,
            hubs=sampled_hubs,
            hourly_profiles=hourly_profiles,
            learning_rows=learning_rows,
            technology_year=args.year,
        )
        allocations = optimize_allocate(
            candidates,
            metric=args.metric,
            minimum_source_fraction=args.minimum_source_fraction,
            target_total_mtco2_per_year=args.target_total_mtco2,
            target_source_fraction=args.target_source_fraction,
        )
        for record in summarize_allocations(allocations):
            record["run_id"] = run_id
            for key, value in sample.items():
                record[key] = value
            records.append(record)
    write_csv(args.out, records)


def run_build_real_inputs(args: argparse.Namespace) -> None:
    paths = build_real_inputs(
        data_dir=args.data_dir,
        out_dir=args.out_dir,
        source_year=args.source_year,
        top_sources=args.top_sources,
        capture_rate=args.capture_rate,
        exchange_rate_cny_per_usd=args.exchange_rate,
        storage_horizon_years=args.storage_horizon_years,
        source_calibration_path=args.source_calibration or None,
        extra_sources_path=args.extra_sources or None,
    )
    records = [
        {"name": name, "path": str(path)}
        for name, path in paths.items()
    ]
    write_csv(args.manifest_out, records)


def _profitability_assumptions_from_args(args: argparse.Namespace):
    return load_profitability_assumptions(
        product_prices=args.product_prices,
        quality_specs=args.product_quality_specs,
        policy_rules=args.policy_rules,
        mrv_costs=args.mrv_costs,
        finance=args.finance_assumptions,
        reliability=args.technology_reliability,
        city_centers=args.city_centers,
        source_prefecture_joins=args.source_prefecture_joins,
    )


def run_profit_scan(args: argparse.Namespace) -> None:
    candidates = _spatial_candidates_from_args(args)
    assumptions = _profitability_assumptions_from_args(args)
    records = profit_scan(
        candidates,
        assumptions=assumptions,
        year=args.year,
        target_market=args.target_market,
        price_case=args.price_case,
        min_margin_usd_per_tco2=args.min_margin,
    )
    write_csv(args.out, records)


def run_profit_scan_city(args: argparse.Namespace) -> None:
    candidates = _spatial_candidates_from_args(args)
    assumptions = _profitability_assumptions_from_args(args)
    records = profit_scan(
        candidates,
        assumptions=assumptions,
        year=args.year,
        target_market=args.target_market,
        price_case=args.price_case,
        min_margin_usd_per_tco2=None,
    )
    recommendations = city_profit_recommendations(records)
    write_csv(args.out, recommendations)
    if args.detail_out:
        write_csv(args.detail_out, records)


def add_profitability_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--product-prices", default="data/product_prices.csv")
    parser.add_argument("--product-quality-specs", default="data/product_quality_specs.csv")
    parser.add_argument("--policy-rules", default="data/policy_eligibility_rules.csv")
    parser.add_argument("--mrv-costs", default="data/mrv_certification_costs.csv")
    parser.add_argument("--finance-assumptions", default="data/finance_assumptions.csv")
    parser.add_argument("--technology-reliability", default="data/technology_reliability.csv")
    parser.add_argument("--city-centers", default="data/city_centers_screening.csv")
    parser.add_argument("--source-prefecture-joins", default="")
    parser.add_argument("--target-market", default="china")
    parser.add_argument("--price-case", choices=["low", "base", "high"], default="base")
    parser.add_argument("--min-margin", type=float, default=None)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="co2alloc")
    subparsers = parser.add_subparsers(dest="command", required=True)

    baseline = subparsers.add_parser("baseline")
    add_scenario_args(baseline)
    baseline.add_argument("--out", default="output/baseline.csv")
    baseline.set_defaults(func=run_baseline)

    grid = subparsers.add_parser("grid")
    add_scenario_args(grid)
    grid.add_argument("--out", default="output/decision_grid.csv")
    grid.add_argument("--ascii-out", default="")
    grid.add_argument("--svg-out", default="")
    grid.add_argument("--metric", choices=["net_cost", "gross_cost", "abatement_cost", "removal_cost"], default="net_cost")
    grid.add_argument("--elec-min", type=float, default=10.0)
    grid.add_argument("--elec-max", type=float, default=120.0)
    grid.add_argument("--elec-steps", type=int, default=12)
    grid.add_argument("--h2-min", type=float, default=0.5)
    grid.add_argument("--h2-max", type=float, default=6.0)
    grid.add_argument("--h2-steps", type=int, default=12)
    grid.set_defaults(func=run_grid)

    sensitivity = subparsers.add_parser("sensitivity")
    add_scenario_args(sensitivity)
    sensitivity.add_argument("--out", default="output/sensitivity.csv")
    sensitivity.add_argument("--metric", choices=["net_cost", "gross_cost", "abatement_cost", "removal_cost"], default="net_cost")
    sensitivity.add_argument("--perturbation", type=float, default=0.25)
    sensitivity.set_defaults(func=run_sensitivity)

    family = subparsers.add_parser("family")
    add_scenario_args(family)
    family.add_argument("--out", default="output/family_best.csv")
    family.add_argument("--metric", choices=["net_cost", "gross_cost", "abatement_cost", "removal_cost"], default="net_cost")
    family.set_defaults(func=run_family)

    spatial_candidates = subparsers.add_parser("spatial-candidates")
    add_scenario_args(spatial_candidates)
    spatial_candidates.add_argument("--sources", default="data/spatial_sources.csv")
    spatial_candidates.add_argument("--destinations", default="data/spatial_destinations.csv")
    spatial_candidates.add_argument("--transport-modes", default="data/transport_modes.csv")
    spatial_candidates.add_argument("--hubs", default="data/hubs.csv")
    spatial_candidates.add_argument("--hourly-profiles", default="data/hourly_energy_profiles.csv")
    spatial_candidates.add_argument("--learning", default="data/technology_scenarios.csv")
    spatial_candidates.add_argument("--year", type=int, default=2030)
    spatial_candidates.add_argument("--max-distance", type=float, default=None)
    spatial_candidates.add_argument("--policy-source", choices=["destination", "cli"], default="destination")
    spatial_candidates.add_argument("--out", default="output/spatial_candidates.csv")
    spatial_candidates.set_defaults(func=run_spatial_candidates)

    spatial_allocate = subparsers.add_parser("spatial-allocate")
    add_scenario_args(spatial_allocate)
    spatial_allocate.add_argument("--sources", default="data/spatial_sources.csv")
    spatial_allocate.add_argument("--destinations", default="data/spatial_destinations.csv")
    spatial_allocate.add_argument("--transport-modes", default="data/transport_modes.csv")
    spatial_allocate.add_argument("--hubs", default="data/hubs.csv")
    spatial_allocate.add_argument("--hourly-profiles", default="data/hourly_energy_profiles.csv")
    spatial_allocate.add_argument("--learning", default="data/technology_scenarios.csv")
    spatial_allocate.add_argument("--year", type=int, default=2030)
    spatial_allocate.add_argument("--max-distance", type=float, default=None)
    spatial_allocate.add_argument("--metric", choices=["adjusted_net_cost", "adjusted_abatement_cost", "adjusted_removal_cost"], default="adjusted_net_cost")
    spatial_allocate.add_argument("--optimizer", choices=["lp", "greedy"], default="lp")
    spatial_allocate.add_argument("--minimum-source-fraction", type=float, default=1.0)
    spatial_allocate.add_argument("--target-total-mtco2", type=float, default=None)
    spatial_allocate.add_argument("--target-source-fraction", type=float, default=None)
    spatial_allocate.add_argument("--policy-source", choices=["destination", "cli"], default="destination")
    spatial_allocate.add_argument("--out", default="output/spatial_allocations.csv")
    spatial_allocate.add_argument("--summary-out", default="output/spatial_summary.csv")
    spatial_allocate.set_defaults(func=run_spatial_allocate)

    monte_carlo = subparsers.add_parser("monte-carlo")
    add_scenario_args(monte_carlo)
    monte_carlo.add_argument("--sources", default="data/spatial_sources.csv")
    monte_carlo.add_argument("--destinations", default="data/spatial_destinations.csv")
    monte_carlo.add_argument("--transport-modes", default="data/transport_modes.csv")
    monte_carlo.add_argument("--hubs", default="data/hubs.csv")
    monte_carlo.add_argument("--hourly-profiles", default="data/hourly_energy_profiles.csv")
    monte_carlo.add_argument("--learning", default="data/technology_scenarios.csv")
    monte_carlo.add_argument("--uncertainty", default="data/uncertainty_parameters.csv")
    monte_carlo.add_argument("--year", type=int, default=2030)
    monte_carlo.add_argument("--max-distance", type=float, default=None)
    monte_carlo.add_argument("--metric", choices=["adjusted_net_cost", "adjusted_abatement_cost", "adjusted_removal_cost"], default="adjusted_net_cost")
    monte_carlo.add_argument("--minimum-source-fraction", type=float, default=1.0)
    monte_carlo.add_argument("--target-total-mtco2", type=float, default=None)
    monte_carlo.add_argument("--target-source-fraction", type=float, default=None)
    monte_carlo.add_argument("--policy-source", choices=["destination", "cli"], default="destination")
    monte_carlo.add_argument("--runs", type=int, default=100)
    monte_carlo.add_argument("--seed", type=int, default=42)
    monte_carlo.add_argument("--out", default="output/monte_carlo_summary.csv")
    monte_carlo.set_defaults(func=run_monte_carlo)

    profit_scan_parser = subparsers.add_parser("profit-scan")
    add_scenario_args(profit_scan_parser)
    profit_scan_parser.add_argument("--sources", default="data/spatial_sources.csv")
    profit_scan_parser.add_argument("--destinations", default="data/spatial_destinations.csv")
    profit_scan_parser.add_argument("--transport-modes", default="data/transport_modes.csv")
    profit_scan_parser.add_argument("--hubs", default="data/hubs.csv")
    profit_scan_parser.add_argument("--hourly-profiles", default="data/hourly_energy_profiles.csv")
    profit_scan_parser.add_argument("--learning", default="data/technology_scenarios.csv")
    profit_scan_parser.add_argument("--year", type=int, default=2030)
    profit_scan_parser.add_argument("--max-distance", type=float, default=None)
    profit_scan_parser.add_argument("--policy-source", choices=["destination", "cli"], default="destination")
    add_profitability_args(profit_scan_parser)
    profit_scan_parser.add_argument("--out", default="output/profit_scan.csv")
    profit_scan_parser.set_defaults(func=run_profit_scan)

    profit_city = subparsers.add_parser("profit-scan-city")
    add_scenario_args(profit_city)
    profit_city.add_argument("--sources", default="data/spatial_sources.csv")
    profit_city.add_argument("--destinations", default="data/spatial_destinations.csv")
    profit_city.add_argument("--transport-modes", default="data/transport_modes.csv")
    profit_city.add_argument("--hubs", default="data/hubs.csv")
    profit_city.add_argument("--hourly-profiles", default="data/hourly_energy_profiles.csv")
    profit_city.add_argument("--learning", default="data/technology_scenarios.csv")
    profit_city.add_argument("--year", type=int, default=2030)
    profit_city.add_argument("--max-distance", type=float, default=None)
    profit_city.add_argument("--policy-source", choices=["destination", "cli"], default="destination")
    add_profitability_args(profit_city)
    profit_city.add_argument("--out", default="output/city_profit_recommendations.csv")
    profit_city.add_argument("--detail-out", default="")
    profit_city.set_defaults(func=run_profit_scan_city)

    real_inputs = subparsers.add_parser("build-real-inputs")
    real_inputs.add_argument("--data-dir", default="data")
    real_inputs.add_argument("--out-dir", default="data/real_inputs")
    real_inputs.add_argument("--source-year", type=int, default=2024)
    real_inputs.add_argument("--top-sources", type=int, default=120)
    real_inputs.add_argument("--capture-rate", type=float, default=0.90)
    real_inputs.add_argument("--exchange-rate", type=float, default=7.2)
    real_inputs.add_argument("--storage-horizon-years", type=int, default=20)
    real_inputs.add_argument("--source-calibration", default="")
    real_inputs.add_argument("--extra-sources", default="")
    real_inputs.add_argument("--manifest-out", default="data/real_inputs/manifest.csv")
    real_inputs.set_defaults(func=run_build_real_inputs)

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
