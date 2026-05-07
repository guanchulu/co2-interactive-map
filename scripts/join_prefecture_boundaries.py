"""Join point CSV rows to prefecture boundary polygons."""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BOUNDARIES = ROOT / "data" / "admin" / "prefecture_boundaries.geojson"


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


def rings_from_geometry(geometry: dict[str, Any]) -> list[list[list[float]]]:
    gtype = geometry.get("type")
    coords = geometry.get("coordinates") or []
    if gtype == "Polygon":
        return coords
    if gtype == "MultiPolygon":
        rings: list[list[list[float]]] = []
        for polygon in coords:
            rings.extend(polygon)
        return rings
    return []


def all_points(rings: list[list[list[float]]]) -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = []
    for ring in rings:
        for point in ring:
            if len(point) >= 2:
                points.append((float(point[0]), float(point[1])))
    return points


def bbox(points: list[tuple[float, float]]) -> tuple[float, float, float, float]:
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return min(xs), min(ys), max(xs), max(ys)


def point_in_ring(lon: float, lat: float, ring: list[list[float]]) -> bool:
    inside = False
    if len(ring) < 3:
        return False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = float(ring[i][0]), float(ring[i][1])
        xj, yj = float(ring[j][0]), float(ring[j][1])
        intersects = (yi > lat) != (yj > lat)
        if intersects:
            x_at_lat = (xj - xi) * (lat - yi) / (yj - yi) + xi
            if lon < x_at_lat:
                inside = not inside
        j = i
    return inside


def point_in_feature(lon: float, lat: float, rings: list[list[list[float]]]) -> bool:
    inside_any = False
    for ring in rings:
        if point_in_ring(lon, lat, ring):
            inside_any = not inside_any
    return inside_any


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371.0088
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2.0) ** 2
    return 2.0 * radius * math.asin(math.sqrt(a))


def feature_center(properties: dict[str, Any], points: list[tuple[float, float]]) -> tuple[float, float]:
    center = properties.get("centroid") or properties.get("center") or []
    if isinstance(center, list) and len(center) >= 2:
        return float(center[1]), float(center[0])
    lon = sum(point[0] for point in points) / max(len(points), 1)
    lat = sum(point[1] for point in points) / max(len(points), 1)
    return lat, lon


def load_boundaries(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    loaded: list[dict[str, Any]] = []
    for feature in data.get("features", []):
        rings = rings_from_geometry(feature.get("geometry") or {})
        points = all_points(rings)
        if not points:
            continue
        props = feature.get("properties") or {}
        center_lat, center_lon = feature_center(props, points)
        loaded.append(
            {
                "properties": props,
                "rings": rings,
                "bbox": bbox(points),
                "center_lat": center_lat,
                "center_lon": center_lon,
            }
        )
    return loaded


def match_point(lon: float, lat: float, features: list[dict[str, Any]]) -> tuple[dict[str, Any], str, float]:
    bbox_matches = []
    for feature in features:
        min_lon, min_lat, max_lon, max_lat = feature["bbox"]
        if min_lon <= lon <= max_lon and min_lat <= lat <= max_lat:
            bbox_matches.append(feature)
    for feature in bbox_matches:
        if point_in_feature(lon, lat, feature["rings"]):
            return feature, "polygon_contains", 0.0
    nearest = min(
        features,
        key=lambda feature: haversine_km(lat, lon, feature["center_lat"], feature["center_lon"]),
    )
    distance = haversine_km(lat, lon, nearest["center_lat"], nearest["center_lon"])
    return nearest, "nearest_centroid_fallback", distance


def join_points(
    points: list[dict[str, str]],
    features: list[dict[str, Any]],
    id_column: str,
    lat_column: str,
    lon_column: str,
    type_label: str,
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for row in points:
        lat = float(row[lat_column])
        lon = float(row[lon_column])
        feature, method, fallback_km = match_point(lon, lat, features)
        props = feature["properties"]
        output.append(
            {
                "entity_type": type_label,
                "entity_id": row.get(id_column, ""),
                "latitude": lat,
                "longitude": lon,
                "prefecture_code": props.get("prefecture_code", ""),
                "prefecture_name": props.get("prefecture_name", ""),
                "province_code": props.get("province_code", ""),
                "province_name": props.get("province_name", ""),
                "boundary_level": props.get("boundary_level", ""),
                "join_method": method,
                "fallback_distance_km": fallback_km,
                "boundary_source": props.get("source", ""),
                "evidence_grade": props.get("evidence_grade", ""),
            }
        )
    return output


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--boundaries", default=str(DEFAULT_BOUNDARIES))
    parser.add_argument("--points", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--id-column", required=True)
    parser.add_argument("--lat-column", default="latitude")
    parser.add_argument("--lon-column", default="longitude")
    parser.add_argument("--type-label", default="point")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    boundaries = load_boundaries(Path(args.boundaries))
    points = read_csv(Path(args.points))
    rows = join_points(
        points,
        boundaries,
        id_column=args.id_column,
        lat_column=args.lat_column,
        lon_column=args.lon_column,
        type_label=args.type_label,
    )
    write_csv(Path(args.out), rows)
    fallback_count = sum(1 for row in rows if row["join_method"] != "polygon_contains")
    print(f"Wrote {args.out}: {len(rows)} rows, {fallback_count} nearest-centroid fallbacks")


if __name__ == "__main__":
    main()
