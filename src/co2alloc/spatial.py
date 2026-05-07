"""Spatial, policy-aware CO2 source-sink allocation model."""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .constants import capital_recovery_factor
from .decision import evaluate_all
from .hourly import EffectiveElectricity, HourlyPoint, effective_electricity
from .hydrogen import HydrogenSupply, electrolytic_hydrogen, market_hydrogen
from .learning import LearningRow, learning_multipliers
from .pipeline_cost import pipeline_transport_cost, pipeline_transport_emissions_kgco2e_per_tco2
from .scenario import Scenario
from .types import Evaluation


EARTH_RADIUS_KM = 6371.0088


@dataclass(frozen=True, slots=True)
class Source:
    source_id: str
    region: str
    source_type: str
    latitude: float
    longitude: float
    co2_available_mtpa: float
    capture_cost_usd_per_tco2: float
    capture_emissions_kgco2e_per_tco2: float
    capture_energy_kwh_per_tco2: float
    co2_purity_fraction: float
    capture_pressure_bar: float = 1.2
    sox_ppm: float = 0.0
    nox_ppm: float = 0.0
    h2s_ppm: float = 0.0
    o2_percent: float = 0.0
    water_ppm: float = 0.0
    annual_capacity_factor: float = 0.9


@dataclass(frozen=True, slots=True)
class Destination:
    destination_id: str
    region: str
    sink_type: str
    latitude: float
    longitude: float
    allowed_pathways: tuple[str, ...]
    capacity_mtco2_per_year: float
    electricity_price_usd_per_mwh: float
    grid_emissions_kgco2e_per_mwh: float
    h2_price_usd_per_kg: float
    h2_emissions_kgco2e_per_kg: float
    carbon_price_usd_per_tco2: float = 0.0
    carbon_tax_usd_per_tco2: float = 0.0
    durable_removal_credit_usd_per_tco2: float = 0.0
    heat_price_usd_per_gj: float = 6.0
    min_co2_purity_fraction: float = 0.95
    required_pressure_bar: float = 110.0
    max_sox_ppm: float = 10.0
    max_nox_ppm: float = 10.0
    max_h2s_ppm: float = 1.0
    max_o2_percent: float = 2.0
    max_water_ppm: float = 50.0
    purification_cost_usd_per_tco2_per_fraction: float = 120.0
    purification_emissions_kgco2e_per_tco2_per_fraction: float = 80.0
    impurity_removal_cost_usd_per_tco2_per_index: float = 8.0
    impurity_removal_emissions_kgco2e_per_tco2_per_index: float = 3.0
    pressure_boost_kwh_per_tco2_per_ln_ratio: float = 24.0
    h2_supply_mode: str = "market"
    electrolyzer_capex_usd_per_kw: float = 700.0
    electrolyzer_kwh_per_kg_h2: float = 52.0
    electrolyzer_capacity_factor: float = 0.55
    electrolyzer_lifetime_years: int = 15
    electrolyzer_fixed_om_fraction: float = 0.03
    h2_compression_storage_cost_usd_per_kg: float = 0.25
    water_l_per_kg_h2: float = 15.0
    water_price_usd_per_m3: float = 1.0
    water_emissions_kgco2e_per_m3: float = 0.4
    hourly_profile_id: str = ""
    electricity_procurement_mode: str = "annual_average"
    flexible_load_fraction: float = 1.0
    water_available_m3_per_year: float = 1e12
    land_available_km2: float = 1e9
    land_cost_usd_per_m2_year: float = 0.0
    permit_risk_cost_usd_per_tco2: float = 0.0
    trl_risk_premium_fraction: float = 0.0


@dataclass(frozen=True, slots=True)
class TransportMode:
    mode: str
    min_distance_km: float
    max_distance_km: float
    route_factor: float
    fixed_cost_usd_per_tco2: float
    cost_usd_per_tkm: float
    emissions_kgco2e_per_tkm: float
    reference_flow_mtpa: float = 10.0
    scale_exponent: float = 0.25
    min_scale_multiplier: float = 0.55
    max_scale_multiplier: float = 2.5

    def supports(self, distance_km: float) -> bool:
        return self.min_distance_km <= distance_km <= self.max_distance_km


@dataclass(frozen=True, slots=True)
class Hub:
    hub_id: str
    region: str
    latitude: float
    longitude: float
    capacity_mtco2_per_year: float
    compression_cost_usd_per_tco2: float
    compression_emissions_kgco2e_per_tco2: float


@dataclass(frozen=True, slots=True)
class SpatialCandidate:
    source: Source
    destination: Destination
    transport_mode: TransportMode
    hub: Hub | None
    distance_km: float
    routed_distance_km: float
    transport_scale_multiplier: float
    evaluation: Evaluation
    effective_electricity: EffectiveElectricity
    hydrogen_supply: HydrogenSupply
    capture_energy_cost_usd_per_tco2: float
    capture_energy_emissions_kgco2e_per_tco2: float
    spec_cost_usd_per_tco2: float
    spec_emissions_kgco2e_per_tco2: float
    transport_cost_usd_per_tco2: float
    transport_emissions_kgco2e_per_tco2: float
    water_m3_per_tco2: float
    land_m2_per_tpa_co2: float
    land_cost_usd_per_tco2: float
    risk_cost_usd_per_tco2: float
    capex_learning_multiplier: float
    opex_learning_multiplier: float
    adjusted_induced_kgco2e_per_tco2: float
    adjusted_net_avoided_kgco2e_per_tco2: float
    adjusted_gross_cost_usd_per_tco2: float
    adjusted_net_cost_usd_per_tco2: float
    adjusted_abatement_cost_usd_per_tco2: float
    adjusted_removal_cost_usd_per_tco2: float

    @property
    def pathway(self) -> str:
        return self.evaluation.inventory.pathway

    @property
    def technology_family(self) -> str:
        return self.evaluation.inventory.technology_family

    @property
    def pathway_market_capacity_mtpa(self) -> float:
        return self.evaluation.inventory.market_capacity_mtco2_per_year

    def flat_record(self) -> dict[str, float | str]:
        inv = self.evaluation.inventory
        return {
            "source_id": self.source.source_id,
            "source_region": self.source.region,
            "source_type": self.source.source_type,
            "destination_id": self.destination.destination_id,
            "destination_region": self.destination.region,
            "sink_type": self.destination.sink_type,
            "hub_id": self.hub.hub_id if self.hub else "",
            "pathway": inv.pathway,
            "technology_family": inv.technology_family,
            "product": inv.product_name,
            "transport_mode": self.transport_mode.mode,
            "distance_km": self.distance_km,
            "routed_distance_km": self.routed_distance_km,
            "transport_scale_multiplier": self.transport_scale_multiplier,
            "source_available_mtpa": self.source.co2_available_mtpa,
            "destination_capacity_mtpa": self.destination.capacity_mtco2_per_year,
            "pathway_market_capacity_mtpa": inv.market_capacity_mtco2_per_year,
            "electricity_price_usd_per_mwh": self.effective_electricity.price_usd_per_mwh,
            "grid_emissions_kgco2e_per_mwh": self.effective_electricity.emissions_kgco2e_per_mwh,
            "selected_electricity_hours": self.effective_electricity.selected_hours,
            "h2_supply_mode": self.hydrogen_supply.mode,
            "effective_h2_price_usd_per_kg": self.hydrogen_supply.price_usd_per_kg,
            "effective_h2_emissions_kgco2e_per_kg": self.hydrogen_supply.emissions_kgco2e_per_kg,
            "h2_electrolysis_kwh_per_kg": self.hydrogen_supply.electricity_kwh_per_kg,
            "h2_water_l_per_kg": self.hydrogen_supply.water_l_per_kg,
            "carbon_price_usd_per_tco2": self.destination.carbon_price_usd_per_tco2,
            "carbon_tax_usd_per_tco2": self.destination.carbon_tax_usd_per_tco2,
            "durable_removal_credit_usd_per_tco2": self.destination.durable_removal_credit_usd_per_tco2,
            "capture_cost_usd_per_tco2": self.source.capture_cost_usd_per_tco2,
            "capture_emissions_kgco2e_per_tco2": self.source.capture_emissions_kgco2e_per_tco2,
            "capture_energy_kwh_per_tco2": self.source.capture_energy_kwh_per_tco2,
            "capture_energy_cost_usd_per_tco2": self.capture_energy_cost_usd_per_tco2,
            "capture_energy_emissions_kgco2e_per_tco2": self.capture_energy_emissions_kgco2e_per_tco2,
            "source_co2_purity_fraction": self.source.co2_purity_fraction,
            "required_co2_purity_fraction": self.destination.min_co2_purity_fraction,
            "source_pressure_bar": self.source.capture_pressure_bar,
            "required_pressure_bar": self.destination.required_pressure_bar,
            "sox_ppm": self.source.sox_ppm,
            "nox_ppm": self.source.nox_ppm,
            "h2s_ppm": self.source.h2s_ppm,
            "o2_percent": self.source.o2_percent,
            "water_ppm": self.source.water_ppm,
            "spec_cost_usd_per_tco2": self.spec_cost_usd_per_tco2,
            "spec_emissions_kgco2e_per_tco2": self.spec_emissions_kgco2e_per_tco2,
            "transport_cost_usd_per_tco2": self.transport_cost_usd_per_tco2,
            "transport_emissions_kgco2e_per_tco2": self.transport_emissions_kgco2e_per_tco2,
            "water_m3_per_tco2": self.water_m3_per_tco2,
            "land_m2_per_tpa_co2": self.land_m2_per_tpa_co2,
            "land_cost_usd_per_tco2": self.land_cost_usd_per_tco2,
            "risk_cost_usd_per_tco2": self.risk_cost_usd_per_tco2,
            "capex_learning_multiplier": self.capex_learning_multiplier,
            "opex_learning_multiplier": self.opex_learning_multiplier,
            "product_kg_per_tco2": inv.product_kg,
            "h2_kg_per_tco2": inv.h2_kg,
            "electricity_kwh_per_tco2": inv.electricity_kwh,
            "solar_input_kwh_per_tco2": inv.solar_input_kwh,
            "co2_stored_kg_per_tco2": inv.co2_stored_kg,
            "carbon_residence_years": inv.carbon_residence_years,
            "adjusted_induced_kgco2e_per_tco2": self.adjusted_induced_kgco2e_per_tco2,
            "adjusted_net_avoided_kgco2e_per_tco2": self.adjusted_net_avoided_kgco2e_per_tco2,
            "adjusted_gross_cost_usd_per_tco2": self.adjusted_gross_cost_usd_per_tco2,
            "adjusted_net_cost_usd_per_tco2": self.adjusted_net_cost_usd_per_tco2,
            "adjusted_abatement_cost_usd_per_tco2": self.adjusted_abatement_cost_usd_per_tco2,
            "adjusted_removal_cost_usd_per_tco2": self.adjusted_removal_cost_usd_per_tco2,
        }


def _read_rows(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def _float(row: dict[str, str], key: str, default: float) -> float:
    value = row.get(key, "")
    return default if value == "" else float(value)


def _int(row: dict[str, str], key: str, default: int) -> int:
    value = row.get(key, "")
    return default if value == "" else int(float(value))


def _split_list(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(";") if item.strip())


def load_sources(path: str | Path) -> list[Source]:
    return [
        Source(
            source_id=row["source_id"],
            region=row["region"],
            source_type=row["source_type"],
            latitude=float(row["latitude"]),
            longitude=float(row["longitude"]),
            co2_available_mtpa=float(row["co2_available_mtpa"]),
            capture_cost_usd_per_tco2=float(row["capture_cost_usd_per_tco2"]),
            capture_emissions_kgco2e_per_tco2=float(row["capture_emissions_kgco2e_per_tco2"]),
            capture_energy_kwh_per_tco2=_float(row, "capture_energy_kwh_per_tco2", 0.0),
            co2_purity_fraction=float(row["co2_purity_fraction"]),
            capture_pressure_bar=_float(row, "capture_pressure_bar", 1.2),
            sox_ppm=_float(row, "sox_ppm", 0.0),
            nox_ppm=_float(row, "nox_ppm", 0.0),
            h2s_ppm=_float(row, "h2s_ppm", 0.0),
            o2_percent=_float(row, "o2_percent", 0.0),
            water_ppm=_float(row, "water_ppm", 0.0),
            annual_capacity_factor=_float(row, "annual_capacity_factor", 0.9),
        )
        for row in _read_rows(path)
    ]


def load_destinations(path: str | Path) -> list[Destination]:
    return [
        Destination(
            destination_id=row["destination_id"],
            region=row["region"],
            sink_type=row["sink_type"],
            latitude=float(row["latitude"]),
            longitude=float(row["longitude"]),
            allowed_pathways=_split_list(row["allowed_pathways"]),
            capacity_mtco2_per_year=float(row["capacity_mtco2_per_year"]),
            electricity_price_usd_per_mwh=float(row["electricity_price_usd_per_mwh"]),
            grid_emissions_kgco2e_per_mwh=float(row["grid_emissions_kgco2e_per_mwh"]),
            h2_price_usd_per_kg=float(row["h2_price_usd_per_kg"]),
            h2_emissions_kgco2e_per_kg=float(row["h2_emissions_kgco2e_per_kg"]),
            carbon_price_usd_per_tco2=_float(row, "carbon_price_usd_per_tco2", 0.0),
            carbon_tax_usd_per_tco2=_float(row, "carbon_tax_usd_per_tco2", 0.0),
            durable_removal_credit_usd_per_tco2=_float(row, "durable_removal_credit_usd_per_tco2", 0.0),
            heat_price_usd_per_gj=_float(row, "heat_price_usd_per_gj", 6.0),
            min_co2_purity_fraction=_float(row, "min_co2_purity_fraction", 0.95),
            required_pressure_bar=_float(row, "required_pressure_bar", 110.0),
            max_sox_ppm=_float(row, "max_sox_ppm", 10.0),
            max_nox_ppm=_float(row, "max_nox_ppm", 10.0),
            max_h2s_ppm=_float(row, "max_h2s_ppm", 1.0),
            max_o2_percent=_float(row, "max_o2_percent", 2.0),
            max_water_ppm=_float(row, "max_water_ppm", 50.0),
            purification_cost_usd_per_tco2_per_fraction=_float(row, "purification_cost_usd_per_tco2_per_fraction", 120.0),
            purification_emissions_kgco2e_per_tco2_per_fraction=_float(row, "purification_emissions_kgco2e_per_tco2_per_fraction", 80.0),
            impurity_removal_cost_usd_per_tco2_per_index=_float(row, "impurity_removal_cost_usd_per_tco2_per_index", 8.0),
            impurity_removal_emissions_kgco2e_per_tco2_per_index=_float(row, "impurity_removal_emissions_kgco2e_per_tco2_per_index", 3.0),
            pressure_boost_kwh_per_tco2_per_ln_ratio=_float(row, "pressure_boost_kwh_per_tco2_per_ln_ratio", 24.0),
            h2_supply_mode=row.get("h2_supply_mode") or "market",
            electrolyzer_capex_usd_per_kw=_float(row, "electrolyzer_capex_usd_per_kw", 700.0),
            electrolyzer_kwh_per_kg_h2=_float(row, "electrolyzer_kwh_per_kg_h2", 52.0),
            electrolyzer_capacity_factor=_float(row, "electrolyzer_capacity_factor", 0.55),
            electrolyzer_lifetime_years=_int(row, "electrolyzer_lifetime_years", 15),
            electrolyzer_fixed_om_fraction=_float(row, "electrolyzer_fixed_om_fraction", 0.03),
            h2_compression_storage_cost_usd_per_kg=_float(row, "h2_compression_storage_cost_usd_per_kg", 0.25),
            water_l_per_kg_h2=_float(row, "water_l_per_kg_h2", 15.0),
            water_price_usd_per_m3=_float(row, "water_price_usd_per_m3", 1.0),
            water_emissions_kgco2e_per_m3=_float(row, "water_emissions_kgco2e_per_m3", 0.4),
            hourly_profile_id=row.get("hourly_profile_id") or "",
            electricity_procurement_mode=row.get("electricity_procurement_mode") or "annual_average",
            flexible_load_fraction=_float(row, "flexible_load_fraction", 1.0),
            water_available_m3_per_year=_float(row, "water_available_m3_per_year", 1e12),
            land_available_km2=_float(row, "land_available_km2", 1e9),
            land_cost_usd_per_m2_year=_float(row, "land_cost_usd_per_m2_year", 0.0),
            permit_risk_cost_usd_per_tco2=_float(row, "permit_risk_cost_usd_per_tco2", 0.0),
            trl_risk_premium_fraction=_float(row, "trl_risk_premium_fraction", 0.0),
        )
        for row in _read_rows(path)
    ]


def load_transport_modes(path: str | Path) -> list[TransportMode]:
    return [
        TransportMode(
            mode=row["mode"],
            min_distance_km=float(row["min_distance_km"]),
            max_distance_km=float(row["max_distance_km"]),
            route_factor=float(row["route_factor"]),
            fixed_cost_usd_per_tco2=float(row["fixed_cost_usd_per_tco2"]),
            cost_usd_per_tkm=float(row["cost_usd_per_tkm"]),
            emissions_kgco2e_per_tkm=float(row["emissions_kgco2e_per_tkm"]),
            reference_flow_mtpa=_float(row, "reference_flow_mtpa", 10.0),
            scale_exponent=_float(row, "scale_exponent", 0.25),
            min_scale_multiplier=_float(row, "min_scale_multiplier", 0.55),
            max_scale_multiplier=_float(row, "max_scale_multiplier", 2.5),
        )
        for row in _read_rows(path)
    ]


def load_hubs(path: str | Path | None) -> list[Hub]:
    if path is None or not Path(path).exists():
        return []
    return [
        Hub(
            hub_id=row["hub_id"],
            region=row["region"],
            latitude=float(row["latitude"]),
            longitude=float(row["longitude"]),
            capacity_mtco2_per_year=float(row["capacity_mtco2_per_year"]),
            compression_cost_usd_per_tco2=float(row["compression_cost_usd_per_tco2"]),
            compression_emissions_kgco2e_per_tco2=float(row["compression_emissions_kgco2e_per_tco2"]),
        )
        for row in _read_rows(path)
    ]


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(d_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2.0) ** 2
    )
    return 2.0 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def _transport_scale(mode: TransportMode, flow_mtpa: float) -> float:
    raw = (mode.reference_flow_mtpa / max(flow_mtpa, 1e-6)) ** mode.scale_exponent
    return min(mode.max_scale_multiplier, max(mode.min_scale_multiplier, raw))


def _transport_cost_and_emissions(
    mode: TransportMode,
    routed_distance_km: float,
    flow_mtpa: float,
    scale_multiplier: float,
    scenario: Scenario,
    electricity: EffectiveElectricity,
) -> tuple[float, float]:
    if mode.mode.startswith("pipeline"):
        cost = pipeline_transport_cost(
            distance_km=routed_distance_km,
            flow_mtpa=max(flow_mtpa, 1e-9),
            electricity_price_usd_per_mwh=electricity.price_usd_per_mwh,
            discount_rate=scenario.discount_rate,
            lifetime_years=scenario.plant_lifetime_years,
            capacity_factor=scenario.capacity_factor,
        ).levelized_cost_usd_per_tco2
        emissions = pipeline_transport_emissions_kgco2e_per_tco2(
            routed_distance_km,
            electricity.emissions_kgco2e_per_mwh,
        )
        return cost, emissions
    cost = routed_distance_km * mode.cost_usd_per_tkm * scale_multiplier
    emissions = routed_distance_km * mode.emissions_kgco2e_per_tkm
    return cost, emissions


def _effective_electricity(
    destination: Destination,
    hourly_profiles: dict[str, list[HourlyPoint]] | None,
) -> EffectiveElectricity:
    points = (hourly_profiles or {}).get(destination.hourly_profile_id, [])
    return effective_electricity(
        points,
        destination.electricity_procurement_mode,
        destination.flexible_load_fraction,
        destination.electricity_price_usd_per_mwh,
        destination.grid_emissions_kgco2e_per_mwh,
    )


def _hydrogen_supply(
    destination: Destination,
    base: Scenario,
    electricity: EffectiveElectricity,
) -> HydrogenSupply:
    mode = destination.h2_supply_mode.lower().strip()
    if mode == "market":
        return market_hydrogen(
            destination.h2_price_usd_per_kg,
            destination.h2_emissions_kgco2e_per_kg,
        )
    if mode == "electrolysis":
        return electrolytic_hydrogen(
            electricity_price_usd_per_mwh=electricity.price_usd_per_mwh,
            grid_emissions_kgco2e_per_mwh=electricity.emissions_kgco2e_per_mwh,
            electrolyzer_capex_usd_per_kw=destination.electrolyzer_capex_usd_per_kw,
            electrolyzer_kwh_per_kg=destination.electrolyzer_kwh_per_kg_h2,
            electrolyzer_capacity_factor=destination.electrolyzer_capacity_factor,
            electrolyzer_lifetime_years=destination.electrolyzer_lifetime_years,
            discount_rate=base.discount_rate,
            fixed_om_fraction_of_capex_per_year=destination.electrolyzer_fixed_om_fraction,
            water_l_per_kg=destination.water_l_per_kg_h2,
            water_price_usd_per_m3=destination.water_price_usd_per_m3,
            water_emissions_kgco2e_per_m3=destination.water_emissions_kgco2e_per_m3,
            compression_storage_cost_usd_per_kg=destination.h2_compression_storage_cost_usd_per_kg,
        )
    raise ValueError(f"Unknown hydrogen supply mode: {destination.h2_supply_mode}")


def _destination_scenario(
    base: Scenario,
    destination: Destination,
    transport_mode: TransportMode,
    routed_distance_km: float,
    electricity: EffectiveElectricity,
    hydrogen: HydrogenSupply,
) -> Scenario:
    return base.with_updates(
        electricity_price_usd_per_mwh=electricity.price_usd_per_mwh,
        h2_price_usd_per_kg=hydrogen.price_usd_per_kg,
        heat_price_usd_per_gj=destination.heat_price_usd_per_gj,
        carbon_price_usd_per_tco2=destination.carbon_price_usd_per_tco2,
        carbon_tax_usd_per_tco2=destination.carbon_tax_usd_per_tco2,
        durable_removal_credit_usd_per_tco2=destination.durable_removal_credit_usd_per_tco2,
        co2_transport_distance_km=0.0,
        co2_transport_cost_usd_per_tkm=0.0,
        co2_transport_emissions_kgco2e_per_tkm=0.0,
        grid_emissions_kgco2e_per_mwh=electricity.emissions_kgco2e_per_mwh,
        h2_emissions_kgco2e_per_kg=hydrogen.emissions_kgco2e_per_kg,
    )


def _impurity_index(source: Source, destination: Destination) -> float:
    return (
        max(0.0, source.sox_ppm - destination.max_sox_ppm) / max(destination.max_sox_ppm, 1e-9)
        + max(0.0, source.nox_ppm - destination.max_nox_ppm) / max(destination.max_nox_ppm, 1e-9)
        + max(0.0, source.h2s_ppm - destination.max_h2s_ppm) / max(destination.max_h2s_ppm, 1e-9)
        + max(0.0, source.o2_percent - destination.max_o2_percent) / max(destination.max_o2_percent, 1e-9)
        + max(0.0, source.water_ppm - destination.max_water_ppm) / max(destination.max_water_ppm, 1e-9)
    )


def _spec_costs(
    source: Source,
    destination: Destination,
    electricity: EffectiveElectricity,
) -> tuple[float, float]:
    purity_gap = max(0.0, destination.min_co2_purity_fraction - source.co2_purity_fraction)
    purity_cost = purity_gap * destination.purification_cost_usd_per_tco2_per_fraction
    purity_emissions = purity_gap * destination.purification_emissions_kgco2e_per_tco2_per_fraction
    impurity_index = _impurity_index(source, destination)
    impurity_cost = impurity_index * destination.impurity_removal_cost_usd_per_tco2_per_index
    impurity_emissions = impurity_index * destination.impurity_removal_emissions_kgco2e_per_tco2_per_index
    pressure_ratio = max(destination.required_pressure_bar, 1e-9) / max(source.capture_pressure_bar, 1e-9)
    pressure_kwh = max(0.0, math.log(pressure_ratio)) * destination.pressure_boost_kwh_per_tco2_per_ln_ratio
    pressure_cost = pressure_kwh / 1000.0 * electricity.price_usd_per_mwh
    pressure_emissions = pressure_kwh / 1000.0 * electricity.emissions_kgco2e_per_mwh
    return (
        purity_cost + impurity_cost + pressure_cost,
        purity_emissions + impurity_emissions + pressure_emissions,
    )


def _capex_component_usd_per_tco2(evaluation: Evaluation, scenario: Scenario) -> float:
    crf = capital_recovery_factor(scenario.discount_rate, scenario.plant_lifetime_years)
    return evaluation.inventory.capex_usd_per_tpa_co2 * crf / max(scenario.capacity_factor, 1e-6)


def _adjust_candidate(
    source: Source,
    destination: Destination,
    mode: TransportMode,
    hub: Hub | None,
    distance_km: float,
    routed_distance_km: float,
    scale_multiplier: float,
    evaluation: Evaluation,
    scenario: Scenario,
    electricity: EffectiveElectricity,
    hydrogen: HydrogenSupply,
    learning_rows: list[LearningRow] | None,
    technology_year: int,
) -> SpatialCandidate:
    inv = evaluation.inventory
    feed_t = inv.co2_feed_tonnes
    spec_cost, spec_emissions = _spec_costs(source, destination, electricity)
    capture_energy_cost = source.capture_energy_kwh_per_tco2 / 1000.0 * electricity.price_usd_per_mwh
    capture_energy_emissions = source.capture_energy_kwh_per_tco2 / 1000.0 * electricity.emissions_kgco2e_per_mwh
    capture_total_cost = source.capture_cost_usd_per_tco2 + capture_energy_cost
    capture_total_emissions = source.capture_emissions_kgco2e_per_tco2 + capture_energy_emissions
    hub_cost = hub.compression_cost_usd_per_tco2 if hub else 0.0
    hub_emissions = hub.compression_emissions_kgco2e_per_tco2 if hub else 0.0
    variable_transport_cost, variable_transport_emissions = _transport_cost_and_emissions(
        mode,
        routed_distance_km,
        source.co2_available_mtpa,
        scale_multiplier,
        scenario,
        electricity,
    )
    transport_cost = mode.fixed_cost_usd_per_tco2 + variable_transport_cost + hub_cost
    transport_emissions = variable_transport_emissions + hub_emissions
    capex_mult, fixed_mult, variable_mult = learning_multipliers(
        learning_rows or [],
        technology_year,
        inv.pathway,
        inv.technology_family,
    )
    capex_component = _capex_component_usd_per_tco2(evaluation, scenario)
    capex_delta = capex_component * (capex_mult - 1.0)
    opex_component = inv.fixed_opex_usd_per_tco2 + inv.variable_opex_usd_per_tco2
    opex_delta = opex_component * ((fixed_mult + variable_mult) / 2.0 - 1.0)
    risk_cost = capex_component * destination.trl_risk_premium_fraction + destination.permit_risk_cost_usd_per_tco2
    water_m3 = inv.water_kg / 1000.0 + inv.h2_kg * hydrogen.water_l_per_kg / 1000.0
    land_cost = inv.land_m2 * destination.land_cost_usd_per_m2_year

    adjusted_induced = (
        evaluation.lca.induced_emissions_kgco2e
        + capture_total_emissions * feed_t
        + spec_emissions * feed_t
        + transport_emissions * feed_t
    )
    adjusted_net_avoided = (
        evaluation.lca.net_avoided_kgco2e
        - capture_total_emissions * feed_t
        - spec_emissions * feed_t
        - transport_emissions * feed_t
    )
    adjusted_gross_cost = (
        evaluation.economics.gross_cost_usd_per_tco2
        + capture_total_cost
        + spec_cost
        + transport_cost
        + capex_delta
        + opex_delta
        + land_cost
        + risk_cost
    )
    avoided_t = adjusted_net_avoided / 1000.0
    carbon_credit = max(0.0, avoided_t) * scenario.carbon_price_usd_per_tco2 / feed_t
    removal_credit_kg = max(0.0, evaluation.lca.durable_retained_kgco2 - adjusted_induced)
    durable_credit = removal_credit_kg / 1000.0 * scenario.durable_removal_credit_usd_per_tco2 / feed_t
    taxable_t = max(0.0, (adjusted_induced + inv.co2_released_end_of_life_kg) / 1000.0)
    carbon_tax = taxable_t * scenario.carbon_tax_usd_per_tco2 / feed_t
    cost_before_credit = adjusted_gross_cost - evaluation.economics.product_revenue_usd_per_tco2
    adjusted_net_cost = cost_before_credit - carbon_credit - durable_credit + carbon_tax
    adjusted_abatement = cost_before_credit / avoided_t if avoided_t > 0 else math.inf
    retained_t = evaluation.lca.durable_retained_kgco2 / 1000.0
    adjusted_removal = cost_before_credit / retained_t if retained_t > 0 else math.inf
    return SpatialCandidate(
        source=source,
        destination=destination,
        transport_mode=mode,
        hub=hub,
        distance_km=distance_km,
        routed_distance_km=routed_distance_km,
        transport_scale_multiplier=scale_multiplier,
        evaluation=evaluation,
        effective_electricity=electricity,
        hydrogen_supply=hydrogen,
        capture_energy_cost_usd_per_tco2=capture_energy_cost,
        capture_energy_emissions_kgco2e_per_tco2=capture_energy_emissions,
        spec_cost_usd_per_tco2=spec_cost,
        spec_emissions_kgco2e_per_tco2=spec_emissions,
        transport_cost_usd_per_tco2=transport_cost,
        transport_emissions_kgco2e_per_tco2=transport_emissions,
        water_m3_per_tco2=water_m3,
        land_m2_per_tpa_co2=inv.land_m2,
        land_cost_usd_per_tco2=land_cost,
        risk_cost_usd_per_tco2=risk_cost,
        capex_learning_multiplier=capex_mult,
        opex_learning_multiplier=(fixed_mult + variable_mult) / 2.0,
        adjusted_induced_kgco2e_per_tco2=adjusted_induced,
        adjusted_net_avoided_kgco2e_per_tco2=adjusted_net_avoided,
        adjusted_gross_cost_usd_per_tco2=adjusted_gross_cost,
        adjusted_net_cost_usd_per_tco2=adjusted_net_cost,
        adjusted_abatement_cost_usd_per_tco2=adjusted_abatement,
        adjusted_removal_cost_usd_per_tco2=adjusted_removal,
    )


def _route_options(
    source: Source,
    destination: Destination,
    hubs: Iterable[Hub],
) -> list[tuple[Hub | None, float]]:
    direct = haversine_km(source.latitude, source.longitude, destination.latitude, destination.longitude)
    options: list[tuple[Hub | None, float]] = [(None, direct)]
    for hub in hubs:
        via = haversine_km(source.latitude, source.longitude, hub.latitude, hub.longitude)
        via += haversine_km(hub.latitude, hub.longitude, destination.latitude, destination.longitude)
        if via <= direct * 1.8:
            options.append((hub, via))
    return options


def generate_spatial_candidates(
    sources: Iterable[Source],
    destinations: Iterable[Destination],
    transport_modes: Iterable[TransportMode],
    base: Scenario | None = None,
    max_distance_km: float | None = None,
    hubs: Iterable[Hub] | None = None,
    hourly_profiles: dict[str, list[HourlyPoint]] | None = None,
    learning_rows: list[LearningRow] | None = None,
    technology_year: int = 2030,
) -> list[SpatialCandidate]:
    base_scenario = base or Scenario()
    hub_list = list(hubs or [])
    candidates: list[SpatialCandidate] = []
    for source in sources:
        for destination in destinations:
            electricity = _effective_electricity(destination, hourly_profiles)
            hydrogen = _hydrogen_supply(destination, base_scenario, electricity)
            for hub, distance in _route_options(source, destination, hub_list):
                if max_distance_km is not None and distance > max_distance_km:
                    continue
                for mode in transport_modes:
                    routed_distance = distance * mode.route_factor
                    if not mode.supports(routed_distance):
                        continue
                    scale_multiplier = _transport_scale(mode, source.co2_available_mtpa)
                    scenario = _destination_scenario(
                        base_scenario,
                        destination,
                        mode,
                        routed_distance,
                        electricity,
                        hydrogen,
                    )
                    for evaluation in evaluate_all(scenario):
                        if evaluation.inventory.pathway not in destination.allowed_pathways:
                            continue
                        if evaluation.lca.net_avoided_kgco2e < scenario.min_net_avoided_kgco2e_per_tco2:
                            continue
                        candidate = _adjust_candidate(
                            source,
                            destination,
                            mode,
                            hub,
                            distance,
                            routed_distance,
                            scale_multiplier,
                            evaluation,
                            scenario,
                            electricity,
                            hydrogen,
                            learning_rows,
                            technology_year,
                        )
                        if candidate.adjusted_net_avoided_kgco2e_per_tco2 < scenario.min_net_avoided_kgco2e_per_tco2:
                            continue
                        candidates.append(candidate)
    return candidates


def rank_spatial_candidates(
    candidates: Iterable[SpatialCandidate],
    metric: str = "adjusted_net_cost",
) -> list[SpatialCandidate]:
    if metric == "adjusted_net_cost":
        key = lambda c: c.adjusted_net_cost_usd_per_tco2
    elif metric == "adjusted_abatement_cost":
        key = lambda c: c.adjusted_abatement_cost_usd_per_tco2
    elif metric == "adjusted_removal_cost":
        key = lambda c: c.adjusted_removal_cost_usd_per_tco2
    else:
        raise ValueError(f"Unknown spatial metric: {metric}")
    finite = [candidate for candidate in candidates if math.isfinite(key(candidate))]
    return sorted(finite, key=key)


def _record_allocation(candidate: SpatialCandidate, amount: float, optimizer: str) -> dict[str, float | str]:
    record = candidate.flat_record()
    record["allocated_mtco2_per_year"] = amount
    record["annual_net_cost_musd_per_year"] = amount * candidate.adjusted_net_cost_usd_per_tco2
    record["annual_net_avoided_mtco2e_per_year"] = amount * candidate.adjusted_net_avoided_kgco2e_per_tco2 / 1000.0
    record["annual_water_m3_per_year"] = amount * 1e6 * candidate.water_m3_per_tco2
    record["annual_land_m2"] = amount * 1e6 * candidate.land_m2_per_tpa_co2
    record["optimizer"] = optimizer
    return record


def greedy_allocate(
    candidates: Iterable[SpatialCandidate],
    metric: str = "adjusted_net_cost",
) -> list[dict[str, float | str]]:
    ranked = rank_spatial_candidates(candidates, metric=metric)
    source_remaining = {c.source.source_id: c.source.co2_available_mtpa for c in ranked}
    destination_remaining = {c.destination.destination_id: c.destination.capacity_mtco2_per_year for c in ranked}
    pathway_remaining = {c.pathway: c.pathway_market_capacity_mtpa for c in ranked}
    hub_remaining = {c.hub.hub_id: c.hub.capacity_mtco2_per_year for c in ranked if c.hub}
    water_remaining = {c.destination.destination_id: c.destination.water_available_m3_per_year for c in ranked}
    land_remaining = {c.destination.destination_id: c.destination.land_available_km2 * 1e6 for c in ranked}
    allocations: list[dict[str, float | str]] = []
    for candidate in ranked:
        amount_limits = [
            source_remaining[candidate.source.source_id],
            destination_remaining[candidate.destination.destination_id],
            pathway_remaining[candidate.pathway],
        ]
        if candidate.hub:
            amount_limits.append(hub_remaining[candidate.hub.hub_id])
        if candidate.water_m3_per_tco2 > 0:
            amount_limits.append(water_remaining[candidate.destination.destination_id] / (candidate.water_m3_per_tco2 * 1e6))
        if candidate.land_m2_per_tpa_co2 > 0:
            amount_limits.append(land_remaining[candidate.destination.destination_id] / (candidate.land_m2_per_tpa_co2 * 1e6))
        amount = min(amount_limits)
        if amount <= 1e-9:
            continue
        source_remaining[candidate.source.source_id] -= amount
        destination_remaining[candidate.destination.destination_id] -= amount
        pathway_remaining[candidate.pathway] -= amount
        if candidate.hub:
            hub_remaining[candidate.hub.hub_id] -= amount
        water_remaining[candidate.destination.destination_id] -= amount * 1e6 * candidate.water_m3_per_tco2
        land_remaining[candidate.destination.destination_id] -= amount * 1e6 * candidate.land_m2_per_tpa_co2
        allocations.append(_record_allocation(candidate, amount, "greedy"))
    return allocations


def optimize_allocate(
    candidates: Iterable[SpatialCandidate],
    metric: str = "adjusted_net_cost",
    minimum_source_fraction: float = 1.0,
    target_total_mtco2_per_year: float | None = None,
    target_source_fraction: float | None = None,
) -> list[dict[str, float | str]]:
    try:
        from scipy.optimize import linprog
    except ImportError as exc:
        raise RuntimeError("scipy is required for optimize_allocate") from exc

    ranked = list(candidates)
    if not ranked:
        return []
    if metric == "adjusted_net_cost":
        objective = [c.adjusted_net_cost_usd_per_tco2 for c in ranked]
    elif metric == "adjusted_abatement_cost":
        objective = [c.adjusted_abatement_cost_usd_per_tco2 for c in ranked]
    elif metric == "adjusted_removal_cost":
        objective = [c.adjusted_removal_cost_usd_per_tco2 for c in ranked]
    else:
        raise ValueError(f"Unknown spatial metric: {metric}")

    source_ids = sorted({c.source.source_id for c in ranked})
    destination_ids = sorted({c.destination.destination_id for c in ranked})
    pathway_ids = sorted({c.pathway for c in ranked})
    hub_ids = sorted({c.hub.hub_id for c in ranked if c.hub})
    source_capacity = {c.source.source_id: c.source.co2_available_mtpa for c in ranked}
    destination_capacity = {c.destination.destination_id: c.destination.capacity_mtco2_per_year for c in ranked}
    pathway_capacity = {c.pathway: c.pathway_market_capacity_mtpa for c in ranked}
    hub_capacity = {c.hub.hub_id: c.hub.capacity_mtco2_per_year for c in ranked if c.hub}
    water_capacity = {c.destination.destination_id: c.destination.water_available_m3_per_year for c in ranked}
    land_capacity = {c.destination.destination_id: c.destination.land_available_km2 * 1e6 for c in ranked}

    total_source_capacity = sum(source_capacity.values())
    if target_total_mtco2_per_year is not None and target_source_fraction is not None:
        raise ValueError("Use either target_total_mtco2_per_year or target_source_fraction, not both")
    target_total = target_total_mtco2_per_year
    if target_source_fraction is not None:
        target_total = total_source_capacity * target_source_fraction

    a_ub: list[list[float]] = []
    b_ub: list[float] = []
    a_eq: list[list[float]] = []
    b_eq: list[float] = []
    for source_id in source_ids:
        row = [1.0 if c.source.source_id == source_id else 0.0 for c in ranked]
        a_ub.append(row)
        b_ub.append(source_capacity[source_id])
        if minimum_source_fraction > 0:
            a_ub.append([-value for value in row])
            b_ub.append(-source_capacity[source_id] * minimum_source_fraction)
    for destination_id in destination_ids:
        a_ub.append([1.0 if c.destination.destination_id == destination_id else 0.0 for c in ranked])
        b_ub.append(destination_capacity[destination_id])
        a_ub.append([
            c.water_m3_per_tco2 * 1e6 if c.destination.destination_id == destination_id else 0.0
            for c in ranked
        ])
        b_ub.append(water_capacity[destination_id])
        a_ub.append([
            c.land_m2_per_tpa_co2 * 1e6 if c.destination.destination_id == destination_id else 0.0
            for c in ranked
        ])
        b_ub.append(land_capacity[destination_id])
    for pathway in pathway_ids:
        a_ub.append([1.0 if c.pathway == pathway else 0.0 for c in ranked])
        b_ub.append(pathway_capacity[pathway])
    for hub_id in hub_ids:
        a_ub.append([1.0 if c.hub and c.hub.hub_id == hub_id else 0.0 for c in ranked])
        b_ub.append(hub_capacity[hub_id])

    if target_total is not None:
        if target_total < 0:
            raise ValueError("target allocation must be non-negative")
        if minimum_source_fraction > 0 and target_total < total_source_capacity * minimum_source_fraction - 1e-9:
            raise ValueError("target allocation is below the requested minimum_source_fraction")
        a_eq.append([1.0] * len(ranked))
        b_eq.append(target_total)

    result = linprog(
        c=objective,
        A_ub=a_ub,
        b_ub=b_ub,
        A_eq=a_eq or None,
        b_eq=b_eq or None,
        bounds=[(0, None)] * len(ranked),
        method="highs",
    )
    if not result.success:
        raise RuntimeError(f"Spatial LP allocation failed: {result.message}")
    return [
        _record_allocation(candidate, float(amount), "linear_program")
        for candidate, amount in zip(ranked, result.x)
        if amount > 1e-7
    ]


def summarize_allocations(
    allocations: Iterable[dict[str, float | str]],
) -> list[dict[str, float | str]]:
    rows = list(allocations)
    total_allocated = sum(float(row["allocated_mtco2_per_year"]) for row in rows)
    total_cost = sum(float(row["annual_net_cost_musd_per_year"]) for row in rows)
    total_avoided = sum(float(row["annual_net_avoided_mtco2e_per_year"]) for row in rows)
    total_water = sum(float(row.get("annual_water_m3_per_year", 0.0)) for row in rows)
    total_land = sum(float(row.get("annual_land_m2", 0.0)) for row in rows)
    summary = [
        {
            "scope": "system_total",
            "allocated_mtco2_per_year": total_allocated,
            "annual_net_cost_musd_per_year": total_cost,
            "annual_net_avoided_mtco2e_per_year": total_avoided,
            "annual_water_m3_per_year": total_water,
            "annual_land_m2": total_land,
            "weighted_net_cost_usd_per_tco2": total_cost / total_allocated if total_allocated > 0 else math.inf,
            "weighted_net_avoided_tco2e_per_tco2": total_avoided / total_allocated if total_allocated > 0 else 0.0,
        }
    ]
    by_family: dict[str, dict[str, float]] = {}
    for row in rows:
        family = str(row["technology_family"])
        bucket = by_family.setdefault(family, {"allocated": 0.0, "cost": 0.0, "avoided": 0.0})
        bucket["allocated"] += float(row["allocated_mtco2_per_year"])
        bucket["cost"] += float(row["annual_net_cost_musd_per_year"])
        bucket["avoided"] += float(row["annual_net_avoided_mtco2e_per_year"])
    for family, bucket in sorted(by_family.items()):
        allocated = bucket["allocated"]
        summary.append(
            {
                "scope": f"technology_family:{family}",
                "allocated_mtco2_per_year": allocated,
                "annual_net_cost_musd_per_year": bucket["cost"],
                "annual_net_avoided_mtco2e_per_year": bucket["avoided"],
                "weighted_net_cost_usd_per_tco2": bucket["cost"] / allocated if allocated > 0 else math.inf,
                "weighted_net_avoided_tco2e_per_tco2": bucket["avoided"] / allocated if allocated > 0 else 0.0,
            }
        )
    return summary
