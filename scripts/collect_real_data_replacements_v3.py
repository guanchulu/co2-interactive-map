"""Collect real-data replacements and auditable substitutes for submission V3.

The goal is not to hide missing data. Each row states whether the preferred
dataset was found, downloaded, blocked, or replaced by a transparent proxy.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = ROOT / "output" / "real_data_search_v3"
DOC = ROOT / "docs" / "joule_submission" / "real_data_search_v3_summary.md"


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def unit_value_usd_per_kg(value_1000usd: float, quantity_kg: float) -> float:
    return round(value_1000usd * 1000.0 / quantity_kg, 6)


def source_registry_rows() -> list[dict[str, Any]]:
    return [
        {
            "gap": "industrial_source_inventory",
            "data_need": "province-sector CO2 emissions and industrial process emissions",
            "preferred_source": "CEADs 2022 30-province emission inventories and province energy inventories",
            "status": "downloaded_processed",
            "evidence_grade": "A/B",
            "source_url": "https://www.ceads.net.cn/data/province/",
            "local_path": "data/raw/co2_sources/CEADs_2022_30_province_emission_inventory.xlsx; data/raw/co2_sources/CEADs_2022_province_energy_inventory_en.xlsx; data/raw/co2_sources/CEADs_1997_2022_apparent_emission_inventory.xlsx; data/raw/co2_sources/CEADs_1997_2019_290_city_emission_inventory.xlsx; data/raw/co2_sources/CEADs_2010_24_city_45_sector_production_inventory.zip; data/processed/co2_sources/ceads_2022_province_model_source_totals.csv; data/processed/co2_sources/ceads_2022_province_energy_long.csv; data/processed/co2_sources/ceads_1997_2022_apparent_total_by_province.csv; data/processed/co2_sources/ceads_1997_2019_city_emissions_long.csv; data/processed/co2_sources/ceads_city_prefecture_crosswalk.csv; data/processed/co2_sources/ceads_city_emissions_prefecture_summary.csv; data/processed/co2_sources/ceads_city_emission_lp_caps.csv; data/processed/co2_sources/ceads_2010_24_city_sector_emissions_long.csv",
            "substitute_source": "GEM asset trackers + Climate TRACE source emissions + EDGAR 2025 remain as point-source/location layer and cross-check",
            "substitute_local_path": "data/processed/co2_sources/gem_*.csv; data/processed/co2_sources/climatetrace_china_key_sources_annual.csv",
            "model_use": "Calibrate provincial/source-type available CO2, expose national closure residuals, cross-check historical province/city emission trends, and constrain non-DAC city allocation with CEADs city-history caps.",
            "notes": "Downloaded files provide 2022 province-sector emissions, 2022 province energy, 1997-2022 provincial apparent emissions, 1997-2019 city emissions, and 2010 24-city sector detail. They are accounting inventories, not point-source asset lists; the CEADs city inventory is now crosswalked to current prefecture codes for map history and non-DAC LP caps, while historical split/sub-prefecture labels remain proxy evidence.",
        },
        {
            "gap": "industrial_activity_anchors",
            "data_need": "national output anchors for cement, steel, ethylene, aluminium and chemicals",
            "preferred_source": "NBS 2024 Statistical Communique, Table 3",
            "status": "found_official_html",
            "evidence_grade": "A",
            "source_url": "https://www.stats.gov.cn/sj/zxfb/202502/t20250228_1958817.html",
            "local_path": "",
            "substitute_source": "China Statistical Yearbook image tables already downloaded for regional detail",
            "substitute_local_path": "data/raw/markets/china_statistical_yearbook_2024/",
            "model_use": "Top-down closure targets: cement 18.3e8 t, crude steel 100509.1e4 t, ethylene 3493.4e4 t, aluminium 4400.5e4 t.",
            "notes": "Official national totals are suitable for closure checks; provincial allocation still needs yearbook/OCR or NBS session data.",
        },
        {
            "gap": "product_prices",
            "data_need": "observed product prices for methanol, ethylene, formate, carbonates, methane, SAF and CO",
            "preferred_source": "open commodity posts and official/World Bank trade unit values",
            "status": "found_with_substitutes",
            "evidence_grade": "B for Methanex/EIA/WITS; C for CO and SAF premium substitutes",
            "source_url": "https://www.methanex.com/our-products/about-methanol/pricing/; https://wits.worldbank.org/",
            "local_path": "data/processed/markets/open_product_price_observations_v3.csv",
            "substitute_source": "WITS 2024 HS trade unit values; CO methanol-equivalent backcast; EIA fossil jet parity",
            "substitute_local_path": "data/processed/markets/product_trade_unit_values_wits_2024.csv",
            "model_use": "Replace D-grade product prices with B/C observed or proxy values and keep premium cases separate.",
            "notes": "No open unified China SAF spot price or bulk CO price was found; these stay capped scenario variables.",
        },
        {
            "gap": "product_market_capacity",
            "data_need": "product market capacity and saturation ceilings",
            "preferred_source": "NBS yearbook, WITS trade volumes, CAAC aviation activity and industry associations",
            "status": "found_partial_with_substitutes",
            "evidence_grade": "B/C",
            "source_url": "https://www.stats.gov.cn/sj/ndsj/; https://wits.worldbank.org/; https://www.caac.gov.cn/",
            "local_path": "data/processed/markets/open_product_capacity_observations.csv",
            "substitute_source": "WITS trade volumes for specialty products; NBS national output for bulk products; CAAC aviation activity for SAF demand",
            "substitute_local_path": "data/processed/markets/product_trade_unit_values_wits_2024.csv",
            "model_use": "Bound high-value product sinks by observed market volume and saturation fractions.",
            "notes": "Trade volumes are not domestic demand. They are acceptable conservative proxies when domestic market tables are unavailable.",
        },
        {
            "gap": "saf_process_package",
            "data_need": "SAF process mass balance, energy balance, CAPEX, OPEX and product slate",
            "preferred_source": "Aspen literature/process supplementary data plus NREL process reports",
            "status": "found_benchmark_not_full_local_flowsheet",
            "evidence_grade": "B for literature; C until digitized",
            "source_url": "https://doi.org/10.1016/j.enconman.2024.118728; https://www.nrel.gov/docs/fy22osti/82703.pdf",
            "local_path": "data/processed/saf/saf_real_data_replacements_v3.csv",
            "substitute_source": "NREL FT-SAF report and iCET China SAF report",
            "substitute_local_path": "data/raw/saf/iCET_SAF_Report_2024.pdf",
            "model_use": "Replace reduced-order SAF with route-specific benchmark ranges and demote unsupported SAF profit claims.",
            "notes": "Full Aspen files are not openly available; use peer-reviewed reported cases until author data or own DWSIM/IDAES flowsheets are produced.",
        },
        {
            "gap": "reservoir_pressure_simulation",
            "data_need": "pressure buildup, injectivity, well count, plume and leakage constraints",
            "preferred_source": "China storage/injection grid plus MRST/TOUGH/CO2-SCREEN/CO2_S_COM simulation outputs",
            "status": "found_data_and_tools_proxy_output_needed",
            "evidence_grade": "B for China storage grid; C for proxy until simulations are run",
            "source_url": "https://doi.org/10.1038/s41597-025-04875-3; https://www.sintef.no/en/software/mrst-co2lab/; https://www.netl.doe.gov/node/5571",
            "local_path": "data/processed/storage/reservoir_simulation_source_registry_v3.csv",
            "substitute_source": "5 km China storage potential/injection-rate data plus proxy well-count screen",
            "substitute_local_path": "data/processed/storage/storage_pressure_screen_v2.csv",
            "model_use": "Screen large durable-storage claims; flag basins requiring numerical pressure simulation before final claims.",
            "notes": "No public China-wide reservoir simulation output table was found; the correct substitute is to run the tools against the China grid.",
        },
        {
            "gap": "policy_eligibility",
            "data_need": "route-specific ETS/CCER/CDR/SAF qualification rules",
            "preferred_source": "State Council ETS regulation, MEE/CCER rules, CAAC SAF pilot records",
            "status": "found_official_policy_texts",
            "evidence_grade": "A/B for text; C for modeled eligibility until legal coding",
            "source_url": "https://english.www.gov.cn/policies/latestreleases/202402/04/content_WS65bf7f70c6d0868f4e8e3c94.html; https://www.caac.gov.cn/English/News/202409/t20240927_225510.html",
            "local_path": "data/raw/policy/",
            "substitute_source": "parameterized route eligibility rules with no durable credit for EOR",
            "substitute_local_path": "data/policy_eligibility_rules.csv",
            "model_use": "Prevent credits from being assigned to ineligible products, fuels, EOR and non-durable routes.",
            "notes": "This is a policy-text source layer, not a legal opinion.",
        },
    ]


def trade_unit_value_rows() -> list[dict[str, Any]]:
    rows = [
        {
            "product": "ethylene",
            "model_product": "ethylene",
            "hs_code": "290121",
            "trade_flow": "China import from world",
            "year": 2024,
            "trade_value_1000usd": 1_980_829.38,
            "quantity_kg": 2_223_310_000,
            "source_url": "https://wits.worldbank.org/trade/comtrade/en/country/CHN/year/2024/tradeflow/Imports/partner/ALL/product/290121",
            "evidence_grade": "B_proxy",
            "limitations": "Import unit value, not domestic spot price.",
        },
        {
            "product": "formic_acid",
            "model_product": "formic_acid_equivalent",
            "hs_code": "291511",
            "trade_flow": "China export to world",
            "year": 2024,
            "trade_value_1000usd": 124_151.46,
            "quantity_kg": 255_545_000,
            "source_url": "https://wits.worldbank.org/trade/comtrade/en/country/ALL/year/2024/tradeflow/Exports/partner/WLD/product/291511",
            "evidence_grade": "B_proxy",
            "limitations": "Export unit value, not domestic specialty/offtake price.",
        },
        {
            "product": "calcium_carbonate",
            "model_product": "carbonate_product",
            "hs_code": "283650",
            "trade_flow": "China export to world",
            "year": 2024,
            "trade_value_1000usd": 38_188.08,
            "quantity_kg": 140_763_000,
            "source_url": "https://wits.worldbank.org/trade/comtrade/en/country/ALL/year/2024/tradeflow/Exports/partner/WLD/product/283650",
            "evidence_grade": "B_proxy",
            "limitations": "Chemical calcium-carbonate trade, not construction aggregate market.",
        },
        {
            "product": "liquefied_natural_gas",
            "model_product": "methane",
            "hs_code": "271111",
            "trade_flow": "China import from world",
            "year": 2024,
            "trade_value_1000usd": 44_057_222.72,
            "quantity_kg": 76_572_100_000,
            "source_url": "https://wits.worldbank.org/trade/comtrade/en/country/CHN/year/2024/tradeflow/Imports/partner/ALL/product/271111",
            "evidence_grade": "B_proxy",
            "limitations": "LNG import unit value, not city-gate gas price or e-methane premium.",
        },
    ]
    for row in rows:
        row["unit_value_usd_per_kg"] = unit_value_usd_per_kg(
            float(row["trade_value_1000usd"]),
            float(row["quantity_kg"]),
        )
        row["model_use"] = "Use as conservative observed price proxy or saturation guardrail in commodity-only cases."
    return rows


def price_observation_rows() -> list[dict[str, Any]]:
    trade = {row["model_product"]: row for row in trade_unit_value_rows()}
    methanol_china = 0.610
    co_proxy = round(methanol_china * 32.04 / 28.01, 6)
    return [
        {
            "observation_id": "methanex_china_cpcp_2026_05",
            "product": "methanol",
            "region": "China",
            "observation_date": "2026-04-29",
            "valid_period": "2026-05-01 to 2026-05-31",
            "reported_value": 610,
            "reported_unit": "USD/metric_tonne",
            "converted_usd_per_kg": methanol_china,
            "source_name": "Methanex China Posted Contract Price",
            "source_url": "https://www.methanex.com/our-products/about-methanol/pricing/",
            "evidence_grade": "B",
            "notes": "Open posted contract price; use as methanol commodity case, not green premium.",
        },
        {
            "observation_id": "methanex_asia_apcp_2026_05",
            "product": "methanol",
            "region": "Asia Pacific",
            "observation_date": "2026-04-29",
            "valid_period": "2026-05-01 to 2026-05-31",
            "reported_value": 740,
            "reported_unit": "USD/metric_tonne",
            "converted_usd_per_kg": 0.740,
            "source_name": "Methanex Asian Posted Contract Price",
            "source_url": "https://www.methanex.com/our-products/about-methanol/pricing/",
            "evidence_grade": "B",
            "notes": "Regional comparator for sensitivity.",
        },
        {
            "observation_id": "eia_usgc_jet_2026_04_17",
            "product": "fossil_jet_fuel_benchmark",
            "region": "U.S. Gulf Coast",
            "observation_date": "2026-04-17",
            "valid_period": "weekly ending 2026-04-17",
            "reported_value": 3.709,
            "reported_unit": "USD/gallon",
            "converted_usd_per_kg": 1.218674,
            "source_name": "EIA weekly U.S. Gulf Coast kerosene-type jet fuel spot price FOB",
            "source_url": "https://www.eia.gov/dnav/pet/hist/LeafHandler.ashx?f=w&n=pet&s=eer_epjk_pf4_rgc_dpg",
            "evidence_grade": "B",
            "notes": "Converted with 0.804 kg/L jet-fuel density; fossil parity, not SAF premium.",
        },
        {
            "observation_id": "wits_china_ethylene_import_unit_value_2024",
            "product": "ethylene",
            "region": "China",
            "observation_date": "2024",
            "valid_period": "2024 annual",
            "reported_value": trade["ethylene"]["unit_value_usd_per_kg"],
            "reported_unit": "USD/kg import unit value",
            "converted_usd_per_kg": trade["ethylene"]["unit_value_usd_per_kg"],
            "source_name": "World Bank WITS / UN Comtrade",
            "source_url": trade["ethylene"]["source_url"],
            "evidence_grade": "B_proxy",
            "notes": trade["ethylene"]["limitations"],
        },
        {
            "observation_id": "wits_china_formic_acid_export_unit_value_2024",
            "product": "formic_acid_equivalent",
            "region": "China",
            "observation_date": "2024",
            "valid_period": "2024 annual",
            "reported_value": trade["formic_acid_equivalent"]["unit_value_usd_per_kg"],
            "reported_unit": "USD/kg export unit value",
            "converted_usd_per_kg": trade["formic_acid_equivalent"]["unit_value_usd_per_kg"],
            "source_name": "World Bank WITS / UN Comtrade",
            "source_url": trade["formic_acid_equivalent"]["source_url"],
            "evidence_grade": "B_proxy",
            "notes": trade["formic_acid_equivalent"]["limitations"],
        },
        {
            "observation_id": "wits_china_calcium_carbonate_export_unit_value_2024",
            "product": "carbonate_product",
            "region": "China",
            "observation_date": "2024",
            "valid_period": "2024 annual",
            "reported_value": trade["carbonate_product"]["unit_value_usd_per_kg"],
            "reported_unit": "USD/kg export unit value",
            "converted_usd_per_kg": trade["carbonate_product"]["unit_value_usd_per_kg"],
            "source_name": "World Bank WITS / UN Comtrade",
            "source_url": trade["carbonate_product"]["source_url"],
            "evidence_grade": "B_proxy",
            "notes": trade["carbonate_product"]["limitations"],
        },
        {
            "observation_id": "wits_china_lng_import_unit_value_2024",
            "product": "methane",
            "region": "China",
            "observation_date": "2024",
            "valid_period": "2024 annual",
            "reported_value": trade["methane"]["unit_value_usd_per_kg"],
            "reported_unit": "USD/kg LNG import unit value",
            "converted_usd_per_kg": trade["methane"]["unit_value_usd_per_kg"],
            "source_name": "World Bank WITS / UN Comtrade",
            "source_url": trade["methane"]["source_url"],
            "evidence_grade": "B_proxy",
            "notes": trade["methane"]["limitations"],
        },
        {
            "observation_id": "co_methanol_equivalent_backcast_2026_05",
            "product": "carbon_monoxide",
            "region": "China",
            "observation_date": "2026-04-29",
            "valid_period": "proxy from May 2026 methanol price",
            "reported_value": co_proxy,
            "reported_unit": "USD/kg CO-equivalent",
            "converted_usd_per_kg": co_proxy,
            "source_name": "Methanol-value backcast from Methanex China price",
            "source_url": "https://www.methanex.com/our-products/about-methanol/pricing/",
            "evidence_grade": "C_substitute",
            "notes": "No open China bulk CO price found. Proxy assumes one kg CO can support 32.04/28.01 kg methanol before conversion/upgrading costs.",
        },
        {
            "observation_id": "china_saf_news_price_2026_02",
            "product": "sustainable_aviation_fuel",
            "region": "China export/HEFA market",
            "observation_date": "2026-02-02",
            "valid_period": "news snapshot",
            "reported_value": 2642,
            "reported_unit": "USD/metric_tonne",
            "converted_usd_per_kg": 2.642,
            "source_name": "Caixin Global news proxy",
            "source_url": "https://www.caixinglobal.com/2026-02-02/cover-story-how-gutter-oil-became-a-prized-fuel-for-international-airlines-102410360.html",
            "evidence_grade": "C_news_proxy",
            "notes": "HEFA/UCO-linked market news, not CO2-derived PtL SAF price. Use only as a capped optimistic market comparator.",
        },
    ]


def saf_rows() -> list[dict[str, Any]]:
    return [
        {
            "item": "china_saf_pilot",
            "status": "found_official",
            "value": "12 flights from Beijing Daxing, Chengdu Shuangliu, Zhengzhou Xinzheng and Ningbo Lishe in pilot phase",
            "unit": "pilot deployment record",
            "source_url": "https://www.caac.gov.cn/English/News/202409/t20240927_225510.html",
            "local_path": "",
            "evidence_grade": "A/B",
            "model_use": "SAF policy/location eligibility and airport demand anchoring.",
        },
        {
            "item": "china_saf_capacity_2025_news",
            "status": "found_industry_news",
            "value": 1.375,
            "unit": "Mt/year certified production capacity",
            "source_url": "https://www.spglobal.com/energy/en/news-research/latest-news/refined-products/122525-shandong-haike-certified-for-saf-boosts-chinas-capacity-to-138-mil-mty",
            "local_path": "",
            "evidence_grade": "C_news",
            "model_use": "Upper bound for current HEFA-like China SAF supply, not PtL e-SAF.",
        },
        {
            "item": "china_saf_report_icet_2024",
            "status": "downloaded",
            "value": "China SAF industry report",
            "unit": "PDF",
            "source_url": "https://www.icet.org.cn/admin/upload/iCET%20SAF%20Report%202024.pdf",
            "local_path": "data/raw/saf/iCET_SAF_Report_2024.pdf",
            "evidence_grade": "B/C",
            "model_use": "China-specific SAF policy, supply-chain and e-fuel narrative cross-check.",
        },
        {
            "item": "ptl_saf_aspen_benchmark_eyberg_2024",
            "status": "found_peer_reviewed",
            "value": "Aspen Plus V12 FT and MtJ benchmark",
            "unit": "process/TEA article",
            "source_url": "https://doi.org/10.1016/j.enconman.2024.118728",
            "local_path": "",
            "evidence_grade": "B",
            "model_use": "SAF process mass/energy/CAPEX/OPEX benchmark until our own flowsheet is built.",
        },
        {
            "item": "nrel_ft_saf_82703",
            "status": "found_downloadable",
            "value": "NREL FT-SAF techno-economic benchmark",
            "unit": "PDF report",
            "source_url": "https://www.nrel.gov/docs/fy22osti/82703.pdf",
            "local_path": "",
            "evidence_grade": "B",
            "model_use": "FT product slate, upgrading, TRL and cost sanity check.",
        },
    ]


def reservoir_rows() -> list[dict[str, Any]]:
    return [
        {
            "tool_or_dataset": "China fine-grid storage and injection-rate dataset",
            "status": "downloaded_processed",
            "source_url": "https://doi.org/10.1038/s41597-025-04875-3",
            "local_path": "data/raw/storage/; data/processed/storage/",
            "evidence_grade": "B",
            "model_use": "China-specific DSA/EOR capacity and injection-rate screen.",
            "limitation": "Not a full pressure/plume/interference simulation.",
        },
        {
            "tool_or_dataset": "MRST-co2lab",
            "status": "found_open_source_tool",
            "source_url": "https://www.sintef.no/en/software/mrst-co2lab/",
            "local_path": "",
            "evidence_grade": "B_tool",
            "model_use": "Vertical-equilibrium storage simulation and structural trapping workflow.",
            "limitation": "Requires MATLAB/MRST and China reservoir parameterization.",
        },
        {
            "tool_or_dataset": "NETL CO2-SCREEN",
            "status": "manual_downloaded",
            "source_url": "https://www.netl.doe.gov/node/5571",
            "local_path": "data/raw/reservoir_tools/NETL_CO2_SCREEN_users_manual.pdf",
            "evidence_grade": "B_tool",
            "model_use": "Prospective storage-resource and Monte Carlo efficiency-factor screen.",
            "limitation": "High-level resource screen, not project-level reservoir simulator.",
        },
        {
            "tool_or_dataset": "NETL CO2_S_COM",
            "status": "found_reference",
            "source_url": "https://netl.doe.gov/projects/VueConnection/download.aspx?filename=CO2SCOMModelingcostonshoreCO2storagesalinereservoirs_080624.pdf&id=3b274e24-f1c3-405d-a4df-cbeac0293796",
            "local_path": "",
            "evidence_grade": "B_tool",
            "model_use": "Storage cost, well count and pressure-interference cost benchmark.",
            "limitation": "U.S. formation database; use equations/structure as substitute unless China data are mapped.",
        },
        {
            "tool_or_dataset": "TOUGH3/ECO2N",
            "status": "found_tool",
            "source_url": "https://tough.lbl.gov/software/tough3/",
            "local_path": "",
            "evidence_grade": "B_tool",
            "model_use": "Full multiphase CO2-brine thermal/reservoir simulation option for selected basins.",
            "limitation": "Requires setup and calibration; too heavy for national first-pass screening.",
        },
    ]


def write_summary() -> None:
    text = """# Real Data Search V3 Summary

This pass found or substituted every high-priority data gap requested for the next manuscript upgrade.

## Machine-readable outputs

- `data/catalog/real_data_source_registry_v3.csv`
- `data/processed/markets/product_trade_unit_values_wits_2024.csv`
- `data/processed/markets/open_product_price_observations_v3.csv`
- `data/processed/saf/saf_real_data_replacements_v3.csv`
- `data/processed/storage/reservoir_simulation_source_registry_v3.csv`
- `output/real_data_search_v3/real_data_search_summary.md`

## Main interpretation

- CEADs 2022 30-province emission inventory was manually downloaded and parsed. Additional CEADs 2022 provincial energy, 1997-2022 apparent provincial emissions, 1997-2019 290-city emissions, and 2010 24-city sector workbooks were also downloaded and parsed. The 2022 province-sector workbook provides the primary province-sector accounting calibration target; the added files provide fuel-mix, historical trend, city-emission and city-sector validation layers. The 290-city table is now crosswalked to current prefecture codes for interactive map history and non-DAC LP city caps. GEM, Climate TRACE and EDGAR remain point-source/location and cross-check layers.
- Direct open China prices were found for methanol and fossil jet parity. For ethylene, formate, carbonate product and methane, WITS/UN Comtrade unit values are the best open substitutes. For CO, no open bulk China price was found; a methanol-equivalent backcast is used as a transparent substitute.
- Direct open China SAF spot prices remain weak. Use fossil jet parity, China HEFA/SAF news proxies and policy premium scenarios separately. Do not mix these with PtL SAF process cost.
- China storage capacity/injection data are already strong enough for screening. Pressure-safe claims still require MRST, CO2-SCREEN, CO2_S_COM or TOUGH-style simulations.
"""
    OUT.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    (OUT / "real_data_search_summary.md").write_text(text, encoding="utf-8")
    DOC.write_text(text, encoding="utf-8")


def main() -> None:
    write_csv(DATA / "catalog" / "real_data_source_registry_v3.csv", source_registry_rows())
    write_csv(DATA / "processed" / "markets" / "product_trade_unit_values_wits_2024.csv", trade_unit_value_rows())
    write_csv(DATA / "processed" / "markets" / "open_product_price_observations_v3.csv", price_observation_rows())
    write_csv(DATA / "processed" / "saf" / "saf_real_data_replacements_v3.csv", saf_rows())
    write_csv(DATA / "processed" / "storage" / "reservoir_simulation_source_registry_v3.csv", reservoir_rows())
    write_summary()
    print(f"Wrote V3 real-data search outputs to {OUT}")


if __name__ == "__main__":
    main()
