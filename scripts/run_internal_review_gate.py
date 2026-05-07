"""Automated internal review gate for the CO2 Joule manuscript package.

The script scores the package against a 100-point gate. It exits non-zero if
the score is below 100, so the workflow cannot proceed silently with missing
model modules, weak figure coverage, or unresolved review risks.
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs" / "joule_submission"
SRC = ROOT / "src" / "co2alloc"
OUT = ROOT / "output" / "internal_review_gate"
TRUE_MM = ROOT / "output" / "true_multimodal_inputs"


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
    if not math.isfinite(parsed):
        return default
    return parsed


def exists(path: str) -> bool:
    return (ROOT / path).exists()


def file_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def check(condition: bool, name: str, points: int, evidence: str, failures: list[str]) -> dict[str, Any]:
    awarded = points if condition else 0
    if not condition:
        failures.append(name)
    return {
        "check": name,
        "points_possible": points,
        "points_awarded": awarded,
        "pass": int(condition),
        "evidence": evidence,
    }


def storyline_figures_ok() -> tuple[bool, str]:
    folder = DOCS / "figures_storyline"
    files = sorted(folder.glob("figure*.svg"))
    if len(files) != 6:
        return False, f"{len(files)} storyline SVGs"
    sizes = [path.stat().st_size for path in files]
    if min(sizes) < 5000:
        return False, f"smallest SVG {min(sizes)} bytes"
    figure2 = folder / "figure2_where_to_build.svg"
    if not figure2.exists() or figure2.stat().st_size < 250_000:
        return False, "national heatmap figure is missing or too sparse"
    script_text = file_text(ROOT / "scripts" / "make_storyline_figures.py")
    if "draw_margin_heatmap" not in script_text or "geometry_to_path" not in script_text:
        return False, "storyline generator lacks polygon heatmap renderer"
    figure6 = folder / "figure6_optimized_buildout_gap.svg"
    if not figure6.exists() or figure6.stat().st_size < 40_000:
        return False, "network-route-policy-uncertainty composite figure is missing or too sparse"
    if "draw_route_network" not in script_text or "evidence grade" not in figure6.read_text(encoding="utf-8"):
        return False, "Figure 6 lacks route-network or evidence-quality panels"
    names = " ".join(path.name for path in files)
    required = ["decision", "baseline", "where", "when", "switch", "market", "policy", "optimized"]
    ok = all(word in names for word in required)
    return ok, f"6 storyline SVGs; national heatmap {figure2.stat().st_size} bytes; composite Figure 6 {figure6.stat().st_size} bytes; min size {min(sizes)} bytes"


def composite_figures_ok() -> tuple[bool, str]:
    folder = DOCS / "figures_composite"
    files = sorted(folder.glob("figure*.svg"))
    return len(files) >= 8, f"{len(files)} composite SVGs"


def interactive_map_ok() -> tuple[bool, str]:
    app_dir = ROOT / "docs" / "interactive_map"
    required = [
        app_dir / "index.html",
        app_dir / "styles.css",
        app_dir / "app.js",
        app_dir / "data" / "city_boundaries.geojson",
        app_dir / "data" / "city_metrics.json",
        app_dir / "data" / "route_links.json",
        app_dir / "data" / "supporting_tables.json",
        app_dir / "data" / "summary.json",
    ]
    missing = [path.name for path in required if not path.exists()]
    if missing:
        return False, "missing: " + ", ".join(missing)
    app_js = file_text(app_dir / "app.js")
    index_html = file_text(app_dir / "index.html")
    summary = json.loads(file_text(app_dir / "data" / "summary.json"))
    has_click = "addEventListener(\"click\"" in app_js and "selectCity" in app_js
    has_fusion_layer = "Multimodal score" in index_html and "fusion_scores" in app_js
    has_true_layers = all(label in index_html for label in ["Policy-text score", "Satellite/visual score", "Process/reservoir score"]) and "component_scores" in app_js
    has_ceads_layer = "CEADs city emissions" in index_html and "ceads_history" in app_js and "ceads_history_city_count" in summary
    has_english_ui = "Click a city region" in index_html and "Recommended Pathway" in index_html and "推荐" not in index_html + app_js
    ok = has_click and summary.get("city_count", 0) >= 150 and (app_dir / "data" / "city_boundaries.geojson").stat().st_size > 500_000
    ok = ok and has_fusion_layer and has_true_layers and has_ceads_layer and has_english_ui
    return ok, f"{summary.get('city_count', 0)} cities; click handler={has_click}; fusion layer={has_fusion_layer}; true layers={has_true_layers}; CEADs layer={has_ceads_layer}; English UI={has_english_ui}; boundary bytes={(app_dir / 'data' / 'city_boundaries.geojson').stat().st_size}"


def frontier_ok() -> tuple[bool, str]:
    path = ROOT / "output" / "china2060_frontier_upgrade" / "buildout_frontier.csv"
    rows = read_csv(path)
    target_1000 = [
        row for row in rows
        if int(row["year"]) == 2060
        and row["scenario"] == "policy_supported_effort"
        and row["frontier_target_label"] == "durable_1000_mt"
    ]
    target_500 = [
        row for row in rows
        if int(row["year"]) == 2060
        and row["scenario"] == "policy_supported_effort"
        and row["frontier_target_label"] == "durable_500_mt"
    ]
    ok = bool(rows) and target_1000 and int(target_1000[0]["success"]) == 0 and target_500 and int(target_500[0]["success"]) == 1
    return ok, f"{len(rows)} frontier rows; 500Mt feasible={target_500[0]['success'] if target_500 else 'missing'}; 1000Mt feasible={target_1000[0]['success'] if target_1000 else 'missing'}"


def city_archetypes_ok() -> tuple[bool, str]:
    rows = read_csv(ROOT / "output" / "china2060_city_archetypes" / "city_archetypes_by_year.csv")
    rows_2060 = [row for row in rows if int(row["year"]) == 2060]
    archetypes = {row["archetype"] for row in rows_2060}
    ceads_matched = [row for row in rows_2060 if int(f(row.get("ceads_history_match"))) == 1]
    ok = len(rows_2060) >= 100 and len(archetypes) >= 4 and len(ceads_matched) >= 100
    return ok, f"{len(rows_2060)} 2060 cities, {len(archetypes)} archetypes, {len(ceads_matched)} with CEADs history"


def market_stress_ok() -> tuple[bool, str]:
    stress = read_csv(ROOT / "output" / "china2060_market_stress" / "market_stress_summary.csv")
    eor = read_csv(ROOT / "output" / "china2060_market_stress" / "eor_oil_price_sensitivity.csv")
    scenarios = {row["scenario"] for row in stress}
    eor_2060 = [row for row in eor if int(row["year"]) == 2060]
    eor_durable_zero = all(f(row["durable_allocated_mtco2_per_year"]) == 0.0 for row in eor_2060)
    ok = len(scenarios) >= 7 and eor_durable_zero
    return ok, f"{len(scenarios)} stress scenarios; EOR durable zero={eor_durable_zero}"


def uncertainty_ok() -> tuple[bool, str]:
    rows = read_csv(ROOT / "output" / "china2060_deployment_optimization" / "uncertainty_positive_probability.csv")
    drivers = read_csv(ROOT / "output" / "china2060_deployment_optimization" / "uncertainty_driver_rank.csv")
    ok = len(rows) >= 10 and len(drivers) >= 30
    return ok, f"{len(rows)} probability rows; {len(drivers)} driver rows"


def model_extension_ok() -> tuple[bool, str]:
    required = [
        "output/china2060_frontier_upgrade/policy_roi_summary.csv",
        "output/china2060_frontier_upgrade/product_saturation_curves.csv",
        "output/china2060_frontier_upgrade/storage_wellfield_pressure_proxy.csv",
        "output/china2060_frontier_upgrade/saf_transparent_process_cases.csv",
        "output/china2060_frontier_upgrade/robust_portfolio_scores.csv",
    ]
    missing = [path for path in required if not exists(path)]
    return not missing, "missing: " + ", ".join(missing) if missing else "all frontier extension outputs exist"


def submission_upgrade_v2_ok() -> tuple[bool, str]:
    folder = ROOT / "output" / "submission_upgrade_v2"
    required = [
        folder / "industrial_source_balance_v2.csv",
        folder / "industrial_source_targets_v2.csv",
        folder / "saf_process_upgrade_requirements_v2.csv",
        folder / "saf_price_process_cases_v2.csv",
        folder / "product_market_upgrade_requirements_v2.csv",
        folder / "product_market_capacity_v2.csv",
        folder / "storage_simulation_queue_v2.csv",
        folder / "storage_pressure_screen_v2.csv",
        folder / "revision_closure_gate_v2.csv",
        folder / "evidence_sources_v2.csv",
        ROOT / "data" / "catalog" / "real_data_source_registry_v3.csv",
        ROOT / "data" / "processed" / "markets" / "product_trade_unit_values_wits_2024.csv",
        ROOT / "data" / "processed" / "markets" / "open_product_price_observations_v3.csv",
        ROOT / "data" / "processed" / "saf" / "saf_real_data_replacements_v3.csv",
        ROOT / "data" / "processed" / "storage" / "reservoir_simulation_source_registry_v3.csv",
        ROOT / "data" / "raw" / "co2_sources" / "CEADs_2022_30_province_emission_inventory.xlsx",
        ROOT / "data" / "raw" / "co2_sources" / "CEADs_2022_province_energy_inventory_en.xlsx",
        ROOT / "data" / "raw" / "co2_sources" / "CEADs_1997_2022_apparent_emission_inventory.xlsx",
        ROOT / "data" / "raw" / "co2_sources" / "CEADs_1997_2019_290_city_emission_inventory.xlsx",
        ROOT / "data" / "raw" / "co2_sources" / "CEADs_2010_24_city_45_sector_production_inventory.zip",
        ROOT / "data" / "processed" / "co2_sources" / "ceads_2022_province_model_source_totals.csv",
        ROOT / "data" / "processed" / "co2_sources" / "source_inventory_calibration_ceads_2022.csv",
        ROOT / "data" / "processed" / "co2_sources" / "ceads_2022_province_energy_long.csv",
        ROOT / "data" / "processed" / "co2_sources" / "ceads_1997_2022_apparent_total_by_province.csv",
        ROOT / "data" / "processed" / "co2_sources" / "ceads_1997_2019_city_emissions_long.csv",
        ROOT / "data" / "processed" / "co2_sources" / "ceads_2019_city_emissions_for_prefecture_join.csv",
        ROOT / "data" / "processed" / "co2_sources" / "ceads_2010_24_city_sector_file_registry.csv",
        ROOT / "data" / "processed" / "co2_sources" / "ceads_2010_24_city_sector_emissions_long.csv",
        ROOT / "data" / "processed" / "co2_sources" / "ceads_city_prefecture_crosswalk.csv",
        ROOT / "data" / "processed" / "co2_sources" / "ceads_city_emissions_prefecture_long.csv",
        ROOT / "data" / "processed" / "co2_sources" / "ceads_city_emissions_prefecture_summary.csv",
        ROOT / "data" / "processed" / "co2_sources" / "ceads_city_emission_lp_caps.csv",
        DOCS / "submission_upgrade_v2_summary.md",
        DOCS / "real_data_search_v3_summary.md",
        DOCS / "ceads_2022_inventory_summary.md",
        DOCS / "ceads_additional_data_summary.md",
        DOCS / "ceads_city_crosswalk_summary.md",
    ]
    missing = [path.name for path in required if not path.exists()]
    if missing:
        return False, "missing: " + ", ".join(missing)
    source_rows = read_csv(folder / "industrial_source_balance_v2.csv")
    source_target_rows = read_csv(folder / "industrial_source_targets_v2.csv")
    saf_rows = read_csv(folder / "saf_process_upgrade_requirements_v2.csv")
    saf_price_rows = read_csv(folder / "saf_price_process_cases_v2.csv")
    market_rows = read_csv(folder / "product_market_upgrade_requirements_v2.csv")
    market_capacity_rows = read_csv(folder / "product_market_capacity_v2.csv")
    storage_rows = read_csv(folder / "storage_simulation_queue_v2.csv")
    pressure_rows = read_csv(folder / "storage_pressure_screen_v2.csv")
    gate_rows = read_csv(folder / "revision_closure_gate_v2.csv")
    evidence_rows = read_csv(folder / "evidence_sources_v2.csv")
    real_registry_rows = read_csv(ROOT / "data" / "catalog" / "real_data_source_registry_v3.csv")
    trade_rows = read_csv(ROOT / "data" / "processed" / "markets" / "product_trade_unit_values_wits_2024.csv")
    price_v3_rows = read_csv(ROOT / "data" / "processed" / "markets" / "open_product_price_observations_v3.csv")
    saf_v3_rows = read_csv(ROOT / "data" / "processed" / "saf" / "saf_real_data_replacements_v3.csv")
    reservoir_v3_rows = read_csv(ROOT / "data" / "processed" / "storage" / "reservoir_simulation_source_registry_v3.csv")
    ceads_model_rows = read_csv(ROOT / "data" / "processed" / "co2_sources" / "ceads_2022_province_model_source_totals.csv")
    ceads_calibration_rows = read_csv(ROOT / "data" / "processed" / "co2_sources" / "source_inventory_calibration_ceads_2022.csv")
    ceads_energy_rows = read_csv(ROOT / "data" / "processed" / "co2_sources" / "ceads_2022_province_energy_long.csv")
    ceads_apparent_total_rows = read_csv(ROOT / "data" / "processed" / "co2_sources" / "ceads_1997_2022_apparent_total_by_province.csv")
    ceads_city_rows = read_csv(ROOT / "data" / "processed" / "co2_sources" / "ceads_1997_2019_city_emissions_long.csv")
    ceads_city_join_rows = read_csv(ROOT / "data" / "processed" / "co2_sources" / "ceads_2019_city_emissions_for_prefecture_join.csv")
    ceads_24_registry_rows = read_csv(ROOT / "data" / "processed" / "co2_sources" / "ceads_2010_24_city_sector_file_registry.csv")
    ceads_24_emission_rows = read_csv(ROOT / "data" / "processed" / "co2_sources" / "ceads_2010_24_city_sector_emissions_long.csv")
    ceads_crosswalk_rows = read_csv(ROOT / "data" / "processed" / "co2_sources" / "ceads_city_prefecture_crosswalk.csv")
    ceads_crosswalk_unmatched_rows = [row for row in ceads_crosswalk_rows if row.get("match_status") != "matched"]
    ceads_prefecture_summary_rows = read_csv(ROOT / "data" / "processed" / "co2_sources" / "ceads_city_emissions_prefecture_summary.csv")
    ceads_city_cap_rows = read_csv(ROOT / "data" / "processed" / "co2_sources" / "ceads_city_emission_lp_caps.csv")
    cement = next((row for row in source_rows if row.get("sector") == "cement"), None)
    cement_exposed = bool(cement) and f(cement.get("coverage_ratio_current_to_base"), 1.0) < 0.05
    cement_target = next((row for row in source_target_rows if row.get("sector") == "cement"), None)
    cement_multiplier_high = bool(cement_target) and f(cement_target.get("calibration_multiplier_to_base")) > 10.0
    fossil_price = next((row for row in saf_price_rows if row.get("case_id") == "FOSSIL_JET_BENCHMARK_CURRENT"), None)
    saf_price_separated = bool(fossil_price) and f(fossil_price.get("commodity_or_process_value")) > 0.0
    observed_capacity_count = sum(
        1 for row in market_capacity_rows if f(row.get("observed_capacity_t_product_per_year")) > 0.0
    )
    pressure_screened = len(pressure_rows) >= 15 and max(
        [f(row.get("proxy_min_well_count")) for row in pressure_rows] or [0.0]
    ) >= 20.0
    has_wits_proxy = len(trade_rows) >= 4 and all(f(row.get("unit_value_usd_per_kg")) > 0 for row in trade_rows)
    price_products = {row.get("product") for row in price_v3_rows}
    has_price_spread = {
        "methanol",
        "fossil_jet_fuel_benchmark",
        "ethylene",
        "formic_acid_equivalent",
        "carbonate_product",
        "methane",
        "carbon_monoxide",
        "sustainable_aviation_fuel",
    }.issubset(price_products)
    has_saf_real_sources = len(saf_v3_rows) >= 5 and any(row.get("status") == "downloaded" for row in saf_v3_rows)
    has_reservoir_tools = len(reservoir_v3_rows) >= 5 and any(row.get("status") == "manual_downloaded" for row in reservoir_v3_rows)
    ceads_registry_downloaded = any(
        row.get("gap") == "industrial_source_inventory" and row.get("status") == "downloaded_processed"
        for row in real_registry_rows
    )
    ceads_source_types = {row.get("source_type") for row in ceads_model_rows}
    has_ceads_mapping = len(ceads_model_rows) >= 200 and {"coal_power", "steel", "cement", "lime", "chemicals"}.issubset(ceads_source_types)
    max_ceads_multiplier = max([f(row.get("calibration_multiplier")) for row in ceads_calibration_rows] or [0.0])
    has_ceads_calibration = len(ceads_calibration_rows) >= 50 and max_ceads_multiplier > 2.0
    has_ceads_additional = (
        len(ceads_energy_rows) >= 14000
        and len(ceads_apparent_total_rows) >= 780
        and len(ceads_city_rows) >= 3900
        and len(ceads_city_join_rows) >= 150
        and len(ceads_24_registry_rows) >= 24
        and len(ceads_24_emission_rows) >= 6000
        and len(ceads_crosswalk_rows) >= 290
        and not ceads_crosswalk_unmatched_rows
        and len(ceads_prefecture_summary_rows) >= 250
        and len(ceads_city_cap_rows) >= 240
    )
    has_high_risk_gate = any(row.get("major_revision_risk_if_failed") == "high" for row in gate_rows)
    ok = (
        len(source_rows) >= 8
        and len(source_target_rows) >= 2
        and len(saf_rows) >= 5
        and len(saf_price_rows) >= 5
        and len(market_rows) >= 7
        and len(market_capacity_rows) >= 7
        and len(storage_rows) >= 15
        and pressure_screened
        and len(gate_rows) >= 7
        and len(evidence_rows) >= 6
        and len(real_registry_rows) >= 7
        and cement_exposed
        and cement_multiplier_high
        and saf_price_separated
        and observed_capacity_count >= 3
        and has_wits_proxy
        and has_price_spread
        and has_saf_real_sources
        and has_reservoir_tools
        and ceads_registry_downloaded
        and has_ceads_mapping
        and has_ceads_calibration
        and has_ceads_additional
        and has_high_risk_gate
    )
    return ok, (
        f"{len(source_rows)} source rows; {len(source_target_rows)} source targets; "
        f"{len(saf_rows)} SAF rows; {len(saf_price_rows)} SAF price/process rows; "
        f"{len(market_rows)} market rows; {len(market_capacity_rows)} capacity rows; "
        f"{len(storage_rows)} storage rows; {len(pressure_rows)} pressure rows; "
        f"{len(evidence_rows)} evidence sources; {len(real_registry_rows)} V3 real-data rows; "
        f"cement gap={cement_exposed}; "
        f"cement multiplier high={cement_multiplier_high}; SAF price separated={saf_price_separated}; "
        f"observed product capacities={observed_capacity_count}; pressure screened={pressure_screened}; "
        f"WITS proxies={has_wits_proxy}; price spread={has_price_spread}; "
        f"SAF real sources={has_saf_real_sources}; reservoir tools={has_reservoir_tools}; "
        f"CEADs downloaded={ceads_registry_downloaded}; CEADs mapping={has_ceads_mapping}; "
        f"CEADs calibration={has_ceads_calibration}; max CEADs multiplier={max_ceads_multiplier:.2f}; "
        f"CEADs additional={has_ceads_additional} "
        f"(energy {len(ceads_energy_rows)}, apparent totals {len(ceads_apparent_total_rows)}, "
        f"city rows {len(ceads_city_rows)}, 2019 city rows {len(ceads_city_join_rows)}, "
        f"24-city registry {len(ceads_24_registry_rows)}, 24-city emissions {len(ceads_24_emission_rows)}, "
        f"crosswalk {len(ceads_crosswalk_rows)}, unmatched {len(ceads_crosswalk_unmatched_rows)}, "
        f"prefecture summaries {len(ceads_prefecture_summary_rows)}, LP caps {len(ceads_city_cap_rows)}); "
        f"high-risk gates={has_high_risk_gate}"
    )


def multimodal_ok() -> tuple[bool, str]:
    folder = ROOT / "output" / "multimodal_evidence_layer"
    required = [
        folder / "modality_manifest.csv",
        folder / "city_multimodal_features.csv",
        folder / "city_multimodal_scores.csv",
        folder / "city_modality_contributions.csv",
        folder / "pathway_multimodal_summary.csv",
        folder / "multimodal_upgrade_gaps.csv",
        folder / "fusion_architecture.csv",
        folder / "multimodal_evidence_key_findings.md",
    ]
    true_required = [
        TRUE_MM / "policy_text_embeddings.csv",
        TRUE_MM / "city_policy_embedding_features.csv",
        TRUE_MM / "city_visual_remote_sensing_features.csv",
        TRUE_MM / "city_process_flowsheet_features.csv",
        TRUE_MM / "city_reservoir_simulator_features.csv",
        TRUE_MM / "city_true_multimodal_feature_inputs.csv",
        TRUE_MM / "source_registry.csv",
    ]
    missing = [path.name for path in required + true_required if not path.exists()]
    if missing:
        return False, "missing: " + ", ".join(missing)
    manifest = read_csv(folder / "modality_manifest.csv")
    features = read_csv(folder / "city_multimodal_scores.csv")
    contributions = read_csv(folder / "city_modality_contributions.csv")
    pathways = read_csv(folder / "pathway_multimodal_summary.csv")
    architecture = read_csv(folder / "fusion_architecture.csv")
    true_features = read_csv(TRUE_MM / "city_true_multimodal_feature_inputs.csv")
    policy_embeddings = read_csv(TRUE_MM / "policy_text_embeddings.csv")
    selected = [row for row in features if f(row["allocated_mtco2_per_year"]) > 0]
    required_score_cols = [
        "fusion_near_term_profit_score",
        "fusion_2060_neutrality_backbone_score",
        "fusion_policy_exit_resilience_score",
        "fusion_data_quality_priority_score",
    ]
    has_scores = bool(features) and all(column in features[0] for column in required_score_cols)
    required_true_cols = [
        "feature_policy_text_score",
        "feature_visual_remote_sensing_score",
        "feature_process_flowsheet_score",
        "feature_reservoir_simulation_score",
    ]
    has_true_feature_scores = bool(features) and all(column in features[0] for column in required_true_cols)
    ok = (
        len(manifest) >= 7
        and len(features) >= 150
        and len(selected) >= 10
        and len(contributions) >= 7000
        and len(pathways) >= 3
        and len(architecture) >= 5
        and len(true_features) >= 150
        and len(policy_embeddings) >= 5
        and has_scores
        and has_true_feature_scores
    )
    return ok, f"{len(manifest)} modalities; {len(features)} city scores; {len(contributions)} contributions; {len(true_features)} true multimodal rows; {len(selected)} LP-selected cities"


def old_review_risks_ok() -> tuple[bool, str]:
    spatial = file_text(SRC / "spatial.py")
    realdata = file_text(SRC / "realdata.py")
    cli = file_text(SRC / "cli.py")
    checks = {
        "spatial_transport_zeroed": "co2_transport_distance_km=0.0" in spatial and "co2_transport_cost_usd_per_tkm=0.0" in spatial,
        "lp_target_constraints": "target_total_mtco2_per_year" in spatial and "target_source_fraction" in spatial and "a_eq.append" in spatial,
        "policy_source_cli": "--policy-source" in cli and "_apply_policy_source" in cli,
        "exchange_rate_proxy": "exchange_rate_cny_per_usd" in realdata and "return cny_per_kwh * 1000.0 / exchange_rate_cny_per_usd" in realdata,
    }
    ok = all(checks.values())
    failed = [key for key, value in checks.items() if not value]
    return ok, "failed: " + ", ".join(failed) if failed else "old P1/P2 review risks have code-level mitigations"


def docs_ok() -> tuple[bool, str]:
    required = [
        DOCS / "manuscript.md",
        DOCS / "supplemental_information.md",
        DOCS / "figure_captions.md",
        DOCS / "reproducibility.md",
        DOCS / "literature_benchmark.md",
        DOCS / "next_model_and_figure_upgrade_plan.md",
        DOCS / "model_reasonableness_audit.md",
        DOCS / "submission_upgrade_v2_summary.md",
    ]
    missing = [str(path.name) for path in required if not path.exists()]
    text = "\n".join(file_text(path) for path in required if path.exists())
    keywords = [
        "policy",
        "Monte Carlo",
        "LP",
        "EOR",
        "durable",
        "market",
        "storage",
        "SAF",
        "multimodal",
        "CEADs city",
        "policy-text",
        "remote-sensing",
        "reservoir",
        "source inventory",
    ]
    lower_text = text.lower()
    ok = not missing and all(keyword.lower() in lower_text for keyword in keywords)
    return ok, "missing docs: " + ", ".join(missing) if missing else "core docs include policy/LP/Monte Carlo/EOR/durable/market/storage/SAF/multimodal/CEADs city"


def score() -> tuple[int, list[dict[str, Any]], list[str]]:
    failures: list[str] = []
    rows: list[dict[str, Any]] = []
    checks = [
        (*old_review_risks_ok(), "Old review findings mitigated", 10),
        (*city_archetypes_ok(), "City archetype classifier complete", 10),
        (*frontier_ok(), "Buildout frontier and durable target optimization complete", 15),
        (*model_extension_ok(), "Policy ROI, demand saturation, storage proxy, SAF process, robust analysis complete", 12),
        (*market_stress_ok(), "Policy-exit, shock and EOR accounting complete", 10),
        (*uncertainty_ok(), "Monte Carlo uncertainty and driver ranking complete", 10),
        (*storyline_figures_ok(), "Redesigned storyline figures complete", 13),
        (*composite_figures_ok(), "Original composite figure set retained", 3),
        (*interactive_map_ok(), "Interactive city map app complete", 2),
        (*multimodal_ok(), "Multimodal evidence-fusion layer complete", 5),
        (*submission_upgrade_v2_ok(), "Submission-upgrade v2 closure gates complete", 5),
        (*docs_ok(), "Manuscript, SI, captions and reproducibility updated", 5),
    ]
    for ok, evidence, name, points in checks:
        rows.append(check(ok, name, points, evidence, failures))
    total = sum(int(row["points_awarded"]) for row in rows)
    return total, rows, failures


def write_markdown(total: int, rows: list[dict[str, Any]], failures: list[str]) -> None:
    status = "PASS" if total == 100 else "FAIL"
    lines = [
        "# Automated Internal Review Gate",
        "",
        f"Score: **{total}/100**",
        f"Status: **{status}**",
        "",
        "| Check | Points | Pass | Evidence |",
        "|---|---:|---:|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row['check']} | {row['points_awarded']}/{row['points_possible']} | {row['pass']} | {row['evidence']} |"
        )
    if failures:
        lines.extend(["", "## Failures", ""])
        lines.extend(f"- {failure}" for failure in failures)
    else:
        lines.extend(
            [
                "",
                "## Gate Interpretation",
                "",
                "The package passes the internal 100-point gate. This means the requested model upgrades, figure logic, stress tests, optimization, uncertainty treatment and review-risk mitigations are present and machine-checked. It does not mean the paper is guaranteed to be accepted by a journal.",
            ]
        )
    (OUT / "internal_review_scorecard.md").write_text("\n".join(lines), encoding="utf-8")
    (DOCS / "internal_review_scorecard.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    total, rows, failures = score()
    write_csv(OUT / "internal_review_scorecard.csv", rows)
    (OUT / "internal_review_score.json").write_text(
        json.dumps({"score": total, "pass": total == 100, "failures": failures, "checks": rows}, indent=2),
        encoding="utf-8",
    )
    write_markdown(total, rows, failures)
    print(f"Internal review gate score: {total}/100")
    if total != 100:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
