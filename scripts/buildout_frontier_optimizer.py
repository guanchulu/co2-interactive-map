"""Next-generation buildout frontier and policy/market analysis.

This script converts route-level profitability into manuscript-facing decision
outputs:

- profit-vs-durable-CO2 efficient frontiers,
- policy return-on-investment,
- product price saturation curves,
- storage wellfield/pressure proxy,
- transparent reduced-order SAF process cases,
- robust portfolio scores under disruption.
"""

from __future__ import annotations

import csv
import math
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = ROOT / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from optimize_and_uncertainty_screen import (  # noqa: E402
    solve_lp,
)
from analyze_market_stress_scenarios import (  # noqa: E402
    CATEGORY_LABELS,
    STRESS_SCENARIOS,
    load_capacities,
    load_price_table,
    read_csv,
    write_csv,
)


DATA = ROOT / "data"
CHINA = ROOT / "output" / "china2060_optimistic_profitability"
STRESS = ROOT / "output" / "china2060_market_stress"
OUT = ROOT / "output" / "china2060_frontier_upgrade"


FRONTIER_YEARS = [2040, 2050, 2060]
FRONTIER_SCENARIOS = [
    "policy_supported_effort",
    "policy_exit_green_premium",
    "commodity_only_no_support",
]
FRONTIER_TARGETS = [0.0, 50.0, 80.0, 100.0, 150.0, 250.0, 500.0, 750.0, 1000.0]
EPS = 1e-9


PRODUCT_ELASTICITY = {
    "sustainable_aviation_fuel": 0.25,
    "methanol": 0.35,
    "methane": 0.30,
    "carbon_monoxide": 0.45,
    "formic_acid_equivalent": 0.55,
    "ethylene": 0.25,
    "carbonate_product": 0.65,
}


SHOCK_WEIGHTS = {
    "policy_supported_effort": 0.48,
    "policy_exit_green_premium": 0.12,
    "commodity_only_no_support": 0.10,
    "war_energy_security_shock": 0.08,
    "earthquake_pipeline_disruption": 0.05,
    "pandemic_demand_slump": 0.12,
    "compound_stress_no_support": 0.05,
}


SCENARIO_BY_NAME = {scenario.name: scenario for scenario in STRESS_SCENARIOS}


def f(value: Any, default: float = 0.0) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(parsed):
        return default
    return parsed


def read_effort() -> dict[int, dict[str, float]]:
    rows = {}
    for row in read_csv(DATA / "china2060_optimistic_effort_scenario.csv"):
        year = int(row["year"])
        rows[year] = {
            "electricity_price_usd_per_mwh": f(row["electricity_price_usd_per_mwh"]),
            "h2_price_usd_per_kg": f(row["h2_price_usd_per_kg"]),
            "carbon_price_usd_per_tco2": f(row["carbon_price_usd_per_tco2"]),
            "durable_removal_credit_usd_per_tco2": f(row["durable_removal_credit_usd_per_tco2"]),
        }
    return rows


def run_frontier() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    source_caps, dest_caps = load_capacities()
    prices = load_price_table()
    rows: list[dict[str, Any]] = []
    allocations: list[dict[str, Any]] = []
    for year in FRONTIER_YEARS:
        records = read_csv(CHINA / f"china2060_{year}_profit_detail.csv")
        for scenario_name in FRONTIER_SCENARIOS:
            scenario = SCENARIO_BY_NAME[scenario_name]
            for target in FRONTIER_TARGETS:
                target_arg = None if target == 0.0 else target
                summary, top = solve_lp(
                    year,
                    scenario,
                    records,
                    source_caps,
                    dest_caps,
                    prices,
                    target_arg,
                )
                summary["frontier_target_label"] = "max_profit" if target == 0.0 else f"durable_{target:.0f}_mt"
                summary["target_durable_mtco2_per_year"] = target
                summary["support_required_busd_per_year"] = max(0.0, -f(summary["profit_busd_per_year"]))
                summary["profit_per_durable_tco2_usd"] = (
                    f(summary["profit_busd_per_year"]) * 1000.0 / f(summary["durable_allocated_mtco2_per_year"])
                    if f(summary["durable_allocated_mtco2_per_year"]) > EPS
                    else 0.0
                )
                rows.append(summary)
                for item in top[:100]:
                    allocations.append({"frontier_target_label": summary["frontier_target_label"], **item})
    return rows, allocations


def policy_roi_rows() -> list[dict[str, Any]]:
    stress_rows = read_csv(STRESS / "market_stress_summary.csv")
    out: list[dict[str, Any]] = []
    categories = sorted({row["category"] for row in stress_rows if row["pathway"] == "all"})
    for year in [2040, 2050, 2060]:
        for category in categories:
            supported = next(
                (
                    row
                    for row in stress_rows
                    if int(row["year"]) == year
                    and row["scenario"] == "policy_supported_effort"
                    and row["category"] == category
                    and row["pathway"] == "all"
                ),
                None,
            )
            no_support = next(
                (
                    row
                    for row in stress_rows
                    if int(row["year"]) == year
                    and row["scenario"] == "commodity_only_no_support"
                    and row["category"] == category
                    and row["pathway"] == "all"
                ),
                None,
            )
            if not supported:
                continue
            managed = f(supported["allocated_mtco2_per_year"])
            durable = f(supported["durable_allocated_mtco2_per_year"])
            profit = f(supported["profit_busd_per_year"])
            policy_revenue = f(supported["policy_revenue_busd_per_year"])
            no_support_managed = f(no_support["allocated_mtco2_per_year"]) if no_support else 0.0
            no_support_profit = f(no_support["profit_busd_per_year"]) if no_support else 0.0
            out.append(
                {
                    "year": year,
                    "category": category,
                    "category_label": CATEGORY_LABELS.get(category, category),
                    "policy_supported_managed_mtco2_per_year": managed,
                    "policy_supported_durable_mtco2_per_year": durable,
                    "policy_supported_profit_busd_per_year": profit,
                    "policy_revenue_busd_per_year": policy_revenue,
                    "commodity_only_managed_mtco2_per_year": no_support_managed,
                    "commodity_only_profit_busd_per_year": no_support_profit,
                    "capacity_survival_fraction_without_policy": no_support_managed / managed if managed > EPS else 0.0,
                    "profit_survival_fraction_without_policy": no_support_profit / profit if profit > EPS else 0.0,
                    "managed_mtco2_per_busd_policy": managed / policy_revenue if policy_revenue > EPS else math.inf,
                    "durable_mtco2_per_busd_policy": durable / policy_revenue if policy_revenue > EPS else math.inf,
                    "profit_busd_per_busd_policy": profit / policy_revenue if policy_revenue > EPS else math.inf,
                    "policy_interpretation": policy_interpretation(category, managed, durable, policy_revenue, no_support_managed),
                }
            )
    return out


def policy_interpretation(category: str, managed: float, durable: float, policy_revenue: float, no_support: float) -> str:
    if managed <= EPS:
        return "no material deployment in this category"
    survival = no_support / managed
    if category in {"geological_storage", "mineral_products"}:
        return "durable-capacity policy lever"
    if survival > 0.5:
        return "market-backed route after early policy support"
    if policy_revenue > EPS:
        return "policy-sensitive private profit route"
    return "offtake-sensitive route"


def product_saturation_rows() -> list[dict[str, Any]]:
    rows = read_csv(STRESS / "market_scale_by_product.csv")
    out: list[dict[str, Any]] = []
    for row in rows:
        year = int(row["year"])
        product = row["product"]
        if year not in {2040, 2050, 2060}:
            continue
        base_price = f(row["price_usd_per_kg"])
        market_volume = f(row["volume_limit_mt_product_per_year"])
        co2_required = f(row["co2_required_if_full_market_mtco2_per_year"], math.inf)
        elasticity = PRODUCT_ELASTICITY.get(product, 0.35)
        for share_i in range(0, 11):
            share = share_i / 10.0
            price = base_price * max(0.20, 1.0 - elasticity * (share**1.35))
            product_volume = market_volume * share
            out.append(
                {
                    "year": year,
                    "product": product,
                    "price_case": row["price_case"],
                    "supply_share_of_addressable_market": share,
                    "saturated_price_usd_per_kg": price,
                    "product_volume_mt_per_year": product_volume,
                    "gross_market_value_busd_per_year": price * product_volume,
                    "co2_required_mtco2_per_year": co2_required * share if math.isfinite(co2_required) else "",
                    "elasticity_assumption": elasticity,
                    "interpretation": "price premium erodes as CO2-derived supply approaches market saturation",
                }
            )
    return out


def storage_wellfield_rows() -> list[dict[str, Any]]:
    rows = read_csv(DATA / "processed" / "storage" / "storage_injectivity_screening.csv")
    out: list[dict[str, Any]] = []
    default_well_rate_mtpa = 0.25
    for row in rows:
        capacity = f(row["screening_injection_capacity_mtpa"])
        storage_potential = f(row["storage_potential_all_mt"])
        dsa_rate = f(row["dsa_injection_rate_avg_mtpa"])
        eor_rate = f(row["eor_injection_rate_avg_mtpa"])
        if capacity <= 0 and storage_potential <= 0:
            continue
        implied_well_rate = max(default_well_rate_mtpa, min(1.0, max(dsa_rate, eor_rate, default_well_rate_mtpa) / 8.0))
        wells = math.ceil(capacity / implied_well_rate) if capacity > 0 else 0
        pressure_proxy = min(1.0, capacity / max(1.0, storage_potential / 30.0)) if storage_potential > 0 else 1.0
        ramp_years = max(1.0, wells / 20.0)
        out.append(
            {
                "region": row["region"],
                "storage_potential_all_mt": storage_potential,
                "screening_injection_capacity_mtpa": capacity,
                "dsa_injection_rate_avg_mtpa": dsa_rate,
                "eor_injection_rate_avg_mtpa": eor_rate,
                "proxy_well_rate_mtpa_per_well": implied_well_rate,
                "proxy_well_count_for_screening_capacity": wells,
                "pressure_constraint_proxy_0_to_1": pressure_proxy,
                "buildout_ramp_years_at_20_wells_per_year": ramp_years,
                "bottleneck": storage_bottleneck(storage_potential, capacity, pressure_proxy, wells),
                "evidence_grade": row.get("evidence_grade", "B"),
                "note": "Reduced-order wellfield proxy; not a reservoir simulation.",
            }
        )
    return sorted(out, key=lambda item: f(item["screening_injection_capacity_mtpa"]), reverse=True)


def storage_bottleneck(storage_potential: float, capacity: float, pressure_proxy: float, wells: int) -> str:
    if storage_potential <= 0 or capacity <= 0:
        return "no screened injection capacity"
    if pressure_proxy > 0.7:
        return "pressure/injection-rate constrained"
    if wells > 100:
        return "wellfield construction constrained"
    return "storage appraisal and permitting constrained"


def saf_process_rows() -> list[dict[str, Any]]:
    cases = read_csv(DATA / "saf_process_cases.csv")
    effort = read_effort()
    prices = load_price_table()
    out: list[dict[str, Any]] = []
    for case in cases:
        pathway = case["pathway"]
        for year in [2030, 2040, 2050, 2060]:
            effort_row = effort[year]
            price_row = prices.get((year, "sustainable_aviation_fuel"), {})
            h2 = f(case["h2_kg_per_tco2"])
            elec = f(case["electricity_kwh_per_tco2"])
            heat = f(case["heat_gj_per_tco2"])
            saf = f(case["saf_kg_per_tco2"])
            capex = f(case["capex_usd_per_tpa_co2"]) * 0.12
            fixed = f(case["fixed_opex_usd_per_tco2"])
            variable = f(case["variable_opex_usd_per_tco2"])
            h2_cost = h2 * effort_row["h2_price_usd_per_kg"]
            elec_cost = elec * effort_row["electricity_price_usd_per_mwh"] / 1000.0
            heat_cost = heat * 6.0
            total_cost = capex + fixed + variable + h2_cost + elec_cost + heat_cost
            for price_case in ["base", "high"]:
                price = price_row.get(price_case, 0.0)
                revenue = saf * price
                out.append(
                    {
                        "case_id": case["case_id"],
                        "pathway": pathway,
                        "year": year,
                        "price_case": price_case,
                        "model_type": "transparent_reduced_order_flowsheet",
                        "h2_kg_per_tco2": h2,
                        "electricity_kwh_per_tco2": elec,
                        "heat_gj_per_tco2": heat,
                        "saf_kg_per_tco2": saf,
                        "annualized_capex_usd_per_tco2": capex,
                        "fixed_opex_usd_per_tco2": fixed,
                        "variable_opex_usd_per_tco2": variable,
                        "h2_cost_usd_per_tco2": h2_cost,
                        "electricity_cost_usd_per_tco2": elec_cost,
                        "heat_cost_usd_per_tco2": heat_cost,
                        "total_process_cost_usd_per_tco2": total_cost,
                        "saf_price_usd_per_kg": price,
                        "saf_revenue_usd_per_tco2": revenue,
                        "process_margin_before_policy_usd_per_tco2": revenue - total_cost,
                        "carbon_efficiency_proxy_tco2_to_saf_kg": saf / 1000.0,
                        "evidence_grade": "C",
                        "note": "Transparent reduced-order flowsheet; still not Aspen/IDAES-grade.",
                    }
                )
    return out


def robust_portfolio_rows() -> list[dict[str, Any]]:
    stress_rows = read_csv(STRESS / "market_stress_summary.csv")
    out: list[dict[str, Any]] = []
    keys = sorted(
        {
            (int(row["year"]), row["category"], row["pathway"])
            for row in stress_rows
            if int(row["year"]) in {2040, 2050, 2060}
        }
    )
    for year, category, pathway in keys:
        scenario_values = []
        for scenario, weight in SHOCK_WEIGHTS.items():
            row = next(
                (
                    item
                    for item in stress_rows
                    if int(item["year"]) == year
                    and item["category"] == category
                    and item["pathway"] == pathway
                    and item["scenario"] == scenario
                ),
                None,
            )
            profit = f(row["profit_busd_per_year"]) if row else 0.0
            capacity = f(row["allocated_mtco2_per_year"]) if row else 0.0
            scenario_values.append((scenario, weight, profit, capacity))
        expected_profit = sum(weight * profit for _, weight, profit, _ in scenario_values)
        expected_capacity = sum(weight * capacity for _, weight, _, capacity in scenario_values)
        worst_profit = min(profit for _, _, profit, _ in scenario_values)
        supported_profit = next((profit for scenario, _, profit, _ in scenario_values if scenario == "policy_supported_effort"), 0.0)
        profit_at_risk = max(0.0, supported_profit - worst_profit)
        robustness = expected_profit / max(abs(supported_profit), 1.0) if supported_profit else 0.0
        out.append(
            {
                "year": year,
                "category": category,
                "pathway": pathway,
                "expected_profit_busd_per_year": expected_profit,
                "expected_capacity_mtco2_per_year": expected_capacity,
                "worst_case_profit_busd_per_year": worst_profit,
                "policy_supported_profit_busd_per_year": supported_profit,
                "profit_at_risk_busd_per_year": profit_at_risk,
                "robustness_score": robustness,
                "portfolio_role": robust_role(category, robustness, expected_profit, worst_profit),
            }
        )
    return sorted(out, key=lambda item: (int(item["year"]), -f(item["expected_profit_busd_per_year"])))


def robust_role(category: str, robustness: float, expected_profit: float, worst_profit: float) -> str:
    if expected_profit <= 0:
        return "not robustly investable"
    if category in {"geological_storage", "mineral_products"} and worst_profit >= 0:
        return "robust durable backbone"
    if robustness >= 0.5:
        return "robust private-profit wedge"
    return "upside route with downside risk"


def write_key_findings(frontier: list[dict[str, Any]], policy_roi: list[dict[str, Any]], robust: list[dict[str, Any]]) -> None:
    supported_2060 = [
        row
        for row in frontier
        if int(row["year"]) == 2060
        and row["scenario"] == "policy_supported_effort"
        and row["frontier_target_label"] == "max_profit"
    ][0]
    target_500 = [
        row
        for row in frontier
        if int(row["year"]) == 2060
        and row["scenario"] == "policy_supported_effort"
        and row["frontier_target_label"] == "durable_500_mt"
    ][0]
    target_1000 = [
        row
        for row in frontier
        if int(row["year"]) == 2060
        and row["scenario"] == "policy_supported_effort"
        and row["frontier_target_label"] == "durable_1000_mt"
    ][0]
    best_policy = max(
        [row for row in policy_roi if int(row["year"]) == 2060 and math.isfinite(f(row["profit_busd_per_busd_policy"]))],
        key=lambda row: f(row["profit_busd_per_busd_policy"]),
    )
    robust_2060 = [row for row in robust if int(row["year"]) == 2060 and row["pathway"] == "all"]
    best_robust = max(robust_2060, key=lambda row: f(row["expected_profit_busd_per_year"]))
    text = f"""# Frontier Upgrade Key Findings

- 2060 maximum-profit LP selects {f(supported_2060['allocated_mtco2_per_year']):.1f} MtCO2/yr managed CO2 and {f(supported_2060['durable_allocated_mtco2_per_year']):.1f} MtCO2/yr durable CO2, with {f(supported_2060['profit_busd_per_year']):.1f} billion USD/yr profit.
- A 500 MtCO2/yr durable target is {'feasible' if int(target_500['success']) else 'infeasible'} under policy support, with {f(target_500['profit_busd_per_year']):.1f} billion USD/yr profit.
- A 1000 MtCO2/yr durable target is {'feasible' if int(target_1000['success']) else 'infeasible'} in the current screened network.
- Highest 2060 profit per policy-dollar category: {best_policy['category_label']} ({f(best_policy['profit_busd_per_busd_policy']):.2f} USD profit per USD policy revenue).
- Most robust 2060 all-pathway category by expected profit: {CATEGORY_LABELS.get(best_robust['category'], best_robust['category'])}, expected profit {f(best_robust['expected_profit_busd_per_year']):.1f} billion USD/yr.

Interpretation: the stronger paper claim is an efficient-frontier claim, not a universal-profitability claim. Profitable utilization and durable carbon-neutral capacity move together only over part of the frontier; beyond that, storage/mineralization buildout and policy support dominate.
"""
    (OUT / "frontier_upgrade_key_findings.md").write_text(text, encoding="utf-8")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    frontier, allocations = run_frontier()
    policy_roi = policy_roi_rows()
    saturation = product_saturation_rows()
    storage = storage_wellfield_rows()
    saf = saf_process_rows()
    robust = robust_portfolio_rows()
    write_csv(OUT / "buildout_frontier.csv", frontier)
    write_csv(OUT / "frontier_top_allocations.csv", allocations)
    write_csv(OUT / "policy_roi_summary.csv", policy_roi)
    write_csv(OUT / "product_saturation_curves.csv", saturation)
    write_csv(OUT / "storage_wellfield_pressure_proxy.csv", storage)
    write_csv(OUT / "saf_transparent_process_cases.csv", saf)
    write_csv(OUT / "robust_portfolio_scores.csv", robust)
    write_key_findings(frontier, policy_roi, robust)
    print(f"Wrote frontier upgrade outputs to {OUT}")


if __name__ == "__main__":
    main()
