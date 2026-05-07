"""Crosswalk CEADs city names to current prefecture codes.

The CEADs 290-city workbook stores Chinese city labels but not current
prefecture codes.  This script links those labels to the DataV prefecture
boundary codes used by the spatial model, while keeping historical boundary
changes explicit.
"""

from __future__ import annotations

import csv
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CITY_LONG = ROOT / "data" / "processed" / "co2_sources" / "ceads_1997_2019_city_emissions_long.csv"
BOUNDARIES = ROOT / "data" / "admin" / "prefecture_boundaries.geojson"
OUT_DIR = ROOT / "data" / "processed" / "co2_sources"
SUMMARY_DOC = ROOT / "docs" / "joule_submission" / "ceads_city_crosswalk_summary.md"

SUFFIXES = ["自治州", "地区", "林区", "市", "盟"]
PROVINCE_SUFFIXES = [
    "壮族自治区",
    "回族自治区",
    "维吾尔自治区",
    "藏族自治区",
    "自治区",
    "省",
    "市",
]
ETHNIC_TERMS = [
    "回族",
    "壮族",
    "蒙古族",
    "蒙古",
    "藏族",
    "彝族",
    "苗族",
    "土家族",
    "哈尼族",
    "傣族",
    "傈僳族",
    "哈萨克",
    "柯尔克孜",
    "朝鲜族",
    "白族",
    "侗族",
    "瑶族",
    "布依族",
]

# Current-boundary proxies for CEADs historical labels that no longer map
# one-to-one to a current prefecture boundary.
MANUAL_OVERRIDES: dict[str, dict[str, Any]] = {
    "山东莱芜": {
        "prefecture_code": "370100",
        "match_method": "historical_prefecture_merged_to_current_city",
        "confidence": 0.75,
        "use_in_map": 1,
        "use_in_lp_city_cap": 1,
        "notes": "Laiwu was merged into Jinan; current-boundary map and LP cap use Jinan.",
    },
    "安徽巢湖": {
        "prefecture_code": "340100",
        "match_method": "historical_prefecture_split_current_proxy",
        "confidence": 0.55,
        "use_in_map": 1,
        "use_in_lp_city_cap": 0,
        "notes": "Historical Chaohu was split; map uses Hefei proxy, but LP cap is disabled.",
    },
    "新疆伊犁州直属县": {
        "prefecture_code": "654000",
        "match_method": "ceads_subprefecture_to_current_prefecture",
        "confidence": 0.70,
        "use_in_map": 1,
        "use_in_lp_city_cap": 0,
        "notes": "CEADs label covers Ili directly administered counties; map uses Ili prefecture proxy, LP cap disabled.",
    },
    "湖北恩施州": {
        "prefecture_code": "422800",
        "match_method": "ceads_autonomous_prefecture_short_label",
        "confidence": 0.95,
        "use_in_map": 1,
        "use_in_lp_city_cap": 1,
        "notes": "CEADs short label maps to Enshi Tujia and Miao Autonomous Prefecture.",
    },
}


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
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if math.isfinite(parsed) else default


def short_province(name: str) -> str:
    text = name.strip().replace(" ", "")
    for suffix in PROVINCE_SUFFIXES:
        if text.endswith(suffix):
            return text[: -len(suffix)]
    return text


def core_city_name(name: str) -> str:
    text = name.strip().replace(" ", "")
    for suffix in SUFFIXES:
        if text.endswith(suffix):
            text = text[: -len(suffix)]
            break
    for term in ETHNIC_TERMS:
        text = text.replace(term, "")
    return text


def load_boundaries() -> tuple[dict[str, dict[str, Any]], dict[tuple[str, str], dict[str, Any]], set[str]]:
    geo = json.loads(BOUNDARIES.read_text(encoding="utf-8"))
    by_code: dict[str, dict[str, Any]] = {}
    by_pair: dict[tuple[str, str], dict[str, Any]] = {}
    province_prefixes: set[str] = set()
    for feature in geo.get("features", []):
        props = feature.get("properties", {})
        code = str(props.get("prefecture_code", ""))
        if not code:
            continue
        province_short = short_province(str(props.get("province_name", "")))
        city_core = core_city_name(str(props.get("prefecture_name", "")))
        rec = {
            "prefecture_code": code,
            "prefecture_name_zh": props.get("prefecture_name", ""),
            "prefecture_core_zh": city_core,
            "province_code": str(props.get("province_code", "")),
            "province_name_zh": props.get("province_name", ""),
            "province_short_zh": province_short,
            "boundary_level": props.get("boundary_level", ""),
            "boundary_source": props.get("source", ""),
            "boundary_evidence_grade": props.get("evidence_grade", "B"),
        }
        by_code[code] = rec
        by_pair[(province_short, city_core)] = rec
        province_prefixes.add(province_short)
        province_prefixes.add(str(props.get("province_name", "")).strip())
    return by_code, by_pair, province_prefixes


def strip_province_prefix(city_name: str, province_prefixes: set[str]) -> tuple[str, str]:
    text = city_name.strip().replace(" ", "")
    for prefix in sorted(province_prefixes, key=len, reverse=True):
        if prefix and text.startswith(prefix) and len(text) > len(prefix):
            return short_province(prefix), text[len(prefix) :]
    return "", text


def build_crosswalk() -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    by_code, by_pair, province_prefixes = load_boundaries()
    city_rows = read_csv(CITY_LONG)
    ceads_city_names = sorted({row["city_name_clean_zh"] for row in city_rows})
    boundary_by_core: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for rec in by_code.values():
        boundary_by_core[rec["prefecture_core_zh"]].append(rec)

    crosswalk: list[dict[str, Any]] = []
    lookup: dict[str, dict[str, Any]] = {}
    for ceads_name in ceads_city_names:
        source_province, city_label_without_province = strip_province_prefix(ceads_name, province_prefixes)
        city_core = core_city_name(city_label_without_province)
        match: dict[str, Any] | None = None
        method = ""
        confidence = 0.0
        use_in_map = 0
        use_in_lp_city_cap = 0
        notes = ""

        if ceads_name in MANUAL_OVERRIDES:
            override = MANUAL_OVERRIDES[ceads_name]
            match = by_code.get(str(override["prefecture_code"]))
            method = override["match_method"]
            confidence = f(override["confidence"])
            use_in_map = int(override["use_in_map"])
            use_in_lp_city_cap = int(override["use_in_lp_city_cap"])
            notes = str(override["notes"])
        elif source_province and (source_province, city_core) in by_pair:
            match = by_pair[(source_province, city_core)]
            method = "province_prefix_exact_city_core"
            confidence = 1.0
            use_in_map = 1
            use_in_lp_city_cap = 1
            notes = "Exact match after stripping CEADs province prefix and current administrative suffix."
        else:
            candidates = boundary_by_core.get(core_city_name(ceads_name), [])
            if len(candidates) == 1:
                match = candidates[0]
                method = "unique_city_core_exact"
                confidence = 0.95
                use_in_map = 1
                use_in_lp_city_cap = 1
                notes = "Unique exact city-core match without explicit province prefix."

        if match is None:
            row = {
                "ceads_city_name_zh": ceads_name,
                "ceads_source_province_zh": source_province,
                "ceads_city_core_zh": city_core,
                "prefecture_code": "",
                "prefecture_name_zh": "",
                "prefecture_core_zh": "",
                "province_code": "",
                "province_name_zh": "",
                "match_status": "unmatched",
                "match_method": "unmatched",
                "match_confidence": 0.0,
                "use_in_map": 0,
                "use_in_lp_city_cap": 0,
                "evidence_grade": "D",
                "notes": "No current-boundary match; requires manual administrative history review.",
            }
        else:
            row = {
                "ceads_city_name_zh": ceads_name,
                "ceads_source_province_zh": source_province or match["province_short_zh"],
                "ceads_city_core_zh": city_core,
                "prefecture_code": match["prefecture_code"],
                "prefecture_name_zh": match["prefecture_name_zh"],
                "prefecture_core_zh": match["prefecture_core_zh"],
                "province_code": match["province_code"],
                "province_name_zh": match["province_name_zh"],
                "match_status": "matched",
                "match_method": method,
                "match_confidence": confidence,
                "use_in_map": use_in_map,
                "use_in_lp_city_cap": use_in_lp_city_cap,
                "evidence_grade": "B" if confidence >= 0.95 else "B/C",
                "notes": notes,
            }
        crosswalk.append(row)
        lookup[ceads_name] = row
    return crosswalk, lookup


def enriched_long_rows(crosswalk_lookup: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in read_csv(CITY_LONG):
        cw = crosswalk_lookup[row["city_name_clean_zh"]]
        out.append(
            {
                **row,
                "prefecture_code": cw["prefecture_code"],
                "prefecture_name_zh": cw["prefecture_name_zh"],
                "province_code": cw["province_code"],
                "province_name_zh": cw["province_name_zh"],
                "match_status": cw["match_status"],
                "match_method": cw["match_method"],
                "match_confidence": cw["match_confidence"],
                "use_in_map": cw["use_in_map"],
                "use_in_lp_city_cap": cw["use_in_lp_city_cap"],
                "crosswalk_evidence_grade": cw["evidence_grade"],
            }
        )
    return out


def slope(rows: list[tuple[int, float]]) -> float:
    if len(rows) < 2:
        return 0.0
    xs = [year for year, _ in rows]
    ys = [value for _, value in rows]
    xbar = sum(xs) / len(xs)
    ybar = sum(ys) / len(ys)
    denom = sum((x - xbar) ** 2 for x in xs)
    if denom <= 0:
        return 0.0
    return sum((x - xbar) * (y - ybar) for x, y in rows) / denom


def summarize_prefectures(long_rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in long_rows:
        if row["match_status"] == "matched" and int(row["use_in_map"]) == 1:
            grouped[str(row["prefecture_code"])].append(row)

    summary: list[dict[str, Any]] = []
    caps: list[dict[str, Any]] = []
    for code, rows in sorted(grouped.items()):
        by_year: dict[int, float] = defaultdict(float)
        names = sorted({row["city_name_clean_zh"] for row in rows})
        methods = sorted({row["match_method"] for row in rows})
        min_conf = min(f(row["match_confidence"], 0.0) for row in rows)
        use_lp = any(int(row["use_in_lp_city_cap"]) == 1 for row in rows)
        for row in rows:
            by_year[int(row["year"])] += f(row["emissions_mtco2"])
        series = sorted(by_year.items())
        latest_year, latest_value = series[-1]
        peak_year, peak_value = max(series, key=lambda item: item[1])
        first_year, first_value = series[0]
        value_2010 = by_year.get(2010, 0.0)
        value_2015 = by_year.get(2015, 0.0)
        value_2019 = by_year.get(2019, 0.0)
        change = ((latest_value - value_2010) / value_2010 * 100.0) if value_2010 > 0 else ""
        base_row = rows[0]
        rec = {
            "prefecture_code": code,
            "prefecture_name_zh": base_row["prefecture_name_zh"],
            "province_code": base_row["province_code"],
            "province_name_zh": base_row["province_name_zh"],
            "ceads_city_names_zh": ";".join(names),
            "match_methods": ";".join(methods),
            "match_confidence_min": min_conf,
            "use_in_lp_city_cap": int(use_lp),
            "years_observed": len(series),
            "first_year": first_year,
            "first_emissions_mtco2": first_value,
            "latest_year": latest_year,
            "latest_emissions_mtco2": latest_value,
            "peak_year": peak_year,
            "peak_emissions_mtco2": peak_value,
            "emissions_2010_mtco2": value_2010,
            "emissions_2015_mtco2": value_2015,
            "emissions_2019_mtco2": value_2019,
            "change_2010_to_latest_pct": change,
            "trend_slope_mtco2_per_year": slope(series),
            "history_evidence_grade": "B" if min_conf >= 0.95 else "B/C",
            "source": "CEADs 1995/1997-2019 290-city emission inventory crosswalked to DataV prefectures",
        }
        summary.append(rec)
        if use_lp and latest_value > 0:
            caps.append(
                {
                    "prefecture_code": code,
                    "prefecture_name_zh": base_row["prefecture_name_zh"],
                    "cap_basis_year": latest_year,
                    "latest_emissions_mtco2": latest_value,
                    "capture_rate_for_cap": 0.90,
                    "city_non_dac_capture_cap_mtco2_per_year": latest_value * 0.90,
                    "match_confidence_min": min_conf,
                    "source": "CEADs city emissions crosswalk; non-DAC LP city cap",
                }
            )
    return summary, caps


def write_summary(crosswalk: list[dict[str, Any]], summary_rows: list[dict[str, Any]], caps: list[dict[str, Any]]) -> None:
    matched = [row for row in crosswalk if row["match_status"] == "matched"]
    exact = [row for row in matched if row["match_confidence"] >= 0.95]
    proxy = [row for row in matched if row["match_confidence"] < 0.95]
    lp_cap = [row for row in matched if int(row["use_in_lp_city_cap"]) == 1]
    latest_total = sum(f(row["latest_emissions_mtco2"]) for row in summary_rows)
    lines = [
        "# CEADs City Crosswalk Summary",
        "",
        "The CEADs 290-city emission inventory is now linked to the current prefecture-code layer used by the spatial model.",
        "",
        f"- Unique CEADs city labels: {len(crosswalk):,}.",
        f"- Matched labels: {len(matched):,}; high-confidence exact/current labels: {len(exact):,}; historical/proxy labels: {len(proxy):,}.",
        f"- Current prefectures with CEADs history summaries: {len(summary_rows):,}.",
        f"- CEADs labels eligible for non-DAC LP city caps: {len(lp_cap):,}; cap table rows: {len(caps):,}.",
        f"- Latest-year crosswalked city emissions sum: {latest_total:,.1f} MtCO2.",
        "",
        "Manual/proxy matches are retained for map context, but only high-confidence current or merged-prefecture matches are used as LP city caps. Split or sub-prefecture historical labels are not used as hard optimization constraints.",
    ]
    SUMMARY_DOC.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    crosswalk, lookup = build_crosswalk()
    long_rows = enriched_long_rows(lookup)
    summary_rows, caps = summarize_prefectures(long_rows)
    unmatched = [row for row in crosswalk if row["match_status"] != "matched"]

    write_csv(OUT_DIR / "ceads_city_prefecture_crosswalk.csv", crosswalk)
    write_csv(OUT_DIR / "ceads_city_prefecture_unmatched.csv", unmatched)
    write_csv(OUT_DIR / "ceads_city_emissions_prefecture_long.csv", long_rows)
    write_csv(OUT_DIR / "ceads_city_emissions_prefecture_summary.csv", summary_rows)
    write_csv(OUT_DIR / "ceads_city_emission_lp_caps.csv", caps)
    write_summary(crosswalk, summary_rows, caps)
    print("Built CEADs city-prefecture crosswalk")
    print(f"matched labels: {sum(1 for row in crosswalk if row['match_status'] == 'matched')}/{len(crosswalk)}")
    print(f"prefecture summaries: {len(summary_rows)}")
    print(f"LP city caps: {len(caps)}")


if __name__ == "__main__":
    main()
