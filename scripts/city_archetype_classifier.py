"""Classify Chinese prefectures into CO2 allocation-base archetypes.

The goal is a manuscript-facing typology, not a legal investment
recommendation. It converts city recommendation tables into a smaller number
of interpretable deployment archetypes for maps, tables, and Results text.
"""

from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CHINA = ROOT / "output" / "china2060_optimistic_profitability"
OUT = ROOT / "output" / "china2060_city_archetypes"
CEADS_CITY_SUMMARY = ROOT / "data" / "processed" / "co2_sources" / "ceads_city_emissions_prefecture_summary.csv"
YEARS = [2030, 2035, 2040, 2045, 2050, 2055, 2060]


ARCHETYPE_LABELS = {
    "storage_first": "Storage-first city",
    "mineralization_base": "Mineralization base",
    "coastal_saf_export_hub": "Coastal SAF/export hub",
    "northwest_h2_chemical_hub": "Northwest H2/chemical hub",
    "electrochemical_formate_hub": "Electrochemical/formate hub",
    "policy_backed_chemical_hub": "Policy-backed chemical hub",
    "wait_or_aggregate": "Wait / aggregate to hub",
}


ARCHETYPE_LOGIC = {
    "storage_first": "Nearer storage value dominates utilization; prioritize appraisal, pipelines and injection permits.",
    "mineralization_base": "Best route is carbonate/mineral product; prioritize aggregate standards and construction-material offtake.",
    "coastal_saf_export_hub": "SAF/fuels dominate; prioritize certified H2, fuel offtake, port logistics and aviation policy.",
    "northwest_h2_chemical_hub": "Low-carbon H2/renewables plus chemical route; prioritize H2 utility and CO/syngas contracts.",
    "electrochemical_formate_hub": "Electro/formate route dominates; prioritize flexible power, stack lifetime and specialty-product offtake.",
    "policy_backed_chemical_hub": "Thermochemical product route is positive but policy/offtake dependent.",
    "wait_or_aggregate": "No robust positive route; keep capture-ready, aggregate to hub, or wait for infrastructure/policy.",
}


NORTHWEST_REGIONS = {
    "Inner Mongolia",
    "Gansu",
    "Qinghai",
    "Ningxia",
    "Xinjiang",
    "Shaanxi",
    "Shanxi",
}


COASTAL_REGIONS = {
    "Shanghai",
    "Guangdong",
    "Fujian",
    "Zhejiang",
    "Jiangsu",
    "Shandong",
    "Liaoning",
    "Tianjin",
    "Hebei",
    "Guangxi",
    "Hainan",
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


def f(value: Any, default: float = 0.0) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(parsed):
        return default
    return parsed


def load_ceads_city_history() -> dict[str, dict[str, str]]:
    if not CEADS_CITY_SUMMARY.exists():
        return {}
    return {str(row["prefecture_code"]): row for row in read_csv(CEADS_CITY_SUMMARY)}


def classify(row: dict[str, str]) -> tuple[str, float]:
    best_pathway = row.get("best_pathway", "")
    best_family = row.get("best_family", "")
    best_product = row.get("best_product", "")
    source_region = row.get("source_region", "")
    margin = f(row.get("best_margin_usd_per_tco2"), -math.inf)
    storage_margin = f(row.get("best_storage_margin_usd_per_tco2"), -math.inf)
    nonstorage_margin = f(row.get("best_nonstorage_margin_usd_per_tco2"), -math.inf)
    storage_distance = f(row.get("nearest_storage_distance_km"), math.inf)

    if margin <= 0:
        return "wait_or_aggregate", min(0.95, max(0.30, abs(margin) / 500.0))
    if best_pathway == "mineralization":
        return "mineralization_base", min(0.95, 0.55 + margin / 1000.0)
    if best_product == "sustainable_aviation_fuel" or "saf" in best_pathway:
        if source_region in COASTAL_REGIONS:
            return "coastal_saf_export_hub", min(0.95, 0.60 + margin / 2000.0)
        return "policy_backed_chemical_hub", min(0.90, 0.50 + margin / 2500.0)
    if best_family == "storage" or (storage_distance <= 350 and storage_margin >= nonstorage_margin - 50):
        return "storage_first", min(0.95, 0.55 + max(storage_margin, margin) / 1200.0)
    if best_family == "electrochemical" or "formate" in best_product:
        return "electrochemical_formate_hub", min(0.90, 0.50 + margin / 2000.0)
    if source_region in NORTHWEST_REGIONS and best_pathway in {"rwgs_to_co", "co2_to_methanol", "co2_to_methane"}:
        return "northwest_h2_chemical_hub", min(0.90, 0.55 + margin / 2000.0)
    if best_family == "thermochemical":
        return "policy_backed_chemical_hub", min(0.90, 0.50 + margin / 2500.0)
    return "wait_or_aggregate", 0.40


def enrich_row(year: int, row: dict[str, str], ceads_history: dict[str, dict[str, str]]) -> dict[str, Any]:
    archetype, confidence = classify(row)
    margin = f(row.get("best_margin_usd_per_tco2"), -math.inf)
    npv = f(row.get("best_npv_proxy_musd"), 0.0)
    candidate_count = int(f(row.get("candidate_count"), 0.0))
    ceads = ceads_history.get(str(row.get("city_id", "")), {})
    return {
        "year": year,
        "city_id": row.get("city_id", ""),
        "city_name": row.get("city_name", ""),
        "source_region": row.get("source_region", ""),
        "archetype": archetype,
        "archetype_label": ARCHETYPE_LABELS[archetype],
        "archetype_confidence": round(confidence, 3),
        "investment_logic": ARCHETYPE_LOGIC[archetype],
        "recommended_base_from_previous_model": row.get("recommended_base", ""),
        "best_pathway": row.get("best_pathway", ""),
        "best_product": row.get("best_product", ""),
        "best_family": row.get("best_family", ""),
        "best_margin_usd_per_tco2": margin,
        "best_npv_proxy_musd": npv,
        "nearest_storage_distance_km": f(row.get("nearest_storage_distance_km"), math.inf),
        "storage_distance_band": row.get("storage_distance_band", ""),
        "best_storage_margin_usd_per_tco2": f(row.get("best_storage_margin_usd_per_tco2"), -math.inf),
        "best_nonstorage_pathway": row.get("best_nonstorage_pathway", ""),
        "best_nonstorage_margin_usd_per_tco2": f(row.get("best_nonstorage_margin_usd_per_tco2"), -math.inf),
        "candidate_count": candidate_count,
        "ceads_history_match": int(bool(ceads)),
        "ceads_latest_year": ceads.get("latest_year", ""),
        "ceads_latest_emissions_mtco2": f(ceads.get("latest_emissions_mtco2"), 0.0) if ceads else "",
        "ceads_peak_year": ceads.get("peak_year", ""),
        "ceads_peak_emissions_mtco2": f(ceads.get("peak_emissions_mtco2"), 0.0) if ceads else "",
        "ceads_emissions_2010_mtco2": f(ceads.get("emissions_2010_mtco2"), 0.0) if ceads else "",
        "ceads_emissions_2019_mtco2": f(ceads.get("emissions_2019_mtco2"), 0.0) if ceads else "",
        "ceads_change_2010_to_latest_pct": ceads.get("change_2010_to_latest_pct", ""),
        "ceads_trend_slope_mtco2_per_year": f(ceads.get("trend_slope_mtco2_per_year"), 0.0) if ceads else "",
        "ceads_years_observed": ceads.get("years_observed", ""),
        "ceads_match_confidence_min": ceads.get("match_confidence_min", ""),
        "ceads_history_evidence_grade": ceads.get("history_evidence_grade", ""),
    }


def summarize(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[tuple[int, str], dict[str, Any]] = {}
    for row in rows:
        key = (int(row["year"]), str(row["archetype"]))
        bucket = buckets.setdefault(
            key,
            {
                "year": row["year"],
                "archetype": row["archetype"],
                "archetype_label": row["archetype_label"],
                "city_count": 0,
                "positive_city_count": 0,
                "mean_margin_usd_per_tco2": 0.0,
                "best_margin_usd_per_tco2": -math.inf,
                "best_city": "",
                "total_npv_proxy_busd": 0.0,
            },
        )
        bucket["city_count"] += 1
        margin = float(row["best_margin_usd_per_tco2"])
        if margin > 0:
            bucket["positive_city_count"] += 1
        bucket["mean_margin_usd_per_tco2"] += margin
        bucket["total_npv_proxy_busd"] += float(row["best_npv_proxy_musd"]) / 1000.0
        if margin > float(bucket["best_margin_usd_per_tco2"]):
            bucket["best_margin_usd_per_tco2"] = margin
            bucket["best_city"] = row["city_name"]
    out = []
    for bucket in buckets.values():
        bucket["mean_margin_usd_per_tco2"] = bucket["mean_margin_usd_per_tco2"] / max(1, bucket["city_count"])
        out.append(bucket)
    return sorted(out, key=lambda item: (int(item["year"]), str(item["archetype"])))


def top_rows(rows: list[dict[str, Any]], n: int = 20) -> list[dict[str, Any]]:
    out = []
    for year in YEARS:
        year_rows = [row for row in rows if int(row["year"]) == year]
        for archetype in ARCHETYPE_LABELS:
            group = [row for row in year_rows if row["archetype"] == archetype]
            group.sort(key=lambda item: float(item["best_margin_usd_per_tco2"]), reverse=True)
            for rank, row in enumerate(group[:n], start=1):
                out.append({"rank_within_archetype": rank, **row})
    return out


def write_findings(rows: list[dict[str, Any]], summary_rows: list[dict[str, Any]]) -> None:
    rows_2060 = [row for row in rows if int(row["year"]) == 2060]
    positive_2060 = [row for row in rows_2060 if float(row["best_margin_usd_per_tco2"]) > 0]
    ceads_matched_2060 = [row for row in rows_2060 if int(row.get("ceads_history_match", 0)) == 1]
    counts = {
        archetype: sum(1 for row in rows_2060 if row["archetype"] == archetype)
        for archetype in ARCHETYPE_LABELS
    }
    best = max(rows_2060, key=lambda row: float(row["best_margin_usd_per_tco2"]))
    text = [
        "# City Archetype Key Findings",
        "",
        f"- 2060 screened cities: {len(rows_2060)}.",
        f"- 2060 positive-margin cities: {len(positive_2060)}.",
        f"- 2060 screened cities with CEADs emission history: {len(ceads_matched_2060)}.",
        f"- Best 2060 city: {best['city_name']} via {best['best_pathway']} at {float(best['best_margin_usd_per_tco2']):.1f} USD/tCO2.",
        "- 2060 archetype counts:",
    ]
    for archetype, count in counts.items():
        text.append(f"  - {ARCHETYPE_LABELS[archetype]}: {count}.")
    text.extend(
        [
            "",
            "Manuscript interpretation: city planning should not start from CO2 volume alone. The model separates storage-first cities, mineralization bases, coastal SAF/export hubs, northwest H2/chemical hubs, electrochemical/formate hubs, policy-backed chemical hubs, and cities that should wait or aggregate to a hub.",
        ]
    )
    (OUT / "city_archetype_key_findings.md").write_text("\n".join(text), encoding="utf-8")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    ceads_history = load_ceads_city_history()
    rows: list[dict[str, Any]] = []
    for year in YEARS:
        path = CHINA / f"china2060_{year}_city_recommendations.csv"
        for row in read_csv(path):
            rows.append(enrich_row(year, row, ceads_history))
    summary_rows = summarize(rows)
    write_csv(OUT / "city_archetypes_by_year.csv", rows)
    write_csv(OUT / "city_archetype_summary.csv", summary_rows)
    write_csv(OUT / "top_cities_by_archetype.csv", top_rows(rows))
    write_findings(rows, summary_rows)
    print(f"Wrote city archetype outputs to {OUT}")


if __name__ == "__main__":
    main()
