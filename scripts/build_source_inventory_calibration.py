"""Build province/source-type calibration factors for CO2 source inventories.

Preferred input is a normalized CEADs table:

year,province,source_type,emissions_mtco2

If that file is unavailable, the script writes a transparent fallback with
multiplier 1.0 from the current point-source inventory. The real-data builder
can consume either output through --source-calibration.
"""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCES = ROOT / "data" / "real_inputs_top300" / "spatial_sources_real.csv"
DEFAULT_OUTPUT = ROOT / "data" / "processed" / "co2_sources" / "source_inventory_calibration_fallback.csv"
DEFAULT_TEMPLATE = ROOT / "data" / "processed" / "co2_sources" / "ceads_province_sector_totals_template.csv"


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


def grouped_source_totals(sources: list[dict[str, str]]) -> dict[tuple[str, str], float]:
    totals: dict[tuple[str, str], float] = defaultdict(float)
    for row in sources:
        totals[(row["region"], row["source_type"])] += float(row["co2_available_mtpa"])
    return totals


def grouped_ceads_totals(rows: list[dict[str, str]], year: int, capture_rate: float) -> dict[tuple[str, str], float]:
    totals: dict[tuple[str, str], float] = defaultdict(float)
    for row in rows:
        if int(float(row["year"])) != year:
            continue
        totals[(row["province"], row["source_type"])] += float(row["emissions_mtco2"]) * capture_rate
    return totals


def build_calibration(
    sources: list[dict[str, str]],
    ceads_rows: list[dict[str, str]] | None,
    year: int,
    capture_rate: float,
) -> list[dict[str, Any]]:
    source_totals = grouped_source_totals(sources)
    target_totals = grouped_ceads_totals(ceads_rows, year, capture_rate) if ceads_rows else {}
    rows = []
    for key in sorted(source_totals):
        source_total = source_totals[key]
        target_total = target_totals.get(key, source_total)
        multiplier = target_total / source_total if source_total else 1.0
        rows.append(
            {
                "year": year,
                "province": key[0],
                "source_type": key[1],
                "source_available_mtpa_before_calibration": round(source_total, 6),
                "target_available_mtpa_after_calibration": round(target_total, 6),
                "calibration_multiplier": round(multiplier, 9),
                "target_source": "CEADs_normalized" if ceads_rows else "point_source_fallback",
                "algorithm": "target_available_mtpa/source_available_mtpa grouped by province and source_type",
            }
        )
    return rows


def write_template(path: Path) -> None:
    write_csv(
        path,
        [
            {
                "year": 2024,
                "province": "Shandong",
                "source_type": "steel",
                "emissions_mtco2": "",
                "notes": "Fill from manually downloaded CEADs province-sector table; units must be MtCO2/yr before capture.",
            }
        ],
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sources", default=str(DEFAULT_SOURCES))
    parser.add_argument("--ceads-normalized", default="")
    parser.add_argument("--year", type=int, default=2024)
    parser.add_argument("--capture-rate", type=float, default=0.90)
    parser.add_argument("--out", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--template-out", default=str(DEFAULT_TEMPLATE))
    return parser


def main() -> None:
    args = build_parser().parse_args()
    sources = read_csv(Path(args.sources))
    ceads_rows = read_csv(Path(args.ceads_normalized)) if args.ceads_normalized else None
    write_csv(Path(args.out), build_calibration(sources, ceads_rows, args.year, args.capture_rate))
    write_template(Path(args.template_out))


if __name__ == "__main__":
    main()
