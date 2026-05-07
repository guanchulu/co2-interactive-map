"""Allocate product-market CO2 capacity proxies to screening cities.

This is not a final demand model. It creates an auditable city-level interface
from current NBS-derived regional proxies and explicit demand indices. Rows with
evidence grade C/D must remain sensitivity inputs until replaced with direct
city product-market data.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CAPACITY_INPUT = ROOT / "data" / "processed" / "markets" / "product_destination_capacity_china_2023.csv"
CITY_INPUT = ROOT / "data" / "city_centers_screening.csv"
OUTPUT = ROOT / "data" / "processed" / "markets" / "city_product_market_capacity_screening_2023.csv"


REGION_RULES = {
    "EAST_CHEM_SH": {
        "provinces": {"Shanghai", "Jiangsu", "Zhejiang", "Anhui", "Fujian", "Shandong"},
        "index": "chemical_demand_index",
        "product_group": "methanol;carbon_monoxide;formic_acid_equivalent;ethylene",
    },
    "SOUTH_FUELS_GD": {
        "provinces": {"Guangdong", "Guangxi", "Hainan"},
        "index": "fuel_demand_index",
        "product_group": "methanol;methane;sustainable_aviation_fuel",
    },
    "YANGTZE_MINERAL_HB": {
        "provinces": {"Hubei", "Hunan", "Jiangxi", "Anhui", "Jiangsu", "Zhejiang", "Shanghai", "Chongqing", "Sichuan"},
        "index": "construction_material_demand_index",
        "product_group": "carbonate_product",
    },
    "NW_RENEW_H2_QH": {
        "provinces": {"Qinghai", "Gansu", "Xinjiang", "Ningxia", "Inner Mongolia", "Shaanxi"},
        "index": "renewable_power_index",
        "product_group": "methanol;carbon_monoxide;formic_acid_equivalent;sustainable_aviation_fuel",
    },
}


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


def f(row: dict[str, str], key: str) -> float:
    value = row.get(key, "")
    return float(value) if value else 0.0


def allocate_capacity(capacity_row: dict[str, str], cities: list[dict[str, str]]) -> list[dict[str, Any]]:
    destination_id = capacity_row["destination_id"]
    rule = REGION_RULES.get(destination_id)
    if rule is None:
        return []
    eligible = [
        city for city in cities
        if city.get("province") in rule["provinces"]
    ]
    index_name = str(rule["index"])
    weights = [
        max(0.0, f(city, index_name))
        for city in eligible
    ]
    total_weight = sum(weights)
    if total_weight <= 0:
        return []
    total_capacity = float(capacity_row["capacity_mtco2_per_year"])
    rows = []
    for city, weight in zip(eligible, weights):
        fraction = weight / total_weight
        rows.append(
            {
                "year": capacity_row.get("source_year", "2023"),
                "city_id": city["city_id"],
                "city_name": city["city_name"],
                "province": city["province"],
                "source_destination_id": destination_id,
                "product_group": rule["product_group"],
                "capacity_mtco2_per_year": round(total_capacity * fraction, 6),
                "allocation_weight": round(weight, 6),
                "allocation_fraction": round(fraction, 8),
                "allocation_index": index_name,
                "regional_capacity_mtco2_per_year": total_capacity,
                "basis": capacity_row.get("basis", ""),
                "real_data_flag": capacity_row.get("real_data_flag", ""),
                "evidence_grade": capacity_row.get("evidence_grade", ""),
                "source_table": capacity_row.get("source_table", ""),
                "source_url": capacity_row.get("source_url", ""),
                "notes": "Screening allocation from regional capacity to city demand index; replace with observed city product demand for final model.",
            }
        )
    return rows


def main() -> None:
    capacities = read_csv(CAPACITY_INPUT)
    cities = read_csv(CITY_INPUT)
    rows: list[dict[str, Any]] = []
    for capacity in capacities:
        rows.extend(allocate_capacity(capacity, cities))
    write_csv(OUTPUT, rows)
    print(f"Wrote {OUTPUT}: {len(rows)} rows")


if __name__ == "__main__":
    main()
