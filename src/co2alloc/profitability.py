"""Profitability accounting for spatial CO2 allocation candidates."""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .constants import capital_recovery_factor
from .spatial import SpatialCandidate, haversine_km


@dataclass(frozen=True, slots=True)
class ProductPrice:
    year: int
    region: str
    product: str
    grade: str
    market_type: str
    low: float
    base: float
    high: float
    volume_limit_t_per_year: float


@dataclass(frozen=True, slots=True)
class ProductQualitySpec:
    product: str
    grade: str
    target_market: str
    upgrading_cost_usd_per_kg: float
    upgrading_energy_kwh_per_kg: float
    marketable_fraction: float
    certification_required: bool


@dataclass(frozen=True, slots=True)
class PolicyRule:
    policy_id: str
    jurisdiction: str
    target_market: str
    product: str
    pathway: str
    start_year: int
    end_year: int
    credit_usd_per_tco2_avoided: float
    durable_credit_usd_per_tco2: float
    carbon_tax_usd_per_tco2: float
    saf_premium_usd_per_kg: float
    clean_fuel_credit_usd_per_kg: float
    eligibility_fraction: float
    stacking_allowed: bool
    certificate_transfer_allowed: bool


@dataclass(frozen=True, slots=True)
class MrvCost:
    scheme: str
    target_market: str
    product: str
    pathway: str
    fixed_cost_usd_per_year: float
    variable_cost_usd_per_tproduct: float
    verification_delay_months: float
    uncertainty_discount_fraction: float
    reversal_buffer_fraction: float
    chain_of_custody: str


@dataclass(frozen=True, slots=True)
class FinanceAssumption:
    region: str
    pathway: str
    technology_family: str
    project_type: str
    year: int
    wacc_base: float
    construction_years: float
    capex_contingency_fraction: float
    owner_cost_fraction: float
    offtake_contract_years: float
    merchant_risk_premium: float
    policy_risk_premium: float


@dataclass(frozen=True, slots=True)
class ReliabilityAssumption:
    pathway: str
    technology_family: str
    year: int
    trl: float
    availability_fraction: float
    replacement_cost_fraction: float
    performance_degradation_per_year: float
    contingency_fraction: float
    min_commercial_scale_tco2_per_year: float


@dataclass(frozen=True, slots=True)
class CityCenter:
    city_id: str
    city_name: str
    province: str
    latitude: float
    longitude: float
    city_type: str
    chemical_demand_index: float
    fuel_demand_index: float
    construction_material_demand_index: float
    renewable_power_index: float
    port_access_index: float
    storage_access_hint: str


@dataclass(frozen=True, slots=True)
class PrefectureJoin:
    entity_id: str
    prefecture_code: str
    prefecture_name: str
    province_name: str
    boundary_level: str
    join_method: str
    fallback_distance_km: float
    evidence_grade: str


@dataclass(frozen=True, slots=True)
class ProfitabilityAssumptions:
    product_prices: list[ProductPrice]
    quality_specs: list[ProductQualitySpec]
    policy_rules: list[PolicyRule]
    mrv_costs: list[MrvCost]
    finance: list[FinanceAssumption]
    reliability: list[ReliabilityAssumption]
    city_centers: list[CityCenter]
    source_prefecture_joins: dict[str, PrefectureJoin]


def _read_rows(path: str | Path) -> list[dict[str, str]]:
    file_path = Path(path)
    if not file_path.exists():
        return []
    with file_path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def _float(row: dict[str, str], key: str, default: float = 0.0) -> float:
    value = row.get(key, "")
    return default if value == "" else float(value)


def _int(row: dict[str, str], key: str, default: int = 0) -> int:
    value = row.get(key, "")
    return default if value == "" else int(float(value))


def _bool(row: dict[str, str], key: str, default: bool = False) -> bool:
    value = row.get(key, "")
    if value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "y"}


def _norm(value: str) -> str:
    return value.strip().lower()


def load_product_prices(path: str | Path) -> list[ProductPrice]:
    return [
        ProductPrice(
            year=_int(row, "year"),
            region=row.get("region", "all"),
            product=row.get("product", "all"),
            grade=row.get("grade", "all"),
            market_type=row.get("market_type", "all"),
            low=_float(row, "price_low_usd_per_kg"),
            base=_float(row, "price_base_usd_per_kg"),
            high=_float(row, "price_high_usd_per_kg"),
            volume_limit_t_per_year=_float(row, "volume_limit_t_per_year", math.inf),
        )
        for row in _read_rows(path)
    ]


def load_quality_specs(path: str | Path) -> list[ProductQualitySpec]:
    return [
        ProductQualitySpec(
            product=row.get("product", "all"),
            grade=row.get("grade", "all"),
            target_market=row.get("target_market", "all"),
            upgrading_cost_usd_per_kg=_float(row, "upgrading_cost_usd_per_kg"),
            upgrading_energy_kwh_per_kg=_float(row, "upgrading_energy_kwh_per_kg"),
            marketable_fraction=_float(row, "marketable_fraction", 1.0),
            certification_required=_bool(row, "certification_required"),
        )
        for row in _read_rows(path)
    ]


def load_policy_rules(path: str | Path) -> list[PolicyRule]:
    return [
        PolicyRule(
            policy_id=row.get("policy_id", ""),
            jurisdiction=row.get("jurisdiction", ""),
            target_market=row.get("target_market", "all"),
            product=row.get("product", "all"),
            pathway=row.get("pathway", "all"),
            start_year=_int(row, "start_year"),
            end_year=_int(row, "end_year", 9999),
            credit_usd_per_tco2_avoided=_float(row, "credit_usd_per_tco2_avoided"),
            durable_credit_usd_per_tco2=_float(row, "durable_credit_usd_per_tco2"),
            carbon_tax_usd_per_tco2=_float(row, "carbon_tax_usd_per_tco2"),
            saf_premium_usd_per_kg=_float(row, "saf_premium_usd_per_kg"),
            clean_fuel_credit_usd_per_kg=_float(row, "clean_fuel_credit_usd_per_kg"),
            eligibility_fraction=_float(row, "eligibility_fraction", 1.0),
            stacking_allowed=_bool(row, "stacking_allowed", True),
            certificate_transfer_allowed=_bool(row, "certificate_transfer_allowed", True),
        )
        for row in _read_rows(path)
    ]


def load_mrv_costs(path: str | Path) -> list[MrvCost]:
    return [
        MrvCost(
            scheme=row.get("scheme", ""),
            target_market=row.get("target_market", "all"),
            product=row.get("product", "all"),
            pathway=row.get("pathway", "all"),
            fixed_cost_usd_per_year=_float(row, "fixed_cost_usd_per_year"),
            variable_cost_usd_per_tproduct=_float(row, "variable_cost_usd_per_tproduct"),
            verification_delay_months=_float(row, "verification_delay_months"),
            uncertainty_discount_fraction=_float(row, "uncertainty_discount_fraction"),
            reversal_buffer_fraction=_float(row, "reversal_buffer_fraction"),
            chain_of_custody=row.get("chain_of_custody", ""),
        )
        for row in _read_rows(path)
    ]


def load_finance(path: str | Path) -> list[FinanceAssumption]:
    return [
        FinanceAssumption(
            region=row.get("region", "all"),
            pathway=row.get("pathway", "all"),
            technology_family=row.get("technology_family", "all"),
            project_type=row.get("project_type", "merchant"),
            year=_int(row, "year"),
            wacc_base=_float(row, "wacc_base", 0.08),
            construction_years=_float(row, "construction_years"),
            capex_contingency_fraction=_float(row, "capex_contingency_fraction"),
            owner_cost_fraction=_float(row, "owner_cost_fraction"),
            offtake_contract_years=_float(row, "offtake_contract_years"),
            merchant_risk_premium=_float(row, "merchant_risk_premium"),
            policy_risk_premium=_float(row, "policy_risk_premium"),
        )
        for row in _read_rows(path)
    ]


def load_reliability(path: str | Path) -> list[ReliabilityAssumption]:
    return [
        ReliabilityAssumption(
            pathway=row.get("pathway", "all"),
            technology_family=row.get("technology_family", "all"),
            year=_int(row, "year"),
            trl=_float(row, "trl"),
            availability_fraction=_float(row, "availability_fraction", 0.9),
            replacement_cost_fraction=_float(row, "replacement_cost_fraction"),
            performance_degradation_per_year=_float(row, "performance_degradation_per_year"),
            contingency_fraction=_float(row, "contingency_fraction"),
            min_commercial_scale_tco2_per_year=_float(row, "min_commercial_scale_tco2_per_year"),
        )
        for row in _read_rows(path)
    ]


def load_city_centers(path: str | Path) -> list[CityCenter]:
    return [
        CityCenter(
            city_id=row["city_id"],
            city_name=row["city_name"],
            province=row["province"],
            latitude=float(row["latitude"]),
            longitude=float(row["longitude"]),
            city_type=row.get("city_type", ""),
            chemical_demand_index=_float(row, "chemical_demand_index"),
            fuel_demand_index=_float(row, "fuel_demand_index"),
            construction_material_demand_index=_float(row, "construction_material_demand_index"),
            renewable_power_index=_float(row, "renewable_power_index"),
            port_access_index=_float(row, "port_access_index"),
            storage_access_hint=row.get("storage_access_hint", ""),
        )
        for row in _read_rows(path)
    ]


def load_prefecture_joins(path: str | Path | None) -> dict[str, PrefectureJoin]:
    if path is None or str(path) == "":
        return {}
    joins: dict[str, PrefectureJoin] = {}
    for row in _read_rows(path):
        entity_id = row.get("entity_id", "")
        if not entity_id:
            continue
        joins[entity_id] = PrefectureJoin(
            entity_id=entity_id,
            prefecture_code=row.get("prefecture_code", ""),
            prefecture_name=row.get("prefecture_name", ""),
            province_name=row.get("province_name", ""),
            boundary_level=row.get("boundary_level", ""),
            join_method=row.get("join_method", ""),
            fallback_distance_km=_float(row, "fallback_distance_km"),
            evidence_grade=row.get("evidence_grade", ""),
        )
    return joins


def load_profitability_assumptions(
    product_prices: str | Path = "data/product_prices.csv",
    quality_specs: str | Path = "data/product_quality_specs.csv",
    policy_rules: str | Path = "data/policy_eligibility_rules.csv",
    mrv_costs: str | Path = "data/mrv_certification_costs.csv",
    finance: str | Path = "data/finance_assumptions.csv",
    reliability: str | Path = "data/technology_reliability.csv",
    city_centers: str | Path = "data/city_centers_screening.csv",
    source_prefecture_joins: str | Path | None = "",
) -> ProfitabilityAssumptions:
    return ProfitabilityAssumptions(
        product_prices=load_product_prices(product_prices),
        quality_specs=load_quality_specs(quality_specs),
        policy_rules=load_policy_rules(policy_rules),
        mrv_costs=load_mrv_costs(mrv_costs),
        finance=load_finance(finance),
        reliability=load_reliability(reliability),
        city_centers=load_city_centers(city_centers),
        source_prefecture_joins=load_prefecture_joins(source_prefecture_joins),
    )


def _specificity_score(value: str, target: str) -> int:
    value_n = _norm(value)
    target_n = _norm(target)
    if value_n == target_n:
        return 3
    if value_n in {"all", "global", ""}:
        return 1
    return -100


def _market_specificity_score(value: str, target: str) -> int:
    value_n = _norm(value)
    target_n = _norm(target)
    if value_n == target_n:
        return 3
    if target_n == "china" and value_n in {"domestic", "china_domestic"}:
        return 2
    if target_n in {"china_2060", "china_dual_carbon"} and value_n in {"china", "domestic", "china_domestic"}:
        return 2
    if value_n in {"all", "global", ""}:
        return 1
    return -100


def _year_score(row_year: int, year: int) -> int:
    if row_year == year:
        return 8
    if row_year <= year:
        return 4
    return 1


def select_product_price(
    rows: list[ProductPrice],
    product: str,
    region: str,
    year: int,
    market_type: str,
) -> ProductPrice:
    fallback = ProductPrice(year, "all", product, "all", market_type, 0.0, 0.0, 0.0, math.inf)
    best = fallback
    best_score = -10_000
    for row in rows:
        product_score = _specificity_score(row.product, product)
        region_score = _specificity_score(row.region, region)
        market_score = _market_specificity_score(row.market_type, market_type)
        if product_score < 0 or region_score < 0 or market_score < 0:
            continue
        score = product_score * 100 + region_score * 20 + market_score * 10 + _year_score(row.year, year)
        if row.year > year:
            score -= 3
        if score > best_score:
            best = row
            best_score = score
    return best


def select_quality_spec(
    rows: list[ProductQualitySpec],
    product: str,
    target_market: str,
) -> ProductQualitySpec:
    fallback = ProductQualitySpec(product, "all", target_market, 0.0, 0.0, 1.0, False)
    best = fallback
    best_score = -10_000
    for row in rows:
        product_score = _specificity_score(row.product, product)
        market_score = _specificity_score(row.target_market, target_market)
        if product_score < 0 or market_score < 0:
            continue
        score = product_score * 100 + market_score * 10
        if score > best_score:
            best = row
            best_score = score
    return best


def applicable_policy_rules(
    rows: list[PolicyRule],
    product: str,
    pathway: str,
    target_market: str,
    year: int,
) -> list[PolicyRule]:
    applicable: list[PolicyRule] = []
    for row in rows:
        if not (row.start_year <= year <= row.end_year):
            continue
        if _specificity_score(row.product, product) < 0:
            continue
        if _specificity_score(row.pathway, pathway) < 0:
            continue
        if _specificity_score(row.target_market, target_market) < 0:
            continue
        applicable.append(row)
    return applicable


def select_mrv_costs(
    rows: list[MrvCost],
    product: str,
    pathway: str,
    target_market: str,
) -> list[MrvCost]:
    selected: list[MrvCost] = []
    for row in rows:
        if _specificity_score(row.product, product) < 0:
            continue
        if _specificity_score(row.pathway, pathway) < 0:
            continue
        if _specificity_score(row.target_market, target_market) < 0:
            continue
        selected.append(row)
    return selected


def select_finance(
    rows: list[FinanceAssumption],
    region: str,
    pathway: str,
    technology_family: str,
    year: int,
) -> FinanceAssumption:
    fallback = FinanceAssumption("all", "all", "all", "merchant", year, 0.08, 3.0, 0.15, 0.08, 0.0, 0.02, 0.02)
    best = fallback
    best_score = -10_000
    for row in rows:
        region_score = _specificity_score(row.region, region)
        pathway_score = _specificity_score(row.pathway, pathway)
        family_score = _specificity_score(row.technology_family, technology_family)
        if region_score < 0 or pathway_score < 0 or family_score < 0:
            continue
        score = region_score * 50 + pathway_score * 100 + family_score * 30 + _year_score(row.year, year)
        if row.year > year:
            score -= 3
        if score > best_score:
            best = row
            best_score = score
    return best


def select_reliability(
    rows: list[ReliabilityAssumption],
    pathway: str,
    technology_family: str,
    year: int,
) -> ReliabilityAssumption:
    fallback = ReliabilityAssumption("all", "all", year, 9.0, 0.9, 0.0, 0.0, 0.10, 0.0)
    best = fallback
    best_score = -10_000
    for row in rows:
        pathway_score = _specificity_score(row.pathway, pathway)
        family_score = _specificity_score(row.technology_family, technology_family)
        if pathway_score < 0 or family_score < 0:
            continue
        score = pathway_score * 100 + family_score * 30 + _year_score(row.year, year)
        if row.year > year:
            score -= 3
        if score > best_score:
            best = row
            best_score = score
    return best


def assign_city(
    candidate: SpatialCandidate,
    city_centers: list[CityCenter],
    prefecture_joins: dict[str, PrefectureJoin] | None = None,
) -> tuple[str, str, str, float, str, str]:
    prefecture_join = (prefecture_joins or {}).get(candidate.source.source_id)
    if prefecture_join is not None:
        return (
            prefecture_join.prefecture_code,
            prefecture_join.prefecture_name,
            "prefecture_boundary",
            prefecture_join.fallback_distance_km,
            prefecture_join.join_method,
            prefecture_join.evidence_grade,
        )
    if not city_centers:
        return candidate.source.region, candidate.source.region, "province_fallback", 0.0, "province_fallback", ""
    same_region = [
        city for city in city_centers
        if _norm(city.province) == _norm(candidate.source.region)
    ]
    pool = same_region or city_centers
    best = min(
        pool,
        key=lambda city: haversine_km(
            candidate.source.latitude,
            candidate.source.longitude,
            city.latitude,
            city.longitude,
        ),
    )
    distance = haversine_km(candidate.source.latitude, candidate.source.longitude, best.latitude, best.longitude)
    return best.city_id, best.city_name, best.city_type, distance, "nearest_city_center", "D"


def storage_distance_band(distance_km: float | None) -> str:
    if distance_km is None or not math.isfinite(distance_km):
        return "no_storage_candidate"
    if distance_km <= 150:
        return "near_0_150km"
    if distance_km <= 350:
        return "medium_150_350km"
    if distance_km <= 800:
        return "far_350_800km"
    return "very_far_gt800km"


def _annuity_factor(discount_rate: float, years: int) -> float:
    if years <= 0:
        return 0.0
    if discount_rate == 0:
        return float(years)
    return (1.0 - (1.0 + discount_rate) ** (-years)) / discount_rate


def profit_record_for_candidate(
    candidate: SpatialCandidate,
    assumptions: ProfitabilityAssumptions,
    year: int,
    target_market: str = "china",
    price_case: str = "base",
    base_discount_rate: float = 0.08,
    plant_lifetime_years: int = 20,
) -> dict[str, float | str]:
    inv = candidate.evaluation.inventory
    product = inv.product_name
    pathway = inv.pathway
    family = inv.technology_family
    product_price = select_product_price(
        assumptions.product_prices,
        product=product,
        region=candidate.destination.region,
        year=year,
        market_type=target_market,
    )
    price_value = {
        "low": product_price.low,
        "base": product_price.base,
        "high": product_price.high,
    }.get(price_case, product_price.base)
    quality = select_quality_spec(assumptions.quality_specs, product, target_market)
    marketable_product_kg = inv.product_kg * quality.marketable_fraction
    product_revenue = marketable_product_kg * price_value

    avoided_t = max(0.0, candidate.adjusted_net_avoided_kgco2e_per_tco2 / 1000.0)
    durable_t = max(0.0, (candidate.evaluation.lca.durable_retained_kgco2 - candidate.adjusted_induced_kgco2e_per_tco2) / 1000.0)
    taxable_t = max(0.0, (candidate.adjusted_induced_kgco2e_per_tco2 + inv.co2_released_end_of_life_kg) / 1000.0)
    rules = applicable_policy_rules(assumptions.policy_rules, product, pathway, target_market, year)
    eligibility = max([rule.eligibility_fraction for rule in rules], default=1.0)
    carbon_credit_price = max([rule.credit_usd_per_tco2_avoided for rule in rules] + [candidate.destination.carbon_price_usd_per_tco2])
    durable_credit_price = max([rule.durable_credit_usd_per_tco2 for rule in rules] + [candidate.destination.durable_removal_credit_usd_per_tco2])
    carbon_tax_price = max([rule.carbon_tax_usd_per_tco2 for rule in rules] + [candidate.destination.carbon_tax_usd_per_tco2])
    saf_premium = sum(rule.saf_premium_usd_per_kg for rule in rules)
    clean_fuel_credit = sum(rule.clean_fuel_credit_usd_per_kg for rule in rules)
    positive_policy_revenue = (
        avoided_t * carbon_credit_price
        + durable_t * durable_credit_price
        + marketable_product_kg * (saf_premium + clean_fuel_credit)
    ) * eligibility
    carbon_tax = taxable_t * carbon_tax_price

    deployable_mtpa = max(
        1e-9,
        min(
            candidate.source.co2_available_mtpa,
            candidate.destination.capacity_mtco2_per_year,
            candidate.pathway_market_capacity_mtpa,
            product_price.volume_limit_t_per_year / 1e6 if product_price.volume_limit_t_per_year > 0 else math.inf,
        ),
    )
    mrv_rows = select_mrv_costs(assumptions.mrv_costs, product, pathway, target_market)
    mrv_fixed_cost = sum(row.fixed_cost_usd_per_year for row in mrv_rows) / (deployable_mtpa * 1e6)
    mrv_variable_cost = sum(row.variable_cost_usd_per_tproduct for row in mrv_rows) * marketable_product_kg / 1000.0
    mrv_discount = max([row.uncertainty_discount_fraction for row in mrv_rows], default=0.0)
    reversal_buffer = max([row.reversal_buffer_fraction for row in mrv_rows], default=0.0)
    policy_revenue = positive_policy_revenue * (1.0 - mrv_discount - reversal_buffer) - carbon_tax

    quality_upgrade_cost = (
        marketable_product_kg * quality.upgrading_cost_usd_per_kg
        + marketable_product_kg * quality.upgrading_energy_kwh_per_kg / 1000.0 * candidate.effective_electricity.price_usd_per_mwh
    )
    finance = select_finance(assumptions.finance, candidate.destination.region, pathway, family, year)
    reliability = select_reliability(assumptions.reliability, pathway, family, year)
    base_crf = capital_recovery_factor(base_discount_rate, plant_lifetime_years)
    risk_adjusted_wacc = finance.wacc_base + finance.merchant_risk_premium + finance.policy_risk_premium
    risk_crf = capital_recovery_factor(risk_adjusted_wacc, plant_lifetime_years)
    capex_component_base = inv.capex_usd_per_tpa_co2 * candidate.capex_learning_multiplier * base_crf / max(candidate.destination.electrolyzer_capacity_factor if pathway.startswith("electrolysis_") else 0.9, 1e-6)
    finance_cost_adjustment = capex_component_base * (risk_crf / max(base_crf, 1e-9) - 1.0)
    capex_risk_cost = capex_component_base * (
        finance.capex_contingency_fraction
        + finance.owner_cost_fraction
        + reliability.contingency_fraction
    ) * base_crf
    reliability_cost = capex_component_base * (
        reliability.replacement_cost_fraction / max(plant_lifetime_years, 1)
        + reliability.performance_degradation_per_year
        + max(0.0, 0.90 - reliability.availability_fraction) * 0.25
    )
    scale_penalty = 0.0
    if deployable_mtpa * 1e6 < reliability.min_commercial_scale_tco2_per_year:
        scale_gap = reliability.min_commercial_scale_tco2_per_year / max(deployable_mtpa * 1e6, 1.0)
        scale_penalty = min(250.0, 20.0 * math.log(scale_gap))

    non_base_cost_adders = (
        quality_upgrade_cost
        + mrv_fixed_cost
        + mrv_variable_cost
        + finance_cost_adjustment
        + capex_risk_cost
        + reliability_cost
        + scale_penalty
    )
    risk_adjusted_gross_cost = candidate.adjusted_gross_cost_usd_per_tco2 + non_base_cost_adders
    margin = product_revenue + policy_revenue - risk_adjusted_gross_cost
    annual_margin_musd = margin * deployable_mtpa
    npv_proxy_musd = annual_margin_musd * _annuity_factor(risk_adjusted_wacc, plant_lifetime_years)
    break_even_product_price = math.inf
    if marketable_product_kg > 0:
        break_even_product_price = max(0.0, (risk_adjusted_gross_cost - policy_revenue) / marketable_product_kg)
    break_even_policy_credit = math.inf
    if avoided_t > 0:
        break_even_policy_credit = max(0.0, (risk_adjusted_gross_cost - product_revenue) / avoided_t)
    break_even_h2_price = math.inf
    if inv.h2_kg > 0:
        break_even_h2_price = candidate.hydrogen_supply.price_usd_per_kg + margin / inv.h2_kg
    break_even_electricity_price = math.inf
    if inv.electricity_kwh > 0:
        break_even_electricity_price = candidate.effective_electricity.price_usd_per_mwh + margin / (inv.electricity_kwh / 1000.0)

    city_id, city_name, city_type, city_distance_km, city_join_method, city_evidence_grade = assign_city(
        candidate,
        assumptions.city_centers,
        assumptions.source_prefecture_joins,
    )
    return {
        "year": year,
        "target_market": target_market,
        "price_case": price_case,
        "city_id": city_id,
        "city_name": city_name,
        "city_type": city_type,
        "source_to_city_center_km": city_distance_km,
        "city_join_method": city_join_method,
        "city_evidence_grade": city_evidence_grade,
        "source_id": candidate.source.source_id,
        "source_region": candidate.source.region,
        "source_type": candidate.source.source_type,
        "capture_cost_usd_per_tco2": candidate.source.capture_cost_usd_per_tco2,
        "capture_emissions_kgco2e_per_tco2": candidate.source.capture_emissions_kgco2e_per_tco2,
        "capture_energy_kwh_per_tco2": candidate.source.capture_energy_kwh_per_tco2,
        "capture_energy_cost_usd_per_tco2": candidate.capture_energy_cost_usd_per_tco2,
        "capture_energy_emissions_kgco2e_per_tco2": candidate.capture_energy_emissions_kgco2e_per_tco2,
        "source_co2_purity_fraction": candidate.source.co2_purity_fraction,
        "source_pressure_bar": candidate.source.capture_pressure_bar,
        "destination_id": candidate.destination.destination_id,
        "destination_region": candidate.destination.region,
        "sink_type": candidate.destination.sink_type,
        "destination_capacity_mtco2_per_year": candidate.destination.capacity_mtco2_per_year,
        "pathway": pathway,
        "technology_family": family,
        "product": product,
        "transport_mode": candidate.transport_mode.mode,
        "distance_km": candidate.distance_km,
        "routed_distance_km": candidate.routed_distance_km,
        "spec_cost_usd_per_tco2": candidate.spec_cost_usd_per_tco2,
        "spec_emissions_kgco2e_per_tco2": candidate.spec_emissions_kgco2e_per_tco2,
        "transport_cost_usd_per_tco2": candidate.transport_cost_usd_per_tco2,
        "transport_emissions_kgco2e_per_tco2": candidate.transport_emissions_kgco2e_per_tco2,
        "land_cost_usd_per_tco2": candidate.land_cost_usd_per_tco2,
        "spatial_risk_cost_usd_per_tco2": candidate.risk_cost_usd_per_tco2,
        "adjusted_gross_cost_usd_per_tco2": candidate.adjusted_gross_cost_usd_per_tco2,
        "adjusted_net_cost_usd_per_tco2": candidate.adjusted_net_cost_usd_per_tco2,
        "deployable_mtco2_per_year": deployable_mtpa,
        "product_kg_per_tco2": inv.product_kg,
        "marketable_product_kg_per_tco2": marketable_product_kg,
        "product_price_usd_per_kg": price_value,
        "product_revenue_usd_per_tco2": product_revenue,
        "policy_revenue_usd_per_tco2": policy_revenue,
        "positive_policy_revenue_before_mrv_usd_per_tco2": positive_policy_revenue,
        "carbon_tax_usd_per_tco2": carbon_tax,
        "quality_upgrade_cost_usd_per_tco2": quality_upgrade_cost,
        "mrv_cost_usd_per_tco2": mrv_fixed_cost + mrv_variable_cost,
        "finance_cost_adjustment_usd_per_tco2": finance_cost_adjustment,
        "capex_risk_cost_usd_per_tco2": capex_risk_cost,
        "reliability_cost_usd_per_tco2": reliability_cost,
        "scale_penalty_usd_per_tco2": scale_penalty,
        "risk_adjusted_gross_cost_usd_per_tco2": risk_adjusted_gross_cost,
        "margin_usd_per_tco2": margin,
        "annual_margin_musd_per_year": annual_margin_musd,
        "npv_proxy_musd": npv_proxy_musd,
        "npv_positive_flag": 1 if npv_proxy_musd > 0 else 0,
        "break_even_product_price_usd_per_kg": break_even_product_price,
        "break_even_policy_credit_usd_per_tco2": break_even_policy_credit,
        "break_even_h2_price_usd_per_kg": break_even_h2_price,
        "break_even_electricity_price_usd_per_mwh": break_even_electricity_price,
        "adjusted_net_avoided_tco2e_per_tco2": candidate.adjusted_net_avoided_kgco2e_per_tco2 / 1000.0,
        "electricity_price_usd_per_mwh": candidate.effective_electricity.price_usd_per_mwh,
        "grid_emissions_kgco2e_per_mwh": candidate.effective_electricity.emissions_kgco2e_per_mwh,
        "h2_price_usd_per_kg": candidate.hydrogen_supply.price_usd_per_kg,
        "h2_emissions_kgco2e_per_kg": candidate.hydrogen_supply.emissions_kgco2e_per_kg,
        "policy_ids": ";".join(rule.policy_id for rule in rules),
        "mrv_schemes": ";".join(row.scheme for row in mrv_rows),
        "finance_project_type": finance.project_type,
        "risk_adjusted_wacc": risk_adjusted_wacc,
        "technology_availability_fraction": reliability.availability_fraction,
        "technology_trl": reliability.trl,
    }


def profit_scan(
    candidates: Iterable[SpatialCandidate],
    assumptions: ProfitabilityAssumptions,
    year: int,
    target_market: str = "china",
    price_case: str = "base",
    min_margin_usd_per_tco2: float | None = None,
) -> list[dict[str, float | str]]:
    records = [
        profit_record_for_candidate(
            candidate,
            assumptions=assumptions,
            year=year,
            target_market=target_market,
            price_case=price_case,
        )
        for candidate in candidates
    ]
    if min_margin_usd_per_tco2 is not None:
        records = [
            row for row in records
            if float(row["margin_usd_per_tco2"]) >= min_margin_usd_per_tco2
        ]
    return sorted(records, key=lambda row: float(row["margin_usd_per_tco2"]), reverse=True)


def _recommend_base(best: dict[str, float | str] | None, best_nonstorage: dict[str, float | str] | None, storage_distance: float | None) -> str:
    chosen = best if best and float(best["margin_usd_per_tco2"]) > 0 else best_nonstorage
    if chosen is None:
        return "no_build_or_wait"
    pathway = str(chosen["pathway"])
    family = str(chosen["technology_family"])
    product = str(chosen["product"])
    margin = float(chosen["margin_usd_per_tco2"])
    if margin <= 0 and (storage_distance is None or storage_distance <= 350):
        return "storage_or_capture_ready_watchlist"
    if margin <= 0:
        return "no_build_or_wait"
    if pathway == "geological_storage":
        return "storage_hub"
    if family == "mineralization":
        return "mineralization_base"
    if product == "sustainable_aviation_fuel":
        return "saf_export_fuel_base"
    if family == "thermochemical":
        return "thermochemical_chemical_base"
    if family == "electrochemical" and product == "formic_acid_equivalent":
        return "electrochemical_formate_base"
    if family == "electrochemical" and product == "carbon_monoxide":
        return "electrochemical_co_base"
    if family == "photochemical":
        return "photochemical_pilot_base"
    return "no_build_or_wait" if margin <= 0 else "utilization_base"


def city_profit_recommendations(
    profit_records: Iterable[dict[str, float | str]],
) -> list[dict[str, float | str]]:
    by_city: dict[str, list[dict[str, float | str]]] = {}
    for record in profit_records:
        by_city.setdefault(str(record["city_id"]), []).append(record)
    recommendations: list[dict[str, float | str]] = []
    for city_id, rows in sorted(by_city.items()):
        sorted_rows = sorted(rows, key=lambda row: float(row["margin_usd_per_tco2"]), reverse=True)
        best = sorted_rows[0] if sorted_rows else None
        nonstorage = [
            row for row in sorted_rows
            if str(row["pathway"]) != "geological_storage"
        ]
        best_nonstorage = nonstorage[0] if nonstorage else None
        storage_rows = [
            row for row in rows
            if str(row["pathway"]) == "geological_storage"
        ]
        best_storage = max(storage_rows, key=lambda row: float(row["margin_usd_per_tco2"])) if storage_rows else None
        nearest_storage_distance = min((float(row["distance_km"]) for row in storage_rows), default=math.inf)
        if math.isinf(nearest_storage_distance):
            nearest_storage_distance = math.inf
        chosen = best or best_nonstorage
        recommendations.append(
            {
                "city_id": city_id,
                "city_name": str(chosen["city_name"]) if chosen else "",
                "city_type": str(chosen["city_type"]) if chosen else "",
                "source_region": str(chosen["source_region"]) if chosen else "",
                "recommended_base": _recommend_base(best, best_nonstorage, nearest_storage_distance),
                "storage_distance_band": storage_distance_band(nearest_storage_distance),
                "nearest_storage_distance_km": nearest_storage_distance,
                "best_pathway": str(best["pathway"]) if best else "",
                "best_product": str(best["product"]) if best else "",
                "best_family": str(best["technology_family"]) if best else "",
                "best_margin_usd_per_tco2": float(best["margin_usd_per_tco2"]) if best else -math.inf,
                "best_npv_proxy_musd": float(best["npv_proxy_musd"]) if best else -math.inf,
                "best_break_even_product_price_usd_per_kg": float(best["break_even_product_price_usd_per_kg"]) if best else math.inf,
                "best_storage_margin_usd_per_tco2": float(best_storage["margin_usd_per_tco2"]) if best_storage else -math.inf,
                "best_nonstorage_pathway": str(best_nonstorage["pathway"]) if best_nonstorage else "",
                "best_nonstorage_product": str(best_nonstorage["product"]) if best_nonstorage else "",
                "best_nonstorage_margin_usd_per_tco2": float(best_nonstorage["margin_usd_per_tco2"]) if best_nonstorage else -math.inf,
                "candidate_count": len(rows),
            }
        )
    return sorted(recommendations, key=lambda row: str(row["city_name"]))
