"""Parse additional CEADs workbooks downloaded after the 2022 province file.

The parser intentionally uses only Python's standard library.  It normalizes
four CEADs downloads into CSV interfaces that can be used by the manuscript
evidence registry without requiring pandas/openpyxl on a clean machine.
"""

from __future__ import annotations

import csv
import io
import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "co2_sources"
OUT = ROOT / "data" / "processed" / "co2_sources"
DOC = ROOT / "docs" / "joule_submission" / "ceads_additional_data_summary.md"

ENERGY_XLSX = RAW / "CEADs_2022_province_energy_inventory_en.xlsx"
APPARENT_XLSX = RAW / "CEADs_1997_2022_apparent_emission_inventory.xlsx"
CITY_290_XLSX = RAW / "CEADs_1997_2019_290_city_emission_inventory.xlsx"
CITY_24_ZIP = RAW / "CEADs_2010_24_city_45_sector_production_inventory.zip"

NS = {
    "a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}

PROVINCE_NAMES = {
    "InnerMongolia": "Inner Mongolia",
    "Inner mongolia": "Inner Mongolia",
}

APPARENT_INDICATORS = {
    ("Fossil fuel", "Raw coal total"): "raw_coal_total",
    ("Fossil fuel", "Crude oil total"): "crude_oil_total",
    ("Fossil fuel", "Natural gas total"): "natural_gas_total",
    ("Process", "Cement"): "cement_process",
}


def f(value: Any) -> float:
    try:
        if value in ("", None):
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


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


def normalize_sheet_target(target: str) -> str:
    if target.startswith("/"):
        return target.lstrip("/")
    if target.startswith("xl/"):
        return target
    return "xl/" + target.lstrip("/")


def workbook_sheets(zf: zipfile.ZipFile) -> list[tuple[str, str]]:
    workbook = ET.fromstring(zf.read("xl/workbook.xml"))
    relroot = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
    rels = {rel.attrib["Id"]: rel.attrib["Target"] for rel in relroot}
    sheets = []
    sheet_root = workbook.find("a:sheets", NS)
    if sheet_root is None:
        return sheets
    for sheet in sheet_root:
        rid = sheet.attrib["{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"]
        sheets.append((sheet.attrib["name"], normalize_sheet_target(rels[rid])))
    return sheets


def cell_value(cell: ET.Element, shared: list[str]) -> str:
    if cell.attrib.get("t") == "inlineStr":
        inline = cell.find("a:is", NS)
        if inline is None:
            return ""
        return "".join(
            text.text or ""
            for text in inline.iter("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t")
        )
    value_node = cell.find("a:v", NS)
    value = "" if value_node is None else value_node.text or ""
    if cell.attrib.get("t") == "s" and value:
        return shared[int(value)]
    return value


def sheet_matrix(zf: zipfile.ZipFile, path: str, shared: list[str]) -> list[list[str]]:
    root = ET.fromstring(zf.read(path))
    rows: list[list[str]] = []
    for row in root.findall(".//a:sheetData/a:row", NS):
        row_values: dict[int, str] = {}
        for cell in row.findall("a:c", NS):
            row_values[column_index(cell.attrib["r"])] = cell_value(cell, shared)
        if row_values:
            rows.append([row_values.get(i, "") for i in range(max(row_values) + 1)])
    return rows


def province_from_sheet(sheet_name: str) -> str:
    base = re.sub(r"\d+$", "", sheet_name).strip()
    return PROVINCE_NAMES.get(base, base)


def province_name(value: str) -> str:
    text = value.strip()
    return PROVINCE_NAMES.get(text, text)


def clean_city_name(value: str) -> str:
    text = value.strip()
    for suffix in ("市", "盟", "地区", "自治州"):
        if text.endswith(suffix):
            text = text[: -len(suffix)]
    return text


def parse_province_energy(path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
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
            products = rows[0]
            units = rows[1]
            for row in rows[2:]:
                if not row or not row[0]:
                    continue
                sector = row[0].strip()
                sector_total_tce = 0.0
                nonzero_products = 0
                for idx in range(1, min(len(row), len(products))):
                    product = products[idx].strip()
                    if not product:
                        continue
                    amount = f(row[idx])
                    if amount == 0.0:
                        continue
                    unit = units[idx].strip() if idx < len(units) else ""
                    long_rows.append(
                        {
                            "year": 2022,
                            "province": province,
                            "ceads_sector": sector,
                            "energy_product": product,
                            "amount": amount,
                            "unit": unit,
                            "source": "CEADs 2022 provincial energy inventory",
                        }
                    )
                    nonzero_products += 1
                    if product == "Total":
                        sector_total_tce = amount
                summary_rows.append(
                    {
                        "year": 2022,
                        "province": province,
                        "ceads_sector": sector,
                        "nonzero_energy_products": nonzero_products,
                        "total_energy_tce_10k_tce_if_reported": sector_total_tce,
                        "source": "CEADs 2022 provincial energy inventory",
                    }
                )
    return long_rows, summary_rows


def apparent_indicator(category: str, item: str, original_category: str) -> str | None:
    cat = category.strip()
    it = item.strip()
    if original_category.strip().startswith("Total apparent CO2 emissions") and not it:
        return "total_apparent_co2"
    return APPARENT_INDICATORS.get((cat, it))


def parse_apparent_emissions(path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    long_rows: list[dict[str, Any]] = []
    totals: list[dict[str, Any]] = []
    cement: list[dict[str, Any]] = []
    with zipfile.ZipFile(path) as zf:
        shared = load_shared_strings(zf)
        for sheet_name, sheet_path in workbook_sheets(zf):
            if not sheet_name.isdigit():
                continue
            year = int(sheet_name)
            rows = sheet_matrix(zf, sheet_path, shared)
            if not rows:
                continue
            header = rows[0]
            provinces = [province_name(value) for value in header[2:]]
            current_category = ""
            for row in rows[1:]:
                if len(row) < 3:
                    continue
                original_category = row[0].strip()
                if original_category:
                    current_category = original_category
                item = row[1].strip() if len(row) > 1 else ""
                indicator = apparent_indicator(current_category, item, original_category)
                if not indicator:
                    continue
                for offset, province in enumerate(provinces, start=2):
                    if not province or offset >= len(row):
                        continue
                    amount = f(row[offset])
                    rec = {
                        "year": year,
                        "province": province,
                        "category": current_category,
                        "item": item or current_category,
                        "indicator": indicator,
                        "emissions_mtco2": amount,
                        "unit": "Mt CO2",
                        "source": "CEADs 1997-2022 apparent emission inventory",
                    }
                    long_rows.append(rec)
                    if indicator == "total_apparent_co2":
                        totals.append(
                            {
                                "year": year,
                                "province": province,
                                "total_apparent_co2_mtco2": amount,
                                "source": rec["source"],
                            }
                        )
                    elif indicator == "cement_process":
                        cement.append(
                            {
                                "year": year,
                                "province": province,
                                "cement_process_mtco2": amount,
                                "source": rec["source"],
                            }
                        )
    return long_rows, totals, cement


def parse_290_city_inventory(path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    long_rows: list[dict[str, Any]] = []
    with zipfile.ZipFile(path) as zf:
        shared = load_shared_strings(zf)
        vector_sheet = None
        for sheet_name, sheet_path in workbook_sheets(zf):
            if sheet_name.strip().lower() == "emission vector":
                vector_sheet = sheet_path
                break
        if vector_sheet is None:
            raise ValueError("CEADs 290-city workbook lacks 'emission vector' sheet")
        rows = sheet_matrix(zf, vector_sheet, shared)
        for row in rows[1:]:
            if len(row) < 4 or not row[1]:
                continue
            year = int(f(row[2]))
            city_name = row[1].strip()
            long_rows.append(
                {
                    "ceads_city_id": row[0],
                    "city_name_zh": city_name,
                    "city_name_clean_zh": clean_city_name(city_name),
                    "year": year,
                    "emissions_mtco2": f(row[3]),
                    "unit": "Mt CO2",
                    "source": "CEADs 1997-2019 290-city emission inventory",
                }
            )
    join_rows = [
        {
            "ceads_city_id": row["ceads_city_id"],
            "city_name_zh": row["city_name_zh"],
            "city_name_clean_zh": row["city_name_clean_zh"],
            "year": row["year"],
            "emissions_mtco2": row["emissions_mtco2"],
            "join_status": "legacy_join_target_crosswalked_separately",
            "source": row["source"],
        }
        for row in long_rows
        if int(row["year"]) == 2019
    ]
    return long_rows, join_rows


def member_workbook_sheets(zip_member_bytes: bytes) -> list[str]:
    with zipfile.ZipFile(io.BytesIO(zip_member_bytes)) as zf:
        return [name for name, _ in workbook_sheets(zf)]


def member_sheet_matrix(zip_member_bytes: bytes, sheet_name: str) -> list[list[str]]:
    with zipfile.ZipFile(io.BytesIO(zip_member_bytes)) as zf:
        shared = load_shared_strings(zf)
        sheets = {name: path for name, path in workbook_sheets(zf)}
        return sheet_matrix(zf, sheets[sheet_name], shared)


def parse_24_city_zip(path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    registry: list[dict[str, Any]] = []
    sector_emissions: list[dict[str, Any]] = []
    sector_energy: list[dict[str, Any]] = []
    with zipfile.ZipFile(path) as outer:
        members = [
            member
            for member in outer.namelist()
            if member.lower().endswith(".xlsx")
            and not member.split("/")[-1].startswith("._")
            and "__MACOSX" not in member
        ]
        for member in members:
            base = member.split("/")[-1]
            data = outer.read(member)
            try:
                sheets = member_workbook_sheets(data)
                status = "parsed_structure"
            except zipfile.BadZipFile:
                sheets = []
                status = "bad_xlsx"
            province = ""
            city = ""
            m = re.match(r"(?P<province>[^-]+)-(?P<city>.+)\.xlsx$", base, re.IGNORECASE)
            if m:
                province = m.group("province").strip()
                city = m.group("city").replace("Xi'an", "Xian").strip()
            workbook_type = "city_energy_workbook" if city else "combined_or_reference_workbook"
            registry.append(
                {
                    "zip_member": member,
                    "file_name": base,
                    "workbook_type": workbook_type,
                    "province_name_en": province,
                    "city_name_en": city,
                    "sheet_count": len(sheets),
                    "sheet_names": ";".join(sheets),
                    "size_bytes": len(data),
                    "parse_status": status,
                    "source": "CEADs 2010 24-city 45-sector production inventory",
                }
            )

            if city and "Industrial energy consumption" in sheets:
                rows = member_sheet_matrix(data, "Industrial energy consumption")
                if len(rows) >= 4:
                    products = rows[1]
                    units = rows[2]
                    for row in rows[3:]:
                        if len(row) < 3 or not row[1]:
                            continue
                        sector = row[1].strip()
                        for idx in range(2, min(len(row), len(products))):
                            product = products[idx].strip()
                            amount = f(row[idx])
                            if not product or amount == 0.0:
                                continue
                            sector_energy.append(
                                {
                                    "year": 2010,
                                    "province_name_en": province,
                                    "city_name_en": city,
                                    "ceads_sector": sector,
                                    "energy_product": product,
                                    "amount": amount,
                                    "unit": units[idx].strip() if idx < len(units) else "",
                                    "source": "CEADs 2010 24-city 45-sector production inventory",
                                }
                            )

            if base == "CO2 emissions 24 city 2010.xlsx":
                for sheet in sheets:
                    if sheet.upper() == "NOTE" or sheet == "Summary":
                        continue
                    rows = member_sheet_matrix(data, sheet)
                    if len(rows) < 3:
                        continue
                    products = rows[0]
                    units = rows[1]
                    for row in rows[2:]:
                        if not row or not row[0]:
                            continue
                        sector = row[0].strip()
                        for idx in range(1, min(len(row), len(products))):
                            product = products[idx].strip()
                            amount = f(row[idx])
                            if not product or amount == 0.0:
                                continue
                            sector_emissions.append(
                                {
                                    "year": 2010,
                                    "city_name_en": sheet.replace("Xian", "Xian").strip(),
                                    "ceads_sector": sector,
                                    "fuel_or_account": product,
                                    "emissions_mtco2": amount,
                                    "unit": units[idx].strip() if idx < len(units) else "Mt CO2",
                                    "source": "CEADs 2010 24-city 45-sector production inventory",
                                }
                            )
    return registry, sector_energy, sector_emissions


def write_summary(
    energy_long: list[dict[str, Any]],
    apparent_long: list[dict[str, Any]],
    apparent_totals: list[dict[str, Any]],
    city_long: list[dict[str, Any]],
    city_join: list[dict[str, Any]],
    registry: list[dict[str, Any]],
    city24_energy: list[dict[str, Any]],
    city24_emissions: list[dict[str, Any]],
) -> None:
    total_2022 = sum(
        f(row["total_apparent_co2_mtco2"]) for row in apparent_totals if int(row["year"]) == 2022
    )
    city_2019 = sum(f(row["emissions_mtco2"]) for row in city_join)
    parsed_city_workbooks = sum(1 for row in registry if row["workbook_type"] == "city_energy_workbook")
    lines = [
        "# Additional CEADs Data Integration",
        "",
        "Newly downloaded CEADs files were normalized with `scripts/parse_ceads_additional_downloads.py`.",
        "",
        "## Processed Interfaces",
        "",
        f"- 2022 provincial energy inventory: {len(energy_long):,} non-zero province-sector-fuel rows.",
        f"- 1997-2022 apparent emissions: {len(apparent_long):,} indicator rows; 2022 summed provincial apparent emissions = {total_2022:,.1f} MtCO2.",
        f"- 1995/1997-2019 290-city inventory: {len(city_long):,} city-year rows; 2019 subset = {len(city_join):,} cities and {city_2019:,.1f} MtCO2.",
        f"- 2010 24-city 45-sector package: {len(registry):,} xlsx members registered; {parsed_city_workbooks:,} city energy workbooks; {len(city24_energy):,} city-sector-energy rows; {len(city24_emissions):,} city-sector-emission rows.",
        "",
        "## Model Use",
        "",
        "- The provincial energy inventory supports capture-energy and fuel-mix checks against the 2022 province-sector CO2 inventory.",
        "- The apparent-emissions time series supports historical province trend and peaking-date consistency checks.",
        "- The 290-city table supports city-level emission trend validation and is crosswalked separately by `scripts/build_ceads_city_crosswalk.py` for interactive-map history and non-DAC LP city caps.",
        "- The 24-city 2010 sector package supports city-sector emission-pattern calibration and is treated as historical benchmarking evidence, not a current-capacity constraint.",
    ]
    DOC.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    energy_long, energy_summary = parse_province_energy(ENERGY_XLSX)
    apparent_long, apparent_totals, apparent_cement = parse_apparent_emissions(APPARENT_XLSX)
    city_long, city_join = parse_290_city_inventory(CITY_290_XLSX)
    registry, city24_energy, city24_emissions = parse_24_city_zip(CITY_24_ZIP)

    write_csv(OUT / "ceads_2022_province_energy_long.csv", energy_long)
    write_csv(OUT / "ceads_2022_province_energy_summary.csv", energy_summary)
    write_csv(OUT / "ceads_1997_2022_apparent_emissions_long.csv", apparent_long)
    write_csv(OUT / "ceads_1997_2022_apparent_total_by_province.csv", apparent_totals)
    write_csv(OUT / "ceads_1997_2022_apparent_cement_process.csv", apparent_cement)
    write_csv(OUT / "ceads_1997_2019_city_emissions_long.csv", city_long)
    write_csv(OUT / "ceads_2019_city_emissions_for_prefecture_join.csv", city_join)
    write_csv(OUT / "ceads_2010_24_city_sector_file_registry.csv", registry)
    write_csv(OUT / "ceads_2010_24_city_sector_energy_long.csv", city24_energy)
    write_csv(OUT / "ceads_2010_24_city_sector_emissions_long.csv", city24_emissions)
    write_summary(
        energy_long,
        apparent_long,
        apparent_totals,
        city_long,
        city_join,
        registry,
        city24_energy,
        city24_emissions,
    )
    print("Parsed additional CEADs files")
    print(f"province energy rows: {len(energy_long)}")
    print(f"apparent emission rows: {len(apparent_long)}")
    print(f"290-city rows: {len(city_long)}")
    print(f"24-city sector emission rows: {len(city24_emissions)}")


if __name__ == "__main__":
    main()
