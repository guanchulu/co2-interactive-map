"""Build destination-level CO2 product-market capacities from normalized NBS rows."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "data" / "processed" / "markets" / "nbs_market_observations_2023.csv"
DEFAULT_OUTPUT = ROOT / "data" / "processed" / "markets" / "product_destination_capacity_china_2023.csv"

CO2_T_PER_T_ETHYLENE = 2.0 * 44.0095 / 28.05316
CO2_T_PER_T_CH4 = 44.0095 / 16.04246
MT_CH4_PER_BCM_NATURAL_GAS = 0.716


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


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


def value(rows: list[dict[str, str]], region: str, product: str) -> float:
    total = 0.0
    for row in rows:
        if row["region"] == region and row["product"] == product:
            total += float(row["quantity"])
    return total


def build_capacities(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    east_regions = ["Shanghai", "Jiangsu", "Zhejiang", "Anhui", "Fujian", "Shandong"]
    east_ethylene_mt = sum(value(rows, region, "ethylene") for region in east_regions) * 0.01
    east_theoretical = east_ethylene_mt * CO2_T_PER_T_ETHYLENE
    east_access_fraction = 0.35

    south_regions = ["Guangdong", "Guangxi", "Hainan"]
    south_gas_bcm = sum(value(rows, region, "natural_gas") for region in south_regions) * 0.1
    south_theoretical = south_gas_bcm * MT_CH4_PER_BCM_NATURAL_GAS * CO2_T_PER_T_CH4
    south_access_fraction = 0.48

    hubei_cement_mt = value(rows, "Hubei", "cement") * 0.01
    concrete_multiplier_t_concrete_per_t_cement = 5.0
    mineral_uptake_tco2_per_t_concrete = 0.0714
    mineral_capacity = hubei_cement_mt * concrete_multiplier_t_concrete_per_t_cement * mineral_uptake_tco2_per_t_concrete

    return [
        {
            "destination_id": "NW_RENEW_H2_QH",
            "capacity_mtco2_per_year": 25.0,
            "basis": "scenario_hub_capacity",
            "real_data_flag": 0,
            "evidence_grade": "D",
            "source_table": "IEA/IRENA green-H2 scenario plus local renewable-hub assumption",
            "source_url": "",
            "source_year": 2023,
            "source_regions": "Qinghai",
            "source_products": "renewable_h2_chemical_hub",
            "algorithm": "scenario_capacity",
            "algorithm_version": "market_capacity_v1",
            "market_access_fraction": 1.0,
            "notes": "No NBS product output directly represents future green-H2 CO2 conversion hub capacity.",
        },
        {
            "destination_id": "EAST_CHEM_SH",
            "capacity_mtco2_per_year": round(east_theoretical * east_access_fraction, 6),
            "basis": "regional_ethylene_output_proxy",
            "real_data_flag": 1,
            "evidence_grade": "C",
            "source_table": "NBS China Statistical Yearbook 2024 Table 13-13",
            "source_url": "https://www.stats.gov.cn/sj/ndsj/2024/indexeh.htm",
            "source_year": 2023,
            "source_regions": ";".join(east_regions),
            "source_products": "ethylene",
            "algorithm": "sum(ethylene_10kt)*0.01*stoich_CO2_to_ethylene*market_access_fraction",
            "algorithm_version": "market_capacity_v1",
            "market_access_fraction": east_access_fraction,
            "notes": "Proxy for East China chemical offtake; includes only existing ethylene output, not all CO2-derived chemical demand.",
        },
        {
            "destination_id": "SOUTH_FUELS_GD",
            "capacity_mtco2_per_year": round(south_theoretical * south_access_fraction, 6),
            "basis": "regional_natural_gas_output_proxy",
            "real_data_flag": 1,
            "evidence_grade": "C",
            "source_table": "NBS China Statistical Yearbook 2024 Table 09-19",
            "source_url": "https://www.stats.gov.cn/sj/ndsj/2024/indexeh.htm",
            "source_year": 2023,
            "source_regions": ";".join(south_regions),
            "source_products": "natural_gas",
            "algorithm": "sum(natural_gas_100_million_m3)*0.1*bcm_to_mt_ch4*stoich_CO2_to_CH4*market_access_fraction",
            "algorithm_version": "market_capacity_v1",
            "market_access_fraction": south_access_fraction,
            "notes": "Proxy for e-methane/fuel offtake in South China; natural gas output is used as a regional market anchor.",
        },
        {
            "destination_id": "YANGTZE_MINERAL_HB",
            "capacity_mtco2_per_year": round(mineral_capacity, 6),
            "basis": "regional_cement_output_concrete_proxy",
            "real_data_flag": 1,
            "evidence_grade": "C",
            "source_table": "NBS China Statistical Yearbook 2024 Table 13-13",
            "source_url": "https://www.stats.gov.cn/sj/ndsj/2024/indexeh.htm",
            "source_year": 2023,
            "source_regions": "Hubei",
            "source_products": "cement",
            "algorithm": "cement_10kt*0.01*concrete_multiplier*mineral_uptake_tco2_per_t_concrete",
            "algorithm_version": "market_capacity_v1",
            "market_access_fraction": 1.0,
            "notes": "Proxy for concrete/mineralization market using cement output, concrete multiplier 5, uptake 0.0714 tCO2/t concrete.",
        },
    ]


def main() -> None:
    rows = read_csv(DEFAULT_INPUT)
    write_csv(DEFAULT_OUTPUT, build_capacities(rows))


if __name__ == "__main__":
    main()
