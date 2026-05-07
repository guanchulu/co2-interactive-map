from __future__ import annotations

import csv
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

import rasterio
from rasterio.warp import transform

try:
    from pypinyin import lazy_pinyin
except ImportError:  # pragma: no cover - optional label-only dependency
    lazy_pinyin = None


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RAW_STORAGE = DATA / "raw" / "storage"
PROCESSED_STORAGE = DATA / "processed" / "storage"
PREFECTURES = DATA / "admin" / "prefecture_boundaries.geojson"
OUT = PROCESSED_STORAGE / "eor_city_screening.csv"


PROVINCE_CODE_TO_EN = {
    110000: "Beijing",
    120000: "Tianjin",
    130000: "Hebei",
    140000: "Shanxi",
    150000: "Inner Mongolia",
    210000: "Liaoning",
    220000: "Jilin",
    230000: "Heilongjiang",
    310000: "Shanghai",
    320000: "Jiangsu",
    330000: "Zhejiang",
    340000: "Anhui",
    350000: "Fujian",
    360000: "Jiangxi",
    370000: "Shandong",
    410000: "Henan",
    420000: "Hubei",
    430000: "Hunan",
    440000: "Guangdong",
    450000: "Guangxi",
    460000: "Hainan",
    500000: "Chongqing",
    510000: "Sichuan",
    520000: "Guizhou",
    530000: "Yunnan",
    540000: "Tibet",
    610000: "Shaanxi",
    620000: "Gansu",
    630000: "Qinghai",
    640000: "Ningxia",
    650000: "Xinjiang",
}


PROVINCE_NAME_ALIASES = {
    "Guangxi Zhuang Autonomous Region": "Guangxi",
    "Inner Mongolia Autonomous Region": "Inner Mongolia",
    "Ningxia Hui Autonomous Region": "Ningxia",
    "Tibet Autonomous Region": "Tibet",
    "Xinjiang Uygur Autonomous Region": "Xinjiang",
}


PREFECTURE_CODE_TO_EN = {
    "130200": "Tangshan",
    "130300": "Qinhuangdao",
    "210200": "Dalian",
    "211100": "Panjin",
    "211400": "Huludao",
    "220700": "Songyuan",
    "230600": "Daqing",
    "370500": "Dongying",
    "410900": "Puyang",
    "632800": "Haixi",
    "650400": "Turpan",
}


PREFECTURE_SUFFIXES = (
    "\u8499\u53e4\u65cf\u85cf\u65cf\u81ea\u6cbb\u5dde",
    "\u8499\u53e4\u81ea\u6cbb\u5dde",
    "\u85cf\u65cf\u81ea\u6cbb\u5dde",
    "\u56de\u65cf\u81ea\u6cbb\u5dde",
    "\u58ee\u65cf\u82d7\u65cf\u81ea\u6cbb\u5dde",
    "\u5e03\u4f9d\u65cf\u82d7\u65cf\u81ea\u6cbb\u5dde",
    "\u81ea\u6cbb\u5dde",
    "\u5730\u533a",
    "\u76df",
    "\u5e02",
)


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


def f(value: Any, default: float = 0.0) -> float:
    try:
        if value in ("", None):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def prefecture_label_en(code: str, name: str) -> str:
    if code in PREFECTURE_CODE_TO_EN:
        return PREFECTURE_CODE_TO_EN[code]
    cleaned = name.strip()
    for suffix in PREFECTURE_SUFFIXES:
        if cleaned.endswith(suffix):
            cleaned = cleaned[: -len(suffix)]
            break
    if not cleaned or lazy_pinyin is None:
        return code
    return "".join(part.capitalize() for part in lazy_pinyin(cleaned))


def load_prefecture_centers() -> list[dict[str, Any]]:
    geo = json.loads(PREFECTURES.read_text(encoding="utf-8"))
    centers: list[dict[str, Any]] = []
    for feature in geo["features"]:
        props = feature["properties"]
        lon, lat = props.get("center") or props.get("centroid")
        province_code = int(props["province_code"])
        centers.append(
            {
                "prefecture_code": str(props["prefecture_code"]),
                "prefecture_name": props["prefecture_name"],
                "province_code": str(province_code),
                "province": PROVINCE_CODE_TO_EN.get(province_code, props["province_name"]),
                "latitude": float(lat),
                "longitude": float(lon),
            }
        )
    return centers


def nearest_prefecture(lat: float, lon: float, centers: list[dict[str, Any]]) -> dict[str, Any]:
    lat_rad = math.radians(lat)

    def score(center: dict[str, Any]) -> float:
        dlat = lat - center["latitude"]
        dlon = (lon - center["longitude"]) * math.cos(lat_rad)
        return dlat * dlat + dlon * dlon

    return min(centers, key=score)


def aggregate_raster_to_prefectures(path: Path, centers: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"raw_sum": 0.0, "positive_pixel_count": 0}
    )
    with rasterio.open(path) as dataset:
        data = dataset.read(1, masked=True).filled(0.0)
        rows, cols = (data > 0).nonzero()
        if len(rows) == 0:
            return {}
        xs, ys = rasterio.transform.xy(dataset.transform, rows, cols, offset="center")
        lons, lats = transform(dataset.crs, "EPSG:4326", xs, ys)
        for row_idx, col_idx, lat, lon in zip(rows, cols, lats, lons):
            value = float(data[row_idx, col_idx])
            if value <= 0:
                continue
            center = nearest_prefecture(lat, lon, centers)
            key = center["prefecture_code"]
            record = out[key]
            record.update(center)
            record["raw_sum"] += value
            record["positive_pixel_count"] += 1
    return out


def province_eor_totals() -> dict[str, dict[str, float]]:
    rows = read_csv(PROCESSED_STORAGE / "provincial_level_co2_storage_figshare_27646707.csv")
    totals: dict[str, dict[str, float]] = {}
    for row in rows:
        province = PROVINCE_NAME_ALIASES.get(row["Province name"], row["Province name"])
        totals[province] = {
            "published_eor_storage_potential_mt": f(row.get("Storage potential-EOR (Mt)")),
            "published_eor_injection_rate_avg_mtpa": f(
                row.get("Injection rate capability-EOR (Mt/a) (Average)")
            ),
            "published_eor_injection_rate_min_mtpa": f(
                row.get("Injection rate capability-EOR (Mt/a) (Minimum)")
            ),
            "published_eor_injection_rate_max_mtpa": f(
                row.get("Injection rate capability-EOR (Mt/a) (Maximum)")
            ),
        }
    return totals


def build_rows(storage_horizon_years: int = 20) -> list[dict[str, Any]]:
    centers = load_prefecture_centers()
    injection = aggregate_raster_to_prefectures(RAW_STORAGE / "EOR-injectionl.tif", centers)
    storage = aggregate_raster_to_prefectures(RAW_STORAGE / "EOR-storage potential.tif", centers)
    province_totals = province_eor_totals()

    province_raw_injection: dict[str, float] = defaultdict(float)
    province_raw_storage: dict[str, float] = defaultdict(float)
    for record in injection.values():
        province_raw_injection[record["province"]] += record["raw_sum"]
    for record in storage.values():
        province_raw_storage[record["province"]] += record["raw_sum"]

    keys = sorted(set(injection) | set(storage))
    rows: list[dict[str, Any]] = []
    for key in keys:
        base = injection.get(key) or storage.get(key)
        if not base:
            continue
        province = base["province"]
        totals = province_totals.get(province, {})
        raw_injection = injection.get(key, {}).get("raw_sum", 0.0)
        raw_storage = storage.get(key, {}).get("raw_sum", 0.0)

        published_injection = totals.get("published_eor_injection_rate_avg_mtpa", 0.0)
        published_storage = totals.get("published_eor_storage_potential_mt", 0.0)
        scaled_injection = (
            raw_injection / province_raw_injection[province] * published_injection
            if province_raw_injection[province] > 0
            else 0.0
        )
        scaled_storage = (
            raw_storage / province_raw_storage[province] * published_storage
            if province_raw_storage[province] > 0
            else 0.0
        )
        annual_capacity = min(
            scaled_injection,
            scaled_storage / max(storage_horizon_years, 1) if scaled_storage > 0 else 0.0,
        )
        if annual_capacity <= 1e-6:
            continue
        rows.append(
            {
                "destination_id": f"EOR_{key}",
                "prefecture_code": key,
                "prefecture_name": base["prefecture_name"],
                "prefecture_name_en": prefecture_label_en(key, base["prefecture_name"]),
                "province_code": base["province_code"],
                "province": province,
                "latitude": round(base["latitude"], 6),
                "longitude": round(base["longitude"], 6),
                "eor_injection_rate_avg_mtpa": round(scaled_injection, 6),
                "eor_storage_potential_mt": round(scaled_storage, 6),
                "eor_annual_capacity_mtco2_per_year": round(annual_capacity, 6),
                "positive_injection_pixel_count": int(
                    injection.get(key, {}).get("positive_pixel_count", 0)
                ),
                "positive_storage_pixel_count": int(
                    storage.get(key, {}).get("positive_pixel_count", 0)
                ),
                "published_province_eor_injection_rate_avg_mtpa": round(published_injection, 6),
                "published_province_eor_storage_potential_mt": round(published_storage, 6),
                "storage_horizon_years": storage_horizon_years,
                "source_url": "https://doi.org/10.6084/m9.figshare.27646707",
                "evidence_grade": "B/C",
                "notes": (
                    "EOR-positive raster cells assigned to nearest prefecture center and scaled "
                    "to published provincial EOR injection/storage totals; screening layer only."
                ),
            }
        )
    return sorted(rows, key=lambda row: row["eor_annual_capacity_mtco2_per_year"], reverse=True)


if __name__ == "__main__":
    rows = build_rows()
    write_csv(OUT, rows)
    print(f"Wrote {len(rows)} EOR city-screening rows to {OUT}")
