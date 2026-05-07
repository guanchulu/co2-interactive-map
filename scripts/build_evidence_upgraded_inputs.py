"""Build evidence-upgraded input tables for the Joule draft.

The generated tables intentionally separate three concepts:

1. Observed public data points.
2. Model-facing scenario inputs derived from those observations.
3. Remaining calibration gaps that still need engineering-grade data.

This keeps the model usable while preventing C/D-grade assumptions from being
presented as measured market or process data.
"""

from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
PROCESSED = DATA / "processed"

METHANEX_URL = "https://www.methanex.com/our-products/about-methanol/pricing/"
EIA_JET_URL = "https://www.eia.gov/dnav/pet/hist/LeafHandler.ashx?f=w&n=pet&s=eer_epjk_pf4_rgc_dpg"
CAAC_2023_URL = "https://www.caac.gov.cn/English/News/202406/t20240627_224599.html"
CAAC_2022_PDF_URL = "https://www.caac.gov.cn/English/Research/Reports/Statistical/202312/P020231225495691527532.pdf"
CHINA_STORAGE_NATURE_URL = "https://www.nature.com/articles/s41597-025-04875-3"
CHINA_STORAGE_FIGSHARE_URL = "https://doi.org/10.6084/m9.figshare.27646707"
NREL_SAF_URL = "https://www.nrel.gov/docs/fy22osti/82703.pdf"
SAF_COMPARATIVE_URL = "https://www.sciencedirect.com/science/article/pii/S001623612600774X"
SAF_EKEROSENE_URL = "https://www.sciencedirect.com/science/article/pii/S0196890425008787"
CO_ELECTROLYSIS_URL = "https://www.nature.com/articles/s41467-024-50521-8"
FORMATE_ELECTROLYSIS_URL = "https://www.nature.com/articles/s41929-026-01524-9"
ETHYLENE_ELECTROLYSIS_URL = "https://www.sciencedirect.com/science/article/pii/S221298202400101X"
FRAUNHOFER_ETHYLENE_URL = "https://www.umsicht.fraunhofer.de/en/press-media/press-releases/2024/electrolysis-ethylene.html"
FORMATE_INDUSTRIAL_REVIEW_URL = "https://www.osti.gov/pages/servlets/purl/1756565"
PEC_FORMATE_URL = "https://www.nature.com/articles/s41467-023-36726-3"
PHOTOCATALYSIS_PRIMER_URL = "https://www.nature.com/articles/s43586-023-00243-w"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        extra = row.pop(None, None)
        if extra:
            note_tail = ",".join(value for value in extra if value)
            if note_tail:
                row["notes"] = (row.get("notes", "") + "," + note_tail).strip(",")
    return rows


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


def as_float(row: dict[str, str], key: str, default: float = 0.0) -> float:
    value = row.get(key, "")
    if value == "":
        return default
    return float(value)


def fmt(value: float) -> str:
    if math.isinf(value):
        return "inf"
    return f"{value:.6g}"


def product_price_observations() -> list[dict[str, Any]]:
    jet_density_kg_per_l = 0.804
    liters_per_gallon = 3.785411784
    kg_per_gallon = jet_density_kg_per_l * liters_per_gallon
    jet_usd_per_gallon = 3.709
    jet_usd_per_kg = jet_usd_per_gallon / kg_per_gallon
    return [
        {
            "observation_id": "methanex_china_cpcp_2026_04",
            "product": "methanol",
            "region": "China",
            "observation_date": "2026-03-27",
            "valid_period": "2026-04-01 to 2026-04-30",
            "reported_value": 590,
            "reported_unit": "USD/metric_tonne",
            "converted_usd_per_kg": 0.590,
            "source_name": "Methanex China Posted Contract Price",
            "source_url": METHANEX_URL,
            "evidence_grade": "B",
            "notes": "Posted contract price; model low/high remain scenario sensitivities.",
        },
        {
            "observation_id": "methanex_asia_apcp_2026_04",
            "product": "methanol",
            "region": "Asia Pacific",
            "observation_date": "2026-03-27",
            "valid_period": "2026-04-01 to 2026-04-30",
            "reported_value": 740,
            "reported_unit": "USD/metric_tonne",
            "converted_usd_per_kg": 0.740,
            "source_name": "Methanex Asian Posted Contract Price",
            "source_url": METHANEX_URL,
            "evidence_grade": "B",
            "notes": "Regional comparator for China methanol sensitivity.",
        },
        {
            "observation_id": "eia_usgc_jet_2026_04_17",
            "product": "fossil_jet_fuel_benchmark",
            "region": "U.S. Gulf Coast",
            "observation_date": "2026-04-17",
            "valid_period": "weekly ending 2026-04-17",
            "reported_value": jet_usd_per_gallon,
            "reported_unit": "USD/gallon",
            "converted_usd_per_kg": jet_usd_per_kg,
            "source_name": "EIA weekly U.S. Gulf Coast kerosene-type jet fuel spot price FOB",
            "source_url": EIA_JET_URL,
            "evidence_grade": "B",
            "notes": "Converted with jet fuel density 0.804 kg/L; fossil benchmark, not SAF premium price.",
        },
    ]


def product_capacity_observations() -> list[dict[str, Any]]:
    traffic_billion_tkm_2023 = 118.834
    fuel_kg_per_tkm_2022 = 0.302
    implied_jet_fuel_mt = traffic_billion_tkm_2023 * fuel_kg_per_tkm_2022
    return [
        {
            "observation_id": "caac_china_jet_fuel_proxy_2023",
            "product": "sustainable_aviation_fuel",
            "region": "China",
            "year": 2023,
            "reported_quantity": traffic_billion_tkm_2023,
            "reported_unit": "billion tonne-km",
            "derived_market_capacity_t_per_year": round(implied_jet_fuel_mt * 1_000_000),
            "source_name": "CAAC 2023 traffic and CAAC 2022 fuel intensity",
            "source_url": f"{CAAC_2023_URL}; {CAAC_2022_PDF_URL}",
            "evidence_grade": "C",
            "notes": "Proxy multiplies 2023 total traffic by 2022 fuel intensity; replace with direct jet-fuel consumption if available.",
        },
        {
            "observation_id": "china_methanol_capacity_2023_cnfia_reported",
            "product": "methanol",
            "region": "China",
            "year": 2023,
            "reported_quantity": 106.186,
            "reported_unit": "million tonnes per year capacity",
            "derived_market_capacity_t_per_year": 106_186_000,
            "source_name": "China Nitrogen Fertilizer Industry Association reported via industry news",
            "source_url": "https://sddslchem.com/info-detail/106186000-tons-chinas-methanol-production-capacity-increased-by-6455-million-tons-last-year",
            "evidence_grade": "C",
            "notes": "Capacity, not demand or low-carbon offtake. Needs official NBS/association table for submission.",
        },
        {
            "observation_id": "china_ethylene_consumption_capacity_2023_industry_reported",
            "product": "ethylene",
            "region": "China",
            "year": 2023,
            "reported_quantity": 33.87,
            "reported_unit": "million tonnes apparent consumption",
            "derived_market_capacity_t_per_year": 33_870_000,
            "source_name": "Industry chain report",
            "source_url": "https://www.guidechem.com/guideview/indunews/strategic-of-china-ethylene-industry-chain.html",
            "evidence_grade": "C",
            "notes": "Public industry proxy; replace with NBS or audited industry yearbook for final submission.",
        },
    ]


def build_product_prices() -> None:
    rows = read_csv(DATA / "product_prices.csv")
    jet_price = product_price_observations()[2]["converted_usd_per_kg"]
    for row in rows:
        row.pop("", None)
        product = row["product"]
        year = int(row["year"])
        row["original_source"] = row.get("source", "")
        row["price_evidence_grade"] = "D" if row.get("source") == "model_default" else "C"
        row["capacity_evidence_grade"] = "D"
        row["source_url"] = ""
        row["replacement_status"] = "unchanged_scenario"
        if product == "methanol":
            row["price_base_usd_per_kg"] = "0.59"
            row["volume_limit_t_per_year"] = "106186000" if year <= 2030 else row["volume_limit_t_per_year"]
            row["source"] = "methanex_current_price_plus_scenario_range"
            row["source_url"] = METHANEX_URL
            row["price_evidence_grade"] = "B_for_base_C_for_forward_scenario"
            row["capacity_evidence_grade"] = "C"
            row["replacement_status"] = "base_price_replaced_capacity_screened"
            row["notes"] = (
                "Base price uses Methanex China April 2026 CPCP; low/high and future years remain sensitivity ranges. "
                + row.get("notes", "")
            )
        elif product == "sustainable_aviation_fuel":
            row["price_low_usd_per_kg"] = fmt(jet_price)
            if row.get("market_type") == "eu_saf":
                row["price_base_usd_per_kg"] = fmt(max(as_float(row, "price_base_usd_per_kg"), 2.80))
                row["price_high_usd_per_kg"] = fmt(max(as_float(row, "price_high_usd_per_kg"), 5.30))
                row["source_url"] = f"{EIA_JET_URL}; {SAF_COMPARATIVE_URL}; {SAF_EKEROSENE_URL}"
            else:
                row["price_base_usd_per_kg"] = fmt(max(as_float(row, "price_base_usd_per_kg"), jet_price + 0.35))
                row["source_url"] = EIA_JET_URL
            if year <= 2030:
                row["volume_limit_t_per_year"] = "35887668"
            row["source"] = "eia_jet_benchmark_plus_saf_premium_scenario"
            row["price_evidence_grade"] = "B_for_fossil_benchmark_C_for_saf_premium"
            row["capacity_evidence_grade"] = "C"
            row["replacement_status"] = "low_price_and_market_capacity_replaced"
            row["notes"] = (
                "Low price is fossil jet benchmark; SAF base/high retain premium or TEA-cost sensitivity. "
                + row.get("notes", "")
            )
        elif product == "ethylene":
            if year <= 2030:
                row["volume_limit_t_per_year"] = "33870000"
            row["source"] = "industry_capacity_proxy_plus_model_price"
            row["source_url"] = "https://www.guidechem.com/guideview/indunews/strategic-of-china-ethylene-industry-chain.html"
            row["capacity_evidence_grade"] = "C"
            row["replacement_status"] = "capacity_screened_price_unchanged"
        elif product == "carbonate_product":
            row["price_evidence_grade"] = "D"
            row["capacity_evidence_grade"] = "C"
            row["replacement_status"] = "requires_construction_material_price_replacement"
        elif product in {"carbon_monoxide", "formic_acid_equivalent", "methane"}:
            row["price_evidence_grade"] = "D"
            row["capacity_evidence_grade"] = "D"
            row["replacement_status"] = "requires_public_price_and_capacity_replacement"
    write_csv(PROCESSED / "markets" / "open_product_price_observations.csv", product_price_observations())
    write_csv(PROCESSED / "markets" / "open_product_capacity_observations.csv", product_capacity_observations())
    write_csv(DATA / "product_prices_evidence_upgraded.csv", rows)


def build_saf_benchmarks() -> None:
    rows = [
        {
            "case_id": "nrel_biomass_ft_ccu_2022",
            "pathway": "biomass_ft_plus_ccu",
            "model_type": "NREL TEA/LCA presentation",
            "metric": "CCU H2 and electricity demand",
            "value": "0.36 MJ H2 and 0.43 MJ electricity per MJ FT fuel for CCU case",
            "source_url": NREL_SAF_URL,
            "evidence_grade": "B",
            "model_use": "calibration_target",
            "notes": "Used to check whether reduced-order SAF energy demand is directionally consistent; not an Aspen file in this repo.",
        },
        {
            "case_id": "nrel_dac_co2_ft_2022",
            "pathway": "dac_co2_rwgs_ft",
            "model_type": "NREL TEA/LCA presentation",
            "metric": "DAC CO2 to FT fuel energy demand",
            "value": "1.2 MJ H2, 0.4 MJ natural gas, and 0.5 MJ electricity per MJ fuel",
            "source_url": NREL_SAF_URL,
            "evidence_grade": "B",
            "model_use": "calibration_target",
            "notes": "Supports conclusion that CO2-derived SAF is energy-intensive and long-term without low-carbon inputs.",
        },
        {
            "case_id": "comparative_ptl_saf_2026",
            "pathway": "fts_mtj_etj",
            "model_type": "Aspen Plus V14 plus custom TEA",
            "metric": "net production cost",
            "value": "MtJ-2 about 2.8-5.3 USD/kg; electrolysis 55-80% of CAPEX",
            "source_url": SAF_COMPARATIVE_URL,
            "evidence_grade": "B",
            "model_use": "price_threshold_context",
            "notes": "Open abstract/search-accessible benchmark; full extraction should be checked against article tables before submission.",
        },
        {
            "case_id": "ekerosen_lca_tea_2025",
            "pathway": "rwgs_ft_ekerosene",
            "model_type": "techno-economic and LCA",
            "metric": "levelized cost and GHG reduction",
            "value": "base e-kerosene cost 5.12 EUR/kg; 85-90% lower carbon emissions with renewable electricity",
            "source_url": SAF_EKEROSENE_URL,
            "evidence_grade": "B",
            "model_use": "price_threshold_context",
            "notes": "Used only as literature context, not as a direct product price.",
        },
    ]
    write_csv(PROCESSED / "saf" / "saf_literature_benchmarks.csv", rows)


def build_storage_screening() -> None:
    provincial_path = PROCESSED / "storage" / "provincial_level_co2_storage_figshare_27646707.csv"
    county_path = PROCESSED / "storage" / "county_level_co2_storage_figshare_27646707.csv"
    rows: list[dict[str, Any]] = []
    if provincial_path.exists():
        for row in read_csv(provincial_path):
            dsa_avg = as_float(row, "Injection rate capability-DSA (Mt/a) (Average)")
            eor_avg = as_float(row, "Injection rate capability-EOR (Mt/a) (Average)")
            total = dsa_avg + eor_avg
            potential = as_float(row, "Storage potential-ALL (Mt)")
            rows.append(
                {
                    "level": "province",
                    "region": row.get("Province name", ""),
                    "county": "",
                    "storage_potential_all_mt": potential,
                    "dsa_injection_rate_avg_mtpa": dsa_avg,
                    "dsa_injection_rate_min_mtpa": as_float(row, "Injection rate capability-DSA (Mt/a) (Minimum)"),
                    "dsa_injection_rate_max_mtpa": as_float(row, "Injection rate capability-DSA (Mt/a) (Maximum)"),
                    "eor_injection_rate_avg_mtpa": eor_avg,
                    "eor_injection_rate_min_mtpa": as_float(row, "Injection rate capability-EOR (Mt/a) (Minimum)"),
                    "eor_injection_rate_max_mtpa": as_float(row, "Injection rate capability-EOR (Mt/a) (Maximum)"),
                    "screening_injection_capacity_mtpa": total,
                    "years_to_fill_at_avg_injection": potential / total if total > 0 else math.inf,
                    "source_url": f"{CHINA_STORAGE_NATURE_URL}; {CHINA_STORAGE_FIGSHARE_URL}",
                    "evidence_grade": "B",
                    "notes": "Regional injection-rate capacity from gridded China storage dataset; not a reservoir pressure simulation.",
                }
            )
    if county_path.exists():
        for row in read_csv(county_path):
            dsa = as_float(row, "Injection rate capability-DSA (Mt/a)")
            eor = as_float(row, "Injection rate capability-EOR (Mt/a)")
            total = dsa + eor
            potential = as_float(row, "Storage potential-ALL (Mt)")
            rows.append(
                {
                    "level": "county",
                    "region": row.get("Province name", ""),
                    "county": row.get("County name", ""),
                    "storage_potential_all_mt": potential,
                    "dsa_injection_rate_avg_mtpa": dsa,
                    "dsa_injection_rate_min_mtpa": "",
                    "dsa_injection_rate_max_mtpa": "",
                    "eor_injection_rate_avg_mtpa": eor,
                    "eor_injection_rate_min_mtpa": "",
                    "eor_injection_rate_max_mtpa": "",
                    "screening_injection_capacity_mtpa": total,
                    "years_to_fill_at_avg_injection": potential / total if total > 0 else math.inf,
                    "source_url": f"{CHINA_STORAGE_NATURE_URL}; {CHINA_STORAGE_FIGSHARE_URL}",
                    "evidence_grade": "B",
                    "notes": "County-level injection capacity; pressure interference, plume geometry, and well count still need reservoir simulation.",
                }
            )
    write_csv(PROCESSED / "storage" / "storage_injectivity_screening.csv", rows)
    pressure_rows = [
        {
            "gap_id": "reservoir_pressure_simulation",
            "needed_parameter": "pressure buildup and interference by reservoir unit",
            "current_status": "not_resolved",
            "minimum_solution": "build reduced-order radial-flow pressure screen with depth, thickness, permeability, porosity, temperature, salinity, well spacing, and max bottom-hole pressure",
            "submission_solution": "calibrate with basin-level reservoir models or published project injection histories",
            "evidence_grade": "D",
        },
        {
            "gap_id": "well_count_and_spacing",
            "needed_parameter": "injector count, completion design, spacing constraints, and caprock pressure limit",
            "current_status": "not_resolved",
            "minimum_solution": "derive well count from county/province injection capacity and assumed Mtpa per well range",
            "submission_solution": "replace with project-specific wellfield design or basin atlas data",
            "evidence_grade": "D",
        },
    ]
    write_csv(PROCESSED / "storage" / "storage_pressure_simulation_requirements.csv", pressure_rows)


def build_technology_lifetime_tables() -> None:
    rows = [
        {
            "pathway": "electrolysis_to_co",
            "technology_family": "electrochemical",
            "product": "carbon_monoxide",
            "catalyst_or_reactor": "Ag hollow fiber penetration electrode",
            "current_density_ma_cm2": 2000,
            "faradaic_efficiency_fraction": 0.95,
            "reported_stability_h": 200,
            "scale_note": "strong-acid high-rate CO electrolysis; over 85% single-pass conversion",
            "source_url": CO_ELECTROLYSIS_URL,
            "evidence_grade": "B",
            "model_mapping": "raises performance ceiling but lowers confidence in commercial stack lifetime",
        },
        {
            "pathway": "electrolysis_to_formate",
            "technology_family": "electrochemical",
            "product": "formic_acid_equivalent",
            "catalyst_or_reactor": "Cu/Bi nanowire membrane electrode assembly",
            "current_density_ma_cm2": 200,
            "faradaic_efficiency_fraction": 0.90,
            "reported_stability_h": 8000,
            "scale_note": "4.5 M formate, 100 cm2 electrolyser shown for over 2000 h",
            "source_url": FORMATE_ELECTROLYSIS_URL,
            "evidence_grade": "B",
            "model_mapping": "supports less severe formate degradation penalty than prior placeholder",
        },
        {
            "pathway": "electrolysis_to_formate",
            "technology_family": "electrochemical",
            "product": "formic_acid_equivalent",
            "catalyst_or_reactor": "Dioxide Materials / Bi oxide industrial perspective",
            "current_density_ma_cm2": 200,
            "faradaic_efficiency_fraction": 0.80,
            "reported_stability_h": 1000,
            "scale_note": "FE may fall from about 80% initially to 65-70% by 1000 h in concentrated formic acid operation",
            "source_url": FORMATE_INDUSTRIAL_REVIEW_URL,
            "evidence_grade": "B",
            "model_mapping": "keeps uncertainty penalty despite newer long-duration benchmark",
        },
        {
            "pathway": "electrolysis_to_ethylene",
            "technology_family": "electrochemical",
            "product": "ethylene",
            "catalyst_or_reactor": "Cu-based low-temperature CO2 electrolyzer",
            "current_density_ma_cm2": 100,
            "faradaic_efficiency_fraction": 0.20,
            "reported_stability_h": 720,
            "scale_note": "month-long C2H4 stability at lower current density; 75 h at 300 mA/cm2",
            "source_url": ETHYLENE_ELECTROLYSIS_URL,
            "evidence_grade": "B",
            "model_mapping": "increases degradation and scale penalty for ethylene route",
        },
        {
            "pathway": "electrolysis_to_ethylene",
            "technology_family": "electrochemical",
            "product": "ethylene",
            "catalyst_or_reactor": "Fraunhofer CODE project statement",
            "current_density_ma_cm2": "",
            "faradaic_efficiency_fraction": 0.60,
            "reported_stability_h": "few_hours",
            "scale_note": "public industrial project states lab ethylene yield around 60% but cells fail within hours",
            "source_url": FRAUNHOFER_ETHYLENE_URL,
            "evidence_grade": "C",
            "model_mapping": "supports high FOAK risk penalty",
        },
        {
            "pathway": "photoelectrochemical_to_formate",
            "technology_family": "photochemical",
            "product": "formic_acid_equivalent",
            "catalyst_or_reactor": "tandem PEC formate cell",
            "current_density_ma_cm2": "",
            "faradaic_efficiency_fraction": 0.852,
            "reported_stability_h": "",
            "scale_note": "high formate FE and robustness reported, but accessible text does not provide a bankable lifetime",
            "source_url": PEC_FORMATE_URL,
            "evidence_grade": "C",
            "model_mapping": "keeps photochemical lifetime as unresolved sensitivity",
        },
        {
            "pathway": "photocatalytic_to_co",
            "technology_family": "photochemical",
            "product": "carbon_monoxide",
            "catalyst_or_reactor": "photocatalytic CO2 reduction literature",
            "current_density_ma_cm2": "",
            "faradaic_efficiency_fraction": "",
            "reported_stability_h": "",
            "scale_note": "review-level evidence; long-duration pilot lifetime remains missing",
            "source_url": PHOTOCATALYSIS_PRIMER_URL,
            "evidence_grade": "D",
            "model_mapping": "photocatalytic route remains a pilot/watchlist case",
        },
    ]
    write_csv(PROCESSED / "technology" / "electro_photo_lifetime_benchmarks.csv", rows)

    reliability_rows = read_csv(DATA / "technology_reliability.csv")
    replacements = {
        "electrolysis_to_co": {
            "availability_fraction": "0.74",
            "stack_lifetime_hours": "2000",
            "replacement_cost_fraction": "0.26",
            "performance_degradation_per_year": "0.035",
            "contingency_fraction": "0.35",
            "notes": "Evidence-upgraded: high-rate CO benchmark has 200 h demonstrated stability; commercial stack lifetime remains extrapolated.",
        },
        "electrolysis_to_formate": {
            "availability_fraction": "0.80",
            "stack_lifetime_hours": "8000",
            "replacement_cost_fraction": "0.18",
            "performance_degradation_per_year": "0.018",
            "contingency_fraction": "0.28",
            "notes": "Evidence-upgraded: 2026 MEA formate benchmark reports over 8000 h at 200 mA/cm2, with scale caveat.",
        },
        "electrolysis_to_ethylene": {
            "availability_fraction": "0.66",
            "stack_lifetime_hours": "720",
            "replacement_cost_fraction": "0.35",
            "performance_degradation_per_year": "0.050",
            "contingency_fraction": "0.45",
            "notes": "Evidence-upgraded: ethylene remains lifetime-limited; month-long stability only at lower current density.",
        },
        "photocatalytic_to_co": {
            "availability_fraction": "0.55",
            "replacement_cost_fraction": "0.40",
            "performance_degradation_per_year": "0.070",
            "contingency_fraction": "0.55",
            "notes": "Evidence-upgraded: no bankable long-duration photocatalytic CO lifetime found.",
        },
        "photoelectrochemical_to_formate": {
            "availability_fraction": "0.58",
            "replacement_cost_fraction": "0.40",
            "performance_degradation_per_year": "0.070",
            "contingency_fraction": "0.55",
            "notes": "Evidence-upgraded: PEC formate has promising FE but lifetime remains non-bankable.",
        },
    }
    for row in reliability_rows:
        if row["pathway"] in replacements:
            row.update(replacements[row["pathway"]])
            row["evidence_upgrade_source"] = "data/processed/technology/electro_photo_lifetime_benchmarks.csv"
            row["evidence_grade"] = "C"
        else:
            row["evidence_upgrade_source"] = ""
            row["evidence_grade"] = "C"
    write_csv(DATA / "technology_reliability_evidence_upgraded.csv", reliability_rows)


def build_evidence_ledger() -> None:
    rows = [
        {
            "parameter_group": "product_prices",
            "model_file": "data/product_prices_evidence_upgraded.csv",
            "previous_grade": "D",
            "current_grade": "B/C/D mixed",
            "replacement_status": "methanol and fossil jet benchmark replaced; SAF premium and specialty products remain scenarios",
            "next_action": "add audited China chemical price time series for CO, formic acid, ethylene, methane, carbonate products",
        },
        {
            "parameter_group": "product_capacity",
            "model_file": "data/processed/markets/open_product_capacity_observations.csv",
            "previous_grade": "D",
            "current_grade": "C",
            "replacement_status": "SAF, methanol, and ethylene capacity proxies added",
            "next_action": "replace with NBS/easyquery/OCR yearbook tables and regional offtake capacity by prefecture",
        },
        {
            "parameter_group": "SAF_process_package",
            "model_file": "data/processed/saf/saf_literature_benchmarks.csv",
            "previous_grade": "D",
            "current_grade": "B/C literature calibration",
            "replacement_status": "NREL and recent Aspen literature benchmarks added; no local Aspen/IDAES flowsheet yet",
            "next_action": "build rigorous FT-SAF and MTJ flowsheets or import literature mass/energy tables with full citations",
        },
        {
            "parameter_group": "storage_injectivity",
            "model_file": "data/processed/storage/storage_injectivity_screening.csv",
            "previous_grade": "C",
            "current_grade": "B",
            "replacement_status": "China province/county injection-rate dataset integrated",
            "next_action": "add reservoir pressure buildup, caprock pressure, plume, and wellfield constraints",
        },
        {
            "parameter_group": "storage_pressure",
            "model_file": "data/processed/storage/storage_pressure_simulation_requirements.csv",
            "previous_grade": "D",
            "current_grade": "D",
            "replacement_status": "requirements specified but not solved",
            "next_action": "implement reduced-order pressure model and calibrate with reservoir/project data",
        },
        {
            "parameter_group": "electrochemical_lifetime",
            "model_file": "data/processed/technology/electro_photo_lifetime_benchmarks.csv",
            "previous_grade": "C/D",
            "current_grade": "B/C",
            "replacement_status": "CO, formate, and ethylene durability evidence added; reliability penalties updated",
            "next_action": "extract full degradation curves and convert to stack replacement cost distributions",
        },
        {
            "parameter_group": "photochemical_lifetime",
            "model_file": "data/processed/technology/electro_photo_lifetime_benchmarks.csv",
            "previous_grade": "D",
            "current_grade": "C/D",
            "replacement_status": "review and PEC benchmark added; no bankable long-duration pilot lifetime found",
            "next_action": "seek pilot-duration photocatalytic/PEC CO2 conversion datasets or keep as exploratory scenario",
        },
        {
            "parameter_group": "policy_eligibility",
            "model_file": "data/policy_eligibility_rules.csv",
            "previous_grade": "C",
            "current_grade": "C",
            "replacement_status": "parameterized rules retained",
            "next_action": "legal audit of SAF, carbon market, CCER/removal, and chain-of-custody eligibility",
        },
    ]
    write_csv(DATA / "evidence_upgrade_ledger.csv", rows)


def main() -> None:
    build_product_prices()
    build_saf_benchmarks()
    build_storage_screening()
    build_technology_lifetime_tables()
    build_evidence_ledger()
    print("Wrote evidence-upgraded input tables.")


if __name__ == "__main__":
    main()
