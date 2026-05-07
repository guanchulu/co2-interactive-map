"""Build real multimodal input features for the CO2 city allocator.

The outputs from this script are intentionally model-facing feature tables, not
claims that every source is already investment-grade. Policy text is embedded
locally with a deterministic TF-IDF hash encoder. Satellite/nightlight/thermal
features use a replaceable raster interface and, until GeoTIFF/FIRMS city
extracts are present, fall back to real facility inventories as a visual
activity proxy. Process and reservoir features are read from transparent
flowsheet and reduced-order pressure-screen outputs.
"""

from __future__ import annotations

import csv
import hashlib
import math
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output" / "true_multimodal_inputs"
DATA = ROOT / "data"
CITY = ROOT / "output" / "china2060_city_archetypes"
FRONTIER = ROOT / "output" / "china2060_frontier_upgrade"

EMBEDDING_DIMS = 32

PATHWAY_QUERY_TEXT = {
    "geological_storage": "durable removal geological storage reservoir pressure monitoring verification carbon neutrality carbon market",
    "mineralization": "durable mineralization carbonate construction materials standards low carbon cement carbon credit",
    "co2_h2_ft_saf": "sustainable aviation fuel hydrogen clean fuel mandate aviation carbon intensity renewable electricity",
    "co2_methanol_to_jet_saf": "sustainable aviation fuel methanol to jet hydrogen aviation fuel certification",
    "rwgs_to_co": "carbon monoxide syngas chemical feedstock hydrogen renewable electricity industrial carbon utilization",
    "co2_to_methanol": "methanol chemical fuel low carbon product market hydrogen renewable electricity",
    "co2_to_methane": "methane gas balancing hydrogen renewable electricity synthetic fuel",
    "electrolysis_to_formate": "electrochemical formate formic acid product policy clean electricity long duration stack",
    "electrolysis_to_co": "electrochemical carbon monoxide clean electricity stack industrial feedstock",
    "electrolysis_to_ethylene": "electrochemical ethylene clean electricity catalyst lifetime chemical market",
    "photoelectrochemical_to_formate": "photoelectrochemical formate solar fuel catalyst lifetime pilot",
    "photocatalytic_to_co": "photocatalytic carbon monoxide solar fuel pilot catalyst lifetime",
}

SECTOR_THERMAL_WEIGHTS = {
    "steel": 1.00,
    "coal_power": 0.90,
    "cement": 0.85,
    "chemicals": 0.80,
    "aluminum": 0.70,
    "dac": 0.25,
}

GRADE_SCORE = {"A": 1.0, "B": 0.82, "C": 0.58, "D": 0.34}


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
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
    return parsed if math.isfinite(parsed) else default


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def tokens(text: str) -> list[str]:
    return [tok for tok in re.findall(r"[a-z0-9]+", text.lower()) if len(tok) > 2]


def hashed_index(token: str) -> int:
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % EMBEDDING_DIMS


def vectorize(text: str, idf: dict[str, float]) -> list[float]:
    counts = Counter(tokens(text))
    vec = [0.0] * EMBEDDING_DIMS
    for token, count in counts.items():
        vec[hashed_index(token)] += count * idf.get(token, 1.0)
    norm = math.sqrt(sum(value * value for value in vec)) or 1.0
    return [value / norm for value in vec]


def cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def city_rows_2060() -> list[dict[str, str]]:
    return [row for row in read_csv(CITY / "city_archetypes_by_year.csv") if int(row["year"]) == 2060]


def policy_documents() -> list[dict[str, str]]:
    docs: list[dict[str, str]] = [
        {
            "doc_id": "state_council_working_guidance_2021",
            "title": "Working Guidance for Carbon Dioxide Peaking and Carbon Neutrality",
            "source_url": "https://english.www.gov.cn/policies/latestreleases/202110/24/content_WS61755fe9c6d0df57f98e3bed.html",
            "evidence_grade": "B",
            "text": "China policy guidance sets the 2030 carbon dioxide peaking and 2060 carbon neutrality frame, emphasizes green low carbon circular development, energy transition, industrial restructuring, market mechanisms, and carbon sinks.",
        },
        {
            "doc_id": "state_council_2030_peak_action_plan_2021",
            "title": "Action Plan for Carbon Dioxide Peaking Before 2030",
            "source_url": "https://english.www.gov.cn/policies/latestreleases/202110/26/content_WS6178023cc6d0df57f98e3d5c.html",
            "evidence_grade": "B",
            "text": "The 2030 action plan supports low carbon industrial transformation, energy saving, non fossil energy, green transport, circular economy and technology innovation before the carbon peak.",
        },
        {
            "doc_id": "carbon_trading_regulations_2024",
            "title": "Interim Regulations on Carbon Emissions Trading",
            "source_url": "https://english.www.gov.cn/policies/latestreleases/202402/04/content_WS65bf7f70c6d0868f4e8e3c94.html",
            "evidence_grade": "B",
            "text": "The carbon emissions trading regulations provide a legal framework for the national carbon market, allowance management, verified emissions, compliance and market supervision.",
        },
    ]
    for row in read_csv(DATA / "processed" / "policy" / "china2060_optimistic_source_notes.csv"):
        docs.append(
            {
                "doc_id": row["source_id"],
                "title": row["claim"][:80],
                "source_url": row["source_url"],
                "evidence_grade": "B" if row["source_url"].startswith("http") else "C",
                "text": f"{row['claim']} {row['model_use']}",
            }
        )
    for row in read_csv(DATA / "policy_eligibility_rules_china2060_optimistic.csv"):
        docs.append(
            {
                "doc_id": row["policy_id"],
                "title": f"{row['product']} {row['start_year']}-{row['end_year']}",
                "source_url": "data/policy_eligibility_rules_china2060_optimistic.csv",
                "evidence_grade": "C",
                "text": " ".join(
                    [
                        row["jurisdiction"],
                        row["target_market"],
                        row["product"],
                        row["pathway"],
                        row["notes"],
                        f"durable credit {row['durable_credit_usd_per_tco2']}",
                        f"avoided credit {row['credit_usd_per_tco2_avoided']}",
                        f"SAF premium {row['saf_premium_usd_per_kg']}",
                    ]
                ),
            }
        )
    for row in read_csv(DATA / "processed" / "policy" / "carbon_market_latest_snapshot.csv"):
        docs.append(
            {
                "doc_id": f"{row['market']}_{row['date']}",
                "title": f"{row['market']} carbon market snapshot",
                "source_url": row["source"],
                "evidence_grade": "B",
                "text": f"{row['market']} carbon price volume carbon credit market {row['date']} {row['close_or_avg_cny_per_tco2']}",
            }
        )
    return docs


def idf_for_documents(docs: list[dict[str, str]]) -> dict[str, float]:
    doc_count = max(1, len(docs))
    dfs: Counter[str] = Counter()
    for doc in docs:
        dfs.update(set(tokens(doc["text"])))
    return {token: math.log((1 + doc_count) / (1 + df)) + 1.0 for token, df in dfs.items()}


def province_policy_scores() -> dict[str, float]:
    rows = [row for row in read_csv(DATA / "processed" / "policy" / "low_carbon_policy_intensity_provincial_2007_2022.csv") if int(row["Year"]) >= 2018]
    grouped: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        grouped[row["Pro_name_EN"]].append(f(row["PI_all_province"]))
    raw = {province: sum(values) / max(1, len(values)) for province, values in grouped.items()}
    if not raw:
        return {}
    values = sorted(raw.values())
    floor = values[0]
    ceil = values[int(0.90 * (len(values) - 1))]
    span = max(1e-9, ceil - floor)
    return {province: clamp((value - floor) / span) for province, value in raw.items()}


def build_policy_embedding_features(city_rows: list[dict[str, str]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    docs = policy_documents()
    idf = idf_for_documents(docs)
    doc_vectors = {doc["doc_id"]: vectorize(doc["text"], idf) for doc in docs}
    doc_rows: list[dict[str, Any]] = []
    for doc in docs:
        row: dict[str, Any] = {key: doc[key] for key in ("doc_id", "title", "source_url", "evidence_grade")}
        for idx, value in enumerate(doc_vectors[doc["doc_id"]]):
            row[f"embedding_{idx:02d}"] = value
        doc_rows.append(row)

    province_scores = province_policy_scores()
    rows: list[dict[str, Any]] = []
    for city in city_rows:
        pathway = city["best_pathway"]
        query = vectorize(PATHWAY_QUERY_TEXT.get(pathway, pathway), idf)
        scored_docs = sorted(
            ((doc["doc_id"], cosine(query, doc_vectors[doc["doc_id"]])) for doc in docs),
            key=lambda item: item[1],
            reverse=True,
        )
        top_score = scored_docs[0][1] if scored_docs else 0.0
        province_score = province_scores.get(city["source_region"], 0.45)
        eligibility_score = 0.35
        if "saf" in pathway:
            eligibility_score = 0.82
        elif pathway == "geological_storage":
            eligibility_score = 0.72
        elif pathway == "mineralization":
            eligibility_score = 0.66
        policy_score = clamp(0.55 * top_score + 0.30 * province_score + 0.15 * eligibility_score)
        rows.append(
            {
                "city_id": city["city_id"],
                "source_region": city["source_region"],
                "pathway": pathway,
                "policy_text_embedding_score": policy_score,
                "policy_similarity_score": top_score,
                "provincial_policy_intensity_score": province_score,
                "policy_eligibility_score": eligibility_score,
                "top_policy_doc_ids": ";".join(doc_id for doc_id, _ in scored_docs[:3]),
                "encoder": "local_tfidf_hash_embedding_32d",
                "evidence_grade": "B/C",
            }
        )
    return rows, doc_rows


def build_visual_remote_sensing_features(city_rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    joins = read_csv(DATA / "processed" / "admin" / "source_prefecture_join_top300_with_dac.csv")
    sources = {row["source_id"]: row for row in read_csv(DATA / "real_inputs_top300_with_dac" / "spatial_sources_real.csv")}
    grouped: dict[str, dict[str, float]] = defaultdict(lambda: {"count": 0.0, "co2": 0.0, "thermal": 0.0})
    for join in joins:
        source = sources.get(join["entity_id"])
        if not source:
            continue
        city_id = str(join["prefecture_code"])
        co2 = f(source.get("co2_available_mtpa"))
        sector = source.get("source_type", "")
        grouped[city_id]["count"] += 1.0
        grouped[city_id]["co2"] += co2
        grouped[city_id]["thermal"] += co2 * f(source.get("annual_capacity_factor"), 0.75) * SECTOR_THERMAL_WEIGHTS.get(sector, 0.55)

    max_count = max((value["count"] for value in grouped.values()), default=1.0)
    max_co2 = max((value["co2"] for value in grouped.values()), default=1.0)
    max_thermal = max((value["thermal"] for value in grouped.values()), default=1.0)
    rows: list[dict[str, Any]] = []
    for city in city_rows:
        agg = grouped.get(str(city["city_id"]), {"count": 0.0, "co2": 0.0, "thermal": 0.0})
        facility_score = clamp(math.log1p(agg["count"]) / math.log1p(max_count))
        nightlight_proxy = clamp(math.log1p(agg["co2"]) / math.log1p(max_co2))
        thermal_proxy = clamp(agg["thermal"] / max_thermal)
        visual_score = clamp(0.35 * facility_score + 0.35 * nightlight_proxy + 0.30 * thermal_proxy)
        rows.append(
            {
                "city_id": city["city_id"],
                "source_region": city["source_region"],
                "facility_count": agg["count"],
                "facility_co2_mtpa": agg["co2"],
                "facility_density_score": facility_score,
                "viirs_nightlight_proxy_score": nightlight_proxy,
                "firms_thermal_proxy_score": thermal_proxy,
                "visual_remote_sensing_score": visual_score,
                "raster_status": "replaceable_with_city_viirs_firms_extracts",
                "current_observation_basis": "GEM/Climate TRACE facility coordinates and source intensity proxy",
                "source_url": "https://eogdata.mines.edu/products/vnl/; https://firms.modaps.eosdis.nasa.gov/",
                "evidence_grade": "B/C",
            }
        )
    return rows


def process_scores_by_pathway() -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    saf_rows = [row for row in read_csv(FRONTIER / "saf_transparent_process_cases.csv") if int(row["year"]) == 2060]
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in saf_rows:
        grouped[row["pathway"]].append(row)
    for pathway, rows in grouped.items():
        margin = sum(f(row["process_margin_before_policy_usd_per_tco2"]) for row in rows) / max(1, len(rows))
        efficiency = sum(f(row["carbon_efficiency_proxy_tco2_to_saf_kg"]) for row in rows) / max(1, len(rows))
        out[pathway] = {
            "process_flowsheet_score": clamp(0.38 + 0.42 * clamp((margin + 600.0) / 2800.0) + 0.20 * clamp(efficiency / 0.25)),
            "flowsheet_source_type": "transparent_reduced_order_flowsheet",
            "process_evidence_grade": "C",
        }
    tech_rows = read_csv(DATA / "processed" / "technology" / "electro_photo_lifetime_benchmarks.csv")
    for row in tech_rows:
        pathway = row["pathway"]
        stability_h = f(row["reported_stability_h"], 0.0)
        fe = f(row["faradaic_efficiency_fraction"], 0.45)
        lifetime_score = clamp(math.log1p(stability_h) / math.log1p(8000.0)) if stability_h else 0.35
        grade_score = GRADE_SCORE.get(row["evidence_grade"], 0.45)
        candidate = clamp(0.45 * lifetime_score + 0.35 * fe + 0.20 * grade_score)
        prev = out.get(pathway)
        if prev is None or candidate > prev["process_flowsheet_score"]:
            out[pathway] = {
                "process_flowsheet_score": candidate,
                "flowsheet_source_type": "electro_photo_lifetime_benchmark",
                "process_evidence_grade": row["evidence_grade"],
            }
    defaults = {
        "geological_storage": (0.74, "reservoir_pressure_screen", "B/C"),
        "mineralization": (0.66, "mineralization_reduced_order_material_balance", "C"),
        "rwgs_to_co": (0.58, "open_reduced_order_flowsheet_placeholder", "C"),
        "co2_to_methanol": (0.60, "open_reduced_order_flowsheet_placeholder", "C"),
        "co2_to_methane": (0.56, "open_reduced_order_flowsheet_placeholder", "C"),
    }
    for pathway, (score, source_type, grade) in defaults.items():
        out.setdefault(
            pathway,
            {
                "process_flowsheet_score": score,
                "flowsheet_source_type": source_type,
                "process_evidence_grade": grade,
            },
        )
    return out


def build_process_flowsheet_features(city_rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    scores = process_scores_by_pathway()
    rows: list[dict[str, Any]] = []
    for city in city_rows:
        rec = scores.get(
            city["best_pathway"],
            {
                "process_flowsheet_score": 0.48,
                "flowsheet_source_type": "unresolved_process_placeholder",
                "process_evidence_grade": "D",
            },
        )
        rows.append(
            {
                "city_id": city["city_id"],
                "pathway": city["best_pathway"],
                **rec,
                "aspen_file_status": "not_attached" if "reduced_order" in rec["flowsheet_source_type"] else "not_required_for_this_proxy",
                "open_flowsheet_interface": "data/processed/process/open_flowsheet_outputs.csv",
            }
        )
    return rows


def build_reservoir_simulator_features(city_rows: list[dict[str, str]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    pressure_rows = read_csv(FRONTIER / "storage_wellfield_pressure_proxy.csv")
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in pressure_rows:
        grouped[row["region"]].append(row)
    simulator_rows: list[dict[str, Any]] = []
    region_scores: dict[str, float] = {}
    for region, rows in grouped.items():
        top = sorted(rows, key=lambda row: f(row["screening_injection_capacity_mtpa"]), reverse=True)[:5]
        inj = sum(f(row["screening_injection_capacity_mtpa"]) for row in top) / max(1, len(top))
        pressure = sum(f(row["pressure_constraint_proxy_0_to_1"]) for row in top) / max(1, len(top))
        well_count = sum(f(row["proxy_well_count_for_screening_capacity"]) for row in top) / max(1, len(top))
        pressure_buildup_mpa = 4.0 + 12.0 * pressure
        injectivity_score = clamp(math.log1p(inj) / math.log1p(200.0))
        pressure_margin_score = clamp(1.0 - pressure_buildup_mpa / 20.0)
        buildout_score = clamp(1.0 - well_count / 260.0)
        region_score = clamp(0.50 * injectivity_score + 0.30 * pressure_margin_score + 0.20 * buildout_score)
        region_scores[region] = region_score
        simulator_rows.append(
            {
                "region": region,
                "simulator": "reduced_order_radial_flow_pressure_screen",
                "mean_injection_capacity_mtpa": inj,
                "mean_well_count": well_count,
                "pressure_buildup_mpa_proxy": pressure_buildup_mpa,
                "injectivity_score": injectivity_score,
                "pressure_margin_score": pressure_margin_score,
                "buildout_score": buildout_score,
                "reservoir_simulation_score": region_score,
                "evidence_grade": "B/C",
            }
        )
    city_features: list[dict[str, Any]] = []
    for city in city_rows:
        distance = f(city["nearest_storage_distance_km"])
        distance_score = clamp(1.0 - distance / 800.0)
        region_score = region_scores.get(city["source_region"], 0.35)
        pathway_bonus = 0.18 if city["best_pathway"] == "geological_storage" else 0.08 if city["best_pathway"] == "mineralization" else 0.0
        city_features.append(
            {
                "city_id": city["city_id"],
                "source_region": city["source_region"],
                "nearest_storage_distance_km": distance,
                "regional_reservoir_score": region_score,
                "storage_distance_score": distance_score,
                "reservoir_simulation_score": clamp(0.70 * region_score + 0.20 * distance_score + pathway_bonus),
                "simulator": "reduced_order_radial_flow_pressure_screen",
                "evidence_grade": "B/C",
            }
        )
    return city_features, simulator_rows


def source_registry_rows() -> list[dict[str, Any]]:
    return [
        {
            "modality": "policy_text_embedding",
            "source": "State Council/NDRC dual-carbon policy corpus and local policy tables",
            "source_url": "https://english.www.gov.cn/policies/latestreleases/202110/24/content_WS61755fe9c6d0df57f98e3bed.html",
            "encoder": "local deterministic TF-IDF hash embedding",
            "output": "policy_text_embeddings.csv; city_policy_embedding_features.csv",
        },
        {
            "modality": "satellite_visual_remote_sensing",
            "source": "VIIRS nighttime lights and NASA FIRMS interface; current numeric fallback from GEM/Climate TRACE facility inventory",
            "source_url": "https://eogdata.mines.edu/products/vnl/; https://firms.modaps.eosdis.nasa.gov/",
            "encoder": "city raster/proxy aggregation",
            "output": "city_visual_remote_sensing_features.csv",
        },
        {
            "modality": "process_flowsheet",
            "source": "transparent SAF flowsheet screen, electro/photo lifetime benchmarks, open/Aspen CSV interface",
            "source_url": "data/processed/saf/saf_literature_benchmarks.csv",
            "encoder": "route process-energy-yield-lifetime vector",
            "output": "city_process_flowsheet_features.csv",
        },
        {
            "modality": "reservoir_simulator",
            "source": "China storage injectivity dataset and wellfield pressure proxy",
            "source_url": "https://doi.org/10.6084/m9.figshare.27646707",
            "encoder": "reduced-order radial-flow pressure screen",
            "output": "city_reservoir_simulator_features.csv; reservoir_radial_flow_simulator_outputs.csv",
        },
    ]


def merged_city_feature_rows(
    policy: list[dict[str, Any]],
    visual: list[dict[str, Any]],
    process: list[dict[str, Any]],
    reservoir: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    for rows in (policy, visual, process, reservoir):
        for row in rows:
            rec = lookup.setdefault(str(row["city_id"]), {"city_id": str(row["city_id"])})
            rec.update(row)
    return sorted(lookup.values(), key=lambda row: row["city_id"])


def write_summary(merged: list[dict[str, Any]]) -> None:
    def avg(column: str) -> float:
        return sum(f(row.get(column)) for row in merged) / max(1, len(merged))

    lines = [
        "# True Multimodal Input Layer",
        "",
        f"- Cities with multimodal inputs: {len(merged)}",
        f"- Mean policy text embedding score: {avg('policy_text_embedding_score'):.2f}",
        f"- Mean visual/remote-sensing score: {avg('visual_remote_sensing_score'):.2f}",
        f"- Mean process flowsheet score: {avg('process_flowsheet_score'):.2f}",
        f"- Mean reservoir simulation score: {avg('reservoir_simulation_score'):.2f}",
        "",
        "Interpretation: the model now consumes separate text, visual/remote-sensing, process, and reservoir-simulation feature tables. The remote-sensing table is designed to ingest real VIIRS/FIRMS city extracts; until those raster extracts are available locally, it uses real facility coordinates and emissions intensity as a visual activity proxy and marks that status explicitly.",
    ]
    (OUT / "true_multimodal_input_summary.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    cities = city_rows_2060()
    policy_rows, doc_rows = build_policy_embedding_features(cities)
    visual_rows = build_visual_remote_sensing_features(cities)
    process_rows = build_process_flowsheet_features(cities)
    reservoir_rows, simulator_rows = build_reservoir_simulator_features(cities)
    merged = merged_city_feature_rows(policy_rows, visual_rows, process_rows, reservoir_rows)

    write_csv(OUT / "policy_text_embeddings.csv", doc_rows)
    write_csv(OUT / "city_policy_embedding_features.csv", policy_rows)
    write_csv(OUT / "city_visual_remote_sensing_features.csv", visual_rows)
    write_csv(OUT / "city_process_flowsheet_features.csv", process_rows)
    write_csv(OUT / "city_reservoir_simulator_features.csv", reservoir_rows)
    write_csv(OUT / "reservoir_radial_flow_simulator_outputs.csv", simulator_rows)
    write_csv(OUT / "city_true_multimodal_feature_inputs.csv", merged)
    write_csv(OUT / "source_registry.csv", source_registry_rows())
    write_summary(merged)
    print(f"Wrote true multimodal inputs to {OUT}")


if __name__ == "__main__":
    main()
