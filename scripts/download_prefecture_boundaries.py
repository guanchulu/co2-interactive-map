"""Download and assemble China prefecture-level boundary GeoJSON.

The preferred long-term source is an audited official administrative boundary
file. This script creates the same model interface from DataV/AMap-style public
GeoJSON so the spatial join can run now and be replaced later without changing
downstream code.
"""

from __future__ import annotations

import json
import time
import urllib.request
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data" / "admin"
OUT_PATH = OUT_DIR / "prefecture_boundaries.geojson"
META_PATH = OUT_DIR / "prefecture_boundaries_metadata.json"

BASE_URL = "https://geo.datav.aliyun.com/areas_v3/bound"
CHINA_FULL_URL = f"{BASE_URL}/100000_full.json"
MUNICIPALITY_CODES = {110000, 120000, 310000, 500000}


def fetch_json(url: str) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": "co2-allocation-model/0.1"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def normalize_feature(feature: dict[str, Any], province: dict[str, Any]) -> dict[str, Any]:
    properties = dict(feature.get("properties") or {})
    province_props = province.get("properties") or {}
    adcode = int(properties.get("adcode"))
    province_code = int(province_props.get("adcode"))
    province_name = province_props.get("name", "")
    city_name = properties.get("name", "")
    normalized = {
        "prefecture_code": adcode,
        "prefecture_name": city_name,
        "province_code": province_code,
        "province_name": province_name,
        "boundary_level": properties.get("level", ""),
        "center": properties.get("center", []),
        "centroid": properties.get("centroid", properties.get("center", [])),
        "source": "DataV areas_v3 public boundary service",
        "source_url": BASE_URL,
        "evidence_grade": "B",
        "notes": "Formal polygon join interface; replace with audited official prefecture boundaries when available.",
    }
    return {
        "type": "Feature",
        "properties": normalized,
        "geometry": feature.get("geometry"),
    }


def build_prefecture_features() -> list[dict[str, Any]]:
    china = fetch_json(CHINA_FULL_URL)
    provinces = china.get("features", [])
    features: list[dict[str, Any]] = []
    seen: set[int] = set()
    for province in provinces:
        province_props = province.get("properties") or {}
        try:
            province_code = int(province_props.get("adcode"))
        except (TypeError, ValueError):
            continue
        province_name = province_props.get("name", "")
        if province_code in MUNICIPALITY_CODES:
            normalized = normalize_feature(province, province)
            normalized["properties"]["boundary_level"] = "municipality"
            features.append(normalized)
            seen.add(province_code)
            continue

        url = f"{BASE_URL}/{province_code}_full.json"
        try:
            province_full = fetch_json(url)
        except Exception as exc:  # pragma: no cover - network fallback path
            normalized = normalize_feature(province, province)
            normalized["properties"]["boundary_level"] = "province_fallback"
            normalized["properties"]["notes"] += f" Province full download failed: {exc}"
            features.append(normalized)
            seen.add(province_code)
            continue
        time.sleep(0.05)

        city_rows = [
            row for row in province_full.get("features", [])
            if (row.get("properties") or {}).get("level") == "city"
        ]
        if not city_rows and province_name:
            normalized = normalize_feature(province, province)
            normalized["properties"]["boundary_level"] = "province_fallback"
            features.append(normalized)
            seen.add(province_code)
            continue
        for row in city_rows:
            adcode = int((row.get("properties") or {}).get("adcode"))
            if adcode in seen:
                continue
            features.append(normalize_feature(row, province))
            seen.add(adcode)
    return features


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    features = build_prefecture_features()
    collection = {
        "type": "FeatureCollection",
        "features": features,
    }
    OUT_PATH.write_text(json.dumps(collection, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    META_PATH.write_text(
        json.dumps(
            {
                "source": "DataV areas_v3 public boundary service",
                "china_url": CHINA_FULL_URL,
                "boundary_level": "prefecture/city where available; municipality polygon for direct-administered cities",
                "feature_count": len(features),
                "evidence_grade": "B",
                "limitations": [
                    "Not a legal compliance boundary file.",
                    "Administrative boundary vintage follows the public DataV/AMap source, not a model-specific validation year.",
                    "Directly administered municipalities are represented as municipality polygons.",
                    "Replace this file with audited official prefecture boundaries for final publication.",
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Wrote {OUT_PATH} with {len(features)} features")


if __name__ == "__main__":
    main()
