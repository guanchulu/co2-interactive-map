"""Run expanded real-data spatial allocation scenarios.

This script uses the top 300 Climate TRACE China point sources and a fixed
system allocation target close to the current destination-capacity envelope.
It writes one allocation/summary pair per scenario plus consolidated tables.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from co2alloc.cli import main as co2alloc_main  # noqa: E402


DATASET_NAME = "top300_target575"
INPUT_DIR = ROOT / "data" / "real_inputs_top300"
OUTPUT_DIR = ROOT / "output"
SOURCE_CALIBRATION = ROOT / "data" / "processed" / "co2_sources" / "source_inventory_calibration_ceads_2022.csv"


SCENARIOS = [
    {
        "name": "current_2030",
        "year": 2030,
        "policy_source": "destination",
        "carbon_price": 80.0,
        "carbon_tax": 0.0,
        "durable_credit": 0.0,
    },
    {
        "name": "current_2040",
        "year": 2040,
        "policy_source": "destination",
        "carbon_price": 80.0,
        "carbon_tax": 0.0,
        "durable_credit": 0.0,
    },
    {
        "name": "current_2050",
        "year": 2050,
        "policy_source": "destination",
        "carbon_price": 80.0,
        "carbon_tax": 0.0,
        "durable_credit": 0.0,
    },
    {
        "name": "mid_policy_2040",
        "year": 2040,
        "policy_source": "cli",
        "carbon_price": 80.0,
        "carbon_tax": 30.0,
        "durable_credit": 60.0,
    },
    {
        "name": "high_policy_2050",
        "year": 2050,
        "policy_source": "cli",
        "carbon_price": 150.0,
        "carbon_tax": 80.0,
        "durable_credit": 120.0,
    },
]


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


def run_build_inputs() -> None:
    co2alloc_main(
        [
            "build-real-inputs",
            "--source-year",
            "2024",
            "--top-sources",
            "300",
            "--out-dir",
            str(INPUT_DIR),
            "--manifest-out",
            str(INPUT_DIR / "manifest.csv"),
            "--storage-horizon-years",
            "20",
            "--source-calibration",
            str(SOURCE_CALIBRATION),
        ]
    )


def run_scenario(scenario: dict[str, Any]) -> tuple[Path, Path]:
    alloc_path = OUTPUT_DIR / f"expanded_{scenario['name']}_allocations.csv"
    summary_path = OUTPUT_DIR / f"expanded_{scenario['name']}_summary.csv"
    co2alloc_main(
        [
            "spatial-allocate",
            "--sources",
            str(INPUT_DIR / "spatial_sources_real.csv"),
            "--destinations",
            str(INPUT_DIR / "spatial_destinations_real.csv"),
            "--transport-modes",
            str(ROOT / "data" / "transport_modes.csv"),
            "--hubs",
            str(INPUT_DIR / "hubs_real.csv"),
            "--hourly-profiles",
            str(INPUT_DIR / "hourly_energy_profiles_real.csv"),
            "--learning",
            str(ROOT / "data" / "technology_scenarios.csv"),
            "--year",
            str(scenario["year"]),
            "--max-distance",
            "3000",
            "--optimizer",
            "lp",
            "--minimum-source-fraction",
            "0",
            "--target-total-mtco2",
            "575",
            "--policy-source",
            scenario["policy_source"],
            "--carbon-price",
            str(scenario["carbon_price"]),
            "--carbon-tax",
            str(scenario["carbon_tax"]),
            "--durable-removal-credit",
            str(scenario["durable_credit"]),
            "--out",
            str(alloc_path),
            "--summary-out",
            str(summary_path),
        ]
    )
    return alloc_path, summary_path


def scenario_summaries(scenario: dict[str, Any], summary_path: Path) -> list[dict[str, Any]]:
    rows = []
    for row in read_csv(summary_path):
        rows.append(
            {
                "dataset": DATASET_NAME,
                "scenario": scenario["name"],
                "technology_year": scenario["year"],
                "policy_source": scenario["policy_source"],
                "carbon_price_usd_per_tco2": scenario["carbon_price"],
                "carbon_tax_usd_per_tco2": scenario["carbon_tax"],
                "durable_removal_credit_usd_per_tco2": scenario["durable_credit"],
                **row,
            }
        )
    return rows


def family_mix(scenario: dict[str, Any], allocation_path: Path) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, float]] = {}
    for row in read_csv(allocation_path):
        family = row["technology_family"]
        bucket = grouped.setdefault(family, {"allocated": 0.0, "cost": 0.0, "avoided": 0.0})
        bucket["allocated"] += float(row["allocated_mtco2_per_year"])
        bucket["cost"] += float(row["annual_net_cost_musd_per_year"])
        bucket["avoided"] += float(row["annual_net_avoided_mtco2e_per_year"])
    rows = []
    for family, bucket in sorted(grouped.items()):
        allocated = bucket["allocated"]
        rows.append(
            {
                "dataset": DATASET_NAME,
                "scenario": scenario["name"],
                "technology_year": scenario["year"],
                "technology_family": family,
                "allocated_mtco2_per_year": allocated,
                "annual_net_cost_musd_per_year": bucket["cost"],
                "annual_net_avoided_mtco2e_per_year": bucket["avoided"],
                "weighted_net_cost_usd_per_tco2": bucket["cost"] / allocated if allocated else "",
                "weighted_net_avoided_tco2e_per_tco2": bucket["avoided"] / allocated if allocated else "",
            }
        )
    return rows


def main() -> None:
    run_build_inputs()
    all_summary_rows: list[dict[str, Any]] = []
    all_family_rows: list[dict[str, Any]] = []
    for scenario in SCENARIOS:
        allocation_path, summary_path = run_scenario(scenario)
        all_summary_rows.extend(scenario_summaries(scenario, summary_path))
        all_family_rows.extend(family_mix(scenario, allocation_path))
    write_csv(OUTPUT_DIR / "expanded_scenario_summary.csv", all_summary_rows)
    write_csv(OUTPUT_DIR / "expanded_scenario_family_mix.csv", all_family_rows)


if __name__ == "__main__":
    main()
