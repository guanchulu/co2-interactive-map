"""Parse the downloaded CEADs 2022 provincial CO2 inventory workbook.

The workbook is an xlsx file with one sheet per province. This parser avoids
external Excel dependencies so the workflow stays reproducible on a clean
Python installation.
"""

from __future__ import annotations

import csv
import re
import zipfile
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RAW = DATA / "raw" / "co2_sources" / "CEADs_2022_30_province_emission_inventory.xlsx"
SOURCES = DATA / "real_inputs_top300_with_dac" / "spatial_sources_real.csv"
OUT_DIR = DATA / "processed" / "co2_sources"
SUMMARY = ROOT / "docs" / "joule_submission" / "ceads_2022_inventory_summary.md"

NS = {
    "a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}

PROVINCE_NAMES = {
    "InnerMongolia": "Inner Mongolia",
}

POWER_SECTOR = "Production and Supply of Electric Power, Steam and Hot Water"
GAS_SUPPLY_SECTOR = "Production and Supply of Gas"
STEEL_SECTOR = "Smelting and Pressing of Ferrous Metals"
NONFERROUS_SECTOR = "Smelting and Pressing of Nonferrous Metals"
NONMETAL_SECTOR = "Nonmetal Mineral Products"
CHEMICAL_SECTORS = {
    "Raw Chemical Materials and Chemical Products",
    "Petroleum Processing and Coking",
    "Chemical Fiber",
}
GAS_FUELS = {"Natural_Gas", "Other_Gas"}
TOTAL_COL = "Scope_1_Total"
PROCESS_COL = "Process"


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


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def f(value: Any) -> float:
    try:
        if value in ("", None):
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def column_index(cell_ref: str) -> int:
    letters = "".join(ch for ch in cell_ref if ch.isalpha())
    idx = 0
    for ch in letters:
        idx = idx * 26 + ord(ch.upper()) - 64
    return idx - 1


def load_shared_strings(zf: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in zf.namelist():
        return []
    root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
    values = []
    for item in root.findall("a:si", NS):
        values.append(
            "".join(
                text.text or ""
                for text in item.iter("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t")
            )
        )
    return values


def workbook_sheets(zf: zipfile.ZipFile) -> list[tuple[str, str]]:
    workbook = ET.fromstring(zf.read("xl/workbook.xml"))
    relroot = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
    rels = {rel.attrib["Id"]: rel.attrib["Target"] for rel in relroot}
    sheets = []
    for sheet in workbook.find("a:sheets", NS):
        rid = sheet.attrib["{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"]
        target = "xl/" + rels[rid].lstrip("/")
        sheets.append((sheet.attrib["name"], target))
    return sheets


def sheet_matrix(zf: zipfile.ZipFile, path: str, shared: list[str]) -> list[list[str]]:
    root = ET.fromstring(zf.read(path))
    rows: list[list[str]] = []
    for row in root.findall(".//a:sheetData/a:row", NS):
        row_values: dict[int, str] = {}
        for cell in row.findall("a:c", NS):
            value_node = cell.find("a:v", NS)
            value = "" if value_node is None else value_node.text or ""
            if cell.attrib.get("t") == "s" and value:
                value = shared[int(value)]
            row_values[column_index(cell.attrib["r"])] = value
        if row_values:
            max_col = max(row_values)
            rows.append([row_values.get(i, "") for i in range(max_col + 1)])
    return rows


def province_from_sheet(sheet_name: str) -> str:
    base = re.sub(r"\d+$", "", sheet_name)
    return PROVINCE_NAMES.get(base, base)


def parse_ceads_workbook(path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    long_rows: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []
    with zipfile.ZipFile(path) as zf:
        shared = load_shared_strings(zf)
        for sheet_name, sheet_path in workbook_sheets(zf):
            if sheet_name.upper() == "NOTE":
                continue
            province = province_from_sheet(sheet_name)
            rows = sheet_matrix(zf, sheet_path, shared)
            if len(rows) < 4:
                continue
            headers = rows[0]
            for row in rows[2:]:
                if not row or not row[0]:
                    continue
                sector = row[0]
                values = {headers[i]: f(row[i]) for i in range(1, min(len(row), len(headers)))}
                total = values.get(TOTAL_COL, 0.0)
                process = values.get(PROCESS_COL, 0.0)
                summary_rows.append(
                    {
                        "year": 2022,
                        "province": province,
                        "ceads_sector": sector,
                        "scope1_total_mtco2": round(total, 6),
                        "process_mtco2": round(process, 6),
                        "energy_mtco2": round(max(total - process, 0.0), 6),
                        "source": "CEADs 2022 30-province emission inventory",
                    }
                )
                for account, amount in values.items():
                    long_rows.append(
                        {
                            "year": 2022,
                            "province": province,
                            "ceads_sector": sector,
                            "fuel_or_account": account,
                            "emissions_mtco2": round(amount, 9),
                            "unit": "Mt CO2",
                            "source": "CEADs 2022 30-province emission inventory",
                        }
                    )
    return long_rows, summary_rows


def current_source_shares() -> dict[tuple[str, str], float]:
    totals: dict[tuple[str, str], float] = defaultdict(float)
    for row in read_csv(SOURCES):
        totals[(row["region"], row["source_type"])] += f(row.get("co2_available_mtpa"))
    return totals


def sector_lookup(summary_rows: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    return {(row["province"], row["ceads_sector"]): row for row in summary_rows}


def build_model_source_rows(summary_rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    by_key = sector_lookup(summary_rows)
    provinces = sorted({row["province"] for row in summary_rows})
    current = current_source_shares()
    rows: list[dict[str, Any]] = []
    gaps: list[dict[str, Any]] = []

    def add(province: str, source_type: str, amount: float, sector: str, calculation: str) -> None:
        if amount <= 0:
            return
        rows.append(
            {
                "year": 2022,
                "province": province,
                "source_type": source_type,
                "emissions_mtco2": round(amount, 6),
                "ceads_sector": sector,
                "calculation": calculation,
                "evidence_grade": "A/B",
                "source": "CEADs 2022 30-province emission inventory",
            }
        )

    for province in provinces:
        power = by_key.get((province, POWER_SECTOR), {})
        if power:
            power_total = f(power.get("scope1_total_mtco2"))
            gas_amount = 0.0
            for long_row in summary_rows_to_long_cache.get((province, POWER_SECTOR), []):
                if long_row["fuel_or_account"] in GAS_FUELS:
                    gas_amount += f(long_row["emissions_mtco2"])
            add(province, "gas_power", gas_amount, POWER_SECTOR, "Natural_Gas + Other_Gas in power/heat sector")
            add(province, "coal_power", max(power_total - gas_amount, 0.0), POWER_SECTOR, "Scope_1_Total minus gas fuels in power/heat sector")

        gas_supply = by_key.get((province, GAS_SUPPLY_SECTOR), {})
        if gas_supply:
            add(province, "gas_power", f(gas_supply.get("scope1_total_mtco2")), GAS_SUPPLY_SECTOR, "Gas supply sector added to gas-power/gas-system calibration")

        steel = by_key.get((province, STEEL_SECTOR), {})
        add(province, "steel", f(steel.get("scope1_total_mtco2")), STEEL_SECTOR, "Scope_1_Total")

        nonferrous = by_key.get((province, NONFERROUS_SECTOR), {})
        add(province, "aluminum", f(nonferrous.get("scope1_total_mtco2")), NONFERROUS_SECTOR, "Scope_1_Total; proxy for nonferrous/aluminium source class")

        for sector in CHEMICAL_SECTORS:
            chemical = by_key.get((province, sector), {})
            add(province, "chemicals", f(chemical.get("scope1_total_mtco2")), sector, "Scope_1_Total added to chemicals source class")

        nonmetal = by_key.get((province, NONMETAL_SECTOR), {})
        nonmetal_amount = f(nonmetal.get("scope1_total_mtco2"))
        cement_current = current.get((province, "cement"), 0.0)
        lime_current = current.get((province, "lime"), 0.0)
        denominator = cement_current + lime_current
        if nonmetal_amount > 0 and denominator > 0:
            if cement_current > 0:
                add(province, "cement", nonmetal_amount * cement_current / denominator, NONMETAL_SECTOR, "Nonmetal Mineral Products split by current cement/lime source share")
            if lime_current > 0:
                add(province, "lime", nonmetal_amount * lime_current / denominator, NONMETAL_SECTOR, "Nonmetal Mineral Products split by current cement/lime source share")
        elif nonmetal_amount > 0:
            gaps.append(
                {
                    "year": 2022,
                    "province": province,
                    "ceads_sector": NONMETAL_SECTOR,
                    "unallocated_emissions_mtco2": round(nonmetal_amount, 6),
                    "reason": "No cement or lime point source exists in current top-300 source layer for this province.",
                    "model_implication": "The point-source layer underrepresents cement/lime/nonmetal-mineral CO2 in this province.",
                }
            )
    return rows, gaps


summary_rows_to_long_cache: dict[tuple[str, str], list[dict[str, Any]]] = {}


def cache_long_rows(long_rows: list[dict[str, Any]]) -> None:
    summary_rows_to_long_cache.clear()
    for row in long_rows:
        summary_rows_to_long_cache.setdefault((row["province"], row["ceads_sector"]), []).append(row)


def write_summary(
    summary_rows: list[dict[str, Any]],
    model_rows: list[dict[str, Any]],
    gaps: list[dict[str, Any]],
) -> None:
    total = sum(f(row["scope1_total_mtco2"]) for row in summary_rows if row["ceads_sector"] == "TotalEmissions")
    process = sum(f(row["process_mtco2"]) for row in summary_rows if row["ceads_sector"] == "TotalEmissions")
    by_source: dict[str, float] = defaultdict(float)
    for row in model_rows:
        by_source[row["source_type"]] += f(row["emissions_mtco2"])
    unallocated_nonmetal = sum(f(row["unallocated_emissions_mtco2"]) for row in gaps)
    lines = [
        "# CEADs 2022 Inventory Summary",
        "",
        "Downloaded CEADs workbook: `data/raw/co2_sources/CEADs_2022_30_province_emission_inventory.xlsx`.",
        "",
        f"Parsed 30 provinces with total Scope 1 CO2 of {total:,.1f} MtCO2 in 2022.",
        f"Reported process CO2 in the province totals is {process:,.1f} MtCO2.",
        "",
        "Model-source mapped totals before capture-rate scaling:",
        "",
        "| source_type | CEADs-mapped emissions (MtCO2/yr) |",
        "|---|---:|",
    ]
    for source_type, amount in sorted(by_source.items()):
        lines.append(f"| {source_type} | {amount:,.1f} |")
    lines.extend(
        [
            "",
            f"Unallocated nonmetal-mineral province gaps: {len(gaps)} provinces, {unallocated_nonmetal:,.1f} MtCO2/yr.",
            "",
            "Important interpretation: CEADs is a province-sector accounting inventory, not a point-source asset list. It is used here as a calibration target for the existing point-source network. Nonmetal mineral products are split only where current cement/lime sources exist; otherwise the missing province is recorded as a source-layer gap.",
        ]
    )
    SUMMARY.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    long_rows, summary_rows = parse_ceads_workbook(RAW)
    cache_long_rows(long_rows)
    model_rows, gaps = build_model_source_rows(summary_rows)
    write_csv(OUT_DIR / "ceads_2022_province_sector_account_long.csv", long_rows)
    write_csv(OUT_DIR / "ceads_2022_province_sector_summary.csv", summary_rows)
    write_csv(OUT_DIR / "ceads_2022_province_model_source_totals.csv", model_rows)
    write_csv(OUT_DIR / "ceads_2022_nonmetal_mineral_unallocated_gap.csv", gaps)
    write_summary(summary_rows, model_rows, gaps)
    print(f"Parsed CEADs workbook into {OUT_DIR}")


if __name__ == "__main__":
    main()
