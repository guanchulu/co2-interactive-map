"""Build data files for the interactive CO2 city map.

The web app deliberately consumes compact JSON/GeoJSON instead of the raw model
CSV files. This keeps the UI fast and makes the app reproducible from the
analysis outputs.
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any

try:
    from pypinyin import lazy_pinyin
except ImportError:  # pragma: no cover - optional UI-name helper
    lazy_pinyin = None


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "interactive_map" / "data"
CITY = ROOT / "output" / "china2060_city_archetypes"
FRONTIER = ROOT / "output" / "china2060_frontier_upgrade"
OPT = ROOT / "output" / "china2060_deployment_optimization"
STRESS = ROOT / "output" / "china2060_market_stress"
MM = ROOT / "output" / "multimodal_evidence_layer"
DATA = ROOT / "data"
CEADS_CITY_SUMMARY = DATA / "processed" / "co2_sources" / "ceads_city_emissions_prefecture_summary.csv"
CEADS_CITY_LONG = DATA / "processed" / "co2_sources" / "ceads_city_emissions_prefecture_long.csv"


PATHWAY_LABELS = {
    "geological_storage": "Geological storage",
    "mineralization": "Mineralization",
    "co2_h2_ft_saf": "FT-SAF",
    "co2_methanol_to_jet_saf": "MTJ-SAF",
    "rwgs_to_co": "RWGS-CO",
    "co2_to_methanol": "Methanol",
    "co2_to_methane": "Methane",
    "electrolysis_to_formate": "Electro-formate",
    "electrolysis_to_co": "Electro-CO",
    "electrolysis_to_ethylene": "Electro-ethylene",
    "photoelectrochemical_to_formate": "PEC-formate",
    "photocatalytic_to_co": "Photocatalytic CO",
}

CITY_DISPLAY_NAMES = {
    "120000": "Tianjin",
    "130200": "Tangshan",
    "130300": "Qinhuangdao",
    "130800": "Chengde",
    "130900": "Cangzhou",
    "150600": "Ordos",
    "152500": "Xilingol League",
    "330900": "Zhoushan",
    "341200": "Fuyang",
    "360400": "Jiujiang",
    "360500": "Xinyu",
    "370100": "Jinan",
    "370400": "Zaozhuang",
    "371100": "Rizhao",
    "371400": "Dezhou",
    "371600": "Binzhou",
    "420100": "Wuhan",
    "440300": "Shenzhen",
    "522700": "Qiannan",
    "610800": "Yulin",
    "620100": "Lanzhou",
    "620900": "Jiuquan",
    "632800": "Haixi",
    "640100": "Yinchuan",
    "650500": "Hami",
}

ADMIN_SUFFIXES = (
    "特别行政区",
    "维吾尔自治区",
    "壮族自治区",
    "回族自治区",
    "自治区",
    "自治州",
    "自治县",
    "省",
    "地区",
    "盟",
    "市",
    "县",
)


def contains_cjk(value: str) -> bool:
    return any("\u3400" <= char <= "\u9fff" for char in value)


def pinyin_title(value: str) -> str:
    cleaned = value.strip()
    for suffix in ADMIN_SUFFIXES:
        if cleaned.endswith(suffix):
            cleaned = cleaned[: -len(suffix)]
            break
    if not cleaned or not contains_cjk(cleaned) or lazy_pinyin is None:
        return ""
    joined = "".join(piece.lower() for piece in lazy_pinyin(cleaned, errors="ignore") if piece)
    return joined[:1].upper() + joined[1:] if joined else ""


def display_city_name(city_id: str, source_region: str, city_name: str = "") -> str:
    if city_id in CITY_DISPLAY_NAMES:
        return CITY_DISPLAY_NAMES[city_id]
    romanized = pinyin_title(city_name)
    if romanized:
        return romanized
    if city_name and not contains_cjk(city_name):
        return city_name
    return f"{source_region} prefecture {city_id}"


def display_admin_name(raw_name: str, fallback: str) -> str:
    romanized = pinyin_title(raw_name)
    if romanized:
        return romanized
    if raw_name and not contains_cjk(raw_name):
        return raw_name
    return fallback


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def f(value: Any, default: float = 0.0) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if math.isfinite(parsed) else default


def simplify_ring(ring: list[list[float]], max_points: int = 80) -> list[list[float]]:
    if len(ring) <= max_points:
        return ring
    step = max(1, len(ring) // max_points)
    sampled = ring[::step]
    if sampled[-1] != ring[-1]:
        sampled.append(ring[-1])
    return sampled


def simplify_geometry(geometry: dict[str, Any]) -> dict[str, Any]:
    geom_type = geometry.get("type")
    coords = geometry.get("coordinates", [])
    if geom_type == "Polygon":
        return {
            "type": "Polygon",
            "coordinates": [simplify_ring(ring) for ring in coords],
        }
    if geom_type == "MultiPolygon":
        return {
            "type": "MultiPolygon",
            "coordinates": [[simplify_ring(ring) for ring in polygon] for polygon in coords],
        }
    return geometry


def load_points(path: Path, id_col: str) -> dict[str, dict[str, Any]]:
    points: dict[str, dict[str, Any]] = {}
    if not path.exists():
        return points
    for row in read_csv(path):
        points[str(row[id_col])] = {
            "id": row[id_col],
            "region": row.get("region", ""),
            "type": row.get("source_type") or row.get("sink_type") or "",
            "lon": f(row.get("longitude")),
            "lat": f(row.get("latitude")),
            "capacity": f(row.get("co2_available_mtpa") or row.get("capacity_mtco2_per_year")),
        }
    return points


def load_ceads_city_histories() -> dict[str, dict[str, Any]]:
    if not CEADS_CITY_SUMMARY.exists() or not CEADS_CITY_LONG.exists():
        return {}
    summary_rows = {str(row["prefecture_code"]): row for row in read_csv(CEADS_CITY_SUMMARY)}
    series_by_city: dict[str, dict[int, float]] = {}
    for row in read_csv(CEADS_CITY_LONG):
        if row.get("match_status") != "matched" or int(f(row.get("use_in_map"))) != 1:
            continue
        city_id = str(row["prefecture_code"])
        year = int(f(row["year"]))
        series_by_city.setdefault(city_id, {})
        series_by_city[city_id][year] = series_by_city[city_id].get(year, 0.0) + f(row["emissions_mtco2"])
    histories: dict[str, dict[str, Any]] = {}
    for city_id, row in summary_rows.items():
        series = [
            {"year": year, "emissions_mtco2": value}
            for year, value in sorted(series_by_city.get(city_id, {}).items())
        ]
        histories[city_id] = {
            "available": True,
            "latest_year": int(f(row.get("latest_year"))),
            "latest_emissions_mtco2": f(row.get("latest_emissions_mtco2")),
            "peak_year": int(f(row.get("peak_year"))),
            "peak_emissions_mtco2": f(row.get("peak_emissions_mtco2")),
            "emissions_2010_mtco2": f(row.get("emissions_2010_mtco2")),
            "emissions_2019_mtco2": f(row.get("emissions_2019_mtco2")),
            "change_2010_to_latest_pct": f(row.get("change_2010_to_latest_pct"), None),
            "trend_slope_mtco2_per_year": f(row.get("trend_slope_mtco2_per_year")),
            "years_observed": int(f(row.get("years_observed"))),
            "match_confidence_min": f(row.get("match_confidence_min")),
            "history_evidence_grade": row.get("history_evidence_grade", ""),
            "series": series,
        }
    return histories


def build_city_metrics() -> dict[str, Any]:
    rows = read_csv(CITY / "city_archetypes_by_year.csv")
    features = read_csv(MM / "city_multimodal_features.csv") if (MM / "city_multimodal_features.csv").exists() else []
    feature_lookup = {str(row["city_id"]): row for row in features}
    ceads_histories = load_ceads_city_histories()
    by_city: dict[str, dict[str, Any]] = {}
    for row in rows:
        city_id = str(row["city_id"])
        year = str(int(row["year"]))
        city_display = display_city_name(city_id, row["source_region"], row.get("city_name", ""))
        record = by_city.setdefault(
            city_id,
            {
                "city_id": city_id,
                "city_name": city_display,
                "city_name_en": city_display,
                "display_name": city_display,
                "display_name_en": city_display,
                "source_region": row["source_region"],
                "timeline": {},
                "allocations": [],
                "ceads_history": ceads_histories.get(city_id, {"available": False, "series": []}),
            },
        )
        record["timeline"][year] = {
            "archetype": row["archetype"],
            "archetype_label": row["archetype_label"],
            "archetype_confidence": f(row["archetype_confidence"]),
            "investment_logic": row["investment_logic"],
            "recommended_base": row["recommended_base_from_previous_model"],
            "best_pathway": row["best_pathway"],
            "best_pathway_label": PATHWAY_LABELS.get(row["best_pathway"], row["best_pathway"]),
            "best_product": row["best_product"],
            "best_family": row["best_family"],
            "best_margin_usd_per_tco2": f(row["best_margin_usd_per_tco2"]),
            "best_npv_proxy_musd": f(row["best_npv_proxy_musd"]),
            "nearest_storage_distance_km": f(row["nearest_storage_distance_km"]),
            "storage_distance_band": row["storage_distance_band"],
            "best_storage_margin_usd_per_tco2": f(row["best_storage_margin_usd_per_tco2"]),
            "best_nonstorage_pathway": row["best_nonstorage_pathway"],
            "best_nonstorage_margin_usd_per_tco2": f(row["best_nonstorage_margin_usd_per_tco2"]),
            "candidate_count": f(row["candidate_count"]),
        }
    for city_id, row in feature_lookup.items():
        if city_id not in by_city:
            continue
        by_city[city_id]["multimodal"] = {
            "readiness_score": f(row["multimodal_readiness_score"]),
            "dominant_allocation_category": row["dominant_allocation_category"],
            "first_profitable_year": row.get("first_profitable_year", ""),
            "fusion_scores": {
                "near_term_profit": f(row.get("fusion_near_term_profit_score")),
                "neutrality_backbone": f(row.get("fusion_2060_neutrality_backbone_score")),
                "policy_exit_resilience": f(row.get("fusion_policy_exit_resilience_score")),
                "data_quality_priority": f(row.get("fusion_data_quality_priority_score")),
            },
            "fusion_ranks": {
                "near_term_profit": f(row.get("rank_near_term_profit")),
                "neutrality_backbone": f(row.get("rank_2060_neutrality_backbone")),
                "policy_exit_resilience": f(row.get("rank_policy_exit_resilience")),
                "data_quality_priority": f(row.get("rank_data_quality_priority")),
            },
            "component_scores": {
                "policy_text": f(row.get("feature_policy_text_score")),
                "visual_remote_sensing": f(row.get("feature_visual_remote_sensing_score")),
                "process_flowsheet": f(row.get("feature_process_flowsheet_score")),
                "reservoir_simulation": f(row.get("feature_reservoir_simulation_score")),
            },
            "component_sources": {
                "policy_top_doc_ids": row.get("policy_top_doc_ids", ""),
                "visual_raster_status": row.get("visual_raster_status", ""),
                "flowsheet_source_type": row.get("flowsheet_source_type", ""),
                "reservoir_simulator": row.get("reservoir_simulator", ""),
            },
            "flags": {
                "TEA/LCA": f(row["tabular_tea_lca_flag"]),
                "Geospatial": f(row["geospatial_vector_flag"]),
                "Temporal policy": f(row["temporal_power_policy_flag"]),
                "Policy text embedding": f(row["text_policy_literature_flag"]),
                "Process/reservoir simulation": f(row["process_simulation_flag"]),
                "Satellite/visual proxy": f(row["remote_sensing_facility_proxy_flag"]),
                "Market demand": f(row["market_demand_flag"]),
            },
        }
    return by_city


def attach_allocations(cities: dict[str, Any]) -> list[dict[str, Any]]:
    rows = read_csv(FRONTIER / "frontier_top_allocations.csv")
    sources = load_points(DATA / "real_inputs_top300_with_dac" / "spatial_sources_real.csv", "source_id")
    destinations = load_points(DATA / "real_inputs_top300_with_dac" / "spatial_destinations_real.csv", "destination_id")
    route_links: list[dict[str, Any]] = []
    for row in rows:
        if row["frontier_target_label"] != "max_profit" or int(row["year"]) != 2060 or row["scenario"] != "policy_supported_effort":
            continue
        city_id = str(row["city_id"])
        allocation = {
            "source_id": row["source_id"],
            "destination_id": row["destination_id"],
            "category": row["category"],
            "pathway": row["pathway"],
            "pathway_label": row["pathway_label"],
            "product": row["product"],
            "allocated_mtco2_per_year": f(row["allocated_mtco2_per_year"]),
            "margin_usd_per_tco2": f(row["adjusted_margin_usd_per_tco2"]),
            "profit_musd_per_year": f(row["profit_musd_per_year"]),
            "durable_flag": int(row["durable_flag"]),
            "distance_km": f(row["distance_km"]),
        }
        if city_id in cities:
            cities[city_id]["allocations"].append(allocation)
        source = sources.get(row["source_id"])
        dest = destinations.get(row["destination_id"])
        if source and dest:
            route_links.append(
                {
                    **allocation,
                    "city_id": city_id,
                    "source_lon": source["lon"],
                    "source_lat": source["lat"],
                    "destination_lon": dest["lon"],
                    "destination_lat": dest["lat"],
                    "source_type": source["type"],
                    "destination_type": dest["type"],
                }
            )
    for city in cities.values():
        total = sum(item["allocated_mtco2_per_year"] for item in city["allocations"])
        durable = sum(item["allocated_mtco2_per_year"] for item in city["allocations"] if item["durable_flag"])
        profit = sum(item["profit_musd_per_year"] for item in city["allocations"])
        city["allocation_summary"] = {
            "allocated_mtco2_per_year": total,
            "durable_mtco2_per_year": durable,
            "profit_musd_per_year": profit,
            "route_count": len(city["allocations"]),
        }
        city["allocations"].sort(key=lambda item: item["allocated_mtco2_per_year"], reverse=True)
    route_links.sort(key=lambda item: item["allocated_mtco2_per_year"], reverse=True)
    return route_links


def build_boundaries(cities: dict[str, Any]) -> dict[str, Any]:
    admin = json.loads((DATA / "admin" / "prefecture_boundaries.geojson").read_text(encoding="utf-8"))
    out_features = []
    for feature in admin.get("features", []):
        props = feature.get("properties", {})
        city_id = str(props.get("prefecture_code", ""))
        metrics = cities.get(city_id)
        city_display = metrics["display_name"] if metrics else f"City {city_id}"
        province_display = display_admin_name(props.get("province_name", ""), "Unknown province")
        compact_props = {
            "city_id": city_id,
            "city_name": city_display,
            "city_name_en": city_display,
            "province_name": province_display,
            "province_name_en": province_display,
            "screened": bool(metrics),
            "center": props.get("center") or props.get("centroid"),
        }
        if metrics and "2060" in metrics["timeline"]:
            y2060 = metrics["timeline"]["2060"]
            y2030 = metrics["timeline"].get("2030", {})
            compact_props.update(
                {
                    "archetype": y2060["archetype"],
                    "best_pathway": y2060["best_pathway"],
                    "best_margin_2030": y2030.get("best_margin_usd_per_tco2"),
                    "best_margin_2060": y2060["best_margin_usd_per_tco2"],
                    "allocated_2060": metrics["allocation_summary"]["allocated_mtco2_per_year"],
                    "ceads_latest_emissions": metrics.get("ceads_history", {}).get("latest_emissions_mtco2"),
                }
            )
        out_features.append(
            {
                "type": "Feature",
                "properties": compact_props,
                "geometry": simplify_geometry(feature.get("geometry", {})),
            }
        )
    return {"type": "FeatureCollection", "features": out_features}


def build_supporting_tables() -> dict[str, Any]:
    uncertainty = {
        row["pathway"]: {
            "pathway_label": row["pathway_label"],
            "product": row["product"],
            "probability_positive": f(row["probability_positive"]),
            "p05": f(row["margin_p05_usd_per_tco2"]),
            "p50": f(row["margin_p50_usd_per_tco2"]),
            "p95": f(row["margin_p95_usd_per_tco2"]),
        }
        for row in read_csv(OPT / "uncertainty_positive_probability.csv")
    }
    drivers: dict[str, list[dict[str, Any]]] = {}
    driver_path = OPT / "uncertainty_driver_rank.csv"
    if driver_path.exists():
        for row in read_csv(driver_path):
            drivers.setdefault(row["pathway"], []).append(
                {"driver": row["driver"], "correlation": f(row["abs_correlation_with_margin"])}
            )
    stress_rows = [
        row
        for row in read_csv(STRESS / "market_stress_summary.csv")
        if int(row["year"]) == 2060 and row["pathway"] == "all"
    ]
    stress = [
        {
            "scenario": row["scenario"],
            "scenario_label": row["scenario_label"],
            "category": row["category"],
            "category_label": row["category_label"],
            "profit_busd_per_year": f(row["profit_busd_per_year"]),
            "allocated_mtco2_per_year": f(row["allocated_mtco2_per_year"]),
        }
        for row in stress_rows
    ]
    manifest_path = MM / "modality_manifest.csv"
    modalities = read_csv(manifest_path) if manifest_path.exists() else []
    return {"uncertainty": uncertainty, "drivers": drivers, "stress": stress, "modalities": modalities}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    cities = build_city_metrics()
    route_links = attach_allocations(cities)
    boundaries = build_boundaries(cities)
    support = build_supporting_tables()
    summary = {
        "years": [2030, 2035, 2040, 2045, 2050, 2055, 2060],
        "city_count": len(cities),
        "positive_2030": sum(1 for city in cities.values() if city["timeline"].get("2030", {}).get("best_margin_usd_per_tco2", -1) > 0),
        "positive_2060": sum(1 for city in cities.values() if city["timeline"].get("2060", {}).get("best_margin_usd_per_tco2", -1) > 0),
        "allocated_cities_2060": sum(1 for city in cities.values() if city["allocation_summary"]["allocated_mtco2_per_year"] > 0),
        "managed_mtco2_2060": sum(city["allocation_summary"]["allocated_mtco2_per_year"] for city in cities.values()),
        "durable_mtco2_2060": sum(city["allocation_summary"]["durable_mtco2_per_year"] for city in cities.values()),
        "profit_busd_2060": sum(city["allocation_summary"]["profit_musd_per_year"] for city in cities.values()) / 1000.0,
        "ceads_history_city_count": sum(1 for city in cities.values() if city.get("ceads_history", {}).get("available")),
        "ceads_latest_emissions_mtco2_sum": sum(
            f(city.get("ceads_history", {}).get("latest_emissions_mtco2"))
            for city in cities.values()
            if city.get("ceads_history", {}).get("available")
        ),
    }
    write_json(OUT / "city_boundaries.geojson", boundaries)
    write_json(OUT / "city_metrics.json", cities)
    write_json(OUT / "route_links.json", route_links)
    write_json(OUT / "supporting_tables.json", support)
    write_json(OUT / "summary.json", summary)
    print(f"Wrote interactive map data to {OUT}")


if __name__ == "__main__":
    main()
