"""Build reviewer-facing upgrade tables for the next submission pass.

This script does not change the profitability run directly. It creates the
interfaces needed to replace C/D assumptions with auditable data for the four
largest remaining weaknesses: industrial source closure, SAF TEA/process
evidence, product-market capacity, and storage reservoir simulation.
"""

from __future__ import annotations

import csv
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = ROOT / "output" / "submission_upgrade_v2"
DOC_OUT = ROOT / "docs" / "joule_submission" / "submission_upgrade_v2_summary.md"

SOURCES = DATA / "real_inputs_top300_with_dac" / "spatial_sources_real.csv"
DESTINATIONS = DATA / "real_inputs_top300_with_dac" / "spatial_destinations_real.csv"
MARKETS = DATA / "processed" / "markets" / "city_product_market_capacity_screening_2023.csv"
SAF_CASES = DATA / "saf_process_cases.csv"
STORAGE_PARAMS = DATA / "storage_reservoir_screening_parameters.csv"
PRICE_OBSERVATIONS = DATA / "processed" / "markets" / "open_product_price_observations.csv"
CAPACITY_OBSERVATIONS = DATA / "processed" / "markets" / "open_product_capacity_observations.csv"


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
        if value in ("", None):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def source_mix() -> dict[str, float]:
    totals: dict[str, float] = defaultdict(float)
    for row in read_csv(SOURCES):
        totals[row["source_type"]] += f(row.get("co2_available_mtpa"))
    return totals


def industrial_source_balance_rows() -> list[dict[str, Any]]:
    totals = source_mix()
    rows: list[dict[str, Any]] = []

    cement_output_mt = 1825.24
    cement_low = cement_output_mt * 0.45
    cement_base = cement_output_mt * 0.55
    cement_high = cement_output_mt * 0.65
    current_cement = totals.get("cement", 0.0)
    rows.append(
        {
            "sector": "cement",
            "current_model_available_mtco2_per_year": round(current_cement, 3),
            "national_activity_anchor": "China cement output 2024",
            "activity_value": cement_output_mt,
            "activity_unit": "Mt cement/year",
            "co2_factor_low_tco2_per_t_activity": 0.45,
            "co2_factor_base_tco2_per_t_activity": 0.55,
            "co2_factor_high_tco2_per_t_activity": 0.65,
            "implied_co2_low_mt_per_year": round(cement_low, 1),
            "implied_co2_base_mt_per_year": round(cement_base, 1),
            "implied_co2_high_mt_per_year": round(cement_high, 1),
            "coverage_ratio_current_to_base": round(current_cement / cement_base, 5) if cement_base else "",
            "priority": "P0",
            "recommended_action": "Rebuild cement source layer from clinker/cement assets and calibrate to NBS or industry annual totals.",
            "source_url": "https://www.ccement.com/news/content/57080305714285001.html",
            "evidence_grade_after_upgrade": "B if official/industry total is paired with asset-level allocation",
        }
    )

    sector_actions = {
        "steel": "Calibrate GEM iron/steel assets to crude steel, pig iron, and EAF/BOF route totals.",
        "chemicals": "Split chemicals into methanol, ammonia, ethylene, refinery hydrogen, coal chemicals, and process-specific CO2 purity classes.",
        "coal_power": "Calibrate plant emissions to unit-level generation, heat rate, capacity factor, retirement, and post-2030 dispatch.",
        "gas_power": "Calibrate to gas generation and utilization; keep separate from industrial high-purity CO2.",
        "aluminum": "Check whether listed CO2 is direct process emissions, power-related emissions, or inventory artifact before capture modeling.",
        "lime": "Reconcile lime process emissions and kiln locations with cement/mineralization feedstock demand.",
        "dac": "Replace fixed DAC hubs with renewable-resource, water, heat, land, and storage-paired siting model.",
    }
    for sector, action in sector_actions.items():
        rows.append(
            {
                "sector": sector,
                "current_model_available_mtco2_per_year": round(totals.get(sector, 0.0), 3),
                "national_activity_anchor": "to_be_added",
                "activity_value": "",
                "activity_unit": "",
                "co2_factor_low_tco2_per_t_activity": "",
                "co2_factor_base_tco2_per_t_activity": "",
                "co2_factor_high_tco2_per_t_activity": "",
                "implied_co2_low_mt_per_year": "",
                "implied_co2_base_mt_per_year": "",
                "implied_co2_high_mt_per_year": "",
                "coverage_ratio_current_to_base": "",
                "priority": "P0" if sector in {"steel", "chemicals", "coal_power"} else "P1",
                "recommended_action": action,
                "source_url": "NBS/CEADs/GEM/Climate TRACE/industry yearbook",
                "evidence_grade_after_upgrade": "B after source-specific reconciliation",
            }
        )
    return rows


def industrial_source_targets_v2_rows() -> list[dict[str, Any]]:
    totals = source_mix()
    return [
        {
            "sector": "cement",
            "target_year": 2024,
            "activity_anchor": "national cement output",
            "activity_value": 1825.24,
            "activity_unit": "Mt cement/year",
            "co2_factor_low": 0.45,
            "co2_factor_base": 0.55,
            "co2_factor_high": 0.65,
            "capture_rate_for_available_co2": 0.90,
            "target_available_low_mtco2_per_year": round(1825.24 * 0.45 * 0.90, 1),
            "target_available_base_mtco2_per_year": round(1825.24 * 0.55 * 0.90, 1),
            "target_available_high_mtco2_per_year": round(1825.24 * 0.65 * 0.90, 1),
            "current_available_mtco2_per_year": round(totals.get("cement", 0.0), 3),
            "calibration_multiplier_to_base": round((1825.24 * 0.55 * 0.90) / max(totals.get("cement", 0.0), 1e-9), 3),
            "data_source": "NBS-reported 2024 national cement output via China Cement Network/Mysteel; replace with direct NBS API/table if available",
            "source_url": "https://www.ccement.com/news/content/57080305714285001.html",
            "evidence_grade": "B for national total; C for emission-factor range until clinker ratio is added",
            "model_use": "Use only as top-down closure target until plant-level clinker/cement assets are allocated.",
        },
        {
            "sector": "civil_aviation_saf_demand",
            "target_year": 2024,
            "activity_anchor": "CAAC transport turnover and airport throughput",
            "activity_value": 1485.17,
            "activity_unit": "100 million tonne-km",
            "co2_factor_low": "",
            "co2_factor_base": "",
            "co2_factor_high": "",
            "capture_rate_for_available_co2": "",
            "target_available_low_mtco2_per_year": "",
            "target_available_base_mtco2_per_year": "",
            "target_available_high_mtco2_per_year": "",
            "current_available_mtco2_per_year": "",
            "calibration_multiplier_to_base": "",
            "data_source": "CAAC 2024 Civil Aviation Industry Development Statistical Bulletin",
            "source_url": "https://www.caac.gov.cn/XXGK/XXGK/TJSJ/202505/P020250515367555717699.pdf",
            "evidence_grade": "B for activity; fuel demand requires energy-statistics conversion",
            "model_use": "Use to allocate SAF demand spatially; do not infer fuel consumption without a documented intensity.",
        },
    ]


def saf_process_upgrade_rows() -> list[dict[str, Any]]:
    current = read_csv(SAF_CASES) if SAF_CASES.exists() else []
    rows: list[dict[str, Any]] = [
        {
            "case_id": "LITERATURE_FT_MTJ_ASPEN_2024",
            "pathway": "co2_h2_ft_saf;co2_methanol_to_jet_saf",
            "model_type": "Aspen Plus literature benchmark",
            "status": "benchmark_to_digitize",
            "reported_cost_usd_per_kg_saf_low": "",
            "reported_cost_usd_per_kg_saf_high": "",
            "reported_carbon_efficiency": "about 0.90",
            "reported_energy_efficiency": "about 0.40",
            "required_model_fields": "CO2,H2,electricity,heat,product_slate,CAPEX,OPEX,recycle,separations,carbon_balance,energy_balance",
            "source_url": "https://www.sciencedirect.com/science/article/pii/S0196890424006691",
            "evidence_grade": "B after data extraction",
            "notes": "Use to replace reduced-order FT and MTJ mass/energy balances.",
        },
        {
            "case_id": "HARMONIZED_PTL_SAF_TEA_2026",
            "pathway": "FTS;MtJ-1;MtJ-2;EtJ",
            "model_type": "Aspen Plus plus custom TEA literature benchmark",
            "status": "benchmark_to_digitize",
            "reported_cost_usd_per_kg_saf_low": 2.8,
            "reported_cost_usd_per_kg_saf_high": 8.2,
            "reported_carbon_efficiency": "0.42-0.63 by route",
            "reported_energy_efficiency": "0.48-0.54 for alcohol routes, about 0.50 for FTS",
            "required_model_fields": "regional electricity,H2 CAPEX share,route-specific NPC,product slate,certification boundary",
            "source_url": "https://www.sciencedirect.com/science/article/pii/S001623612600774X",
            "evidence_grade": "B/C after checking supplementary data",
            "notes": "Use as cost-range guardrail; do not mix with policy-backed offtake price.",
        },
        {
            "case_id": "NREL_FT_SAF_82703",
            "pathway": "biomass_or_hybrid_ft_saf",
            "model_type": "NREL benchmark report",
            "status": "benchmark_to_digitize",
            "reported_cost_usd_per_kg_saf_low": "",
            "reported_cost_usd_per_kg_saf_high": "",
            "reported_carbon_efficiency": "",
            "reported_energy_efficiency": "",
            "required_model_fields": "FT product slate,upgrading,yield,CAPEX,OPEX,feedstock sensitivity",
            "source_url": "https://www.nrel.gov/docs/fy22osti/82703.pdf",
            "evidence_grade": "B",
            "notes": "Use as sanity check for FT upgrading and fuel-slate assumptions.",
        },
    ]
    for row in current:
        rows.append(
            {
                "case_id": row.get("case_id"),
                "pathway": row.get("pathway"),
                "model_type": row.get("model_type"),
                "status": "current_internal_case",
                "reported_cost_usd_per_kg_saf_low": "",
                "reported_cost_usd_per_kg_saf_high": "",
                "reported_carbon_efficiency": "",
                "reported_energy_efficiency": "",
                "required_model_fields": "replace_or_recalibrate",
                "source_url": row.get("source", ""),
                "evidence_grade": row.get("evidence_grade", ""),
                "notes": row.get("notes", ""),
            }
        )
    return rows


def saf_price_process_cases_v2_rows() -> list[dict[str, Any]]:
    price_rows = read_csv(PRICE_OBSERVATIONS) if PRICE_OBSERVATIONS.exists() else []
    fossil_jet = next(
        (
            row for row in price_rows
            if row.get("product") in {"jet_fuel", "fossil_jet_fuel_benchmark"}
        ),
        None,
    )
    fossil_jet_year = ""
    if fossil_jet:
        fossil_jet_year = fossil_jet.get("year") or fossil_jet.get("observation_date", "")[:4]
    return [
        {
            "case_id": "CAAC_ACTIVITY_2024",
            "case_type": "demand_anchor",
            "pathway": "sustainable_aviation_fuel",
            "year": 2024,
            "commodity_or_process_value": "transport turnover 1485.17 hundred-million tonne-km; airport throughput 1.460 billion passengers",
            "unit": "activity",
            "evidence_grade": "B",
            "source": "CAAC 2024 statistical bulletin",
            "source_url": "https://www.caac.gov.cn/XXGK/XXGK/TJSJ/202505/P020250515367555717699.pdf",
            "model_action": "Allocate SAF market capacity by airport/city activity; add official fuel consumption or documented fuel-intensity conversion before final volume claims.",
        },
        {
            "case_id": "FOSSIL_JET_BENCHMARK_CURRENT",
            "case_type": "commodity_price",
            "pathway": "sustainable_aviation_fuel",
            "year": fossil_jet_year or "2026",
            "commodity_or_process_value": fossil_jet.get("converted_usd_per_kg", "") if fossil_jet else "",
            "unit": "USD/kg",
            "evidence_grade": fossil_jet.get("evidence_grade", "B/C") if fossil_jet else "missing",
            "source": fossil_jet.get("source_name", "open price observation table") if fossil_jet else "missing",
            "source_url": fossil_jet.get("source_url", "") if fossil_jet else "",
            "model_action": "Use as fossil parity floor; never use as SAF premium price.",
        },
        {
            "case_id": "PTL_FT_MTJ_ASPEN_EYBERG_2024",
            "case_type": "process_benchmark",
            "pathway": "co2_h2_ft_saf;co2_methanol_to_jet_saf",
            "year": 2024,
            "commodity_or_process_value": "Aspen Plus V12; optimized configurations raise carbon efficiency toward about 90% and energy efficiency toward about 40%",
            "unit": "process benchmark",
            "evidence_grade": "B",
            "source": "Eyberg et al., Energy Conversion and Management 315, 118728",
            "source_url": "https://doi.org/10.1016/j.enconman.2024.118728",
            "model_action": "Digitize process table or request data; replace reduced-order FT/MtJ balances before strong SAF margin claim.",
        },
        {
            "case_id": "NREL_FT_SAF_82703",
            "case_type": "process_benchmark",
            "pathway": "ft_saf;co2_to_saf",
            "year": 2022,
            "commodity_or_process_value": "Aspen-based TEA/LCA benchmark; DAC CO2 to FT fuel flagged as energy intensive and lower TRL",
            "unit": "process benchmark",
            "evidence_grade": "B",
            "source": "NREL/PR-5100-82703",
            "source_url": "https://www.nrel.gov/docs/fy22osti/82703.pdf",
            "model_action": "Use as sanity check for FT product slate, TRL and renewable-H2 dependence.",
        },
        {
            "case_id": "POLICY_BACKED_SAF_PREMIUM",
            "case_type": "scenario_price",
            "pathway": "sustainable_aviation_fuel",
            "year": 2030,
            "commodity_or_process_value": "separate premium curve required",
            "unit": "USD/kg premium over fossil jet",
            "evidence_grade": "C until offtake/mandate data are entered",
            "source": "policy/offtake to be added",
            "source_url": "",
            "model_action": "Keep high SAF prices in optimistic scenario only; report commodity-only and capped-premium cases.",
        },
    ]


def product_market_upgrade_rows() -> list[dict[str, Any]]:
    rows = read_csv(MARKETS) if MARKETS.exists() else []
    evidence_by_product: dict[str, Counter[str]] = defaultdict(Counter)
    capacity_by_product: dict[str, float] = defaultdict(float)
    for row in rows:
        products = [p.strip() for p in row.get("product_group", "").split(";") if p.strip()]
        share = f(row.get("capacity_mtco2_per_year")) / max(len(products), 1)
        for product in products:
            evidence_by_product[product][row.get("evidence_grade", "")] += 1
            capacity_by_product[product] += share

    product_specs = {
        "sustainable_aviation_fuel": "Airport jet-fuel demand, blending mandate, certified SAF premium, airport/refinery/port logistics.",
        "methanol": "Provincial methanol demand, MTO demand, green shipping fuel, export ports, low-carbon premium contracts.",
        "carbon_monoxide": "Local downstream chemical demand; short transport radius; colocated syngas users.",
        "formic_acid_equivalent": "Observed formic acid/formate demand and export capacity; specialty-market premium cap.",
        "ethylene": "Ethylene/polymer demand plus technology-readiness cap; do not treat as bulk CO2 sink.",
        "methane": "Gas grid demand, e-methane premium, leakage-adjusted displacement, storage/blending limits.",
        "carbonate_product": "Construction-material demand, aggregate standards, concrete plants, transport radius, certified uptake.",
    }
    out: list[dict[str, Any]] = []
    for product, action in product_specs.items():
        counts = evidence_by_product.get(product, Counter())
        out.append(
            {
                "product": product,
                "current_screened_capacity_mtco2_per_year": round(capacity_by_product.get(product, 0.0), 3),
                "current_evidence_rows": sum(counts.values()),
                "current_evidence_mix": ";".join(f"{grade}:{count}" for grade, count in sorted(counts.items())) or "none",
                "priority": "P0" if product in {"sustainable_aviation_fuel", "carbonate_product", "methanol", "carbon_monoxide"} else "P1",
                "required_real_capacity_method": action,
                "required_price_method": "Separate commodity price, certified green premium, policy credit, and saturation curve.",
                "required_outputs": "city_product_demand_real.csv;premium_capacity_by_product_region.csv;product_price_saturation_curves.csv",
                "claim_after_upgrade": "Can support city-level volume/profit claims if evidence grade reaches B or better.",
            }
        )
    return out


def product_market_capacity_v2_rows() -> list[dict[str, Any]]:
    requirements = product_market_upgrade_rows()
    capacity_rows = read_csv(CAPACITY_OBSERVATIONS) if CAPACITY_OBSERVATIONS.exists() else []
    cap_by_product = {row.get("product"): row for row in capacity_rows}
    out: list[dict[str, Any]] = []
    for row in requirements:
        product = row["product"]
        observed = cap_by_product.get(product, {})
        observed_capacity_t = f(observed.get("derived_market_capacity_t_per_year"))
        current_capacity = f(row["current_screened_capacity_mtco2_per_year"])
        out.append(
            {
                "product": product,
                "current_screened_capacity_mtco2_per_year": current_capacity,
                "observed_capacity_t_product_per_year": round(observed_capacity_t, 3) if observed_capacity_t else "",
                "observed_capacity_mt_product_per_year": round(observed_capacity_t / 1_000_000.0, 3) if observed_capacity_t else "",
                "observed_capacity_unit": "product tonnes/year" if observed_capacity_t else "",
                "observed_capacity_source": observed.get("source_name", ""),
                "observed_capacity_url": observed.get("source_url", ""),
                "observed_evidence_grade": observed.get("evidence_grade", ""),
                "market_evidence_status": row["current_evidence_mix"],
                "conservative_deployable_fraction_2030": 0.02 if product == "sustainable_aviation_fuel" else 0.05,
                "policy_case_deployable_fraction_2040": 0.10 if product == "sustainable_aviation_fuel" else 0.15,
                "policy_case_deployable_fraction_2060": 0.30 if product == "sustainable_aviation_fuel" else 0.25,
                "saturation_rule": "price premium decays after deployable fraction is exceeded; route cannot exceed observed/premium capacity",
                "next_data_action": row["required_real_capacity_method"],
                "claim_status": "screening only until observed product capacity and premium-capacity curve are populated",
            }
        )
    return out


def storage_simulation_queue_rows() -> list[dict[str, Any]]:
    destinations = read_csv(DESTINATIONS) if DESTINATIONS.exists() else []
    storage_rows = [
        row for row in destinations
        if row.get("sink_type") in {"provincial_storage", "eor_oilfield"}
    ]
    storage_rows.sort(key=lambda row: f(row.get("capacity_mtco2_per_year")), reverse=True)
    out: list[dict[str, Any]] = []
    for row in storage_rows[:25]:
        sink_type = row.get("sink_type")
        out.append(
            {
                "destination_id": row.get("destination_id"),
                "region": row.get("region"),
                "sink_type": sink_type,
                "screened_capacity_mtco2_per_year": row.get("capacity_mtco2_per_year"),
                "latitude": row.get("latitude"),
                "longitude": row.get("longitude"),
                "simulation_level_required": "Level 3 numerical" if f(row.get("capacity_mtco2_per_year")) >= 10 else "Level 2 analytical pressure screen",
                "preferred_tool": "MRST-co2lab or TOUGH3/ECO2N",
                "required_inputs": "depth,thickness,permeability,porosity,temperature,pressure,fracture_pressure,salinity,well_count,well_spacing,caprock,fault_distance",
                "required_outputs": "pressure_buildup_mpa,plume_radius_km,well_count,ramp_rate_mt_per_year,leakage_flag,seismic_risk,mrv_cost",
                "claim_after_upgrade": "May support storage buildout claim only after pressure and injectivity constraints pass.",
            }
        )
    existing = read_csv(STORAGE_PARAMS) if STORAGE_PARAMS.exists() else []
    for row in existing:
        out.append(
            {
                "destination_id": row.get("storage_id"),
                "region": row.get("region"),
                "sink_type": "existing_parameter_placeholder",
                "screened_capacity_mtco2_per_year": "",
                "latitude": "",
                "longitude": "",
                "simulation_level_required": row.get("pressure_model_type"),
                "preferred_tool": "MRST-co2lab or TOUGH3/ECO2N",
                "required_inputs": "complete missing reservoir fields",
                "required_outputs": "pressure/plume/well/MRV outputs",
                "claim_after_upgrade": row.get("notes"),
            }
        )
    return out


def storage_pressure_screen_v2_rows() -> list[dict[str, Any]]:
    queue = storage_simulation_queue_rows()
    out: list[dict[str, Any]] = []
    for row in queue:
        capacity = f(row.get("screened_capacity_mtco2_per_year"))
        if capacity <= 0:
            continue
        sink_type = row.get("sink_type")
        per_well = 0.55 if sink_type == "provincial_storage" else 0.35
        well_count = max(1, int((capacity / per_well) + 0.999))
        pressure_evidence = "C_pressure_proxy"
        if capacity >= 10:
            priority = "Level 3 numerical simulation before final claim"
        elif capacity >= 2:
            priority = "Level 2 analytical pressure screen before final claim"
        else:
            priority = "retain as low-volume screen unless selected by LP"
        out.append(
            {
                "destination_id": row.get("destination_id"),
                "region": row.get("region"),
                "sink_type": sink_type,
                "screened_capacity_mtco2_per_year": round(capacity, 4),
                "proxy_per_well_injection_mtco2_per_year": per_well,
                "proxy_min_well_count": well_count,
                "proxy_wellfield_scale_flag": "large" if well_count >= 20 else "medium" if well_count >= 5 else "small",
                "pressure_simulation_priority": priority,
                "pressure_model_evidence_grade": pressure_evidence,
                "missing_reservoir_inputs": "depth;thickness;permeability;porosity;fracture_pressure;fault_distance;caprock;salinity",
                "allowed_claim": "well-count proxy only; not a pressure-safe capacity claim",
            }
        )
    return out


def evidence_sources_v2_rows() -> list[dict[str, Any]]:
    return [
        {
            "source_id": "CEADS_2022_PROVINCE_INVENTORY",
            "source_type": "official_academic_inventory",
            "title": "CEADs 2022 30-province CO2 emission inventory",
            "url": "https://www.ceads.net.cn/data/province/",
            "used_for": "province-sector source inventory calibration",
            "evidence_grade": "A/B",
        },
        {
            "source_id": "CEADS_2022_PROVINCE_ENERGY_INVENTORY",
            "source_type": "official_academic_inventory",
            "title": "CEADs 2022 provincial energy inventory",
            "url": "https://www.ceads.net.cn/data/province/",
            "used_for": "province-sector fuel-mix and capture-energy cross-check",
            "evidence_grade": "A/B",
        },
        {
            "source_id": "CEADS_1997_2022_APPARENT_EMISSIONS",
            "source_type": "official_academic_inventory",
            "title": "CEADs 1997-2022 apparent emission inventory",
            "url": "https://www.ceads.net.cn/data/province/",
            "used_for": "provincial historical trend and peaking-date consistency checks",
            "evidence_grade": "A/B",
        },
        {
            "source_id": "CEADS_1997_2019_290_CITY_EMISSIONS",
            "source_type": "official_academic_inventory",
            "title": "CEADs 1997-2019 290-city emission inventory",
            "url": "https://www.ceads.net.cn/data/city/",
            "used_for": "city-level emission-trend validation; crosswalked to current prefecture codes for map history and non-DAC city caps",
            "evidence_grade": "A/B for inventory; B/C for current city-code join",
        },
        {
            "source_id": "CEADS_CITY_PREFECTURE_CROSSWALK",
            "source_type": "derived_crosswalk",
            "title": "CEADs 290-city labels crosswalked to DataV prefecture codes",
            "url": "derived from CEADs city inventory and public prefecture boundaries",
            "used_for": "interactive map CEADs history layer and non-DAC LP city-emission caps",
            "evidence_grade": "B for current-prefecture matches; B/C for historical/proxy labels",
        },
        {
            "source_id": "CEADS_2010_24_CITY_45_SECTOR",
            "source_type": "official_academic_inventory",
            "title": "CEADs 2010 24-city 45-sector production-based inventory",
            "url": "https://www.ceads.net.cn/data/city/",
            "used_for": "historical city-sector emission-pattern benchmark",
            "evidence_grade": "A/B for downloaded workbook; C for present-day extrapolation",
        },
        {
            "source_id": "NBS_2024_STATISTICAL_COMMUNIQUE",
            "source_type": "official_statistics",
            "title": "Statistical Communique of the People's Republic of China on the 2024 National Economic and Social Development",
            "url": "https://www.stats.gov.cn/sj/zxfb/202502/t20250228_1958817.html",
            "used_for": "macroeconomic/statistical-year framing and official data provenance",
            "evidence_grade": "A/B",
        },
        {
            "source_id": "NBS_REPORTED_CEMENT_2024_CCEMENT",
            "source_type": "official_data_republication",
            "title": "2024 national cement output reported from NBS release",
            "url": "https://www.ccement.com/news/content/57080305714285001.html",
            "used_for": "cement source-inventory closure target",
            "evidence_grade": "B until direct NBS table/API is captured",
        },
        {
            "source_id": "CAAC_2024_STATISTICAL_BULLETIN",
            "source_type": "official_statistics",
            "title": "2024 Civil Aviation Industry Development Statistical Bulletin",
            "url": "https://www.caac.gov.cn/XXGK/XXGK/TJSJ/202505/P020250515367555717699.pdf",
            "used_for": "SAF demand spatial/activity anchor",
            "evidence_grade": "B",
        },
        {
            "source_id": "EYBERG_2024_PTL_SAF",
            "source_type": "peer_reviewed_process_tea",
            "title": "Techno-economic assessment and comparison of FT and MtJ processes to produce SAF via PtL",
            "url": "https://doi.org/10.1016/j.enconman.2024.118728",
            "used_for": "SAF Aspen process benchmark",
            "evidence_grade": "B",
        },
        {
            "source_id": "NREL_82703_FT_SAF",
            "source_type": "national_lab_process_tea",
            "title": "Techno-Economic Evaluation of Strategies to Approach Net-Zero Carbon SAF via Woody Biomass Gasification and FT Synthesis",
            "url": "https://www.nrel.gov/docs/fy22osti/82703.pdf",
            "used_for": "FT SAF process and TRL sanity check",
            "evidence_grade": "B",
        },
        {
            "source_id": "CHINA_STORAGE_FIGSHARE_27646707",
            "source_type": "peer_reviewed_dataset",
            "title": "China CO2 storage potential and injection-rate dataset",
            "url": "https://doi.org/10.6084/m9.figshare.27646707",
            "used_for": "storage and EOR capacity/injectivity screen",
            "evidence_grade": "B",
        },
    ]


def closure_gate_rows() -> list[dict[str, Any]]:
    return [
        {
            "gate": "source_inventory_closure",
            "pass_threshold": "Key sector national totals within +/-10% or explicitly labeled screened network.",
            "major_revision_risk_if_failed": "high",
            "owner_output": "industrial_source_balance_v2.csv",
        },
        {
            "gate": "saf_process_and_price_separation",
            "pass_threshold": "SAF profit reported under separate commodity, premium, policy, and process-cost cases; reduced-order cases demoted.",
            "major_revision_risk_if_failed": "high",
            "owner_output": "saf_process_upgrade_requirements_v2.csv",
        },
        {
            "gate": "product_market_capacity",
            "pass_threshold": "Each positive product route has B-grade city/province demand, premium capacity, and saturation curve.",
            "major_revision_risk_if_failed": "high",
            "owner_output": "product_market_upgrade_requirements_v2.csv",
        },
        {
            "gate": "reservoir_pressure_simulation",
            "pass_threshold": "Top storage basins pass pressure/injectivity/well-count screen; 500 Mt and 1 Gt claims reference simulated capacity.",
            "major_revision_risk_if_failed": "high",
            "owner_output": "storage_simulation_queue_v2.csv",
        },
        {
            "gate": "hourly_power_h2",
            "pass_threshold": "Electrochemical/SAF/methanol windows include hourly clean-power and hydrogen flexibility sensitivity.",
            "major_revision_risk_if_failed": "medium",
            "owner_output": "future module",
        },
        {
            "gate": "policy_eligibility_audit",
            "pass_threshold": "Durable removal, ETS/CCER, SAF and green-product credits are route/location qualified.",
            "major_revision_risk_if_failed": "medium",
            "owner_output": "future module",
        },
        {
            "gate": "claim_lock",
            "pass_threshold": "Main claims are conditional frontier claims, not universal profitability claims.",
            "major_revision_risk_if_failed": "low if wording is maintained",
            "owner_output": "manuscript and SI",
        },
    ]


def write_summary() -> None:
    text = """# Submission Upgrade V2 Summary

This upgrade layer turns the largest remaining reviewer risks into explicit
data interfaces. It does not claim that all gaps are already solved.

Generated outputs:

- `output/submission_upgrade_v2/industrial_source_balance_v2.csv`
- `output/submission_upgrade_v2/industrial_source_targets_v2.csv`
- `output/submission_upgrade_v2/saf_process_upgrade_requirements_v2.csv`
- `output/submission_upgrade_v2/saf_price_process_cases_v2.csv`
- `output/submission_upgrade_v2/product_market_upgrade_requirements_v2.csv`
- `output/submission_upgrade_v2/product_market_capacity_v2.csv`
- `output/submission_upgrade_v2/storage_simulation_queue_v2.csv`
- `output/submission_upgrade_v2/storage_pressure_screen_v2.csv`
- `output/submission_upgrade_v2/revision_closure_gate_v2.csv`
- `output/submission_upgrade_v2/evidence_sources_v2.csv`
- `data/processed/co2_sources/ceads_2022_province_energy_long.csv`
- `data/processed/co2_sources/ceads_1997_2022_apparent_total_by_province.csv`
- `data/processed/co2_sources/ceads_1997_2019_city_emissions_long.csv`
- `data/processed/co2_sources/ceads_city_prefecture_crosswalk.csv`
- `data/processed/co2_sources/ceads_city_emissions_prefecture_summary.csv`
- `data/processed/co2_sources/ceads_city_emission_lp_caps.csv`
- `data/processed/co2_sources/ceads_2010_24_city_sector_emissions_long.csv`

Interpretation:

- Once these gates pass with B-grade or better data, the model architecture
  should not need major redesign.
- The additional CEADs files upgrade historical source-accounting evidence.
  The 290-city inventory is now crosswalked to the current prefecture-code layer
  for city-history visualization and non-DAC LP caps; historical split labels
  remain flagged as proxy evidence rather than hard constraints.
- Numerical conclusions will still change when real data replace proxies.
- Remaining journal revisions should be sensitivity, wording, and validation
  updates rather than structural rewrites, unless reviewers request a different
  research question.
"""
    DOC_OUT.write_text(text, encoding="utf-8")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    write_csv(OUT / "industrial_source_balance_v2.csv", industrial_source_balance_rows())
    write_csv(OUT / "industrial_source_targets_v2.csv", industrial_source_targets_v2_rows())
    write_csv(OUT / "saf_process_upgrade_requirements_v2.csv", saf_process_upgrade_rows())
    write_csv(OUT / "saf_price_process_cases_v2.csv", saf_price_process_cases_v2_rows())
    write_csv(OUT / "product_market_upgrade_requirements_v2.csv", product_market_upgrade_rows())
    write_csv(OUT / "product_market_capacity_v2.csv", product_market_capacity_v2_rows())
    write_csv(OUT / "storage_simulation_queue_v2.csv", storage_simulation_queue_rows())
    write_csv(OUT / "storage_pressure_screen_v2.csv", storage_pressure_screen_v2_rows())
    write_csv(OUT / "revision_closure_gate_v2.csv", closure_gate_rows())
    write_csv(OUT / "evidence_sources_v2.csv", evidence_sources_v2_rows())
    write_summary()
    print(f"Wrote submission upgrade v2 outputs to {OUT}")


if __name__ == "__main__":
    main()
