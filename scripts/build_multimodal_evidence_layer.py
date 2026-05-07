"""Build a multimodal evidence-fusion layer for the CO2 allocation model.

The goal is not to claim a black-box AI model. It is to expose the modalities
that a reviewer would expect in a modern cross-scale CO2 paper: tabular TEA/LCA,
geospatial data, temporal power/policy trajectories, text evidence, process
models, market data, and industrial-source proxies.
"""

from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output" / "multimodal_evidence_layer"
CITY = ROOT / "output" / "china2060_city_archetypes"
FRONTIER = ROOT / "output" / "china2060_frontier_upgrade"
OPT = ROOT / "output" / "china2060_deployment_optimization"
STRESS = ROOT / "output" / "china2060_market_stress"
TRUE_MM = ROOT / "output" / "true_multimodal_inputs"


PATHWAY_TO_CATEGORY = {
    "geological_storage": "geological_storage",
    "mineralization": "mineral_products",
    "co2_h2_ft_saf": "synthetic_fuels",
    "co2_methanol_to_jet_saf": "synthetic_fuels",
    "rwgs_to_co": "chemicals",
    "co2_to_methanol": "chemicals",
    "co2_to_methane": "chemicals",
    "electrolysis_to_formate": "chemicals",
    "electrolysis_to_co": "chemicals",
    "electrolysis_to_ethylene": "chemicals",
    "photoelectrochemical_to_formate": "chemicals",
    "photocatalytic_to_co": "chemicals",
}


DECISION_MODE_WEIGHTS = {
    "near_term_profit": {
        "economic": 0.24,
        "temporal": 0.14,
        "allocation_fit": 0.12,
        "market": 0.10,
        "uncertainty": 0.10,
        "stress": 0.08,
        "evidence": 0.04,
        "policy_text": 0.05,
        "visual": 0.04,
        "flowsheet": 0.07,
        "reservoir": 0.02,
    },
    "2060_neutrality_backbone": {
        "durability": 0.22,
        "economic": 0.14,
        "spatial": 0.12,
        "stress": 0.11,
        "evidence": 0.08,
        "uncertainty": 0.08,
        "allocation_fit": 0.04,
        "policy_text": 0.06,
        "visual": 0.04,
        "flowsheet": 0.05,
        "reservoir": 0.06,
    },
    "policy_exit_resilience": {
        "stress": 0.23,
        "economic": 0.15,
        "uncertainty": 0.15,
        "market": 0.10,
        "evidence": 0.08,
        "temporal": 0.05,
        "allocation_fit": 0.04,
        "policy_text": 0.07,
        "visual": 0.04,
        "flowsheet": 0.06,
        "reservoir": 0.03,
    },
    "data_quality_priority": {
        "evidence": 0.20,
        "uncertainty": 0.13,
        "spatial": 0.10,
        "process": 0.10,
        "economic": 0.07,
        "stress": 0.07,
        "policy_text": 0.13,
        "visual": 0.08,
        "flowsheet": 0.07,
        "reservoir": 0.05,
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


def f(value: Any, default: float = 0.0) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if math.isfinite(parsed) else default


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def pathway_category(pathway: str) -> str:
    return PATHWAY_TO_CATEGORY.get(pathway, "chemicals")


def durability_score_for(pathway: str) -> float:
    if pathway == "geological_storage":
        return 1.0
    if pathway == "mineralization":
        return 0.92
    if pathway in ("co2_h2_ft_saf", "co2_methanol_to_jet_saf"):
        return 0.30
    return 0.42


def first_profitable_year(timeline: list[dict[str, str]]) -> int | None:
    positives = [int(row["year"]) for row in timeline if f(row["best_margin_usd_per_tco2"]) > 0]
    return min(positives) if positives else None


def temporal_score(first_year: int | None) -> float:
    if first_year is None:
        return 0.0
    return clamp(1.0 - (first_year - 2030) / 30.0)


def load_uncertainty() -> dict[str, dict[str, float]]:
    path = OPT / "uncertainty_positive_probability.csv"
    if not path.exists():
        return {}
    return {
        row["pathway"]: {
            "probability_positive": f(row["probability_positive"]),
            "p05": f(row["margin_p05_usd_per_tco2"]),
            "p50": f(row["margin_p50_usd_per_tco2"]),
            "p95": f(row["margin_p95_usd_per_tco2"]),
        }
        for row in read_csv(path)
    }


def load_stress_scores() -> dict[str, dict[str, float]]:
    path = STRESS / "market_stress_summary.csv"
    if not path.exists():
        return {}
    rows = [row for row in read_csv(path) if int(row["year"]) == 2060 and row["pathway"] == "all"]
    by_category: dict[str, list[float]] = {}
    supported: dict[str, float] = {}
    for row in rows:
        category = row["category"]
        profit = f(row["profit_busd_per_year"])
        by_category.setdefault(category, []).append(profit)
        if row["scenario"] == "policy_supported_effort":
            supported[category] = profit
    out: dict[str, dict[str, float]] = {}
    for category, values in by_category.items():
        positive_fraction = sum(1 for value in values if value > 0) / max(1, len(values))
        supported_profit = max(0.0, supported.get(category, 0.0))
        average_profit = sum(values) / max(1, len(values))
        normalized_average = clamp((average_profit + 20.0) / (supported_profit + 20.0)) if supported_profit else positive_fraction
        out[category] = {
            "stress_positive_fraction": positive_fraction,
            "stress_average_profit_busd": average_profit,
            "stress_score": clamp(0.65 * positive_fraction + 0.35 * normalized_average),
        }
    return out


def load_true_multimodal_features() -> dict[str, dict[str, str]]:
    path = TRUE_MM / "city_true_multimodal_feature_inputs.csv"
    if not path.exists():
        return {}
    return {str(row["city_id"]): row for row in read_csv(path)}


def feature_scores(
    row: dict[str, str],
    timeline: list[dict[str, str]],
    alloc: dict[str, Any],
    modality_flags: dict[str, float],
    uncertainty: dict[str, dict[str, float]],
    stress_scores: dict[str, dict[str, float]],
    true_features: dict[str, str],
) -> dict[str, float]:
    pathway = row["best_pathway"]
    category = pathway_category(pathway)
    margin = f(row["best_margin_usd_per_tco2"])
    allocated = f(alloc.get("allocated_mtco2_per_year"))
    first_year = first_profitable_year(timeline)
    uncertainty_record = uncertainty.get(pathway, {})
    stress_record = stress_scores.get(category, {})
    flowsheet_score = clamp(f(true_features.get("process_flowsheet_score"), modality_flags["process_simulation"]))
    reservoir_score = clamp(f(true_features.get("reservoir_simulation_score"), 0.45))
    policy_text_score = clamp(f(true_features.get("policy_text_embedding_score"), modality_flags["text_policy_literature"]))
    visual_score = clamp(f(true_features.get("visual_remote_sensing_score"), modality_flags["remote_sensing_facility_proxy"]))
    return {
        "economic": clamp((margin + 150.0) / 1700.0),
        "temporal": temporal_score(first_year),
        "spatial": modality_flags["geospatial_vector"],
        "market": modality_flags["market_demand"],
        "process": clamp(0.60 * flowsheet_score + 0.40 * reservoir_score),
        "evidence": sum(modality_flags.values()) / len(modality_flags),
        "uncertainty": clamp(f(uncertainty_record.get("probability_positive"), 0.35)),
        "stress": clamp(f(stress_record.get("stress_score"), 0.35)),
        "durability": durability_score_for(pathway),
        "allocation_fit": clamp(math.log1p(max(0.0, allocated)) / math.log1p(32.0)),
        "policy_text": policy_text_score,
        "visual": visual_score,
        "flowsheet": flowsheet_score,
        "reservoir": reservoir_score,
    }


def fused_scores(scores: dict[str, float]) -> tuple[dict[str, float], list[dict[str, Any]]]:
    fused: dict[str, float] = {}
    contributions: list[dict[str, Any]] = []
    for mode, weights in DECISION_MODE_WEIGHTS.items():
        total = 0.0
        for feature, weight in weights.items():
            value = scores.get(feature, 0.0)
            contribution = value * weight
            total += contribution
            contributions.append(
                {
                    "decision_mode": mode,
                    "feature": feature,
                    "raw_score": value,
                    "weight": weight,
                    "contribution": contribution,
                }
            )
        fused[mode] = total
    return fused, contributions


def build_manifest() -> list[dict[str, Any]]:
    return [
        {
            "modality": "tabular_tea_lca",
            "current_inputs": "pathway costs, capture energy, product prices, policy values, uncertainty draws",
            "encoder": "standardized numeric feature table",
            "decision_use": "route margin, net emissions, uncertainty and profitability probability",
            "evidence_grade_now": "B/C",
            "upgrade_to_a_grade": "replace proxy product prices and process yields with audited market/process datasets",
        },
        {
            "modality": "geospatial_vector",
            "current_inputs": "prefecture boundaries, source-city joins, routed distance, storage/product destinations",
            "encoder": "city polygon, centroid, distance bands, hub adjacency",
            "decision_use": "source-sink matching, hub siting, transport penalty, national heatmap",
            "evidence_grade_now": "B",
            "upgrade_to_a_grade": "audited official prefecture boundaries, pipeline corridors, port/rail/road network costs",
        },
        {
            "modality": "temporal_power_policy",
            "current_inputs": "2030-2060 learning cases, electricity and grid-carbon proxies, policy support cases",
            "encoder": "year-scenario tensor",
            "decision_use": "break-even timing, policy-exit risk, China 2030/2060 alignment",
            "evidence_grade_now": "C",
            "upgrade_to_a_grade": "province hourly prices, hourly grid emissions, explicit dispatch or power-system coupling",
        },
        {
            "modality": "text_policy_literature",
            "current_inputs": "official dual-carbon policy notes, carbon-market rules, policy eligibility tables and literature-derived priors",
            "encoder": "deterministic local TF-IDF hash embeddings plus source provenance",
            "decision_use": "policy qualification, route eligibility, assumption provenance, reviewer traceability",
            "evidence_grade_now": "B/C",
            "upgrade_to_a_grade": "full legal-text corpus with human-audited retrieval passages and policy-effective-date tracking",
        },
        {
            "modality": "process_simulation",
            "current_inputs": "transparent SAF flowsheet screen, electro/photo lifetime benchmarks, open/Aspen CSV interface and reservoir pressure screen",
            "encoder": "process-yield, energy-intensity, lifetime and pressure feature vectors",
            "decision_use": "route-specific CAPEX/OPEX, H2 demand, separations, reliability, lifetime and injectivity penalty",
            "evidence_grade_now": "B/C",
            "upgrade_to_a_grade": "validated Aspen Plus, IDAES or DWSIM packages and calibrated field-scale reservoir simulators",
        },
        {
            "modality": "remote_sensing_facility_proxy",
            "current_inputs": "VIIRS/FIRMS source interfaces plus GEM/Climate TRACE facility coordinates and intensity proxies",
            "encoder": "city raster/proxy aggregation for nightlight, thermal anomaly and facility-density features",
            "decision_use": "CO2 source density, hub aggregation, capture-ready prioritization",
            "evidence_grade_now": "B/C",
            "upgrade_to_a_grade": "city-clipped VIIRS nightlight GeoTIFF and FIRMS thermal-anomaly CSV extracts with QA filtering",
        },
        {
            "modality": "market_demand",
            "current_inputs": "regional product market capacity, price saturation, SAF export and shock cases",
            "encoder": "regional demand ceiling and price-erosion curves",
            "decision_use": "avoid treating all CO2-derived products as unlimited sinks",
            "evidence_grade_now": "C",
            "upgrade_to_a_grade": "audited offtake, NBS/industry-yearbook product flows and regional import/export balances",
        },
    ]


def allocation_lookup() -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    path = FRONTIER / "frontier_top_allocations.csv"
    if not path.exists():
        return out
    for row in read_csv(path):
        if row["frontier_target_label"] != "max_profit" or int(row["year"]) != 2060:
            continue
        city_id = str(row["city_id"])
        record = out.setdefault(city_id, {"allocated_mtco2_per_year": 0.0, "profit_musd_per_year": 0.0, "categories": {}})
        mt = f(row["allocated_mtco2_per_year"])
        record["allocated_mtco2_per_year"] += mt
        record["profit_musd_per_year"] += f(row["profit_musd_per_year"])
        cats = record["categories"]
        cats[row["category"]] = cats.get(row["category"], 0.0) + mt
    for record in out.values():
        if record["categories"]:
            record["dominant_allocation_category"] = max(record["categories"].items(), key=lambda item: item[1])[0]
        else:
            record["dominant_allocation_category"] = "none"
    return out


def city_features() -> list[dict[str, Any]]:
    all_rows = read_csv(CITY / "city_archetypes_by_year.csv")
    timeline_by_city: dict[str, list[dict[str, str]]] = {}
    for row in all_rows:
        timeline_by_city.setdefault(str(row["city_id"]), []).append(row)
    rows = [row for row in all_rows if int(row["year"]) == 2060]
    allocations = allocation_lookup()
    uncertainty = load_uncertainty()
    stress_scores = load_stress_scores()
    true_feature_lookup = load_true_multimodal_features()
    output: list[dict[str, Any]] = []
    contribution_rows: list[dict[str, Any]] = []
    for row in rows:
        city_id = str(row["city_id"])
        alloc = allocations.get(city_id, {})
        margin = f(row["best_margin_usd_per_tco2"])
        storage_distance = f(row["nearest_storage_distance_km"])
        allocated = f(alloc.get("allocated_mtco2_per_year"))
        true_features = true_feature_lookup.get(city_id, {})
        policy_text_score = clamp(f(true_features.get("policy_text_embedding_score"), 0.60))
        visual_score = clamp(f(true_features.get("visual_remote_sensing_score"), 0.55))
        process_score = clamp(f(true_features.get("process_flowsheet_score"), 0.55))
        reservoir_score = clamp(f(true_features.get("reservoir_simulation_score"), 0.45))
        modality_flags = {
            "tabular_tea_lca": 1.0,
            "geospatial_vector": 1.0 if storage_distance > 0 else 0.6,
            "temporal_power_policy": 1.0,
            "text_policy_literature": policy_text_score,
            "process_simulation": clamp(0.65 * process_score + 0.35 * reservoir_score),
            "remote_sensing_facility_proxy": visual_score,
            "market_demand": 0.75 if row["best_product"] not in ("", "none") else 0.45,
        }
        if allocated > 0:
            modality_flags["market_demand"] = max(modality_flags["market_demand"], 0.85)
        readiness = sum(modality_flags.values()) / len(modality_flags)
        timeline = sorted(timeline_by_city.get(city_id, []), key=lambda item: int(item["year"]))
        first_year = first_profitable_year(timeline)
        scores = feature_scores(row, timeline, alloc, modality_flags, uncertainty, stress_scores, true_features)
        fused, contributions = fused_scores(scores)
        for contribution in contributions:
            contribution_rows.append(
                {
                    "city_id": city_id,
                    "city_name": row["city_name"],
                    "pathway": row["best_pathway"],
                    **contribution,
                }
            )
        output.append(
            {
                "city_id": city_id,
                "city_name": row["city_name"],
                "source_region": row["source_region"],
                "archetype": row["archetype"],
                "best_pathway": row["best_pathway"],
                "best_product": row["best_product"],
                "best_margin_usd_per_tco2": margin,
                "nearest_storage_distance_km": storage_distance,
                "allocated_mtco2_per_year": allocated,
                "allocation_profit_musd_per_year": f(alloc.get("profit_musd_per_year")),
                "dominant_allocation_category": alloc.get("dominant_allocation_category", "none"),
                "first_profitable_year": first_year or "",
                "pathway_category": pathway_category(row["best_pathway"]),
                "tabular_tea_lca_flag": modality_flags["tabular_tea_lca"],
                "geospatial_vector_flag": modality_flags["geospatial_vector"],
                "temporal_power_policy_flag": modality_flags["temporal_power_policy"],
                "text_policy_literature_flag": modality_flags["text_policy_literature"],
                "process_simulation_flag": modality_flags["process_simulation"],
                "remote_sensing_facility_proxy_flag": modality_flags["remote_sensing_facility_proxy"],
                "market_demand_flag": modality_flags["market_demand"],
                "multimodal_readiness_score": readiness,
                "feature_economic_score": scores["economic"],
                "feature_temporal_score": scores["temporal"],
                "feature_spatial_score": scores["spatial"],
                "feature_market_score": scores["market"],
                "feature_process_score": scores["process"],
                "feature_evidence_score": scores["evidence"],
                "feature_uncertainty_score": scores["uncertainty"],
                "feature_stress_score": scores["stress"],
                "feature_durability_score": scores["durability"],
                "feature_allocation_fit_score": scores["allocation_fit"],
                "feature_policy_text_score": scores["policy_text"],
                "feature_visual_remote_sensing_score": scores["visual"],
                "feature_process_flowsheet_score": scores["flowsheet"],
                "feature_reservoir_simulation_score": scores["reservoir"],
                "policy_top_doc_ids": true_features.get("top_policy_doc_ids", ""),
                "visual_raster_status": true_features.get("raster_status", ""),
                "flowsheet_source_type": true_features.get("flowsheet_source_type", ""),
                "reservoir_simulator": true_features.get("simulator", ""),
                "fusion_near_term_profit_score": fused["near_term_profit"],
                "fusion_2060_neutrality_backbone_score": fused["2060_neutrality_backbone"],
                "fusion_policy_exit_resilience_score": fused["policy_exit_resilience"],
                "fusion_data_quality_priority_score": fused["data_quality_priority"],
                "model_role": "train/evaluate candidate city-route ranking" if allocated > 0 else "screen or holdout city-route candidate",
            }
        )
    ranked = sorted(output, key=lambda row: (f(row["allocated_mtco2_per_year"]), f(row["best_margin_usd_per_tco2"])), reverse=True)
    write_csv(OUT / "city_modality_contributions.csv", contribution_rows)
    return ranked


def architecture_rows() -> list[dict[str, Any]]:
    return [
        {
            "stage": "1_ingest",
            "operation": "load tabular, geospatial, temporal, policy-text embeddings, remote-sensing proxies, process, reservoir and market inputs",
            "output": "modality-specific feature tables with evidence grades",
        },
        {
            "stage": "2_encode",
            "operation": "standardize numeric features, distance bands, year-scenario tensors, TF-IDF policy embeddings, visual activity proxies and process vectors",
            "output": "city-route feature vectors plus modality masks",
        },
        {
            "stage": "3_fuse",
            "operation": "late-fusion weighting by evidence grade and uncertainty; missing modalities remain explicit",
            "output": "multimodal readiness score and uncertainty-adjusted margin",
        },
        {
            "stage": "4_decide",
            "operation": "feed fused city-route candidates into LP/MILP allocation, stress tests and Monte Carlo",
            "output": "profit, durable CO2, robustness and feasibility frontier",
        },
        {
            "stage": "5_audit",
            "operation": "emit source trace, modality coverage and reviewer-facing limitation flags",
            "output": "transparent SI tables and reproducible data provenance",
        },
    ]


def add_ranks(features: list[dict[str, Any]]) -> None:
    rank_columns = {
        "near_term_profit": "fusion_near_term_profit_score",
        "2060_neutrality_backbone": "fusion_2060_neutrality_backbone_score",
        "policy_exit_resilience": "fusion_policy_exit_resilience_score",
        "data_quality_priority": "fusion_data_quality_priority_score",
    }
    for mode, column in rank_columns.items():
        ordered = sorted(features, key=lambda row: f(row[column]), reverse=True)
        for rank, row in enumerate(ordered, start=1):
            row[f"rank_{mode}"] = rank


def pathway_summary(features: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in features:
        grouped.setdefault(str(row["best_pathway"]), []).append(row)
    rows: list[dict[str, Any]] = []
    for pathway, group in grouped.items():
        rows.append(
            {
                "pathway": pathway,
                "pathway_category": group[0]["pathway_category"],
                "city_count": len(group),
                "positive_city_count": sum(1 for row in group if f(row["best_margin_usd_per_tco2"]) > 0),
                "lp_selected_city_count": sum(1 for row in group if f(row["allocated_mtco2_per_year"]) > 0),
                "mean_margin_usd_per_tco2": sum(f(row["best_margin_usd_per_tco2"]) for row in group) / len(group),
                "mean_multimodal_readiness_score": sum(f(row["multimodal_readiness_score"]) for row in group) / len(group),
                "mean_near_term_profit_score": sum(f(row["fusion_near_term_profit_score"]) for row in group) / len(group),
                "mean_neutrality_backbone_score": sum(f(row["fusion_2060_neutrality_backbone_score"]) for row in group) / len(group),
                "mean_policy_exit_resilience_score": sum(f(row["fusion_policy_exit_resilience_score"]) for row in group) / len(group),
                "mean_data_quality_priority_score": sum(f(row["fusion_data_quality_priority_score"]) for row in group) / len(group),
            }
        )
    return sorted(rows, key=lambda row: f(row["mean_neutrality_backbone_score"]), reverse=True)


def upgrade_gap_rows() -> list[dict[str, Any]]:
    return [
        {
            "gap": "text_policy_literature_is_rule_based",
            "current_state": "official and local policy records are embedded with deterministic TF-IDF hash vectors",
            "upgrade": "replace summarized policy records with full legal text chunks, multilingual embeddings and human-audited retrieval passages",
            "expected_effect": "higher confidence in policy qualification and effective-date interpretation",
        },
        {
            "gap": "remote_sensing_facility_proxy_not_image_derived",
            "current_state": "VIIRS/FIRMS raster interfaces are defined; current numeric fallback uses real facility coordinates and emissions intensity",
            "upgrade": "download and clip VIIRS nightlight GeoTIFFs and NASA FIRMS thermal-anomaly CSVs to city polygons",
            "expected_effect": "actual image-derived industrial activity validation and hub-density confidence",
        },
        {
            "gap": "process_simulation_reduced_order",
            "current_state": "SAF flowsheets, electro/photo lifetime benchmarks and storage pressure screens are encoded as route feature vectors",
            "upgrade": "connect Aspen Plus, IDAES or DWSIM exports and calibrated reservoir simulators directly to the CSV interface",
            "expected_effect": "higher process evidence grade and lower technology-lifetime uncertainty",
        },
        {
            "gap": "fusion_weights_are_expert_defined",
            "current_state": "decision-mode weights are transparent and deterministic",
            "upgrade": "calibrate weights against historical CCUS project outcomes or expert elicitation",
            "expected_effect": "turns the fusion layer from scoring model into statistically calibrated decision model",
        },
    ]


def write_summary(features: list[dict[str, Any]]) -> None:
    positive = [row for row in features if f(row["best_margin_usd_per_tco2"]) > 0]
    allocated = [row for row in features if f(row["allocated_mtco2_per_year"]) > 0]
    avg_score = sum(f(row["multimodal_readiness_score"]) for row in features) / max(1, len(features))
    avg_policy = sum(f(row["feature_policy_text_score"]) for row in features) / max(1, len(features))
    avg_visual = sum(f(row["feature_visual_remote_sensing_score"]) for row in features) / max(1, len(features))
    avg_process = sum(f(row["feature_process_flowsheet_score"]) for row in features) / max(1, len(features))
    avg_reservoir = sum(f(row["feature_reservoir_simulation_score"]) for row in features) / max(1, len(features))
    top_neutrality = sorted(features, key=lambda row: f(row["fusion_2060_neutrality_backbone_score"]), reverse=True)[:5]
    lines = [
        "# Multimodal Evidence-Fusion Layer",
        "",
        f"- Cities screened: {len(features)}",
        f"- Positive-margin 2060 cities: {len(positive)}",
        f"- Cities selected in max-profit LP: {len(allocated)}",
        f"- Mean multimodal readiness score: {avg_score:.2f}",
        f"- Mean policy-text score: {avg_policy:.2f}",
        f"- Mean visual/remote-sensing score: {avg_visual:.2f}",
        f"- Mean process-flowsheet score: {avg_process:.2f}",
        f"- Mean reservoir-simulation score: {avg_reservoir:.2f}",
        f"- Top 2060 neutrality-backbone city IDs: {', '.join(str(row['city_id']) for row in top_neutrality)}",
        "",
        "Interpretation: this upgrades the model framing from a single tabular TEA to a true text-visual-space-process evidence-fusion allocator. The current implementation is transparent and deterministic: it creates policy-text embeddings, visual/remote-sensing activity features, process-flow vectors, reservoir-simulation scores, city ranks, modality contributions, pathway summaries, and explicit upgrade gaps.",
    ]
    (OUT / "multimodal_evidence_key_findings.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = build_manifest()
    features = city_features()
    add_ranks(features)
    write_csv(OUT / "modality_manifest.csv", manifest)
    write_csv(OUT / "city_multimodal_features.csv", features)
    write_csv(OUT / "city_multimodal_scores.csv", features)
    write_csv(OUT / "pathway_multimodal_summary.csv", pathway_summary(features))
    write_csv(OUT / "multimodal_upgrade_gaps.csv", upgrade_gap_rows())
    write_csv(OUT / "fusion_architecture.csv", architecture_rows())
    write_summary(features)
    print(f"Wrote multimodal evidence layer to {OUT}")


if __name__ == "__main__":
    main()
