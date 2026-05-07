"""Hourly electricity price and carbon-intensity profiles."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class HourlyPoint:
    profile_id: str
    hour: int
    price_usd_per_mwh: float
    emissions_kgco2e_per_mwh: float


@dataclass(frozen=True, slots=True)
class EffectiveElectricity:
    price_usd_per_mwh: float
    emissions_kgco2e_per_mwh: float
    selected_hours: int


def load_hourly_profiles(path: str | Path) -> dict[str, list[HourlyPoint]]:
    profiles: dict[str, list[HourlyPoint]] = {}
    with Path(path).open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            point = HourlyPoint(
                profile_id=row["profile_id"],
                hour=int(row["hour"]),
                price_usd_per_mwh=float(row["price_usd_per_mwh"]),
                emissions_kgco2e_per_mwh=float(row["emissions_kgco2e_per_mwh"]),
            )
            profiles.setdefault(point.profile_id, []).append(point)
    return {key: sorted(value, key=lambda point: point.hour) for key, value in profiles.items()}


def effective_electricity(
    points: list[HourlyPoint],
    procurement_mode: str,
    flexible_load_fraction: float,
    fallback_price_usd_per_mwh: float,
    fallback_emissions_kgco2e_per_mwh: float,
) -> EffectiveElectricity:
    if not points or procurement_mode == "annual_average":
        if not points:
            return EffectiveElectricity(
                fallback_price_usd_per_mwh,
                fallback_emissions_kgco2e_per_mwh,
                0,
            )
        selected = points
    elif procurement_mode == "flexible_low_cost":
        selected_count = max(1, round(len(points) * flexible_load_fraction))
        selected = sorted(points, key=lambda point: point.price_usd_per_mwh)[:selected_count]
    elif procurement_mode == "flexible_low_carbon":
        selected_count = max(1, round(len(points) * flexible_load_fraction))
        selected = sorted(points, key=lambda point: point.emissions_kgco2e_per_mwh)[:selected_count]
    else:
        raise ValueError(f"Unknown electricity procurement mode: {procurement_mode}")
    price = sum(point.price_usd_per_mwh for point in selected) / len(selected)
    emissions = sum(point.emissions_kgco2e_per_mwh for point in selected) / len(selected)
    return EffectiveElectricity(price, emissions, len(selected))

