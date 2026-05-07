"""Create concise technology profitability threshold tables."""

from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MATRIX_DIR = ROOT / "output" / "standard_profitability_matrix"
INPUT = MATRIX_DIR / "standard_scenario_pathway_summary.csv"
OUTPUT = MATRIX_DIR / "technology_profitability_thresholds.csv"


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


def f(row: dict[str, str], key: str, default: float = math.inf) -> float:
    try:
        return float(row.get(key, ""))
    except ValueError:
        return default


def condition(row: dict[str, str]) -> str:
    product = row["product"]
    product_price = f(row, "best_break_even_product_price_usd_per_kg")
    policy_credit = f(row, "best_break_even_policy_credit_usd_per_tco2")
    if product != "none" and math.isfinite(product_price):
        return f"{product} price >= {product_price:.2f} USD/kg under {row['scenario']}"
    if math.isfinite(policy_credit):
        return f"policy/removal credit >= {policy_credit:.1f} USD/tCO2 under {row['scenario']}"
    return "No finite break-even threshold in current reduced-order model"


def main() -> None:
    rows = read_csv(INPUT)
    best_by_pathway: dict[tuple[str, str, str], dict[str, str]] = {}
    for row in rows:
        key = (row["technology_family"], row["pathway"], row["product"])
        incumbent = best_by_pathway.get(key)
        if incumbent is None or f(row, "best_margin_usd_per_tco2", -math.inf) > f(incumbent, "best_margin_usd_per_tco2", -math.inf):
            best_by_pathway[key] = row
    out = []
    for (family, pathway, product), row in sorted(best_by_pathway.items()):
        margin = f(row, "best_margin_usd_per_tco2", -math.inf)
        out.append(
            {
                "technology_family": family,
                "pathway": pathway,
                "product": product,
                "best_scenario": row["scenario"],
                "best_city": row["best_city"],
                "best_margin_usd_per_tco2": margin,
                "profitability_gap_usd_per_tco2": max(0.0, -margin),
                "break_even_product_price_usd_per_kg": row["best_break_even_product_price_usd_per_kg"],
                "break_even_policy_credit_usd_per_tco2": row["best_break_even_policy_credit_usd_per_tco2"],
                "break_even_h2_price_usd_per_kg": row["best_break_even_h2_price_usd_per_kg"],
                "break_even_electricity_price_usd_per_mwh": row["best_break_even_electricity_price_usd_per_mwh"],
                "minimum_condition_to_profit": condition(row),
            }
        )
    write_csv(OUTPUT, sorted(out, key=lambda row: float(row["profitability_gap_usd_per_tco2"])))
    print(f"Wrote {OUTPUT}: {len(out)} rows")


if __name__ == "__main__":
    main()
