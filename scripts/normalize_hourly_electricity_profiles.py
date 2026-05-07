"""Normalize sub-hourly electricity price/carbon profiles to hourly CSV.

The spatial model consumes one row per province/profile and hour:

profile_id,hour,price_usd_per_mwh,emissions_kgco2e_per_mwh

Raw market data can be hourly, 15-minute, or another regular interval. This
script aggregates raw rows to hourly arithmetic means before model ingestion.
"""

from __future__ import annotations

import argparse
import csv
import math
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


TIME_CANDIDATES = ("timestamp", "datetime", "time", "hour", "interval", "period")
PROFILE_CANDIDATES = ("profile_id", "province", "region", "area")


def parse_datetime(value: str) -> datetime | None:
    cleaned = value.strip().replace("/", "-")
    if not cleaned:
        return None
    try:
        return datetime.fromisoformat(cleaned)
    except ValueError:
        pass
    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M",
        "%Y%m%d%H%M%S",
        "%Y%m%d%H%M",
    ):
        try:
            return datetime.strptime(cleaned, fmt)
        except ValueError:
            continue
    return None


def pick_column(fieldnames: list[str], requested: str | None, candidates: tuple[str, ...]) -> str:
    if requested:
        if requested not in fieldnames:
            raise ValueError(f"Column not found: {requested}")
        return requested
    lower = {name.lower(): name for name in fieldnames}
    for candidate in candidates:
        if candidate in lower:
            return lower[candidate]
    raise ValueError(f"Could not infer column; available columns: {', '.join(fieldnames)}")


def hourly_bucket(
    raw_time: str,
    input_interval_minutes: float | None,
    base_datetime: datetime | None,
) -> int:
    parsed = parse_datetime(raw_time)
    if parsed is not None:
        if base_datetime is None:
            raise ValueError("base_datetime is required for timestamp input")
        return int((parsed - base_datetime).total_seconds() // 3600)

    value = float(raw_time)
    if input_interval_minutes and not math.isclose(input_interval_minutes, 60.0):
        return int(math.floor(value * input_interval_minutes / 60.0))
    return int(math.floor(value))


def aggregate_rows_to_hourly(
    rows: list[dict[str, str]],
    profile_column: str,
    time_column: str,
    price_column: str,
    emissions_column: str,
    input_interval_minutes: float | None = None,
) -> list[dict[str, Any]]:
    bases: dict[str, datetime] = {}
    for row in rows:
        parsed = parse_datetime(row[time_column])
        if parsed is None:
            continue
        profile = row[profile_column]
        bases[profile] = min(parsed, bases.get(profile, parsed))

    grouped: dict[tuple[str, int], dict[str, float]] = defaultdict(
        lambda: {"price_sum": 0.0, "emissions_sum": 0.0, "count": 0.0}
    )
    for row in rows:
        profile = row[profile_column]
        hour = hourly_bucket(row[time_column], input_interval_minutes, bases.get(profile))
        if hour < 0:
            raise ValueError(f"Negative hour after normalization for profile {profile}: {hour}")
        bucket = grouped[(profile, hour)]
        bucket["price_sum"] += float(row[price_column])
        bucket["emissions_sum"] += float(row[emissions_column])
        bucket["count"] += 1.0

    output = []
    for (profile, hour), bucket in sorted(grouped.items()):
        count = bucket["count"]
        output.append(
            {
                "profile_id": profile,
                "hour": hour,
                "price_usd_per_mwh": bucket["price_sum"] / count,
                "emissions_kgco2e_per_mwh": bucket["emissions_sum"] / count,
                "raw_points_per_hour": int(count),
            }
        )
    return output


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "profile_id",
        "hour",
        "price_usd_per_mwh",
        "emissions_kgco2e_per_mwh",
        "raw_points_per_hour",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--profile-column", default=None)
    parser.add_argument("--time-column", default=None)
    parser.add_argument("--price-column", default="price_usd_per_mwh")
    parser.add_argument("--emissions-column", default="emissions_kgco2e_per_mwh")
    parser.add_argument(
        "--input-interval-minutes",
        type=float,
        default=None,
        help="Use this when numeric time is a sub-hourly period index, e.g. 15 for 15-minute rows.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    fieldnames, rows = read_csv(Path(args.input))
    profile_column = pick_column(fieldnames, args.profile_column, PROFILE_CANDIDATES)
    time_column = pick_column(fieldnames, args.time_column, TIME_CANDIDATES)
    for column in (args.price_column, args.emissions_column):
        if column not in fieldnames:
            raise ValueError(f"Column not found: {column}")
    output = aggregate_rows_to_hourly(
        rows,
        profile_column=profile_column,
        time_column=time_column,
        price_column=args.price_column,
        emissions_column=args.emissions_column,
        input_interval_minutes=args.input_interval_minutes,
    )
    write_csv(Path(args.output), output)


if __name__ == "__main__":
    main()
