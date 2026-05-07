"""Build spatial model inputs from downloaded public China datasets.

The routines here intentionally stay dependency-free. They convert the
processed CSV files in ``data/processed`` into the existing screening-model
input schema used by :mod:`co2alloc.spatial`.
"""

from __future__ import annotations

import csv
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .io import write_csv


ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True, slots=True)
class Province:
    abbr: str
    name_en: str
    name_cn: str
    lat: float
    lon: float


PROVINCES: tuple[Province, ...] = (
    Province("BJ", "Beijing", "北京市", 39.9042, 116.4074),
    Province("TJ", "Tianjin", "天津市", 39.3434, 117.3616),
    Province("HE", "Hebei", "河北省", 38.0428, 114.5149),
    Province("SX", "Shanxi", "山西省", 37.8735, 112.5624),
    Province("NM", "Inner Mongolia", "内蒙古自治区", 40.8175, 111.7652),
    Province("LN", "Liaoning", "辽宁省", 41.8354, 123.4291),
    Province("JL", "Jilin", "吉林省", 43.8965, 125.3268),
    Province("HL", "Heilongjiang", "黑龙江省", 45.7422, 126.6617),
    Province("SH", "Shanghai", "上海市", 31.2304, 121.4737),
    Province("JS", "Jiangsu", "江苏省", 32.0603, 118.7969),
    Province("ZJ", "Zhejiang", "浙江省", 30.2741, 120.1551),
    Province("AH", "Anhui", "安徽省", 31.8206, 117.2272),
    Province("FJ", "Fujian", "福建省", 26.0745, 119.2965),
    Province("JX", "Jiangxi", "江西省", 28.6820, 115.8582),
    Province("SD", "Shandong", "山东省", 36.6683, 117.0208),
    Province("HA", "Henan", "河南省", 34.7657, 113.7532),
    Province("HB", "Hubei", "湖北省", 30.5928, 114.3055),
    Province("HN", "Hunan", "湖南省", 28.2282, 112.9388),
    Province("GD", "Guangdong", "广东省", 23.1291, 113.2644),
    Province("GX", "Guangxi", "广西壮族自治区", 22.8170, 108.3669),
    Province("HI", "Hainan", "海南省", 20.0440, 110.1999),
    Province("CQ", "Chongqing", "重庆市", 29.5630, 106.5516),
    Province("SC", "Sichuan", "四川省", 30.5728, 104.0668),
    Province("GZ", "Guizhou", "贵州省", 26.6470, 106.6302),
    Province("YN", "Yunnan", "云南省", 25.0389, 102.7183),
    Province("XZ", "Tibet", "西藏自治区", 29.6520, 91.1721),
    Province("SN", "Shaanxi", "陕西省", 34.3416, 108.9398),
    Province("GS", "Gansu", "甘肃省", 36.0611, 103.8343),
    Province("QH", "Qinghai", "青海省", 36.6171, 101.7782),
    Province("NX", "Ningxia", "宁夏回族自治区", 38.4872, 106.2309),
    Province("XJ", "Xinjiang", "新疆维吾尔自治区", 43.8256, 87.6168),
)


STORAGE_NAME_ALIASES = {
    "Guangxi Zhuang Autonomous Region": "Guangxi",
    "Inner Mongolia Autonomous Region": "Inner Mongolia",
    "Ningxia Hui Autonomous Region": "Ningxia",
    "Tibet Autonomous Region": "Tibet",
    "Xinjiang Uygur Autonomous Region": "Xinjiang",
}


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def _float(value: str | None, default: float = 0.0) -> float:
    if value is None or value == "":
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _safe_id(value: str, max_len: int = 80) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]+", "_", value).strip("_").upper()
    return cleaned[:max_len] or "UNKNOWN"


def _province_by_name(name: str) -> Province | None:
    normalized = STORAGE_NAME_ALIASES.get(name, name)
    for province in PROVINCES:
        if province.name_en == normalized:
            return province
    return None


def _nearest_province(lat: float, lon: float) -> Province:
    return min(PROVINCES, key=lambda p: (p.lat - lat) ** 2 + (p.lon - lon) ** 2)


def _price_proxy_usd_per_mwh(
    province_abbr: str,
    exchange_rate_cny_per_usd: float = 7.2,
) -> float:
    # Public hourly spot prices are not uniformly downloadable. These are
    # transparent industrial-price proxies until exchange data are added.
    cny_per_kwh = {
        "BJ": 0.70,
        "TJ": 0.62,
        "HE": 0.56,
        "SX": 0.43,
        "NM": 0.38,
        "LN": 0.55,
        "JL": 0.50,
        "HL": 0.48,
        "SH": 0.78,
        "JS": 0.68,
        "ZJ": 0.72,
        "AH": 0.58,
        "FJ": 0.62,
        "JX": 0.56,
        "SD": 0.60,
        "HA": 0.55,
        "HB": 0.57,
        "HN": 0.58,
        "GD": 0.72,
        "GX": 0.55,
        "HI": 0.78,
        "CQ": 0.61,
        "SC": 0.45,
        "GZ": 0.53,
        "YN": 0.42,
        "XZ": 0.40,
        "SN": 0.48,
        "GS": 0.43,
        "QH": 0.36,
        "NX": 0.39,
        "XJ": 0.35,
    }.get(province_abbr, 0.58)
    return cny_per_kwh * 1000.0 / exchange_rate_cny_per_usd


def _capture_defaults(subsector: str, source_type: str, source_name: str) -> dict[str, float | str]:
    label = f"{subsector} {source_type} {source_name}".lower()
    if subsector == "electricity-generation":
        if "gas" in label or "lng" in label:
            return {
                "source_type": "gas_power",
                "capture_cost_usd_per_tco2": 70.0,
                "capture_emissions_kgco2e_per_tco2": 100.0,
                "capture_energy_kwh_per_tco2": 160.0,
                "co2_purity_fraction": 0.08,
                "capture_pressure_bar": 1.1,
                "sox_ppm": 5.0,
                "nox_ppm": 30.0,
                "h2s_ppm": 0.1,
                "o2_percent": 8.0,
                "water_ppm": 2500.0,
                "annual_capacity_factor": 0.70,
            }
        return {
            "source_type": "coal_power",
            "capture_cost_usd_per_tco2": 48.0,
            "capture_emissions_kgco2e_per_tco2": 105.0,
            "capture_energy_kwh_per_tco2": 140.0,
            "co2_purity_fraction": 0.14,
            "capture_pressure_bar": 1.2,
            "sox_ppm": 60.0,
            "nox_ppm": 120.0,
            "h2s_ppm": 0.3,
            "o2_percent": 5.0,
            "water_ppm": 4200.0,
            "annual_capacity_factor": 0.76,
        }
    if subsector in {"cement", "lime"}:
        return {
            "source_type": subsector,
            "capture_cost_usd_per_tco2": 74.0,
            "capture_emissions_kgco2e_per_tco2": 130.0,
            "capture_energy_kwh_per_tco2": 125.0,
            "co2_purity_fraction": 0.20,
            "capture_pressure_bar": 1.2,
            "sox_ppm": 120.0,
            "nox_ppm": 180.0,
            "h2s_ppm": 0.1,
            "o2_percent": 6.0,
            "water_ppm": 5000.0,
            "annual_capacity_factor": 0.78,
        }
    if subsector == "iron-and-steel":
        return {
            "source_type": "steel",
            "capture_cost_usd_per_tco2": 62.0,
            "capture_emissions_kgco2e_per_tco2": 115.0,
            "capture_energy_kwh_per_tco2": 110.0,
            "co2_purity_fraction": 0.22,
            "capture_pressure_bar": 1.3,
            "sox_ppm": 35.0,
            "nox_ppm": 80.0,
            "h2s_ppm": 0.5,
            "o2_percent": 4.0,
            "water_ppm": 3500.0,
            "annual_capacity_factor": 0.82,
        }
    if subsector == "aluminum":
        return {
            "source_type": "aluminum",
            "capture_cost_usd_per_tco2": 90.0,
            "capture_emissions_kgco2e_per_tco2": 150.0,
            "capture_energy_kwh_per_tco2": 180.0,
            "co2_purity_fraction": 0.04,
            "capture_pressure_bar": 1.1,
            "sox_ppm": 20.0,
            "nox_ppm": 40.0,
            "h2s_ppm": 0.1,
            "o2_percent": 10.0,
            "water_ppm": 2500.0,
            "annual_capacity_factor": 0.80,
        }
    return {
        "source_type": "chemicals",
        "capture_cost_usd_per_tco2": 55.0,
        "capture_emissions_kgco2e_per_tco2": 95.0,
        "capture_energy_kwh_per_tco2": 70.0,
        "co2_purity_fraction": 0.55,
        "capture_pressure_bar": 2.0,
        "sox_ppm": 20.0,
        "nox_ppm": 45.0,
        "h2s_ppm": 8.0,
        "o2_percent": 2.5,
        "water_ppm": 1200.0,
        "annual_capacity_factor": 0.86,
    }


def _carbon_prices_usd(policy_dir: Path, exchange_rate_cny_per_usd: float) -> tuple[float, float]:
    rows = _read_rows(policy_dir / "carbon_market_latest_snapshot.csv")
    cea = 0.0
    ccer = 0.0
    for row in rows:
        value = _float(row.get("close_or_avg_cny_per_tco2"))
        if row.get("market") == "CEA":
            cea = value / exchange_rate_cny_per_usd
        elif row.get("market") == "CCER":
            ccer = value / exchange_rate_cny_per_usd
    return cea, ccer


def _province_grid_factors(electricity_dir: Path) -> dict[str, float]:
    factors: dict[str, float] = {}
    for row in _read_rows(electricity_dir / "mee_nbs_2023_power_co2_emission_factors.csv"):
        if row.get("scope") == "province" and row.get("definition") == "average_power_co2_factor":
            factors[row["province_abbr"]] = _float(row.get("factor_kgco2_per_kwh")) * 1000.0
    return factors


def _policy_intensity(policy_dir: Path) -> dict[str, float]:
    path = policy_dir / "low_carbon_policy_intensity_provincial_2007_2022.csv"
    rows = [row for row in _read_rows(path) if row.get("Year") == "2022"]
    by_name = {row["Pro_name_EN"]: _float(row.get("PI_all_province")) for row in rows}
    values = list(by_name.values())
    if not values:
        return {}
    min_v = min(values)
    max_v = max(values)
    span = max(max_v - min_v, 1e-9)
    normalized: dict[str, float] = {}
    for province in PROVINCES:
        raw = by_name.get(province.name_en, min_v)
        normalized[province.abbr] = (raw - min_v) / span
    return normalized


def _source_calibration_factors(path: str | Path | None) -> dict[tuple[str, str], float]:
    if path is None:
        return {}
    calibration_path = Path(path)
    if not calibration_path.exists():
        return {}
    factors: dict[tuple[str, str], float] = {}
    for row in _read_rows(calibration_path):
        province = row.get("province") or row.get("region") or ""
        source_type = row.get("source_type") or ""
        if not province or not source_type:
            continue
        factor = _float(row.get("calibration_multiplier"), 1.0)
        if factor > 0:
            factors[(province, source_type)] = factor
    return factors


def build_real_sources(
    processed_dir: Path,
    source_year: int,
    top_sources: int,
    capture_rate: float,
    source_calibration_path: str | Path | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    source_path = processed_dir / "co2_sources" / "climatetrace_china_key_sources_annual.csv"
    calibration = _source_calibration_factors(source_calibration_path)
    rows = []
    for row in _read_rows(source_path):
        if int(float(row.get("year") or 0)) != source_year:
            continue
        lat = _float(row.get("lat"), math.nan)
        lon = _float(row.get("lon"), math.nan)
        emissions_tco2 = _float(row.get("emissions_tco2"))
        if not math.isfinite(lat) or not math.isfinite(lon) or emissions_tco2 <= 0:
            continue
        rows.append(row)
    rows.sort(key=lambda r: _float(r.get("emissions_tco2")), reverse=True)

    sources: list[dict[str, Any]] = []
    metadata: list[dict[str, Any]] = []
    for row in rows[:top_sources]:
        lat = _float(row["lat"])
        lon = _float(row["lon"])
        province = _nearest_province(lat, lon)
        defaults = _capture_defaults(row["subsector"], row["source_type"], row["source_name"])
        source_id = f"CT_{_safe_id(row['source_id'])}"
        source_type = defaults["source_type"]
        calibration_multiplier = calibration.get(
            (province.name_en, source_type),
            calibration.get(("China", source_type), 1.0),
        )
        co2_available = _float(row["emissions_tco2"]) / 1_000_000.0 * capture_rate * calibration_multiplier
        sources.append(
            {
                "source_id": source_id,
                "region": province.name_en,
                "source_type": source_type,
                "latitude": lat,
                "longitude": lon,
                "co2_available_mtpa": round(co2_available, 6),
                "capture_cost_usd_per_tco2": defaults["capture_cost_usd_per_tco2"],
                "capture_emissions_kgco2e_per_tco2": defaults["capture_emissions_kgco2e_per_tco2"],
                "capture_energy_kwh_per_tco2": defaults["capture_energy_kwh_per_tco2"],
                "co2_purity_fraction": defaults["co2_purity_fraction"],
                "capture_pressure_bar": defaults["capture_pressure_bar"],
                "sox_ppm": defaults["sox_ppm"],
                "nox_ppm": defaults["nox_ppm"],
                "h2s_ppm": defaults["h2s_ppm"],
                "o2_percent": defaults["o2_percent"],
                "water_ppm": defaults["water_ppm"],
                "annual_capacity_factor": defaults["annual_capacity_factor"],
            }
        )
        metadata.append(
            {
                "source_id": source_id,
                "climatetrace_source_id": row["source_id"],
                "source_name": row["source_name"],
                "sector": row["sector"],
                "subsector": row["subsector"],
                "source_type_raw": row["source_type"],
                "year": source_year,
                "emissions_tco2": row["emissions_tco2"],
                "province_abbr": province.abbr,
                "province_name": province.name_en,
                "capture_rate_assumed": capture_rate,
                "source_calibration_multiplier": calibration_multiplier,
                "capture_energy_kwh_per_tco2": defaults["capture_energy_kwh_per_tco2"],
            }
        )
    return sources, metadata


def load_extra_sources(path: str | Path | None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if path is None or str(path) == "":
        return [], []
    source_path = Path(path)
    if not source_path.exists():
        raise FileNotFoundError(f"Extra source file not found: {source_path}")
    sources: list[dict[str, Any]] = []
    metadata: list[dict[str, Any]] = []
    for row in _read_rows(source_path):
        source_id = row["source_id"]
        sources.append(
            {
                "source_id": source_id,
                "region": row["region"],
                "source_type": row["source_type"],
                "latitude": _float(row.get("latitude")),
                "longitude": _float(row.get("longitude")),
                "co2_available_mtpa": _float(row.get("co2_available_mtpa")),
                "capture_cost_usd_per_tco2": _float(row.get("capture_cost_usd_per_tco2")),
                "capture_emissions_kgco2e_per_tco2": _float(row.get("capture_emissions_kgco2e_per_tco2")),
                "capture_energy_kwh_per_tco2": _float(row.get("capture_energy_kwh_per_tco2")),
                "co2_purity_fraction": _float(row.get("co2_purity_fraction"), 0.99),
                "capture_pressure_bar": _float(row.get("capture_pressure_bar"), 1.1),
                "sox_ppm": _float(row.get("sox_ppm")),
                "nox_ppm": _float(row.get("nox_ppm")),
                "h2s_ppm": _float(row.get("h2s_ppm")),
                "o2_percent": _float(row.get("o2_percent")),
                "water_ppm": _float(row.get("water_ppm")),
                "annual_capacity_factor": _float(row.get("annual_capacity_factor"), 0.85),
            }
        )
        metadata.append(
            {
                "source_id": source_id,
                "source_name": row.get("source_name", source_id),
                "sector": row.get("sector", "engineered_removal"),
                "subsector": row.get("subsector", row["source_type"]),
                "source_type_raw": row.get("source_type_raw", row["source_type"]),
                "year": row.get("year", ""),
                "emissions_tco2": row.get("emissions_tco2", ""),
                "province_abbr": row.get("province_abbr", ""),
                "province_name": row["region"],
                "capture_rate_assumed": row.get("capture_rate_assumed", ""),
                "source_calibration_multiplier": row.get("source_calibration_multiplier", ""),
                "capture_energy_kwh_per_tco2": _float(row.get("capture_energy_kwh_per_tco2")),
                "extra_source_path": str(source_path),
            }
        )
    return sources, metadata


def _destination_common(
    province: Province,
    grid_factors: dict[str, float],
    carbon_price: float,
    removal_credit: float,
    exchange_rate_cny_per_usd: float,
) -> dict[str, Any]:
    return {
        "electricity_price_usd_per_mwh": round(
            _price_proxy_usd_per_mwh(province.abbr, exchange_rate_cny_per_usd),
            3,
        ),
        "grid_emissions_kgco2e_per_mwh": round(grid_factors.get(province.abbr, 530.6), 3),
        "h2_price_usd_per_kg": 3.0,
        "h2_emissions_kgco2e_per_kg": 4.0,
        "carbon_price_usd_per_tco2": round(carbon_price, 3),
        "carbon_tax_usd_per_tco2": 0.0,
        "durable_removal_credit_usd_per_tco2": round(removal_credit, 3),
        "heat_price_usd_per_gj": 6.0,
        "min_co2_purity_fraction": 0.95,
        "required_pressure_bar": 115.0,
        "max_sox_ppm": 10.0,
        "max_nox_ppm": 10.0,
        "max_h2s_ppm": 10.0,
        "max_o2_percent": 2.0,
        "max_water_ppm": 200.0,
        "purification_cost_usd_per_tco2_per_fraction": 120.0,
        "purification_emissions_kgco2e_per_tco2_per_fraction": 80.0,
        "impurity_removal_cost_usd_per_tco2_per_index": 8.0,
        "impurity_removal_emissions_kgco2e_per_tco2_per_index": 3.0,
        "pressure_boost_kwh_per_tco2_per_ln_ratio": 24.0,
        "h2_supply_mode": "market",
        "electrolyzer_capex_usd_per_kw": 675.0,
        "electrolyzer_kwh_per_kg_h2": 53.8,
        "electrolyzer_capacity_factor": 0.55,
        "electrolyzer_lifetime_years": 15,
        "electrolyzer_fixed_om_fraction": 0.03,
        "h2_compression_storage_cost_usd_per_kg": 0.25,
        "water_l_per_kg_h2": 15.0,
        "water_price_usd_per_m3": 1.0,
        "water_emissions_kgco2e_per_m3": 0.4,
        "hourly_profile_id": province.abbr,
        "electricity_procurement_mode": "annual_average",
        "flexible_load_fraction": 1.0,
        "water_available_m3_per_year": 100_000_000.0,
        "land_available_km2": 100.0,
        "land_cost_usd_per_m2_year": 0.1,
        "permit_risk_cost_usd_per_tco2": 3.0,
        "trl_risk_premium_fraction": 0.02,
    }


def _product_destination_capacities(markets_dir: Path) -> dict[str, float]:
    path = markets_dir / "product_destination_capacity_china_2023.csv"
    if not path.exists():
        return {}
    capacities: dict[str, float] = {}
    for row in _read_rows(path):
        destination_id = row.get("destination_id", "")
        if not destination_id:
            continue
        capacity = _float(row.get("capacity_mtco2_per_year"))
        if capacity > 0:
            capacities[destination_id] = capacity
    return capacities


def _product_destination_specs(path: Path | None = None) -> list[dict[str, Any]]:
    specs_path = path or ROOT / "data" / "product_destinations.csv"
    if not specs_path.exists():
        return []
    specs: list[dict[str, Any]] = []
    for row in _read_rows(specs_path):
        specs.append(
            {
                "destination_id": row["destination_id"],
                "region": row["region"],
                "sink_type": row["sink_type"],
                "allowed_pathways": row["allowed_pathways"],
                "default_capacity_mtco2_per_year": _float(row.get("default_capacity_mtco2_per_year")),
                "h2_supply_mode": row.get("h2_supply_mode") or "market",
                "electricity_price_override_usd_per_mwh": _float(row.get("electricity_price_override_usd_per_mwh"), math.nan),
                "grid_emissions_override_kgco2e_per_mwh": _float(row.get("grid_emissions_override_kgco2e_per_mwh"), math.nan),
                "electricity_procurement_mode": row.get("electricity_procurement_mode") or "annual_average",
                "flexible_load_fraction": _float(row.get("flexible_load_fraction"), 1.0),
                "basis": row.get("basis", ""),
                "evidence_grade": row.get("evidence_grade", ""),
                "notes": row.get("notes", ""),
            }
        )
    return specs


def build_real_destinations(
    processed_dir: Path,
    grid_factors: dict[str, float],
    carbon_price: float,
    removal_credit: float,
    exchange_rate_cny_per_usd: float,
    storage_horizon_years: int = 20,
) -> list[dict[str, Any]]:
    storage_path = processed_dir / "storage" / "provincial_level_co2_storage_figshare_27646707.csv"
    policy = _policy_intensity(processed_dir / "policy")
    product_capacities = _product_destination_capacities(processed_dir / "markets")
    destinations: list[dict[str, Any]] = []
    for row in _read_rows(storage_path):
        province = _province_by_name(row["Province name"])
        if province is None:
            continue
        dsa = _float(row.get("Injection rate capability-DSA (Mt/a) (Average)"))
        eor = _float(row.get("Injection rate capability-EOR (Mt/a) (Average)"))
        injection_capacity = dsa + eor
        storage_potential = _float(row.get("Storage potential-ALL (Mt)"))
        capacity = min(injection_capacity, storage_potential / max(storage_horizon_years, 1))
        if capacity <= 0 or storage_potential <= 0:
            continue
        common = _destination_common(
            province,
            grid_factors,
            carbon_price,
            removal_credit,
            exchange_rate_cny_per_usd,
        )
        policy_score = policy.get(province.abbr, 0.5)
        common["permit_risk_cost_usd_per_tco2"] = round(2.0 + 4.0 * (1.0 - policy_score), 3)
        destinations.append(
            {
                "destination_id": f"STORAGE_{province.abbr}",
                "region": province.name_en,
                "sink_type": "provincial_storage",
                "latitude": province.lat,
                "longitude": province.lon,
                "allowed_pathways": "geological_storage",
                "capacity_mtco2_per_year": round(capacity, 6),
                **common,
            }
        )

    eor_city_path = processed_dir / "storage" / "eor_city_screening.csv"
    if eor_city_path.exists():
        for row in _read_rows(eor_city_path):
            province = _province_by_name(row["province"])
            if province is None:
                continue
            capacity = _float(row.get("eor_annual_capacity_mtco2_per_year"))
            if capacity <= 0:
                continue
            common = _destination_common(
                province,
                grid_factors,
                0.0,
                0.0,
                exchange_rate_cny_per_usd,
            )
            policy_score = policy.get(province.abbr, 0.5)
            common["permit_risk_cost_usd_per_tco2"] = round(3.0 + 5.0 * (1.0 - policy_score), 3)
            common["min_co2_purity_fraction"] = 0.95
            common["required_pressure_bar"] = 120.0
            common["max_sox_ppm"] = 10.0
            common["max_nox_ppm"] = 10.0
            common["max_h2s_ppm"] = 10.0
            common["max_o2_percent"] = 2.0
            common["max_water_ppm"] = 200.0
            destinations.append(
                {
                    "destination_id": row["destination_id"],
                    "region": (
                        f"{province.name_en} EOR "
                        f"{row.get('prefecture_name_en') or row['prefecture_code']}"
                    ),
                    "sink_type": "eor_oilfield",
                    "latitude": _float(row.get("latitude")),
                    "longitude": _float(row.get("longitude")),
                    "allowed_pathways": "geological_storage",
                    "capacity_mtco2_per_year": round(capacity, 6),
                    **common,
                }
            )

    for spec in _product_destination_specs():
        dest_id = spec["destination_id"]
        province_name = spec["region"]
        sink_type = spec["sink_type"]
        pathways = spec["allowed_pathways"]
        capacity = product_capacities.get(dest_id, spec["default_capacity_mtco2_per_year"])
        province = _province_by_name(province_name)
        if province is None:
            continue
        common = _destination_common(
            province,
            grid_factors,
            carbon_price,
            0.0,
            exchange_rate_cny_per_usd,
        )
        common["h2_supply_mode"] = spec["h2_supply_mode"]
        common["electricity_procurement_mode"] = spec["electricity_procurement_mode"]
        common["flexible_load_fraction"] = spec["flexible_load_fraction"]
        if math.isfinite(spec["electricity_price_override_usd_per_mwh"]):
            common["electricity_price_usd_per_mwh"] = spec["electricity_price_override_usd_per_mwh"]
        if math.isfinite(spec["grid_emissions_override_kgco2e_per_mwh"]):
            common["grid_emissions_kgco2e_per_mwh"] = spec["grid_emissions_override_kgco2e_per_mwh"]
        if sink_type == "mineral_market":
            common["min_co2_purity_fraction"] = 0.80
            common["required_pressure_bar"] = 30.0
            common["max_sox_ppm"] = 100.0
            common["max_nox_ppm"] = 150.0
            common["max_h2s_ppm"] = 5.0
            common["max_o2_percent"] = 6.0
            common["max_water_ppm"] = 3000.0
        else:
            common["min_co2_purity_fraction"] = 0.98
            common["required_pressure_bar"] = 85.0
            common["max_sox_ppm"] = 2.0
            common["max_nox_ppm"] = 5.0
            common["max_h2s_ppm"] = 0.5
            common["max_o2_percent"] = 0.5
            common["max_water_ppm"] = 20.0
        destinations.append(
            {
                "destination_id": dest_id,
                "region": province.name_en,
                "sink_type": sink_type,
                "latitude": province.lat,
                "longitude": province.lon,
                "allowed_pathways": pathways,
                "capacity_mtco2_per_year": capacity,
                **common,
            }
        )
    return destinations


def build_real_hourly_profiles(
    processed_dir: Path,
    grid_factors: dict[str, float],
    exchange_rate_cny_per_usd: float = 7.2,
) -> list[dict[str, Any]]:
    load_path = processed_dir / "electricity" / "china_provincial_hourly_load_zenodo_8322210_wide.csv"
    rows = _read_rows(load_path)
    if not rows:
        return []
    provinces = [key for key in rows[0] if key != "hour_index"]
    loads_by_province: dict[str, list[float]] = {
        province: [_float(row.get(province)) for row in rows]
        for province in provinces
    }
    profiles: list[dict[str, Any]] = []
    for province in provinces:
        loads = loads_by_province[province]
        if not loads:
            continue
        min_load = min(loads)
        max_load = max(loads)
        span = max(max_load - min_load, 1e-9)
        price_base = _price_proxy_usd_per_mwh(province, exchange_rate_cny_per_usd)
        emissions_base = grid_factors.get(province, 530.6)
        price_shape = [0.75 + 0.50 * ((load - min_load) / span) for load in loads]
        emissions_shape = [0.85 + 0.30 * ((load - min_load) / span) for load in loads]
        price_avg = sum(price_shape) / len(price_shape)
        emissions_avg = sum(emissions_shape) / len(emissions_shape)
        for idx, load in enumerate(loads):
            profiles.append(
                {
                    "profile_id": province,
                    "hour": int(float(rows[idx]["hour_index"])) - 1,
                    "price_usd_per_mwh": round(price_base * price_shape[idx] / price_avg, 6),
                    "emissions_kgco2e_per_mwh": round(emissions_base * emissions_shape[idx] / emissions_avg, 6),
                }
            )
    return profiles


def build_real_hubs(processed_dir: Path) -> list[dict[str, Any]]:
    port_rows = _read_rows(processed_dir / "transport" / "unece_unlocode_cn_water_ports.csv")
    wanted = {
        "Tianjin": ("PORT_TIANJIN", 40.0),
        "Qingdao": ("PORT_QINGDAO", 35.0),
        "Shanghai": ("PORT_SHANGHAI", 45.0),
        "Ningbo": ("PORT_NINGBO", 40.0),
        "Shenzhen": ("PORT_SHENZHEN", 35.0),
        "Dalian": ("PORT_DALIAN", 30.0),
    }
    hubs: list[dict[str, Any]] = []
    for name, (hub_id, capacity) in wanted.items():
        matches = [
            row
            for row in port_rows
            if name.lower() in (row.get("name_wo_diacritics") or row.get("name") or "").lower()
            and row.get("latitude")
            and row.get("longitude")
        ]
        if not matches:
            continue
        row = matches[0]
        hubs.append(
            {
                "hub_id": hub_id,
                "region": row.get("subdivision") or name,
                "latitude": _float(row.get("latitude")),
                "longitude": _float(row.get("longitude")),
                "capacity_mtco2_per_year": capacity,
                "compression_cost_usd_per_tco2": 5.0,
                "compression_emissions_kgco2e_per_tco2": 7.0,
            }
        )
    hubs.extend(
        [
            {
                "hub_id": "INLAND_ORDOS",
                "region": "Inner Mongolia",
                "latitude": 39.6086,
                "longitude": 109.7816,
                "capacity_mtco2_per_year": 50.0,
                "compression_cost_usd_per_tco2": 4.0,
                "compression_emissions_kgco2e_per_tco2": 5.0,
            },
            {
                "hub_id": "INLAND_NW_RENEW",
                "region": "Northwest China",
                "latitude": 38.0,
                "longitude": 100.0,
                "capacity_mtco2_per_year": 40.0,
                "compression_cost_usd_per_tco2": 4.0,
                "compression_emissions_kgco2e_per_tco2": 5.0,
            },
        ]
    )
    return hubs


def build_real_inputs(
    data_dir: str | Path = ROOT / "data",
    out_dir: str | Path = ROOT / "data" / "real_inputs",
    source_year: int = 2024,
    top_sources: int = 120,
    capture_rate: float = 0.90,
    exchange_rate_cny_per_usd: float = 7.2,
    storage_horizon_years: int = 20,
    source_calibration_path: str | Path | None = None,
    extra_sources_path: str | Path | None = None,
) -> dict[str, Path]:
    data_root = Path(data_dir)
    processed_dir = data_root / "processed"
    output_dir = Path(out_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    grid_factors = _province_grid_factors(processed_dir / "electricity")
    carbon_price, removal_credit = _carbon_prices_usd(processed_dir / "policy", exchange_rate_cny_per_usd)
    sources, source_metadata = build_real_sources(
        processed_dir,
        source_year=source_year,
        top_sources=top_sources,
        capture_rate=capture_rate,
        source_calibration_path=source_calibration_path,
    )
    extra_sources, extra_source_metadata = load_extra_sources(extra_sources_path)
    sources.extend(extra_sources)
    source_metadata.extend(extra_source_metadata)
    destinations = build_real_destinations(
        processed_dir,
        grid_factors=grid_factors,
        carbon_price=carbon_price,
        removal_credit=removal_credit,
        exchange_rate_cny_per_usd=exchange_rate_cny_per_usd,
        storage_horizon_years=storage_horizon_years,
    )
    hourly_profiles = build_real_hourly_profiles(
        processed_dir,
        grid_factors,
        exchange_rate_cny_per_usd=exchange_rate_cny_per_usd,
    )
    hubs = build_real_hubs(processed_dir)

    paths = {
        "sources": output_dir / "spatial_sources_real.csv",
        "source_metadata": output_dir / "spatial_sources_real_metadata.csv",
        "destinations": output_dir / "spatial_destinations_real.csv",
        "hourly_profiles": output_dir / "hourly_energy_profiles_real.csv",
        "hubs": output_dir / "hubs_real.csv",
        "summary": output_dir / "build_summary.csv",
    }
    write_csv(paths["sources"], sources)
    write_csv(paths["source_metadata"], source_metadata)
    write_csv(paths["destinations"], destinations)
    write_csv(paths["hourly_profiles"], hourly_profiles)
    write_csv(paths["hubs"], hubs)
    write_csv(
        paths["summary"],
        [
            {
                "source_year": source_year,
                "top_sources": top_sources,
                "capture_rate": capture_rate,
                "exchange_rate_cny_per_usd": exchange_rate_cny_per_usd,
                "storage_horizon_years": storage_horizon_years,
                "source_calibration_path": str(source_calibration_path or ""),
                "extra_sources_path": str(extra_sources_path or ""),
                "extra_source_count": len(extra_sources),
                "source_count": len(sources),
                "source_available_mtpa": round(sum(float(row["co2_available_mtpa"]) for row in sources), 6),
                "destination_count": len(destinations),
                "storage_destination_count": sum(1 for row in destinations if row["sink_type"] == "provincial_storage"),
                "eor_destination_count": sum(1 for row in destinations if row["sink_type"] == "eor_oilfield"),
                "total_destination_capacity_mtpa": round(sum(float(row["capacity_mtco2_per_year"]) for row in destinations), 6),
                "hourly_profile_rows": len(hourly_profiles),
                "hub_count": len(hubs),
                "carbon_price_usd_per_tco2": round(carbon_price, 6),
                "durable_removal_credit_usd_per_tco2": round(removal_credit, 6),
            }
        ],
    )
    return paths
